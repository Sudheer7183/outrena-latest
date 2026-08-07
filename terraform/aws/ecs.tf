# ecs.tf — ECS cluster + CloudWatch log groups.
#
# Per-service task definitions + services live in their own files for
# readability:
#   ecs_backend.tf    — FastAPI Fargate task + ALB-backed service
#   ecs_frontend.tf   — nginx (Vite build) Fargate task + ALB-backed service
#   ecs_worker.tf     — Celery worker Fargate task (no ALB)
#   ecs_keycloak.tf   — Keycloak Fargate task + ALB-backed service
#
# This file creates the shared cluster + the four CloudWatch log groups that
# the task defs reference via `awslogs` log driver.

# ── ECS cluster ───────────────────────────────────────────────────────────────
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  # Container Insights gives per-task CPU/memory/RX/TX metrics — required
  # for the CloudWatch alarms in cloudwatch.tf. ~$0.30/task/month extra.
  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${local.name_prefix}-ecs-cluster"
  }
}

# ── CloudWatch log groups ─────────────────────────────────────────────────────
# One log group per service so retention + metric filters can be set
# independently. KMS-encrypted with the RDS key (reused for all app secrets).

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${local.name_prefix}/backend"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.rds.arn

  tags = {
    Name = "${local.name_prefix}-backend-log-group"
  }
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${local.name_prefix}/frontend"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.rds.arn

  tags = {
    Name = "${local.name_prefix}-frontend-log-group"
  }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name_prefix}/worker"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.rds.arn

  tags = {
    Name = "${local.name_prefix}-worker-log-group"
  }
}

resource "aws_cloudwatch_log_group" "keycloak" {
  name              = "/ecs/${local.name_prefix}/keycloak"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.rds.arn

  tags = {
    Name = "${local.name_prefix}-keycloak-log-group"
  }
}
