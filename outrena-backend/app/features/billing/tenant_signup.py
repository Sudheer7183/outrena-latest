"""
tenant_signup.py — Self-serve tenant signup request router.

Endpoints (no auth, no tenant):
  POST /tenant-signup                  → submit a signup request (201)
  GET  /tenant-signup/{id}/status      → poll for review status

Submitted requests sit in PENDING_APPROVAL until a SUPER_ADMIN approves
or rejects via /platform/admin/signups/{id}/approve|reject.

Phase 8 (dual-path integrations): the signup payload now carries an
optional ``integration_mode`` field ("platform_managed" |
"tenant_managed", default "tenant_managed") that flows through to
``tenant_config.integration_mode`` at provisioning time.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_public
from app.features.billing.tenant_signup_service import TenantSignupService
from app.utils.slug import validate_slug

router = APIRouter(prefix="/tenant-signup", tags=["Tenant Signup"])
_service = TenantSignupService()


class SignupRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    subdomain: str = Field(..., min_length=3, max_length=63)
    owner_email: EmailStr
    owner_first_name: str = Field(..., min_length=1, max_length=120)
    owner_last_name: str = Field(..., min_length=1, max_length=120)
    plan_id: int = Field(..., ge=1)
    # NEW (Phase 8) — requested integrations mode at signup time.
    # "platform_managed" | "tenant_managed" (default).
    integration_mode: str = Field(
        default="tenant_managed", pattern="^(platform_managed|tenant_managed)$"
    )

    @field_validator("subdomain")
    @classmethod
    def _slug_rules(cls, value: str) -> str:
        return validate_slug(value)


class SignupCreatedResponse(BaseModel):
    signup_id: int
    status: str = "pending_approval"


class SignupStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    signup_id: int
    status: str
    tenant_slug: str | None
    rejection_reason: str | None
    created_at: datetime


@router.post("", response_model=SignupCreatedResponse, status_code=status.HTTP_201_CREATED)
async def submit_signup(
    body: SignupRequest,
    db: AsyncSession = Depends(get_db_public),
) -> SignupCreatedResponse:
    """Submit a self-serve tenant signup request for SUPER_ADMIN review."""
    signup_id = await _service.create_signup(
        db,
        company_name=body.company_name,
        subdomain=body.subdomain,
        owner_email=str(body.owner_email),
        owner_first_name=body.owner_first_name,
        owner_last_name=body.owner_last_name,
        plan_id=body.plan_id,
        integration_mode=body.integration_mode,
    )
    return SignupCreatedResponse(signup_id=signup_id)


@router.get("/{signup_id}/status", response_model=SignupStatusResponse)
async def get_signup_status(
    signup_id: int,
    db: AsyncSession = Depends(get_db_public),
) -> SignupStatusResponse:
    """Poll the review status of a signup request."""
    result = await _service.get_signup_status(db, signup_id)
    return SignupStatusResponse(**result)


__all__ = ["router"]
