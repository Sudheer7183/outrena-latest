# postgres.tf — Azure Database for PostgreSQL 16 Flexible Server.
#
# Per migration doc §12.3:
#   - GP_Gen5_2 SKU (prod: GP_Gen5_4)
#   - Zone-redundant HA in prod
#   - 35-day backup retention in prod (PITR)
#   - Geo-redundant backup in prod (paired-region DR)
#
# Network: delegated DataSubnet + private DNS zone privatelink.postgres.database.
# azure.com → data plane traffic stays inside the VNet, never traverses the
# public internet.

# ── Private DNS Zone for PostgreSQL ──────────────────────────────────────────
resource "azurerm_private_dns_zone" "pg" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "pg" {
  name                  = "${local.name_prefix}-pg-dns-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.pg.name
  virtual_network_id    = azurerm_virtual_network.main.id
  tags                  = local.default_tags
}

# ── PostgreSQL Flexible Server ───────────────────────────────────────────────
resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${local.name_prefix}-pg"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = var.postgres_version
  sku_name                      = var.postgres_sku
  storage_mb                    = var.postgres_storage_mb
  backup_retention_days         = var.postgres_backup_retention_days
  geo_redundant_backup_enabled  = var.postgres_geo_redundant_backup
  administrator_login           = var.postgres_admin_login
  administrator_password        = random_password.db_admin_password.result
  delegated_subnet_id           = azurerm_subnet.data.id
  private_dns_zone_id           = azurerm_private_dns_zone.pg.id
  public_network_access_enabled = false

  dynamic "high_availability" {
    for_each = var.postgres_high_availability ? [1] : []
    content {
      mode = "ZoneRedundant"
    }
  }

  # Maintenance window — Sundays 02:00 UTC (low-traffic window for OUTRENA).
  maintenance_window {
    day_of_week  = 0
    start_hour   = 2
    start_minute = 0
  }

  tags = merge(local.default_tags, {
    Name = "${local.name_prefix}-pg"
  })

  # Postgres flexible server cannot be created until the delegated subnet +
  # private DNS zone link exist.
  depends_on = [
    azurerm_private_dns_zone_virtual_network_link.pg,
    azurerm_subnet_network_security_group_association.data,
  ]
}

# ── Application databases (outrena + keycloak) ───────────────────────────────
resource "azurerm_postgresql_flexible_server_database" "outrena" {
  name      = var.database_name
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_database" "keycloak" {
  name      = var.keycloak_database_name
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# ── Security-hardening server parameters ─────────────────────────────────────
# Audit logging + connection throttling per Azure security baseline.
resource "azurerm_postgresql_flexible_server_configuration" "log_connections" {
  name      = "log_connections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_configuration" "log_disconnections" {
  name      = "log_disconnections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_configuration" "connection_throttling" {
  name      = "connection_throttling"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

# ── Diagnostic setting → Log Analytics ───────────────────────────────────────
# All Postgres logs (QueryStoreRuntimeUsage, PostgreSQLLogs) + metrics shipped
# to the central Log Analytics workspace (created in container_apps_env.tf).
resource "azurerm_monitor_diagnostic_setting" "postgres" {
  name                       = "${local.name_prefix}-pg-diag"
  target_resource_id         = azurerm_postgresql_flexible_server.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_log {
    category_group = "auditLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
