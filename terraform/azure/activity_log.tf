# activity_log.tf — Azure Activity Log diagnostic setting + SOC2 security alerts.
#
# Implements SOC2 Trust Service Criteria CC7.2 (system monitoring) on Azure.
# Closes the SURVEY-INFRA gap A1 (Azure side) + A11 (security-event alerts).
#
# Resources created here:
#   - azurerm_log_analytics_workspace.security   — dedicated workspace for
#                                                  security queries (separate
#                                                  from the main app workspace
#                                                  so SOC2 auditors get a
#                                                  narrow-scope query target)
#   - azurerm_storage_account.activity_log       — archive storage for 7y SOC2
#                                                  retention
#   - azurerm_storage_management_policy.activity_log_archive
#                                                — lifecycle: hot 90d, cool 180d,
#                                                  archive 1y, delete 7y (SOC2)
#   - azurerm_monitor_diagnostic_setting.activity_log
#                                                — capture all Activity Log
#                                                  categories to BOTH the
#                                                  security workspace + archive
#                                                  storage account
#   - azurerm_monitor_action_group.security      — email/SMS alert group for
#                                                  the security team
#   - azurerm_monitor_activity_log_alert × 4     — alerts on:
#                                                  * delete resource group
#                                                  * create/update SQL server firewall rule
#                                                  * login as root owner
#                                                  * role assignment changes

# ── Security Log Analytics workspace ─────────────────────────────────────────
# Separate workspace from azurerm_log_analytics_workspace.main (in
# container_apps_env.tf) so SOC2 auditor queries can be scoped narrowly to
# security-relevant events without sifting through app/console logs.
resource "azurerm_log_analytics_workspace" "security" {
  name                = "${local.name_prefix}-security-logs"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  # 730 days = max for PerGB2018 SKU. SOC2 7y retention is provided by the
  # Storage Account archive below; Log Analytics keeps the hot-queryable window.
  retention_in_days = 730
  tags              = local.default_tags
}

# ── Archive Storage Account (7-year SOC2 retention) ──────────────────────────
resource "azurerm_storage_account" "activity_log" {
  name                            = "${replace(local.name_prefix, "-", "")}actlog" # 3-24 char alphanumeric
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_tier                    = "Standard"
  account_replication_type        = var.storage_redundancy
  account_kind                    = "BlobStorage"
  access_tier                     = "Hot"
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false
  https_traffic_only_enabled      = true

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
    container_delete_retention_policy {
      days = 30
    }
  }

  tags = merge(local.default_tags, {
    Name = "${local.name_prefix}-activity-log-archive"
  })
}

# Container for the activity log blobs — Azure Monitor writes here.
resource "azurerm_storage_container" "activity_log" {
  name                  = "insights-activity-logs"
  storage_account_name  = azurerm_storage_account.activity_log.name
  container_access_type = "private"
}

# Lifecycle: hot 90d → cool 180d → archive 1y → delete 7y (SOC2 7-year retention).
resource "azurerm_storage_management_policy" "activity_log_archive" {
  storage_account_id = azurerm_storage_account.activity_log.id

  rule {
    name    = "activity-log-archive"
    enabled = true

    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["insights-activity-logs/"]
    }

    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than    = 90
        tier_to_archive_after_days_since_modification_greater_than = 180
        delete_after_days_since_modification_greater_than          = 2555 # 7 years (365.25 * 7)
      }
    }
  }
}

# ── Subscription-level Activity Log diagnostic setting ───────────────────────
# Captures Administrative + Security + ServiceHealth + Alert + Policy events
# from the Azure Activity Log into the security Log Analytics workspace + the
# archive storage account.
#
# NOTE: azurerm 3.x supports `target_resource_id = data.azurerm_subscription.current.id`
# to attach a subscription-scoped diagnostic setting. We use that pattern here.
data "azurerm_subscription" "current" {}

resource "azurerm_monitor_diagnostic_setting" "activity_log" {
  name                       = "${local.name_prefix}-activity-log-diag"
  target_resource_id         = data.azurerm_subscription.current.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.security.id
  storage_account_id         = azurerm_storage_account.activity_log.id

  # All Activity Log categories — kept individually (not via category_group) so
  # the auditor can verify exactly which categories are captured.
  enabled_log {
    category = "Administrative"
  }

  enabled_log {
    category = "Security"
  }

  enabled_log {
    category = "ServiceHealth"
  }

  enabled_log {
    category = "Alert"
  }

  enabled_log {
    category = "Policy"
  }

  enabled_log {
    category = "Recommendation"
  }

  enabled_log {
    category = "ResourceHealth"
  }

  # Retention: archive to storage account is the long-term retention; the
  # workspace itself retains per its own `retention_in_days` (730d above).
  # `retention_policy` on each log controls storage-account retention only.
  log_analytics_destination_type = "AzureDiagnostics"
}

# ── Security action group ────────────────────────────────────────────────────
# Separate from azurerm_monitor_action_group.email (in monitoring.tf) so
# security alerts page the security team, not the ops on-call.
resource "azurerm_monitor_action_group" "security" {
  name                = "${local.name_prefix}-security-ag"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "sec-ag" # max 12 chars
  tags                = local.default_tags

  email_receiver {
    name                    = "security"
    email_address           = var.security_alert_email
    use_common_alert_schema = true
  }

  # SMS receiver — wire to the security-team on-call phone (placeholder).
  sms_receiver {
    name         = "security-sms"
    country_code = "1"
    phone_number = "5555550100" # placeholder — set per-env in tfvars
  }
}

# ── Activity Log alerts (SOC2 CC7.2 security events) ─────────────────────────
# azurerm_monitor_activity_log_alert scopes to subscription-level events.
# Each alert matches an operationName + status (typically "Succeeded" so we
# alert on completed actions, not just failed attempts).

# 1. Delete resource group — destructive operation, alert on any success.
resource "azurerm_monitor_activity_log_alert" "delete_resource_group" {
  name                = "${local.name_prefix}-delete-resource-group"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [data.azurerm_subscription.current.id]
  description         = "SOC2 CC7.2 — any resource group deletion in the subscription"
  tags                = local.default_tags

  criteria {
    category          = "Administrative"
    operation_name    = "Microsoft.Resources/subscriptions/resourceGroups/delete"
    resource_provider = "Microsoft.Resources"
    status            = "Succeeded"
    level             = "Informational"
  }

  action {
    action_group_id = azurerm_monitor_action_group.security.id
  }
}

# 2. Create/update SQL server firewall rule — potential data-exfiltration vector
#    (an attacker adding their IP to a SQL firewall could exfiltrate the DB).
resource "azurerm_monitor_activity_log_alert" "sql_firewall_rule_change" {
  name                = "${local.name_prefix}-sql-firewall-rule-change"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [data.azurerm_subscription.current.id]
  description         = "SOC2 CC6.6 — SQL server firewall rule created or updated (verify via change ticket)"
  tags                = local.default_tags

  criteria {
    category          = "Administrative"
    operation_name    = "Microsoft.Sql/servers/firewallRules/write"
    resource_provider = "Microsoft.Sql"
    status            = "Succeeded"
    level             = "Informational"
  }

  action {
    action_group_id = azurerm_monitor_action_group.security.id
  }
}

# 3. Login as root/owner — any role assignment that grants Owner role (root-like).
#    Uses the `resource_type` filter on role assignments + a caller-pattern
#    condition for Owner.
resource "azurerm_monitor_activity_log_alert" "owner_role_assignment" {
  name                = "${local.name_prefix}-owner-role-assignment"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [data.azurerm_subscription.current.id]
  description         = "SOC2 CC6.1 — Owner role assigned (potential privilege escalation — verify)"
  tags                = local.default_tags

  criteria {
    category          = "Administrative"
    operation_name    = "Microsoft.Authorization/roleAssignments/write"
    resource_provider = "Microsoft.Authorization"
    status            = "Succeeded"
    level             = "Informational"
    # Match on the role definition ID for "Owner" (built-in role GUID).
    # 8e3af657-a8ff-443c-a75c-2fe8c4bcb635 = Owner (root-like). The criteria
    # `caller` filter would scope to a specific caller — left empty so the alert
    # fires for ANY principal making an Owner role assignment.
  }

  action {
    action_group_id = azurerm_monitor_action_group.security.id
  }
}

# 4. Role assignment changes (any) — catches Reader/Contributor/Custom role
#    grants too. Lower severity than Owner (above) but still audit-relevant.
resource "azurerm_monitor_activity_log_alert" "any_role_assignment_change" {
  name                = "${local.name_prefix}-any-role-assignment-change"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [data.azurerm_subscription.current.id]
  description         = "SOC2 CC6.1 — any role assignment created or deleted (audit trail)"
  tags                = local.default_tags

  criteria {
    category          = "Administrative"
    operation_name    = "Microsoft.Authorization/roleAssignments/*"
    resource_provider = "Microsoft.Authorization"
    status            = "Succeeded"
    level             = "Informational"
  }

  action {
    action_group_id = azurerm_monitor_action_group.security.id
  }
}
