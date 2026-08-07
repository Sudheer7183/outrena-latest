# acr.tf — Azure Container Registry + AcrPull role assignments for each
# Container App managed identity.
#
# Per migration doc §12.3 + §12.1:
#   - dev/staging: Standard SKU, public_network_access_enabled=false (PE only)
#   - prod: Premium SKU with georeplications (paired-region) + zone redundancy
#   - network_rule_set: default Deny, allow from AppSubnet (where CAE pulls)
#   - admin_enabled=false — all auth via managed identities (AcrPull role)

# ── Container Registry ───────────────────────────────────────────────────────
resource "azurerm_container_registry" "main" {
  name                          = var.acr_name
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  sku                           = var.acr_sku
  admin_enabled                 = false
  public_network_access_enabled = false
  zone_redundancy_enabled       = local.is_prod

  # Premium-tier georeplication in prod — replicates content to a paired
  # region for fast pulls during regional failover.
  dynamic "georeplications" {
    for_each = local.is_prod ? ["westus2"] : []
    content {
      location                = georeplications.value
      zone_redundancy_enabled = true
      tags                    = local.default_tags
    }
  }

  # Network rule set — default Deny, allow only from AppSubnet (where the
  # main Container Apps Environment pulls). Prod may add IdpSubnet if
  # Keycloak image is mirrored to ACR.
  network_rule_set {
    default_action = "Deny"

    virtual_network {
      action    = "Allow"
      subnet_id = azurerm_subnet.apps.id
    }

    # IdpSubnet allow — for Keycloak Container App if image is mirrored.
    virtual_network {
      action    = "Allow"
      subnet_id = azurerm_subnet.idp.id
    }
  }

  tags = merge(local.default_tags, {
    Name = "${local.name_prefix}-acr"
  })
}

# ── AcrPull role assignments for each Container App managed identity ─────────
# Each identity needs `AcrPull` on the registry to pull images without
# admin credentials. Frontend doesn't strictly need this if its image is
# public, but we grant it for parity (cheap + enables future ACR mirroring).

resource "azurerm_role_assignment" "backend_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.backend.principal_id
}

resource "azurerm_role_assignment" "frontend_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.frontend.principal_id
}

resource "azurerm_role_assignment" "worker_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.worker.principal_id
}

# Keycloak pulls from public quay.io by default — no AcrPull needed.
# Grant one anyway so a prod mirrored Keycloak image works without re-apply.
resource "azurerm_role_assignment" "keycloak_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.keycloak.principal_id
}
