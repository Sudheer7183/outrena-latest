# main.tf — OUTRENA AWS Terraform root module.
#
# All resources are split across purpose-specific files for readability:
#
#   versions.tf          — provider pinning + S3 backend
#   variables.tf         — primary input variables (lead-authored)
#   locals_extra.tf      — extra inputs (alert_email, KMS rotation, WAF rate
#                          limit, etc.) NOT declared in variables.tf
#   vpc.tf               — VPC, subnets, NAT/IGW, route tables, VPC endpoints
#   security_groups.tf   — SG table from migration doc §11.2
#   acm.tf               — ACM wildcard cert + DNS validation
#   route53.tf           — Hosted zone + weighted blue/green records
#   alb.tf               — ALB + target groups + listeners + WAFv2
#   s3.tf                — csv / collateral / alb_logs buckets + KMS key
#   rds.tf               — RDS PostgreSQL 16 Multi-AZ + Secrets Manager
#   elasticache.tf       — ElastiCache Redis 7 replication group + KMS key
#   iam.tf               — ECS task execution + per-service task roles
#   ecs.tf               — ECS cluster + CloudWatch log groups
#   ecs_backend.tf       — Backend Fargate task + service
#   ecs_frontend.tf      — Frontend Fargate task + service
#   ecs_worker.tf        — Celery worker Fargate task + service
#   ecs_keycloak.tf      — Keycloak Fargate task + service
#   ecr.tf               — ECR repos for backend + frontend
#   secrets.tf           — Secrets Manager: keycloak admin, mailbridge url
#   cloudwatch.tf        — SNS + dashboards + alarms + metric filters
#   outputs.tf           — Stack outputs (ALB DNS, RDS endpoint, etc.)
#
#   envs/<dev|staging|prod>/backend.tfbackend   — per-env S3 state backend
#   envs/<dev|staging|prod>/<env>.tfvars        — per-env variable overrides
#
# All resources inherit Project/Environment/ManagedBy/Repo tags via the
# provider default_tags block in versions.tf. Resource-level tags only set
# `Name = "${local.name_prefix}-<purpose>"` for human readability.

locals {
  # Short prefix used across resource names: outrena-dev-, outrena-stg-, outrena-prd-
  name_prefix = "${var.project_name}-${var.environment_short}"

  # Common tag map merged into every resource (provider default_tags add the
  # four canonical tags; this is for resource-specific extra tags if needed).
  common_tags = {
    Name = local.name_prefix
  }

  # Convenience: flat lists of subnet IDs by tier (vpc.tf creates maps keyed
  # by "<index>:<az>" — we flatten when a service needs a list).
  public_subnet_ids  = [for s in aws_subnet.public : s.id]
  private_subnet_ids = [for s in aws_subnet.private : s.id]
  data_subnet_ids    = [for s in aws_subnet.data : s.id]
}
