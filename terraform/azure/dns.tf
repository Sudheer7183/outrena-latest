# dns.tf — Azure DNS zone + Traffic Manager for blue/green cutover.
#
# Per migration doc §12.3 + §16.3 (Weighted DNS cutover):
#   - Apex + www + api + auth A-records → App Gateway public IP
#   - Traffic Manager profile with Weighted routing, monitor HTTP /health :443
#   - Two endpoints:
#       new → App Gateway FQDN (FastAPI stack), weight = var.blue_green_weight_new
#       old → legacy Next.js stack (external endpoint), weight = var.blue_green_weight_old
#   - Old endpoint is `enabled = var.blue_green_weight_old > 0` so it cleanly
#     removes from rotation when weight is 0 (instead of relying on the
#     traffic-manager weight=0 quirk).

# ── Azure DNS zone for base_domain ───────────────────────────────────────────
resource "azurerm_dns_zone" "main" {
  name                = var.base_domain
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# ── A records: apex + www + api + auth → App Gateway public IP ───────────────
resource "azurerm_dns_a_record" "apex" {
  name                = "@"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 60
  records             = [azurerm_public_ip.appgw.ip_address]
  tags                = local.default_tags
}

resource "azurerm_dns_a_record" "www" {
  name                = "www"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 60
  records             = [azurerm_public_ip.appgw.ip_address]
  tags                = local.default_tags
}

resource "azurerm_dns_a_record" "api" {
  name                = "api"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 60
  records             = [azurerm_public_ip.appgw.ip_address]
  tags                = local.default_tags
}

resource "azurerm_dns_a_record" "auth" {
  name                = "auth"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 60
  records             = [azurerm_public_ip.appgw.ip_address]
  tags                = local.default_tags
}

# ── Traffic Manager profile (Weighted routing for blue/green) ────────────────
resource "azurerm_traffic_manager_profile" "main" {
  name                   = "${local.name_prefix}-tm"
  resource_group_name    = azurerm_resource_group.main.name
  traffic_routing_method = "Weighted"
  traffic_view_enabled   = false

  dns_config {
    relative_name = local.name_prefix
    ttl           = 60
  }

  monitor_config {
    protocol                     = "HTTPS"
    port                         = 443
    path                         = "/health"
    interval_in_seconds          = 30
    timeout_in_seconds           = 10
    tolerated_number_of_failures = 3
  }

  tags = local.default_tags
}

# ── NEW endpoint: App Gateway FQDN (FastAPI stack) ───────────────────────────
# Uses azurerm_traffic_manager_azure_endpoint because the App Gateway is an
# Azure resource — target_resource_id points at the public IP fronting it.
resource "azurerm_traffic_manager_azure_endpoint" "new" {
  name               = "new-fastapi"
  profile_id         = azurerm_traffic_manager_profile.main.id
  target_resource_id = azurerm_public_ip.appgw.id
  weight             = var.blue_green_weight_new
  enabled            = var.blue_green_weight_new > 0
}

# ── OLD endpoint: legacy Next.js stack ───────────────────────────────────────
# External endpoint (FQDN-based) since the legacy stack may live outside Azure.
# IMPORTANT: var.legacy_endpoint_target MUST point to the old Next.js stack
# (e.g., `old-nextjs.azurewebsites.net` or the legacy CloudFront / S3 URL).
# Disabled cleanly when blue_green_weight_old = 0 (initial cutover start state).
resource "azurerm_traffic_manager_external_endpoint" "old" {
  name              = "old-nextjs"
  profile_id        = azurerm_traffic_manager_profile.main.id
  target            = var.legacy_endpoint_target
  endpoint_location = azurerm_resource_group.main.location
  weight            = var.blue_green_weight_old
  enabled           = var.blue_green_weight_old > 0
}
