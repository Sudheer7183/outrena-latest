# network.tf — VNet + 4 subnets per migration doc §12.1.
#
# Layout:
#   AppGatewaySubnet — Application Gateway v2 (WAF) nodes. No delegation.
#   AppSubnet         — Delegated to Microsoft.App/environments. Holds the
#                       main Container Apps Environment (backend, frontend, worker).
#                       Min /23 (per Azure docs for Container Apps Environment).
#   DataSubnet        — PostgreSQL Flexible Server (delegated subnet) + Redis
#                       Private Endpoint + Blob Private Endpoints. No internet egress.
#   IdpSubnet         — Delegated to Microsoft.App/environments. Holds the
#                       idp Container Apps Environment (Keycloak only) — isolated
#                       blast radius per §12.1 diagram.

# ── VNet ─────────────────────────────────────────────────────────────────────
resource "azurerm_virtual_network" "main" {
  name                = "${local.name_prefix}-vnet"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = [var.vnet_cidr]
  # Azure DNS resolver — required for Private Endpoint + Private DNS Zone resolution.
  dns_servers = ["168.63.129.16"]

  tags = merge(local.default_tags, {
    Name = "${local.name_prefix}-vnet"
  })
}

# ── AppGatewaySubnet (Application Gateway nodes) ─────────────────────────────
# Application Gateway v2 requires a dedicated subnet (cannot share with
# anything except other App Gateways). No service delegation needed.
resource "azurerm_subnet" "appgw" {
  name                 = "AppGatewaySubnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.subnets.app_gateway]
}

# ── AppSubnet (Container Apps Environment — main) ────────────────────────────
# Delegated to Microsoft.App/environments. Container Apps Environment
# consumes the entire subnet — no other resources can live here.
resource "azurerm_subnet" "apps" {
  name                 = "AppSubnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.subnets.apps]

  delegation {
    name = "Microsoft.App-environments"
    service_delegation {
      name = "Microsoft.App/environments"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

# ── DataSubnet (PostgreSQL + Redis PE + Blob PE) ─────────────────────────────
# PostgreSQL Flexible Server requires its own delegated subnet. Redis Cache
# uses a Private Endpoint (Standard tier) or VNet injection (Premium tier) —
# we use Private Endpoint for cross-tier compatibility.
resource "azurerm_subnet" "data" {
  name                 = "DataSubnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.subnets.data]

  # Delegated subnet for PostgreSQL Flexible Server.
  # Private Endpoints for Redis + Blob also live here (no delegation needed for those).
  delegation {
    name = "Microsoft.DBforPostgreSQL-flexibleServers"
    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

# ── IdpSubnet (Container Apps Environment — Keycloak) ────────────────────────
# Separate subnet + separate Container Apps Environment for Keycloak blast-radius
# isolation per §12.1 diagram (Identity subnet).
resource "azurerm_subnet" "idp" {
  name                 = "IdpSubnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.subnets.idp]

  delegation {
    name = "Microsoft.App-environments"
    service_delegation {
      name = "Microsoft.App/environments"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}
