"""Initial tenant-schema migration: 5 enums + all tenant-scoped tables.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00

This migration creates the 5 required enum types (migration doc §5.2) plus
all tenant-scoped tables (§5.1, §5.6) — 28 spec models + 22 Phase 3+ extension
models — inside each ``tenant_{slug}`` schema. It is a NO-OP for the ``public``
schema: ``public.tenants``, ``public.tenant_config``, and
``public.platform_audit_log`` are owned by migration ``0001_initial_public.py``.

Follows §4.6 hard rules:

1. **Schema targeting via ``_s()``, never ``os.environ`` inside migration files.**
   ``env.py`` iterates schemas within one process; env vars are not re-set per
   schema. Only ``context.get_context().version_table_schema`` is correct.

2. **Branch on schema inside ``upgrade()``.** Early-return for ``public``;
   create everything for any ``tenant_{slug}`` schema.

3. **Idempotency guards on every DDL operation.** ``_type_exists``,
   ``_table_exists``, ``_column_exists`` checks before any CREATE.

4. **Revision ID ≤ 32 chars** (``"0002"`` — 4 chars).

5. **Autogenerate filter:** ``env.py`` iterates only ACTIVE/PROVISIONING tenant
   schemas + public, so this migration is only applied to those schemas.

The 5 required enums are created with snake_case names matching §5.2:
``seniority_tier``, ``intent_source``, ``enrichment_tier``, ``touch_angle``,
``email_status``. The 8 additional flow-engine enums (used by ``flow_models``)
are created with the same snake_case convention.

Tables are created in dependency order (referenced tables first) so inline
``sa.ForeignKey(...)`` constraints resolve at CREATE TABLE time. All FKs
reference unqualified ``Target.id`` — the session's ``search_path`` is locked
to the tenant schema by ``env.py``, so unqualified names resolve correctly.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

# Populated by _create_enum() as each type is declared, so _enum() can look
# up the member values without duplicating them at every column call site.
_ENUM_VALUES: dict[str, tuple[str, ...]] = {}

# ── revision identifiers ────────────────────────────────────────────────────
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── §4.6 hard-rule helpers ──────────────────────────────────────────────────


def _s() -> str:
    """Return the active schema for this migration step.

    Reads ``context.get_context().version_table_schema`` (NOT ``os.environ``)
    because ``env.py`` iterates schemas within one process and env vars are
    not re-set per schema. Defaults to ``"public"`` if no context is active
    (e.g. offline mode or unit tests).
    """
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return getattr(ctx, "version_table_schema", None) or "public"


def _type_exists(bind, schema: str, name: str) -> bool:
    """Check if a PostgreSQL enum type exists in the given schema."""
    result = bind.execute(
        text(
            "SELECT 1 FROM pg_type t "
            "JOIN pg_namespace n ON t.typnamespace = n.oid "
            "WHERE n.nspname = :schema AND t.typname = :name"
        ),
        {"schema": schema, "name": name},
    )
    return result.fetchone() is not None


def _table_exists(bind, schema: str, name: str) -> bool:
    """Check if a table exists in the given schema."""
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name"
        ),
        {"schema": schema, "name": name},
    )
    return result.fetchone() is not None


def _column_exists(bind, schema: str, table: str, column: str) -> bool:
    """Check if a column exists in the given schema.table.

    Used by future ALTER TABLE migrations that add columns with
    ``ADD COLUMN IF NOT EXISTS`` not available in older PG versions
    or when working around constraint naming issues.
    """
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table "
            "AND column_name = :column"
        ),
        {"schema": schema, "table": table, "column": column},
    )
    return result.fetchone() is not None


def _create_enum(bind, schema: str, name: str, values: tuple[str, ...]) -> None:
    """``CREATE TYPE {schema}.{name} AS ENUM (...)`` — idempotent.

    Skips creation if the type already exists in the target schema.
    Always records ``values`` in ``_ENUM_VALUES`` so ``_enum()`` can build
    a correctly-populated, create_type=False column type reference.
    """
    _ENUM_VALUES[name] = values
    if _type_exists(bind, schema, name):
        return
    vals = ", ".join(f"'{v}'" for v in values)
    bind.execute(text(f'CREATE TYPE {schema}."{name}" AS ENUM ({vals})'))


def _enum(schema: str, name: str) -> PGEnum:
    """Return a PG-native ``ENUM`` type that references an existing type.

    IMPORTANT: ``create_type`` is a PostgreSQL-dialect-specific parameter —
    it only exists on ``sqlalchemy.dialects.postgresql.ENUM``. The generic
    ``sa.Enum(create_type=False)`` silently DROPS that kwarg (it is not a
    recognized parameter on the generic type), so the internal PG dialect
    impl SQLAlchemy builds for DDL purposes always defaults to
    create_type=True regardless of what was passed to sa.Enum(). This is
    why every op.create_table() call using a plain sa.Enum() column here
    was emitting a redundant ``CREATE TYPE`` (with no values, since none
    were given) that failed with DuplicateObjectError — the type had
    already been created moments earlier by _create_enum() above.

    Using the dialect-specific ENUM class directly, with the real member
    values (recorded by _create_enum), makes create_type=False actually
    take effect.
    """
    values = _ENUM_VALUES.get(name, ())
    return PGEnum(*values, name=name, schema=schema, create_type=False)


# ── upgrade / downgrade ─────────────────────────────────────────────────────


def upgrade() -> None:
    schema = _s()
    if schema == "public":
        # Public-schema DDL is owned by 0001_initial_public.py
        # (public.tenants + public.tenant_config + public.platform_audit_log).
        # This migration is a no-op for the public schema.
        return

    bind = op.get_bind()

    # ── 5 required enum types (migration doc §5.2) ────────────────────────
    _create_enum(bind, schema, "seniority_tier", ("C_Suite", "Director", "IC"))
    _create_enum(
        bind,
        schema,
        "intent_source",
        (
            "FUNDING_URGENCY",
            "HIRING_BUDGET",
            "FORUM_PAIN",
            "LINKEDIN_DEMAND",
            "REFERRAL",
            "INBOUND",
            "OTHER",
        ),
    )
    _create_enum(bind, schema, "enrichment_tier", ("ENRICHED", "PARTIAL", "UNENRICHABLE"))
    _create_enum(
        bind,
        schema,
        "touch_angle",
        (
            "FirstTouch",
            "NewEvidence",
            "DifferentPain",
            "IndustryInsight",
            "DirectQuestion",
            "Breakup",
        ),
    )
    _create_enum(
        bind,
        schema,
        "email_status",
        (
            "Draft",
            "QaFailed",
            "QaPassed",
            "Scheduled",
            "Sent",
            "Replied",
            "Bounced",
            "Failed",
        ),
    )

    # ── 8 additional enum types (flow_models + phase3_models) ──────────────
    _create_enum(
        bind,
        schema,
        "flow_run_status",
        ("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "RATE_LIMITED"),
    )
    _create_enum(
        bind,
        schema,
        "flow_run_step_kind",
        ("SOURCE", "ENRICHMENT", "GATE", "SCORE", "IMPORT"),
    )
    _create_enum(
        bind,
        schema,
        "flow_run_step_status",
        ("PENDING", "RUNNING", "SUCCESS", "SKIPPED", "FAILED", "GATED_OUT"),
    )
    _create_enum(
        bind,
        schema,
        "flow_ab_test_status",
        ("DRAFT", "RUNNING", "COMPLETED", "PAUSED"),
    )
    _create_enum(
        bind,
        schema,
        "webhook_trigger_event",
        ("ICP_CREATED", "FLOW_RUN_COMPLETED", "FLOW_RUN_FAILED", "PROSPECT_IMPORTED"),
    )
    _create_enum(
        bind,
        schema,
        "webhook_delivery_status",
        ("PENDING", "DELIVERED", "FAILED", "RETRYING"),
    )
    _create_enum(
        bind,
        schema,
        "autopilot_queue_status",
        ("QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"),
    )
    _create_enum(
        bind,
        schema,
        "rate_limit_window",
        ("MINUTELY", "HOURLY", "DAILY"),
    )

    # ════════════════════════════════════════════════════════════════════════
    # Tier 0 — Independent tables (no FK to other tenant tables)
    # ════════════════════════════════════════════════════════════════════════

    # ── LlmConfig ──────────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "LlmConfig"):
        op.create_table(
            "LlmConfig",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("modelId", sa.String(), nullable=False),
            sa.Column("apiKey", sa.String(), nullable=True),
            sa.Column("baseUrl", sa.String(), nullable=True),
            sa.Column("isDefault", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("settings", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("modelTier", sa.String(), nullable=False, server_default="'standard'"),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index(
            "ix_LlmConfig_isDefault_isActive",
            "LlmConfig",
            ["isDefault", "isActive"],
            schema=schema,
        )

    # ── IcpProfile ─────────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "IcpProfile"):
        op.create_table(
            "IcpProfile",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("persona", sa.Text(), nullable=False),
            sa.Column("companyType", sa.String(), nullable=True),
            sa.Column("topObjections", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("painPoints", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("valueProps", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("senderRole", sa.String(), nullable=True),
            sa.Column("senderCompany", sa.String(), nullable=True),
            sa.Column("senderOffer", sa.String(), nullable=True),
            sa.Column("proofMetric", sa.String(), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── Domain ─────────────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "Domain"):
        op.create_table(
            "Domain",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("domainName", sa.String(), nullable=False, unique=True),
            sa.Column("spfStatus", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("dkimStatus", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("dmarcStatus", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("dailySendLimit", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("warmingWeek", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("lastChecked", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── PromptTemplate ─────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "PromptTemplate"):
        op.create_table(
            "PromptTemplate",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("key", sa.String(), nullable=False, unique=True),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=False),
            sa.Column("template", sa.Text(), nullable=False),
            sa.Column("isEditable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("defaultValue", sa.Text(), nullable=False),
            sa.Column("variables", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("sortOrder", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── SystemParameter ────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "SystemParameter"):
        op.create_table(
            "SystemParameter",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("key", sa.String(), nullable=False, unique=True),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("label", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=False),
            sa.Column("impact", sa.String(), nullable=False),
            sa.Column("valueType", sa.String(), nullable=False, server_default="'number'"),
            sa.Column("value", sa.String(), nullable=False),
            sa.Column("defaultValue", sa.String(), nullable=False),
            sa.Column("minValue", sa.String(), nullable=True),
            sa.Column("maxValue", sa.String(), nullable=True),
            sa.Column("unit", sa.String(), nullable=True),
            sa.Column("isAdvanced", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── ProspectingIntegration ─────────────────────────────────────────────
    if not _table_exists(bind, schema, "ProspectingIntegration"):
        op.create_table(
            "ProspectingIntegration",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("platform", sa.String(), nullable=False, unique=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("apiKey", sa.String(), nullable=True),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("settings", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("lastTestedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("lastTestResult", sa.String(), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── ExclusionRule ──────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "ExclusionRule"):
        op.create_table(
            "ExclusionRule",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("value", sa.String(), nullable=False),
            sa.Column("reason", sa.String(), nullable=True),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("type", "value", name="uq_ExclusionRule_type_value"),
            schema=schema,
        )
        op.create_index("ix_ExclusionRule_type", "ExclusionRule", ["type"], schema=schema)
        op.create_index("ix_ExclusionRule_isActive", "ExclusionRule", ["isActive"], schema=schema)

    # ── Collateral ─────────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "Collateral"):
        op.create_table(
            "Collateral",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("url", sa.String(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("fileName", sa.String(), nullable=True),
            sa.Column("fileSize", sa.Integer(), nullable=True),
            sa.Column("mimeType", sa.String(), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── LinkedInConfig ─────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "LinkedInConfig"):
        op.create_table(
            "LinkedInConfig",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("accountName", sa.String(), nullable=False),
            sa.Column("accountHandle", sa.String(), nullable=True),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("cookieJar", sa.Text(), nullable=True),
            sa.Column("lastSyncedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("syncStatus", sa.String(), nullable=False, server_default="'idle'"),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── EmailTemplate ──────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "EmailTemplate"):
        op.create_table(
            "EmailTemplate",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False, server_default="'general'"),
            sa.Column("framework", sa.String(), nullable=True),
            sa.Column("subjectTemplate", sa.String(), nullable=True),
            sa.Column("bodyTemplate", sa.Text(), nullable=False),
            sa.Column("variables", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("isShared", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_EmailTemplate_category", "EmailTemplate", ["category"], schema=schema)

    # ── SourceConfig ───────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "SourceConfig"):
        op.create_table(
            "SourceConfig",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("apiKey", sa.String(), nullable=True),
            sa.Column("dailyQuota", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("usedToday", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("settings", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("source", name="uq_SourceConfig_source"),
            schema=schema,
        )

    # ── SignalMonitor ──────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "SignalMonitor"):
        op.create_table(
            "SignalMonitor",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("signalType", sa.String(), nullable=False),
            sa.Column("conditions", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("lastRunAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_SignalMonitor_isActive", "SignalMonitor", ["isActive"], schema=schema)

    # ── DomainEnrichment ───────────────────────────────────────────────────
    if not _table_exists(bind, schema, "DomainEnrichment"):
        op.create_table(
            "DomainEnrichment",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("domain", sa.String(), nullable=False),
            sa.Column("companyName", sa.String(), nullable=True),
            sa.Column("industry", sa.String(), nullable=True),
            sa.Column("employeeCount", sa.Integer(), nullable=True),
            sa.Column("revenueRange", sa.String(), nullable=True),
            sa.Column("techStack", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("location", sa.String(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("payload", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("lastEnrichedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("domain", name="uq_DomainEnrichment_domain"),
            schema=schema,
        )
        op.create_index("ix_DomainEnrichment_domain", "DomainEnrichment", ["domain"], schema=schema)

    # ── SchedulerStatus (single-row, Integer PK) ───────────────────────────
    if not _table_exists(bind, schema, "SchedulerStatus"):
        op.create_table(
            "SchedulerStatus",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("lastTickAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("nextTickAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sentSinceLastTick", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skippedSinceLastTick", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("isRunning", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── RateLimit ──────────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "RateLimit"):
        op.create_table(
            "RateLimit",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("key", sa.String(), nullable=False, unique=True),
            sa.Column("label", sa.String(), nullable=False),
            sa.Column("platform", sa.String(), nullable=True),
            sa.Column("window", _enum(schema, "rate_limit_window"), nullable=False),
            sa.Column("limit", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("windowStart", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("throttleMode", sa.String(), nullable=False, server_default="'skip'"),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_RateLimit_platform", "RateLimit", ["platform"], schema=schema)
        op.create_index("ix_RateLimit_key", "RateLimit", ["key"], schema=schema)

    # ── ProspectingFlow ────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "ProspectingFlow"):
        op.create_table(
            "ProspectingFlow",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("isDefault", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("isTemplate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("templateTag", sa.String(), nullable=True),
            sa.Column("templateIcon", sa.String(), nullable=True),
            sa.Column("templateColor", sa.String(), nullable=True),
            sa.Column("sourceSteps", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("enrichmentSteps", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("qualityGates", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_ProspectingFlow_isDefault", "ProspectingFlow", ["isDefault"], schema=schema)
        op.create_index("ix_ProspectingFlow_isActive", "ProspectingFlow", ["isActive"], schema=schema)
        op.create_index("ix_ProspectingFlow_isTemplate", "ProspectingFlow", ["isTemplate"], schema=schema)

    # ── WeeklyDigest ───────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "WeeklyDigest"):
        op.create_table(
            "WeeklyDigest",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("weekStart", sa.DateTime(timezone=True), nullable=False),
            sa.Column("weekEnd", sa.DateTime(timezone=True), nullable=False),
            sa.Column("sentCount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("replyCount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("positiveReplyCount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("meetingCount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("bounceCount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("summary", sa.Text(), nullable=False, server_default="''"),
            sa.Column("highlights", sa.Text(), nullable=False, server_default="'[]'"),
            # Three spec-required JSON columns for metrics (audit-A1 M-35).
            # `highlights` above is one of the three; `topProspects` +
            # `campaignPerformance` round out the trio. Stored as TEXT-holding-
            # JSON strings (Phase 4+ may migrate to JSONB).
            sa.Column("topProspects", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("campaignPerformance", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("generatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_WeeklyDigest_weekStart", "WeeklyDigest", ["weekStart"], schema=schema)
    else:
        # Idempotent column additions for already-provisioned schemas.
        if not _column_exists(bind, schema, "WeeklyDigest", "topProspects"):
            op.add_column(
                "WeeklyDigest",
                sa.Column(
                    "topProspects", sa.Text(), nullable=False, server_default="'[]'"
                ),
                schema=schema,
            )
        if not _column_exists(bind, schema, "WeeklyDigest", "campaignPerformance"):
            op.add_column(
                "WeeklyDigest",
                sa.Column(
                    "campaignPerformance",
                    sa.Text(),
                    nullable=False,
                    server_default="'{}'",
                ),
                schema=schema,
            )

    # ════════════════════════════════════════════════════════════════════════
    # Tier 1 — FK to Tier 0 only
    # ════════════════════════════════════════════════════════════════════════

    # ── Prospect (FK → IcpProfile) ─────────────────────────────────────────
    if not _table_exists(bind, schema, "Prospect"):
        op.create_table(
            "Prospect",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("firstName", sa.String(), nullable=False),
            sa.Column("lastName", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("company", sa.String(), nullable=True),
            sa.Column("domain", sa.String(), nullable=True),
            sa.Column("linkedinUrl", sa.String(), nullable=True),
            sa.Column("seniority", _enum(schema, "seniority_tier"), nullable=False),
            sa.Column("signals", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("qaScore", sa.Integer(), nullable=True),
            sa.Column("emailValidated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("emailValidationDetail", sa.String(), nullable=True),
            sa.Column("emailConfidence", sa.Float(), nullable=True),
            sa.Column("isCatchAll", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("enrichmentTier", _enum(schema, "enrichment_tier"), nullable=False),
            sa.Column("intentSource", _enum(schema, "intent_source"), nullable=False),
            sa.Column("intentDetail", sa.String(), nullable=True),
            sa.Column("intentStrength", sa.Integer(), nullable=True),
            sa.Column("timezone", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="'new'"),
            sa.Column("suppressed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("suppressionReason", sa.String(), nullable=True),
            sa.Column("suppressedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("unsubscribeToken", sa.String(), nullable=True, unique=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("icpFitScore", sa.Integer(), nullable=True),
            sa.Column("icpPersona", sa.String(), nullable=True),
            sa.Column("icpScoreBreakdown", sa.Text(), nullable=True),
            sa.Column("ultimateProfile", sa.Text(), nullable=True),
            sa.Column("urgencyTier", sa.String(), nullable=True),
            sa.Column("urgencyDeadline", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "icpProfileId",
                sa.String(length=64),
                sa.ForeignKey("IcpProfile.id"),
                nullable=True,
            ),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── MailBridgeConfig (FK → Domain) ─────────────────────────────────────
    if not _table_exists(bind, schema, "MailBridgeConfig"):
        op.create_table(
            "MailBridgeConfig",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("baseUrl", sa.String(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False, server_default="'gmail'"),
            sa.Column("fromEmail", sa.String(), nullable=False),
            sa.Column("fromName", sa.String(), nullable=True),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("webhookSecret", sa.String(), nullable=True),
            sa.Column(
                "domainId",
                sa.String(length=64),
                sa.ForeignKey("Domain.id"),
                nullable=True,
            ),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ════════════════════════════════════════════════════════════════════════
    # Tier 2 — FK to Tier 0 + Tier 1
    # ════════════════════════════════════════════════════════════════════════

    # ── Campaign (FK → IcpProfile, LlmConfig, Domain) ──────────────────────
    if not _table_exists(bind, schema, "Campaign"):
        op.create_table(
            "Campaign",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="'draft'"),
            sa.Column("framework", sa.String(), nullable=True),
            sa.Column("senderRole", sa.String(), nullable=True),
            sa.Column("senderCompany", sa.String(), nullable=True),
            sa.Column("senderOffer", sa.String(), nullable=True),
            sa.Column("proofMetric", sa.String(), nullable=True),
            sa.Column("senderProduct", sa.String(), nullable=True),
            sa.Column("targetAudience", sa.String(), nullable=True),
            sa.Column("complianceFooter", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("unsubscribeUrl", sa.String(), nullable=True),
            sa.Column("physicalAddress", sa.String(), nullable=True),
            sa.Column("webhookUrl", sa.String(), nullable=True),
            sa.Column("brandVoiceProfile", sa.Text(), nullable=True),
            sa.Column(
                "icpProfileId",
                sa.String(length=64),
                sa.ForeignKey("IcpProfile.id"),
                nullable=True,
            ),
            sa.Column(
                "llmConfigId",
                sa.String(length=64),
                sa.ForeignKey("LlmConfig.id"),
                nullable=True,
            ),
            sa.Column(
                "domainId",
                sa.String(length=64),
                sa.ForeignKey("Domain.id"),
                nullable=True,
            ),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── FlowRun (FK → ProspectingFlow, IcpProfile) ─────────────────────────
    if not _table_exists(bind, schema, "FlowRun"):
        op.create_table(
            "FlowRun",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "flowId",
                sa.String(length=64),
                sa.ForeignKey("ProspectingFlow.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "icpProfileId",
                sa.String(length=64),
                sa.ForeignKey("IcpProfile.id"),
                nullable=False,
            ),
            sa.Column("status", _enum(schema, "flow_run_status"), nullable=False),
            sa.Column("triggeredBy", sa.String(), nullable=False, server_default="'manual'"),
            sa.Column("triggeredById", sa.String(), nullable=True),
            sa.Column("config", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("stats", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("importedProspectIds", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column("errorMessage", sa.String(), nullable=True),
            sa.Column("startedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_FlowRun_flowId", "FlowRun", ["flowId"], schema=schema)
        op.create_index("ix_FlowRun_icpProfileId", "FlowRun", ["icpProfileId"], schema=schema)
        op.create_index("ix_FlowRun_status", "FlowRun", ["status"], schema=schema)
        op.create_index("ix_FlowRun_triggeredBy", "FlowRun", ["triggeredBy"], schema=schema)

    # ════════════════════════════════════════════════════════════════════════
    # Tier 3 — FK to Tier 0-2
    # ════════════════════════════════════════════════════════════════════════

    # ── CampaignProspect (FK → Campaign, Prospect) ─────────────────────────
    if not _table_exists(bind, schema, "CampaignProspect"):
        op.create_table(
            "CampaignProspect",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "campaignId",
                sa.String(length=64),
                sa.ForeignKey("Campaign.id"),
                nullable=False,
            ),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=False,
            ),
            sa.Column("status", sa.String(), nullable=False, server_default="'pending'"),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "campaignId", "prospectId", name="uq_CampaignProspect_campaign_prospect"
            ),
            schema=schema,
        )

    # ── CampaignCollateralLink (FK → Collateral, Campaign) ─────────────────
    if not _table_exists(bind, schema, "CampaignCollateralLink"):
        op.create_table(
            "CampaignCollateralLink",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "collateralId",
                sa.String(length=64),
                sa.ForeignKey("Collateral.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "campaignId",
                sa.String(length=64),
                sa.ForeignKey("Campaign.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sortOrder", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "collateralId", "campaignId", name="uq_CampCollateral_collateral_campaign"
            ),
            schema=schema,
        )
        op.create_index(
            "ix_CampaignCollateralLink_campaignId",
            "CampaignCollateralLink",
            ["campaignId"],
            schema=schema,
        )

    # ── Sequence (FK → Campaign, Prospect) ─────────────────────────────────
    if not _table_exists(bind, schema, "Sequence"):
        op.create_table(
            "Sequence",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "campaignId",
                sa.String(length=64),
                sa.ForeignKey("Campaign.id"),
                nullable=False,
            ),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=False,
            ),
            sa.Column("touchNumber", sa.Integer(), nullable=False),
            sa.Column("sendDay", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(), nullable=False, server_default="'email'"),
            sa.Column("angle", _enum(schema, "touch_angle"), nullable=False),
            sa.Column("framework", sa.String(), nullable=True),
            sa.Column("subjectLine", sa.String(), nullable=True),
            sa.Column("bodyCopy", sa.Text(), nullable=True),
            sa.Column("qaScore", sa.Integer(), nullable=True),
            sa.Column("qaDetails", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("personalisationConfidence", sa.Float(), nullable=True),
            sa.Column("flagForManualReview", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("status", _enum(schema, "email_status"), nullable=False),
            sa.Column("sentAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("openedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("repliedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("bouncedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("mailBridgeMessageId", sa.String(), nullable=True),
            sa.Column("bounceReason", sa.String(), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index(
            "ix_Sequence_campaignId_prospectId",
            "Sequence",
            ["campaignId", "prospectId"],
            schema=schema,
        )

    # ── CampaignMetric (FK → Campaign) ─────────────────────────────────────
    if not _table_exists(bind, schema, "CampaignMetric"):
        op.create_table(
            "CampaignMetric",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "campaignId",
                sa.String(length=64),
                sa.ForeignKey("Campaign.id"),
                nullable=False,
            ),
            sa.Column("date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("totalSent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("totalOpened", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("totalReplied", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("totalBounced", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("openRate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("replyRate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("bounceRate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("diagnosticNote", sa.String(), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── CampaignResult (FK → Campaign, CASCADE) ────────────────────────────
    if not _table_exists(bind, schema, "CampaignResult"):
        op.create_table(
            "CampaignResult",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "campaignId",
                sa.String(length=64),
                sa.ForeignKey("Campaign.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("totalSent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("totalReplied", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("totalPositive", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("totalBounced", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("replyRate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("positiveReplyRate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("bounceRate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("whatWorked", sa.String(), nullable=True),
            sa.Column("whatDidntWork", sa.String(), nullable=True),
            sa.Column("nextActions", sa.String(), nullable=True),
            sa.Column("insights", sa.String(), nullable=True),
            sa.Column("generatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_CampaignResult_campaignId", "CampaignResult", ["campaignId"], schema=schema)

    # ── Deal (FK → Prospect, Campaign) ─────────────────────────────────────
    if not _table_exists(bind, schema, "Deal"):
        op.create_table(
            "Deal",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("value", sa.Float(), nullable=False, server_default="0"),
            sa.Column("stage", sa.String(), nullable=False, server_default="'qualified'"),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=True,
            ),
            sa.Column(
                "campaignId",
                sa.String(length=64),
                sa.ForeignKey("Campaign.id"),
                nullable=True,
            ),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("expectedClose", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source", sa.String(), nullable=False, server_default="'cold_email'"),
            sa.Column("healthStatus", sa.String(), nullable=True),
            sa.Column("healthReason", sa.String(), nullable=True),
            sa.Column("healthCheckedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── AbTest (FK → Campaign) ─────────────────────────────────────────────
    if not _table_exists(bind, schema, "AbTest"):
        op.create_table(
            "AbTest",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column(
                "campaignId",
                sa.String(length=64),
                sa.ForeignKey("Campaign.id"),
                nullable=False,
            ),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("element", sa.String(), nullable=False),
            sa.Column("variantALabel", sa.String(), nullable=False, server_default="'Variant A'"),
            sa.Column("variantBLabel", sa.String(), nullable=False, server_default="'Variant B'"),
            sa.Column("variantASubject", sa.String(), nullable=True),
            sa.Column("variantBSubject", sa.String(), nullable=True),
            sa.Column("variantABody", sa.Text(), nullable=True),
            sa.Column("variantBBody", sa.Text(), nullable=True),
            sa.Column("splitRatio", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("status", sa.String(), nullable=False, server_default="'draft'"),
            sa.Column("touchNumber", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("startedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("endedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_AbTest_campaignId", "AbTest", ["campaignId"], schema=schema)
        op.create_index("ix_AbTest_status", "AbTest", ["status"], schema=schema)

    # ── EmailAbTest (FK → Campaign, CASCADE) ───────────────────────────────
    if not _table_exists(bind, schema, "EmailAbTest"):
        op.create_table(
            "EmailAbTest",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "campaignId",
                sa.String(length=64),
                sa.ForeignKey("Campaign.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("subjectA", sa.String(), nullable=False),
            sa.Column("subjectB", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="'running'"),
            sa.Column("winner", sa.String(), nullable=True),
            sa.Column("startedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("completedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_EmailAbTest_campaignId", "EmailAbTest", ["campaignId"], schema=schema)

    # ── OptimizationRule (FK → Campaign, SET NULL) ─────────────────────────
    if not _table_exists(bind, schema, "OptimizationRule"):
        op.create_table(
            "OptimizationRule",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("metric", sa.String(), nullable=False),
            sa.Column("operator", sa.String(), nullable=False),
            sa.Column("threshold", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "campaignId",
                sa.String(length=64),
                sa.ForeignKey("Campaign.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("lastEvaluatedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_OptimizationRule_isActive", "OptimizationRule", ["isActive"], schema=schema)
        op.create_index(
            "ix_OptimizationRule_campaignId", "OptimizationRule", ["campaignId"], schema=schema
        )

    # ── Competitor (FK → Prospect) ─────────────────────────────────────────
    if not _table_exists(bind, schema, "Competitor"):
        op.create_table(
            "Competitor",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=True,
            ),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("domain", sa.String(), nullable=True),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("positioning", sa.String(), nullable=True),
            sa.Column("overlapScore", sa.Float(), nullable=True),
            sa.Column("source", sa.String(), nullable=False, server_default="'auto'"),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── CallLog (FK → Prospect) ────────────────────────────────────────────
    if not _table_exists(bind, schema, "CallLog"):
        op.create_table(
            "CallLog",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=False,
            ),
            sa.Column("phone", sa.String(), nullable=False),
            sa.Column("outcome", sa.String(), nullable=False, server_default="'pending'"),
            sa.Column("durationSec", sa.Integer(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("calledAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── JobChangeAlert (FK → Prospect, IcpProfile) ─────────────────────────
    if not _table_exists(bind, schema, "JobChangeAlert"):
        op.create_table(
            "JobChangeAlert",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=False,
            ),
            sa.Column("previousCompany", sa.String(), nullable=True),
            sa.Column("previousTitle", sa.String(), nullable=True),
            sa.Column("newCompany", sa.String(), nullable=False),
            sa.Column("newTitle", sa.String(), nullable=True),
            sa.Column("newDomain", sa.String(), nullable=True),
            sa.Column("newLinkedinUrl", sa.String(), nullable=True),
            sa.Column("detectedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column(
                "icpProfileId",
                sa.String(length=64),
                sa.ForeignKey("IcpProfile.id"),
                nullable=True,
            ),
            sa.Column("icpFitScore", sa.Float(), nullable=True),
            sa.Column("icpPersona", sa.String(), nullable=True),
            sa.Column("matchReason", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="'new'"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("scanSource", sa.String(), nullable=False, server_default="'manual'"),
            sa.Column("lastScannedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_JobChangeAlert_prospectId", "JobChangeAlert", ["prospectId"], schema=schema)
        op.create_index("ix_JobChangeAlert_status", "JobChangeAlert", ["status"], schema=schema)

    # ── MeetingPrep (FK → Prospect) ────────────────────────────────────────
    if not _table_exists(bind, schema, "MeetingPrep"):
        op.create_table(
            "MeetingPrep",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=False,
            ),
            sa.Column("callType", sa.String(), nullable=False),
            sa.Column("brief", sa.Text(), nullable=False),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_MeetingPrep_prospectId", "MeetingPrep", ["prospectId"], schema=schema)

    # ── LinkedInEngagement (FK → Prospect, IcpProfile) ─────────────────────
    if not _table_exists(bind, schema, "LinkedInEngagement"):
        op.create_table(
            "LinkedInEngagement",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=True,
            ),
            sa.Column(
                "icpProfileId",
                sa.String(length=64),
                sa.ForeignKey("IcpProfile.id"),
                nullable=True,
            ),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="'pending'"),
            sa.Column("scheduledAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("executedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index(
            "ix_LinkedInEngagement_prospectId", "LinkedInEngagement", ["prospectId"], schema=schema
        )
        op.create_index(
            "ix_LinkedInEngagement_icpProfileId",
            "LinkedInEngagement",
            ["icpProfileId"],
            schema=schema,
        )

    # ── LinkedInInboxMessage (FK → Prospect) ───────────────────────────────
    if not _table_exists(bind, schema, "LinkedInInboxMessage"):
        op.create_table(
            "LinkedInInboxMessage",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=True,
            ),
            sa.Column("senderName", sa.String(), nullable=False),
            sa.Column("senderHandle", sa.String(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="'unread'"),
            sa.Column("receivedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("triagedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index(
            "ix_LinkedInInboxMessage_prospectId",
            "LinkedInInboxMessage",
            ["prospectId"],
            schema=schema,
        )
        op.create_index(
            "ix_LinkedInInboxMessage_status", "LinkedInInboxMessage", ["status"], schema=schema
        )

    # ── ProspectSource (FK → Prospect, CASCADE) ────────────────────────────
    if not _table_exists(bind, schema, "ProspectSource"):
        op.create_table(
            "ProspectSource",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("query", sa.String(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("rawPayload", sa.Text(), nullable=True),
            sa.Column("importedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_ProspectSource_prospectId", "ProspectSource", ["prospectId"], schema=schema)
        op.create_index("ix_ProspectSource_source", "ProspectSource", ["source"], schema=schema)

    # ── Signal (FK → Prospect, SET NULL) ───────────────────────────────────
    if not _table_exists(bind, schema, "Signal"):
        op.create_table(
            "Signal",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("summary", sa.String(), nullable=False),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("source", sa.String(), nullable=False, server_default="'auto'"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("detectedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_Signal_prospectId", "Signal", ["prospectId"], schema=schema)
        op.create_index("ix_Signal_type", "Signal", ["type"], schema=schema)
        op.create_index("ix_Signal_detectedAt", "Signal", ["detectedAt"], schema=schema)

    # ── FlowRunStep (FK → FlowRun, CASCADE) ────────────────────────────────
    if not _table_exists(bind, schema, "FlowRunStep"):
        op.create_table(
            "FlowRunStep",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "runId",
                sa.String(length=64),
                sa.ForeignKey("FlowRun.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("kind", _enum(schema, "flow_run_step_kind"), nullable=False),
            sa.Column("stepKey", sa.String(), nullable=False),
            sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", _enum(schema, "flow_run_step_status"), nullable=False),
            sa.Column("metrics", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("durationMs", sa.Integer(), nullable=True),
            sa.Column("errorMessage", sa.String(), nullable=True),
            sa.Column("startedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_FlowRunStep_runId", "FlowRunStep", ["runId"], schema=schema)
        op.create_index("ix_FlowRunStep_kind", "FlowRunStep", ["kind"], schema=schema)

    # ── FlowAbTest (FK → ProspectingFlow x2, IcpProfile) ───────────────────
    if not _table_exists(bind, schema, "FlowAbTest"):
        op.create_table(
            "FlowAbTest",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column(
                "icpProfileId",
                sa.String(length=64),
                sa.ForeignKey("IcpProfile.id"),
                nullable=False,
            ),
            sa.Column(
                "flowAId",
                sa.String(length=64),
                sa.ForeignKey("ProspectingFlow.id"),
                nullable=False,
            ),
            sa.Column(
                "flowBId",
                sa.String(length=64),
                sa.ForeignKey("ProspectingFlow.id"),
                nullable=False,
            ),
            sa.Column("status", _enum(schema, "flow_ab_test_status"), nullable=False),
            sa.Column("significance", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("summary", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("startedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_FlowAbTest_icpProfileId", "FlowAbTest", ["icpProfileId"], schema=schema)
        op.create_index("ix_FlowAbTest_status", "FlowAbTest", ["status"], schema=schema)

    # ── FlowWebhook (FK → ProspectingFlow, SET NULL) ───────────────────────
    if not _table_exists(bind, schema, "FlowWebhook"):
        op.create_table(
            "FlowWebhook",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("url", sa.String(), nullable=False),
            sa.Column("secret", sa.String(), nullable=True),
            sa.Column("events", sa.Text(), nullable=False, server_default="'[]'"),
            sa.Column(
                "flowId",
                sa.String(length=64),
                sa.ForeignKey("ProspectingFlow.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("config", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_FlowWebhook_flowId", "FlowWebhook", ["flowId"], schema=schema)
        op.create_index("ix_FlowWebhook_isActive", "FlowWebhook", ["isActive"], schema=schema)

    # ── AutopilotQueue (FK → ProspectingFlow CASCADE, IcpProfile, FlowRun) ─
    if not _table_exists(bind, schema, "AutopilotQueue"):
        op.create_table(
            "AutopilotQueue",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "flowId",
                sa.String(length=64),
                sa.ForeignKey("ProspectingFlow.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "icpProfileId",
                sa.String(length=64),
                sa.ForeignKey("IcpProfile.id"),
                nullable=False,
            ),
            sa.Column("status", _enum(schema, "autopilot_queue_status"), nullable=False),
            sa.Column("origin", sa.String(), nullable=False, server_default="'manual'"),
            sa.Column("config", sa.Text(), nullable=False, server_default="'{}'"),
            sa.Column(
                "flowRunId",
                sa.String(length=64),
                sa.ForeignKey("FlowRun.id"),
                nullable=True,
            ),
            sa.Column("errorMessage", sa.String(), nullable=True),
            sa.Column("queuedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("pickedUpAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_AutopilotQueue_status", "AutopilotQueue", ["status"], schema=schema)
        op.create_index("ix_AutopilotQueue_flowId", "AutopilotQueue", ["flowId"], schema=schema)
        op.create_index(
            "ix_AutopilotQueue_icpProfileId", "AutopilotQueue", ["icpProfileId"], schema=schema
        )

    # ── RateLimitLog (FK → FlowRun) ────────────────────────────────────────
    if not _table_exists(bind, schema, "RateLimitLog"):
        op.create_table(
            "RateLimitLog",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("platform", sa.String(), nullable=True),
            sa.Column("outcome", sa.String(), nullable=False),
            sa.Column(
                "flowRunId",
                sa.String(length=64),
                sa.ForeignKey("FlowRun.id"),
                nullable=True,
            ),
            sa.Column("detail", sa.String(), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_RateLimitLog_key", "RateLimitLog", ["key"], schema=schema)
        op.create_index("ix_RateLimitLog_platform", "RateLimitLog", ["platform"], schema=schema)
        op.create_index("ix_RateLimitLog_createdAt", "RateLimitLog", ["createdAt"], schema=schema)
        op.create_index("ix_RateLimitLog_flowRunId", "RateLimitLog", ["flowRunId"], schema=schema)

    # ════════════════════════════════════════════════════════════════════════
    # Tier 4 — FK to Tier 0-3
    # ════════════════════════════════════════════════════════════════════════

    # ── SubjectLine (FK → Sequence) ────────────────────────────────────────
    if not _table_exists(bind, schema, "SubjectLine"):
        op.create_table(
            "SubjectLine",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "sequenceId",
                sa.String(length=64),
                sa.ForeignKey("Sequence.id"),
                nullable=False,
            ),
            sa.Column("variant", sa.String(), nullable=False),
            sa.Column("isSelected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── ReplyDraft (FK → Sequence, Prospect) ───────────────────────────────
    if not _table_exists(bind, schema, "ReplyDraft"):
        op.create_table(
            "ReplyDraft",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "sequenceId",
                sa.String(length=64),
                sa.ForeignKey("Sequence.id"),
                nullable=False,
            ),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=False,
            ),
            sa.Column("originalReply", sa.Text(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("summary", sa.String(), nullable=True),
            sa.Column("suggestedAction", sa.String(), nullable=True),
            sa.Column("draftBody", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="'pending'"),
            sa.Column("sentAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("autoPilotEligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("autoSentAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("meetingProposedTime", sa.DateTime(timezone=True), nullable=True),
            sa.Column("meetingBookedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("meetingCalendarLink", sa.String(), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    # ── AbTestAssignment (FK → AbTest, Prospect, Sequence) ─────────────────
    if not _table_exists(bind, schema, "AbTestAssignment"):
        op.create_table(
            "AbTestAssignment",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "abTestId",
                sa.String(length=64),
                sa.ForeignKey("AbTest.id"),
                nullable=False,
            ),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=False,
            ),
            sa.Column("variant", sa.String(), nullable=False),
            sa.Column(
                "sequenceId",
                sa.String(length=64),
                sa.ForeignKey("Sequence.id"),
                nullable=True,
            ),
            sa.Column("sentAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("openedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("repliedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("bouncedAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("replyCategory", sa.String(), nullable=True),
            sa.Column("isPositiveReply", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "abTestId", "prospectId", name="uq_AbTestAssignment_test_prospect"
            ),
            schema=schema,
        )
        op.create_index(
            "ix_AbTestAssignment_abTestId_variant",
            "AbTestAssignment",
            ["abTestId", "variant"],
            schema=schema,
        )

    # ── OptimizationAction (FK → OptimizationRule CASCADE, Campaign) ───────
    if not _table_exists(bind, schema, "OptimizationAction"):
        op.create_table(
            "OptimizationAction",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "ruleId",
                sa.String(length=64),
                sa.ForeignKey("OptimizationRule.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "campaignId",
                sa.String(length=64),
                sa.ForeignKey("Campaign.id"),
                nullable=True,
            ),
            sa.Column("metric", sa.String(), nullable=False),
            sa.Column("observedValue", sa.Float(), nullable=False),
            sa.Column("threshold", sa.Float(), nullable=False),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("result", sa.String(), nullable=True),
            sa.Column("executedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index(
            "ix_OptimizationAction_ruleId", "OptimizationAction", ["ruleId"], schema=schema
        )
        op.create_index(
            "ix_OptimizationAction_campaignId",
            "OptimizationAction",
            ["campaignId"],
            schema=schema,
        )

    # ── Meeting (FK → Prospect, MeetingPrep) ───────────────────────────────
    if not _table_exists(bind, schema, "Meeting"):
        op.create_table(
            "Meeting",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("scheduledAt", sa.DateTime(timezone=True), nullable=False),
            sa.Column("durationMin", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("meetingUrl", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="'scheduled'"),
            sa.Column(
                "prospectId",
                sa.String(length=64),
                sa.ForeignKey("Prospect.id"),
                nullable=True,
            ),
            sa.Column(
                "meetingPrepId",
                sa.String(length=64),
                sa.ForeignKey("MeetingPrep.id"),
                nullable=True,
            ),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_Meeting_scheduledAt", "Meeting", ["scheduledAt"], schema=schema)
        op.create_index("ix_Meeting_prospectId", "Meeting", ["prospectId"], schema=schema)

    # ── ContentIdea (FK → IcpProfile) ──────────────────────────────────────
    if not _table_exists(bind, schema, "ContentIdea"):
        op.create_table(
            "ContentIdea",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "icpProfileId",
                sa.String(length=64),
                sa.ForeignKey("IcpProfile.id"),
                nullable=True,
            ),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("angle", sa.String(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="'draft'"),
            sa.Column("isFavorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("generatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index("ix_ContentIdea_icpProfileId", "ContentIdea", ["icpProfileId"], schema=schema)

    # ── FlowWebhookDelivery (FK → FlowWebhook CASCADE) ─────────────────────
    if not _table_exists(bind, schema, "FlowWebhookDelivery"):
        op.create_table(
            "FlowWebhookDelivery",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "webhookId",
                sa.String(length=64),
                sa.ForeignKey("FlowWebhook.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event", _enum(schema, "webhook_trigger_event"), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("statusCode", sa.Integer(), nullable=True),
            sa.Column("response", sa.Text(), nullable=True),
            sa.Column("status", _enum(schema, "webhook_delivery_status"), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("deliveredAt", sa.DateTime(timezone=True), nullable=True),
            sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
        op.create_index(
            "ix_FlowWebhookDelivery_webhookId",
            "FlowWebhookDelivery",
            ["webhookId"],
            schema=schema,
        )
        op.create_index(
            "ix_FlowWebhookDelivery_status", "FlowWebhookDelivery", ["status"], schema=schema
        )


def downgrade() -> None:
    """Drop all tenant-scoped tables + enum types in reverse dependency order.

    Public schema is a no-op (its tables are owned by 0001_initial_public.py).
    """
    schema = _s()
    if schema == "public":
        return

    bind = op.get_bind()

    # ── Drop tables in reverse dependency order ────────────────────────────
    _tenant_tables_reversed = (
        # Tier 4
        "FlowWebhookDelivery", "ContentIdea", "Meeting", "OptimizationAction",
        "AbTestAssignment", "ReplyDraft", "SubjectLine",
        # Tier 3
        "RateLimitLog", "AutopilotQueue", "FlowWebhook", "FlowAbTest",
        "FlowRunStep", "Signal", "ProspectSource", "LinkedInInboxMessage",
        "LinkedInEngagement", "MeetingPrep", "JobChangeAlert", "CallLog",
        "Competitor", "OptimizationRule", "EmailAbTest", "AbTest", "Deal",
        "CampaignResult", "CampaignMetric", "Sequence",
        "CampaignCollateralLink", "CampaignProspect",
        # Tier 2
        "FlowRun", "Campaign",
        # Tier 1
        "MailBridgeConfig", "Prospect",
        # Tier 0
        "WeeklyDigest", "ProspectingFlow", "RateLimit", "SchedulerStatus",
        "DomainEnrichment", "SignalMonitor", "SourceConfig", "EmailTemplate",
        "LinkedInConfig", "Collateral", "ExclusionRule",
        "ProspectingIntegration", "SystemParameter", "PromptTemplate",
        "Domain", "IcpProfile", "LlmConfig",
    )
    for table_name in _tenant_tables_reversed:
        if _table_exists(bind, schema, table_name):
            op.drop_table(table_name, schema=schema)

    # ── Drop enum types (reverse creation order) ───────────────────────────
    _tenant_enums = (
        "rate_limit_window",
        "autopilot_queue_status",
        "webhook_delivery_status",
        "webhook_trigger_event",
        "flow_ab_test_status",
        "flow_run_step_status",
        "flow_run_step_kind",
        "flow_run_status",
        "email_status",
        "touch_angle",
        "enrichment_tier",
        "intent_source",
        "seniority_tier",
    )
    for enum_name in _tenant_enums:
        if _type_exists(bind, schema, enum_name):
            bind.execute(text(f'DROP TYPE {schema}."{enum_name}"'))
