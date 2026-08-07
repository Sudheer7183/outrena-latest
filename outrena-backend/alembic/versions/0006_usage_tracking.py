"""Usage tracking + per-user cost (Phase 8 — SAAS2-OBS-BE).

Revision ID: 0006
Revises: 0005
Create Date: 2025-01-20 00:00:00

This migration branches on schema (same pattern as 0002 + 0003):

  PUBLIC schema  → creates ``public.cost_config`` (key-value table for
    per-(event_type, provider, model) cost overrides) and seeds it with
    the hardcoded defaults from CostService.DEFAULT_COST_TABLE.

  tenant_{slug} schema → creates the tenant-scoped usage tables:
    - ``usage_events``    — the raw event log (one row per billable action)
    - ``cost_summaries``  — materialized daily/monthly roll-up

Both branches are import-safe (no app imports that require a DB).

Revision ID is ``0006`` and ``down_revision = "0005"`` per the task spec
(SAAS2-OBS-BE). Revisions 0004 + 0005 are owned by sibling tasks BE-A +
BE-B and are assumed to have been applied first; if they have not, this
migration will fail at the alembic version-chain check (intentional —
alembic refuses to skip revisions).
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

# ── revision identifiers ────────────────────────────────────────────────────
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── §4.6 hard-rule helpers (mirror 0002_initial_tenant.py conventions) ──────


def _s() -> str:
    """Return the active schema for this migration step.

    Reads ``context.get_context().version_table_schema`` (NOT ``os.environ``)
    because ``env.py`` iterates schemas within one process and env vars
    are not re-set per schema. Defaults to ``"public"`` if no context
    is active (e.g., offline mode or unit tests).
    """
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return getattr(ctx, "version_table_schema", None) or "public"


def _table_exists(bind, schema: str, name: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name"
        ),
        {"schema": schema, "name": name},
    )
    return result.fetchone() is not None


def _index_exists(bind, schema: str, table: str, index: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = :schema AND tablename = :table AND indexname = :index"
        ),
        {"schema": schema, "table": table, "index": index},
    )
    return result.fetchone() is not None


def _json_dumps(value: object) -> str:
    """Serialize to a JSON string for the CAST(:x AS jsonb) bind param."""
    return json.dumps(value, default=str)


# ── Seed data — mirrors CostService.DEFAULT_COST_TABLE (subset; the rest ──
#    are picked up at runtime from the Python defaults). Only the most
#    commonly-used providers/models are seeded here so the table has
#    immediate value; the SUPER_ADMIN endpoint can add the rest.
# ──────────────────────────────────────────────────────────────────────────
_SEED_COST_CONFIG: list[dict[str, object]] = [
    # LLM (event_type=llm_call, model set, cost_per_unit_cents = input rate,
    # output rate stored in extra JSON)
    {"event_type": "llm_call", "provider": "openai", "model": "gpt-4o",
     "cost_per_unit_cents": 2.5, "unit": "tokens_input",
     "extra": {"output_cents_per_1k": 10.0}},
    {"event_type": "llm_call", "provider": "openai", "model": "gpt-4o-mini",
     "cost_per_unit_cents": 0.15, "unit": "tokens_input",
     "extra": {"output_cents_per_1k": 0.6}},
    {"event_type": "llm_call", "provider": "anthropic", "model": "claude-3-5-sonnet",
     "cost_per_unit_cents": 3.0, "unit": "tokens_input",
     "extra": {"output_cents_per_1k": 15.0}},
    {"event_type": "llm_call", "provider": "anthropic", "model": "claude-3-5-haiku",
     "cost_per_unit_cents": 0.8, "unit": "tokens_input",
     "extra": {"output_cents_per_1k": 4.0}},
    {"event_type": "llm_call", "provider": "google", "model": "gemini-1.5-pro",
     "cost_per_unit_cents": 1.25, "unit": "tokens_input",
     "extra": {"output_cents_per_1k": 5.0}},
    {"event_type": "llm_call", "provider": "google", "model": "gemini-1.5-flash",
     "cost_per_unit_cents": 0.075, "unit": "tokens_input",
     "extra": {"output_cents_per_1k": 0.3}},
    {"event_type": "llm_call", "provider": "zai", "model": "glm-4-flash",
     "cost_per_unit_cents": 0.0, "unit": "tokens_input",
     "extra": {"output_cents_per_1k": 0.0}},
    {"event_type": "llm_call", "provider": "zai", "model": "glm-4",
     "cost_per_unit_cents": 0.7, "unit": "tokens_input",
     "extra": {"output_cents_per_1k": 0.7}},
    # Enrichment (event_type=prospect_enrich, model NULL)
    {"event_type": "prospect_enrich", "provider": "apollo", "model": None,
     "cost_per_unit_cents": 5.0, "unit": "calls", "extra": None},
    {"event_type": "prospect_enrich", "provider": "zoominfo", "model": None,
     "cost_per_unit_cents": 8.0, "unit": "calls", "extra": None},
    {"event_type": "prospect_enrich", "provider": "clearbit", "model": None,
     "cost_per_unit_cents": 3.0, "unit": "calls", "extra": None},
    {"event_type": "prospect_enrich", "provider": "hunter", "model": None,
     "cost_per_unit_cents": 2.0, "unit": "calls", "extra": None},
    {"event_type": "prospect_enrich", "provider": "lusha", "model": None,
     "cost_per_unit_cents": 6.0, "unit": "calls", "extra": None},
    {"event_type": "prospect_enrich", "provider": "snov", "model": None,
     "cost_per_unit_cents": 2.5, "unit": "calls", "extra": None},
    # LinkedIn (event_type=linkedin_action, model NULL, provider = action name)
    {"event_type": "linkedin_action", "provider": "action", "model": None,
     "cost_per_unit_cents": 2.0, "unit": "actions", "extra": None},
]


# ── upgrade / downgrade ─────────────────────────────────────────────────────


def upgrade() -> None:
    schema = _s()
    if schema == "public":
        _upgrade_public()
    else:
        _upgrade_tenant(schema)


def downgrade() -> None:
    schema = _s()
    if schema == "public":
        _downgrade_public()
    else:
        _downgrade_tenant(schema)


# ── PUBLIC schema upgrade ────────────────────────────────────────────────────


def _upgrade_public() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "public", "cost_config"):
        op.create_table(
            "cost_config",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False),
            sa.Column("model", sa.String(length=120), nullable=True),
            sa.Column(
                "cost_per_unit_cents",
                sa.Numeric(precision=12, scale=4),
                nullable=False,
                server_default="0",
            ),
            sa.Column("unit", sa.String(length=20), nullable=False, server_default="count"),
            sa.Column(
                "extra",
                sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "event_type",
                "provider",
                "model",
                name="uq_cost_config_event_provider_model",
            ),
            schema="public",
        )
        op.create_index(
            "ix_cost_config_event_type",
            "cost_config",
            ["event_type"],
            schema="public",
        )
        op.create_index(
            "ix_cost_config_provider",
            "cost_config",
            ["provider"],
            schema="public",
        )

    # Seed default rows (idempotent — ON CONFLICT DO NOTHING).
    for row in _SEED_COST_CONFIG:
        bind.execute(
            text(
                "INSERT INTO public.cost_config "
                "(event_type, provider, model, cost_per_unit_cents, unit, extra) "
                "VALUES (:et, :p, :m, :c, :u, CAST(:x AS jsonb)) "
                "ON CONFLICT (event_type, provider, model) DO NOTHING"
            ),
            {
                "et": row["event_type"],
                "p": row["provider"],
                "m": row["model"],
                "c": row["cost_per_unit_cents"],
                "u": row["unit"],
                "x": _json_dumps(row["extra"] or {}),
            },
        )


def _downgrade_public() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "public", "cost_config", "ix_cost_config_provider"):
        op.execute("DROP INDEX IF EXISTS public.ix_cost_config_provider")
    if _index_exists(bind, "public", "cost_config", "ix_cost_config_event_type"):
        op.execute("DROP INDEX IF EXISTS public.ix_cost_config_event_type")
    if _table_exists(bind, "public", "cost_config"):
        op.drop_table("cost_config", schema="public")


# ── TENANT schema upgrade ────────────────────────────────────────────────────


def _upgrade_tenant(schema: str) -> None:
    bind = op.get_bind()

    # ── usage_events ──────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "usage_events"):
        op.create_table(
            "usage_events",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(length=128), nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=True),
            sa.Column("resource", sa.String(length=120), nullable=True),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("unit", sa.String(length=20), nullable=False, server_default="count"),
            sa.Column(
                "metadata",
                sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("cost_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "occurred_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )

    if not _index_exists(bind, schema, "usage_events", "ix_usage_events_user_occurred"):
        op.create_index(
            "ix_usage_events_user_occurred",
            "usage_events",
            ["user_id", "occurred_at"],
            schema=schema,
        )
    if not _index_exists(bind, schema, "usage_events", "ix_usage_events_type_occurred"):
        op.create_index(
            "ix_usage_events_type_occurred",
            "usage_events",
            ["event_type", "occurred_at"],
            schema=schema,
        )
    if not _index_exists(bind, schema, "usage_events", "ix_usage_events_occurred"):
        op.create_index(
            "ix_usage_events_occurred",
            "usage_events",
            ["occurred_at"],
            schema=schema,
        )

    # ── cost_summaries ────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "cost_summaries"):
        op.create_table(
            "cost_summaries",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(length=128), nullable=True),
            sa.Column("period", sa.String(length=20), nullable=False),
            sa.Column("period_type", sa.String(length=10), nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=True),
            sa.Column(
                "total_quantity", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "total_cost_cents", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "event_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "period",
                "period_type",
                "event_type",
                "provider",
                name="uq_cost_summaries_user_period_type_provider",
            ),
            schema=schema,
        )

    if not _index_exists(bind, schema, "cost_summaries", "ix_cost_summaries_period"):
        op.create_index(
            "ix_cost_summaries_period",
            "cost_summaries",
            ["period"],
            schema=schema,
        )
    if not _index_exists(
        bind, schema, "cost_summaries", "ix_cost_summaries_user_period"
    ):
        op.create_index(
            "ix_cost_summaries_user_period",
            "cost_summaries",
            ["user_id", "period"],
            schema=schema,
        )


def _downgrade_tenant(schema: str) -> None:
    bind = op.get_bind()
    # Drop indexes first (FK-free tables, but indexes are dependencies of
    # the table itself only in the implicit sense — explicit drop avoids
    # any CASCADE ambiguity).
    if _index_exists(
        bind, schema, "cost_summaries", "ix_cost_summaries_user_period"
    ):
        op.execute(
            f'DROP INDEX IF EXISTS "{schema}".ix_cost_summaries_user_period'
        )
    if _index_exists(bind, schema, "cost_summaries", "ix_cost_summaries_period"):
        op.execute(f'DROP INDEX IF EXISTS "{schema}".ix_cost_summaries_period')
    if _table_exists(bind, schema, "cost_summaries"):
        op.drop_table("cost_summaries", schema=schema)

    if _index_exists(bind, schema, "usage_events", "ix_usage_events_occurred"):
        op.execute(f'DROP INDEX IF EXISTS "{schema}".ix_usage_events_occurred')
    if _index_exists(bind, schema, "usage_events", "ix_usage_events_type_occurred"):
        op.execute(
            f'DROP INDEX IF EXISTS "{schema}".ix_usage_events_type_occurred'
        )
    if _index_exists(bind, schema, "usage_events", "ix_usage_events_user_occurred"):
        op.execute(
            f'DROP INDEX IF EXISTS "{schema}".ix_usage_events_user_occurred'
        )
    if _table_exists(bind, schema, "usage_events"):
        op.drop_table("usage_events", schema=schema)


__all__ = ["upgrade", "downgrade"]
