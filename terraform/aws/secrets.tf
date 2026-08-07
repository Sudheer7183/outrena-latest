# secrets.tf — Secrets Manager secrets for Keycloak admin + MailBridge URL.
#
# The RDS master + Redis AUTH secrets live with their respective resources
# (rds.tf, elasticache.tf). This file holds the app-level secrets that are
# NOT tied to a single AWS resource.

# ── Keycloak admin password ───────────────────────────────────────────────────
resource "random_password" "keycloak_admin" {
  count   = var.keycloak_admin_password == "" ? 1 : 0
  length  = 32
  special = true
  # Keycloak admin console accepts most special chars, but avoid ones that
  # break shell quoting when passed via ECS env.
  override_special = "!#$%&*()-_=+"
}

locals {
  keycloak_admin_password = var.keycloak_admin_password == "" ? random_password.keycloak_admin[0].result : var.keycloak_admin_password
}

resource "aws_secretsmanager_secret" "keycloak_admin" {
  name                    = "${local.name_prefix}-keycloak-admin"
  description             = "OUTRENA Keycloak admin credentials"
  kms_key_id              = aws_kms_key.rds.arn # reuse RDS KMS key (no per-secret key needed)
  recovery_window_in_days = 30

  tags = {
    Name = "${local.name_prefix}-keycloak-admin-secret"
  }
}

resource "aws_secretsmanager_secret_version" "keycloak_admin" {
  secret_id = aws_secretsmanager_secret.keycloak_admin.id

  secret_string = jsonencode({
    KEYCLOAK_ADMIN          = var.keycloak_admin_username
    KEYCLOAK_ADMIN_PASSWORD = local.keycloak_admin_password
  })
}

# ── MailBridge URL ────────────────────────────────────────────────────────────
# Only create if var.mailbridge_url is non-empty (dev may skip MailBridge).
resource "aws_secretsmanager_secret" "mailbridge_url" {
  count                   = var.mailbridge_url == "" ? 0 : 1
  name                    = "${local.name_prefix}-mailbridge-url"
  description             = "OUTRENA MailBridge inbound webhook URL"
  kms_key_id              = aws_kms_key.rds.arn
  recovery_window_in_days = 30

  tags = {
    Name = "${local.name_prefix}-mailbridge-url-secret"
  }
}

resource "aws_secretsmanager_secret_version" "mailbridge_url" {
  count     = var.mailbridge_url == "" ? 0 : 1
  secret_id = aws_secretsmanager_secret.mailbridge_url[0].id
  secret_string = jsonencode({
    MAILBRIDGE_DEFAULT_URL = var.mailbridge_url
  })
}

# ── Keycloak DB password (separate from app DB password) ──────────────────────
# Keycloak has its own DB (var.keycloak_db_name) and role
# (var.keycloak_db_username) inside the RDS instance. The password is
# generated here and the role is provisioned via a post-apply psql script
# (see ecs_keycloak.tf for the manual step / null_resource comment).
resource "random_password" "keycloak_db" {
  length  = 32
  special = false # Postgres role passwords — keep it simple to avoid quoting issues
}

resource "aws_secretsmanager_secret" "keycloak_db" {
  name                    = "${local.name_prefix}-keycloak-db"
  description             = "OUTRENA Keycloak DB role password"
  kms_key_id              = aws_kms_key.rds.arn
  recovery_window_in_days = 30

  tags = {
    Name = "${local.name_prefix}-keycloak-db-secret"
  }
}

resource "aws_secretsmanager_secret_version" "keycloak_db" {
  secret_id = aws_secretsmanager_secret.keycloak_db.id
  secret_string = jsonencode({
    KC_DB_USERNAME = var.keycloak_db_username
    KC_DB_PASSWORD = random_password.keycloak_db.result
    KC_DB_URL      = "jdbc:postgresql://${aws_db_instance.main.address}:5432/${var.keycloak_db_name}"
  })
}
