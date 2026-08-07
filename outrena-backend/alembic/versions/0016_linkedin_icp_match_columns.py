"""
0016_linkedin_icp_match_columns.py — Add ICP match fields to LinkedInEngagement.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-01 00:00:00

Changes:
  1. Add "isIcpMatch"  BOOLEAN NULL  — whether the engagement matches an ICP
  2. Add "suggestedNote" TEXT NULL    — AI-suggested outreach note

Both columns are nullable so existing rows are unaffected. They are populated
by POST /linkedin/engagements/check-icp which batch-checks engagements against
ICP profiles using LLM.

This migration is idempotent: if the columns already exist (e.g. the table
was dropped and re-created by a future migration), the ALTER TABLE is skipped
via a column-existence check.

Applies to every tenant schema that is ACTIVE or PROVISIONING at migration
time, plus the public schema (public schema has no LinkedInEngagement table,
so the add is a silent no-op there).
"""
from __future__ import annotations

from typing import Union

from alembic import context, op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels = None
depends_on = None


def _s() -> str:
    """Return the active schema for this migration step."""
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return ctx.version_table_schema or "public"


def _col_exists(bind, schema: str, table: str, column: str) -> bool:
    """Return True if the column already exists in the table."""
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema "
            "  AND table_name   = :table "
            "  AND column_name  = :col "
            "LIMIT 1"
        ),
        {"schema": schema, "table": table, "col": column},
    )
    return result.fetchone() is not None


def _table_exists(bind, schema: str, table: str) -> bool:
    """Return True if the table exists in the schema."""
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table LIMIT 1"
        ),
        {"schema": schema, "table": table},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    schema = _s()
    bind = op.get_bind()

    table = "LinkedInEngagement"
    if not _table_exists(bind, schema, table):
        return

    # Add isIcpMatch BOOLEAN NULL (idempotent)
    if not _col_exists(bind, schema, table, "isIcpMatch"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'ADD COLUMN "isIcpMatch" BOOLEAN DEFAULT NULL'
            )
        )

    # Add suggestedNote TEXT NULL (idempotent)
    if not _col_exists(bind, schema, table, "suggestedNote"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'ADD COLUMN "suggestedNote" TEXT DEFAULT NULL'
            )
        )


def downgrade() -> None:
    schema = _s()
    bind = op.get_bind()

    table = "LinkedInEngagement"
    if not _table_exists(bind, schema, table):
        return

    # Drop suggestedNote (idempotent)
    if _col_exists(bind, schema, table, "suggestedNote"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'DROP COLUMN "suggestedNote"'
            )
        )

    # Drop isIcpMatch (idempotent)
    if _col_exists(bind, schema, table, "isIcpMatch"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'DROP COLUMN "isIcpMatch"'
            )
        )
