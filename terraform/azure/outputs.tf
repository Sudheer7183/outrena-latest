# outputs.tf — public surface area for downstream CI/CD + ops runbooks.

# ── Edge ─────────────────────────────────────────────────────────────────────
output "app_gateway_fqdn" {
  description = "Public FQDN of the Application Gateway (where user traffic lands)."
  value       = azurerm_public_ip.appgw.fqdn
}

output "app_gateway_public_ip" {
  description = "Public IP of the Application Gateway (for DNS A-record pointing)."
  value       = azurerm_public_ip.appgw.ip_address
}

output "traffic_manager_fqdn" {
  description = "Traffic Manager FQDN — CNAME this from your vanity domain for blue/green cutover."
  value       = azurerm_traffic_manager_profile.main.fqdn
}

# ── Data plane ───────────────────────────────────────────────────────────────
output "postgres_fqdn" {
  description = "PostgreSQL Flexible Server FQDN (resolves to a private IP inside the VNet via PE)."
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "redis_hostname" {
  description = "Azure Cache for Redis hostname (resolves to a private IP inside the VNet via PE)."
  value       = azurerm_redis_cache.main.hostname
}

output "csv_storage_account_name" {
  value = azurerm_storage_account.csv.name
}

output "collateral_storage_account_name" {
  value = azurerm_storage_account.collateral.name
}

# ── Container Apps (revision FQDNs — used by App Gateway backend pools) ──────
output "backend_revision_fqdn" {
  description = "Latest revision FQDN of the backend Container App."
  value       = azurerm_container_app.backend.latest_revision_fqdn
}

output "frontend_revision_fqdn" {
  value = azurerm_container_app.frontend.latest_revision_fqdn
}

output "worker_revision_fqdn" {
  value = azurerm_container_app.worker.latest_revision_fqdn
}

output "keycloak_revision_fqdn" {
  description = "Latest revision FQDN of the Keycloak Container App (internal — only reachable via App Gateway /auth/*)."
  value       = azurerm_container_app.keycloak.latest_revision_fqdn
}

# ── Secrets / registries ─────────────────────────────────────────────────────
output "key_vault_uri" {
  description = "Key Vault URI — used by CI/CD to push additional secrets (e.g., real TLS cert in prod)."
  value       = azurerm_key_vault.main.vault_uri
}

output "acr_login_server" {
  description = "ACR login server — `docker login` target for CI/CD push."
  value       = azurerm_container_registry.main.login_server
}

# ── Identities (for downstream role assignments) ────────────────────────────
output "backend_identity_principal_id" {
  description = "Principal ID of the backend managed identity — grant to any new secret in Key Vault."
  value       = azurerm_user_assigned_identity.backend.principal_id
}

output "worker_identity_principal_id" {
  value = azurerm_user_assigned_identity.worker.principal_id
}

output "keycloak_identity_principal_id" {
  value = azurerm_user_assigned_identity.keycloak.principal_id
}

# ── Log Analytics ────────────────────────────────────────────────────────────
output "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID — for Kusto queries in ops runbooks."
  value       = azurerm_log_analytics_workspace.main.id
}

output "log_analytics_customer_id" {
  description = "Log Analytics customer (workspace) ID — used by the ContainerAppConsoleLogs KQL queries."
  value       = azurerm_log_analytics_workspace.main.workspace_id
}

# ── SOC2 / Activity Log / Key Vault rotation outputs (SAAS-INFRA) ────────────
output "log_analytics_security_workspace_id" {
  description = "Log Analytics workspace ID for security queries (separate from the main app workspace — narrow scope for SOC2 auditors)."
  value       = azurerm_log_analytics_workspace.security.id
}

output "activity_log_archive_storage_account" {
  description = "Storage account name for the 7-year SOC2 Activity Log archive (hot 90d, cool 180d, archive 1y, delete 7y)."
  value       = azurerm_storage_account.activity_log.name
}

output "activity_log_diagnostic_setting_name" {
  description = "Name of the subscription-level Activity Log diagnostic setting (captures Administrative + Security + ServiceHealth + Alert + Policy categories)."
  value       = azurerm_monitor_diagnostic_setting.activity_log.name
}

output "security_action_group_name" {
  description = "Azure Monitor action group name for SOC2 security alerts (separate from the ops action group)."
  value       = azurerm_monitor_action_group.security.name
}

output "key_vault_rotation_function_name" {
  description = "Azure Function App name hosting the timer-triggered Key Vault secret rotation (every 30d at 03:00 UTC)."
  value       = azurerm_linux_function_app.secret_rotation.name
}

output "key_vault_rotation_identity_principal_id" {
  description = "Principal ID of the rotation Function App's user-assigned managed identity — has Key Vault Secrets Officer role."
  value       = azurerm_user_assigned_identity.rotation.principal_id
}
