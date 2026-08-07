"""
plan.py — Subscription plan catalog (public schema, read-only after seed).

One row per commercial plan. The catalog is platform-wide — every tenant
picks from this list. Plans are referenced by Subscription (public) and by
TenantSignupRequest (public).

Seeded by alembic migration 0003_saas_platform with four tiers:
Free, Starter, Growth, Scale.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Plan(Base):
    """Commercial plan catalog row (public schema)."""

    __tablename__ = "plans"
    __table_args__ = ({"schema": "public"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    price_monthly_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_yearly_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seat_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    feature_flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=func.cast("{}", JSONB)
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.cast("true", Boolean)
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["Plan"]
