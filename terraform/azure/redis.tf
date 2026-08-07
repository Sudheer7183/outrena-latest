# redis.tf — Azure Cache for Redis (Standard C1 default, Premium P1 in prod).
#
# Per migration doc §12.3 — Standard C1, TLS enabled. We use a Private
# Endpoint (works for both Standard + Premium) to keep data plane traffic
# inside the VNet. Premium tier additionally supports VNet injection (subnet
# deployment) — see commented block below for that alternative.
#
# Redis 7 note: as of azurerm 3.110, Redis 7 is generally available only on
# the Premium + Enterprise tiers. We pin to 6 for cross-tier compatibility —
# bump to 7 only after switching prod to Premium and validating.

# ── Private DNS Zone for Redis ───────────────────────────────────────────────
resource "azurerm_private_dns_zone" "redis" {
  name                = "privatelink.redis.cache.windows.net"
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "redis" {
  name                  = "${local.name_prefix}-redis-dns-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.redis.name
  virtual_network_id    = azurerm_virtual_network.main.id
  tags                  = local.default_tags
}

# ── Azure Cache for Redis ────────────────────────────────────────────────────
# NOTE: Standard / Basic tier does NOT support `subnet_id` (VNet injection) —
# that requires Premium. For cross-tier portability we use a Private Endpoint
# on DataSubnet for both Standard and Premium. If you require VNet injection
# (Premium-only), uncomment the `subnet_id` + `private_static_ip_address`
# lines and remove the `azurerm_private_endpoint.redis` block below.
resource "azurerm_redis_cache" "main" {
  name                          = "${local.name_prefix}-redis"
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  sku_name                      = var.redis_sku
  family                        = var.redis_family
  capacity                      = var.redis_capacity
  minimum_tls_version           = "1.2"
  redis_version                 = var.redis_version
  public_network_access_enabled = false
  non_ssl_port_enabled          = false

  redis_configuration {
    maxmemory_policy = "allkeys-lru"
  }

  tags = merge(local.default_tags, {
    Name = "${local.name_prefix}-redis"
  })

  depends_on = [azurerm_subnet_network_security_group_association.data]
}

# ── Private Endpoint (Standard + Premium) ────────────────────────────────────
# Plumbs the Redis data plane into DataSubnet. The Private DNS zone group
# auto-registers the PE's private IP into privatelink.redis.cache.windows.net,
# so the public FQDN resolves to the private IP from inside the VNet.
resource "azurerm_private_endpoint" "redis" {
  name                = "${local.name_prefix}-redis-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.data.id
  tags                = local.default_tags

  private_service_connection {
    name                           = "${local.name_prefix}-redis-psc"
    private_connection_resource_id = azurerm_redis_cache.main.id
    subresource_names              = ["redisCache"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.redis.id]
  }
}

# ── Redis connection string stored in Key Vault ──────────────────────────────
# TLS-port (6380) + access key. Container Apps reference this secret via
# `secret.key_vault_secret_id = azurerm_key_vault_secret.redis_url.id`.
# NOTE: azurerm_key_vault_secret.redis_url lives in key_vault.tf (it sits
# alongside the other composite connection strings for ordering clarity).
