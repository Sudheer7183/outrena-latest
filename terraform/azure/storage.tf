# storage.tf — Blob Storage accounts for CSV uploads + sales collateral.
#
# Per migration doc §12.3 — outrena<env>csv + outrena<env>collateral, soft
# delete + versioning. Both accounts use Private Endpoints (privatelink.blob.
# core.windows.net) so the data plane never traverses the public internet.

# ── Private DNS Zone for Blob ────────────────────────────────────────────────
resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "blob" {
  name                  = "${local.name_prefix}-blob-dns-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.blob.name
  virtual_network_id    = azurerm_virtual_network.main.id
  tags                  = local.default_tags
}

# ── CSV storage account ──────────────────────────────────────────────────────
resource "azurerm_storage_account" "csv" {
  name                            = var.csv_storage_account_name
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
    Name = "${local.name_prefix}-csv-storage"
  })
}

# ── Collateral storage account ───────────────────────────────────────────────
resource "azurerm_storage_account" "collateral" {
  name                            = var.collateral_storage_account_name
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
      days = 90
    }
    container_delete_retention_policy {
      days = 90
    }
  }

  tags = merge(local.default_tags, {
    Name = "${local.name_prefix}-collateral-storage"
  })
}

# ── Storage containers ───────────────────────────────────────────────────────
resource "azurerm_storage_container" "csv" {
  name                  = var.csv_container_name
  storage_account_name  = azurerm_storage_account.csv.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "collateral" {
  name                  = var.collateral_container_name
  storage_account_name  = azurerm_storage_account.collateral.name
  container_access_type = "private"
}

# ── Private Endpoints (Blob subresource) ─────────────────────────────────────
resource "azurerm_private_endpoint" "csv_blob" {
  name                = "${local.name_prefix}-csv-blob-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.data.id
  tags                = local.default_tags

  private_service_connection {
    name                           = "${local.name_prefix}-csv-blob-psc"
    private_connection_resource_id = azurerm_storage_account.csv.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob.id]
  }
}

resource "azurerm_private_endpoint" "collateral_blob" {
  name                = "${local.name_prefix}-collateral-blob-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.data.id
  tags                = local.default_tags

  private_service_connection {
    name                           = "${local.name_prefix}-collateral-blob-psc"
    private_connection_resource_id = azurerm_storage_account.collateral.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob.id]
  }
}

# ── Network rules (default Deny, allow from AppSubnet) ───────────────────────
# Public network access is already disabled at the account level; these rules
# further tighten the data plane to ONLY the AppSubnet (where backend +
# worker live) plus the Container Apps managed identity.
resource "azurerm_storage_account_network_rules" "csv" {
  storage_account_id = azurerm_storage_account.csv.id

  default_action             = "Deny"
  bypass                     = ["AzureServices"]
  virtual_network_subnet_ids = [azurerm_subnet.apps.id]
}

resource "azurerm_storage_account_network_rules" "collateral" {
  storage_account_id = azurerm_storage_account.collateral.id

  default_action             = "Deny"
  bypass                     = ["AzureServices"]
  virtual_network_subnet_ids = [azurerm_subnet.apps.id]
}

# ── Lifecycle management policy (Hot → Cool → Archive → Delete) ──────────────
# Cool after 30d, Archive after 90d, Delete after 365d — matches the migration
# doc §12.3 implicit retention policy + cost optimisation for old CSVs.
resource "azurerm_storage_management_policy" "csv" {
  storage_account_id = azurerm_storage_account.csv.id

  rule {
    name    = "csv-lifecycle"
    enabled = true

    filters {
      blob_types = ["blockBlob"]
    }

    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than    = 30
        tier_to_archive_after_days_since_modification_greater_than = 90
        delete_after_days_since_modification_greater_than          = 365
      }
    }
  }
}

resource "azurerm_storage_management_policy" "collateral" {
  storage_account_id = azurerm_storage_account.collateral.id

  rule {
    name    = "collateral-lifecycle"
    enabled = true

    filters {
      blob_types = ["blockBlob"]
    }

    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than    = 90
        tier_to_archive_after_days_since_modification_greater_than = 180
        # Sales collateral is never auto-deleted (legal hold on PDFs) —
        # omit delete_after_days_since_modification_greater_than entirely.
      }
    }
  }
}

# ── Blob connection strings stored in Key Vault ─────────────────────────────
resource "azurerm_key_vault_secret" "csv_blob_connection_string" {
  name         = "csv-blob-connection-string"
  value        = azurerm_storage_account.csv.primary_blob_connection_string
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.default_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}

resource "azurerm_key_vault_secret" "collateral_blob_connection_string" {
  name         = "collateral-blob-connection-string"
  value        = azurerm_storage_account.collateral.primary_blob_connection_string
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.default_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}
