"""
0015_fix_timestamp_columns.py

Renames ``created_at`` → ``createdAt`` and ``updated_at`` → ``updatedAt`` in
the two tables created by migration 0005 (user_sender_identities and
user_email_quotas). All other tables created in 0002/0003/0004 already use
camelCase column names that match the TimestampMixin ORM definition.

This migration is idempotent: if the column is already named ``createdAt``
(e.g. the table was dropped and re-created by a future migration), the rename
is skipped via a column-existence check.

Applies to every tenant schema that is ACTIVE or PROVISIONING at migration
time, plus the public schema (public schema has no user_email_quotas or
user_sender_identities tables, so the rename is a silent no-op there).
"""
from __future__ import annotations

from typing import Union

from alembic import context, op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
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

    for table in ("user_sender_identities", "user_email_quotas"):
        if not _table_exists(bind, schema, table):
            continue
        # Rename created_at → createdAt (only if snake_case form exists)
        if _col_exists(bind, schema, table, "created_at") and not _col_exists(
            bind, schema, table, "createdAt"
        ):
            op.execute(
                text(
                    f'ALTER TABLE "{schema}"."{table}" '
                    f'RENAME COLUMN created_at TO "createdAt"'
                )
            )
        # Rename updated_at → updatedAt (only if snake_case form exists)
        if _col_exists(bind, schema, table, "updated_at") and not _col_exists(
            bind, schema, table, "updatedAt"
        ):
            op.execute(
                text(
                    f'ALTER TABLE "{schema}"."{table}" '
                    f'RENAME COLUMN updated_at TO "updatedAt"'
                )
            )


def downgrade() -> None:
    schema = _s()
    bind = op.get_bind()

    for table in ("user_sender_identities", "user_email_quotas"):
        if not _table_exists(bind, schema, table):
            continue
        if _col_exists(bind, schema, table, "createdAt") and not _col_exists(
            bind, schema, table, "created_at"
        ):
            op.execute(
                text(
                    f'ALTER TABLE "{schema}"."{table}" '
                    f'RENAME COLUMN "createdAt" TO created_at'
                )
            )
        if _col_exists(bind, schema, table, "updatedAt") and not _col_exists(
            bind, schema, table, "updated_at"
        ):
            op.execute(
                text(
                    f'ALTER TABLE "{schema}"."{table}" '
                    f'RENAME COLUMN "updatedAt" TO updated_at'
                )
            )
