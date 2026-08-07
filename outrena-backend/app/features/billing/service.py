"""
billing_service.py — Subscription lifecycle + seat-limit enforcement.

Owns the Subscription table (public) and the bridge to Plan (public).
Enforces Plan.seat_limit on user create by exposing
``check_seat_available(tenant_id)`` for user_management_service to call
before creating a Keycloak user.

The actual payment provider (Stripe / Mock) is delegated to
payment_service.PaymentService; this service stays provider-agnostic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.subscription import Subscription

logger = structlog.get_logger(__name__)


_TRIAL_DAYS = 14


class BillingService:
    """Tenant subscription management."""

    # ── Plans ───────────────────────────────────────────────────────────────

    async def list_plans(self, db: AsyncSession) -> list[dict[str, Any]]:
        rows = (
            await db.execute(
                select(Plan)
                .where(Plan.is_active.is_(True))
                .order_by(Plan.sort_order)
            )
        ).scalars().all()
        return [self._plan_dict(p) for p in rows]

    # ── Subscription ────────────────────────────────────────────────────────

    async def get_subscription(
        self, db: AsyncSession, tenant_id: int
    ) -> dict[str, Any] | None:
        row = await self._fetch_sub(db, tenant_id)
        if row is None:
            return None
        return await self._sub_dict(db, row)

    async def subscribe(
        self,
        db: AsyncSession,
        tenant_id: int,
        plan_id: int,
        payment_method_id: str | None = None,
        *,
        integration_mode: str | None = None,
    ) -> dict[str, Any]:
        """Create or upgrade the tenant's subscription to ``plan_id``.

        For MockProvider (default) no payment_method_id is required — the
        subscription starts in TRIALING for _TRIAL_DAYS then transitions
        to ACTIVE. For StripeProvider, payment_method_id must be present
        and the actual Stripe subscription is created via payment_service.

        Phase 8 (dual-path integrations): when ``integration_mode`` is not
        provided, the tenant_config row is consulted; the effective monthly
        price is ``plan.price_monthly_cents`` + the delta configured under
        ``plan.feature_flags.integration_path_pricing.<mode>_delta_cents``.
        The resolved mode + effective price are stamped on the Subscription
        row so historical invoices remain accurate if the plan's pricing
        config changes later.
        """
        plan = (
            await db.execute(select(Plan).where(Plan.id == plan_id))
        ).scalar_one_or_none()
        if plan is None or not plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found."
            )

        # Phase 8 — resolve integration_mode + effective price.
        if integration_mode is None:
            integration_mode = await self._resolve_integration_mode(db, tenant_id)
        if integration_mode not in ("platform_managed", "tenant_managed"):
            # Defense-in-depth: a bad client-supplied mode falls back to the
            # default rather than crashing the subscription.
            logger.warning(
                "billing.invalid_integration_mode",
                tenant_id=tenant_id,
                integration_mode=integration_mode,
            )
            integration_mode = "tenant_managed"
        delta_cents = self._path_pricing_delta(plan, integration_mode)
        effective_price_cents = plan.price_monthly_cents + delta_cents

        sub = await self._fetch_sub(db, tenant_id)
        now = datetime.now(timezone.utc)
        period_start = now
        period_end = now + timedelta(days=_TRIAL_DAYS)

        # Delegate external subscription creation to the payment service.
        # Phase 8: pass the EFFECTIVE price (with path delta) to the
        # provider so Stripe / Mock charge the right amount.
        from app.features.billing.payment_service import get_payment_service
        payment = get_payment_service()
        external_id: str | None = None
        client_secret: str | None = None
        try:
            ext = await payment.create_subscription(
                tenant_id=tenant_id,
                plan_id=plan_id,
                price_cents=effective_price_cents,
                payment_method_id=payment_method_id,
            )
            if isinstance(ext, dict):
                external_id = ext.get("external_id")
                client_secret = ext.get("client_secret")
        except Exception as exc:  # noqa: BLE001 — provider errors must not crash subscribe
            logger.error("billing.provider_failed", tenant_id=tenant_id, error=str(exc))

        if sub is None:
            sub = Subscription(
                tenant_id=tenant_id,
                plan_id=plan_id,
                status="TRIALING",
                external_id=external_id,
                current_period_start=period_start,
                current_period_end=period_end,
                cancel_at_period_end=False,
                seats_used=0,
                integration_mode=integration_mode,
                effective_price_cents=effective_price_cents,
            )
            db.add(sub)
        else:
            sub.plan_id = plan_id
            sub.status = "ACTIVE" if external_id else "TRIALING"
            if external_id:
                sub.external_id = external_id
            sub.current_period_start = period_start
            sub.current_period_end = period_end
            sub.cancel_at_period_end = False
            # Phase 8: update mode + effective price on plan change.
            sub.integration_mode = integration_mode
            sub.effective_price_cents = effective_price_cents
        await db.commit()
        sub = await db.get(Subscription, sub.id)
        result = await self._sub_dict(db, sub)
        if client_secret is not None:
            result["client_secret"] = client_secret
        return result

    async def cancel_subscription(self, db: AsyncSession, tenant_id: int) -> None:
        sub = await self._fetch_sub(db, tenant_id)
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription for this tenant.",
            )
        sub.cancel_at_period_end = True
        sub.status = "CANCELED"
        # Notify the payment provider to cancel at period end (MockProvider no-ops).
        from app.features.billing.payment_service import get_payment_service
        try:
            await get_payment_service().cancel_subscription(sub.external_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("billing.cancel_provider_failed", tenant_id=tenant_id, error=str(exc))
        await db.commit()

    async def update_payment_method(
        self, db: AsyncSession, tenant_id: int, payment_method_id: str
    ) -> None:
        sub = await self._fetch_sub(db, tenant_id)
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription for this tenant.",
            )
        from app.features.billing.payment_service import get_payment_service
        try:
            await get_payment_service().update_payment_method(
                sub.external_id, payment_method_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("billing.pm_update_failed", tenant_id=tenant_id, error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Payment provider rejected payment method: {exc}",
            ) from exc

    # ── Invoices ────────────────────────────────────────────────────────────

    async def get_invoices(
        self, db: AsyncSession, tenant_id: int
    ) -> list[dict[str, Any]]:
        sub = await self._fetch_sub(db, tenant_id)
        if sub is None or not sub.external_id:
            return []
        from app.features.billing.payment_service import get_payment_service
        try:
            return await get_payment_service().list_invoices(sub.external_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("billing.invoice_list_failed", tenant_id=tenant_id, error=str(exc))
            return []

    # ── Seat-limit enforcement (called by user_management_service) ──────────

    async def check_seat_available(
        self, db: AsyncSession, tenant_id: int
    ) -> None:
        """Raise HTTP 402 if adding one more seat would exceed the plan limit."""
        sub = await self._fetch_sub(db, tenant_id)
        if sub is None:
            # No subscription record yet — allow (the tenant is in trial).
            return
        plan = (
            await db.execute(select(Plan).where(Plan.id == sub.plan_id))
        ).scalar_one_or_none()
        if plan is None:
            return
        if plan.seat_limit > 0 and sub.seats_used >= plan.seat_limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Seat limit reached for plan '{plan.name}' "
                    f"({sub.seats_used}/{plan.seat_limit}). Upgrade the plan "
                    "to add more users."
                ),
            )

    async def increment_seat(self, db: AsyncSession, tenant_id: int) -> None:
        sub = await self._fetch_sub(db, tenant_id)
        if sub is None:
            return
        sub.seats_used = (sub.seats_used or 0) + 1
        await db.commit()

    async def decrement_seat(self, db: AsyncSession, tenant_id: int) -> None:
        sub = await self._fetch_sub(db, tenant_id)
        if sub is None:
            return
        if sub.seats_used and sub.seats_used > 0:
            sub.seats_used -= 1
            await db.commit()

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    async def _fetch_sub(db: AsyncSession, tenant_id: int) -> Subscription | None:
        return (
            await db.execute(
                select(Subscription).where(Subscription.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def _resolve_integration_mode(
        db: AsyncSession, tenant_id: int
    ) -> str:
        """Look up tenant_config.integration_mode for this tenant.

        Falls back to "tenant_managed" if the row is missing or the column
        is NULL (defensive — every tenant_config row should have a value
        after migration 0004 back-fills the default).
        """
        row = (
            await db.execute(
                text(
                    "SELECT integration_mode FROM public.tenant_config "
                    "WHERE tenant_id = :tid"
                ),
                {"tid": tenant_id},
            )
        ).fetchone()
        if row is None:
            return "tenant_managed"
        return row.integration_mode or "tenant_managed"

    @staticmethod
    def _path_pricing_delta(plan: Plan, integration_mode: str) -> int:
        """Return the per-month delta-cents for the given integration mode.

        Reads ``plan.feature_flags.integration_path_pricing.<mode>_delta_cents``.
        Defaults to 0 when the key is absent (backward-compat with plans
        seeded before Phase 8).
        """
        flags = plan.feature_flags or {}
        if not isinstance(flags, dict):
            return 0
        path_pricing = flags.get("integration_path_pricing") or {}
        if not isinstance(path_pricing, dict):
            return 0
        delta = path_pricing.get(f"{integration_mode}_delta_cents", 0)
        try:
            return int(delta or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _plan_dict(p: Plan) -> dict[str, Any]:
        return {
            "id": p.id,
            "name": p.name,
            "display_name": p.display_name,
            "description": p.description,
            "price_monthly_cents": p.price_monthly_cents,
            "price_yearly_cents": p.price_yearly_cents,
            "seat_limit": p.seat_limit,
            "feature_flags": p.feature_flags or {},
            "sort_order": p.sort_order,
        }

    async def _sub_dict(
        self, db: AsyncSession, sub: Subscription
    ) -> dict[str, Any]:
        plan = (
            await db.execute(select(Plan).where(Plan.id == sub.plan_id))
        ).scalar_one_or_none()
        return {
            "id": sub.id,
            "tenant_id": sub.tenant_id,
            "plan": self._plan_dict(plan) if plan else None,
            "status": sub.status,
            "external_id": sub.external_id,
            "current_period_start": sub.current_period_start,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "seats_used": sub.seats_used,
            "seat_limit": plan.seat_limit if plan else None,
            # Phase 8 — surface integration mode + effective price.
            "integration_mode": getattr(sub, "integration_mode", None),
            "effective_price_cents": getattr(sub, "effective_price_cents", None),
            "created_at": sub.created_at,
            "updated_at": sub.updated_at,
        }


__all__ = ["BillingService"]
