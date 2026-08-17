"""
0017_mailbridge_tenancy_columns.py — Add MailBridge tenancy columns.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-13 00:00:00

Changes:
  1. Add "mailbridge_api_key" VARCHAR NULL to MailBridgeConfig
     — stores the mb_live_... tenant API key from POST /platform/register
  2. Add "mailbridge_external_user_id" VARCHAR(128) NULL to MailBridgeConfig
     — stores the Outrena user UUID used for MailBridge identity propagation

Both columns are nullable so existing rows are unaffected. They enable
Outrena → MailBridge tenancy-mode integration: authenticated API calls
and per-user mailbox routing via identity propagation.

This migration is idempotent: if the columns already exist, the ALTER
TABLE is skipped via a column-existence check.

Applies to every tenant schema that is ACTIVE or PROVISIONING at migration
time.
"""
from __future__ import annotations

from typing import Union

from alembic import context, op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
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

    table = "MailBridgeConfig"
    if not _table_exists(bind, schema, table):
        return

    # Add mailbridge_api_key VARCHAR NULL (idempotent)
    if not _col_exists(bind, schema, table, "mailbridge_api_key"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'ADD COLUMN "mailbridge_api_key" VARCHAR DEFAULT NULL'
            )
        )

    # Add mailbridge_external_user_id VARCHAR(128) NULL (idempotent)
    if not _col_exists(bind, schema, table, "mailbridge_external_user_id"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'ADD COLUMN "mailbridge_external_user_id" VARCHAR(128) DEFAULT NULL'
            )
        )


def downgrade() -> None:
    schema = _s()
    bind = op.get_bind()

    table = "MailBridgeConfig"
    if not _table_exists(bind, schema, table):
        return

    # Drop mailbridge_external_user_id (idempotent)
    if _col_exists(bind, schema, table, "mailbridge_external_user_id"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'DROP COLUMN "mailbridge_external_user_id"'
            )
        )

    # Drop mailbridge_api_key (idempotent)
    if _col_exists(bind, schema, table, "mailbridge_api_key"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'DROP COLUMN "mailbridge_api_key"'
            )
        )
