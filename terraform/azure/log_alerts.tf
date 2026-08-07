# log_alerts.tf — Scheduled log-query alert rules on Log Analytics workspace.
#
# Per migration doc Risk #15 (MailBridge downtime kills scheduler tick) —
# alert on `mailbridge.send_failed` log count > 10 in 5 min.
# Per migration doc §15.1 testing strategy — alert on backend ERROR log
# count > 10 in 5 min (catches unhandled exceptions before users notice).
#
# These use `azurerm_monitor_scheduled_query_rules_alert` (v2 scheduled query
# rules) which evaluate a KQL query against the Log Analytics workspace at a
# fixed frequency.

# ── Backend ERROR count > 10 in 5 min ────────────────────────────────────────
resource "azurerm_monitor_scheduled_query_rules_alert" "backend_errors" {
  name                = "${local.name_prefix}-backend-errors"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  severity            = 1
  frequency           = 5
  time_window         = 5
  tags                = local.default_tags

  data_source_id = azurerm_log_analytics_workspace.main.id

  # ContainerAppConsoleLogs is the table populated by the Container Apps
  # Environment diagnostic setting (monitoring.tf). Filter on the backend
  # container app + ERROR level.
  query = <<-KQL
    ContainerAppConsoleLogs
    | where ContainerAppName =~ "${azurerm_container_app.backend.name}"
    | where LogEntry has "ERROR"
    | summarize error_count = count()
    | where error_count > 10
  KQL

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }

  action {
    action_group = azurerm_monitor_action_group.email.id
  }

  depends_on = [
    azurerm_monitor_diagnostic_setting.cae_main,
  ]
}

# ── MailBridge send_failed count > 10 in 5 min ───────────────────────────────
# Risk #15 mitigation — alert ops when mailbridge starts rejecting sends
# (so the scheduler-tick retry queue doesn't silently grow).
resource "azurerm_monitor_scheduled_query_rules_alert" "mailbridge_send_failed" {
  name                = "${local.name_prefix}-mailbridge-send-failed"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  severity            = 1
  frequency           = 5
  time_window         = 5
  tags                = local.default_tags

  data_source_id = azurerm_log_analytics_workspace.main.id

  # Match the structured log event name emitted by app/services/mailbridge_service.py.
  # The event is emitted via structlog as `event="mailbridge.send_failed"`.
  query = <<-KQL
    ContainerAppConsoleLogs
    | where ContainerAppName in ("${azurerm_container_app.backend.name}", "${azurerm_container_app.worker.name}")
    | where LogEntry has "mailbridge.send_failed"
    | summarize fail_count = count()
    | where fail_count > 10
  KQL

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }

  action {
    action_group = azurerm_monitor_action_group.email.id
  }

  depends_on = [
    azurerm_monitor_diagnostic_setting.cae_main,
  ]
}

# ── Keycloak auth failures spike (potential brute-force) ─────────────────────
# Bonus alert — fires when Keycloak logs > 20 "TYPE=LOGIN_ERROR" events in
# 5 min (indicates a credential-stuffing attack on a tenant).
resource "azurerm_monitor_scheduled_query_rules_alert" "keycloak_auth_failures" {
  name                = "${local.name_prefix}-keycloak-auth-failures"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  severity            = 2
  frequency           = 5
  time_window         = 5
  tags                = local.default_tags

  data_source_id = azurerm_log_analytics_workspace.main.id

  query = <<-KQL
    ContainerAppConsoleLogs
    | where ContainerAppName =~ "${azurerm_container_app.keycloak.name}"
    | where LogEntry has "LOGIN_ERROR"
    | summarize fail_count = count()
    | where fail_count > 20
  KQL

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }

  action {
    action_group = azurerm_monitor_action_group.email.id
  }

  depends_on = [
    azurerm_monitor_diagnostic_setting.cae_idp,
  ]
}
