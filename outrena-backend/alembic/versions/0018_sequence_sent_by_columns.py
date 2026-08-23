"""
0018_sequence_sent_by_columns.py — Track who actually sent each sequence.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-20 00:00:00

Problem being fixed
-------------------
Outrena is multi-user within a single tenant.  A tenant admin can generate
sequences for a prospect but a manager (or any other user) might be the
one who clicks "Send".  Previously the Sequence row only stored
`owner_user_id` — the Keycloak UUID of whoever *created* the campaign —
and both the send path and the reply-poller used that value as the
MailBridge `external_user_id`.

This meant:
  1. Emails were always dispatched from the *creator's* mailbox, ignoring
     the connected account of the person who actually clicked Send.
  2. The reply-poller polled the creator's MailBridge inbox, missing replies
     that landed in the actual sender's inbox (if they are different people).

Fix
---
Two new nullable columns on Sequence:

  sent_by_user_id         VARCHAR(128) NULL
      Keycloak UUID of the Outrena user who triggered the outbound send.
      Set at send-time by the scheduler tick and MailBridgeService.send.
      Distinct from owner_user_id (creator); equals owner_user_id when the
      same person creates and sends.

  sent_via_external_user_id   VARCHAR(128) NULL
      The exact `external_user_id` value passed to MailBridge's
      POST /outbound/send.  This is what MailBridge used to route the email
      through a connected mailbox, and is therefore the correct identity to
      pass to GET /auth/connect/replies when polling for inbound replies.
      Usually equals sent_by_user_id; differs when a MailBridgeConfig has a
      static `mailbridge_external_user_id` override (shared SMTP box).

The reply-poller now uses `sent_via_external_user_id` (falling back to
`owner_user_id` for legacy rows that pre-date this migration) instead of
always using `owner_user_id`.

Both columns are nullable and backward-compatible: existing rows that were
sent before this migration are left NULL, and the poller falls back to
owner_user_id for those rows (previous behaviour, unchanged).

Idempotent: skipped if columns already exist.
Applies to every active tenant schema.
"""
from __future__ import annotations

from typing import Union

from alembic import context, op
from sqlalchemy import text

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels = None
depends_on = None


def _s() -> str:
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return ctx.version_table_schema or "public"


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

    table = "Sequence"
    if not _table_exists(bind, schema, table):
        return

    # sent_by_user_id — Keycloak UUID of the user who clicked Send.
    if not _col_exists(bind, schema, table, "sent_by_user_id"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'ADD COLUMN "sent_by_user_id" VARCHAR(128) DEFAULT NULL'
            )
        )

    # sent_via_external_user_id — exact external_user_id sent to MailBridge.
    # Used by the reply-poller to poll the correct inbox.
    if not _col_exists(bind, schema, table, "sent_via_external_user_id"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'ADD COLUMN "sent_via_external_user_id" VARCHAR(128) DEFAULT NULL'
            )
        )

    # Index on sent_via_external_user_id — the reply-poller filters by this
    # column across potentially thousands of sent-but-unreplied sequences.
    bind.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS "ix_Sequence_sent_via_external_user_id" '
            f'ON "{schema}"."{table}" ("sent_via_external_user_id") '
            f'WHERE "sent_via_external_user_id" IS NOT NULL'
        )
    )


def downgrade() -> None:
    schema = _s()
    bind = op.get_bind()

    table = "Sequence"
    if not _table_exists(bind, schema, table):
        return

    bind.execute(
        text(
            f'DROP INDEX IF EXISTS "{schema}"."ix_Sequence_sent_via_external_user_id"'
        )
    )

    if _col_exists(bind, schema, table, "sent_via_external_user_id"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'DROP COLUMN "sent_via_external_user_id"'
            )
        )

    if _col_exists(bind, schema, table, "sent_by_user_id"):
        op.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f'DROP COLUMN "sent_by_user_id"'
            )
        )