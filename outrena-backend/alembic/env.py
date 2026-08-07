"""
alembic/env.py — Dual-mode multi-schema migration runner (Phase 2).

Two modes (reference model §7 + migration doc §7.2):

  Mode A — ALEMBIC_TARGET_SCHEMA env var set:
      Migrate ONE specific schema only (used by TenantProvisioningService
      during the 6-step flow, when the new tenant's registry row is still
      status='PROVISIONING' and would be missed by active-tenant discovery).

  Mode B — ALEMBIC_TARGET_SCHEMA not set (default):
      1. Migrate public schema first (registry tables).
      2. Iterate all ACTIVE tenant schemas and migrate each one.

Each schema carries its own alembic_version table for independent head
tracking. Idempotency: re-running upgrade head is a no-op.

Critical: schema names are taken from public.tenants.schema_name, NOT
constructed from the slug, so a slug rename (forbidden, but defensive)
can never desync the migration target from the registry.
"""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from app.core.config import get_settings
from app.core.database import Base

# Import ALL models here so Base.metadata is fully populated for autogenerate.
# Phase 1: Tenant + TenantConfig (public schema).
# Phase 2: no new models (provisioning flow only).
# Phase 3: prospect/campaign/flow/config/phase3 models (tenant schema).
from app.models.tenant import Tenant  # noqa: F401 — populate metadata
from app.models.tenant_config import TenantConfig  # noqa: F401
from app.models.subscription import Subscription  # noqa: F401 — BUG-13 fix
from app.models.plan import Plan  # noqa: F401 — BUG-13 fix
from app.models.prospect_models import (  # noqa: F401
    CallLog,
    Competitor,
    IcpProfile,
    JobChangeAlert,
    Meeting,
    MeetingPrep,
    Prospect,
)
from app.models.campaign_models import (  # noqa: F401
    AbTest,
    AbTestAssignment,
    Campaign,
    CampaignCollateralLink,
    CampaignProspect,
    CampaignResult,
    Collateral,
    Deal,
    EmailAbTest,
    ReplyDraft,
    Sequence,
    SubjectLine,
)
from app.models.flow_models import (  # noqa: F401
    AutopilotQueue,
    FlowAbTest,
    FlowRun,
    FlowRunStep,
    FlowWebhook,
    FlowWebhookDelivery,
    ProspectingFlow,
    RateLimit,
    RateLimitLog,
)
from app.models.config_models import (  # noqa: F401
    Domain,
    ExclusionRule,
    LlmConfig,
    MailBridgeConfig,
    PromptTemplate,
    ProspectingIntegration,
    SystemParameter,
)
from app.models.global_llm_config import GlobalLlmConfig  # noqa: F401 — populate metadata
from app.models.phase3_models import (  # noqa: F401
    ContentIdea,
    DomainEnrichment,
    EmailTemplate,
    LinkedInConfig,
    LinkedInEngagement,
    LinkedInInboxMessage,
    OptimizationAction,
    OptimizationRule,
    ProspectSource,
    SchedulerStatus,
    Signal,
    SignalMonitor,
    SourceConfig,
    WeeklyDigest,
)
# SAAS2-USER-BE — per-user email quota + sender identities (tenant schema).
from app.models.user_email import UserEmailQuota, UserSenderIdentity  # noqa: F401
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject DATABASE_URL from settings (overrides sqlalchemy.url in alembic.ini)
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata

# Schemas managed by this runner. Public always goes first; tenant schemas
# follow in alphabetical order for reproducibility.
PUBLIC_SCHEMA = "public"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _target_schema_from_env() -> str | None:
    """Return the explicit target schema from the environment, or None."""
    raw = os.environ.get("ALEMBIC_TARGET_SCHEMA")
    return raw.strip() if raw and raw.strip() else None


async def _list_active_tenant_schemas(connectable: Any) -> list[str]:
    """Read public.tenants for ACTIVE + PROVISIONING rows.

    Returns an empty list if the table does not yet exist — this is the
    correct result on a fresh database where migration 0001 has just run
    for the first time and no tenants have been provisioned yet.
    asyncpg caches prepared-statement plans per-connection; since NullPool
    opens a new physical connection for every connect() call, we catch the
    UndefinedTableError here rather than trying to invalidate the cache.
    """
    try:
        async with connectable.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT schema_name FROM public.tenants "
                    "WHERE deleted_at IS NULL "
                    "AND status IN ('ACTIVE', 'PROVISIONING') "
                    "ORDER BY schema_name"
                )
            )
            rows = [row[0] for row in result.fetchall()]
            print(f"[env.py] _list_active_tenant_schemas found: {rows}")
            return rows
    except Exception as exc:
        # asyncpg raises UndefinedTableError when public.tenants doesn't
        # exist yet (fresh DB — migration 0001 just created it in the same
        # Alembic run, but the new connection's plan cache doesn't know).
        # SQLAlchemy wraps it as ProgrammingError. Any variant means
        # "no tenants to migrate" — return empty list and continue.
        if "UndefinedTableError" in type(exc).__name__ or "tenants" in str(exc):
            print(f"[env.py] _list_active_tenant_schemas swallowed: {type(exc).__name__}: {exc}")
            return []
        raise


def _ensure_schema_exists(connection: Connection, schema_name: str) -> None:
    """CREATE SCHEMA IF NOT EXISTS so the first migration in a fresh schema
    doesn't fail on the version-table creation step."""
    connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))


def _set_search_path(connection: Connection, schema_name: str) -> None:
    """Lock the session's search_path so alembic_version + DDL land in the
    correct schema. Public stays second so shared references resolve."""
    connection.execute(text(f'SET search_path TO "{schema_name}", {PUBLIC_SCHEMA}'))


# ── Offline mode ──────────────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a DB connection."""
    target = _target_schema_from_env()
    schemas = [target] if target else [PUBLIC_SCHEMA]

    url = config.get_main_option("sqlalchemy.url")
    for schema in schemas:
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=True,
            compare_server_default=True,
            version_table_schema=schema,
        )
        with context.begin_transaction():
            context.run_migrations()


# ── Online mode ───────────────────────────────────────────────────────────────


def do_run_migrations(connection: Connection, schema_name: str) -> None:
    print(f"[env.py] do_run_migrations starting for schema_name={schema_name!r}")
    _ensure_schema_exists(connection, schema_name)
    _set_search_path(connection, schema_name)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        version_table_schema=schema_name,
    )
    with context.begin_transaction():
        context.run_migrations()
    # Diagnostic proved context.begin_transaction()'s implicit commit-on-exit
    # was NOT persisting to Postgres — every container restart replayed all
    # migrations from revision "none", meaning alembic_version itself never
    # survived. Force an explicit commit on the sync-bridge connection here.
    connection.commit()
    # Diagnostic: check visibility of public.tenants on THIS SAME connection,
    # immediately after the transaction context manager exits (i.e. after
    # whatever commit/rollback it performs).
    check = connection.execute(
        text("SELECT to_regclass('public.tenants') AS reg")
    ).scalar()
    print(f"[env.py] AFTER migrations for schema_name={schema_name!r}: "
          f"to_regclass('public.tenants') = {check!r}")


async def _migrate_single_schema(connectable: Any, schema_name: str) -> None:
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations, schema_name)


async def run_migrations_online() -> None:
    """Online mode — async engine. Migrate public first, then tenants."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    target = _target_schema_from_env()
    if target:
        # Mode A: one schema only
        await _migrate_single_schema(connectable, target)
    else:
        # Mode B: public first, then every ACTIVE/PROVISIONING tenant schema
        await _migrate_single_schema(connectable, PUBLIC_SCHEMA)

        tenant_schemas = await _list_active_tenant_schemas(connectable)
        for schema_name in tenant_schemas:
            if schema_name == PUBLIC_SCHEMA:
                continue  # already done
            await _migrate_single_schema(connectable, schema_name)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())