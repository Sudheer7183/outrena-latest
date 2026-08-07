# main.tf — Resource Group + naming + default tags.
#
# All Phase-6 Azure resources live in a single resource group (per migration
# doc §12). Resource naming convention: `${local.name_prefix}-<role>` where
# name_prefix = "${var.project_name}-${var.environment_short}" (e.g. outrena-dev).

# Current subscription / tenant — needed for Key Vault RBAC role assignments
# and for data-plane principal lookups.
data "azurerm_client_config" "current" {}

locals {
  # Naming prefix used across every named resource.
  name_prefix = "${var.project_name}-${var.environment_short}"

  # Default tags merged into every resource's `tags` block via
  # `tags = merge(local.default_tags, { ... })`. Mirrors the AWS default_tags
  # pattern (§11) — no native azurerm provider default_tags exists.
  default_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Repo        = "outrena-migration"
    Cloud       = "azure"
    Phase       = "phase-6"
  }

  # Convenience flag — many resources toggle zone redundancy / geo replication
  # based on whether we're in prod.
  is_prod = var.environment == "production"
}

# ── Resource Group ───────────────────────────────────────────────────────────
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.default_tags
}
