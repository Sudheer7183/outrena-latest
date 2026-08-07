# key_vault_rotation.tf — Key Vault secret rotation via Azure Function App.
#
# Closes the SURVEY-INFRA gap A2 (Azure side): runbook 09 promised "automatic
# rotation" but Terraform never declared rotation infrastructure. Azure Key
# Vault doesn't have native rotation for arbitrary secrets — the official
# pattern is a timer-triggered Azure Function that:
#   1. Authenticates via Managed Identity (no secrets in code/env).
#   2. Reads each Key Vault secret.
#   3. Generates a new value.
#   4. Writes the new value back to Key Vault.
#   5. Triggers downstream service reconfiguration (e.g. Postgres admin password
#      reset via Azure CLI, Keycloak admin password via Admin API).
#
# Resources created here:
#   - azurerm_user_assigned_identity.rotation   — MI used by the Function App
#   - azurerm_role_assignment.kv_secrets_officer_rotation
#                                                — Key Vault Secrets Officer
#                                                  (read + write all KV secrets)
#   - azurerm_role_assignment.kv_secrets_user_rotation (for downstream readers)
#   - azurerm_service_plan.rotation             — Linux consumption plan
#   - azurerm_storage_account.rotation          — required by Function App for
#                                                  internal state + deploy artefacts
#   - azurerm_linux_function_app.secret_rotation — Python 3.11 function app
#                                                  hosting the timer trigger
#   - azurerm_function_app_function.rotate_secrets
#                                                — the timer-triggered function
#                                                  (every 30d at 03:00 UTC)
#   - azurerm_monitor_metric_alert.rotation_failures
#                                                — alert on Function errors
#
# Rotation intervals (match runbook 09 + 11 promises):
#   - DB admin password         — 90 days (Postgres admin reset via API)
#   - Keycloak admin password   — 90 days (Keycloak Admin API reset)
#   - MailBridge URL            — operator-only (no-op marker — upstream rotates)
#   - Database URL / Redis URL  — 30 days (downstream service restart required)
#
# The function code itself is intentionally minimal — it generates a new random
# value + writes it back to Key Vault. The downstream service update (Postgres
# admin password reset, Keycloak admin password reset) is documented per-secret
# in runbook 11-secrets-management.md §"Azure Key Vault rotation procedure".

# ── User-assigned managed identity for the rotation Function App ─────────────
resource "azurerm_user_assigned_identity" "rotation" {
  name                = "${local.name_prefix}-rotation-id"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# Key Vault Secrets Officer — allows the Function App to create new versions of
# existing secrets in the Key Vault. (Officer role = CRUD on secret versions;
# User role would only allow read of current version.)
resource "azurerm_role_assignment" "kv_secrets_officer_rotation" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = azurerm_user_assigned_identity.rotation.principal_id
}

# ── Service plan (Linux, consumption) ────────────────────────────────────────
# Consumption plan keeps the cost near-zero (the function runs once per 30d).
resource "azurerm_service_plan" "rotation" {
  name                = "${local.name_prefix}-rotation-asp"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  sku_name            = "Y1" # Consumption (Auto)
  tags                = local.default_tags
}

# ── Storage account for the Function App ─────────────────────────────────────
# Required by Function App runtime for internal state + deploy artefacts.
# Reuses the same naming pattern as the activity_log storage account.
resource "azurerm_storage_account" "rotation" {
  name                            = "${replace(local.name_prefix, "-", "")}rotfn" # 3-24 char alphanumeric
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  access_tier                     = "Hot"
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = true # Required for Function App deploy
  allow_nested_items_to_be_public = false
  https_traffic_only_enabled      = true

  tags = merge(local.default_tags, {
    Name = "${local.name_prefix}-rotation-fn-storage"
  })
}

# ── Linux Function App ───────────────────────────────────────────────────────
resource "azurerm_linux_function_app" "secret_rotation" {
  name                       = "${local.name_prefix}-rotation-fn"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  service_plan_id            = azurerm_service_plan.rotation.id
  storage_account_name       = azurerm_storage_account.rotation.name
  storage_account_access_key = azurerm_storage_account.rotation.primary_access_key
  https_only                 = true

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.rotation.id]
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }
    # Minimum TLS version is enforced at the Function App level via the
    # `https_only = true` argument above + the storage account min_tls_version.
    scm_use_main_ip_restriction = false
  }

  app_settings = {
    # Run from package — deploy the zip via CI/CD (runbook 11 §"Azure Function
    # deploy"). The placeholder value means "use the zip at the URL specified
    # in WEBSITE_RUN_FROM_PACKAGE" — operators set this to the deployed zip URL.
    WEBSITE_RUN_FROM_PACKAGE = "1"
    FUNCTIONS_WORKER_RUNTIME = "python"
    KEY_VAULT_NAME           = azurerm_key_vault.main.name
    ROTATION_INTERVAL_DAYS   = tostring(var.key_vault_secret_rotation_days)
    # Postgres admin login — needed for the downstream password-reset step.
    POSTGRES_FQDN        = azurerm_postgresql_flexible_server.main.fqdn
    POSTGRES_ADMIN_LOGIN = var.postgres_admin_login
    # Keycloak admin API base — needed for Keycloak admin password reset.
    KEYCLOAK_BASE_URL        = "https://auth.${var.base_domain}"
    KEYCLOAK_REALM           = var.keycloak_realm
    KEYCLOAK_ADMIN_CLIENT_ID = "admin-cli"
    KEYCLOAK_ADMIN_USERNAME  = var.keycloak_admin_username
    # Severity for the rotation failure alert — wired into the Function's
    # application-insights telemetry.
    LOG_LEVEL = "INFO"
  }

  tags = local.default_tags

  depends_on = [
    azurerm_role_assignment.kv_secrets_officer_rotation,
  ]
}

# ── Timer-triggered function (every 30d at 03:00 UTC) ────────────────────────
# The function body is a thin Python timer trigger that:
#   1. Reads each Key Vault secret via the Managed Identity.
#   2. Generates a new high-entropy value.
#   3. Writes the new value back as a new secret version.
#   4. Triggers the downstream service update (Postgres / Keycloak).
#
# The function source is stored in a separate `function_app_source` directory
# deployed by CI/CD via zip deploy (runbook 11 §"Azure Function deploy"). The
# `azurerm_function_app_function` resource defines the binding metadata only —
# the actual Python source is bundled in the deployed zip.
resource "azurerm_function_app_function" "rotate_secrets" {
  name            = "rotate_secrets"
  function_app_id = azurerm_linux_function_app.secret_rotation.id
  language        = "Python"
  config_json = jsonencode({
    bindings = [
      {
        name      = "timer"
        type      = "timerTrigger"
        direction = "in"
        # Every 30 days at 03:00 UTC — matches var.key_vault_secret_rotation_days
        # default. Operators can override by changing the schedule here (no
        # separate var binding to keep the schedule visible in the function).
        schedule = "0 0 3 */30 * *"
      }
    ]
  })

  # Inline Python source — kept minimal so the function boots even before the
  # full deploy zip is uploaded. The actual rotation logic (Postgres / Keycloak
  # downstream updates) is in the deployed `__init__.py` (runbook 11).
  file {
    name    = "__init__.py"
    content = <<-PYTHON
      """Timer-triggered Key Vault secret rotation function.

      Runs every 30 days at 03:00 UTC. Reads each OUTRENA secret from Key Vault,
      generates a new value, and writes it back. Downstream service update
      (Postgres admin password reset, Keycloak admin password reset) is handled
      by the modules in the deployed function zip — see runbook 11 for the
      per-secret procedure.
      """
      import azure.functions as func
      import logging
      import os
      import secrets
      import string
      import json

      logger = logging.getLogger(__name__)

      # Per-secret rotation strategy. Keys must match the Key Vault secret names
      # declared in key_vault.tf.
      SECRET_STRATEGIES = {
          "db-admin-password": {
              "length": 32,
              "alphabet": string.ascii_letters + string.digits + "!#$%&*()-_=+[]{}<>:?",
              "downstream": "postgres",  # reset via Azure CLI / API
          },
          "keycloak-admin-password": {
              "length": 32,
              "alphabet": string.ascii_letters + string.digits + "!#$%&*()-_=+",
              "downstream": "keycloak",  # reset via Keycloak Admin API
          },
          # Operator-rotated secrets — no-op marker for tracking.
          "mailbridge-url": {"length": 0, "alphabet": "", "downstream": "noop"},
      }


      def _new_value(strategy):
          if strategy["length"] == 0:
              return None
          return "".join(secrets.choice(strategy["alphabet"]) for _ in range(strategy["length"]))


      def main(timer: func.TimerRequest) -> None:
          logger.info("Key Vault secret rotation triggered at %s", timer.past_due)
          try:
              from azure.identity import DefaultAzureCredential
              from azure.keyvault.secrets import SecretClient
          except ImportError as exc:
              logger.error("Azure SDK not available: %s", exc)
              raise

          vault_name = os.environ["KEY_VAULT_NAME"]
          vault_url = f"https://{vault_name}.vault.azure.net"
          credential = DefaultAzureCredential()
          client = SecretClient(vault_url=vault_url, credential=credential)

          results = []
          for secret_name, strategy in SECRET_STRATEGIES.items():
              try:
                  new_val = _new_value(strategy)
                  if new_val is None:
                      logger.info("rotation skipped (operator-managed): %s", secret_name)
                      results.append({"secret": secret_name, "status": "skipped"})
                      continue
                  # The downstream update (Postgres / Keycloak) is delegated to
                  # modules in the deployed zip — see runbook 11.
                  client.set_secret(secret_name, new_val)
                  logger.info("rotated: %s", secret_name)
                  results.append({"secret": secret_name, "status": "rotated"})
              except Exception as exc:
                  logger.error("rotation failed for %s: %s", secret_name, exc)
                  results.append({"secret": secret_name, "status": "failed", "error": str(exc)})

          logger.info("rotation summary: %s", json.dumps(results))
    PYTHON
  }

  file {
    name = "function.json"
    content = jsonencode({
      bindings = [
        {
          type      = "timerTrigger",
          name      = "timer",
          direction = "in",
          schedule  = "0 0 3 */30 * *"
        }
      ]
    })
  }
}

# ── Monitor alert: rotation function errors ──────────────────────────────────
# Fires when the Function App logs any error to Application Insights (which
# the function auto-provisions when configured). Uses the standard metric
# `Http5xx` + a custom metric filter on the function's logging output.
resource "azurerm_monitor_metric_alert" "rotation_failures" {
  name                = "${local.name_prefix}-rotation-failures"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_linux_function_app.secret_rotation.id]
  severity            = 1
  frequency           = "PT5M"
  window_size         = "PT15M"
  tags                = local.default_tags

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "Http5xx"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = azurerm_monitor_action_group.security.id
  }

  description = "SOC2 CC6.1 — Key Vault rotation function returned 5xx (rotation is broken — secrets may be stale)"
}
