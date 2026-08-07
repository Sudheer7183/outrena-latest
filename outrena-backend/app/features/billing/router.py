"""
billing.py — Tenant subscription & billing router.

Endpoints (verify_tenant + Role.TENANT_ADMIN):
  GET   /billing/subscription    → current subscription + plan + seat info
  GET   /billing/plans           → active commercial plans
  POST  /billing/subscribe       → create or upgrade subscription
  POST  /billing/cancel          → cancel at period end (204)
  GET   /billing/invoices        → list invoices from payment provider
  POST  /billing/payment-method  → update default payment method
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user, require_role, verify_tenant
from app.schemas.auth import Role, TokenPayload
from app.features.billing.service import BillingService

router = APIRouter(prefix="/billing", tags=["Billing"])
_service = BillingService()


# ── Schemas ──────────────────────────────────────────────────────────────────


class PlanSummary(BaseModel):
    id: int
    name: str
    display_name: str
    description: str
    price_monthly_cents: int
    price_yearly_cents: int
    seat_limit: int
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    sort_order: int


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    plan: PlanSummary | None
    status: str
    external_id: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    seats_used: int
    seat_limit: int | None
    created_at: datetime
    updated_at: datetime
    client_secret: str | None = None


class SubscribeRequest(BaseModel):
    plan_id: int = Field(..., ge=1)
    payment_method_id: str | None = None


class SubscribeResponse(BaseModel):
    subscription_id: int
    status: str
    client_secret: str | None = None


class PaymentMethodRequest(BaseModel):
    payment_method_id: str = Field(..., min_length=1)


class InvoiceResponse(BaseModel):
    external_id: str | None
    amount_cents: int
    currency: str
    status: str | None
    created_at: Any | None
    invoice_pdf: str | None = None


def _tenant_id(token: TokenPayload, request) -> int:  # type: ignore[no-untyped-def]
    """Resolve the tenant_id from the resolved tenant on request.state."""
    from fastapi import HTTPException, status as _s
    tenant = getattr(request, "state", None) and getattr(request.state, "tenant", None)
    if tenant is None or not getattr(tenant, "tenant_id", None):
        raise HTTPException(
            status_code=_s.HTTP_400_BAD_REQUEST,
            detail="Tenant could not be resolved for this request.",
        )
    return int(tenant.tenant_id)


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/subscription", response_model=SubscriptionResponse | dict)
async def get_subscription(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> SubscriptionResponse | dict:
    """Return the tenant's current subscription, or an empty body if none."""
    tid = _tenant_id(token, request)
    sub = await _service.get_subscription(db, tid)
    if sub is None:
        return {"subscription": None}
    return SubscriptionResponse(**sub)


@router.get("/plans", response_model=list[PlanSummary])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> list[PlanSummary]:
    return [PlanSummary(**p) for p in await _service.list_plans(db)]


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(
    body: SubscribeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> SubscribeResponse:
    """Create or upgrade the tenant's subscription to ``plan_id``."""
    tid = _tenant_id(token, request)
    result = await _service.subscribe(
        db,
        tenant_id=tid,
        plan_id=body.plan_id,
        payment_method_id=body.payment_method_id,
    )
    return SubscribeResponse(
        subscription_id=result["id"],
        status=result["status"],
        client_secret=result.get("client_secret"),
    )


@router.post("/cancel", response_class=Response, status_code=status.HTTP_204_NO_CONTENT)
async def cancel(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    tid = _tenant_id(token, request)
    await _service.cancel_subscription(db, tid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> list[InvoiceResponse]:
    tid = _tenant_id(token, request)
    invoices = await _service.get_invoices(db, tid)
    return [InvoiceResponse(**inv) for inv in invoices]


@router.post("/payment-method", response_class=Response, status_code=status.HTTP_200_OK)
async def update_payment_method(
    body: PaymentMethodRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    tid = _tenant_id(token, request)
    await _service.update_payment_method(db, tid, body.payment_method_id)
    return Response(status_code=status.HTTP_200_OK)


__all__ = ["router"]
