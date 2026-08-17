# versions.tf — OUTRENA Azure Terraform provider pinning.
#
# Pinned to versions known-good with the migration doc (§12 Azure Deployment
# Architecture). Bump only after a planned upgrade window.

terraform {
  required_version = ">= 1.7.0, < 2.0.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.1"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state — one storage account container per Organisation, one key
  # per environment (dev / staging / prod). State file locking is provided
  # natively by an Azure Storage blob lease, so no separate lock table is
  # needed (unlike AWS S3 + DynamoDB).
  backend "azurerm" {
    # storage_account_name, container_name, key, resource_group_name are
    # overridden per-env via `terraform init -backend-config=envs/<env>/backend.tfbackend`.
    use_oidc = true
  }
}

provider "azurerm" {
  # `skip_provider_registration` defaults to false → azurerm auto-registers
  # the resource providers we use (Microsoft.Network, Microsoft.App,
  # Microsoft.DBforPostgreSQL, Microsoft.Cache, Microsoft.Storage,
  # Microsoft.KeyVault, Microsoft.ContainerRegistry) on first apply. Leave
  # the default; azurerm 3.x doesn't expose a `resource_provider_registrations`
  # narrowing knob (that lands in 4.x).

  features {
    # Key Vault: never auto-purge soft-deleted vaults; allow terraform to
    # recover a soft-deleted vault of the same name on re-create.
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }

    # Don't block resource_group destroy when child resources still exist
    # (children are destroyed first by terraform graph ordering).
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

# ── Default tags (no native provider default_tags in azurerm, so we
# merge local.default_tags into every resource's `tags` block — see main.tf).
# Convention used throughout: `tags = merge(local.default_tags, { Name = ... })`.
