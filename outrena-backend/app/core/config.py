# """
# config.py — Application settings (single source of truth).

# All configuration flows through this one Settings object so no value is ever
# duplicated between .env, alembic.ini, or docker-compose.

# WARNING (Reference Pitfall #4): if a key appears twice in .env, the LAST value
# silently wins. Keep .env free of duplicates — the audit_env.py pre-deploy script
# fails CI on duplicate keys.

# FIX: Added TAVILY_API_KEY field. Previously it was missing from Settings, and
# because Settings uses extra="ignore", the value from .env was silently dropped.
# getattr(settings, "TAVILY_API_KEY", "") always returned "" even when the key
# was set in .env. This caused _web_search() to skip every search silently.
# """
# from __future__ import annotations

# from functools import lru_cache

# from pydantic_settings import BaseSettings, SettingsConfigDict


# class Settings(BaseSettings):
#     """Environment-driven application settings (Pydantic v2)."""

#     model_config = SettingsConfigDict(env_file=".env", extra="ignore")

#     # ── Environment ─────────────────────────────────────────────────────────
#     ENVIRONMENT: str = "development"          # development | staging | production
#     BASE_DOMAIN: str = "localhost"            # e.g. example.com — subdomains hang off this

#     # ── Database / cache ────────────────────────────────────────────────────
#     DATABASE_URL: str = (
#         "postgresql+asyncpg://app:app@localhost:5432/outrena"
#     )
#     REDIS_URL: str = "redis://localhost:6379/0"

#     # ── Auth (Keycloak or any RS256 OIDC provider) ──────────────────────────
#     KEYCLOAK_BASE_URL: str = "http://localhost:8080"
#     KEYCLOAK_REALM: str = "outrena"
#     KEYCLOAK_ADMIN_CLIENT_ID: str = "admin-cli"
#     KEYCLOAK_ADMIN_USERNAME: str = "admin"
#     KEYCLOAK_ADMIN_PASSWORD: str = "admin"
#     KEYCLOAK_FRONTEND_CLIENT_ID: str = "frontend"

#     # Dev-only bypass. NEVER true in production.
#     SKIP_JWT_VERIFICATION: bool = False

#     # Pitfall #2: browser-facing issuer may differ from the Docker-internal
#     # Keycloak URL. When False, signature + audience are still verified.
#     VERIFY_JWT_ISSUER: bool = False

#     # ── CORS ────────────────────────────────────────────────────────────────
#     ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost"]

#     # ── Scheduler (Phase 5) ─────────────────────────────────────────────────
#     SCHEDULER_ENABLED: bool = True
#     SCHEDULER_TICK_SECONDS: int = 300
#     SCHEDULER_PARTIAL_CAP: int = 5
#     SCHEDULER_PARTIAL_PER_TICK_CAP: int = 5

#     # ── LLM gateway ─────────────────────────────────────────────────────────
#     # ZAI default provider (in-house endpoint, no API key required)
#     LLM_API_URL: str = "https://open.bigmodel.cn/api/paas/v4"
#     LLM_DEFAULT_TIMEOUT_SECONDS: int = 60

#     # ── Web search ──────────────────────────────────────────────────────────
#     # FIX: TAVILY_API_KEY was missing — Settings extra="ignore" silently dropped
#     # the .env value, so _web_search() always got "" and skipped every search.
#     # Get your free key at https://tavily.com (1,000 searches/month free).
#     TAVILY_API_KEY: str = "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"

#     # ── Celery / background tasks ───────────────────────────────────────────
#     CELERY_BROKER_URL: str = "redis://localhost:6379/1"
#     CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

#     # ── Storage (S3 on AWS, Blob on Azure) ──────────────────────────────────
#     STORAGE_PROVIDER: str = "local"  # local | s3 | azure_blob
#     S3_BUCKET: str = ""
#     S3_REGION: str = "us-east-1"
#     S3_ACCESS_KEY: str = ""
#     S3_SECRET_KEY: str = ""
#     S3_PUBLIC_URL: str = ""
#     BLOB_CONNECTION_STRING: str = ""
#     BLOB_CONTAINER: str = "outrena"

#     # ── MailBridge ──────────────────────────────────────────────────────────
#     MAILBRIDGE_DEFAULT_URL: str = ""
#     MAILBRIDGE_TIMEOUT_SECONDS: int = 30

#     # ── Logging ─────────────────────────────────────────────────────────────
#     LOG_LEVEL: str = "INFO"

#     # ── SaaS platform (Phase 7 — billing, secrets, audit) ───────────────────
#     PAYMENT_PROVIDER: str = "mock"
#     STRIPE_SECRET_KEY: str = ""
#     STRIPE_WEBHOOK_SECRET: str = ""

#     SECRET_BACKEND: str = "env"
#     AWS_REGION: str = "us-east-1"
#     AZURE_KEYVAULT_URL: str = ""

#     ENCRYPTION_KEY: str = ""

#     PUBLIC_SUPPORT_EMAIL: str = "support@outrena.ai"
#     PUBLIC_SALES_EMAIL: str = "sales@outrena.ai"
#     PUBLIC_SUPPORT_PHONE: str = ""
#     PUBLIC_SUPPORT_ADDRESS: str = ""
#     PUBLIC_SUPPORT_HOURS: str = "Mon–Fri, 9am–6pm ET"

#     # === SAAS2: Dual-path integrations ===
#     PLATFORM_INTEGRATION_KEY_PREFIX: str = "platform/integrations"
#     PLATFORM_LLM_KEY_PREFIX: str = "platform/llm"
#     PLATFORM_INTEGRATION_TYPES: str = "apollo,clay,zoominfo,clearbit,hunter,mailbridge,linkedin"
#     PLATFORM_LLM_PROVIDERS: str = "openai,anthropic,azure_openai,google,cohere,mistral,groq"

#     # === SAAS2: User capabilities ===
#     DEFAULT_USER_DAILY_EMAIL_QUOTA: int = 100
#     SPAM_COMPLAINT_THRESHOLD: float = 0.001
#     BOUNCE_RATE_THRESHOLD: float = 0.05
#     SPAM_THROTTLE_HOURS: int = 24
#     BOUNCE_THROTTLE_HOURS: int = 1

#     # === SAAS2: Telemetry + observability ===
#     OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
#     OTEL_SERVICE_NAME: str = "outrena-backend"
#     OTEL_RESOURCE_ATTRIBUTES: str = "deployment.environment=development,service.namespace=outrena"
#     OTEL_TRACES_SAMPLER: str = "parentbased_traceidratio"
#     OTEL_TRACES_SAMPLER_ARG: str = "1.0"
#     METRICS_ENABLED: bool = True
#     USAGE_COST_TABLE_JSON: str = ""

#     # === SAAS2: GDPR compliance ===
#     GDPR_ENABLED: bool = True
#     DPO_EMAIL: str = "dpo@outrena.io"
#     GDPR_DSR_ACKNOWLEDGE_DAYS: int = 3
#     GDPR_DSR_COMPLETION_DAYS: int = 30
#     DATA_RETENTION_PROSPECT_DAYS: int = 730
#     AUDIT_LOG_PII_READS: bool = True

#     # === PostHog ===
#     POSTHOG_KEY: str = ""
#     POSTHOG_HOST: str = "http://posthog:8000"
#     POSTHOG_FLUSH_AT: int = 10
#     POSTHOG_FLUSH_INTERVAL: float = 1.0
#     POSTHOG_PERSONAL_API_KEY: str = ""
#     POSTHOG_PROJECT_ID: str = ""

#     @property
#     def is_production(self) -> bool:
#         return self.ENVIRONMENT == "production"

#     @property
#     def is_development(self) -> bool:
#         return self.ENVIRONMENT == "development"

#     @property
#     def keycloak_realm_url(self) -> str:
#         return f"{self.KEYCLOAK_BASE_URL}/realms/{self.KEYCLOAK_REALM}"

#     @property
#     def keycloak_jwks_url(self) -> str:
#         return f"{self.keycloak_realm_url}/protocol/openid-connect/certs"


# @lru_cache
# def get_settings() -> Settings:
#     """Cached settings accessor — import this, never instantiate Settings directly."""
#     return Settings()

"""
config.py — Application settings (single source of truth).

All configuration flows through this one Settings object so no value is ever
duplicated between .env, alembic.ini, or docker-compose.

WARNING (Reference Pitfall #4): if a key appears twice in .env, the LAST value
silently wins. Keep .env free of duplicates — the audit_env.py pre-deploy script
fails CI on duplicate keys.

FIX: Added TAVILY_API_KEY field. Previously it was missing from Settings, and
because Settings uses extra="ignore", the value from .env was silently dropped.
getattr(settings, "TAVILY_API_KEY", "") always returned "" even when the key
was set in .env. This caused _web_search() to skip every search silently.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application settings (Pydantic v2)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Environment ─────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"          # development | staging | production
    BASE_DOMAIN: str = "localhost"            # e.g. example.com — subdomains hang off this

    # ── Database / cache ────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://app:app@localhost:5432/outrena"
    )
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Auth (Keycloak or any RS256 OIDC provider) ──────────────────────────
    KEYCLOAK_BASE_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "outrena"
    KEYCLOAK_ADMIN_CLIENT_ID: str = "admin-cli"
    KEYCLOAK_ADMIN_USERNAME: str = "admin"
    KEYCLOAK_ADMIN_PASSWORD: str = "admin"
    KEYCLOAK_FRONTEND_CLIENT_ID: str = "frontend"

    # Dev-only bypass. NEVER true in production.
    SKIP_JWT_VERIFICATION: bool = False

    # Pitfall #2: browser-facing issuer may differ from the Docker-internal
    # Keycloak URL. When False, signature + audience are still verified.
    VERIFY_JWT_ISSUER: bool = False

    # ── CORS ────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost"]

    # ── Scheduler (Phase 5) ─────────────────────────────────────────────────
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TICK_SECONDS: int = 300
    SCHEDULER_PARTIAL_CAP: int = 5
    SCHEDULER_PARTIAL_PER_TICK_CAP: int = 5

    # ── LLM gateway ─────────────────────────────────────────────────────────
    # ZAI default provider (in-house endpoint, no API key required)
    LLM_API_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    LLM_DEFAULT_TIMEOUT_SECONDS: int = 60

    # ── Web search ──────────────────────────────────────────────────────────
    # FIX: TAVILY_API_KEY was missing — Settings extra="ignore" silently dropped
    # the .env value, so _web_search() always got "" and skipped every search.
    # Get your free key at https://tavily.com (1,000 searches/month free).
    TAVILY_API_KEY: str = "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"

    # ── Celery / background tasks ───────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Storage (S3 on AWS, Blob on Azure) ──────────────────────────────────
    STORAGE_PROVIDER: str = "local"  # local | s3 | azure_blob
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_PUBLIC_URL: str = ""
    BLOB_CONNECTION_STRING: str = ""
    BLOB_CONTAINER: str = "outrena"

    # ── MailBridge ──────────────────────────────────────────────────────────
    MAILBRIDGE_DEFAULT_URL: str = "http://172.93.49.106:9005"
    MAILBRIDGE_TIMEOUT_SECONDS: int = 30
    MAILBRIDGE_API_KEY: str = ""  # Tenant API key (mb_live_...) for MailBridge tenancy mode
    MAILBRIDGE_PLATFORM_ADMIN_SECRET: str = ""  # Platform admin secret for POST /platform/register
    MAILBRIDGE_REPLY_POLL_ENABLED: bool = True   # Set False to disable without redeployment
    MAILBRIDGE_REPLY_POLL_SECONDS: int = 120    # How often to poll MailBridge for replies

    # ── Logging ─────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── SaaS platform (Phase 7 — billing, secrets, audit) ───────────────────
    PAYMENT_PROVIDER: str = "mock"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    SECRET_BACKEND: str = "env"
    AWS_REGION: str = "us-east-1"
    AZURE_KEYVAULT_URL: str = ""

    ENCRYPTION_KEY: str = ""

    PUBLIC_SUPPORT_EMAIL: str = "support@outrena.ai"
    PUBLIC_SALES_EMAIL: str = "sales@outrena.ai"
    PUBLIC_SUPPORT_PHONE: str = ""
    PUBLIC_SUPPORT_ADDRESS: str = ""
    PUBLIC_SUPPORT_HOURS: str = "Mon–Fri, 9am–6pm ET"

    # === SAAS2: Dual-path integrations ===
    PLATFORM_INTEGRATION_KEY_PREFIX: str = "platform/integrations"
    PLATFORM_LLM_KEY_PREFIX: str = "platform/llm"
    PLATFORM_INTEGRATION_TYPES: str = "apollo,clay,zoominfo,clearbit,hunter,mailbridge,linkedin"
    PLATFORM_LLM_PROVIDERS: str = "openai,anthropic,azure_openai,google,cohere,mistral,groq"

    # === SAAS2: User capabilities ===
    DEFAULT_USER_DAILY_EMAIL_QUOTA: int = 100
    SPAM_COMPLAINT_THRESHOLD: float = 0.001
    BOUNCE_RATE_THRESHOLD: float = 0.05
    SPAM_THROTTLE_HOURS: int = 24
    BOUNCE_THROTTLE_HOURS: int = 1

    # === SAAS2: Telemetry + observability ===
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_SERVICE_NAME: str = "outrena-backend"
    OTEL_RESOURCE_ATTRIBUTES: str = "deployment.environment=development,service.namespace=outrena"
    OTEL_TRACES_SAMPLER: str = "parentbased_traceidratio"
    OTEL_TRACES_SAMPLER_ARG: str = "1.0"
    METRICS_ENABLED: bool = True
    USAGE_COST_TABLE_JSON: str = ""

    # === SAAS2: GDPR compliance ===
    GDPR_ENABLED: bool = True
    DPO_EMAIL: str = "dpo@outrena.io"
    GDPR_DSR_ACKNOWLEDGE_DAYS: int = 3
    GDPR_DSR_COMPLETION_DAYS: int = 30
    DATA_RETENTION_PROSPECT_DAYS: int = 730
    AUDIT_LOG_PII_READS: bool = True

    # === PostHog ===
    POSTHOG_KEY: str = ""
    POSTHOG_HOST: str = "http://posthog:8000"
    POSTHOG_FLUSH_AT: int = 10
    POSTHOG_FLUSH_INTERVAL: float = 1.0
    POSTHOG_PERSONAL_API_KEY: str = ""
    POSTHOG_PROJECT_ID: str = ""

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def keycloak_realm_url(self) -> str:
        return f"{self.KEYCLOAK_BASE_URL}/realms/{self.KEYCLOAK_REALM}"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.keycloak_realm_url}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import this, never instantiate Settings directly."""
    return Settings()
