"""Add ``owner_user_id`` to ``LinkedInEngagement`` (Task 3-a / FIX 2).

Revision ID: 0011
Revises: 0010
Create Date: 2025-01-11 00:00:00

The ``LinkedInEngagement`` model (``app/models/phase3_models.py``) tracks
LinkedIn touches (connect / message / view / endorse) on a prospect. It had
no ``owner_user_id`` column, so ``LinkedInService._record_usage`` recorded
every LinkedIn usage event against ``user_id="system"`` — making per-user
LinkedIn cost roll-ups impossible and breaking per-user attribution.

Task 3-a / FIX 2 adds the real column:

  ALTER TABLE "LinkedInEngagement"
      ADD COLUMN owner_user_id VARCHAR NULL;
  CREATE INDEX ix_LinkedInEngagement_owner_user_id
      ON "LinkedInEngagement" (owner_user_id);

The column is nullable so existing rows (created before this migration)
keep ``owner_user_id=NULL`` — the service treats NULL the same as
``"system"`` (falls back to the legacy placeholder). New engagements get
the current user's Keycloak sub from the request's ``TokenPayload``.

Branches on schema (same pattern as 0002/0007/0008/0010):
  * PUBLIC schema → no-op (LinkedInEngagement lives in tenant schemas).
  * tenant_{slug} schema → ADD COLUMN + CREATE INDEX (idempotent).

Idempotency: guarded by ``_column_exists`` / ``_index_exists`` so
re-running is a no-op.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

# ── revision identifiers ────────────────────────────────────────────────────
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers (mirror 0002/0007/0008/0010 conventions) ────────────────────────


def _s() -> str:
    """Return the active schema for this migration step."""
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return getattr(ctx, "version_table_schema", None) or "public"


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


# ── upgrade / downgrade ─────────────────────────────────────────────────────


def upgrade() -> None:
    """Add ``owner_user_id`` column + index to ``LinkedInEngagement``.

    No-op on the public schema (LinkedInEngagement is tenant-scoped).
    """
    schema = _s()
    if schema == "public":
        return

    bind = op.get_bind()

    # Add the column (idempotent — skip if already present).
    if not _column_exists(bind, schema, "LinkedInEngagement", "owner_user_id"):
        op.add_column(
            "LinkedInEngagement",
            sa.Column("owner_user_id", sa.String(), nullable=True),
            schema=schema,
        )

    # Add the index (idempotent — skip if already present).
    if not _index_exists(
        bind, schema, "LinkedInEngagement", "ix_LinkedInEngagement_owner_user_id"
    ):
        op.create_index(
            "ix_LinkedInEngagement_owner_user_id",
            "LinkedInEngagement",
            ["owner_user_id"],
            schema=schema,
        )


def downgrade() -> None:
    """Drop the ``owner_user_id`` column + index from ``LinkedInEngagement``.

    Idempotent — safe to run on schemas where the column doesn't exist.
    """
    schema = _s()
    if schema == "public":
        return

    bind = op.get_bind()

    # Drop the index first (idempotent).
    if _index_exists(
        bind, schema, "LinkedInEngagement", "ix_LinkedInEngagement_owner_user_id"
    ):
        op.drop_index(
            "ix_LinkedInEngagement_owner_user_id",
            table_name="LinkedInEngagement",
            schema=schema,
        )

    # Drop the column (idempotent).
    if _column_exists(bind, schema, "LinkedInEngagement", "owner_user_id"):
        op.drop_column("LinkedInEngagement", "owner_user_id", schema=schema)


__all__ = ["revision", "down_revision", "upgrade", "downgrade"]
