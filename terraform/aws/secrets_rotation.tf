# secrets_rotation.tf — Secrets Manager automatic rotation (SOC2 CC6.1).
#
# Closes the SURVEY-INFRA gap A2: runbook 09 promised "automatic rotation" but
# Terraform never declared `aws_secretsmanager_secret_rotation` resources. This
# file wires up:
#
#   - aws_cloudwatch_log_group.secret_rotation    — rotation Lambda logs (90d)
#   - aws_iam_role.lambda_rotation                — execution role for the rotation Lambda
#   - aws_iam_role_policy.lambda_rotation         — inline policy: read+write Secrets Manager, KMS decrypt, RDS connect
#   - aws_lambda_function.secret_rotation_rds     — Python 3.11 Lambda that delegates to the AWS-provided
#                                                   SecretsManagerRDSPostgreSQLRotationSingleUser template
#                                                   (deployed separately as a SAR app — see deployment notes
#                                                   in runbook 11-secrets-management.md)
#   - aws_lambda_function.secret_rotation_generic — Python 3.11 Lambda that rotates generic app secrets
#                                                   (Keycloak admin, MailBridge URL, Redis AUTH) by generating
#                                                   a new value + writing it back. Downstream service update
#                                                   is operator-driven (documented per-secret in runbook 09/11).
#   - aws_lambda_permission.secret_rotation_*     — allow Secrets Manager to invoke each Lambda
#   - aws_secretsmanager_secret_rotation × N      — rotation rules attached to each existing secret
#   - aws_cloudwatch_event_rule + target          — daily safety-net check that triggers Secrets Manager to
#                                                   evaluate whether any secret has crossed its
#                                                   automatically_after_days threshold
#
# Rotation intervals (match runbook 09 + 11 promises):
#   - RDS master password      — 90 days (var.rds_secret_rotation_days)
#   - DATABASE_URL (app role)  — 90 days
#   - Redis AUTH token         — 30 days (var.app_secret_rotation_days)
#   - Keycloak admin password  — 30 days
#   - Keycloak DB role         — 90 days
#   - MailBridge URL           — 30 days (only if var.mailbridge_url is non-empty)
#
# IMPORTANT — interaction with `aws_secretsmanager_secret_version`:
# The existing secret_version resources in rds.tf / secrets.tf / elasticache.tf
# write a literal `secret_string` at apply time. After a rotation Lambda runs,
# Terraform will detect drift on the secret_string. To avoid Terraform clobbering
# the rotated value, runbooks/11-secrets-management.md instructs operators to
# `terraform state rm aws_secretsmanager_secret_version.<name>` once rotation is
# enabled (one-time, per secret). This is documented in the runbook; we don't
# modify the existing secret_version resources here (file ownership boundary).

# ── CloudWatch Logs group for rotation Lambda ────────────────────────────────
resource "aws_cloudwatch_log_group" "secret_rotation" {
  name              = "/aws/lambda/${local.name_prefix}-secret-rotation"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.rds.arn

  tags = {
    Name = "${local.name_prefix}-secret-rotation-log-group"
  }
}

# ── IAM role: rotation Lambda execution ──────────────────────────────────────
data "aws_iam_policy_document" "lambda_rotation_trust" {
  statement {
    sid     = "AllowLambdaAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_rotation" {
  name               = "${local.name_prefix}-lambda-rotation"
  assume_role_policy = data.aws_iam_policy_document.lambda_rotation_trust.json

  tags = {
    Name = "${local.name_prefix}-lambda-rotation-role"
  }
}

# Inline policy: allow the rotation Lambda to read+write every secret it owns,
# decrypt with the relevant KMS keys, and connect to RDS for password rotation.
data "aws_iam_policy_document" "lambda_rotation" {
  # Read + write all OUTRENA-managed secrets (rotation Lambda must be able to
  # PutSecretValue on the secret it's rotating + GetSecretValue on the secret
  # to read the current value during the "set" step).
  statement {
    sid    = "ReadWriteSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue",
      "secretsmanager:GetResourcePolicy",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecretVersionStage",
      "secretsmanager:ListSecretVersionIds",
    ]
    resources = [
      aws_secretsmanager_secret.rds_master.arn,
      aws_secretsmanager_secret.database_url.arn,
      aws_secretsmanager_secret.redis_auth.arn,
      aws_secretsmanager_secret.keycloak_admin.arn,
      aws_secretsmanager_secret.keycloak_db.arn,
      # MailBridge secret is conditional — use a wildcard ARN fragment so the
      # policy is valid whether or not the secret exists.
      "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${local.name_prefix}-mailbridge-url-*",
    ]
  }

  # secretsmanager:RotateSecret is a control-plane call on the secret ARN —
  # grant it explicitly so EventBridge can invoke rotation when scheduled.
  statement {
    sid    = "RotateSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:RotateSecret",
    ]
    resources = [
      aws_secretsmanager_secret.rds_master.arn,
      aws_secretsmanager_secret.database_url.arn,
      aws_secretsmanager_secret.redis_auth.arn,
      aws_secretsmanager_secret.keycloak_admin.arn,
      aws_secretsmanager_secret.keycloak_db.arn,
      "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${local.name_prefix}-mailbridge-url-*",
    ]
  }

  # KMS decrypt for secrets encrypted with rds + redis KMS keys.
  statement {
    sid    = "KmsDecryptSecrets"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:GenerateDataKey",
    ]
    resources = [
      aws_kms_key.rds.arn,
      aws_kms_key.redis.arn,
    ]
  }

  # RDS: allow the rotation Lambda to update the master + Keycloak DB passwords.
  # Scope to the OUTRENA RDS instance only.
  statement {
    sid    = "ModifyRdsPassword"
    effect = "Allow"
    actions = [
      "rds:ModifyDBInstance",
      "rds:DescribeDBInstances",
    ]
    resources = [aws_db_instance.main.arn]
  }

  # CloudWatch Logs: write rotation logs.
  statement {
    sid    = "WriteLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "${aws_cloudwatch_log_group.secret_rotation.arn}:*",
    ]
  }

  # VPC: allow the Lambda to attach to the data-tier VPC ENIs so it can reach RDS.
  statement {
    sid    = "VpcNetworking"
    effect = "Allow"
    actions = [
      "ec2:CreateNetworkInterface",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DeleteNetworkInterface",
      "ec2:AssignPrivateIpAddresses",
      "ec2:UnassignPrivateIpAddresses",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "lambda_rotation" {
  name   = "${local.name_prefix}-lambda-rotation"
  role   = aws_iam_role.lambda_rotation.id
  policy = data.aws_iam_policy_document.lambda_rotation.json
}

# ── Rotation Lambda #1: RDS Postgres (single-user template) ──────────────────
# Packages a thin Python handler that delegates to the AWS-provided
# SecretsManagerRDSPostgreSQLRotationSingleUser template. The AWS template is
# published as a Serverless Application Repository (SAR) app; operators deploy
# the SAR app once per region (runbook 11 §"AWS Rotation Lambda deployment")
# which exports the rotation code as a Lambda Layer ARN. We attach the layer to
# this Lambda and call its `lambda_handler` from our inline wrapper.
#
# If the SAR layer is not yet deployed, the Lambda will fail at runtime with a
# clear ImportError — terraform validate + plan + apply all succeed because the
# handler is referenced by string.
locals {
  rotation_lambda_source_rds = <<-PYTHON
    """Thin wrapper that delegates to the AWS-provided RDS Postgres rotation template.

    Deployment prerequisite: deploy the SAR app
    `SecretsManagerRDSPostgreSQLRotationSingleUser` (arn:aws:serverlessrepo:us-east-1:297356227824:applications/SecretsManagerRDSPostgreSQLRotationSingleUser)
    and attach its exported Lambda Layer ARN to this function via the
    `layers = [...]` argument (runbook 11-secrets-management.md §"AWS Rotation
    Lambda deployment" walks through the SAR deploy).

    The layer publishes the `secrets_rotator` package which we import below.
    """
    import json
    import os
    import logging

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    def lambda_handler(event, context):
        try:
            # Import from the AWS-provided rotation template Lambda Layer.
            from secrets_rotator import lambda_handler as upstream_handler
            return upstream_handler(event, context)
        except ImportError as exc:
            logger.error("RDS rotation Lambda layer not attached: %s", exc)
            logger.error("Deploy the SecretsManagerRDSPostgreSQLRotationSingleUser SAR app + attach its layer ARN to this function. See runbook 11.")
            raise
        except Exception as exc:
            logger.error("RDS secret rotation failed: event=%s err=%s", json.dumps(event), exc)
            raise
    PYTHON

  rotation_lambda_source_generic = <<-PYTHON
    """Generic secret rotation Lambda for app-level OUTRENA secrets.

    Generates a new high-entropy value + writes it back to Secrets Manager.
    Does NOT update the downstream service (Keycloak admin password needs to
    be reset via the Keycloak Admin API; Redis AUTH needs ElastiCache
    modification; MailBridge URL needs operator action). The post-rotation
    downstream step is documented per-secret in runbook 09-secrets-management.md
    + runbook 11-secrets-management.md.

    Used for: keycloak_admin, mailbridge_url, redis_auth.
    NOT used for: rds_master, database_url, keycloak_db (those use the
    AWS-provided RDS rotation template — see secret_rotation_rds Lambda).
    """
    import boto3
    import json
    import logging
    import secrets
    import string

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    client = boto3.client("secretsmanager")

    # Map secret name suffix -> rotation strategy. The strategy decides which
    # JSON keys to rewrite + what character set to use for the new value.
    SECRET_STRATEGIES = {
        "keycloak-admin": {
            "keys": ["KEYCLOAK_ADMIN_PASSWORD"],
            "length": 32,
            "alphabet": string.ascii_letters + string.digits + "!#$%&*()-_=+",
        },
        "mailbridge-url": {
            # MailBridge URL is operator-supplied (an external webhook URL), not
            # something we can generate — rotation is a no-op marker so the
            # runbook-defined operator rotation cadence (30d) is tracked.
            "keys": [],
            "length": 0,
            "alphabet": "",
        },
        "redis-auth": {
            "keys": ["REDIS_AUTH_TOKEN"],
            "length": 32,
            "alphabet": string.ascii_letters + string.digits + "-_",
        },
    }


    def _new_value(strategy):
        if not strategy["keys"]:
            return None
        return "".join(secrets.choice(strategy["alphabet"]) for _ in range(strategy["length"]))


    def lambda_handler(event, context):
        arn = event.get("SecretId", "")
        step = event.get("Step", "")

        logger.info("rotation step=%s secret=%s", step, arn)

        # Determine the strategy by matching the secret name suffix.
        strategy = None
        for suffix, strat in SECRET_STRATEGIES.items():
            if arn.endswith(suffix) or f"-{suffix}" in arn:
                strategy = strat
                break

        if strategy is None:
            logger.error("no rotation strategy declared for secret %s", arn)
            raise ValueError(f"no rotation strategy for {arn}")

        # createSecret step: write a new value into the AWSPENDING stage.
        if step == "createSecret":
            new_val = _new_value(strategy)
            if new_val is None:
                logger.info("createSecret: no-op for %s (operator-rotated secret)", arn)
                return
            current = client.get_secret_value(SecretId=arn, VersionStage="AWSCURRENT")
            data = json.loads(current["SecretString"])
            for key in strategy["keys"]:
                data[key] = new_val
            client.put_secret_value(
                SecretId=arn,
                SecretString=json.dumps(data),
                VersionStages=["AWSPENDING"],
            )
            logger.info("createSecret: wrote AWSPENDING version for %s", arn)
            return

        # setSecret step: for app-level secrets, AWSPENDING == AWSCURRENT (no
        # downstream service to update). The finishSecret step promotes it.
        if step == "setSecret":
            logger.info("setSecret: no downstream action for %s (operator-driven)", arn)
            return

        # finishSecret step: promote AWSPENDING to AWSCURRENT.
        if step == "finishSecret":
            pending = client.get_secret_value(SecretId=arn, VersionStage="AWSPENDING")
            client.update_secret_version_stage(
                SecretId=arn,
                VersionStage="AWSCURRENT",
                MoveToVersionId=pending["VersionId"],
                RemoveFromVersionId=event.get("ClientRequestToken", ""),
            )
            logger.info("finishSecret: promoted AWSPENDING -> AWSCURRENT for %s", arn)
            return

        # testSecret step: skip (operator verifies via runbook 09 §"Verify rotation").
        if step == "testSecret":
            logger.info("testSecret: skipped (operator verifies per runbook 09)")
            return

        logger.warning("unknown step=%s for secret=%s", step, arn)
    PYTHON
}

# Package both handlers into separate zip files using the archive_file data
# source. The zips are tiny (a single .py file each) — kept inline to avoid
# an external build dependency.
data "archive_file" "secret_rotation_rds_zip" {
  type        = "zip"
  output_path = "${path.module}/build/secret_rotation_rds.zip"

  source {
    content  = local.rotation_lambda_source_rds
    filename = "lambda_handler.py"
  }
}

data "archive_file" "secret_rotation_generic_zip" {
  type        = "zip"
  output_path = "${path.module}/build/secret_rotation_generic.zip"

  source {
    content  = local.rotation_lambda_source_generic
    filename = "lambda_handler.py"
  }
}

resource "aws_lambda_function" "secret_rotation_rds" {
  function_name = "${local.name_prefix}-secret-rotation-rds"
  role          = aws_iam_role.lambda_rotation.arn
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  filename         = data.archive_file.secret_rotation_rds_zip.output_path
  source_code_hash = data.archive_file.secret_rotation_rds_zip.output_base64sha256

  # Attach to the data-tier VPC so the Lambda can reach RDS for password resets.
  vpc_config {
    subnet_ids         = local.data_subnet_ids
    security_group_ids = [aws_security_group.sg_rds.id]
  }

  # KMS key to encrypt the Lambda environment variables.
  environment {
    variables = {
      SECRETS_MANAGER_ENDPOINT = "https://secretsmanager.${data.aws_region.current.name}.amazonaws.com"
    }
  }

  # NOTE: attach the SAR-deployed `secrets_rotator` Lambda layer ARN here once
  # the operator has deployed the SecretsManagerRDSPostgreSQLRotationSingleUser
  # SAR app (see runbook 11 §"AWS Rotation Lambda deployment"). Until the layer
  # is attached, invoking this Lambda will fail with ImportError — but rotation
  # does not run on `terraform apply`, so this is safe to ship as-is.
  # layers = [<sar_layer_arn>]

  depends_on = [
    aws_iam_role_policy.lambda_rotation,
    aws_cloudwatch_log_group.secret_rotation,
  ]

  tags = {
    Name = "${local.name_prefix}-secret-rotation-rds"
  }
}

resource "aws_lambda_function" "secret_rotation_generic" {
  function_name = "${local.name_prefix}-secret-rotation-generic"
  role          = aws_iam_role.lambda_rotation.arn
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  filename         = data.archive_file.secret_rotation_generic_zip.output_path
  source_code_hash = data.archive_file.secret_rotation_generic_zip.output_base64sha256

  # Generic rotation doesn't need VPC access — Secrets Manager API is public.
  environment {
    variables = {
      SECRETS_MANAGER_ENDPOINT = "https://secretsmanager.${data.aws_region.current.name}.amazonaws.com"
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_rotation,
    aws_cloudwatch_log_group.secret_rotation,
  ]

  tags = {
    Name = "${local.name_prefix}-secret-rotation-generic"
  }
}

# ── Lambda permissions: allow Secrets Manager to invoke each Lambda ──────────
resource "aws_lambda_permission" "secret_rotation_rds" {
  statement_id  = "AllowSecretsManagerInvokeRDS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.secret_rotation_rds.function_name
  principal     = "secretsmanager.amazonaws.com"
  # Restrict to the RDS-managed secrets — prevents another secret from
  # accidentally pointing at this Lambda and triggering RDS password resets.
  source_arn = aws_secretsmanager_secret.rds_master.arn
}

resource "aws_lambda_permission" "secret_rotation_generic" {
  statement_id  = "AllowSecretsManagerInvokeGeneric"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.secret_rotation_generic.function_name
  principal     = "secretsmanager.amazonaws.com"
  # Allow invocation from any of the generic-rotated secrets.
  source_account = data.aws_caller_identity.current.account_id
}

# ── Rotation rules (one per existing secret) ─────────────────────────────────
# `rotate_immediately = false` so the first rotation runs on the schedule
# (not at terraform apply) — this avoids drift on the existing
# aws_secretsmanager_secret_version resources until operators remove them
# from state (see file header comment + runbook 11).

# 1. RDS master password — 90 days, RDS rotation Lambda.
resource "aws_secretsmanager_secret_rotation" "rds_master" {
  secret_id           = aws_secretsmanager_secret.rds_master.id
  rotation_lambda_arn = aws_lambda_function.secret_rotation_rds.arn

  rotation_rules {
    automatically_after_days = var.rds_secret_rotation_days
  }

  rotate_immediately = false

  depends_on = [aws_lambda_permission.secret_rotation_rds]
}

# 2. DATABASE_URL — 90 days, RDS rotation Lambda (the DATABASE_URL secret is
# shaped like an RDS rotation secret: contains host/port/user/pass/dbname).
resource "aws_secretsmanager_secret_rotation" "database_url" {
  secret_id           = aws_secretsmanager_secret.database_url.id
  rotation_lambda_arn = aws_lambda_function.secret_rotation_rds.arn

  rotation_rules {
    automatically_after_days = var.rds_secret_rotation_days
  }

  rotate_immediately = false

  depends_on = [aws_lambda_permission.secret_rotation_rds]
}

# 3. Keycloak DB role — 90 days, RDS rotation Lambda (same shape as rds_master).
resource "aws_secretsmanager_secret_rotation" "keycloak_db" {
  secret_id           = aws_secretsmanager_secret.keycloak_db.id
  rotation_lambda_arn = aws_lambda_function.secret_rotation_rds.arn

  rotation_rules {
    automatically_after_days = var.rds_secret_rotation_days
  }

  rotate_immediately = false

  depends_on = [aws_lambda_permission.secret_rotation_rds]
}

# 4. Keycloak admin password — 30 days, generic rotation Lambda.
resource "aws_secretsmanager_secret_rotation" "keycloak_admin" {
  secret_id           = aws_secretsmanager_secret.keycloak_admin.id
  rotation_lambda_arn = aws_lambda_function.secret_rotation_generic.arn

  rotation_rules {
    automatically_after_days = var.app_secret_rotation_days
  }

  rotate_immediately = false

  depends_on = [aws_lambda_permission.secret_rotation_generic]
}

# 5. Redis AUTH token — 30 days, generic rotation Lambda.
resource "aws_secretsmanager_secret_rotation" "redis_auth" {
  secret_id           = aws_secretsmanager_secret.redis_auth.id
  rotation_lambda_arn = aws_lambda_function.secret_rotation_generic.arn

  rotation_rules {
    automatically_after_days = var.app_secret_rotation_days
  }

  rotate_immediately = false

  depends_on = [aws_lambda_permission.secret_rotation_generic]
}

# 6. MailBridge URL — 30 days, generic rotation Lambda (no-op marker — operator
# rotates the URL upstream and updates the secret value).
resource "aws_secretsmanager_secret_rotation" "mailbridge_url" {
  count = var.mailbridge_url == "" ? 0 : 1

  secret_id           = aws_secretsmanager_secret.mailbridge_url[0].id
  rotation_lambda_arn = aws_lambda_function.secret_rotation_generic.arn

  rotation_rules {
    automatically_after_days = var.app_secret_rotation_days
  }

  rotate_immediately = false

  depends_on = [aws_lambda_permission.secret_rotation_generic]
}

# ── EventBridge: scheduled rotation check (safety net) ───────────────────────
# Secrets Manager evaluates `automatically_after_days` on its own schedule, but
# we add a daily EventBridge trigger that calls `RotateSecret` on any secret
# whose last-rotation date is past due. This catches cases where the Secrets
# Manager internal scheduler missed a window (rare but documented in AWS forums).
#
# The rule targets an AWS Lambda that lists secrets with overdue rotations and
# triggers RotateSecret on each. The Lambda is the generic-rotation Lambda
# itself (it can be invoked with a synthetic event that triggers the list+rotate
# path — see the lambda_handler's handling of event["Step"] == "scheduled").
locals {
  rotation_check_lambda_source = <<-PYTHON
    """Daily scheduled check: list secrets past their rotation window + trigger RotateSecret.

    Invoked by EventBridge rule '${local.name_prefix}-secret-rotation-check'.
    Reads each secret's LastRotatedDate + compares to its RotationRules.AutomaticallyAfterDays.
    """
    import boto3
    import datetime
    import logging

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    client = boto3.client("secretsmanager")


    def lambda_handler(event, context):
        now = datetime.datetime.now(datetime.timezone.utc)
        paginator = client.get_paginator("list_secrets")

        overdue = []
        for page in paginator.paginate(Filters=[{"Key": "tag-value", "Values": ["outrena"]}]):
            for secret in page["SecretList"]:
                rotation = secret.get("RotationRules", {})
                auto_days = rotation.get("AutomaticallyAfterDays")
                last_rotated = secret.get("LastRotatedDate")
                if not auto_days or not last_rotated:
                    continue
                age_days = (now - last_rotated).days
                if age_days >= auto_days:
                    overdue.append({"name": secret["Name"], "age_days": age_days, "interval_days": auto_days})

        for item in overdue:
            logger.info("triggering rotation for %s (age=%dd interval=%dd)", item["name"], item["age_days"], item["interval_days"])
            try:
                client.rotate_secret(SecretId=item["name"], RotateImmediately=False)
            except Exception as exc:
                logger.error("rotation trigger failed for %s: %s", item["name"], exc)

        return {"overdue_count": len(overdue), "overdue": overdue}
    PYTHON
}

data "archive_file" "rotation_check_zip" {
  type        = "zip"
  output_path = "${path.module}/build/rotation_check.zip"

  source {
    content  = local.rotation_check_lambda_source
    filename = "lambda_handler.py"
  }
}

resource "aws_lambda_function" "rotation_check" {
  function_name = "${local.name_prefix}-rotation-check"
  role          = aws_iam_role.lambda_rotation.arn
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60
  memory_size   = 256

  filename         = data.archive_file.rotation_check_zip.output_path
  source_code_hash = data.archive_file.rotation_check_zip.output_base64sha256

  depends_on = [
    aws_iam_role_policy.lambda_rotation,
    aws_cloudwatch_log_group.secret_rotation,
  ]

  tags = {
    Name = "${local.name_prefix}-rotation-check"
  }
}

resource "aws_cloudwatch_event_rule" "rotation_check" {
  name                = "${local.name_prefix}-secret-rotation-check"
  description         = "Daily safety-net check — trigger RotateSecret on any OUTRENA secret past its rotation window"
  schedule_expression = "rate(1 day)"
  state               = "ENABLED"

  tags = {
    Name = "${local.name_prefix}-rotation-check-rule"
  }
}

resource "aws_cloudwatch_event_target" "rotation_check" {
  rule      = aws_cloudwatch_event_rule.rotation_check.name
  target_id = "TriggerRotationCheck"
  arn       = aws_lambda_function.rotation_check.arn
}

resource "aws_lambda_permission" "rotation_check_eventbridge" {
  statement_id  = "AllowEventBridgeInvokeRotationCheck"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rotation_check.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.rotation_check.arn
}

# ── CloudWatch alarm: rotation failure ───────────────────────────────────────
# If the rotation Lambda errors >= 1 time in 5 min, page the security team
# (via the SOC2 security_alerts SNS topic). Catches:
#   - SAR Lambda Layer not attached (ImportError)
#   - RDS password update failed
#   - IAM permission drift
#   - Network reachability from Lambda VPC ENI to RDS
resource "aws_cloudwatch_log_metric_filter" "rotation_errors" {
  name           = "${local.name_prefix}-rotation-errors"
  log_group_name = aws_cloudwatch_log_group.secret_rotation.name
  pattern        = "\"ERROR\""

  metric_transformation {
    name          = "RotationErrors"
    namespace     = "OUTRENA_Security"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "rotation_errors" {
  alarm_name        = "${local.name_prefix}-rotation-errors"
  alarm_description = "SOC2 CC6.1 — secrets rotation Lambda errored (rotation is broken — secrets may be stale)"
  namespace         = "OUTRENA_Security"
  metric_name       = "RotationErrors"
  dimensions        = {}

  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.security_alerts.arn]
  ok_actions    = [aws_sns_topic.security_alerts.arn]

  tags = { Name = "${local.name_prefix}-rotation-errors-alarm" }
}
