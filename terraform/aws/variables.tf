# variables.tf — OUTRENA AWS deployment inputs.
#
# Every variable has a sensible default for dev so `terraform plan` works
# out-of-the-box. Staging/prod override via `envs/<env>/*.tfvars`.

# ── Global ────────────────────────────────────────────────────────────────────
variable "aws_region" {
  description = "AWS region for all resources. Dev/staging: us-east-1. Prod: us-east-1 (primary), with Multi-AZ RDS across 3 AZs."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment. Drives naming, sizing, and the ENVIRONMENT app var."
  type        = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be one of: development, staging, production."
  }
}

variable "environment_short" {
  description = "3-letter prefix used in resource names (dev/stg/prd)."
  type        = string
  default     = "dev"
}

variable "base_domain" {
  description = "Apex domain. Wildcard cert covers *.<base_domain>. Per-tenant subdomains (acme.<base_domain>) resolve via Route 53."
  type        = string
  default     = "outrena.dev"
}

variable "project_name" {
  description = "Lowercase project slug used in resource naming."
  type        = string
  default     = "outrena"
}

# ── Networking ────────────────────────────────────────────────────────────────
variable "vpc_cidr" {
  description = "VPC CIDR. Must not collide with on-prem or peered VPCs."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "AZs to spread across. Prod uses 3 for Multi-AZ RDS + ECS spread."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "enable_nat_gateway" {
  description = "Whether to provision NAT Gateways (cost-saving in dev: false → private subnets use IGW via public routes, but prod MUST be true)."
  type        = bool
  default     = false
}

variable "single_nat_gateway" {
  description = "Use one NAT GW for all private subnets (cost-saving in staging). Prod should set false (one NAT per AZ)."
  type        = bool
  default     = true
}

# ── ECS / Fargate sizing ──────────────────────────────────────────────────────
variable "backend_task_cpu" {
  description = "CPU units (1 vCPU = 1024) for the backend Fargate task."
  type        = number
  default     = 1024
}

variable "backend_task_memory" {
  description = "Memory (MB) for the backend Fargate task."
  type        = number
  default     = 2048
}

variable "backend_desired_count" {
  description = "Desired backend task count. Prod min 2 for ALB failover."
  type        = number
  default     = 2
}

variable "frontend_task_cpu" {
  description = "CPU units for the frontend Fargate task (serves static SPA via nginx)."
  type        = number
  default     = 512
}

variable "frontend_task_memory" {
  type    = number
  default = 1024
}

variable "frontend_desired_count" {
  type    = number
  default = 2
}

variable "worker_task_cpu" {
  description = "CPU units for the Celery worker Fargate task."
  type        = number
  default     = 1024
}

variable "worker_task_memory" {
  type    = number
  default = 2048
}

variable "worker_desired_count" {
  type    = number
  default = 2
}

variable "keycloak_task_cpu" {
  type    = number
  default = 1024
}

variable "keycloak_task_memory" {
  type    = number
  default = 2048
}

variable "keycloak_desired_count" {
  type    = number
  default = 2
}

variable "backend_ecr_tag" {
  description = "Image tag for the backend + worker (shared image). Set by CI/CD to the git SHA."
  type        = string
  default     = "latest"
}

variable "frontend_ecr_tag" {
  description = "Image tag for the frontend."
  type        = string
  default     = "latest"
}

variable "keycloak_image" {
  description = "Keycloak container image. Pin to a specific digest in prod."
  type        = string
  default     = "quay.io/keycloak/keycloak:24.0"
}

# ── RDS PostgreSQL 16 ─────────────────────────────────────────────────────────
variable "rds_instance_class" {
  description = "RDS instance class. dev: db.t4g.small, prod: db.r6g.large (per migration doc §11.3)."
  type        = string
  default     = "db.t4g.small"
}

variable "rds_allocated_storage" {
  description = "Initial storage (GB). RDS autoscales up to max_allocated_storage."
  type        = number
  default     = 50
}

variable "rds_max_allocated_storage" {
  type    = number
  default = 200
}

variable "rds_multi_az" {
  description = "Synchronous standby in a second AZ. MUST be true in prod."
  type        = bool
  default     = false
}

variable "rds_backup_retention_days" {
  description = "Automated backup retention. Migration doc requires 35 days in prod for PITR."
  type        = number
  default     = 7
}

variable "rds_deletion_protection" {
  description = "Prevents accidental RDS deletion. MUST be true in prod."
  type        = bool
  default     = false
}

variable "database_name" {
  type    = string
  default = "outrena"
}

variable "database_username" {
  type    = string
  default = "outrena_app"
}

variable "database_password" {
  description = "Master password. If empty, a random one is generated and stored in Secrets Manager."
  type        = string
  default     = ""
  sensitive   = true
}

# ── ElastiCache Redis 7 ───────────────────────────────────────────────────────
variable "redis_node_type" {
  description = "ElastiCache node type. dev: cache.t3.micro, prod: cache.r6g.large (per migration doc §11.3)."
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_cluster_mode" {
  description = "Enable cluster mode (3 shards × 1 replica in prod). Dev uses non-cluster for cost."
  type        = bool
  default     = false
}

variable "redis_num_cache_clusters" {
  description = "Replicas per shard (cluster mode) or standalone replicas (non-cluster)."
  type        = number
  default     = 1
}

variable "redis_shard_count" {
  type    = number
  default = 3
}

# ── S3 ─────────────────────────────────────────────────────────────────────────
variable "csv_bucket_name" {
  description = "Globally-unique bucket for CSV uploads. Migration doc §11.3: outrena-<env>-csv."
  type        = string
  default     = "outrena-dev-csv"
}

variable "collateral_bucket_name" {
  description = "Globally-unique bucket for sales collateral (PDFs, images)."
  type        = string
  default     = "outrena-dev-collateral"
}

# ── Logging ───────────────────────────────────────────────────────────────────
variable "log_retention_days" {
  description = "CloudWatch log group retention. dev: 7, staging: 30, prod: 90."
  type        = number
  default     = 7
}

# ── Blue/Green cutover ────────────────────────────────────────────────────────
variable "blue_green_weight_new" {
  description = "Route 53 weight on the NEW (FastAPI) stack. 0 = dark, 100 = full cutover. Migration doc §10 Phase 6 exit: 5 → 25 → 50 → 100 over 7 days."
  type        = number
  default     = 0
}

variable "blue_green_weight_old" {
  description = "Route 53 weight on the OLD (Next.js) stack. 100 - blue_green_weight_new by default."
  type        = number
  default     = 100
}

# ── App config (passed as ECS env vars / secrets) ─────────────────────────────
variable "keycloak_admin_username" {
  type      = string
  default   = "admin"
  sensitive = true
}

variable "keycloak_admin_password" {
  type      = string
  default   = ""
  sensitive = true
}

variable "llm_api_url" {
  description = "LLM gateway URL (ZAI / OpenAI)."
  type        = string
  default     = "https://open.bigmodel.cn/api/paas/v4"
}

variable "mailbridge_url" {
  description = "MailBridge inbound reply webhook URL."
  type        = string
  default     = ""
}

variable "scheduler_tick_seconds" {
  type    = number
  default = 300
}

variable "scheduler_partial_cap" {
  type    = number
  default = 5
}

variable "allowed_origins" {
  description = "CORS allowed origins as JSON array string."
  type        = string
  default     = "[\"http://localhost:5173\",\"http://localhost\"]"
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "skip_jwt_verification" {
  description = "Dev-only JWT bypass. MUST be false in staging/prod. CI audit_env.py enforces."
  type        = bool
  default     = false
}

variable "verify_jwt_issuer" {
  type    = bool
  default = true
}

# ── SOC2 / CloudTrail / Secrets rotation (SAAS-INFRA) ─────────────────────────
variable "cloudtrail_logs_bucket_name" {
  description = "Globally-unique S3 bucket for CloudTrail + AWS Config logs. Must be globally unique across AWS."
  type        = string
  default     = "outrena-dev-cloudtrail-logs"
}

variable "security_alert_email" {
  description = "Email endpoint subscribed to the SOC2 security-alerts SNS topic (separate from var.alert_email). Route to the security team on-call."
  type        = string
  default     = "security@outrena.com"
}

variable "app_secret_rotation_days" {
  description = "Automatic rotation interval (days) for app-level Secrets Manager secrets (Keycloak admin, MailBridge URL, Keycloak DB). Runbook 09 + 11 promise 30d."
  type        = number
  default     = 30
}

variable "rds_secret_rotation_days" {
  description = "Automatic rotation interval (days) for the RDS master + DATABASE_URL secrets. Runbook 09 promises 90d."
  type        = number
  default     = 90
}
