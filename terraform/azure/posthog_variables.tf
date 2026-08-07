# posthog_variables.tf — PostHog-specific Terraform variables for Azure (PH-INFRA).
#
# These variables are PostHog-specific (not shared with the OUTRENA app stack).
# Mirrors the AWS posthog_variables.tf pattern. Defaults are sane for dev so
# `terraform plan` works out-of-the-box; staging/prod override via
# envs/<env>/*.tfvars.

# ── Networking ────────────────────────────────────────────────────────────────
variable "posthog_data_subnet_cidr" {
  description = "CIDR for the PostHog DataSubnet. Must not collide with OUTRENA's subnets (var.subnets) — defaults to the next /24 after IdpSubnet."
  type        = string
  default     = "10.1.8.0/24"
}

variable "posthog_apps_subnet_cidr" {
  description = "CIDR for the PostHog AppsSubnet (Container Apps Environment). Must be /23 or larger. Must not collide with OUTRENA's subnets."
  type        = string
  default     = "10.1.10.0/23"
}

# ── PostHog image ─────────────────────────────────────────────────────────────
variable "posthog_image_tag" {
  description = "PostHog container image tag. Pin to a specific release in prod; release-latest in dev."
  type        = string
  default     = "release-latest"
}

# ── PostgreSQL Flexible Server for PostHog metadata ──────────────────────────
variable "posthog_pg_sku" {
  description = "PostgreSQL Flexible Server SKU for PostHog. dev: B_Standard_B1ms (burstable), prod: GP_Standard_D4s_v3."
  type        = string
  default     = "B_Standard_B1ms"
}

variable "posthog_pg_storage_mb" {
  description = "Storage (MB) for PostHog PostgreSQL Flexible Server."
  type        = number
  default     = 51200
}

variable "posthog_pg_backup_retention_days" {
  description = "PostHog PostgreSQL backup retention. Prod: 35 (PITR); dev: 7."
  type        = number
  default     = 7
}

variable "posthog_pg_geo_redundant_backup" {
  description = "Geo-redundant backup for PostHog PostgreSQL. MUST be true in prod."
  type        = bool
  default     = false
}

# ── Container Apps sizing ─────────────────────────────────────────────────────
variable "posthog_web_cpu" {
  description = "vCPU allocation per PostHog web replica."
  type        = number
  default     = 1.0
}

variable "posthog_web_memory" {
  description = "Memory allocation per PostHog web replica."
  type        = string
  default     = "2.0Gi"
}

variable "posthog_web_min_replicas" {
  description = "Minimum PostHog web replicas. Prod min 2 for failover."
  type        = number
  default     = 2
}

variable "posthog_web_max_replicas" {
  description = "Maximum PostHog web replicas (HPA ceiling)."
  type        = number
  default     = 10
}

variable "posthog_worker_cpu" {
  description = "vCPU allocation per PostHog worker replica."
  type        = number
  default     = 1.0
}

variable "posthog_worker_memory" {
  description = "Memory allocation per PostHog worker replica."
  type        = string
  default     = "2.0Gi"
}

variable "posthog_worker_min_replicas" {
  type    = number
  default = 2
}

variable "posthog_worker_max_replicas" {
  type    = number
  default = 8
}

variable "posthog_plugin_server_cpu" {
  description = "vCPU allocation per PostHog plugin-server replica."
  type        = number
  default     = 1.0
}

variable "posthog_plugin_server_memory" {
  description = "Memory allocation per PostHog plugin-server replica."
  type        = string
  default     = "2.0Gi"
}

variable "posthog_plugin_server_min_replicas" {
  type    = number
  default = 2
}

variable "posthog_plugin_server_max_replicas" {
  type    = number
  default = 8
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
