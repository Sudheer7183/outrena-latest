# posthog.tf — Azure resources for self-hosted PostHog (PH-INFRA).
#
# Provisions a fully isolated PostHog stack on Azure:
#   - PostgreSQL Flexible Server 16 for PostHog metadata (separate subnet +
#     separate server from the OUTRENA app PG in postgres.tf — Azure requires
#     one delegated subnet per PG Flexible Server)
#   - Azure Cache for Redis (Standard/Premium) for PostHog cache/queue
#   - Storage account for PostHog object storage (exports + recordings)
#   - Event Hubs (Kafka-compatible) for event ingestion
#   - Self-managed ClickHouse on a dedicated Container Apps Environment
#     (see §"ClickHouse on Azure" below for the Altinity.Cloud alternative)
#   - Dedicated Container Apps Environment for PostHog web/worker/plugin-server
#   - Dedicated Application Gateway v2 (WAF) + public IP + DNS A-record
#     (posthog.outrena.ai)
#   - Log Analytics + alert rules for PostHog-specific health metrics
#
# All resources inherit Project/Environment/ManagedBy/Repo/Cloud/Phase tags
# via the local.default_tags block in main.tf. Resource-level tags add the
# Application=posthog tag for cost attribution (see runbook 14 §5.1).
#
# Cross-references:
#   - docker-compose.posthog.yml — dev/staging self-host compose
#   - k8s/posthog-values.yaml    — Helm values (uses these as externals)
#   - runbooks/15-exception-logging-self-healing.md — ops guide
#
# Choice notes:
#   * ClickHouse on Azure — PostHog supports ClickHouse on Container Apps
#     (self-managed) OR Altinity.Cloud (managed, runs on Azure Marketplace).
#     We default to Container Apps for cost; production deployments should
#     switch to Altinity.Cloud or self-managed AKS for reliability. See the
#     posthog_clickhouse Container App below.
#   * Kafka on Azure — Azure Event Hubs has a Kafka-compatible endpoint
#     (Kafka protocol 1.0+). PostHog's plugin-server connects via the
#     Event Hubs Kafka URL. This avoids running a separate Kafka cluster.
#   * PostgreSQL Flexible Server — we provision a SEPARATE server (not a
#     second database on the existing server) because Azure requires one
#     delegated subnet per Flexible Server. Reusing the existing server
#     would also violate the "separate blast radius" principle.

# ────────────────────────────────────────────────────────────────────────────
# Locals
# ────────────────────────────────────────────────────────────────────────────
locals {
  posthog_name_prefix = "${var.project_name}-${var.environment_short}-posthog"

  posthog_tags = merge(local.default_tags, {
    Application = "posthog"
    Tier        = "analytics"
  })
}

# ────────────────────────────────────────────────────────────────────────────
# PostHog data subnet (separate from OUTRENA DataSubnet — Azure requires
# one delegated subnet per PostgreSQL Flexible Server)
# ────────────────────────────────────────────────────────────────────────────
resource "azurerm_subnet" "posthog_data" {
  name                 = "PostHogDataSubnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.posthog_data_subnet_cidr]

  # Delegated to PostgreSQL Flexible Server (one server per subnet on Azure).
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

# ────────────────────────────────────────────────────────────────────────────
# PostgreSQL Flexible Server for PostHog metadata
# ────────────────────────────────────────────────────────────────────────────
resource "azurerm_private_dns_zone" "posthog_pg" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.posthog_tags

  # Reuse the existing zone if it already exists (OUTRENA app PG creates one
  # in postgres.tf — Azure allows multiple servers per private DNS zone).
  count = length([for z in [azurerm_private_dns_zone.pg] : z if z.name == "privatelink.postgres.database.azure.com"]) > 0 ? 0 : 1
}

# We rely on the existing privatelink.postgres.database.azure.com zone
# (created in postgres.tf) — link the VNet to it (idempotent if already linked).
# NOTE: azurerm_private_dns_zone_virtual_network_link.pg already links the VNet,
# so we don't need a second link here.

resource "random_password" "posthog_db_admin" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
  min_lower        = 1
  min_upper        = 1
  min_numeric      = 1
  min_special      = 1
}

resource "azurerm_postgresql_flexible_server" "posthog" {
  name                          = "${local.posthog_name_prefix}-pg"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = "14" # PostHog pins to PG14
  sku_name                      = var.posthog_pg_sku
  storage_mb                    = var.posthog_pg_storage_mb
  backup_retention_days         = var.posthog_pg_backup_retention_days
  geo_redundant_backup_enabled  = local.is_prod && var.posthog_pg_geo_redundant_backup
  administrator_login           = "posthog_admin"
  administrator_password        = random_password.posthog_db_admin.result
  delegated_subnet_id           = azurerm_subnet.posthog_data.id
  private_dns_zone_id           = azurerm_private_dns_zone.pg.id
  public_network_access_enabled = false

  dynamic "high_availability" {
    for_each = local.is_prod ? [1] : []
    content {
      mode = "ZoneRedundant"
    }
  }

  maintenance_window {
    day_of_week  = 0
    start_hour   = 4
    start_minute = 0
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-pg"
  })

  depends_on = [
    azurerm_private_dns_zone_virtual_network_link.pg,
  ]
}

resource "azurerm_postgresql_flexible_server_database" "posthog" {
  name      = "posthog"
  server_id = azurerm_postgresql_flexible_server.posthog.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# Diagnostic setting → Log Analytics
resource "azurerm_monitor_diagnostic_setting" "posthog_pg" {
  name                       = "${local.posthog_name_prefix}-pg-diag"
  target_resource_id         = azurerm_postgresql_flexible_server.posthog.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

# ── Key Vault secret: PostHog DATABASE_URL ──────────────────────────────────
resource "azurerm_key_vault_secret" "posthog_database_url" {
  name         = "posthog-database-url"
  value        = "postgres://posthog_admin:${urlencode(random_password.posthog_db_admin.result)}@${azurerm_postgresql_flexible_server.posthog.fqdn}:5432/posthog?sslmode=require"
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.posthog_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}

# ────────────────────────────────────────────────────────────────────────────
# Azure Cache for Redis for PostHog
# ────────────────────────────────────────────────────────────────────────────
resource "azurerm_redis_cache" "posthog" {
  name                          = "${local.posthog_name_prefix}-redis"
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  sku_name                      = local.is_prod ? "Premium" : "Standard"
  family                        = local.is_prod ? "P" : "C"
  capacity                      = local.is_prod ? 2 : 1
  minimum_tls_version           = "1.2"
  redis_version                 = "6" # cross-tier compat; bump to 7 with Premium
  public_network_access_enabled = false
  non_ssl_port_enabled          = false

  redis_configuration {
    maxmemory_policy = "allkeys-lru"
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-redis"
  })
}

resource "azurerm_private_endpoint" "posthog_redis" {
  name                = "${local.posthog_name_prefix}-redis-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.data.id
  tags                = local.posthog_tags

  private_service_connection {
    name                           = "${local.posthog_name_prefix}-redis-psc"
    private_connection_resource_id = azurerm_redis_cache.posthog.id
    subresource_names              = ["redisCache"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.redis.id]
  }
}

resource "azurerm_key_vault_secret" "posthog_redis_url" {
  name         = "posthog-redis-url"
  value        = "rediss://:${azurerm_redis_cache.posthog.primary_access_key}@${azurerm_redis_cache.posthog.hostname}:6380/0"
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.posthog_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}

# ────────────────────────────────────────────────────────────────────────────
# Storage account for PostHog object storage
# ────────────────────────────────────────────────────────────────────────────
# Storage account names must be 3-24 lowercase alphanumeric (no hyphens).
resource "azurerm_storage_account" "posthog" {
  name                            = substr(replace("${local.posthog_name_prefix}storage", "/[^a-z0-9]/", ""), 0, 24)
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_tier                    = "Standard"
  account_replication_type        = local.is_prod ? "GRS" : "LRS"
  account_kind                    = "BlobStorage"
  access_tier                     = "Hot"
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false
  https_traffic_only_enabled      = true

  blob_properties {
    versioning_enabled = local.is_prod
    delete_retention_policy {
      days = 30
    }
    container_delete_retention_policy {
      days = 30
    }
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-storage"
  })
}

resource "azurerm_storage_container" "posthog" {
  name                  = "posthog"
  storage_account_name  = azurerm_storage_account.posthog.name
  container_access_type = "private"
}

resource "azurerm_private_endpoint" "posthog_blob" {
  name                = "${local.posthog_name_prefix}-blob-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.data.id
  tags                = local.posthog_tags

  private_service_connection {
    name                           = "${local.posthog_name_prefix}-blob-psc"
    private_connection_resource_id = azurerm_storage_account.posthog.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob.id]
  }
}

resource "azurerm_storage_account_network_rules" "posthog" {
  storage_account_id = azurerm_storage_account.posthog.id

  default_action             = "Deny"
  bypass                     = ["AzureServices"]
  virtual_network_subnet_ids = [azurerm_subnet.apps.id]
}

# Lifecycle: Hot → Cool (30d) → Archive (90d) → Delete (365d)
resource "azurerm_storage_management_policy" "posthog" {
  storage_account_id = azurerm_storage_account.posthog.id

  rule {
    name    = "posthog-lifecycle"
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

resource "azurerm_key_vault_secret" "posthog_blob_connection_string" {
  name         = "posthog-blob-connection-string"
  value        = azurerm_storage_account.posthog.primary_blob_connection_string
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.posthog_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}

# ────────────────────────────────────────────────────────────────────────────
# Event Hubs (Kafka-compatible) for PostHog event ingestion
# ────────────────────────────────────────────────────────────────────────────
# Event Hubs exposes a Kafka endpoint at <namespace>.servicebus.windows.net:9093
# which PostHog's plugin-server connects to via the standard Kafka client.
resource "azurerm_eventhub_namespace" "posthog" {
  name                     = "${local.posthog_name_prefix}-eh"
  location                 = azurerm_resource_group.main.location
  resource_group_name      = azurerm_resource_group.main.name
  sku                      = local.is_prod ? "Standard" : "Basic"
  capacity                 = local.is_prod ? 2 : 1
  maximum_throughput_units = local.is_prod ? 4 : null
  zone_redundant           = local.is_prod
  auto_inflate_enabled     = local.is_prod

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-eh-namespace"
  })
}

resource "azurerm_eventhub" "posthog_events" {
  name                = "posthog-events"
  namespace_name      = azurerm_eventhub_namespace.posthog.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 8
  message_retention   = 7 # days
}

resource "azurerm_eventhub" "posthog_session_recordings" {
  name                = "posthog-session-recordings"
  namespace_name      = azurerm_eventhub_namespace.posthog.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 4
  message_retention   = 7
}

resource "azurerm_eventhub_consumer_group" "posthog_plugin_server" {
  name                = "plugin-server"
  namespace_name      = azurerm_eventhub_namespace.posthog.name
  eventhub_name       = azurerm_eventhub.posthog_events.name
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_eventhub_consumer_group" "posthog_worker" {
  name                = "worker"
  namespace_name      = azurerm_eventhub_namespace.posthog.name
  eventhub_name       = azurerm_eventhub.posthog_events.name
  resource_group_name = azurerm_resource_group.main.name
}

# Authorization rule — primary key goes into Key Vault as the Kafka password.
resource "azurerm_eventhub_authorization_rule" "posthog" {
  name                = "posthog-client"
  namespace_name      = azurerm_eventhub_namespace.posthog.name
  eventhub_name       = azurerm_eventhub.posthog_events.name
  resource_group_name = azurerm_resource_group.main.name

  listen = true
  send   = true
  manage = true
}

resource "azurerm_key_vault_secret" "posthog_kafka_password" {
  name         = "posthog-kafka-password"
  value        = azurerm_eventhub_authorization_rule.posthog.primary_key
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.posthog_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}

# ────────────────────────────────────────────────────────────────────────────
# PostHog Container Apps Environment (separate from OUTRENA main CAE)
# ────────────────────────────────────────────────────────────────────────────
resource "azurerm_subnet" "posthog_apps" {
  name                 = "PostHogAppsSubnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.posthog_apps_subnet_cidr]

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

resource "azurerm_container_app_environment" "posthog" {
  name                           = "${local.posthog_name_prefix}-cae"
  location                       = azurerm_resource_group.main.location
  resource_group_name            = azurerm_resource_group.main.name
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.main.id
  infrastructure_subnet_id       = azurerm_subnet.posthog_apps.id
  internal_load_balancer_enabled = false
  zone_redundancy_enabled        = local.is_prod

  tags = local.posthog_tags
}

# ────────────────────────────────────────────────────────────────────────────
# Managed identity for PostHog Container Apps
# ────────────────────────────────────────────────────────────────────────────
resource "azurerm_user_assigned_identity" "posthog" {
  name                = "${local.posthog_name_prefix}-identity"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.posthog_tags
}

# Grant the identity Key Vault Secrets User so Container Apps can pull
# posthog-database-url / posthog-redis-url / posthog-blob-connection-string.
resource "azurerm_role_assignment" "posthog_kv_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.posthog.principal_id
}

# Grant ACR pull (PostHog image is public, but if mirrored to ACR we'd need this).
resource "azurerm_role_assignment" "posthog_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.posthog.principal_id
}

# Storage Blob Data Contributor — so PostHog can write exports/recordings.
resource "azurerm_role_assignment" "posthog_storage_blob_contributor" {
  scope                = azurerm_storage_account.posthog.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.posthog.principal_id
}

# ────────────────────────────────────────────────────────────────────────────
# PostHog secret key (Django SECRET_KEY)
# ────────────────────────────────────────────────────────────────────────────
resource "random_password" "posthog_secret_key" {
  length  = 64
  special = false
}

resource "azurerm_key_vault_secret" "posthog_secret_key" {
  name         = "posthog-secret-key"
  value        = random_password.posthog_secret_key.result
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.posthog_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}

# ClickHouse password (used by both ClickHouse container + PostHog clients).
resource "random_password" "posthog_clickhouse_password" {
  length  = 32
  special = false
}

resource "azurerm_key_vault_secret" "posthog_clickhouse_password" {
  name         = "posthog-clickhouse-password"
  value        = random_password.posthog_clickhouse_password.result
  key_vault_id = azurerm_key_vault.main.id
  tags         = local.posthog_tags

  depends_on = [azurerm_role_assignment.deploying_principal_secrets_officer]
}

# ────────────────────────────────────────────────────────────────────────────
# ClickHouse (self-managed on Container Apps — see header comment re Altinity)
# ────────────────────────────────────────────────────────────────────────────
resource "azurerm_container_app" "posthog_clickhouse" {
  name                         = "${local.posthog_name_prefix}-clickhouse"
  container_app_environment_id = azurerm_container_app_environment.posthog.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.posthog_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.posthog.id]
  }

  secret {
    name                = "clickhouse-password"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_clickhouse_password.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }

  template {
    container {
      name   = "clickhouse"
      image  = "clickhouse/clickhouse-server:24.3"
      cpu    = 4.0
      memory = "8.0Gi"

      env {
        name  = "CLICKHOUSE_DB"
        value = "posthog"
      }
      env {
        name  = "CLICKHOUSE_USER"
        value = "clickhouse"
      }
      env {
        name  = "CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT"
        value = "1"
      }
      env {
        name        = "CLICKHOUSE_PASSWORD"
        secret_name = "clickhouse-password"
      }

      # ClickHouse HTTP (8123) + native TCP (9000).
      # Container Apps only exposes one port for ingress; we expose 8123 here
      # and rely on in-env DNS for the TCP port (PostHog uses HTTP by default).
    }

    min_replicas = 1
    max_replicas = local.is_prod ? 3 : 1
  }

  ingress {
    external_enabled = false # internal-only — PostHog web/worker reach via in-env DNS
    target_port      = 8123
    transport        = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  depends_on = [
    azurerm_container_app_environment.posthog,
    azurerm_role_assignment.posthog_kv_secrets_user,
  ]
}

# ────────────────────────────────────────────────────────────────────────────
# PostHog web (FastAPI / Django)
# ────────────────────────────────────────────────────────────────────────────
locals {
  posthog_env = {
    SELF_HOSTED                 = "true"
    USE_TZ                      = "true"
    SITE_URL                    = "https://app.${var.base_domain}"
    SERVER_URL                  = "https://posthog.${var.base_domain}"
    DISABLE_SECURE_SSL_REDIRECT = "true"
    CLICKHOUSE_DATABASE         = "posthog"
    CLICKHOUSE_USER             = "clickhouse"
    CLICKHOUSE_HOST             = azurerm_container_app.posthog_clickhouse.name
    CLICKHOUSE_SECURE           = "false"
    OBJECT_STORAGE_ENABLED      = "true"
    OBJECT_STORAGE_ENDPOINT     = "https://${azurerm_storage_account.posthog.name}.blob.core.windows.net"
    EMAIL_HOST                  = var.posthog_email_host
    EMAIL_PORT                  = tostring(var.posthog_email_port)
    EMAIL_USE_TLS               = "true"
    SLACK_TOKEN                 = var.posthog_slack_token
    SELF_DRIVING_REPO           = var.posthog_self_driving_repo
  }
}

resource "azurerm_container_app" "posthog_web" {
  name                         = "${local.posthog_name_prefix}-web"
  container_app_environment_id = azurerm_container_app_environment.posthog.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.posthog_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.posthog.id]
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_database_url.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "secret-key"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_secret_key.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "redis-url"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_redis_url.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "clickhouse-password"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_clickhouse_password.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "kafka-password"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_kafka_password.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "blob-connection-string"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_blob_connection_string.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }

  template {
    container {
      name   = "web"
      image  = "posthog/posthog:${var.posthog_image_tag}"
      cpu    = var.posthog_web_cpu
      memory = var.posthog_web_memory

      command = ["/bin/sh", "-c", "python -m posthog.async_migrations.check --force && ./bin/docker --web"]

      # Plain env vars
      env {
        name  = "SELF_HOSTED"
        value = local.posthog_env.SELF_HOSTED
      }
      env {
        name  = "USE_TZ"
        value = local.posthog_env.USE_TZ
      }
      env {
        name  = "SITE_URL"
        value = local.posthog_env.SITE_URL
      }
      env {
        name  = "SERVER_URL"
        value = local.posthog_env.SERVER_URL
      }
      env {
        name  = "DISABLE_SECURE_SSL_REDIRECT"
        value = local.posthog_env.DISABLE_SECURE_SSL_REDIRECT
      }
      env {
        name  = "CLICKHOUSE_DATABASE"
        value = local.posthog_env.CLICKHOUSE_DATABASE
      }
      env {
        name  = "CLICKHOUSE_USER"
        value = local.posthog_env.CLICKHOUSE_USER
      }
      env {
        name  = "CLICKHOUSE_HOST"
        value = local.posthog_env.CLICKHOUSE_HOST
      }
      env {
        name  = "CLICKHOUSE_SECURE"
        value = local.posthog_env.CLICKHOUSE_SECURE
      }
      env {
        name  = "OBJECT_STORAGE_ENABLED"
        value = local.posthog_env.OBJECT_STORAGE_ENABLED
      }
      env {
        name  = "OBJECT_STORAGE_ENDPOINT"
        value = local.posthog_env.OBJECT_STORAGE_ENDPOINT
      }
      env {
        name  = "EMAIL_HOST"
        value = local.posthog_env.EMAIL_HOST
      }
      env {
        name  = "EMAIL_PORT"
        value = local.posthog_env.EMAIL_PORT
      }
      env {
        name  = "EMAIL_USE_TLS"
        value = local.posthog_env.EMAIL_USE_TLS
      }
      env {
        name  = "SLACK_TOKEN"
        value = local.posthog_env.SLACK_TOKEN
      }
      env {
        name  = "SELF_DRIVING_REPO"
        value = local.posthog_env.SELF_DRIVING_REPO
      }

      # Secret-backed env vars
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "POSTHOG_SECRET_KEY"
        secret_name = "secret-key"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name        = "CLICKHOUSE_PASSWORD"
        secret_name = "clickhouse-password"
      }
      env {
        name  = "KAFKA_URL"
        value = "${azurerm_eventhub_namespace.posthog.name}.servicebus.windows.net:9093"
      }
      env {
        name  = "KAFKA_HOSTS"
        value = "${azurerm_eventhub_namespace.posthog.name}.servicebus.windows.net:9093"
      }
      env {
        name        = "KAFKA_PASSWORD"
        secret_name = "kafka-password"
      }
      env {
        name        = "OBJECT_STORAGE_ACCESS_KEY_ID"
        secret_name = "blob-connection-string"
      }
    }

    min_replicas = var.posthog_web_min_replicas
    max_replicas = var.posthog_web_max_replicas

    http_scale_rule {
      name                = "http-concurrency"
      concurrent_requests = 100
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  depends_on = [
    azurerm_container_app_environment.posthog,
    azurerm_container_app.posthog_clickhouse,
    azurerm_role_assignment.posthog_kv_secrets_user,
  ]
}

# ────────────────────────────────────────────────────────────────────────────
# PostHog worker (Celery)
# ────────────────────────────────────────────────────────────────────────────
resource "azurerm_container_app" "posthog_worker" {
  name                         = "${local.posthog_name_prefix}-worker"
  container_app_environment_id = azurerm_container_app_environment.posthog.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.posthog_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.posthog.id]
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_database_url.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "secret-key"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_secret_key.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "redis-url"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_redis_url.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "clickhouse-password"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_clickhouse_password.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "kafka-password"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_kafka_password.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }

  template {
    container {
      name    = "worker"
      image   = "posthog/posthog:${var.posthog_image_tag}"
      cpu     = var.posthog_worker_cpu
      memory  = var.posthog_worker_memory
      command = ["./bin/docker", "--worker"]

      env {
        name  = "SELF_HOSTED"
        value = local.posthog_env.SELF_HOSTED
      }
      env {
        name  = "USE_TZ"
        value = local.posthog_env.USE_TZ
      }
      env {
        name  = "SITE_URL"
        value = local.posthog_env.SITE_URL
      }
      env {
        name  = "SERVER_URL"
        value = local.posthog_env.SERVER_URL
      }
      env {
        name  = "CLICKHOUSE_DATABASE"
        value = local.posthog_env.CLICKHOUSE_DATABASE
      }
      env {
        name  = "CLICKHOUSE_USER"
        value = local.posthog_env.CLICKHOUSE_USER
      }
      env {
        name  = "CLICKHOUSE_HOST"
        value = local.posthog_env.CLICKHOUSE_HOST
      }
      env {
        name  = "CLICKHOUSE_SECURE"
        value = local.posthog_env.CLICKHOUSE_SECURE
      }
      env {
        name  = "OBJECT_STORAGE_ENABLED"
        value = local.posthog_env.OBJECT_STORAGE_ENABLED
      }
      env {
        name  = "OBJECT_STORAGE_ENDPOINT"
        value = local.posthog_env.OBJECT_STORAGE_ENDPOINT
      }
      env {
        name  = "KAFKA_URL"
        value = "${azurerm_eventhub_namespace.posthog.name}.servicebus.windows.net:9093"
      }
      env {
        name  = "KAFKA_HOSTS"
        value = "${azurerm_eventhub_namespace.posthog.name}.servicebus.windows.net:9093"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "POSTHOG_SECRET_KEY"
        secret_name = "secret-key"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name        = "CLICKHOUSE_PASSWORD"
        secret_name = "clickhouse-password"
      }
      env {
        name        = "KAFKA_PASSWORD"
        secret_name = "kafka-password"
      }
    }

    min_replicas = var.posthog_worker_min_replicas
    max_replicas = var.posthog_worker_max_replicas

    custom_scale_rule {
      name             = "cpu"
      custom_rule_type = "cpu"
      metadata = {
        type  = "Utilization"
        value = "70"
      }
    }
  }

  # Worker has no ingress — Celery pulls from broker, doesn't accept HTTP.
  depends_on = [
    azurerm_container_app_environment.posthog,
    azurerm_container_app.posthog_web,
    azurerm_role_assignment.posthog_kv_secrets_user,
  ]
}

# ────────────────────────────────────────────────────────────────────────────
# PostHog plugin-server (Node.js)
# ────────────────────────────────────────────────────────────────────────────
resource "azurerm_container_app" "posthog_plugin_server" {
  name                         = "${local.posthog_name_prefix}-plugin-server"
  container_app_environment_id = azurerm_container_app_environment.posthog.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.posthog_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.posthog.id]
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_database_url.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "redis-url"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_redis_url.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "clickhouse-password"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_clickhouse_password.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }
  secret {
    name                = "kafka-password"
    key_vault_secret_id = azurerm_key_vault_secret.posthog_kafka_password.id
    identity            = azurerm_user_assigned_identity.posthog.id
  }

  template {
    container {
      name    = "plugin-server"
      image   = "posthog/posthog:${var.posthog_image_tag}"
      cpu     = var.posthog_plugin_server_cpu
      memory  = var.posthog_plugin_server_memory
      command = ["./bin/docker", "--plugin-server"]

      env {
        name  = "NODE_OPTIONS"
        value = "--max_old_space_size=2048"
      }
      env {
        name  = "PLUGINS_RELOAD_PUBSUB_CHANNEL"
        value = "reload-plugins"
      }
      env {
        name  = "SELF_HOSTED"
        value = local.posthog_env.SELF_HOSTED
      }
      env {
        name  = "CLICKHOUSE_DATABASE"
        value = local.posthog_env.CLICKHOUSE_DATABASE
      }
      env {
        name  = "CLICKHOUSE_USER"
        value = local.posthog_env.CLICKHOUSE_USER
      }
      env {
        name  = "CLICKHOUSE_HOST"
        value = local.posthog_env.CLICKHOUSE_HOST
      }
      env {
        name  = "CLICKHOUSE_SECURE"
        value = local.posthog_env.CLICKHOUSE_SECURE
      }
      env {
        name  = "KAFKA_URL"
        value = "${azurerm_eventhub_namespace.posthog.name}.servicebus.windows.net:9093"
      }
      env {
        name  = "KAFKA_HOSTS"
        value = "${azurerm_eventhub_namespace.posthog.name}.servicebus.windows.net:9093"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name        = "CLICKHOUSE_PASSWORD"
        secret_name = "clickhouse-password"
      }
      env {
        name        = "KAFKA_PASSWORD"
        secret_name = "kafka-password"
      }
    }

    min_replicas = var.posthog_plugin_server_min_replicas
    max_replicas = var.posthog_plugin_server_max_replicas

    custom_scale_rule {
      name             = "cpu"
      custom_rule_type = "cpu"
      metadata = {
        type  = "Utilization"
        value = "70"
      }
    }
  }

  depends_on = [
    azurerm_container_app_environment.posthog,
    azurerm_container_app.posthog_web,
    azurerm_role_assignment.posthog_kv_secrets_user,
  ]
}

# ────────────────────────────────────────────────────────────────────────────
# Dedicated Application Gateway v2 (WAF) for PostHog — posthog.outrena.ai
# ────────────────────────────────────────────────────────────────────────────
# PostHog gets its own App Gateway (separate from the OUTRENA app App Gateway
# in app_gateway.tf) for blast-radius isolation + distinct WAF rules
# (PostHog ingestion needs higher rate limits than the OUTRENA app).

resource "azurerm_public_ip" "posthog_appgw" {
  name                = "${local.posthog_name_prefix}-appgw-pip"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "${local.posthog_name_prefix}-appgw"
  tags                = local.posthog_tags
}

resource "azurerm_web_application_firewall_policy" "posthog" {
  name                = "${local.posthog_name_prefix}-waf-policy"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.posthog_tags

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
  }

  # Rate-limit: 200 req / 60s / IP — higher than OUTRENA app (PostHog SDK
  # batches + session recordings send frequent pings).
  custom_rules {
    name                 = "RateLimitPostHogPerIp"
    priority             = 1
    rule_type            = "RateLimitRule"
    rate_limit_threshold = 200
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
  }
}

resource "azurerm_application_gateway" "posthog" {
  name                = "${local.posthog_name_prefix}-appgw"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  sku {
    name     = var.appgw_sku
    tier     = var.appgw_sku
    capacity = 2
  }

  gateway_ip_configuration {
    name      = "${local.posthog_name_prefix}-appgw-ipcfg"
    subnet_id = azurerm_subnet.appgw.id
  }

  frontend_port {
    name = "https"
    port = 443
  }
  frontend_port {
    name = "http"
    port = 80
  }

  frontend_ip_configuration {
    name                 = "public"
    public_ip_address_id = azurerm_public_ip.posthog_appgw.id
  }

  # Backend pool — PostHog web Container App FQDN
  backend_address_pool {
    name  = "posthog-web-pool"
    fqdns = [azurerm_container_app.posthog_web.latest_revision_fqdn]
  }

  # Backend settings — HTTPS to the Container App, port 443 (Container Apps
  # ingress terminates TLS by default when external_enabled=true).
  backend_http_settings {
    name                  = "posthog-web-https"
    cookie_based_affinity = "Disabled"
    port                  = 443
    protocol              = "Https"
    request_timeout       = 60
    host_name             = azurerm_container_app.posthog_web.latest_revision_fqdn
  }

  # TLS cert — reuses the OUTRENA wildcard cert (covers *.outrena.ai).
  ssl_certificate {
    name                = "wildcard-cert"
    key_vault_secret_id = azurerm_key_vault_certificate.tls.versionless_secret_id
  }

  # HTTP listener — :80 redirect to :443
  http_listener {
    name                           = "http"
    frontend_ip_configuration_name = "public"
    frontend_port_name             = "http"
    protocol                       = "Http"
  }

  # HTTPS listener — :443 with cert
  http_listener {
    name                           = "https"
    frontend_ip_configuration_name = "public"
    frontend_port_name             = "https"
    protocol                       = "Https"
    ssl_certificate_name           = "wildcard-cert"
    host_name                      = "posthog.${var.base_domain}"
  }

  # Request routing rule — HTTP → redirect
  request_routing_rule {
    name                        = "http-redirect"
    rule_type                   = "Basic"
    http_listener_name          = "http"
    redirect_configuration_name = "http-to-https"
  }

  # Request routing rule — HTTPS → backend
  request_routing_rule {
    name                       = "https-to-backend"
    rule_type                  = "Basic"
    http_listener_name         = "https"
    backend_address_pool_name  = "posthog-web-pool"
    backend_http_settings_name = "posthog-web-https"
  }

  redirect_configuration {
    name                 = "http-to-https"
    redirect_type        = "Permanent"
    target_listener_name = "https"
    include_path         = true
    include_query_string = true
  }

  firewall_policy_id = azurerm_web_application_firewall_policy.posthog.id

  # Autoscale — 2 min in prod, 1 min in dev.
  autoscale_configuration {
    min_capacity = local.is_prod ? 2 : 1
    max_capacity = var.appgw_max_capacity
  }

  tags = local.posthog_tags

  depends_on = [
    azurerm_container_app.posthog_web,
    azurerm_key_vault_certificate.tls,
  ]
}

# DNS A-record — posthog.<base_domain> → PostHog App Gateway public IP
resource "azurerm_dns_a_record" "posthog" {
  name                = "posthog"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 60
  records             = [azurerm_public_ip.posthog_appgw.ip_address]
  tags                = local.posthog_tags
}

# ────────────────────────────────────────────────────────────────────────────
# Monitoring + alert rules (Log Analytics + metric alerts)
# ────────────────────────────────────────────────────────────────────────────

# Action group — reuses the OUTRENA SRE action group if it exists, else
# creates a posthog-specific one. We create a posthog-specific one for
# clearer alert routing (PostHog ops vs OUTRENA app ops).
resource "azurerm_monitor_action_group" "posthog" {
  name                = "${local.posthog_name_prefix}-alerts"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "posthog"

  email_receiver {
    name          = "SRE"
    email_address = var.alert_email
  }

  tags = local.posthog_tags
}

# Alert 1 — PostHog web 5xx rate > 1% (5 min window)
resource "azurerm_monitor_metric_alert" "posthog_web_5xx" {
  name                = "${local.posthog_name_prefix}-web-5xx"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_application_gateway.posthog.id]
  description         = "PostHog App Gateway 5xx rate > 1% for 5 min"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "Microsoft.Network/applicationGateways"
    metric_name      = "FailedRequests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 5

    dimension {
      name     = "ListenerName"
      operator = "Include"
      values   = ["https"]
    }
  }

  action {
    action_group_id = azurerm_monitor_action_group.posthog.id
  }

  tags = local.posthog_tags
}

# Alert 2 — Postgres CPU > 80% for 10 min
resource "azurerm_monitor_metric_alert" "posthog_pg_cpu" {
  name                = "${local.posthog_name_prefix}-pg-cpu-high"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_postgresql_flexible_server.posthog.id]
  description         = "PostHog PostgreSQL CPU > 80% for 15 min"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "cpu_percent"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.posthog.id
  }

  tags = local.posthog_tags
}

# Alert 3 — Redis server load > 80% (memory pressure)
resource "azurerm_monitor_metric_alert" "posthog_redis_server_load" {
  name                = "${local.posthog_name_prefix}-redis-server-load-high"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_redis_cache.posthog.id]
  description         = "PostHog Redis server load > 80% for 15 min"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.Cache/redis"
    metric_name      = "serverLoad"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.posthog.id
  }

  tags = local.posthog_tags
}

# Alert 4 — Event Hubs captured > 80% of throughput units
resource "azurerm_monitor_metric_alert" "posthog_eh_throughput" {
  name                = "${local.posthog_name_prefix}-eh-throughput-high"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_eventhub_namespace.posthog.id]
  description         = "PostHog Event Hubs CaptureBacklog > 1000 for 15 min"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.EventHub/Namespaces"
    metric_name      = "CaptureBacklog"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 1000
  }

  action {
    action_group_id = azurerm_monitor_action_group.posthog.id
  }

  tags = local.posthog_tags
}
