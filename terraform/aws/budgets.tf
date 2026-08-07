# budgets.tf — OUTRENA AWS Budgets + per-tenant budget pattern.
#
# Migration doc §14 Risk #22 + Phase 8 SAAS2-OBS-BE runbook (runbooks/14-cost-management.md).
#
# THREE platform-level budgets:
#   1. outrena-<env>-monthly  — total monthly spend. 50/80/100% alerts.
#   2. outrena-<env>-llm      — LLM API spend (Anthropic / OpenAI / ZAI / Google).
#      Filtered by tag Service=LLM. 80/100% alerts. Separate budget per
#      migration doc Risk #22 (LLM cost is the largest variable cost driver).
#   3. outrena-<env>-compute  — EC2 + ECS + Fargate spend. Filtered by
#      Service in {Amazon Elastic Compute Cloud, Amazon Elastic Container Service}.
#      80/100% alerts.
#
# PER-TENANT budgets are NOT created here (tenants are runtime-provisioned
# via the platform API and don't exist at terraform plan time). The pattern
# is:
#   - Each tenant resource carries `Tenant = <slug>` tag (enforced via
#     provider default_tags + per-resource tags).
#   - The platform's tenant_provisioning_service can call the AWS Budgets
#     API to create a per-tenant budget at provisioning time (see the
#     "Per-tenant budget pattern" section at the bottom of this file).
# This file creates the platform-level budgets (always present) and
# documents the per-tenant extension.
#
# Budget notifications go to the same SNS topic as the CloudWatch alarms
# (aws_sns_topic.alerts). The SNS topic has an email subscription
# (var.alert_email, default ops@outrena.com — override per-env in tfvars).

# ── Data source: current AWS account ID ─────────────────────────────────────
# Used as the budget account_id. The aws_caller_identity.current data source
# is declared in s3.tf (for the ALB logs bucket policy) — we re-use it here
# rather than redeclaring. If s3.tf is ever removed, declare a fresh one.

# ── Variables (locals_extra.tf pattern — do NOT edit variables.tf) ──────────

variable "budget_monthly_limit_usd" {
  description = "Monthly budget limit in USD for the platform-wide budget. Override in prod tfvars (e.g., 5000 for dev, 50000 for prod)."
  type        = number
  default     = 1000
}

variable "budget_llm_limit_usd" {
  description = "Monthly LLM-spend budget limit in USD. Separate from the platform budget per migration doc Risk #22 (LLM is the largest variable cost driver)."
  type        = number
  default     = 500
}

variable "budget_compute_limit_usd" {
  description = "Monthly EC2 + ECS + Fargate budget limit in USD."
  type        = number
  default     = 800
}

# ── 1. Platform-wide monthly budget ─────────────────────────────────────────
resource "aws_budgets_budget" "monthly" {
  name              = "${local.name_prefix}-monthly"
  budget_type       = "COST"
  limit_amount      = var.budget_monthly_limit_usd
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2025-01-01_00:00"

  # 50% — informational, email SRE list (default SNS subscription).
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 50
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
  # 80% — escalate to SRE lead (use the same email for simplicity; ops can
  # refine by adding an additional SNS subscription with a filter).
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
  # 100% — page on-call. Same SNS topic that drives CloudWatch alarms; the
  # on-call PagerDuty subscription is wired separately (outside terraform).
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  tags = {
    Name = "${local.name_prefix}-monthly-budget"
  }
}

# ── 2. LLM-spend budget (filtered by tag Service=LLM) ───────────────────────
# Per migration doc Risk #22: LLM is the largest variable cost driver and
# gets its own budget. The Service=LLM tag is applied to:
#   - The LLM API calls themselves (not natively tagged in AWS — this is
#     informational; the actual per-tenant LLM cost is tracked in the app
#     DB via usage_events.cost_cents, not AWS Cost Explorer).
#   - S3 buckets / EFS volumes that hold LLM-generated collateral.
# In practice this budget tracks any resource with the LLM Service tag,
# which is a small subset of total LLM cost (the API calls themselves go
# through the vendor, not AWS). Treat this as a proxy metric.
resource "aws_budgets_budget" "llm" {
  name              = "${local.name_prefix}-llm"
  budget_type       = "COST"
  limit_amount      = var.budget_llm_limit_usd
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2025-01-01_00:00"

  # Cost filter — tag Service=LLM
  cost_filter {
    name = "TagKeyValue"
    values = [
      "Service$LLM",
    ]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  tags = {
    Name = "${local.name_prefix}-llm-budget"
  }
}

# ── 3. Compute budget (EC2 + ECS + Fargate) ─────────────────────────────────
resource "aws_budgets_budget" "compute" {
  name              = "${local.name_prefix}-compute"
  budget_type       = "COST"
  limit_amount      = var.budget_compute_limit_usd
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2025-01-01_00:00"

  # Cost filter — Service in {EC2, ECS, Fargate}
  cost_filter {
    name = "Service"
    values = [
      "Amazon Elastic Compute Cloud - Compute",
      "Amazon Elastic Container Service",
      "Amazon EC2 Container Service",
    ]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  tags = {
    Name = "${local.name_prefix}-compute-budget"
  }
}

# ── Per-tenant budget pattern ───────────────────────────────────────────────
# Per-tenant budgets are NOT created here because tenants are runtime-
# provisioned (via the platform's tenant_provisioning_service) and don't
# exist at terraform plan time. Instead, the platform provisions a per-
# tenant budget via the AWS Budgets API at tenant-creation time. The
# pattern is:
#
#   # Pseudocode for the platform's per-tenant budget creation (Python +
#   # boto3, called from tenant_provisioning_service.provision()):
#   import boto3
#   budgets = boto3.client("budgets")
#   budgets.create_budget(
#       AccountId=account_id,
#       Budget={
#           "BudgetName": f"outrena-{tenant_slug}-monthly",
#           "BudgetType": "COST",
#           "BudgetLimit": {"Amount": str(tenant_monthly_budget_usd), "Unit": "USD"},
#           "TimeUnit": "MONTHLY",
#           "TimePeriod": {"Start": "2025-01-01_00:00"},
#           "CostFilters": {"TagKeyValue": [f"Tenant${tenant_slug}"]},
#       },
#       NotificationsWithSubscribers=[
#           {
#               "Notification": {
#                   "NotificationType": "ACTUAL",
#                   "ComparisonOperator": "GREATER_THAN",
#                   "Threshold": 80,
#                   "ThresholdType": "PERCENTAGE",
#               },
#               "Subscribers": [
#                   {"SubscriptionType": "EMAIL", "Address": ops_email},
#               ],
#           },
#           # ... 100% notification ...
#       ],
#   )
#
# This file creates the platform-level budgets (always present); the per-
# tenant budgets are added on top at runtime. See runbooks/14-cost-management.md
# §4.1 for the operator-facing description.

# ── Outputs ─────────────────────────────────────────────────────────────────
output "budget_monthly_arn" {
  description = "ARN of the platform-wide monthly budget (use with aws budgets describe-budget)."
  value       = aws_budgets_budget.monthly.id
}

output "budget_llm_arn" {
  description = "ARN of the LLM-spend budget."
  value       = aws_budgets_budget.llm.id
}

output "budget_compute_arn" {
  description = "ARN of the compute budget."
  value       = aws_budgets_budget.compute.id
}

output "aws_account_id" {
  description = "AWS account ID the budgets are created in (for cross-reference with the per-tenant pattern)."
  value       = data.aws_caller_identity.current.account_id
}
