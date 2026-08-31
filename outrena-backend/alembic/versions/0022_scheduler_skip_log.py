"""
0022_scheduler_skip_log.py — Add SchedulerSkipLog + SchedulerDailySent tables.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-30 00:00:00

Tables added
------------
SchedulerSkipLog
  Persists per-sequence skip events so the Scheduler page can drill-down into
  WHY each sequence was skipped during a tick.

  Columns:
    id          VARCHAR  primary key (CUID)
    runId       VARCHAR  nullable — FK to SchedulerRun (may be null for manual ticks)
    sequenceId  VARCHAR  not null
    campaignId  VARCHAR  nullable
    prospectId  VARCHAR  nullable
    skipReason  VARCHAR  not null — e.g. "no_email", "suppressed", "business_hours",
                                    "quota_exceeded", "no_mailbridge_config", "send_error"
    detail      TEXT     nullable — extra context (error message, suppression reason, etc.)
    skippedAt   TIMESTAMPTZ server_default now()

SchedulerDailySent
  One row per (campaign, date) — aggregated by the tick writer so the Daily Sent
  log tab can show totals without scanning Sequence.sentAt every time.

  Columns:
    id         VARCHAR  primary key (CUID)
    campaignId VARCHAR  not null
    sentDate   DATE     not null  — UTC date
    sentCount  INTEGER  not null  default 0
    createdAt  TIMESTAMPTZ server_default now()
    updatedAt  TIMESTAMPTZ server_default now()
  Unique: (campaignId, sentDate)

Both tables live in the TENANT schema (same pattern as 0019).
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels = None
depends_on = None


def _s() -> str:
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


def upgrade() -> None:
    schema = _s()
    bind = op.get_bind()

    # ── SchedulerSkipLog ──────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "SchedulerSkipLog"):
        op.create_table(
            "SchedulerSkipLog",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("runId", sa.String(), nullable=True),
            sa.Column("sequenceId", sa.String(), nullable=False),
            sa.Column("campaignId", sa.String(), nullable=True),
            sa.Column("prospectId", sa.String(), nullable=True),
            sa.Column(
                "skipReason",
                sa.String(),
                nullable=False,
                comment=(
                    "no_email | suppressed | business_hours | quota_exceeded "
                    "| no_mailbridge_config | send_error | warmup_cap"
                ),
            ),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column(
                "skippedAt",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            schema=schema,
        )
        op.create_index(
            "ix_SchedulerSkipLog_runId",
            "SchedulerSkipLog",
            ["runId"],
            schema=schema,
        )
        op.create_index(
            "ix_SchedulerSkipLog_campaignId",
            "SchedulerSkipLog",
            ["campaignId"],
            schema=schema,
        )
        op.create_index(
            "ix_SchedulerSkipLog_skippedAt",
            "SchedulerSkipLog",
            ["skippedAt"],
            schema=schema,
        )

    # ── SchedulerDailySent ────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "SchedulerDailySent"):
        op.create_table(
            "SchedulerDailySent",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("campaignId", sa.String(), nullable=False),
            sa.Column("sentDate", sa.Date(), nullable=False),
            sa.Column(
                "sentCount",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "createdAt",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updatedAt",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            schema=schema,
        )
        op.create_index(
            "ix_SchedulerDailySent_campaignId",
            "SchedulerDailySent",
            ["campaignId"],
            schema=schema,
        )
        op.create_index(
            "ix_SchedulerDailySent_sentDate",
            "SchedulerDailySent",
            ["sentDate"],
            schema=schema,
        )
        # Unique constraint so upsert works
        op.create_unique_constraint(
            "uq_SchedulerDailySent_campaign_date",
            "SchedulerDailySent",
            ["campaignId", "sentDate"],
            schema=schema,
        )


def downgrade() -> None:
    schema = _s()
    bind = op.get_bind()

    if _table_exists(bind, schema, "SchedulerDailySent"):
        op.drop_constraint(
            "uq_SchedulerDailySent_campaign_date",
            "SchedulerDailySent",
            schema=schema,
        )
        op.drop_index("ix_SchedulerDailySent_sentDate", table_name="SchedulerDailySent", schema=schema)
        op.drop_index("ix_SchedulerDailySent_campaignId", table_name="SchedulerDailySent", schema=schema)
        op.drop_table("SchedulerDailySent", schema=schema)

    if _table_exists(bind, schema, "SchedulerSkipLog"):
        op.drop_index("ix_SchedulerSkipLog_skippedAt", table_name="SchedulerSkipLog", schema=schema)
        op.drop_index("ix_SchedulerSkipLog_campaignId", table_name="SchedulerSkipLog", schema=schema)
        op.drop_index("ix_SchedulerSkipLog_runId", table_name="SchedulerSkipLog", schema=schema)
        op.drop_table("SchedulerSkipLog", schema=schema)
