# envs/dev/dev.tfvars — dev environment values.
# Apply: terraform apply -var-file=envs/dev/dev.tfvars

# ── Global ──
location            = "eastus"
environment         = "development"
environment_short   = "dev"
base_domain         = "azure.outrena.dev"
project_name        = "outrena"
resource_group_name = "outrena-dev-rg"

# ── Networking ──
vnet_cidr = "10.1.0.0/16"
subnets = {
  app_gateway = "10.1.0.0/24"
  apps        = "10.1.4.0/23"
  data        = "10.1.2.0/24"
  idp         = "10.1.6.0/23"
}

# ── Container App sizing (dev = smallest reasonable) ──
backend_min_replicas  = 1
backend_max_replicas  = 4
backend_cpu           = 0.5
backend_memory        = "1.0Gi"
frontend_min_replicas = 1
frontend_max_replicas = 2
worker_min_replicas   = 1
worker_max_replicas   = 3
keycloak_min_replicas = 1
keycloak_max_replicas = 2

# ── PostgreSQL ──
postgres_sku                   = "GP_Gen5_2"
postgres_storage_mb            = 51200
postgres_backup_retention_days = 7
postgres_geo_redundant_backup  = false
postgres_high_availability     = false

# ── Redis ──
redis_sku      = "Standard"
redis_family   = "C"
redis_capacity = 1
redis_version  = "6"

# ── Blob storage ──
csv_storage_account_name        = "outrenadevcsv"
collateral_storage_account_name = "outrenadevcollateral"
storage_redundancy              = "LRS"

# ── Key Vault ──
key_vault_name = "outrena-dev-kv"

# ── ACR ──
acr_name = "outrenadevacr"
acr_sku  = "Standard"

# ── Logging ──
log_retention_days = 7

# ── Blue/Green cutover (dev: 100% new — no legacy stack to mirror) ──
blue_green_weight_new  = 100
blue_green_weight_old  = 0
legacy_endpoint_target = "legacy-nextjs-dev.azurewebsites.net"

# ── App config ──
keycloak_realm          = "outrena"
keycloak_admin_username = "admin"
keycloak_admin_password = "" # random_password generates one if empty
llm_api_url             = "https://open.bigmodel.cn/api/paas/v4"
mailbridge_url          = ""
scheduler_tick_seconds  = 300
scheduler_partial_cap   = 5
allowed_origins         = "[\"http://localhost:5173\",\"http://localhost\",\"https://*.azure.outrena.dev\"]"
log_level               = "DEBUG"
skip_jwt_verification   = false # dev still verifies JWT; flip true ONLY for local docker-compose
verify_jwt_issuer       = true

# ── Container images ──
acr_backend_tag  = "latest"
acr_frontend_tag = "latest"
keycloak_image   = "quay.io/keycloak/keycloak:24.0"

# ── Alerting ──
alert_email = "ops@outrena.com"
