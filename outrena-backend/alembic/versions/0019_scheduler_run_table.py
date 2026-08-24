"""
0019_scheduler_run_table.py — Create SchedulerRun table in every tenant schema.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-24 00:00:00

Problem being fixed
-------------------
The SchedulerRun ORM model (app/models/phase3_models.py) was defined but
never included in any Alembic migration. This caused two runtime errors:

  1. GET /api/v1/scheduler/runs crashed with:
       UndefinedTableError: relation "SchedulerRun" does not exist

  2. POST /api/v1/scheduler/trigger crashed when attempting to INSERT a
     SchedulerRun row to log the trigger event.

Both errors produced 500 Internal Server Error responses and prevented the
Scheduler Status page from loading at all.

Fix
---
Creates the SchedulerRun table in the current tenant schema (env.py drives
the per-schema loop — same pattern as 0018). Uses _s() to get the schema
from Alembic context, and _table_exists() guard so the migration is
idempotent.

Columns match app/models/phase3_models.py exactly:
  - id           VARCHAR primary key (CUID)
  - startedAt    TIMESTAMPTZ server_default now()
  - completedAt  TIMESTAMPTZ nullable
  - status       VARCHAR not null server_default 'running'
  - sent         INTEGER not null server_default 0
  - skipped      INTEGER not null server_default 0
  - durationMs   INTEGER nullable
  - error        TEXT nullable
  - createdAt    TIMESTAMPTZ server_default now()
  - updatedAt    TIMESTAMPTZ server_default now()
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels = None
depends_on = None


# ── helpers (same pattern as 0018) ────────────────────────────────────────────

def _s() -> str:
    """Return the schema being migrated right now (set by env.py per-tenant loop)."""
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return ctx.version_table_schema or "public"


def _table_exists(bind, schema: str, name: str) -> bool:
    """Return True if table *name* exists in *schema*."""
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
    bind = op.get_bind()

    # Idempotent — skip if table already exists in this schema
    if _table_exists(bind, schema, "SchedulerRun"):
        return

    op.create_table(
        "SchedulerRun",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "startedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column(
            "sent",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "skipped",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("durationMs", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
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

    # Indexes matching ORM __table_args__
    op.create_index(
        "ix_SchedulerRun_status",
        "SchedulerRun",
        ["status"],
        schema=schema,
    )
    op.create_index(
        "ix_SchedulerRun_startedAt",
        "SchedulerRun",
        ["startedAt"],
        schema=schema,
    )


# ── downgrade ─────────────────────────────────────────────────────────────────

def downgrade() -> None:
    schema = _s()
    bind = op.get_bind()

    if not _table_exists(bind, schema, "SchedulerRun"):
        return

    op.drop_index("ix_SchedulerRun_startedAt", table_name="SchedulerRun", schema=schema)
    op.drop_index("ix_SchedulerRun_status", table_name="SchedulerRun", schema=schema)
    op.drop_table("SchedulerRun", schema=schema)