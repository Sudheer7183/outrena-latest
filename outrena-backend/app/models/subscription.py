# """
# subscription.py — Tenant subscription record (public schema).

# One row per tenant (1:1 with public.tenants). Tracks the active Plan, the
# external Stripe subscription id (if any), the current billing period, and
# the seat-usage counter used to enforce Plan.seat_limit on user create.

# Status lifecycle mirrors Stripe's subscription states so a future flip
# from MockProvider to StripeProvider requires no schema change.
# """
# from __future__ import annotations

# from datetime import datetime

# from app.core.database import Base
# from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
# from sqlalchemy.orm import Mapped, mapped_column


# class Subscription(Base):
#     """Tenant commercial subscription (public schema)."""

#     __tablename__ = "subscriptions"
#     __table_args__ = ({"schema": "public"},)

#     id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
#     tenant_id: Mapped[int] = mapped_column(
#         Integer,
#         ForeignKey("public.tenants.id", ondelete="CASCADE"),
#         unique=True,
#         nullable=False,
#     )
#     plan_id: Mapped[int] = mapped_column(
#         Integer,
#         ForeignKey("public.plans.id", ondelete="RESTRICT"),
#         nullable=False,
#     )
#     # TRIALING | ACTIVE | PAST_DUE | CANCELED | UNPAID
#     status: Mapped[str] = mapped_column(String(20), nullable=False, default="TRIALING")
#     external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
#     current_period_start: Mapped[datetime | None] = mapped_column(
#         DateTime(timezone=True), nullable=True
#     )
#     current_period_end: Mapped[datetime | None] = mapped_column(
#         DateTime(timezone=True), nullable=True
#     )
#     cancel_at_period_end: Mapped[bool] = mapped_column(
#         Boolean, nullable=False, default=False, server_default=func.cast("false", Boolean)
#     )
#     seats_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
#     # NEW (migration 0004) — integration mode active for this subscription,
#     # used by billing_service to compute the effective monthly price.
#     # "platform_managed" | "tenant_managed" (default).
#     integration_mode: Mapped[str] = mapped_column(
#         String(32),
#         nullable=False,
#         default="tenant_managed",
#         server_default="tenant_managed",
#     )
#     # NEW (migration 0004) — plan.price_monthly_cents + delta from
#     # Plan.feature_flags.integration_path_pricing.<mode>_delta_cents.
#     # Stored on the row so historical invoices remain accurate if the
#     # plan's pricing config changes later.
#     effective_price_cents: Mapped[int | None] = mapped_column(
#         Integer, nullable=True
#     )
#     created_at: Mapped[datetime] = mapped_column(
#         DateTime(timezone=True), nullable=False, server_default=func.now()
#     )
#     updated_at: Mapped[datetime] = mapped_column(
#         DateTime(timezone=True),
#         nullable=False,
#         server_default=func.now(),
#         onupdate=func.now(),
#     )


# __all__ = ["Subscription"]

"""
subscription.py — Tenant subscription record (public schema).

One row per tenant (1:1 with public.tenants). Tracks the active Plan, the
external Stripe subscription id (if any), the current billing period, and
the seat-usage counter used to enforce Plan.seat_limit on user create.

Status lifecycle mirrors Stripe's subscription states so a future flip
from MockProvider to StripeProvider requires no schema change.
"""
from __future__ import annotations

from datetime import datetime

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column


class Subscription(Base):
    """Tenant commercial subscription (public schema)."""

    __tablename__ = "subscriptions"
    __table_args__ = ({"schema": "public"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            # FIX: was "public.tenants.id" — the Tenant PK column is tenant_id, not id.
            # use_alter=True defers FK resolution to DDL time so SQLAlchemy does not
            # walk the cross-schema FK graph at flush/commit time (same fix as
            # tenant_signup_requests.tenant_id — see models/tenant_signup.py).
            "public.tenants.tenant_id",
            ondelete="CASCADE",
            use_alter=True,
            name="fk_subscriptions_tenant_id",
        ),
        unique=True,
        nullable=False,
    )
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "public.plans.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_subscriptions_plan_id",
        ),
        nullable=False,
    )
    # TRIALING | ACTIVE | PAST_DUE | CANCELED | UNPAID
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="TRIALING")
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.cast("false", Boolean)
    )
    seats_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # NEW (migration 0004) — integration mode active for this subscription,
    # used by billing_service to compute the effective monthly price.
    # "platform_managed" | "tenant_managed" (default).
    integration_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="tenant_managed",
        server_default="tenant_managed",
    )
    # NEW (migration 0004) — plan.price_monthly_cents + delta from
    # Plan.feature_flags.integration_path_pricing.<mode>_delta_cents.
    # Stored on the row so historical invoices remain accurate if the
    # plan's pricing config changes later.
    effective_price_cents: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["Subscription"]
