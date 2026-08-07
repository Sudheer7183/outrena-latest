"""Dual-path integrations + global LLM config (Phase 8).

Revision ID: 0004
Revises: 0003
Create Date: 2025-01-04 00:00:00

This migration branches on schema (same pattern as 0002 + 0003):

  PUBLIC schema:
    - CREATE public.global_llm_config (the platform-wide LLM provider
      config table — replaces per-tenant LlmConfig as the PRIMARY source
      of API keys).
    - ALTER public.tenant_config ADD COLUMN integration_mode VARCHAR(32)
      NOT NULL DEFAULT 'tenant_managed'.
    - ALTER public.tenant_signup_requests ADD COLUMN integration_mode
      VARCHAR(32) NOT NULL DEFAULT 'tenant_managed'.
    - ALTER public.subscriptions ADD COLUMN integration_mode VARCHAR(32)
      NOT NULL DEFAULT 'tenant_managed'.
    - ALTER public.subscriptions ADD COLUMN effective_price_cents INTEGER.
    - UPDATE public.plans SET feature_flags = jsonb_set(...) to add the
      "integration_path_pricing" sub-key to each plan's feature_flags.

  tenant_{slug} schema:
    - ALTER "ProspectingIntegration" ADD COLUMN key_source VARCHAR(32)
      NOT NULL DEFAULT 'tenant'.
    - ALTER "ProspectingIntegration" ADD COLUMN api_key_encrypted TEXT NULL.
    - Back-fill: copy existing "apiKey" values to api_key_encrypted (as
      plaintext for now — the service re-encrypts on next UPDATE). The
      legacy "apiKey" column is left intact for backward-compat reads.
    - ALTER "MailBridgeConfig" ADD COLUMN owner_user_id VARCHAR(128) NULL.
    - ALTER "LlmConfig" ADD COLUMN global_llm_config_id INTEGER NULL
      (FK to public.global_llm_config.id).

Both branches are import-safe: no app imports that require a DB.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

# ── revision identifiers ────────────────────────────────────────────────────
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers (mirror 0003 conventions) ────────────────────────────────────────


def _s() -> str:
    """Return the active schema for this migration step."""
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


def _column_exists(bind, schema: str, table: str, column: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table "
            "AND column_name = :column"
        ),
        {"schema": schema, "table": table, "column": column},
    )
    return result.fetchone() is not None


def _json_dumps(value) -> str:  # type: ignore[no-untyped-def]
    import json
    return json.dumps(value, default=str)


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

    # ── public.global_llm_config ────────────────────────────────────────────
    if not _table_exists(bind, "public", "global_llm_config"):
        op.create_table(
            "global_llm_config",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("api_key_encrypted", sa.String(), nullable=False),
            sa.Column("base_url", sa.String(length=500), nullable=True),
            sa.Column("model_name", sa.String(length=120), nullable=False),
            sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="2048"),
            sa.Column(
                "temperature", sa.Float(),
                nullable=False, server_default="0.7",
            ),
            sa.Column(
                "is_active", sa.Boolean(),
                nullable=False, server_default=sa.text("true"),
            ),
            sa.Column(
                "is_default", sa.Boolean(),
                nullable=False, server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            schema="public",
        )
        op.create_index(
            "ix_global_llm_config_provider",
            "global_llm_config", ["provider"], schema="public",
        )
        op.create_index(
            "ix_global_llm_config_is_default_is_active",
            "global_llm_config", ["is_default", "is_active"], schema="public",
        )

    # ── ALTER public.tenant_config ADD COLUMN integration_mode ──────────────
    if not _column_exists(bind, "public", "tenant_config", "integration_mode"):
        op.execute(
            "ALTER TABLE public.tenant_config "
            "ADD COLUMN integration_mode VARCHAR(32) NOT NULL "
            "DEFAULT 'tenant_managed'"
        )
        op.execute(
            "ALTER TABLE public.tenant_config "
            "ADD CONSTRAINT tenant_config_integration_mode_check "
            "CHECK (integration_mode IN ('platform_managed', 'tenant_managed'))"
        )

    # ── ALTER public.tenant_signup_requests ADD COLUMN integration_mode ─────
    if not _column_exists(
        bind, "public", "tenant_signup_requests", "integration_mode"
    ):
        op.execute(
            "ALTER TABLE public.tenant_signup_requests "
            "ADD COLUMN integration_mode VARCHAR(32) NOT NULL "
            "DEFAULT 'tenant_managed'"
        )
        op.execute(
            "ALTER TABLE public.tenant_signup_requests "
            "ADD CONSTRAINT tenant_signup_requests_integration_mode_check "
            "CHECK (integration_mode IN ('platform_managed', 'tenant_managed'))"
        )

    # ── ALTER public.subscriptions ADD COLUMN integration_mode + effective_price_cents
    if not _column_exists(bind, "public", "subscriptions", "integration_mode"):
        op.execute(
            "ALTER TABLE public.subscriptions "
            "ADD COLUMN integration_mode VARCHAR(32) NOT NULL "
            "DEFAULT 'tenant_managed'"
        )
        op.execute(
            "ALTER TABLE public.subscriptions "
            "ADD CONSTRAINT subscriptions_integration_mode_check "
            "CHECK (integration_mode IN ('platform_managed', 'tenant_managed'))"
        )
    if not _column_exists(
        bind, "public", "subscriptions", "effective_price_cents"
    ):
        op.execute(
            "ALTER TABLE public.subscriptions "
            "ADD COLUMN effective_price_cents INTEGER"
        )

    # ── UPDATE public.plans: add integration_path_pricing to feature_flags ──
    # Example: platform-managed adds +$49/mo (4900 cents) to any plan,
    # tenant-managed adds $0. jsonb_set inserts the sub-key into each
    # plan's existing feature_flags without touching the other keys.
    # Backward-compatible: plans seeded before this migration continue to
    # work — billing_service._path_pricing_delta defaults to 0 when the
    # key is absent.
    _seed_plan_integration_path_pricing(bind)


def _seed_plan_integration_path_pricing(bind) -> None:
    """Add ``integration_path_pricing`` sub-key to every plan's feature_flags.

    Idempotent: re-running the migration does NOT overwrite a manually-set
    delta (the jsonb_set only runs when the key is absent).
    """
    rows = bind.execute(
        text(
            "SELECT name, feature_flags FROM public.plans "
            "WHERE NOT (feature_flags ? 'integration_path_pricing')"
        )
    ).fetchall()
    for row in rows:
        # +$49/mo for platform-managed (4900 cents), $0 for tenant-managed.
        new_flags = {
            "integration_path_pricing": {
                "platform_managed_delta_cents": 4900,
                "tenant_managed_delta_cents": 0,
            }
        }
        bind.execute(
            text(
                "UPDATE public.plans "
                "SET feature_flags = feature_flags || CAST(:flags AS jsonb) "
                "WHERE name = :name"
            ),
            {"flags": _json_dumps(new_flags), "name": row.name},
        )


# ── TENANT schema upgrade ────────────────────────────────────────────────────


def _upgrade_tenant(schema: str) -> None:
    bind = op.get_bind()

    # ── ALTER "ProspectingIntegration" ADD COLUMN key_source ────────────────
    if not _column_exists(bind, schema, "ProspectingIntegration", "key_source"):
        op.execute(
            f'ALTER TABLE "{schema}"."ProspectingIntegration" '
            f"ADD COLUMN key_source VARCHAR(32) NOT NULL DEFAULT 'tenant'"
        )
        op.execute(
            f'ALTER TABLE "{schema}"."ProspectingIntegration" '
            f"ADD CONSTRAINT prospecting_integration_key_source_check "
            f"CHECK (key_source IN ('tenant', 'platform'))"
        )

    # ── ALTER "ProspectingIntegration" ADD COLUMN api_key_encrypted ─────────
    if not _column_exists(
        bind, schema, "ProspectingIntegration", "api_key_encrypted"
    ):
        op.execute(
            f'ALTER TABLE "{schema}"."ProspectingIntegration" '
            f"ADD COLUMN api_key_encrypted TEXT"
        )

    # ── Back-fill api_key_encrypted from legacy apiKey ──────────────────────
    # We copy the plaintext value into api_key_encrypted so the new
    # credential-resolution code path can find it. The next UPDATE will
    # Fernet-encrypt it via IntegrationCredentialsService.store_tenant_credentials
    # (or IntegrationService.update). Legacy apiKey is left intact for
    # backward-compat reads until all callers are migrated.
    op.execute(
        f'UPDATE "{schema}"."ProspectingIntegration" '
        f'SET api_key_encrypted = "apiKey" '
        f'WHERE "apiKey" IS NOT NULL AND api_key_encrypted IS NULL'
    )

    # ── ALTER "MailBridgeConfig" ADD COLUMN owner_user_id ───────────────────
    if not _column_exists(bind, schema, "MailBridgeConfig", "owner_user_id"):
        op.execute(
            f'ALTER TABLE "{schema}"."MailBridgeConfig" '
            f"ADD COLUMN owner_user_id VARCHAR(128)"
        )

    # ── ALTER "LlmConfig" ADD COLUMN global_llm_config_id ───────────────────
    # FK to public.global_llm_config.id (nullable — existing rows are not
    # back-filled; they keep using their own apiKey column until a tenant
    # admin picks a global config via the new override flow).
    if not _column_exists(bind, schema, "LlmConfig", "global_llm_config_id"):
        op.execute(
            f'ALTER TABLE "{schema}"."LlmConfig" '
            f"ADD COLUMN global_llm_config_id INTEGER "
            f"REFERENCES public.global_llm_config(id)"
        )


# ── Downgrade ────────────────────────────────────────────────────────────────


def _downgrade_public() -> None:
    bind = op.get_bind()
    # Drop columns added in upgrade (additive only — leave global_llm_config
    # table for an explicit drop in case BE-C is still using it).
    if _column_exists(bind, "public", "subscriptions", "effective_price_cents"):
        op.execute(
            "ALTER TABLE public.subscriptions "
            "DROP COLUMN effective_price_cents"
        )
    if _column_exists(bind, "public", "subscriptions", "integration_mode"):
        op.execute(
            "ALTER TABLE public.subscriptions "
            "DROP CONSTRAINT IF EXISTS subscriptions_integration_mode_check"
        )
        op.execute(
            "ALTER TABLE public.subscriptions DROP COLUMN integration_mode"
        )
    if _column_exists(
        bind, "public", "tenant_signup_requests", "integration_mode"
    ):
        op.execute(
            "ALTER TABLE public.tenant_signup_requests "
            "DROP CONSTRAINT IF EXISTS tenant_signup_requests_integration_mode_check"
        )
        op.execute(
            "ALTER TABLE public.tenant_signup_requests "
            "DROP COLUMN integration_mode"
        )
    if _column_exists(bind, "public", "tenant_config", "integration_mode"):
        op.execute(
            "ALTER TABLE public.tenant_config "
            "DROP CONSTRAINT IF EXISTS tenant_config_integration_mode_check"
        )
        op.execute(
            "ALTER TABLE public.tenant_config DROP COLUMN integration_mode"
        )
    if _table_exists(bind, "public", "global_llm_config"):
        op.drop_index(
            "ix_global_llm_config_is_default_is_active",
            table_name="global_llm_config", schema="public",
        )
        op.drop_index(
            "ix_global_llm_config_provider",
            table_name="global_llm_config", schema="public",
        )
        op.drop_table("global_llm_config", schema="public")


def _downgrade_tenant(schema: str) -> None:
    bind = op.get_bind()
    if _column_exists(bind, schema, "LlmConfig", "global_llm_config_id"):
        op.execute(
            f'ALTER TABLE "{schema}"."LlmConfig" '
            f"DROP COLUMN global_llm_config_id"
        )
    if _column_exists(bind, schema, "MailBridgeConfig", "owner_user_id"):
        op.execute(
            f'ALTER TABLE "{schema}"."MailBridgeConfig" '
            f"DROP COLUMN owner_user_id"
        )
    if _column_exists(
        bind, schema, "ProspectingIntegration", "api_key_encrypted"
    ):
        op.execute(
            f'ALTER TABLE "{schema}"."ProspectingIntegration" '
            f"DROP COLUMN api_key_encrypted"
        )
    if _column_exists(bind, schema, "ProspectingIntegration", "key_source"):
        op.execute(
            f'ALTER TABLE "{schema}"."ProspectingIntegration" '
            f"DROP CONSTRAINT IF EXISTS prospecting_integration_key_source_check"
        )
        op.execute(
            f'ALTER TABLE "{schema}"."ProspectingIntegration" '
            f"DROP COLUMN key_source"
        )


__all__ = ["upgrade", "downgrade"]
