# cost_alerts.tf — OUTRENA Azure Cost Management budgets + alerts.
#
# Migration doc §14 Risk #22 + Phase 8 SAAS2-OBS-BE runbook (runbooks/14-cost-management.md).
#
# THREE platform-level cost budgets:
#   1. outrena-<env>-monthly  — total monthly spend. 50/80/100% alerts.
#   2. outrena-<env>-llm      — LLM spend (Anthropic / OpenAI / ZAI / Google).
#      Filtered by tag Service=LLM. 80/100% alerts. Separate budget per
#      migration doc Risk #22 (LLM is the largest variable cost driver).
#   3. outrena-<env>-compute  — Container Apps + Container Apps Env compute
#      spend. Filtered by ResourceProvider == Microsoft.App. 80/100% alerts.
#
# PER-TENANT budgets are NOT created here (tenants are runtime-provisioned
# via the platform API and don't exist at terraform plan time). The pattern
# is documented at the bottom of this file — the platform's
# tenant_provisioning_service can call the Azure Cost Management REST API
# to create a per-tenant budget at provisioning time.
#
# Cost alerts go to the SAME action group as the Azure Monitor metric
# alerts (azurerm_monitor_action_group.email — defined in monitoring.tf).
# That action group has an email receiver for var.alert_email (default
# ops@outrena.com — override per-env in tfvars).

# ── Variables (extra inputs — do NOT edit variables.tf) ─────────────────────

variable "cost_budget_monthly_limit_usd" {
  description = "Monthly platform-wide cost budget limit in USD. Override in prod tfvars (e.g., 1000 for dev, 50000 for prod)."
  type        = number
  default     = 1000
}

variable "cost_budget_llm_limit_usd" {
  description = "Monthly LLM-spend cost budget limit in USD. Separate from the platform budget per migration doc Risk #22."
  type        = number
  default     = 500
}

variable "cost_budget_compute_limit_usd" {
  description = "Monthly Container Apps compute budget limit in USD."
  type        = number
  default     = 800
}

# ── 1. Platform-wide monthly cost budget ────────────────────────────────────
# azurerm_consumption_budget_resource_group scopes the budget to the OUTRENA
# resource group (azurerm_resource_group.main). All Phase-6 resources live
# in this RG, so this is equivalent to a subscription-level budget for our
# purposes (we don't have multi-RG sprawl).
resource "azurerm_consumption_budget_resource_group" "monthly" {
  name              = "${local.name_prefix}-monthly"
  resource_group_id = azurerm_resource_group.main.id

  amount            = var.cost_budget_monthly_limit_usd
  time_grain        = "Monthly"
  time_period {
    start_date = "2025-01-01T00:00:00Z"
    end_date   = "2026-12-31T23:59:59Z" # Azure requires an end_date; we set it ~2 years out and refresh.
  }

  filter {
    dimension {
      name = "ResourceGroupName"
      values = [azurerm_resource_group.main.name]
    }
  }

  # 50% — informational, email ops list.
  notification {
    enabled   = true
    threshold = 50.0
    operator  = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }
  # 80% — escalate to SRE lead (same email; ops can refine with extra receivers).
  notification {
    enabled   = true
    threshold = 80.0
    operator  = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }
  # 100% — page on-call. Same contact list; the on-call PagerDuty
  # subscription is wired separately (outside terraform).
  notification {
    enabled   = true
    threshold = 100.0
    operator  = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }

  # NOTE: azurerm_consumption_budget_resource_group does not support a
  # `tags` argument (Azure Cost Management budgets don't carry tags).
  # The provider default_tags in versions.tf still tag the underlying
  # resource where supported, but the budget object itself is tag-less.
}

# ── 2. LLM-spend cost budget (filtered by tag Service=LLM) ─────────────────
# Per migration doc Risk #22: LLM is the largest variable cost driver and
# gets its own budget. The Service=LLM tag is applied to:
#   - Azure Container Apps that run the LLM gateway (backend, worker).
#   - Storage accounts that hold LLM-generated collateral.
# In practice, the LLM API calls themselves go through the vendor
# (Anthropic / OpenAI / ZAI / Google), not Azure, so this budget tracks
# the Azure-side infra cost of running the LLM gateway — not the vendor
# LLM cost itself. The per-tenant LLM vendor cost is tracked in the app
# DB via usage_events.cost_cents (see runbooks/14-cost-management.md §1).
resource "azurerm_consumption_budget_resource_group" "llm" {
  name              = "${local.name_prefix}-llm"
  resource_group_id = azurerm_resource_group.main.id

  amount            = var.cost_budget_llm_limit_usd
  time_grain        = "Monthly"
  time_period {
    start_date = "2025-01-01T00:00:00Z"
    end_date   = "2026-12-31T23:59:59Z"
  }

  filter {
    tag {
      name = "Service"
      values = ["LLM"]
    }
  }

  notification {
    enabled   = true
    threshold = 80.0
    operator  = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }
  notification {
    enabled   = true
    threshold = 100.0
    operator  = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }
}

# ── 3. Compute cost budget (Microsoft.App — Container Apps) ─────────────────
resource "azurerm_consumption_budget_resource_group" "compute" {
  name              = "${local.name_prefix}-compute"
  resource_group_id = azurerm_resource_group.main.id

  amount            = var.cost_budget_compute_limit_usd
  time_grain        = "Monthly"
  time_period {
    start_date = "2025-01-01T00:00:00Z"
    end_date   = "2026-12-31T23:59:59Z"
  }

  filter {
    dimension {
      name = "ServiceName"
      values = ["Container Apps"]
    }
  }

  notification {
    enabled   = true
    threshold = 80.0
    operator  = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }
  notification {
    enabled   = true
    threshold = 100.0
    operator  = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }
}

# ── Per-tenant budget pattern ───────────────────────────────────────────────
# Per-tenant budgets are NOT created here because tenants are runtime-
# provisioned (via the platform's tenant_provisioning_service) and don't
# exist at terraform plan time. Instead, the platform provisions a per-
# tenant budget via the Azure Cost Management REST API at tenant-creation
# time. The pattern is:
#
#   # Pseudocode for the platform's per-tenant budget creation (Python +
#   # azure-mgmt-consumption, called from tenant_provisioning_service):
#   from azure.mgmt.consumption import ConsumptionManagementClient
#   client = ConsumptionManagementClient(credential, subscription_id)
#   client.budgets.create_or_update(
#       resource_group_name=rg_name,
#       budget_name=f"outrena-{tenant_slug}-monthly",
#       parameters={
#           "eTag": None,
#           "properties": {
#               "category": "Cost",
#               "amount": tenant_monthly_budget_usd,
#               "timeGrain": "Monthly",
#               "timePeriod": {
#                   "startDate": "2025-01-01T00:00:00Z",
#                   "endDate": "2026-12-31T23:59:59Z",
#               },
#               "filter": {
#                   "tags": {
#                       "name": "Tenant",
#                       "operator": "In",
#                       "values": [tenant_slug],
#                   }
#               },
#               "notifications": {
#                   "80pct": {
#                       "enabled": True,
#                       "operator": "GreaterThan",
#                       "threshold": 80.0,
#                       "contactEmails": [ops_email],
#                   },
#                   "100pct": {
#                       "enabled": True,
#                       "operator": "GreaterThan",
#                       "threshold": 100.0,
#                       "contactEmails": [ops_email],
#                   },
#               },
#           },
#       },
#   )
#
# This file creates the platform-level budgets (always present); the per-
# tenant budgets are added on top at runtime. See runbooks/14-cost-management.md
# §4.2 for the operator-facing description.

# ── Outputs ─────────────────────────────────────────────────────────────────
output "azure_cost_budget_monthly_id" {
  description = "ID of the platform-wide monthly cost budget."
  value       = azurerm_consumption_budget_resource_group.monthly.id
}

output "azure_cost_budget_llm_id" {
  description = "ID of the LLM-spend cost budget."
  value       = azurerm_consumption_budget_resource_group.llm.id
}

output "azure_cost_budget_compute_id" {
  description = "ID of the Container Apps compute cost budget."
  value       = azurerm_consumption_budget_resource_group.compute.id
}
