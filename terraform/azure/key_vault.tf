# key_vault.tf — Key Vault, secrets, and the TLS cert placeholder.
#
# Per migration doc §12.3 — "Key Vault stores TLS cert, DB password, Keycloak
# admin password, MailBridge URL — accessed via managed identities."
#
# RBAC mode is enabled (no access policies). The deploying principal needs
# `Key Vault Secrets Officer` to write secrets during `terraform apply`. Each
# Container App / App Gateway identity needs `Key Vault Secrets User` (granted
# in managed_identities.tf).

# ── Random passwords (generated once, stored as Key Vault secrets) ───────────
resource "random_password" "db_admin_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
  min_lower        = 1
  min_upper        = 1
  min_numeric      = 1
  min_special      = 1
}

resource "random_password" "keycloak_admin_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
  min_lower        = 1
  min_upper        = 1
  min_numeric      = 1
  min_special      = 1
}

# Allows the value to be supplied via tfvars in non-dev environments if a
# pre-existing password must be reused.
locals {
  effective_keycloak_admin_password = coalesce(
    var.keycloak_admin_password,
    random_password.keycloak_admin_password.result,
  )
}

# ── Key Vault ────────────────────────────────────────────────────────────────
resource "azurerm_key_vault" "main" {
  name                       = var.key_vault_name
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = true
  enable_rbac_authorization  = true

  # Public access remains on for first-time bootstrap (terraform apply runs
  # from a build agent that needs to write secrets). Tighten via network_acls
  # below so only trusted subnets can hit the data plane.
  public_network_access_enabled = true

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    # Allow data-plane calls from the Container Apps subnets (backend, worker,
    # keycloak all fetch secrets at runtime) and the data subnet (storage
    # account / postgres control plane).
    virtual_network_subnet_ids = [
      azurerm_subnet.apps.id,
      azurerm_subnet.idp.id,
      azurerm_subnet.data.id,
    ]
    ip_rules = []
  }

  tags = local.default_tags
}

# ── Deploying principal: Key Vault Secrets Officer (write secrets via terraform) ─
# Required only during apply; safe to leave in place.
resource "azurerm_role_assignment" "deploying_principal_secrets_officer" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# ── Stored secrets ───────────────────────────────────────────────────────────
# Each `azurerm_key_vault_secret` has a stable `id` (versionless) that
# Container Apps reference via `secret.key_vault_secret_id`.

resource "azurerm_key_vault_secret" "db_admin_password" {
  name         = "db-admin-password"
  value        = random_password.db_admin_password.result
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.default_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}

resource "azurerm_key_vault_secret" "keycloak_admin_password" {
  name         = "keycloak-admin-password"
  value        = local.effective_keycloak_admin_password
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.default_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}

resource "azurerm_key_vault_secret" "mailbridge_url" {
  name         = "mailbridge-url"
  value        = coalesce(var.mailbridge_url, "https://mailbridge.example.local/inbound")
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.default_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}

# Composite connection strings — constructed AFTER the upstream resources
# exist (postgres, redis, blob), so they live further down in this file via
# `depends_on` + resource references. Stored as secrets so Container Apps can
# fetch via `key_vault_secret_id` without plaintext in their env block.

resource "azurerm_key_vault_secret" "database_url" {
  name = "database-url"
  # asyncpg driver — matches app/core/config.py DATABASE_URL format
  value = join("", [
    "postgresql+asyncpg://",
    var.postgres_admin_login, ":",
    random_password.db_admin_password.result, "@",
    azurerm_postgresql_flexible_server.main.fqdn, ":5432/",
    var.database_name,
  ])
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.default_tags

  depends_on = [
    azurerm_role_assignment.deploying_principal_secrets_officer,
    azurerm_postgresql_flexible_server.main,
  ]
}

resource "azurerm_key_vault_secret" "celery_broker_url" {
  name = "celery-broker-url"
  value = join("", [
    "rediss://:", azurerm_redis_cache.main.primary_access_key, "@",
    azurerm_redis_cache.main.hostname, ":6380/1",
  ])
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.default_tags

  depends_on = [
    azurerm_role_assignment.deploying_principal_secrets_officer,
    azurerm_redis_cache.main,
  ]
}

resource "azurerm_key_vault_secret" "redis_url" {
  name = "redis-url"
  value = join("", [
    "rediss://:", azurerm_redis_cache.main.primary_access_key, "@",
    azurerm_redis_cache.main.hostname, ":6380/0",
  ])
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.default_tags

  depends_on = [
    azurerm_role_assignment.deploying_principal_secrets_officer,
    azurerm_redis_cache.main,
  ]
}

# ── TLS wildcard certificate (placeholder in dev) ────────────────────────────
# Self-signed cert generated in-key-vault via the "Self" issuer. PROD MUST
# upload a real wildcard cert (DigiCert / Let's Encrypt / Key Vault Cert
# Issuer) — see comments below.
#
# In prod: replace this block with one of:
#   (a) `azurerm_key_vault_certificate` with `certificate_policy.issuer_parameters.name = "MyCA"`
#       and an integrated partner CA (DigiCert / GlobalSign).
#   (b) Manual upload via Azure Portal / az CLI after the vault exists, then
#       reference the resulting secret_id in app_gateway.tf.
#   (c) Bring-your-own PEM via `tls_private_key` + `tls_self_signed_cert`
#       providers (not done here to keep the providers list minimal).
resource "azurerm_key_vault_certificate" "tls" {
  name         = "wildcard-tls"
  key_vault_id = azurerm_key_vault.main.id

  certificate_policy {
    issuer_parameters {
      name = "Self"
    }

    key_properties {
      exportable = true
      key_size   = 2048
      key_type   = "RSA"
      reuse_key  = true
    }

    secret_properties {
      content_type = "application/x-pkcs12"
    }

    x509_certificate_properties {
      key_usage = [
        "cRLSign",
        "dataEncipherment",
        "digitalSignature",
        "keyAgreement",
        "keyCertSign",
        "keyEncipherment",
      ]

      subject_alternative_names {
        dns_names = ["*.${var.base_domain}", var.base_domain]
      }

      subject            = "CN=*.${var.base_domain}"
      validity_in_months = 12
    }
  }

  tags = local.default_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}
