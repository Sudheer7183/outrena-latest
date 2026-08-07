"""
usage.py — Tenant-scoped usage-event + cost-summary models.

Two tables live in each tenant_{slug} schema (created by alembic migration
0006_usage_tracking):

  usage_events   — the raw event log. One row per billable action:
                   LLM call, email send, prospect enrichment, LinkedIn
                   action, webhook receive, generic API call. Tenant-
                   scoped because every row references a tenant user_id
                   (Keycloak UUID) and is consumed by tenant dashboards.

  cost_summaries — a materialized roll-up. One row per
                   (user_id | tenant) × period × event_type × provider.
                   Rebuilt daily by a Celery task (UsageService.
                   rebuild_cost_summaries) so the manager / tenant /
                   platform dashboards do not have to scan the raw event
                   log on every render.

Cost is stored in INTEGER cents (not float dollars) to avoid float-rounding
drift in aggregations. The CostService converts per-provider rates (which
are floats in USD per 1K tokens / per call) to integer cents on write.

Schema-unqualified (matches the rest of the tenant-schema models). The
session's search_path locks them to the active tenant schema.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# ── Event-type vocabulary ──────────────────────────────────────────────────
# Centralized so the API, the service, and the migration all reference the
# same string set. Stored as a plain String column (not a PG enum) so new
# event types can be added without a migration.
EVENT_TYPES: tuple[str, ...] = (
    "llm_call",
    "email_send",
    "email_reply",
    "prospect_enrich",
    "linkedin_action",
    "webhook_receive",
    "api_call",
)

UNITS: tuple[str, ...] = (
    "tokens",
    "emails",
    "calls",
    "actions",
    "count",
)


class UsageEvent(Base):
    """One billable event in a tenant's history.

    Written fire-and-forget by UsageService.record_event (LLM calls, email
    sends, enrichment calls, etc.). Read by the per-user / per-tenant /
    per-manager usage endpoints and by the daily cost-summary rebuild job.
    """

    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_user_occurred", "user_id", "occurred_at"),
        Index("ix_usage_events_type_occurred", "event_type", "occurred_at"),
        Index("ix_usage_events_occurred", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resource: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="count")
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=func.cast("{}", JSONB),
    )
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CostSummary(Base):
    """Materialized cost / usage roll-up.

    One row per (user_id | tenant) × period × event_type × provider.
    ``user_id = NULL`` means the row is the tenant-level roll-up; non-NULL
    means it is the per-user roll-up. Period is a string ("2024-01" for
    monthly, "2024-01-15" for daily) so it sorts lexically and is easy to
    filter on. ``period_type`` disambiguates the granularity.
    """

    __tablename__ = "cost_summaries"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "period",
            "period_type",
            "event_type",
            "provider",
            name="uq_cost_summaries_user_period_type_provider",
        ),
        Index("ix_cost_summaries_period", "period"),
        Index("ix_cost_summaries_user_period", "user_id", "period"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["UsageEvent", "CostSummary", "EVENT_TYPES", "UNITS"]
