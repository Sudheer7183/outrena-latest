# managed_identities.tf — User-assigned managed identities for each Container
# App + App Gateway, plus Key Vault RBAC role assignments.
#
# Per migration doc §12.3 — "Key Vault ... accessed via managed identities."
# Each Container App gets its own user-assigned identity with AcrPull on the
# registry + Key Vault Secrets User on the Key Vault (least privilege —
# identities only see the secrets they need, never the connection string
# plaintext in terraform state).

# ── Backend managed identity ─────────────────────────────────────────────────
resource "azurerm_user_assigned_identity" "backend" {
  name                = "${local.name_prefix}-backend-id"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# ── Frontend managed identity ────────────────────────────────────────────────
resource "azurerm_user_assigned_identity" "frontend" {
  name                = "${local.name_prefix}-frontend-id"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# ── Worker (Celery) managed identity ─────────────────────────────────────────
resource "azurerm_user_assigned_identity" "worker" {
  name                = "${local.name_prefix}-worker-id"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# ── Keycloak managed identity ────────────────────────────────────────────────
resource "azurerm_user_assigned_identity" "keycloak" {
  name                = "${local.name_prefix}-keycloak-id"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# ── App Gateway managed identity (for Key Vault SSL cert retrieval) ──────────
resource "azurerm_user_assigned_identity" "appgw" {
  name                = "${local.name_prefix}-appgw-id"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# ── Key Vault Secrets User role assignments ──────────────────────────────────
# RBAC mode on Key Vault means each identity must be granted explicit read
# access. `Key Vault Secrets User` is the least-privilege role for read-only
# secret access (used by Container Apps `secret.key_vault_secret_id` refs and
# App Gateway `ssl_certificate.key_vault_secret_id`).
locals {
  # Apps that need DB / Redis / Blob secrets
  secret_readers = {
    backend  = azurerm_user_assigned_identity.backend.principal_id
    worker   = azurerm_user_assigned_identity.worker.principal_id
    keycloak = azurerm_user_assigned_identity.keycloak.principal_id
  }
}

resource "azurerm_role_assignment" "kv_secrets_user" {
  for_each = local.secret_readers

  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = each.value
}

# App Gateway needs the TLS cert secret specifically.
resource "azurerm_role_assignment" "appgw_kv_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.appgw.principal_id
}

# Frontend doesn't need Key Vault access in the default deployment (no secrets
# pulled at runtime — it's a static SPA served by nginx). Role assignment
# omitted intentionally; add one here if frontend ever needs runtime secrets.

# AcrPull role assignments live in acr.tf (alongside the registry resource).
