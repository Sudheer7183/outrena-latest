"""
0020_backfill_unsubscribe_tokens.py

Backfill unsubscribeToken for every Prospect row that currently has NULL.

The token was added to the Prospect table in migration 0002, but prospects
imported or created before the ProspectService.create() token-generation
code was deployed have NULL in this column.  A NULL token means
{{unsubscribe_url}} is never replaced in email bodies, so the prospect
receives a broken literal placeholder instead of a working unsubscribe link.

This migration:
  1. Generates a unique 64-character hex token using two concatenated
     gen_random_uuid() calls (no pgcrypto extension required — works on
     any PostgreSQL 13+ instance out of the box).
  2. Applies the same logic to every active tenant schema.
  3. Is fully idempotent: prospects that already have a token are skipped.
  4. Skips the public schema (no Prospect table there).

No new columns. No schema changes. Downgrade is a no-op (tokens are kept).
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels = None
depends_on = None


# ── Helpers (same pattern as 0007) ───────────────────────────────────────────


def _s() -> str:
    """Return the active schema for this migration step."""
    ctx = op.get_context()
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


# ── Alembic hooks ─────────────────────────────────────────────────────────────


def upgrade() -> None:
    schema = _s()
    if schema == "public":
        return  # No Prospect table in the public schema.
    _backfill_tenant(schema)


def downgrade() -> None:
    pass  # Tokens are kept on downgrade — removing them would break existing emails.


# ── Per-tenant backfill ───────────────────────────────────────────────────────


def _backfill_tenant(schema: str) -> None:
    bind = op.get_bind()

    # Guard: skip if the Prospect table does not exist in this schema.
    if not _table_exists(bind, schema, "Prospect"):
        return

    # Guard: skip if the unsubscribeToken column does not exist.
    if not _column_exists(bind, schema, "Prospect", "unsubscribeToken"):
        return

    # Generate a URL-safe token using two concatenated gen_random_uuid() calls.
    #
    # WHY NOT gen_random_bytes():
    #   gen_random_bytes() requires the pgcrypto extension which may not be
    #   installed.  gen_random_uuid() is always available on PostgreSQL 13+
    #   with no extension required.
    #
    # WHY TWO UUIDs:
    #   One UUID without hyphens = 32 hex chars = 128 bits entropy.
    #   Two UUIDs concatenated   = 64 hex chars = 256 bits entropy.
    #   256 bits is equivalent to secrets.token_urlsafe(32) in strength.
    #
    # The result is URL-safe (hex only: 0-9, a-f) — no character substitution
    # needed.  Example: "a3f8c2d1e4b7a09f5c6d2e8f1b3a4c7d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4"

    sql = text(
        'UPDATE "{schema}"."Prospect" '
        'SET "unsubscribeToken" = ('
        "    replace(gen_random_uuid()::text, '-', '') || "
        "    replace(gen_random_uuid()::text, '-', '')"
        ') WHERE "unsubscribeToken" IS NULL'.format(schema=schema)
    )

    result = bind.execute(sql)
    updated = result.rowcount if hasattr(result, "rowcount") else -1
    print(
        f"[0020] {schema}: backfilled unsubscribeToken for {updated} prospect row(s)."
    )
