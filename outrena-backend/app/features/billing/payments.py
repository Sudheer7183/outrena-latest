"""
payments.py — Stripe webhook receiver (HMAC-verified, no tenant context).

Endpoints (no auth — signature-verified by payment_service):
  POST /payments/webhook   → raw body + Stripe-Signature header → 200

Dispatches verified events to BillingService via the payment_service's
internal dispatcher (mock provider just acknowledges; stripe provider
verifies the signature and triggers subscription state transitions).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_public
from app.features.billing.payment_service import get_payment_service

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/webhook", response_class=Response, status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db_public),
) -> Response:
    """Receive + dispatch a Stripe webhook.

    The raw body is read from the request stream so the signature can be
    verified against the exact bytes Stripe sent (no JSON re-serialization).
    """
    raw_body = await request.body()
    try:
        result = await get_payment_service().handle_webhook(raw_body, stripe_signature)
    except ValueError as exc:
        # Missing signature header — StripeProvider raises ValueError.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:  # noqa: BLE001 — webhook must not 500
        # Signature verification failure or dispatch error → 400 (Stripe
        # retries on anything >= 200, so we explicitly reject bad sigs).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook handling failed: {exc}",
        ) from exc
    # 200 + minimal body — Stripe just needs the status code.
    return Response(
        status_code=status.HTTP_200_OK,
        media_type="application/json",
        content=b'{"received":true}',
    )


__all__ = ["router"]
