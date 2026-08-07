"""
tenant_signup_service.py — Self-serve tenant signup request lifecycle.

Prospective tenants submit a signup request from the public landing page
(POST /api/v1/tenant-signup). The request sits in PENDING_APPROVAL until
a SUPER_ADMIN reviews it via /platform/admin/signups/{id}/approve or
/reject. The actual provisioning (calling TenantProvisioningService) is
done by platform_admin_service.approve_signup — this service only owns
the queue row + the public status check.
"""
from __future__ import annotations

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_signup import TenantSignupRequest
from app.features.subdomain.service import is_slug_available

logger = structlog.get_logger(__name__)


class TenantSignupService:
    """Create + read tenant signup requests."""

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
    ) -> int:
        """Create a PENDING_APPROVAL signup request. Returns the new row id.

        409 if the subdomain is already allocated or already requested by a
        pending signup.
        """
        from fastapi import HTTPException, status

        subdomain = subdomain.strip().lower()
        # Normalize + validate integration_mode (defense-in-depth).
        if integration_mode not in ("platform_managed", "tenant_managed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "integration_mode must be 'platform_managed' or "
                    "'tenant_managed'."
                ),
            )
        available, reason = await is_slug_available(subdomain, db)
        if not available:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)

        # Also block if a PENDING_APPROVAL signup already holds this subdomain.
        existing = await db.execute(
            text(
                "SELECT id FROM public.tenant_signup_requests "
                "WHERE subdomain = :slug AND status = 'PENDING_APPROVAL'"
            ),
            {"slug": subdomain},
        )
        if existing.fetchone() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subdomain '{subdomain}' is already requested and pending review.",
            )

        row = TenantSignupRequest(
            company_name=company_name,
            subdomain=subdomain,
            owner_email=owner_email,
            owner_first_name=owner_first_name,
            owner_last_name=owner_last_name,
            plan_id=plan_id,
            status="PENDING_APPROVAL",
            integration_mode=integration_mode,
        )
        db.add(row)
        await db.commit()
        row = await db.get(TenantSignupRequest, row.id)
        logger.info(
            "tenant_signup.created",
            signup_id=row.id,
            subdomain=subdomain,
            company=company_name,
            integration_mode=integration_mode,
        )
        # Notification: in production this would push to email/Slack. Today
        # it just lands in the structlog stream so the platform team can
        # triage from the admin UI without wiring a notification pipeline.
        return row.id

    async def get_signup_status(
        self, db: AsyncSession, signup_id: int
    ) -> dict[str, object]:
        """Return the public status view of a signup (no PII for rejected)."""
        from fastapi import HTTPException, status
        row = (
            await db.execute(
                select(TenantSignupRequest).where(
                    TenantSignupRequest.id == signup_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signup request not found.",
            )
        # Look up tenant slug if provisioned.
        tenant_slug: str | None = None
        if row.tenant_id is not None:
            ts = await db.execute(
                text("SELECT slug FROM public.tenants WHERE tenant_id = :tid"),
                {"tid": row.tenant_id},
            )
            t = ts.fetchone()
            if t is not None:
                tenant_slug = t.slug
        return {
            "signup_id": row.id,
            "status": row.status,
            "tenant_slug": tenant_slug,
            "rejection_reason": row.rejection_reason if row.status == "REJECTED" else None,
            "created_at": row.created_at,
        }


__all__ = ["TenantSignupService"]
