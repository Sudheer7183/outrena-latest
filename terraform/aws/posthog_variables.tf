# posthog_variables.tf — PostHog-specific Terraform variables (PH-INFRA).
#
# These variables are PostHog-specific (not shared with the OUTRENA app
# stack). Mirrors the SAAS-INFRA pattern: variables are declared in a
# separate file rather than editing the lead-authored variables.tf.
# Defaults are sane for dev so `terraform plan` works out-of-the-box;
# staging/prod override via envs/<env>/*.tfvars.
#
# Cross-references:
#   - terraform/aws/posthog.tf — uses these variables
#   - runbooks/15-exception-logging-self-healing.md §"Maintenance" — sizing

# ── PostHog image ─────────────────────────────────────────────────────────────
variable "posthog_image_tag" {
  description = "PostHog container image tag. Pin to a specific release (e.g. release-1.215.0) in prod; release-latest in dev."
  type        = string
  default     = "release-latest"
}

# ── Aurora Postgres for PostHog metadata ──────────────────────────────────────
variable "posthog_db_name" {
  description = "Logical database name for PostHog metadata (separate from the OUTRENA app DB)."
  type        = string
  default     = "posthog"
}

variable "posthog_db_username" {
  description = "PostHog Postgres master username."
  type        = string
  default     = "posthog_app"
}

variable "posthog_db_password" {
  description = "PostHog Postgres master password. If empty, a random one is generated and stored in Secrets Manager."
  type        = string
  default     = ""
  sensitive   = true
}

variable "posthog_db_instance_class" {
  description = "Aurora instance class. dev: db.t4g.medium, prod: db.r6g.large (matches OUTRENA app RDS sizing)."
  type        = string
  default     = "db.t4g.medium"
}

variable "posthog_db_backup_retention_days" {
  description = "Aurora automated backup retention. Prod: 35 (PITR); dev: 7."
  type        = number
  default     = 7
}

# ── ElastiCache Redis for PostHog ─────────────────────────────────────────────
variable "posthog_redis_node_type" {
  description = "ElastiCache node type for PostHog. dev: cache.t3.small, prod: cache.m6g.large."
  type        = string
  default     = "cache.t3.small"
}

# ── MSK Kafka for PostHog ─────────────────────────────────────────────────────
variable "posthog_kafka_instance_type" {
  description = "MSK broker instance type. dev: kafka.t3.small, prod: kafka.m5.large."
  type        = string
  default     = "kafka.t3.small"
}

variable "posthog_kafka_ebs_gb" {
  description = "EBS storage (GB) per MSK broker."
  type        = number
  default     = 100
}

# ── ECS Fargate sizing ────────────────────────────────────────────────────────
variable "posthog_web_cpu" {
  description = "CPU units for PostHog web Fargate task (1 vCPU = 1024)."
  type        = number
  default     = 1024
}

variable "posthog_web_memory" {
  description = "Memory (MB) for PostHog web Fargate task."
  type        = number
  default     = 2048
}

variable "posthog_web_desired_count" {
  description = "Desired PostHog web task count. Prod min 2 for ALB failover."
  type        = number
  default     = 2
}

variable "posthog_worker_cpu" {
  description = "CPU units for PostHog Celery worker Fargate task."
  type        = number
  default     = 1024
}

variable "posthog_worker_memory" {
  description = "Memory (MB) for PostHog Celery worker Fargate task."
  type        = number
  default     = 2048
}

variable "posthog_worker_desired_count" {
  description = "Desired PostHog worker task count."
  type        = number
  default     = 2
}

variable "posthog_plugin_server_cpu" {
  description = "CPU units for PostHog plugin-server Fargate task."
  type        = number
  default     = 1024
}

variable "posthog_plugin_server_memory" {
  description = "Memory (MB) for PostHog plugin-server Fargate task."
  type        = number
  default     = 2048
}

variable "posthog_plugin_server_desired_count" {
  description = "Desired PostHog plugin-server task count."
  type        = number
  default     = 2
}

# ── PostHog integrations ──────────────────────────────────────────────────────
variable "posthog_email_host" {
  description = "SMTP host for PostHog alerting + integration emails. Empty = no email."
  type        = string
  default     = ""
}

variable "posthog_email_port" {
  description = "SMTP port for PostHog email."
  type        = number
  default     = 587
}

variable "posthog_slack_token" {
  description = "Slack bot token for PostHog Slack integration. Empty = no Slack."
  type        = string
  default     = ""
  sensitive   = true
}

variable "posthog_self_driving_repo" {
  description = "GitHub repo (owner/name) that PostHog self-driving opens PRs against."
  type        = string
  default     = "outrena/migration"
}
