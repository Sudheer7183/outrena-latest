# monitoring.tf — Azure Monitor action group, metric alerts, and diagnostic
# settings.
#
# Per migration doc §12 + Risk #15 (MailBridge downtime) + Risk #12 (scheduler
# starvation):
#   - Email action group → var.alert_email
#   - Metric alerts: backend CPU > 80%, postgres CPU > 80%, postgres storage
#     > 80%, redis server load > 90%, app gateway unhealthy host count > 0,
#     app gateway failed requests > 100/min
#   - Diagnostic settings: app gateway, container apps env, all → Log Analytics
#
# Log-pattern alert rules (ERROR count, mailbridge.send_failed count) live in
# log_alerts.tf because they require scheduled_query_rules_alert resources.

# ── Action group (email receiver) ────────────────────────────────────────────
resource "azurerm_monitor_action_group" "email" {
  name                = "${local.name_prefix}-email-ag"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "outrena-em" # max 12 chars
  tags                = local.default_tags

  email_receiver {
    name                    = "ops"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

# ── Metric alerts ────────────────────────────────────────────────────────────

# Backend CPU > 80% for 5 min
resource "azurerm_monitor_metric_alert" "backend_cpu" {
  name                = "${local.name_prefix}-backend-cpu-high"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_container_app.backend.id]
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.default_tags

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "cpuUsage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}

# Postgres CPU > 80% for 5 min
resource "azurerm_monitor_metric_alert" "postgres_cpu" {
  name                = "${local.name_prefix}-postgres-cpu-high"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_postgresql_flexible_server.main.id]
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.default_tags

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "cpu_percent"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}

# Postgres storage > 80% for 5 min
resource "azurerm_monitor_metric_alert" "postgres_storage" {
  name                = "${local.name_prefix}-postgres-storage-high"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_postgresql_flexible_server.main.id]
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.default_tags

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "storage_percent"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}

# Redis server load > 90% for 5 min
resource "azurerm_monitor_metric_alert" "redis_server_load" {
  name                = "${local.name_prefix}-redis-server-load-high"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_redis_cache.main.id]
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.default_tags

  criteria {
    metric_namespace = "Microsoft.Cache/redis"
    metric_name      = "serverLoad"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 90
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}

# App Gateway: unhealthy host count > 0 for 2 min (any backend down)
resource "azurerm_monitor_metric_alert" "appgw_unhealthy_hosts" {
  name                = "${local.name_prefix}-appgw-unhealthy-hosts"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_application_gateway.main.id]
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.default_tags

  criteria {
    metric_namespace = "Microsoft.Network/applicationGateways"
    metric_name      = "UnhealthyHostCount"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}

# App Gateway: failed requests > 100/min
resource "azurerm_monitor_metric_alert" "appgw_failed_requests" {
  name                = "${local.name_prefix}-appgw-failed-requests"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_application_gateway.main.id]
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT1M"
  tags                = local.default_tags

  criteria {
    metric_namespace = "Microsoft.Network/applicationGateways"
    metric_name      = "FailedRequests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 100
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}

# ── Diagnostic settings → Log Analytics ──────────────────────────────────────
# (Postgres diagnostic setting lives in postgres.tf alongside the server.)
resource "azurerm_monitor_diagnostic_setting" "appgw" {
  name                       = "${local.name_prefix}-appgw-diag"
  target_resource_id         = azurerm_application_gateway.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

resource "azurerm_monitor_diagnostic_setting" "cae_main" {
  name                       = "${local.name_prefix}-cae-main-diag"
  target_resource_id         = azurerm_container_app_environment.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

resource "azurerm_monitor_diagnostic_setting" "cae_idp" {
  name                       = "${local.name_prefix}-cae-idp-diag"
  target_resource_id         = azurerm_container_app_environment.idp.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

resource "azurerm_monitor_diagnostic_setting" "redis" {
  name                       = "${local.name_prefix}-redis-diag"
  target_resource_id         = azurerm_redis_cache.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
