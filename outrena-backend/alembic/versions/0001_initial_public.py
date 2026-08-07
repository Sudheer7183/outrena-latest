"""Initial public schema: tenants registry + tenant_config.

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00

This migration creates the platform-wide registry tables in the PUBLIC schema
only. Tenant-scoped tables (the 47 operational models) are created by
migration 0002_initial_tenant.py (Phase 3) which branches on schema name:
returns early for public, creates all 47 tables for any tenant_{slug} schema.

Design:
- public.tenants is the single source of truth for tenant identity.
  Queried by TenantMiddleware on every request via raw text() SQL.
- public.tenant_config holds platform-level config for each tenant
  (plan, seat count, feature flags) — kept separate from tenants so the
  registry row stays small and fast to scan.
- Both tables are addressed with explicit schema qualification throughout
  the codebase (never via search_path).
- Alembic version_table lives in public for this migration.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _s() -> str:
    """Return the active schema for this migration step (mirrors 0002+)."""
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return ctx.version_table_schema or "public"


def upgrade() -> None:
    # This migration creates PUBLIC-schema-only registry tables. When Mode B
    # (env.py) runs it a second time for a tenant schema — version_table_schema
    # set to e.g. "tenant_acme" — every op.create_table call below still
    # hardcodes schema="public", so without this guard it would try to
    # recreate public.tenants / public.tenant_config / public.platform_audit_log,
    # which already exist, and crash with "relation already exists".
    if _s() != "public":
        return

    # ── public.tenants — platform registry ───────────────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS public")

    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("schema_name", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("tenant_type", sa.String(length=50), nullable=False, server_default="STANDARD"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="PROVISIONING",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.UniqueConstraint("schema_name", name="uq_tenants_schema_name"),
        schema="public",
    )

    op.create_index(
        "ix_tenants_status",
        "tenants",
        ["status"],
        schema="public",
    )

    # ── public.tenant_config — per-tenant platform config ────────────────────
    op.create_table(
        "tenant_config",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False, server_default="alpha"),
        sa.Column("max_seats", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "features",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "integrations_shared",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "llm_provider_default",
            sa.String(length=50),
            nullable=False,
            server_default="zai",
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
        sa.PrimaryKeyConstraint("tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["public.tenants.tenant_id"], ondelete="CASCADE"
        ),
        schema="public",
    )

    # ── Audit log (platform-wide) ─────────────────────────────────────────────
    op.create_table(
        "platform_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_sub", sa.String(length=128), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("tenant_slug", sa.String(length=63), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=True),
        sa.Column(
            "metadata",
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
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )

    op.create_index(
        "ix_platform_audit_log_tenant_slug_created_at",
        "platform_audit_log",
        ["tenant_slug", "created_at"],
        schema="public",
    )


def downgrade() -> None:
    if _s() != "public":
        return
    op.drop_index(
        "ix_platform_audit_log_tenant_slug_created_at",
        table_name="platform_audit_log",
        schema="public",
    )
    op.drop_table("platform_audit_log", schema="public")
    op.drop_table("tenant_config", schema="public")
    op.drop_index("ix_tenants_status", table_name="tenants", schema="public")
    op.drop_table("tenants", schema="public")