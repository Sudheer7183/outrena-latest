# nsg.tf — 4 NSGs per migration doc §12.2 NSG table.
#
# NSGs are attached to subnets (not NICs) and define Layer-4 allow rules
# between Azure resources. Default Azure behaviour is allow-all within a VNet,
# so each NSG below is paired with explicit Deny rules to enforce the §12.2
# least-privilege matrix.
#
# ── NSG table (§12.2) ────────────────────────────────────────────────────────
# | NSG        | Inbound                              | Outbound                              |
# |------------|--------------------------------------|---------------------------------------|
# | nsg-appgw  | Internet :443                        | nsg-apps :80/:8000/:8080              |
# | nsg-apps   | nsg-appgw :80/:8000/:8080            | nsg-data :5432/:6379, Internet :443   |
# | nsg-data   | nsg-apps :5432/:6379 (via PE)        | (none)                                |
# | nsg-idp    | nsg-appgw :8080, nsg-apps :8080      | nsg-data :5432                        |
# ────────────────────────────────────────────────────────────────────────────

locals {
  # CIDR aliases for use in NSG rules — kept DRY via locals.
  appgw_cidr = var.subnets.app_gateway
  apps_cidr  = var.subnets.apps
  data_cidr  = var.subnets.data
  idp_cidr   = var.subnets.idp
}

# ── nsg-appgw (Application Gateway subnet) ───────────────────────────────────
resource "azurerm_network_security_group" "appgw" {
  name                = "${local.name_prefix}-nsg-appgw"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# Inbound: Internet :443 (TLS to WAF)
resource "azurerm_network_security_rule" "appgw_in_internet_443" {
  name                        = "Allow-Internet-Inbound-443"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "Internet"
  destination_address_prefix  = local.appgw_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.appgw.name
}

# Outbound: nsg-apps :80 (frontend)
resource "azurerm_network_security_rule" "appgw_out_apps_80" {
  name                        = "Allow-Apps-Outbound-80"
  priority                    = 100
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "80"
  source_address_prefix       = local.appgw_cidr
  destination_address_prefix  = local.apps_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.appgw.name
}

# Outbound: nsg-apps :8000 (backend FastAPI)
resource "azurerm_network_security_rule" "appgw_out_apps_8000" {
  name                        = "Allow-Apps-Outbound-8000"
  priority                    = 110
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8000"
  source_address_prefix       = local.appgw_cidr
  destination_address_prefix  = local.apps_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.appgw.name
}

# Outbound: nsg-apps :8080 (Keycloak — also reaches IdpSubnet)
resource "azurerm_network_security_rule" "appgw_out_idp_8080" {
  name                        = "Allow-Idp-Outbound-8080"
  priority                    = 120
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8080"
  source_address_prefix       = local.appgw_cidr
  destination_address_prefix  = local.idp_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.appgw.name
}

# ── nsg-apps (Container Apps Environment — main) ─────────────────────────────
resource "azurerm_network_security_group" "apps" {
  name                = "${local.name_prefix}-nsg-apps"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# Inbound: nsg-appgw :80 (frontend)
resource "azurerm_network_security_rule" "apps_in_appgw_80" {
  name                        = "Allow-AppGw-Inbound-80"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "80"
  source_address_prefix       = local.appgw_cidr
  destination_address_prefix  = local.apps_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.apps.name
}

# Inbound: nsg-appgw :8000 (backend)
resource "azurerm_network_security_rule" "apps_in_appgw_8000" {
  name                        = "Allow-AppGw-Inbound-8000"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8000"
  source_address_prefix       = local.appgw_cidr
  destination_address_prefix  = local.apps_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.apps.name
}

# Outbound: nsg-data :5432 (PostgreSQL via Private Endpoint)
resource "azurerm_network_security_rule" "apps_out_data_5432" {
  name                        = "Allow-Data-Outbound-5432"
  priority                    = 100
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "5432"
  source_address_prefix       = local.apps_cidr
  destination_address_prefix  = local.data_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.apps.name
}

# Outbound: nsg-data :6379 (Redis via Private Endpoint)
resource "azurerm_network_security_rule" "apps_out_data_6379" {
  name                        = "Allow-Data-Outbound-6379"
  priority                    = 110
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "6379"
  source_address_prefix       = local.apps_cidr
  destination_address_prefix  = local.data_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.apps.name
}

# Outbound: Internet :443 (LLM gateway, MailBridge, ACR, package mirror)
resource "azurerm_network_security_rule" "apps_out_internet_443" {
  name                        = "Allow-Internet-Outbound-443"
  priority                    = 120
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = local.apps_cidr
  destination_address_prefix  = "Internet"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.apps.name
}

# ── nsg-data (Data subnet — PostgreSQL + Redis PE + Blob PE) ─────────────────
resource "azurerm_network_security_group" "data" {
  name                = "${local.name_prefix}-nsg-data"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# Inbound: nsg-apps :5432 (PostgreSQL via Private Endpoint)
resource "azurerm_network_security_rule" "data_in_apps_5432" {
  name                        = "Allow-Apps-Inbound-5432"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "5432"
  source_address_prefix       = local.apps_cidr
  destination_address_prefix  = local.data_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.data.name
}

# Inbound: nsg-apps :6379 (Redis via Private Endpoint)
resource "azurerm_network_security_rule" "data_in_apps_6379" {
  name                        = "Allow-Apps-Inbound-6379"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "6379"
  source_address_prefix       = local.apps_cidr
  destination_address_prefix  = local.data_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.data.name
}

# Inbound: nsg-idp :5432 (Keycloak → PostgreSQL for KC database)
resource "azurerm_network_security_rule" "data_in_idp_5432" {
  name                        = "Allow-Idp-Inbound-5432"
  priority                    = 120
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "5432"
  source_address_prefix       = local.idp_cidr
  destination_address_prefix  = local.data_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.data.name
}

# Note: §12.2 says "no outbound" for nsg-data. Azure default outbound is
# Allow-All — we explicitly Deny Internet egress below. AzureServices bypass
# is still needed for storage account / postgres control plane operations.
resource "azurerm_network_security_rule" "data_out_deny_internet" {
  name                        = "Deny-Internet-Outbound"
  priority                    = 4096
  direction                   = "Outbound"
  access                      = "Deny"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = local.data_cidr
  destination_address_prefix  = "Internet"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.data.name
}

# ── nsg-idp (Identity subnet — Keycloak Container App) ───────────────────────
resource "azurerm_network_security_group" "idp" {
  name                = "${local.name_prefix}-nsg-idp"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.default_tags
}

# Inbound: nsg-appgw :8080 (App Gateway → Keycloak)
resource "azurerm_network_security_rule" "idp_in_appgw_8080" {
  name                        = "Allow-AppGw-Inbound-8080"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8080"
  source_address_prefix       = local.appgw_cidr
  destination_address_prefix  = local.idp_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.idp.name
}

# Inbound: nsg-apps :8080 (Backend → Keycloak Admin API for realm provisioning)
resource "azurerm_network_security_rule" "idp_in_apps_8080" {
  name                        = "Allow-Apps-Inbound-8080"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8080"
  source_address_prefix       = local.apps_cidr
  destination_address_prefix  = local.idp_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.idp.name
}

# Outbound: nsg-data :5432 (Keycloak → PostgreSQL for KC database)
resource "azurerm_network_security_rule" "idp_out_data_5432" {
  name                        = "Allow-Data-Outbound-5432"
  priority                    = 100
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "5432"
  source_address_prefix       = local.idp_cidr
  destination_address_prefix  = local.data_cidr
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.idp.name
}

# ── Subnet → NSG associations ────────────────────────────────────────────────
resource "azurerm_subnet_network_security_group_association" "appgw" {
  subnet_id                 = azurerm_subnet.appgw.id
  network_security_group_id = azurerm_network_security_group.appgw.id
}

resource "azurerm_subnet_network_security_group_association" "apps" {
  subnet_id                 = azurerm_subnet.apps.id
  network_security_group_id = azurerm_network_security_group.apps.id
}

resource "azurerm_subnet_network_security_group_association" "data" {
  subnet_id                 = azurerm_subnet.data.id
  network_security_group_id = azurerm_network_security_group.data.id
}

resource "azurerm_subnet_network_security_group_association" "idp" {
  subnet_id                 = azurerm_subnet.idp.id
  network_security_group_id = azurerm_network_security_group.idp.id
}
