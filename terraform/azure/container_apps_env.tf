# container_apps_env.tf — Container Apps Environments + Log Analytics.
#
# Per migration doc §12.1 + §12.3, two Container Apps Environments:
#   main — AppSubnet. Hosts backend + frontend + worker.
#   idp  — IdpSubnet. Hosts Keycloak only (blast-radius isolation per §12.1).
#
# Both environments share a single Log Analytics workspace for centralized
# ContainerAppConsoleLogs / AppLogs.

# ── Log Analytics workspace ──────────────────────────────────────────────────
resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.name_prefix}-logs"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  tags                = local.default_tags
}

# ── Container Apps Environment — main (backend + frontend + worker) ──────────
resource "azurerm_container_app_environment" "main" {
  name                           = "${local.name_prefix}-cae"
  location                       = azurerm_resource_group.main.location
  resource_group_name            = azurerm_resource_group.main.name
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.main.id
  infrastructure_subnet_id       = azurerm_subnet.apps.id
  internal_load_balancer_enabled = false
  zone_redundancy_enabled        = local.is_prod

  tags = local.default_tags

  depends_on = [azurerm_subnet_network_security_group_association.apps]
}

# ── Container Apps Environment — idp (Keycloak only) ─────────────────────────
# Separate env on IdpSubnet per migration doc §12.1 diagram (Identity subnet).
# Keeps Keycloak's blast radius separate from the main app stack.
resource "azurerm_container_app_environment" "idp" {
  name                           = "${local.name_prefix}-cae-idp"
  location                       = azurerm_resource_group.main.location
  resource_group_name            = azurerm_resource_group.main.name
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.main.id
  infrastructure_subnet_id       = azurerm_subnet.idp.id
  internal_load_balancer_enabled = false
  zone_redundancy_enabled        = local.is_prod

  tags = local.default_tags

  depends_on = [azurerm_subnet_network_security_group_association.idp]
}
