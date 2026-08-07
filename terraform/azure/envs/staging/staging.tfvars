# envs/staging/staging.tfvars — staging environment values.
# Apply: terraform apply -var-file=envs/staging/staging.tfvars

# ── Global ──
location            = "eastus"
environment         = "staging"
environment_short   = "stg"
base_domain         = "staging.azure.outrena.dev"
project_name        = "outrena"
resource_group_name = "outrena-stg-rg"

# ── Networking ──
vnet_cidr = "10.2.0.0/16"
subnets = {
  app_gateway = "10.2.0.0/24"
  apps        = "10.2.4.0/23"
  data        = "10.2.2.0/24"
  idp         = "10.2.6.0/23"
}

# ── Container App sizing (staging = mirror prod at half-capacity) ──
backend_min_replicas  = 2
backend_max_replicas  = 6
backend_cpu           = 1.0
backend_memory        = "2.0Gi"
frontend_min_replicas = 2
frontend_max_replicas = 4
worker_min_replicas   = 2
worker_max_replicas   = 4
keycloak_min_replicas = 2
keycloak_max_replicas = 4

# ── PostgreSQL (staging: same SKU as prod but no HA — cost) ──
postgres_sku                   = "GP_Gen5_2"
postgres_storage_mb            = 102400
postgres_backup_retention_days = 14
postgres_geo_redundant_backup  = false
postgres_high_availability     = false

# ── Redis (staging: Standard C1) ──
redis_sku      = "Standard"
redis_family   = "C"
redis_capacity = 1
redis_version  = "6"

# ── Blob storage ──
csv_storage_account_name        = "outrenastgcsv"
collateral_storage_account_name = "outrenastgcollateral"
storage_redundancy              = "LRS"

# ── Key Vault ──
key_vault_name = "outrena-stg-kv"

# ── ACR ──
acr_name = "outrenastgacr"
acr_sku  = "Standard"

# ── Logging ──
log_retention_days = 30

# ── Blue/Green cutover (staging: 50/50 — soak test alongside legacy) ──
blue_green_weight_new  = 50
blue_green_weight_old  = 50
legacy_endpoint_target = "legacy-nextjs-staging.azurewebsites.net"

# ── App config ──
keycloak_realm          = "outrena"
keycloak_admin_username = "admin"
keycloak_admin_password = ""
llm_api_url             = "https://open.bigmodel.cn/api/paas/v4"
mailbridge_url          = "https://mailbridge-staging.example.local/inbound"
scheduler_tick_seconds  = 300
scheduler_partial_cap   = 5
allowed_origins         = "[\"https://*.staging.azure.outrena.dev\"]"
log_level               = "INFO"
skip_jwt_verification   = false
verify_jwt_issuer       = true

# ── Container images ──
acr_backend_tag  = "staging"
acr_frontend_tag = "staging"
keycloak_image   = "quay.io/keycloak/keycloak:24.0"

# ── Alerting ──
alert_email = "ops@outrena.com"
