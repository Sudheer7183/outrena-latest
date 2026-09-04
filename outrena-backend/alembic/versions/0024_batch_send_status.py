"""
0024_batch_send_status.py — BatchSend intermediate status + batch id column.

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-02

What this migration does
-------------------------
BatchSend (see BatchSend_Implementation_Prompt.docx + the accompanying
Design Review docx) introduces a new intermediate Sequence.status value,
'BatchPending', set by the scheduler the instant a sequence is folded into
a POST /outbound/batch-send call, and replaced with 'Sent' or 'Failed' by
the batch completion webhook handler once MailBridge confirms the result.

Without this intermediate state, a sequence dispatched via BatchSend would
either:
  a) stay 'Scheduled' — and get double-sent by the next scheduler tick
     before the completion webhook arrives, or
  b) jump straight to 'Sent' at dispatch time — leaving a 'Sent' row with
     no sentAt/mailBridgeMessageId if the send actually fails.

See Design Review docx, "The Sequence.status intermediate state problem"
(complication #7).

Two changes, both per-tenant-schema (this migration is a no-op against the
public schema, same convention as every other tenant-data migration here):

  1. ALTER TYPE "{schema}".email_status ADD VALUE 'BatchPending'
     `email_status` is a genuine Postgres ENUM type, created once per
     tenant schema in 0002_initial_tenant.py (_create_enum). SQLAlchemy's
     Sequence.status column uses native_enum=False so the ORM never emits
     an ::email_status cast (see app/models/campaign_models.py comment
     block on why), but the underlying column type is still that Postgres
     enum, so a new label must be added to the type itself before any row
     can be set to 'BatchPending'.

     Executed as a normal statement inside the migration's existing
     transaction, NOT inside op.get_context().autocommit_block(). Two
     reasons:
       - PostgreSQL has allowed ALTER TYPE ... ADD VALUE inside an
         ordinary transaction since PG12 — the only restriction is that
         the new label can't be *used* in the same transaction that added
         it (e.g. an INSERT/UPDATE referencing 'BatchPending'), which this
         migration never does.
       - This repo's env.py drives migrations through an async engine via
         `connection.run_sync(do_run_migrations, schema_name)`, looping
         over tenant schemas itself. That custom transaction/connection
         lifecycle doesn't populate the internal state
         `MigrationContext.autocommit_block()` requires (it asserts
         `self._transaction is not None`), so calling it here raises
         `AssertionError` regardless of Postgres version — confirmed
         against this exact env.py. Running the ALTER TYPE as a plain
         `op.execute()` avoids that assumption entirely.

     Idempotent: checks pg_enum first so re-running this migration (e.g.
     on a tenant schema that already has the value) is a safe no-op
     rather than an error.

  2. ALTER TABLE "{schema}"."Sequence" ADD COLUMN "mailBridgeBatchId" TEXT
     Nullable, traceability-only column recording which MailBridge batchId
     a row was dispatched under. The completion webhook handler looks rows
     up by sequenceId (not this column), so this is not on any hot query
     path — no index needed.

Idempotent throughout: skipped if the enum value / column already exists.
Applies to every active tenant schema (same per-schema execution model as
0002/0017/0018 — Alembic is invoked once per tenant version_table_schema).
"""
from __future__ import annotations

from typing import Union

from alembic import context, op
from sqlalchemy import text

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels = None
depends_on = None


def _s() -> str:
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return ctx.version_table_schema or "public"


def _table_exists(bind, schema: str, table: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table LIMIT 1"
        ),
        {"schema": schema, "table": table},
    )
    return result.fetchone() is not None


def _col_exists(bind, schema: str, table: str, column: str) -> bool:
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


def _enum_type_exists(bind, schema: str, type_name: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM pg_type t "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE n.nspname = :schema AND t.typname = :type_name LIMIT 1"
        ),
        {"schema": schema, "type_name": type_name},
    )
    return result.fetchone() is not None


def _enum_value_exists(bind, schema: str, type_name: str, value: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE n.nspname = :schema AND t.typname = :type_name "
            "  AND e.enumlabel = :value LIMIT 1"
        ),
        {"schema": schema, "type_name": type_name, "value": value},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    schema = _s()
    if schema == "public":
        # Public-schema DDL is owned by 0001_initial_public.py; this
        # migration only touches per-tenant data (email_status enum,
        # Sequence table) — both no-ops against public.
        return

    bind = op.get_bind()

    # ── 1. email_status enum: add 'BatchPending' ───────────────────────
    if _enum_type_exists(bind, schema, "email_status") and not _enum_value_exists(
        bind, schema, "email_status", "BatchPending"
    ):
        # Plain op.execute() inside the migration's existing transaction —
        # NOT op.get_context().autocommit_block(). See module docstring:
        # PG12+ allows ADD VALUE inside a normal transaction as long as the
        # new label isn't used in that same transaction (it isn't, here),
        # and autocommit_block() raises AssertionError under this repo's
        # async run_sync-based env.py regardless of Postgres version.
        op.execute(
            text(f'ALTER TYPE "{schema}".email_status ADD VALUE \'BatchPending\'')
        )

    # ── 2. Sequence.mailBridgeBatchId column ────────────────────────────
    table = "Sequence"
    if _table_exists(bind, schema, table) and not _col_exists(
        bind, schema, table, "mailBridgeBatchId"
    ):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'ADD COLUMN "mailBridgeBatchId" TEXT DEFAULT NULL'
            )
        )


def downgrade() -> None:
    schema = _s()
    if schema == "public":
        return

    bind = op.get_bind()

    table = "Sequence"
    if _table_exists(bind, schema, table) and _col_exists(
        bind, schema, table, "mailBridgeBatchId"
    ):
        op.execute(
            text(f'ALTER TABLE "{schema}"."{table}" DROP COLUMN "mailBridgeBatchId"')
        )

    # NOTE: Postgres does not support removing a value from an enum type
    # (DROP VALUE doesn't exist). Downgrading the email_status enum itself
    # is intentionally a no-op — any 'BatchPending' rows would need to be
    # migrated to another status by a data migration before the value
    # could safely be dropped by recreating the type, which is out of
    # scope for this migration. This matches Postgres's own limitation,
    # not an oversight.