"""
0021_email_suppression_table.py

Create EmailSuppression table in every tenant schema.

WHY THIS TABLE EXISTS
---------------------
The existing Prospect-level suppression (suppressed=true, consent_status='withdrawn')
only marks the specific Prospect ROW whose unsubscribeToken was in the clicked email.

If the same email address appears in two Prospect rows (duplicate import, two campaigns),
or if a new Prospect is created later with the same email address, the suppression is
silently bypassed and the person receives more outreach.

EmailSuppression is the canonical, email-level opt-out record for a tenant.

WHAT IT DOES
------------
- Stores one row per opted-out email address (lowercased, trimmed) per tenant schema.
- Is checked at every send gate BEFORE looking at Prospect.suppressed.
- Is populated automatically when a prospect clicks the unsubscribe link.
- Is also backfilled here from all existing Prospect rows where suppressed=true.

SCHEMA
------
EmailSuppression (per tenant schema):
    id              TEXT        PK (gen_random_uuid())
    email           TEXT        NOT NULL, UNIQUE (lowercased)
    suppressedAt    TIMESTAMPTZ NOT NULL
    source          TEXT        NOT NULL  ('unsubscribe_link' | 'manual' | 'bounce' | 'backfill')
    notes           TEXT        NULLABLE

Uniqueness is on the lowercased email address — one row per email per tenant.

BACKFILL
--------
All existing Prospect rows with suppressed=true are inserted into EmailSuppression
so that the new gate immediately honours pre-existing opt-outs without requiring
another unsubscribe click.

IDEMPOTENT
----------
Table creation is guarded by _table_exists(). The backfill uses INSERT ... ON CONFLICT DO NOTHING.
Both upgrade() and the backfill are safe to run multiple times.
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels = None
depends_on = None


# ── helpers (same pattern as 0019) ────────────────────────────────────────────

def _s() -> str:
    """Return the schema being migrated right now (set by env.py per-tenant loop)."""
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return ctx.version_table_schema or "public"


def _table_exists(bind, schema: str, name: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name LIMIT 1"
        ),
        {"schema": schema, "name": name},
    )
    return result.fetchone() is not None


# ── upgrade ───────────────────────────────────────────────────────────────────

def upgrade() -> None:
    schema = _s()

    # EmailSuppression is a tenant-scoped table — skip for public schema.
    if schema == "public":
        return

    bind = op.get_bind()

    # ── Step 1: Create EmailSuppression table (idempotent) ────────────────────
    if not _table_exists(bind, schema, "EmailSuppression"):
        op.create_table(
            "EmailSuppression",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "email",
                sa.String(),
                nullable=False,
            ),
            sa.Column(
                "suppressedAt",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "source",
                sa.String(),
                nullable=False,
                server_default=sa.text("'unsubscribe_link'"),
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.UniqueConstraint("email", name="uq_EmailSuppression_email"),
            schema=schema,
        )

        op.create_index(
            "ix_EmailSuppression_email",
            "EmailSuppression",
            ["email"],
            schema=schema,
        )

        print(f"[0021] {schema}: created EmailSuppression table.")
    else:
        print(f"[0021] {schema}: EmailSuppression table already exists — skipping create.")

    # ── Step 2: Backfill from existing suppressed Prospect rows ───────────────
    # Prospects that were suppressed before this migration was applied must be
    # added to EmailSuppression so that the new send gate immediately honours
    # their opt-out without requiring another unsubscribe click.
    #
    # Uses INSERT ... ON CONFLICT DO NOTHING so re-running this migration is safe.
    # email is lowercased + trimmed for canonical matching.
    #
    # Only inserts rows where email IS NOT NULL and is not empty.

    if _table_exists(bind, schema, "Prospect"):
        result = bind.execute(
            text(
                f"""
                INSERT INTO "{schema}"."EmailSuppression"
                    (id, email, "suppressedAt", source, notes)
                SELECT
                    replace(gen_random_uuid()::text, '-', ''),
                    lower(trim(email)),
                    COALESCE("suppressedAt", now()),
                    'backfill',
                    'Backfilled by migration 0021 from Prospect.suppressed=true'
                FROM "{schema}"."Prospect"
                WHERE
                    suppressed = true
                    AND email IS NOT NULL
                    AND trim(email) <> ''
                ON CONFLICT (email) DO NOTHING
                """
            )
        )
        inserted = result.rowcount if hasattr(result, "rowcount") else -1
        print(f"[0021] {schema}: backfilled {inserted} email(s) into EmailSuppression.")
    else:
        print(f"[0021] {schema}: Prospect table not found — skipping backfill.")


# ── downgrade ─────────────────────────────────────────────────────────────────

def downgrade() -> None:
    schema = _s()

    if schema == "public":
        return

    bind = op.get_bind()

    if not _table_exists(bind, schema, "EmailSuppression"):
        return

    op.drop_index("ix_EmailSuppression_email", table_name="EmailSuppression", schema=schema)
    op.drop_table("EmailSuppression", schema=schema)
    print(f"[0021] {schema}: dropped EmailSuppression table.")
