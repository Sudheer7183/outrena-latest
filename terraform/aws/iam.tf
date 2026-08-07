# iam.tf — IAM roles + policies for ECS task execution + per-service task roles.
#
# Two role classes:
#   1. Task EXECUTION role — assumed by ECS agent to pull image, fetch
#      secrets, write logs. Same for all services (one role, attached policy
#      `AmazonECSTaskExecutionRolePolicy` AWS-managed + custom Secrets
#      Manager read for the per-env secrets list).
#   2. Task ROLE — assumed by the container itself for app-level AWS calls
#      (S3, KMS, Secrets Manager, CloudWatch). One per service so blast
#      radius is isolated.
#
# All ECS task defs (ecs_backend.tf etc.) reference:
#   execution_role_arn = aws_iam_role.ecs_task_execution.arn
#   task_role_arn      = aws_iam_role.<service>_task.arn

# ── Trust policy: ECS tasks ───────────────────────────────────────────────────
data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    sid     = "AllowECSTasksAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    # Lock down to the account's ECS service — prevents the "confused deputy"
    # attack where another account's ECS task assumes this role.
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:ecs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

# ── Task EXECUTION role (shared) ──────────────────────────────────────────────
resource "aws_iam_role" "ecs_task_execution" {
  name               = "${local.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "${local.name_prefix}-ecs-execution-role"
  }
}

# AWS-managed policy: gives the ECS agent permission to pull ECR images +
# write CloudWatch Logs.
resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Custom inline policy: allow the execution role to read all per-env secrets
# (DATABASE_URL, REDIS_AUTH_TOKEN, Keycloak admin, MailBridge URL, Keycloak DB)
# so it can inject them into the container as `secrets` entries.
data "aws_iam_policy_document" "ecs_execution_secrets" {
  statement {
    sid     = "ReadEnvSecrets"
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.rds_master.arn,
      aws_secretsmanager_secret.database_url.arn,
      aws_secretsmanager_secret.redis_auth.arn,
      aws_secretsmanager_secret.keycloak_admin.arn,
      aws_secretsmanager_secret.keycloak_db.arn,
      # MailBridge secret is conditional — use a wildcard to match either
      # existence state (Terraform will resolve to an empty list when count=0).
      "${local.name_prefix}-mailbridge-url", # name-only ARN fragment — actual ARN used below if exists
    ]
  }

  # KMS decrypt for secrets (all secrets are encrypted with the RDS KMS key).
  statement {
    sid     = "KmsDecryptSecrets"
    effect  = "Allow"
    actions = ["kms:Decrypt", "kms:DescribeKey"]
    resources = [
      aws_kms_key.rds.arn,
      aws_kms_key.redis.arn,
      aws_kms_key.s3.arn,
    ]
  }
}

# Apply secrets policy separately so the conditional mailbridge secret ARN
# (which may not exist in dev) doesn't break the plan.
resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "${local.name_prefix}-ecs-execution-secrets"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid    = "ReadEnvSecrets"
          Effect = "Allow"
          Action = "secretsmanager:GetSecretValue"
          Resource = [
            aws_secretsmanager_secret.rds_master.arn,
            aws_secretsmanager_secret.database_url.arn,
            aws_secretsmanager_secret.redis_auth.arn,
            aws_secretsmanager_secret.keycloak_admin.arn,
            aws_secretsmanager_secret.keycloak_db.arn,
          ]
        }
      ],
      var.mailbridge_url == "" ? [] : [
        {
          Sid    = "ReadMailbridgeSecret"
          Effect = "Allow"
          Action = "secretsmanager:GetSecretValue"
          Resource = [
            aws_secretsmanager_secret.mailbridge_url[0].arn,
          ]
        }
      ],
      [
        {
          Sid    = "KmsDecryptSecrets"
          Effect = "Allow"
          Action = ["kms:Decrypt", "kms:DescribeKey"]
          Resource = [
            aws_kms_key.rds.arn,
            aws_kms_key.redis.arn,
            aws_kms_key.s3.arn,
          ]
        }
      ]
    )
  })
}

# ── Backend task role ─────────────────────────────────────────────────────────
# App-level perms for the FastAPI container: S3 read/write (csv + collateral),
# Secrets Manager read (DATABASE_URL, REDIS_AUTH_TOKEN, MailBridge URL), KMS
# decrypt (S3 + Redis keys), CloudWatch Logs put (for direct-emit fallback).
resource "aws_iam_role" "backend_task" {
  name               = "${local.name_prefix}-backend-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "${local.name_prefix}-backend-task-role"
  }
}

# Inline policy doc for app-level perms. Combines:
#   - data.aws_iam_policy_document.s3_access (defined in s3.tf)
#   - Secrets Manager read for runtime secrets
#   - CloudWatch Logs put (for out-of-band log emission)
#   - KMS decrypt for S3 + Redis + RDS keys
data "aws_iam_policy_document" "backend_task" {
  source_policy_documents = [data.aws_iam_policy_document.s3_access.json]

  statement {
    sid    = "ReadRuntimeSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      aws_secretsmanager_secret.database_url.arn,
      aws_secretsmanager_secret.redis_auth.arn,
      aws_secretsmanager_secret.rds_master.arn,
    ]
  }

  statement {
    sid    = "CloudWatchLogsPut"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = [
      "${aws_cloudwatch_log_group.backend.arn}:*",
      "${aws_cloudwatch_log_group.worker.arn}:*",
    ]
  }

  statement {
    sid     = "KmsDecryptApp"
    effect  = "Allow"
    actions = ["kms:Decrypt", "kms:DescribeKey", "kms:GenerateDataKey"]
    resources = [
      aws_kms_key.rds.arn,
      aws_kms_key.redis.arn,
      aws_kms_key.s3.arn,
    ]
  }
}

resource "aws_iam_policy" "backend_task" {
  name        = "${local.name_prefix}-backend-task-policy"
  description = "App-level perms for OUTRENA backend + worker ECS tasks"
  policy      = data.aws_iam_policy_document.backend_task.json
}

resource "aws_iam_role_policy_attachment" "backend_task" {
  role       = aws_iam_role.backend_task.name
  policy_arn = aws_iam_policy.backend_task.arn
}

# ── Worker task role ──────────────────────────────────────────────────────────
# Same perms as backend (worker shares the image + needs DB/Redis/S3 access
# for Celery tasks like CSV import + scheduler tick).
resource "aws_iam_role" "worker_task" {
  name               = "${local.name_prefix}-worker-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "${local.name_prefix}-worker-task-role"
  }
}

resource "aws_iam_role_policy_attachment" "worker_task" {
  role       = aws_iam_role.worker_task.name
  policy_arn = aws_iam_policy.backend_task.arn
}

# ── Frontend task role (minimal) ──────────────────────────────────────────────
# nginx serves static files — only CloudWatch Logs put is needed.
resource "aws_iam_role" "frontend_task" {
  name               = "${local.name_prefix}-frontend-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "${local.name_prefix}-frontend-task-role"
  }
}

data "aws_iam_policy_document" "frontend_task" {
  statement {
    sid    = "CloudWatchLogsPut"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["${aws_cloudwatch_log_group.frontend.arn}:*"]
  }
}

resource "aws_iam_policy" "frontend_task" {
  name        = "${local.name_prefix}-frontend-task-policy"
  description = "Minimal perms for OUTRENA frontend ECS task (nginx static)"
  policy      = data.aws_iam_policy_document.frontend_task.json
}

resource "aws_iam_role_policy_attachment" "frontend_task" {
  role       = aws_iam_role.frontend_task.name
  policy_arn = aws_iam_policy.frontend_task.arn
}

# ── Keycloak task role ────────────────────────────────────────────────────────
# Keycloak needs: read its own DB password secret + CloudWatch Logs put +
# KMS decrypt for the RDS key (which encrypts the secrets).
resource "aws_iam_role" "keycloak_task" {
  name               = "${local.name_prefix}-keycloak-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "${local.name_prefix}-keycloak-task-role"
  }
}

data "aws_iam_policy_document" "keycloak_task" {
  statement {
    sid    = "ReadKeycloakSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      aws_secretsmanager_secret.keycloak_admin.arn,
      aws_secretsmanager_secret.keycloak_db.arn,
    ]
  }

  statement {
    sid    = "CloudWatchLogsPut"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["${aws_cloudwatch_log_group.keycloak.arn}:*"]
  }

  statement {
    sid       = "KmsDecryptKeycloak"
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:DescribeKey"]
    resources = [aws_kms_key.rds.arn]
  }
}

resource "aws_iam_policy" "keycloak_task" {
  name        = "${local.name_prefix}-keycloak-task-policy"
  description = "Perms for OUTRENA Keycloak ECS task"
  policy      = data.aws_iam_policy_document.keycloak_task.json
}

resource "aws_iam_role_policy_attachment" "keycloak_task" {
  role       = aws_iam_role.keycloak_task.name
  policy_arn = aws_iam_policy.keycloak_task.arn
}
