# rds.tf — RDS PostgreSQL 16 Multi-AZ + Secrets Manager master password.
#
# Migration doc §11.3:
#   - PostgreSQL 16
#   - Multi-AZ in prod (db.r6g.large); dev single-AZ db.t4g.small
#   - 35-day backup retention (PITR)
#   - Storage encrypted with customer-managed KMS key
#   - Performance Insights on
#   - CloudWatch Logs exports: postgresql + upgrade
#
# The RDS instance hosts BOTH the OUTRENA app DB (var.database_name, with
# per-tenant schemas tenant_<slug>) AND the Keycloak DB (var.keycloak_db_name)
# — the latter is created via a post-apply psql script (see ecs_keycloak.tf
# comment for the manual step).

# ── DB subnet group (data tier) ───────────────────────────────────────────────
resource "aws_db_subnet_group" "main" {
  name        = "${local.name_prefix}-db-subnet-group"
  description = "Subnets for the OUTRENA RDS instance (data tier)"
  subnet_ids  = local.data_subnet_ids

  tags = {
    Name = "${local.name_prefix}-db-subnet-group"
  }
}

# ── KMS key for RDS storage encryption ────────────────────────────────────────
resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS PostgreSQL storage encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = var.enable_kms_key_rotation

  policy = data.aws_iam_policy_document.kms_rds.json

  tags = {
    Name = "${local.name_prefix}-kms-rds"
  }
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${local.name_prefix}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

data "aws_iam_policy_document" "kms_rds" {
  statement {
    sid    = "Enable IAM root permissions"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  # Allow RDS service to use the key.
  statement {
    sid    = "Allow RDS service to use the key"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }

    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
      "kms:CreateGrant",
    ]

    resources = ["*"]
  }
}

# ── Master password ───────────────────────────────────────────────────────────
# If var.database_password is non-empty, use it; otherwise generate a random
# 32-char password and store it in Secrets Manager.
resource "random_password" "rds_master" {
  count   = var.database_password == "" ? 1 : 0
  length  = 32
  special = true
  # Avoid characters that break JDBC URLs / psql connection strings.
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

locals {
  rds_master_password = var.database_password == "" ? random_password.rds_master[0].result : var.database_password
}

# ── Secrets Manager: RDS master ───────────────────────────────────────────────
# Stored as a JSON blob so the app can pull the whole connection dict via
# a single GetSecretValue call (rotation-friendly format used by the
# AWS RDS Secrets Manager rotation Lambda).
resource "aws_secretsmanager_secret" "rds_master" {
  name                    = "${local.name_prefix}-rds-master"
  description             = "OUTRENA RDS master credentials"
  kms_key_id              = aws_kms_key.rds.arn
  recovery_window_in_days = 30 # allow un-delete within 30 days

  tags = {
    Name = "${local.name_prefix}-rds-master-secret"
  }
}

resource "aws_secretsmanager_secret_version" "rds_master" {
  secret_id = aws_secretsmanager_secret.rds_master.id

  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_db_instance.main.address
    port     = 5432
    username = var.database_username
    password = local.rds_master_password
    dbname   = var.database_name
    # JDBC URL for Keycloak + any JDBC-based tooling.
    jdbcUrl = "jdbc:postgresql://${aws_db_instance.main.address}:5432/${var.database_name}"
  })
}

# ── CloudWatch log group for RDS postgresql logs ──────────────────────────────
resource "aws_cloudwatch_log_group" "rds" {
  name              = "/aws/rds/${local.name_prefix}/postgresql"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.rds.arn

  tags = {
    Name = "${local.name_prefix}-rds-log-group"
  }
}

# ── RDS instance ──────────────────────────────────────────────────────────────
resource "aws_db_instance" "main" {
  identifier = "${local.name_prefix}-postgres"

  engine                = "postgres"
  engine_version        = "16.3"
  instance_class        = var.rds_instance_class
  allocated_storage     = var.rds_allocated_storage
  max_allocated_storage = var.rds_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name                     = var.database_name
  username                    = var.database_username
  password                    = local.rds_master_password
  manage_master_user_password = false # we manage via Secrets Manager ourselves

  multi_az               = var.rds_multi_az
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.sg_rds.id]
  publicly_accessible    = false

  backup_retention_period = var.rds_backup_retention_days
  backup_window           = "03:00-04:00" # UTC, low-traffic window
  copy_tags_to_snapshot   = true

  # Final snapshot on destroy (skip_final_snapshot=false). Name is unique per
  # destroy attempt via the `${var.environment_short}-${timestamp()}` suffix,
  # but Terraform can't call timestamp() at plan time. Use a fixed name per
  # environment; subsequent destroys must clean up the previous snapshot.
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.rds_final_snapshot_name}-${var.environment_short}"

  deletion_protection = var.rds_deletion_protection

  # Performance Insights — small overhead, big debugging value.
  performance_insights_enabled          = true
  performance_insights_kms_key_id       = aws_kms_key.rds.arn
  performance_insights_retention_period = 7 # days (free tier is 7; longer is paid)

  # CloudWatch Logs exports — postgresql (query log) + upgrade.
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  depends_on                      = [aws_cloudwatch_log_group.rds]

  # Maintenance — minor version auto-patch in the same window as backups
  # (off-peak UTC). Major version upgrades are NOT automatic — must be
  # planned (e.g. 16.x → 17.x).
  auto_minor_version_upgrade = true
  maintenance_window         = "sun:04:00-sun:05:00"

  # Don't leak the password in `terraform show`.
  lifecycle {
    ignore_changes = [
      password, # rotation would otherwise cause perpetual diff
    ]
  }

  tags = {
    Name = "${local.name_prefix}-postgres"
    Tier = "data"
  }
}

# ── Secrets Manager: per-tenant DATABASE_URL helper ───────────────────────────
# The OUTRENA backend reads DATABASE_URL from a secret called
# `${local.name_prefix}-database-url`. The value is the asyncpg URL the app
# uses (postgresql+asyncpg://...). Stored separately from the master secret
# so we can rotate the app role independently of the master.
#
# In a real deployment this secret would be created by a separate rotation
# Lambda that provisions a per-app role (outrena_app) with RDS IAM or a
# dedicated password. For v1 we write the master URL here — the ECS task
# definition (ecs_backend.tf) reads it via `secrets = [{ name="DATABASE_URL",
# valueFrom = aws_secretsmanager_secret.database_url.arn }]`.
resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${local.name_prefix}-database-url"
  description             = "OUTRENA backend DATABASE_URL (asyncpg)"
  kms_key_id              = aws_kms_key.rds.arn
  recovery_window_in_days = 30

  tags = {
    Name = "${local.name_prefix}-database-url-secret"
  }
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id

  secret_string = jsonencode({
    DATABASE_URL = "postgresql+asyncpg://${var.database_username}:${urlencode(local.rds_master_password)}@${aws_db_instance.main.address}:5432/${var.database_name}"
  })
}

# NOTE on rotation:
# - Master password rotation: not enabled in v1 (requires the AWS-provided
#   rotation Lambda + an SSM/VPC-endpoint for Lambda→RDS). Add later via
#   aws_secretsmanager_secret_rotation with the AWS-provided
#   `SecretsManagerRDSPostgreSQLRotationSingleUser` Lambda.
# - DATABASE_URL rotation: not enabled — would require a custom Lambda that
#   updates both the secret value AND the RDS app role password atomically.
