"""
public.py — Unauthenticated public landing-page data router.

Endpoints (no auth, no tenant — TenantMiddleware-exempt via prefix):
  GET  /public/landing        → product description + features + stats
  GET  /public/plans          → active commercial plans
  GET  /public/contact-info   → email/phone/address/support hours
  POST /public/contact        → contact-form submission (202 Accepted)
  GET  /public/subdomain-check → check if a subdomain/slug is available
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_public
from app.core.config import get_settings
from app.features.subdomain.service import is_slug_available
from app.models.contact_message import ContactMessage
from app.models.plan import Plan

router = APIRouter(prefix="/public", tags=["Public"])


# ── Schemas (defined inline — app/schemas/* is out of ownership scope) ────────


class ProductInfo(BaseModel):
    name: str
    tagline: str
    description: str
    features: list[str]


class PlatformStats(BaseModel):
    tenants: int
    users: int
    messages_sent: int


class LandingResponse(BaseModel):
    product: ProductInfo
    stats: PlatformStats


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    display_name: str
    description: str
    price_monthly_cents: int
    price_yearly_cents: int
    seat_limit: int
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    sort_order: int


class ContactInfoResponse(BaseModel):
    email: str
    sales_email: str
    phone: str
    address: str
    support_hours: str


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    company: str | None = Field(default=None, max_length=255)
    message: str = Field(..., min_length=1, max_length=5000)


class ContactResponse(BaseModel):
    accepted: bool = True
    message: str = "Contact request received — our team will be in touch shortly."


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/landing", response_model=LandingResponse)
async def get_landing(
    db: AsyncSession = Depends(get_db_public),
) -> LandingResponse:
    """Public landing-page payload — product info + platform stats."""
    product = ProductInfo(
        name="OUTRENA",
        tagline="The AI-Powered Outreach Operating System.",
        description=(
            "OUTRENA unifies prospecting, outreach, pipeline, and optimization "
            "into one AI-native workflow. Built for B2B revenue teams that need "
            "repeatable, measurable, multi-channel sequences at scale."
        ),
        features=[
            "AI ICP discovery & lookalike prospecting",
            "Multi-channel sequences (email + LinkedIn)",
            "Autopilot pipeline generation",
            "Real-time intent signals & job-change alerts",
            "A/B testing for subject lines & email bodies",
            "Optimization rules engine",
            "Per-tenant data isolation (schema-per-tenant)",
            "SOC2-aligned audit logging",
        ],
    )
    try:
        tenants = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM public.tenants "
                    "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
                )
            )
        ).scalar() or 0
        users = (
            await db.execute(
                text("SELECT COALESCE(SUM(seats_used), 0) FROM public.subscriptions")
            )
        ).scalar() or 0
        # messages_sent: real metric would join sequence_email rows across
        # tenant schemas. For now return 0 — the frontend renders the
        # placeholder; the wiring is a future telemetry task.
        messages_sent = 0
    except Exception:  # noqa: BLE001 — landing page must not crash on DB error
        tenants, users, messages_sent = 0, 0, 0

    return LandingResponse(
        product=product,
        stats=PlatformStats(
            tenants=int(tenants), users=int(users), messages_sent=int(messages_sent)
        ),
    )


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(
    db: AsyncSession = Depends(get_db_public),
) -> list[PlanResponse]:
    """Public list of active commercial plans."""
    rows = (
        await db.execute(
            select(Plan)
            .where(Plan.is_active.is_(True))
            .order_by(Plan.sort_order)
        )
    ).scalars().all()
    return [
        PlanResponse(
            id=r.id,
            name=r.name,
            display_name=r.display_name,
            description=r.description,
            price_monthly_cents=r.price_monthly_cents,
            price_yearly_cents=r.price_yearly_cents,
            seat_limit=r.seat_limit,
            feature_flags=r.feature_flags or {},
            sort_order=r.sort_order,
        )
        for r in rows
    ]


@router.get("/contact-info", response_model=ContactInfoResponse)
async def get_contact_info() -> ContactInfoResponse:
    """Public contact info (sourced from settings)."""
    s = get_settings()
    return ContactInfoResponse(
        email=s.PUBLIC_SUPPORT_EMAIL,
        sales_email=s.PUBLIC_SALES_EMAIL,
        phone=s.PUBLIC_SUPPORT_PHONE,
        address=s.PUBLIC_SUPPORT_ADDRESS,
        support_hours=s.PUBLIC_SUPPORT_HOURS,
    )


@router.post(
    "/contact",
    response_model=ContactResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_contact(
    body: ContactRequest,
    db: AsyncSession = Depends(get_db_public),
) -> ContactResponse:
    """Submit a contact-form message. Stored in public.contact_messages."""
    row = ContactMessage(
        name=body.name,
        email=str(body.email),
        company=body.company,
        message=body.message,
    )
    db.add(row)
    await db.commit()
    return ContactResponse()


class SubdomainCheckResponse(BaseModel):
    available: bool
    reason: str | None = None


@router.get("/subdomain-check", response_model=SubdomainCheckResponse)
async def check_subdomain(
    subdomain: str = Query(..., min_length=1, max_length=63, description="Proposed subdomain/slug"),
    db: AsyncSession = Depends(get_db_public),
) -> SubdomainCheckResponse:
    """Check whether a proposed subdomain (slug) is available for allocation."""
    available, reason = await is_slug_available(subdomain, db)
    return SubdomainCheckResponse(available=available, reason=reason)


__all__ = ["router"]
