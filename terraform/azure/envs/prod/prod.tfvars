# envs/prod/prod.tfvars — production environment values.
# Apply: terraform apply -var-file=envs/prod/prod.tfvars
#
# Per migration doc §12.3 + §13.2 prod column:
#   - GP_Gen5_4 zone-redundant HA Postgres
#   - Premium P1 Redis
#   - GRS Blob storage
#   - ACR Premium with georeplications
#   - 35-day backup retention + geo-redundant backup
#   - blue_green_weight_new=5 (start of cutover), old=95 — see §16.3

# ── Global ──
location            = "eastus"
environment         = "production"
environment_short   = "prd"
base_domain         = "azure.outrena.com"
project_name        = "outrena"
resource_group_name = "outrena-prd-rg"

# ── Networking ──
vnet_cidr = "10.3.0.0/16"
subnets = {
  app_gateway = "10.3.0.0/24"
  apps        = "10.3.4.0/23"
  data        = "10.3.2.0/24"
  idp         = "10.3.6.0/23"
}

# ── Container App sizing (prod = max) ──
backend_min_replicas  = 2
backend_max_replicas  = 10
backend_cpu           = 1.0
backend_memory        = "2.0Gi"
frontend_min_replicas = 2
frontend_max_replicas = 4
worker_min_replicas   = 2
worker_max_replicas   = 6
keycloak_min_replicas = 2
keycloak_max_replicas = 4

# ── PostgreSQL (prod: GP_Gen5_4, zone-redundant HA, 35-day PITR, geo-redundant) ──
postgres_sku                   = "GP_Gen5_4"
postgres_storage_mb            = 102400
postgres_backup_retention_days = 35
postgres_geo_redundant_backup  = true
postgres_high_availability     = true

# ── Redis (prod: Premium P1 — supports VNet injection + better SLA) ──
redis_sku      = "Premium"
redis_family   = "P"
redis_capacity = 1
redis_version  = "6"

# ── Blob storage (prod: GRS for DR) ──
csv_storage_account_name        = "outrenaprdcsv"
collateral_storage_account_name = "outrenaprdcollateral"
storage_redundancy              = "GRS"

# ── Key Vault ──
key_vault_name = "outrena-prd-kv"

# ── ACR (prod: Premium for georeplications + Private Endpoint) ──
acr_name = "outrenaprdacr"
acr_sku  = "Premium"

# ── Logging (prod: 90-day retention) ──
log_retention_days = 90

# ── Blue/Green cutover (prod: START at 5/95, ramp to 100/0 over 7 days per §16.3) ──
# After successful ramp: set blue_green_weight_new=100, blue_green_weight_old=0.
# Keep legacy stack retained for 14 days post-cutover (§16.3 Risk #18).
blue_green_weight_new  = 5
blue_green_weight_old  = 95
legacy_endpoint_target = "legacy-nextjs-prod.azurewebsites.net"

# ── App config ──
keycloak_realm          = "outrena"
keycloak_admin_username = "admin"
keycloak_admin_password = "" # random_password generates one if empty
llm_api_url             = "https://open.bigmodel.cn/api/paas/v4"
mailbridge_url          = "https://mailbridge-prod.example.local/inbound"
scheduler_tick_seconds  = 300
scheduler_partial_cap   = 10
allowed_origins         = "[\"https://*.azure.outrena.com\"]"
log_level               = "INFO"
skip_jwt_verification   = false # MUST be false in prod (CI audit_env.py enforces)
verify_jwt_issuer       = true

# ── Container images ──
# In prod: pin to a specific git SHA tag, never `latest`.
acr_backend_tag  = "v1.0.0"
acr_frontend_tag = "v1.0.0"
keycloak_image   = "quay.io/keycloak/keycloak:24.0"

# ── Alerting ──
alert_email = "ops@outrena.com"
