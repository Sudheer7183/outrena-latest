# variables.tf — OUTRENA Azure deployment inputs.
#
# Every variable has a sensible default for dev so `terraform plan` works
# out-of-the-box. Staging/prod override via `envs/<env>/*.tfvars`.
# Mirrors the AWS variables.tf structure (§11) — same app-config var names so
# the Docker image stays cloud-portable (per migration doc §13.2).

# ── Global ────────────────────────────────────────────────────────────────────
variable "location" {
  description = "Azure region for all resources. Dev/staging: eastus. Prod: eastus (primary), with zone-redundant HA across 3 AZs."
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Deployment environment. Drives naming, sizing, ENVIRONMENT app var, and zone-redundancy toggles."
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
  description = "Apex domain. Wildcard cert covers *.<base_domain>. Per-tenant subdomains (acme.<base_domain>) resolve via Azure DNS."
  type        = string
  default     = "azure.outrena.dev"
}

variable "project_name" {
  description = "Lowercase project slug used in resource naming."
  type        = string
  default     = "outrena"
}

variable "resource_group_name" {
  description = "Resource group name. All Phase-6 resources live in this RG."
  type        = string
  default     = "outrena-dev-rg"
}

# ── Networking ────────────────────────────────────────────────────────────────
variable "vnet_cidr" {
  description = "VNet CIDR. Must not collide with on-prem or peered VNets."
  type        = string
  default     = "10.1.0.0/16"
}

variable "subnets" {
  description = <<-EOT
    Map of subnet CIDRs per migration doc §12.1 layout:
      app_gateway — AppGatewaySubnet (Application Gateway nodes, no delegation)
      apps        — AppSubnet (delegated to Microsoft.App/environments for backend+frontend+worker Container Apps Environment)
      data        — DataSubnet (PostgreSQL Flexible + Redis + Blob Private Endpoints)
      idp         — IdpSubnet (delegated to Microsoft.App/environments for Keycloak Container Apps Environment)
    Container Apps Environment requires /23 or larger.
  EOT
  type = object({
    app_gateway = string
    apps        = string
    data        = string
    idp         = string
  })
  default = {
    app_gateway = "10.1.0.0/24"
    apps        = "10.1.4.0/23"
    data        = "10.1.2.0/24"
    idp         = "10.1.6.0/23"
  }
}

# ── Container App sizing ──────────────────────────────────────────────────────
# Per migration doc §12.3 — backend (2-10 replicas, autoscale on CPU ≥ 70%),
# frontend (2-4), worker (2-6), Keycloak (2).

variable "backend_cpu" {
  description = "vCPU allocation per backend replica (in cores, e.g. 1.0 = 1 vCPU)."
  type        = number
  default     = 1.0
}

variable "backend_memory" {
  description = "Memory allocation per backend replica (e.g. 2.0Gi)."
  type        = string
  default     = "2.0Gi"
}

variable "backend_min_replicas" {
  type    = number
  default = 2
}

variable "backend_max_replicas" {
  type    = number
  default = 10
}

variable "frontend_cpu" {
  type    = number
  default = 0.5
}

variable "frontend_memory" {
  type    = string
  default = "1.0Gi"
}

variable "frontend_min_replicas" {
  type    = number
  default = 2
}

variable "frontend_max_replicas" {
  type    = number
  default = 4
}

variable "worker_cpu" {
  type    = number
  default = 1.0
}

variable "worker_memory" {
  type    = string
  default = "2.0Gi"
}

variable "worker_min_replicas" {
  type    = number
  default = 2
}

variable "worker_max_replicas" {
  type    = number
  default = 6
}

variable "keycloak_cpu" {
  type    = number
  default = 1.0
}

variable "keycloak_memory" {
  type    = string
  default = "2.0Gi"
}

variable "keycloak_min_replicas" {
  type    = number
  default = 2
}

variable "keycloak_max_replicas" {
  type    = number
  default = 4
}

# ── Azure Database for PostgreSQL 16 Flexible Server ─────────────────────────
variable "postgres_sku" {
  description = "PostgreSQL Flexible Server SKU. dev/staging: GP_Gen5_2, prod: GP_Gen5_4 (per migration doc §12.3)."
  type        = string
  default     = "GP_Gen5_2"
}

variable "postgres_storage_mb" {
  description = "Storage (MB) for PostgreSQL Flexible Server."
  type        = number
  default     = 51200
}

variable "postgres_backup_retention_days" {
  description = "Automated backup retention. Migration doc requires 35 days in prod for PITR."
  type        = number
  default     = 7
}

variable "postgres_geo_redundant_backup" {
  description = "Geo-redundant backup (paired region). MUST be true in prod."
  type        = bool
  default     = false
}

variable "postgres_high_availability" {
  description = "Zone-redundant HA. MUST be true in prod."
  type        = bool
  default     = false
}

variable "postgres_version" {
  type    = string
  default = "16"
}

variable "postgres_admin_login" {
  type    = string
  default = "outrena_admin"
}

variable "database_name" {
  type    = string
  default = "outrena"
}

variable "keycloak_database_name" {
  type    = string
  default = "keycloak"
}

# ── Azure Cache for Redis ────────────────────────────────────────────────────
variable "redis_sku" {
  description = "Redis SKU. dev/staging: Standard, prod: Premium (per migration doc §12.3 — Premium required for VNet injection)."
  type        = string
  default     = "Standard"
  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.redis_sku)
    error_message = "redis_sku must be one of: Basic, Standard, Premium."
  }
}

variable "redis_family" {
  description = "Redis family. C = Basic/Standard price-reduced, P = Premium."
  type        = string
  default     = "C"
}

variable "redis_capacity" {
  description = "Redis capacity (1 = C1 / P1, 2 = C2 / P2, ...). Default C1 (1GB) per migration doc §12.3."
  type        = number
  default     = 1
}

variable "redis_version" {
  description = "Redis major version. Note: Redis 7 may require Premium SKU + newer azurerm provider; default 6 for cross-tier compat."
  type        = string
  default     = "6"
}

# ── Blob Storage ──────────────────────────────────────────────────────────────
variable "csv_storage_account_name" {
  description = "Globally-unique storage account for CSV uploads. Must be 3-24 lowercase alphanumeric (no hyphens)."
  type        = string
  default     = "outrenadevcsv"
}

variable "collateral_storage_account_name" {
  description = "Globally-unique storage account for sales collateral (PDFs, images)."
  type        = string
  default     = "outrenadevcollateral"
}

variable "csv_container_name" {
  type    = string
  default = "csv-uploads"
}

variable "collateral_container_name" {
  type    = string
  default = "collateral"
}

variable "storage_redundancy" {
  description = "Storage account replication. dev/staging: LRS, prod: GRS (per migration doc §12.3 — geo-redundant for DR)."
  type        = string
  default     = "LRS"
  validation {
    condition     = contains(["LRS", "GRS", "RAGRS", "ZRS", "GZRS"], var.storage_redundancy)
    error_message = "storage_redundancy must be one of: LRS, GRS, RAGRS, ZRS, GZRS."
  }
}

# ── Key Vault ─────────────────────────────────────────────────────────────────
variable "key_vault_name" {
  description = "Globally-unique Key Vault name (3-24 alphanumeric + hyphen)."
  type        = string
  default     = "outrena-dev-kv"
}

# ── Container Registry ───────────────────────────────────────────────────────
variable "acr_name" {
  description = "Globally-unique ACR name (5-50 alphanumeric only, no hyphens)."
  type        = string
  default     = "outrenadevacr"
}

variable "acr_sku" {
  description = "ACR SKU. dev/staging: Standard, prod: Premium (for georeplications + Private Endpoint)."
  type        = string
  default     = "Standard"
}

# ── Application Gateway ───────────────────────────────────────────────────────
variable "appgw_sku" {
  description = "App Gateway SKU. Always WAF_v2 per migration doc §12.1."
  type        = string
  default     = "WAF_v2"
}

variable "appgw_min_capacity" {
  description = "App Gateway autoscale min instances. Prod: 2 for WAF failover."
  type        = number
  default     = 2
}

variable "appgw_max_capacity" {
  type    = number
  default = 10
}

# ── Container images ──────────────────────────────────────────────────────────
variable "acr_backend_tag" {
  description = "Image tag for the backend + worker (shared image). Set by CI/CD to the git SHA."
  type        = string
  default     = "latest"
}

variable "acr_frontend_tag" {
  description = "Image tag for the frontend."
  type        = string
  default     = "latest"
}

variable "keycloak_image" {
  description = "Keycloak container image. Pin to a specific digest in prod."
  type        = string
  default     = "quay.io/keycloak/keycloak:24.0"
}

# ── Logging ───────────────────────────────────────────────────────────────────
variable "log_retention_days" {
  description = "Log Analytics workspace retention. dev: 7, staging: 30, prod: 90."
  type        = number
  default     = 7
}

# ── Blue/Green cutover (Traffic Manager) ──────────────────────────────────────
variable "blue_green_weight_new" {
  description = "Traffic Manager weight on the NEW (FastAPI) stack. 0 = dark, 100 = full cutover. Migration doc Phase 6 exit: 5 → 25 → 50 → 100 over 7 days."
  type        = number
  default     = 100
}

variable "blue_green_weight_old" {
  description = "Traffic Manager weight on the OLD (Next.js) stack. 100 - blue_green_weight_new by default."
  type        = number
  default     = 0
}

variable "legacy_endpoint_target" {
  description = "FQDN or IP of the legacy Next.js stack (Traffic Manager external endpoint target). Placeholder in dev — set per env in tfvars."
  type        = string
  default     = "legacy-nextjs.azurewebsites.net"
}

# ── App config (passed to Container Apps as env vars / secrets) ───────────────
# Note: DATABASE_URL is NOT a variable — Azure DB provides connection strings
# via Key Vault refs (constructed in key_vault.tf after Postgres is created).
# Same pattern for REDIS_URL and BLOB_CONNECTION_STRING.

variable "keycloak_realm" {
  type    = string
  default = "outrena"
}

variable "keycloak_admin_username" {
  type      = string
  default   = "admin"
  sensitive = true
}

variable "keycloak_admin_password" {
  description = "Keycloak admin password. If empty, a random one is generated and stored in Key Vault."
  type        = string
  default     = ""
  sensitive   = true
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

# ── Alerting ──────────────────────────────────────────────────────────────────
variable "alert_email" {
  description = "Email address for Azure Monitor action group + alert receivers."
  type        = string
  default     = "ops@outrena.com"
}

# ── SOC2 / Activity Log / Key Vault rotation (SAAS-INFRA) ────────────────────
variable "security_alert_email" {
  description = "Email endpoint for the SOC2 security action group (separate from var.alert_email). Route to the security team on-call."
  type        = string
  default     = "security@outrena.com"
}

variable "key_vault_secret_rotation_days" {
  description = "Rotation interval (days) for Key Vault secrets managed by the rotation Function App. Runbook 11 promises 30d."
  type        = number
  default     = 30
}
