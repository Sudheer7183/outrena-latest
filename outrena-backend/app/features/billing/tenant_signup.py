"""
tenant_signup.py — Public self-serve signup endpoints.

Routes (all under /api/v1/tenant-signup, exempt from TenantMiddleware):

  POST /api/v1/tenant-signup
    Submit a new signup request. No auth required.
    Body: TenantSignupSubmitRequest
    Response 201: TenantSignupSubmitResponse

  GET /api/v1/tenant-signup/plans
    Return the active plan catalog for the signup form.
    No auth required.
    Response 200: list[PlanCatalogItem]

  GET /api/v1/tenant-signup/check-subdomain?subdomain=<value>
    Real-time availability check for the subdomain field.
    No auth required.
    Response 200: SubdomainAvailabilityResponse

These endpoints are intentionally unauthenticated — they are the entry
point for prospective tenants who do not yet have an account.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.features.billing.tenant_signup_service import TenantSignupService
from app.utils.slug import validate_slug, SlugValidationError

router = APIRouter(prefix="/tenant-signup", tags=["signup"])


# ── DB dependency (public schema, no tenant required) ───────────────────────

async def _get_db_public() -> AsyncGenerator[AsyncSession, None]:
    """Public-schema session — no tenant middleware resolution needed."""
    async with AsyncSessionLocal() as session:
        await session.execute(text('SET search_path TO "public"'))
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Request / response schemas ───────────────────────────────────────────────

class TenantSignupSubmitRequest(BaseModel):
    company_name: str
    subdomain: str
    owner_email: EmailStr
    owner_first_name: str
    owner_last_name: str
    plan_id: int
    integration_mode: str = "tenant_managed"

    @field_validator("subdomain")
    @classmethod
    def _validate_subdomain(cls, value: str) -> str:
        try:
            return validate_slug(value.strip().lower())
        except SlugValidationError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("integration_mode")
    @classmethod
    def _validate_integration_mode(cls, value: str) -> str:
        if value not in ("platform_managed", "tenant_managed"):
            raise ValueError(
                "integration_mode must be 'platform_managed' or 'tenant_managed'."
            )
        return value

    @field_validator("company_name", "owner_first_name", "owner_last_name")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field must not be blank.")
        return value.strip()


class TenantSignupSubmitResponse(BaseModel):
    id: int
    subdomain: str
    status: str
    created_at: datetime
    message: str


class PlanCatalogItem(BaseModel):
    id: int
    name: str
    display_name: str
    description: str
    price_monthly_cents: int
    price_yearly_cents: int
    seat_limit: int
    feature_flags: dict[str, Any]


class SubdomainAvailabilityResponse(BaseModel):
    subdomain: str
    available: bool
    reason: str | None


# ── Endpoints ────────────────────────────────────────────────────────────────

_service = TenantSignupService()


@router.post(
    "",
    response_model=TenantSignupSubmitResponse,
    status_code=201,
    summary="Submit a self-serve tenant signup request",
)
async def submit_signup(
    body: TenantSignupSubmitRequest,
    db: AsyncSession = Depends(_get_db_public),
) -> TenantSignupSubmitResponse:
    """
    Submit a new tenant signup request. No authentication required.

    The request is queued as PENDING_APPROVAL. A SUPER_ADMIN must approve
    it via /api/platform/admin/signups/{id}/approve to trigger provisioning.
    The submitter will receive an email invitation when their account is ready.
    """
    result = await _service.create_signup(
        db,
        company_name=body.company_name,
        subdomain=body.subdomain,
        owner_email=str(body.owner_email),
        owner_first_name=body.owner_first_name,
        owner_last_name=body.owner_last_name,
        plan_id=body.plan_id,
        integration_mode=body.integration_mode,
    )
    return TenantSignupSubmitResponse(**result)


@router.get(
    "/plans",
    response_model=list[PlanCatalogItem],
    summary="List active plans for the signup form",
)
async def list_plans(
    db: AsyncSession = Depends(_get_db_public),
) -> list[PlanCatalogItem]:
    """Return all active plans ordered by sort_order for the plan selector."""
    plans = await _service.get_plan_catalog(db)
    return [PlanCatalogItem(**p) for p in plans]


@router.get(
    "/check-subdomain",
    response_model=SubdomainAvailabilityResponse,
    summary="Check subdomain availability in real time",
)
async def check_subdomain(
    subdomain: str = Query(..., min_length=3, max_length=63),
    db: AsyncSession = Depends(_get_db_public),
) -> SubdomainAvailabilityResponse:
    """
    Returns whether a subdomain is available for use as a tenant identifier.
    Used by the signup form for real-time validation as the user types.
    """
    result = await _service.check_subdomain_availability(db, subdomain)
    return SubdomainAvailabilityResponse(**result)
