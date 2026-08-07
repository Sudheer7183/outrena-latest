"""Per-user capabilities: owner_user_id + sender identities + email quota.

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-05 00:00:00

This migration is TENANT-schema only (mirrors the 0003 tenant-upgrade pattern):

  For every tenant_{slug} schema (early-return for public):
    1. ALTER campaigns ADD COLUMN owner_user_id VARCHAR(128) NOT NULL
       DEFAULT 'system'  — backfill for rows created before per-user ownership.
    2. ALTER sequences ADD COLUMN owner_user_id VARCHAR(128) NOT NULL
       DEFAULT 'system'.
    3. CREATE TABLE user_sender_identities (per-user sender email + quota).
    4. CREATE TABLE user_email_quotas (per-user, per-day counter + throttle).
    5. CREATE INDEXES:
       - ix_Campaign_owner_user_id
       - ix_Sequence_owner_user_id
       - ix_user_email_quotas_user_id_date (covering index for status reads)
       - ix_user_email_quotas_is_throttled (manager dashboard at-risk view)
       - ix_user_sender_identities_user_id_is_default

The MailBridgeConfig.owner_user_id column is owned by BE-A's migration 0004
(added to app/models/config_models.py by BE-A). This migration does NOT touch
the MailBridgeConfig table.

Idempotency: every DDL operation is guarded by _table_exists / _column_exists
so re-running upgrade head is a no-op.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

# ── revision identifiers ────────────────────────────────────────────────────
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── §4.6 hard-rule helpers (mirror 0002 / 0003 conventions) ────────────────


def _s() -> str:
    """Return the active schema for this migration step.

    Reads ``context.get_context().version_table_schema`` (NOT ``os.environ``)
    because env.py iterates schemas within one process and env vars are not
    re-set per schema. Defaults to "public" if no context is active.
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


def _index_exists(bind, schema: str, table: str, index: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = :schema AND tablename = :table "
            "AND indexname = :index"
        ),
        {"schema": schema, "table": table, "index": index},
    )
    return result.fetchone() is not None


# ── upgrade / downgrade dispatch ───────────────────────────────────────────


def upgrade() -> None:
    schema = _s()
    if schema == "public":
        # Public schema has no per-user tables — this migration is a no-op.
        return
    _upgrade_tenant(schema)


def downgrade() -> None:
    schema = _s()
    if schema == "public":
        return
    _downgrade_tenant(schema)


# ── TENANT schema upgrade ───────────────────────────────────────────────────


def _upgrade_tenant(schema: str) -> None:
    bind = op.get_bind()

    # ── ALTER Campaign ADD COLUMN owner_user_id ────────────────────────────
    if not _column_exists(bind, schema, "Campaign", "owner_user_id"):
        op.execute(
            f'ALTER TABLE "{schema}"."Campaign" '
            f'ADD COLUMN owner_user_id VARCHAR(128) NOT NULL '
            f"DEFAULT 'system'"
        )
    if not _index_exists(bind, schema, "Campaign", "ix_Campaign_owner_user_id"):
        op.create_index(
            "ix_Campaign_owner_user_id",
            "Campaign",
            ["owner_user_id"],
            schema=schema,
        )

    # ── ALTER Sequence ADD COLUMN owner_user_id ────────────────────────────
    if not _column_exists(bind, schema, "Sequence", "owner_user_id"):
        op.execute(
            f'ALTER TABLE "{schema}"."Sequence" '
            f'ADD COLUMN owner_user_id VARCHAR(128) NOT NULL '
            f"DEFAULT 'system'"
        )
    if not _index_exists(bind, schema, "Sequence", "ix_Sequence_owner_user_id"):
        op.create_index(
            "ix_Sequence_owner_user_id",
            "Sequence",
            ["owner_user_id"],
            schema=schema,
        )

    # ── CREATE TABLE user_sender_identities ────────────────────────────────
    if not _table_exists(bind, schema, "user_sender_identities"):
        op.create_table(
            "user_sender_identities",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(length=128), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column(
                "email_type", sa.String(length=40),
                nullable=False, server_default="platform_assigned",
            ),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column(
                "is_verified", sa.Boolean(),
                nullable=False, server_default=sa.text("false"),
            ),
            sa.Column(
                "is_default", sa.Boolean(),
                nullable=False, server_default=sa.text("false"),
            ),
            sa.Column(
                "daily_send_quota", sa.Integer(),
                nullable=False, server_default="100",
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
            sa.UniqueConstraint(
                "user_id", "email",
                name="uq_user_sender_identities_user_email",
            ),
            schema=schema,
        )
    if not _index_exists(
        bind, schema, "user_sender_identities",
        "ix_user_sender_identities_user_id_is_default",
    ):
        op.create_index(
            "ix_user_sender_identities_user_id_is_default",
            "user_sender_identities",
            ["user_id", "is_default"],
            schema=schema,
        )

    # ── CREATE TABLE user_email_quotas ─────────────────────────────────────
    if not _table_exists(bind, schema, "user_email_quotas"):
        op.create_table(
            "user_email_quotas",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(length=128), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column(
                "emails_sent", sa.Integer(),
                nullable=False, server_default="0",
            ),
            sa.Column(
                "emails_bounced", sa.Integer(),
                nullable=False, server_default="0",
            ),
            sa.Column(
                "complaints", sa.Integer(),
                nullable=False, server_default="0",
            ),
            sa.Column(
                "window_start", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "last_reset_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "is_throttled", sa.Boolean(),
                nullable=False, server_default=sa.text("false"),
            ),
            sa.Column(
                "throttled_until", sa.DateTime(timezone=True), nullable=True,
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
            sa.UniqueConstraint(
                "user_id", "date",
                name="uq_user_email_quotas_user_date",
            ),
            schema=schema,
        )
    if not _index_exists(
        bind, schema, "user_email_quotas",
        "ix_user_email_quotas_user_id_date",
    ):
        op.create_index(
            "ix_user_email_quotas_user_id_date",
            "user_email_quotas",
            ["user_id", "date"],
            schema=schema,
        )
    if not _index_exists(
        bind, schema, "user_email_quotas",
        "ix_user_email_quotas_is_throttled",
    ):
        op.create_index(
            "ix_user_email_quotas_is_throttled",
            "user_email_quotas",
            ["is_throttled"],
            schema=schema,
        )


# ── TENANT schema downgrade ─────────────────────────────────────────────────


def _downgrade_tenant(schema: str) -> None:
    bind = op.get_bind()

    # Drop tables (idempotent).
    if _table_exists(bind, schema, "user_email_quotas"):
        op.drop_table("user_email_quotas", schema=schema)
    if _table_exists(bind, schema, "user_sender_identities"):
        op.drop_table("user_sender_identities", schema=schema)

    # Drop indexes (idempotent) + columns on Campaign / Sequence.
    for table, idx in (
        ("Sequence", "ix_Sequence_owner_user_id"),
        ("Campaign", "ix_Campaign_owner_user_id"),
    ):
        if _index_exists(bind, schema, table, idx):
            op.drop_index(idx, table_name=table, schema=schema)

    if _column_exists(bind, schema, "Sequence", "owner_user_id"):
        op.execute(
            f'ALTER TABLE "{schema}"."Sequence" '
            f'DROP COLUMN owner_user_id'
        )
    if _column_exists(bind, schema, "Campaign", "owner_user_id"):
        op.execute(
            f'ALTER TABLE "{schema}"."Campaign" '
            f'DROP COLUMN owner_user_id'
        )


__all__ = ["revision", "down_revision", "upgrade", "downgrade"]
