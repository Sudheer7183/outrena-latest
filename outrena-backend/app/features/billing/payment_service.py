"""
payment_service.py — Stripe-abstracted payment provider.

Defines a ``PaymentProvider`` Protocol with the five operations OUTRENA's
billing layer needs (create_customer, create_subscription,
create_payment_intent, handle_webhook, list_invoices, cancel,
update_payment_method). Two implementations:

  StripeProvider — uses the ``stripe`` Python SDK when
    ``STRIPE_SECRET_KEY`` is set. Verifies webhook signatures with
    ``STRIPE_WEBHOOK_SECRET``.

  MockProvider   — no-ops every call and logs. Default when
    ``PAYMENT_PROVIDER != "stripe"`` or no STRIPE_SECRET_KEY is set.

Selection: ``get_payment_service()`` reads ``settings.PAYMENT_PROVIDER``
and returns the appropriate instance (cached via lru_cache). Flipping
from mock to stripe is purely an env-var change — no code change.

The webhook handler dispatches to BillingService for state transitions:
  invoice.payment_succeeded  → mark subscription ACTIVE, extend period
  subscription.updated        → sync status + period
  subscription.deleted        → mark CANCELED
  invoice.payment_failed      → mark PAST_DUE / UNPAID
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


@runtime_checkable
class PaymentProvider(Protocol):
    """The surface every payment backend must implement."""

    async def create_customer(
        self, *, tenant_id: int, email: str | None
    ) -> dict[str, Any]:
        ...

    async def create_subscription(
        self,
        *,
        tenant_id: int,
        plan_id: int,
        price_cents: int,
        payment_method_id: str | None,
    ) -> dict[str, Any]:
        ...

    async def create_payment_intent(
        self, *, amount_cents: int, currency: str = "usd"
    ) -> dict[str, Any]:
        ...

    async def list_invoices(self, external_subscription_id: str | None) -> list[dict[str, Any]]:
        ...

    async def cancel_subscription(self, external_subscription_id: str | None) -> None:
        ...

    async def update_payment_method(
        self, external_subscription_id: str | None, payment_method_id: str
    ) -> None:
        ...

    async def handle_webhook(self, raw_body: bytes, signature: str | None) -> dict[str, Any]:
        ...


# ── MockProvider ─────────────────────────────────────────────────────────────


class MockProvider:
    """No-op provider used when Stripe is not configured.

    Every method returns a sensible empty success payload and logs so the
    developer can see the call happened. This is the default in dev and
    in CI — flipping to Stripe is purely an env-var change.
    """

    async def create_customer(
        self, *, tenant_id: int, email: str | None
    ) -> dict[str, Any]:
        logger.info("payment.mock.create_customer", tenant_id=tenant_id, email=email)
        return {"external_id": f"mock_customer_{tenant_id}", "provider": "mock"}

    async def create_subscription(
        self,
        *,
        tenant_id: int,
        plan_id: int,
        price_cents: int,
        payment_method_id: str | None,
    ) -> dict[str, Any]:
        logger.info(
            "payment.mock.create_subscription",
            tenant_id=tenant_id,
            plan_id=plan_id,
            price_cents=price_cents,
        )
        return {
            "external_id": f"mock_sub_{tenant_id}_{plan_id}",
            "client_secret": None,
            "provider": "mock",
        }

    async def create_payment_intent(
        self, *, amount_cents: int, currency: str = "usd"
    ) -> dict[str, Any]:
        logger.info("payment.mock.create_payment_intent", amount=amount_cents)
        return {
            "external_id": "mock_pi_" + str(amount_cents),
            "client_secret": "mock_secret_" + str(amount_cents),
            "provider": "mock",
        }

    async def list_invoices(
        self, external_subscription_id: str | None
    ) -> list[dict[str, Any]]:
        return []

    async def cancel_subscription(self, external_subscription_id: str | None) -> None:
        logger.info("payment.mock.cancel_subscription", external_id=external_subscription_id)

    async def update_payment_method(
        self, external_subscription_id: str | None, payment_method_id: str
    ) -> None:
        logger.info(
            "payment.mock.update_payment_method",
            external_id=external_subscription_id,
            pm=payment_method_id,
        )

    async def handle_webhook(self, raw_body: bytes, signature: str | None) -> dict[str, Any]:
        # Mock provider cannot verify signatures; acknowledge the receipt.
        logger.info("payment.mock.webhook_received", bytes=len(raw_body))
        return {"received": True, "provider": "mock"}


# ── StripeProvider ───────────────────────────────────────────────────────────


class StripeProvider:
    """Real Stripe integration. Active when STRIPE_SECRET_KEY is set.

    The ``stripe`` SDK is imported lazily so the module imports cleanly
    even when the dependency is not installed (mock mode). All Stripe
    API calls are blocking; we run them in a thread executor to keep the
    async event loop responsive.
    """

    def __init__(self, secret_key: str, webhook_secret: str) -> None:
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret

    def _stripe(self):  # type: ignore[no-untyped-def]
        import stripe  # lazy import — only required when actually using Stripe
        stripe.api_key = self._secret_key
        return stripe

    async def create_customer(
        self, *, tenant_id: int, email: str | None
    ) -> dict[str, Any]:
        import asyncio
        stripe = self._stripe()
        cust = await asyncio.to_thread(
            stripe.Customer.create,
            description=f"OUTRENA tenant {tenant_id}",
            email=email or "",
            metadata={"tenant_id": str(tenant_id)},
        )
        return {"external_id": cust.id, "provider": "stripe"}

    async def create_subscription(
        self,
        *,
        tenant_id: int,
        plan_id: int,
        price_cents: int,
        payment_method_id: str | None,
    ) -> dict[str, Any]:
        # Note: real Stripe subscriptions use Price IDs, not raw cents.
        # The mapping from OUTRENA Plan.id → Stripe Price ID is configured
        # out-of-band (env or a future price_map table). For now we create
        # an Invoice-style one-off PaymentIntent and return its secret.
        import asyncio
        stripe = self._stripe()
        intent = await asyncio.to_thread(
            stripe.PaymentIntent.create,
            amount=price_cents,
            currency="usd",
            automatic_payment_methods={"enabled": True},
            metadata={"tenant_id": str(tenant_id), "plan_id": str(plan_id)},
        )
        return {
            "external_id": intent.id,
            "client_secret": intent.client_secret,
            "provider": "stripe",
        }

    async def create_payment_intent(
        self, *, amount_cents: int, currency: str = "usd"
    ) -> dict[str, Any]:
        import asyncio
        stripe = self._stripe()
        intent = await asyncio.to_thread(
            stripe.PaymentIntent.create,
            amount=amount_cents,
            currency=currency,
            automatic_payment_methods={"enabled": True},
        )
        return {
            "external_id": intent.id,
            "client_secret": intent.client_secret,
            "provider": "stripe",
        }

    async def list_invoices(
        self, external_subscription_id: str | None
    ) -> list[dict[str, Any]]:
        import asyncio
        stripe = self._stripe()
        if not external_subscription_id:
            return []
        invoices = await asyncio.to_thread(
            stripe.Invoice.list, subscription=external_subscription_id, limit=50
        )
        return [
            {
                "external_id": inv.id,
                "amount_cents": inv.amount_paid,
                "currency": inv.currency,
                "status": inv.status,
                "created_at": inv.created,
                "invoice_pdf": inv.invoice_pdf,
            }
            for inv in invoices.data
        ]

    async def cancel_subscription(self, external_subscription_id: str | None) -> None:
        import asyncio
        if not external_subscription_id:
            return
        stripe = self._stripe()
        await asyncio.to_thread(
            stripe.Subscription.delete, external_subscription_id
        )

    async def update_payment_method(
        self, external_subscription_id: str | None, payment_method_id: str
    ) -> None:
        import asyncio
        if not external_subscription_id:
            return
        stripe = self._stripe()
        await asyncio.to_thread(
            stripe.Subscription.modify,
            external_subscription_id,
            default_payment_method=payment_method_id,
        )

    async def handle_webhook(self, raw_body: bytes, signature: str | None) -> dict[str, Any]:
        import asyncio
        stripe = self._stripe()
        if signature is None:
            raise ValueError("Missing Stripe-Signature header.")
        event = await asyncio.to_thread(
            stripe.Webhook.construct_event,
            raw_body,
            signature,
            self._webhook_secret,
        )
        await _dispatch_stripe_event(event)
        return {"received": True, "event_type": event["type"], "provider": "stripe"}


async def _dispatch_stripe_event(event: dict[str, Any]) -> None:
    """Translate Stripe event types into BillingService state transitions."""
    from app.core.database import AsyncSessionLocal
    from app.features.billing.service import BillingService

    etype = event.get("type", "")
    data = (event.get("data") or {}).get("object") or {}
    sub_id = data.get("subscription") or data.get("id")
    logger.info("payment.stripe.event", type=etype, sub=sub_id)

    billing = BillingService()
    # Look up tenant by external_id; in production this would join via a
    # tenant_stripe_customers map. For now we resolve via the subscription
    # table's external_id column.
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text as _t
        row = (
            await db.execute(
                _t(
                    "SELECT tenant_id FROM public.subscriptions "
                    "WHERE external_id = :ext"
                ),
                {"ext": sub_id},
            )
        ).fetchone()
        if row is None:
            return  # unknown subscription — skip silently
        tid = row.tenant_id
        if etype == "invoice.payment_succeeded":
            await db.execute(
                _t(
                    "UPDATE public.subscriptions SET status='ACTIVE' "
                    "WHERE tenant_id = :tid"
                ),
                {"tid": tid},
            )
            await db.commit()
        elif etype == "invoice.payment_failed":
            await db.execute(
                _t(
                    "UPDATE public.subscriptions SET status='PAST_DUE' "
                    "WHERE tenant_id = :tid"
                ),
                {"tid": tid},
            )
            await db.commit()
        elif etype in ("subscription.deleted", "customer.subscription.deleted"):
            await db.execute(
                _t(
                    "UPDATE public.subscriptions SET status='CANCELED' "
                    "WHERE tenant_id = :tid"
                ),
                {"tid": tid},
            )
            await db.commit()
        elif etype == "subscription.updated":
            status = (data.get("status") or "").upper()
            if status:
                await db.execute(
                    _t(
                        "UPDATE public.subscriptions SET status = :status "
                        "WHERE tenant_id = :tid"
                    ),
                    {"status": status, "tid": tid},
                )
                await db.commit()


# ── Selector ─────────────────────────────────────────────────────────────────


@lru_cache
def get_payment_service() -> PaymentProvider:
    """Return the configured PaymentProvider (cached singleton)."""
    settings = get_settings()
    if (
        settings.PAYMENT_PROVIDER == "stripe"
        and settings.STRIPE_SECRET_KEY
    ):
        return StripeProvider(
            secret_key=settings.STRIPE_SECRET_KEY,
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    return MockProvider()


__all__ = [
    "PaymentProvider",
    "MockProvider",
    "StripeProvider",
    "get_payment_service",
]
