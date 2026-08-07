# locals_extra.tf — extra variables not declared in the lead-authored variables.tf.
#
# Per task convention we DO NOT edit variables.tf. Any variable that the
# security/alb/route53/cloudwatch/ecs/rds modules need which is missing from
# variables.tf is declared here instead. Defaults are sane for dev so
# `terraform plan` works out-of-the-box; staging/prod override via tfvars.

# ── Alerting ──────────────────────────────────────────────────────────────────
variable "alert_email" {
  description = "Email endpoint subscribed to the CloudWatch → SNS alert topic. Override in prod tfvars."
  type        = string
  default     = "ops@outrena.com"
}

# ── Keycloak DB ───────────────────────────────────────────────────────────────
variable "keycloak_db_name" {
  description = "Dedicated logical database inside the RDS instance for Keycloak's own schema. Provisioned via a post-apply psql script (see ecs_keycloak.tf comment)."
  type        = string
  default     = "keycloak"
}

variable "keycloak_db_username" {
  description = "Keycloak DB role. Kept separate from the app role (outrena_app) for blast-radius isolation."
  type        = string
  default     = "keycloak_app"
}

# ── S3 ─────────────────────────────────────────────────────────────────────────
variable "alb_logs_bucket_name" {
  description = "Globally-unique S3 bucket for ALB access logs. Must have the AWS ELB account write prefix."
  type        = string
  default     = "outrena-dev-alb-logs"
}

# ── WAF / ALB ─────────────────────────────────────────────────────────────────
variable "waf_rate_limit" {
  description = "Per-IP request rate limit over 5 minutes before WAF blocks. Migration doc §11.3: 100 in prod, 1000 in dev (CI smoke tests)."
  type        = number
  default     = 1000
}

variable "backend_health_check_path" {
  type    = string
  default = "/health"
}

# ── ECS deploy ─────────────────────────────────────────────────────────────────
variable "ecs_deployment_maximum_percent" {
  description = "Maximum running task percent during a rolling deploy. 200 = double before draining old."
  type        = number
  default     = 200
}

variable "ecs_deployment_minimum_healthy_percent" {
  description = "Minimum healthy percent during a rolling deploy. 100 = no capacity loss."
  type        = number
  default     = 100
}

# ── Backend stack private subnets assign public IP ─────────────────────────────
variable "assign_public_ip_to_fargate" {
  description = "Set to true in dev (no NAT GW cost) — Fargate tasks get a public IP for image pull + LLM/MailBridge egress. MUST be false in staging/prod (private-only via NAT GW)."
  type        = bool
  default     = true
}

# ── KMS key rotation ──────────────────────────────────────────────────────────
variable "enable_kms_key_rotation" {
  description = "Enable automatic annual rotation for customer-managed KMS keys (S3, RDS, Redis, Secrets Manager)."
  type        = bool
  default     = true
}

# ── RDS final snapshot ────────────────────────────────────────────────────────
variable "rds_final_snapshot_name" {
  description = "Final snapshot identifier when RDS is destroyed. Required when skip_final_snapshot=false (the default + prod setting)."
  type        = string
  default     = "outrena-rds-final"
}
