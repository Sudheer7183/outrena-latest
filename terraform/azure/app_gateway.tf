# app_gateway.tf — Application Gateway v2 (WAF) — the public TLS terminator.
#
# Per migration doc §12.1 — WAF v2, TLS :443. Path-based routing:
#   /api/*  → backend   (FastAPI, port 8000)
#   /auth/* → keycloak  (port 8080, internal-only CAE)
#   /*      → frontend  (Vite SPA, port 80)
#
# The TLS cert is pulled from Key Vault via the App Gateway's user-assigned
# managed identity (granted Key Vault Secrets User in managed_identities.tf).
# WAF policy uses OWASP 3.2 ruleset + a custom rate-limit rule.

# ── Public IP for App Gateway ────────────────────────────────────────────────
resource "azurerm_public_ip" "appgw" {
  name                = "${local.name_prefix}-appgw-pip"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "${local.name_prefix}-appgw"
  tags                = local.default_tags
}

# ── WAF policy (OWASP 3.2 + custom rate-limit) ───────────────────────────────
resource "azurerm_web_application_firewall_policy" "main" {
  name                = "${local.name_prefix}-waf-policy"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.default_tags

  policy_settings {
    enabled                     = true
    mode                        = "Prevention"
    request_body_check          = true
    file_upload_limit_in_mb     = 100
    max_request_body_size_in_kb = 128
  }

  managed_rules {
    managed_rule_set {
      type    = "OWASP"
      version = "3.2"
    }

    # Disable rule 942440 (SQL comment detection) — false-positives on
    # legitimate JSON with `--` in URLs. Tune per environment as needed.
    exclusion {
      match_variable          = "RequestArgNames"
      selector_match_operator = "Equals"
      selector                = "comment"
    }
  }

  # Custom rule 1: rate-limit per client IP — 100 req / 60s on /api/*.
  # Protects backend against brute-force / scraping per migration doc §12.3.
  custom_rules {
    name                 = "RateLimitApiPerIp"
    priority             = 1
    rule_type            = "RateLimitRule"
    rate_limit_threshold = 100
    rate_limit_duration  = "OneMin"

    action = "Block"

    match_conditions {
      match_variables {
        variable_name = "RemoteAddr"
      }
      operator           = "IPMatch"
      negation_condition = false
      match_values       = ["0.0.0.0/0"]
    }

    match_conditions {
      match_variables {
        variable_name = "RequestUri"
      }
      operator           = "BeginsWith"
      negation_condition = false
      match_values       = ["/api/"]
    }
  }

  # Custom rule 2: block known-bad user agents (empty UA, sqlmap, nikto).
  custom_rules {
    name      = "BlockBadUserAgents"
    priority  = 2
    rule_type = "MatchRule"

    action = "Block"

    match_conditions {
      match_variables {
        variable_name = "RequestHeaders"
        selector      = "User-Agent"
      }
      operator           = "Equal"
      negation_condition = false
      match_values       = ["", "sqlmap/1.0", "nikto"]
    }
  }
}

# ── Application Gateway v2 ───────────────────────────────────────────────────
resource "azurerm_application_gateway" "main" {
  name                = "${local.name_prefix}-appgw"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.default_tags

  # WAF v2 SKU + autoscale 2-10 instances (per §12.1 + var defaults).
  sku {
    name     = var.appgw_sku
    tier     = var.appgw_sku
    capacity = 2 # ignored when autoscale_configuration is set
  }

  autoscale_configuration {
    min_capacity = var.appgw_min_capacity
    max_capacity = var.appgw_max_capacity
  }

  # User-assigned identity for Key Vault cert retrieval (granted KV Secrets
  # User in managed_identities.tf).
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.appgw.id]
  }

  # WAF policy association
  firewall_policy_id = azurerm_web_application_firewall_policy.main.id

  # ── Gateway IP config — bind to AppGatewaySubnet ──
  gateway_ip_configuration {
    name      = "appGatewayIpConfig"
    subnet_id = azurerm_subnet.appgw.id
  }

  # ── Frontend IP config (public) ──
  frontend_ip_configuration {
    name                 = "frontendPublicIp"
    public_ip_address_id = azurerm_public_ip.appgw.id
  }

  # ── Frontend ports :80 (redirect) + :443 (TLS) ──
  frontend_port {
    name = "http"
    port = 80
  }

  frontend_port {
    name = "https"
    port = 443
  }

  # ── TLS cert from Key Vault ──
  # Uses the resource-level user-assigned identity (above) for KV auth.
  # `versionless_secret_id` so App Gateway auto-rotates on cert renewal.
  ssl_certificate {
    name                = "wildcard-tls"
    key_vault_secret_id = azurerm_key_vault_certificate.tls.versionless_secret_id
  }

  # ── Backend pools ──
  backend_address_pool {
    name = "backend-pool"
    fqdns = [
      azurerm_container_app.backend.latest_revision_fqdn
    ]
  }

  backend_address_pool {
    name = "frontend-pool"
    fqdns = [
      azurerm_container_app.frontend.latest_revision_fqdn
    ]
  }

  backend_address_pool {
    name = "keycloak-pool"
    fqdns = [
      azurerm_container_app.keycloak.latest_revision_fqdn
    ]
  }

  # ── Backend HTTP settings ──
  backend_http_settings {
    name                                = "backend-http-8000"
    cookie_based_affinity               = "Disabled"
    port                                = 8000
    protocol                            = "Http"
    request_timeout                     = 60
    pick_host_name_from_backend_address = true
    probe_name                          = "backend-probe"
  }

  backend_http_settings {
    name                                = "frontend-http-80"
    cookie_based_affinity               = "Disabled"
    port                                = 80
    protocol                            = "Http"
    request_timeout                     = 30
    pick_host_name_from_backend_address = true
    probe_name                          = "frontend-probe"
  }

  backend_http_settings {
    name                                = "keycloak-http-8080"
    cookie_based_affinity               = "Enabled"
    affinity_cookie_name                = "KC_AFFINITY"
    port                                = 8080
    protocol                            = "Http"
    request_timeout                     = 60
    pick_host_name_from_backend_address = true
    probe_name                          = "keycloak-probe"
  }

  # ── Health probes ──
  probe {
    name                = "backend-probe"
    protocol            = "Http"
    path                = "/api/v1/health"
    host                = "127.0.0.1"
    interval            = 30
    timeout             = 10
    unhealthy_threshold = 3
    match {
      status_code = ["200-299"]
    }
  }

  probe {
    name                = "frontend-probe"
    protocol            = "Http"
    path                = "/"
    host                = "127.0.0.1"
    interval            = 30
    timeout             = 10
    unhealthy_threshold = 3
    match {
      status_code = ["200-299"]
    }
  }

  probe {
    name                = "keycloak-probe"
    protocol            = "Http"
    path                = "/auth/realms/master"
    host                = "127.0.0.1"
    interval            = 30
    timeout             = 10
    unhealthy_threshold = 3
    match {
      status_code = ["200-299", "302"]
    }
  }

  # ── Listeners ──
  # HTTP listener — redirect to HTTPS
  http_listener {
    name                           = "http-listener"
    frontend_ip_configuration_name = "frontendPublicIp"
    frontend_port_name             = "http"
    protocol                       = "Http"
  }

  # HTTPS listener — TLS cert
  http_listener {
    name                           = "https-listener"
    frontend_ip_configuration_name = "frontendPublicIp"
    frontend_port_name             = "https"
    protocol                       = "Https"
    ssl_certificate_name           = "wildcard-tls"
    host_name                      = var.base_domain
  }

  # ── Redirect: HTTP → HTTPS ──
  redirect_configuration {
    name                 = "http-to-https"
    redirect_type        = "Permanent"
    target_listener_name = "https-listener"
    include_path         = true
    include_query_string = true
  }

  # ── Path-based routing (main rule: /api/* → backend, /auth/* → keycloak, /* → frontend) ──
  # Root path rule with url_path_map for path-based dispatch. Defaults for
  # unmatched paths come from the url_path_map block below (frontend pool).
  request_routing_rule {
    name               = "https-path-routing"
    rule_type          = "PathBasedRouting"
    http_listener_name = "https-listener"
    url_path_map_name  = "outrena-pathmap"
    priority           = 100
  }

  # ── HTTP listener rule: redirect everything to HTTPS ──
  request_routing_rule {
    name                        = "http-redirect"
    rule_type                   = "Basic"
    http_listener_name          = "http-listener"
    redirect_configuration_name = "http-to-https"
    priority                    = 50
  }

  # ── URL path map ──
  url_path_map {
    name                               = "outrena-pathmap"
    default_backend_address_pool_name  = "frontend-pool"
    default_backend_http_settings_name = "frontend-http-80"

    path_rule {
      name                       = "api-rule"
      paths                      = ["/api/*"]
      backend_address_pool_name  = "backend-pool"
      backend_http_settings_name = "backend-http-8000"
    }

    path_rule {
      name                       = "auth-rule"
      paths                      = ["/auth/*"]
      backend_address_pool_name  = "keycloak-pool"
      backend_http_settings_name = "keycloak-http-8080"
    }
  }

  depends_on = [
    azurerm_subnet_network_security_group_association.appgw,
    azurerm_role_assignment.appgw_kv_secrets_user,
  ]
}
