"""
tenant_signup_service.py — Self-serve signup request persistence layer.

Handles the public-facing POST /api/v1/tenant-signup endpoint. This is
deliberately thin: it validates inputs, persists the TenantSignupRequest
row, and returns. No provisioning happens here — a SUPER_ADMIN must
approve via PlatformAdminService.approve_signup().

Validation rules:
  - subdomain must pass slug validation (3-63 chars, lowercase alnum + hyphens)
  - subdomain must not already exist in public.tenants OR public.tenant_signup_requests
  - owner_email must be a valid email
  - plan_id must reference an active plan in public.plans

DB notes:
  - Uses get_db_public() — search_path is "public" for this session.
  - Calls db.flush() (NOT db.commit()) to get the server-generated id and
    created_at without releasing the connection; the caller (FastAPI dep)
    commits via session.commit() in the finally block of get_db_public().
  - Never calls db.refresh() after flush — captures id and created_at
    as plain values from the ORM object while the session is still open.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.tenant_signup import TenantSignupRequest
from app.utils.slug import SlugValidationError, validate_slug

logger = structlog.get_logger(__name__)


class TenantSignupService:
    """Persists and validates self-serve signup requests."""

    async def create_signup(
        self,
        db: AsyncSession,
        *,
        company_name: str,
        subdomain: str,
        owner_email: str,
        owner_first_name: str,
        owner_last_name: str,
        plan_id: int,
        integration_mode: str = "tenant_managed",
    ) -> dict[str, Any]:
        """
        Validate and persist a new signup request.

        Returns a dict with the new signup's id, subdomain, and status.
        Raises HTTP 422 for validation failures, 409 for conflicts.
        """
        # ── 1. Validate slug format ──────────────────────────────────────────
        try:
            subdomain = validate_slug(subdomain.strip().lower())
        except SlugValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        # ── 2. Validate integration_mode ─────────────────────────────────────
        if integration_mode not in ("platform_managed", "tenant_managed"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "integration_mode must be 'platform_managed' or 'tenant_managed'."
                ),
            )

        # ── 3. Check subdomain is not already taken by an active tenant ───────
        existing_tenant = (
            await db.execute(
                text(
                    "SELECT 1 FROM public.tenants WHERE slug = :slug AND deleted_at IS NULL"
                ),
                {"slug": subdomain},
            )
        ).fetchone()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subdomain '{subdomain}' is already taken.",
            )

        # ── 4. Check subdomain not pending in the signup queue ────────────────
        existing_request = (
            await db.execute(
                select(TenantSignupRequest).where(
                    TenantSignupRequest.subdomain == subdomain,
                    TenantSignupRequest.status.in_(
                        ("PENDING_APPROVAL", "APPROVED")
                    ),
                )
            )
        ).scalar_one_or_none()
        if existing_request:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A signup request for '{subdomain}' is already pending review."
                ),
            )

        # ── 5. Validate plan exists and is active ─────────────────────────────
        plan = (
            await db.execute(
                select(Plan).where(Plan.id == plan_id, Plan.is_active.is_(True))
            )
        ).scalar_one_or_none()
        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Plan id={plan_id} does not exist or is not active.",
            )

        # ── 6. Persist the signup request ─────────────────────────────────────
        signup = TenantSignupRequest(
            company_name=company_name.strip(),
            subdomain=subdomain,
            owner_email=owner_email.strip().lower(),
            owner_first_name=owner_first_name.strip(),
            owner_last_name=owner_last_name.strip(),
            plan_id=plan_id,
            status="PENDING_APPROVAL",
            integration_mode=integration_mode,
        )
        db.add(signup)

        # flush to populate server-generated columns (id, created_at) without
        # releasing the connection back to the pool (which would strip
        # search_path). The get_db_public() dependency commits on exit.
        await db.flush()

        # Capture plain values NOW — never call db.refresh() after commit.
        signup_id: int = signup.id
        signup_subdomain: str = signup.subdomain
        signup_status: str = signup.status
        signup_created_at: datetime = signup.created_at

        logger.info(
            "tenant_signup.created",
            signup_id=signup_id,
            subdomain=signup_subdomain,
            plan_id=plan_id,
        )

        return {
            "id": signup_id,
            "subdomain": signup_subdomain,
            "status": signup_status,
            "created_at": signup_created_at,
            "message": (
                "Your signup request has been received. "
                "You will receive an email once it has been reviewed."
            ),
        }

    async def get_plan_catalog(self, db: AsyncSession) -> list[dict[str, Any]]:
        """Return all active plans for the signup form's plan selector."""
        plans = (
            await db.execute(
                select(Plan)
                .where(Plan.is_active.is_(True))
                .order_by(Plan.sort_order.asc())
            )
        ).scalars().all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "display_name": p.display_name,
                "description": p.description,
                "price_monthly_cents": p.price_monthly_cents,
                "price_yearly_cents": p.price_yearly_cents,
                "seat_limit": p.seat_limit,
                "feature_flags": p.feature_flags,
            }
            for p in plans
        ]

    async def check_subdomain_availability(
        self, db: AsyncSession, subdomain: str
    ) -> dict[str, Any]:
        """
        Quick availability check used by the signup form's real-time
        subdomain field validator (GET /api/v1/tenant-signup/check-subdomain).
        """
        subdomain = subdomain.strip().lower()

        # Format validation first — gives a reason without hitting the DB.
        try:
            validate_slug(subdomain)
        except SlugValidationError as exc:
            return {"subdomain": subdomain, "available": False, "reason": str(exc)}

        # Active tenant check.
        taken_by_tenant = (
            await db.execute(
                text(
                    "SELECT 1 FROM public.tenants "
                    "WHERE slug = :slug AND deleted_at IS NULL"
                ),
                {"slug": subdomain},
            )
        ).fetchone()
        if taken_by_tenant:
            return {
                "subdomain": subdomain,
                "available": False,
                "reason": "This subdomain is already in use.",
            }

        # Pending signup check.
        pending = (
            await db.execute(
                select(TenantSignupRequest).where(
                    TenantSignupRequest.subdomain == subdomain,
                    TenantSignupRequest.status.in_(("PENDING_APPROVAL", "APPROVED")),
                )
            )
        ).scalar_one_or_none()
        if pending:
            return {
                "subdomain": subdomain,
                "available": False,
                "reason": "This subdomain has a pending signup request.",
            }

        return {"subdomain": subdomain, "available": True, "reason": None}


__all__ = ["TenantSignupService"]
