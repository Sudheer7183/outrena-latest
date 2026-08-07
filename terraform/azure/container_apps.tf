# container_apps.tf — 4 Container Apps: backend, frontend, worker, keycloak.
#
# Per migration doc §12.3 + §13.2 env var table. Secrets come from Key Vault
# via `secret.key_vault_secret_id` (managed identity auth — no plaintext in
# env block). Plain env vars use the `env { name, value }` block.
#
# All 4 apps use `revision_mode = "Single"` (new revisions replace old
# in-place — simplifies blue/green via Traffic Manager at the DNS layer).

# ── Backend (FastAPI) ────────────────────────────────────────────────────────
resource "azurerm_container_app" "backend" {
  name                         = "${local.name_prefix}-backend"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.default_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.backend.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.backend.id
  }

  # Secrets pulled from Key Vault via managed identity. Each `secret.name`
  # is the in-app secret reference; `key_vault_secret_id` points to the KV
  # secret's stable ID. The `env.secret_name` below wires them into env vars.
  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.id
    identity            = azurerm_user_assigned_identity.backend.id
  }
  secret {
    name                = "redis-url"
    key_vault_secret_id = azurerm_key_vault_secret.redis_url.id
    identity            = azurerm_user_assigned_identity.backend.id
  }
  secret {
    name                = "celery-broker-url"
    key_vault_secret_id = azurerm_key_vault_secret.celery_broker_url.id
    identity            = azurerm_user_assigned_identity.backend.id
  }
  secret {
    name                = "keycloak-admin-password"
    key_vault_secret_id = azurerm_key_vault_secret.keycloak_admin_password.id
    identity            = azurerm_user_assigned_identity.backend.id
  }
  secret {
    name                = "mailbridge-url"
    key_vault_secret_id = azurerm_key_vault_secret.mailbridge_url.id
    identity            = azurerm_user_assigned_identity.backend.id
  }
  secret {
    name                = "csv-blob-connection-string"
    key_vault_secret_id = azurerm_key_vault_secret.csv_blob_connection_string.id
    identity            = azurerm_user_assigned_identity.backend.id
  }
  secret {
    name                = "collateral-blob-connection-string"
    key_vault_secret_id = azurerm_key_vault_secret.collateral_blob_connection_string.id
    identity            = azurerm_user_assigned_identity.backend.id
  }

  template {
    container {
      name   = "backend"
      image  = "${azurerm_container_registry.main.login_server}/outrena-backend:${var.acr_backend_tag}"
      cpu    = var.backend_cpu
      memory = var.backend_memory

      # ── Plain env vars (§13.2) ──
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "BASE_DOMAIN"
        value = var.base_domain
      }
      env {
        name  = "KEYCLOAK_BASE_URL"
        value = "https://auth.${var.base_domain}"
      }
      env {
        name  = "KEYCLOAK_REALM"
        value = var.keycloak_realm
      }
      env {
        name  = "LLM_API_URL"
        value = var.llm_api_url
      }
      env {
        name  = "SCHEDULER_TICK_SECONDS"
        value = tostring(var.scheduler_tick_seconds)
      }
      env {
        name  = "SCHEDULER_PARTIAL_CAP"
        value = tostring(var.scheduler_partial_cap)
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }
      env {
        name  = "LOG_LEVEL"
        value = var.log_level
      }
      env {
        name  = "SKIP_JWT_VERIFICATION"
        value = tostring(var.skip_jwt_verification)
      }
      env {
        name  = "VERIFY_JWT_ISSUER"
        value = tostring(var.verify_jwt_issuer)
      }
      env {
        name  = "BLOB_CSV_CONTAINER"
        value = var.csv_container_name
      }
      env {
        name  = "BLOB_COLLATERAL_CONTAINER"
        value = var.collateral_container_name
      }

      # ── Secret-backed env vars (§13.2 Key Vault refs) ──
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name        = "CELERY_BROKER_URL"
        secret_name = "celery-broker-url"
      }
      env {
        name        = "KEYCLOAK_ADMIN_PASSWORD"
        secret_name = "keycloak-admin-password"
      }
      env {
        name        = "MAILBRIDGE_URL"
        secret_name = "mailbridge-url"
      }
      env {
        name        = "BLOB_CSV_CONNECTION_STRING"
        secret_name = "csv-blob-connection-string"
      }
      env {
        name        = "BLOB_COLLATERAL_CONNECTION_STRING"
        secret_name = "collateral-blob-connection-string"
      }
    }

    min_replicas = var.backend_min_replicas
    max_replicas = var.backend_max_replicas

    # HTTP concurrency scale rule — when avg concurrent requests > 100, add
    # a replica. Mirrors the migration doc §12.3 "autoscale on CPU ≥ 70%"
    # guidance + adds traffic-driven scaling.
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
    azurerm_container_app_environment.main,
    azurerm_role_assignment.kv_secrets_user,
    azurerm_role_assignment.backend_acr_pull,
  ]
}

# ── Frontend (Vite SPA served by nginx) ──────────────────────────────────────
resource "azurerm_container_app" "frontend" {
  name                         = "${local.name_prefix}-frontend"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.default_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.frontend.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.frontend.id
  }

  template {
    container {
      name   = "frontend"
      image  = "${azurerm_container_registry.main.login_server}/outrena-frontend:${var.acr_frontend_tag}"
      cpu    = var.frontend_cpu
      memory = var.frontend_memory

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "BASE_DOMAIN"
        value = var.base_domain
      }
      env {
        name  = "KEYCLOAK_BASE_URL"
        value = "https://auth.${var.base_domain}"
      }
      env {
        name  = "KEYCLOAK_REALM"
        value = var.keycloak_realm
      }
      env {
        name  = "LOG_LEVEL"
        value = var.log_level
      }
    }

    min_replicas = var.frontend_min_replicas
    max_replicas = var.frontend_max_replicas
  }

  ingress {
    external_enabled = true
    target_port      = 80
    transport        = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  depends_on = [
    azurerm_container_app_environment.main,
    azurerm_role_assignment.frontend_acr_pull,
  ]
}

# ── Worker (Celery) ──────────────────────────────────────────────────────────
resource "azurerm_container_app" "worker" {
  name                         = "${local.name_prefix}-worker"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.default_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.worker.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.worker.id
  }

  # Worker secrets — same set as backend (worker shares the outrena-backend image
  # and needs DB/Redis/Blob/MailBridge access for Celery tasks).
  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.id
    identity            = azurerm_user_assigned_identity.worker.id
  }
  secret {
    name                = "redis-url"
    key_vault_secret_id = azurerm_key_vault_secret.redis_url.id
    identity            = azurerm_user_assigned_identity.worker.id
  }
  secret {
    name                = "celery-broker-url"
    key_vault_secret_id = azurerm_key_vault_secret.celery_broker_url.id
    identity            = azurerm_user_assigned_identity.worker.id
  }
  secret {
    name                = "mailbridge-url"
    key_vault_secret_id = azurerm_key_vault_secret.mailbridge_url.id
    identity            = azurerm_user_assigned_identity.worker.id
  }
  secret {
    name                = "csv-blob-connection-string"
    key_vault_secret_id = azurerm_key_vault_secret.csv_blob_connection_string.id
    identity            = azurerm_user_assigned_identity.worker.id
  }
  secret {
    name                = "collateral-blob-connection-string"
    key_vault_secret_id = azurerm_key_vault_secret.collateral_blob_connection_string.id
    identity            = azurerm_user_assigned_identity.worker.id
  }

  template {
    container {
      name   = "worker"
      image  = "${azurerm_container_registry.main.login_server}/outrena-backend:${var.acr_backend_tag}"
      cpu    = var.worker_cpu
      memory = var.worker_memory

      # Command override — runs Celery worker instead of uvicorn.
      # `celery -A app.celery_app worker --loglevel=INFO --concurrency=4`
      command = [
        "celery",
        "-A", "app.celery_app", "worker",
        "--loglevel=INFO",
        "--concurrency=4",
      ]

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "LOG_LEVEL"
        value = var.log_level
      }
      env {
        name  = "SCHEDULER_TICK_SECONDS"
        value = tostring(var.scheduler_tick_seconds)
      }
      env {
        name  = "SCHEDULER_PARTIAL_CAP"
        value = tostring(var.scheduler_partial_cap)
      }
      env {
        name  = "LLM_API_URL"
        value = var.llm_api_url
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
        name        = "CELERY_BROKER_URL"
        secret_name = "celery-broker-url"
      }
      env {
        name        = "MAILBRIDGE_URL"
        secret_name = "mailbridge-url"
      }
      env {
        name        = "BLOB_CSV_CONNECTION_STRING"
        secret_name = "csv-blob-connection-string"
      }
      env {
        name        = "BLOB_COLLATERAL_CONNECTION_STRING"
        secret_name = "collateral-blob-connection-string"
      }
    }

    min_replicas = var.worker_min_replicas
    max_replicas = var.worker_max_replicas

    # CPU-based scale rule via KEDA cpu scaler — Celery is CPU-bound
    # (LLM calls + JSON parsing). Scale out when avg CPU > 70% per §12.3.
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
    azurerm_container_app_environment.main,
    azurerm_role_assignment.kv_secrets_user,
    azurerm_role_assignment.worker_acr_pull,
  ]
}

# ── Keycloak ─────────────────────────────────────────────────────────────────
# Deployed to the idp Container Apps Environment on IdpSubnet per §12.1.
# External ingress is disabled (only reachable via App Gateway /auth/* path).
resource "azurerm_container_app" "keycloak" {
  name                         = "${local.name_prefix}-keycloak"
  container_app_environment_id = azurerm_container_app_environment.idp.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.default_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.keycloak.id]
  }

  # Keycloak image is pulled from public quay.io — no ACR reference.
  # If you mirror Keycloak to your ACR for air-gapped deployments, swap the
  # image below and add a registry block referencing the keycloak identity.

  secret {
    name                = "keycloak-admin-password"
    key_vault_secret_id = azurerm_key_vault_secret.keycloak_admin_password.id
    identity            = azurerm_user_assigned_identity.keycloak.id
  }
  secret {
    name                = "db-admin-password"
    key_vault_secret_id = azurerm_key_vault_secret.db_admin_password.id
    identity            = azurerm_user_assigned_identity.keycloak.id
  }

  template {
    container {
      name   = "keycloak"
      image  = var.keycloak_image
      cpu    = var.keycloak_cpu
      memory = var.keycloak_memory

      # Keycloak env vars per Keycloak 24 container docs.
      env {
        name  = "KEYCLOAK_ADMIN"
        value = var.keycloak_admin_username
      }
      env {
        name  = "KC_HOSTNAME"
        value = "auth.${var.base_domain}"
      }
      env {
        name  = "KC_HOSTNAME_STRICT"
        value = "false"
      }
      env {
        name  = "KC_HTTP_ENABLED"
        value = "true"
      }
      env {
        name  = "KC_PROXY"
        value = "edge"
      }
      env {
        name  = "KC_DB"
        value = "postgres"
      }
      env {
        name  = "KC_DB_URL"
        value = "jdbc:postgresql://${azurerm_postgresql_flexible_server.main.fqdn}:5432/${var.keycloak_database_name}?sslmode=require"
      }
      env {
        name  = "KC_DB_USERNAME"
        value = var.postgres_admin_login
      }
      env {
        name  = "KC_DB_SCHEMA"
        value = "public"
      }

      env {
        name        = "KEYCLOAK_ADMIN_PASSWORD"
        secret_name = "keycloak-admin-password"
      }
      env {
        name        = "KC_DB_PASSWORD"
        secret_name = "db-admin-password"
      }
    }

    min_replicas = var.keycloak_min_replicas
    max_replicas = var.keycloak_max_replicas
  }

  # Ingress on 8080 — INTERNAL only (external_enabled=false). App Gateway
  # reaches Keycloak via the env's internal FQDN.
  ingress {
    external_enabled = false
    target_port      = 8080
    transport        = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  depends_on = [
    azurerm_container_app_environment.idp,
    azurerm_role_assignment.kv_secrets_user,
    azurerm_postgresql_flexible_server_database.keycloak,
  ]
}
