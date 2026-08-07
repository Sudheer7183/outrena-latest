"""Drop dead ``CampaignMetric`` table (Task 3-a / FIX 1).

Revision ID: 0010
Revises: 0009
Create Date: 2025-01-10 00:00:00

The ``CampaignMetric`` table was created by migration 0002 alongside every
other tenant-scoped table. It was intended to be a daily rollup of campaign
send/open/reply/bounce counts that the analytics endpoints would read from.

However, **no service ever writes to it**. The wiring audit (Task 2-e)
confirmed that:

  * ``AnalyticsService.list_metrics`` / ``generate_result`` / ``diagnose``
    previously queried ``CampaignMetric`` — but since the table is always
    empty, the analytics endpoints silently returned ``[]`` / ``None`` /
    all-zero layers. Task 2-e added a ``_aggregate_from_sequences`` fallback
    so the analytics endpoints work end-to-end without a CampaignMetric
    populator (the ``Sequence`` table is the source of truth — it carries
    ``sentAt`` / ``openedAt`` / ``repliedAt`` / ``bouncedAt`` timestamps
    populated by the MailBridge webhook path).
  * ``OptimizationRuleService._resolve_metric`` queried the latest
    ``CampaignMetric`` row for a campaign — also always empty, so every
    optimization rule evaluation silently skipped.

Task 3-a / FIX 1 removes the dead model + reads from Sequence everywhere.
This migration DROPs the now-orphaned table from every tenant schema.

Branches on schema (same pattern as 0002/0007/0008):
  * PUBLIC schema → no-op (CampaignMetric was never created in public; it
    lives in tenant schemas per 0002_initial_tenant.py).
  * tenant_{slug} schema → DROP TABLE IF EXISTS "CampaignMetric".

Idempotency: guarded by ``_table_exists`` so re-running is a no-op.

The downgrade recreates the table (column definitions copied verbatim
from 0002_initial_tenant.py L865-887) so a rollback restores the original
schema shape — even though the table is dead, a downstream operator who
manually populated it (e.g. via a custom Celery task) can recover the
data after rolling back this migration.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

# ── revision identifiers ────────────────────────────────────────────────────
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers (mirror 0002/0007/0008 conventions) ──────────────────────────────


def _s() -> str:
    """Return the active schema for this migration step.

    Reads ``context.get_context().version_table_schema`` (NOT ``os.environ``)
    because ``env.py`` iterates schemas within one process and env vars are
    not re-set per schema.
    """
    ctx = context.get_context()
    if ctx is None:
        return "public"
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


# ── upgrade / downgrade ─────────────────────────────────────────────────────


def upgrade() -> None:
    """Drop the dead ``CampaignMetric`` table from every tenant schema.

    No-op on the public schema (CampaignMetric was never created there).
    """
    schema = _s()
    if schema == "public":
        # CampaignMetric is a tenant-scoped table (created by 0002 in each
        # tenant schema). Nothing to drop in public.
        return

    bind = op.get_bind()
    if _table_exists(bind, schema, "CampaignMetric"):
        # Task 3-a / FIX 1: CampaignMetric is a dead model — no service ever
        # writes to it. Analytics now aggregates from the Sequence table
        # (the source of truth for send/open/reply/bounce timestamps). Drop
        # the orphaned table.
        op.drop_table("CampaignMetric", schema=schema)


def downgrade() -> None:
    """Recreate the ``CampaignMetric`` table (column defs from 0002 L865-887).

    Restores the original schema shape on rollback. The table is created
    empty — analytics will continue to aggregate from Sequence (the
    _aggregate_from_sequences fallback added by Task 2-e is retained, so
    a rollback does not silently break the analytics endpoints).
    """
    schema = _s()
    if schema == "public":
        return

    bind = op.get_bind()
    if _table_exists(bind, schema, "CampaignMetric"):
        # Already exists — nothing to recreate.
        return

    op.create_table(
        "CampaignMetric",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "campaignId",
            sa.String(length=64),
            sa.ForeignKey("Campaign.id"),
            nullable=False,
        ),
        sa.Column(
            "date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "totalSent", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "totalOpened", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "totalReplied", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "totalBounced", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "openRate", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "replyRate", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "bounceRate", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column("diagnosticNote", sa.String(), nullable=True),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=schema,
    )


__all__ = ["revision", "down_revision", "upgrade", "downgrade"]
