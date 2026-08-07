"""
platform_admin_service.py — SUPER_ADMIN orchestration layer.

Aggregates across the public schema: signup queue review, tenant listing
with billing/seat metrics, platform-wide KPIs, and audit-log search.
Endpoints in app/api/routes/platform.py (under /platform/admin/*) call
into this service.

Approval flow:
  approve_signup(signup_id, reviewer) →
    1. Mark signup row APPROVED.
    2. Call TenantProvisioningService.provision_tenant() (the 6-step flow).
    3. Create a Subscription row tied to the requested plan.
    4. Mark signup PROVISIONED with tenant_id back-filled.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.tenant_signup import TenantSignupRequest
from app.services.audit_service import AuditService
from app.services.tenant_provisioning_service import TenantProvisioningService

logger = structlog.get_logger(__name__)


class PlatformAdminService:
    """Orchestrates platform-wide admin operations."""

    # ── Signup queue ────────────────────────────────────────────────────────

    async def list_signups(
        self,
        db: AsyncSession,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(TenantSignupRequest).order_by(
            TenantSignupRequest.created_at.desc()
        )
        if status_filter:
            stmt = stmt.where(TenantSignupRequest.status == status_filter)
        rows = (await db.execute(stmt)).scalars().all()
        return [self._signup_dict(r) for r in rows]

    async def approve_signup(
        self,
        db: AsyncSession,
        signup_id: int,
        reviewer_sub: str,
    ) -> dict[str, Any]:
        """Approve a signup → provision tenant → create subscription."""
        signup = (
            await db.execute(
                select(TenantSignupRequest).where(
                    TenantSignupRequest.id == signup_id
                )
            )
        ).scalar_one_or_none()
        if signup is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signup request not found.",
            )
        if signup.status not in ("PENDING_APPROVAL", "APPROVED"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Signup is in terminal state '{signup.status}'.",
            )

        # Mark APPROVED first so a re-run after partial failure won't double-
        # provision — the next attempt sees APPROVED and skips to step 3.
        signup.status = "APPROVED"
        signup.reviewed_at = datetime.now(timezone.utc)
        signup.reviewed_by = reviewer_sub
        await db.commit()

        # Step 2 — full 6-step provisioning flow (creates schema, runs
        # migrations, seeds defaults + system roles, creates the IdP user).
        # Phase 8: forward the signup's requested integration_mode.
        provisioning = TenantProvisioningService()
        try:
            slug = await provisioning.provision_tenant(
                tenant_slug=signup.subdomain,
                tenant_name=signup.company_name,
                tenant_type="STANDARD",
                admin_email=signup.owner_email,
                admin_first_name=signup.owner_first_name,
                admin_last_name=signup.owner_last_name,
                temporary_password=None,
                send_invitation=True,
                db=db,
                integration_mode=getattr(signup, "integration_mode", "tenant_managed")
                or "tenant_managed",
            )
        except HTTPException:
            # Roll back to PENDING_APPROVAL so a reviewer can retry after fix.
            signup.status = "PENDING_APPROVAL"
            await db.commit()
            raise

        # Resolve the new tenant_id.
        tid_row = (
            await db.execute(
                text("SELECT tenant_id FROM public.tenants WHERE slug = :slug"),
                {"slug": slug},
            )
        ).fetchone()
        if tid_row is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Provisioning completed but tenant_id could not be resolved.",
            )
        tenant_id = tid_row.tenant_id

        # Step 3 — create the Subscription row tied to the requested plan.
        # Phase 8: also stamp the integration_mode + effective_price_cents
        # via BillingService.subscribe (which reads Plan.feature_flags
        # .integration_path_pricing delta + tenant_config.integration_mode).
        existing = (
            await db.execute(
                select(Subscription).where(Subscription.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if existing is None:
            # Look up the plan + delta so the subscription row captures
            # the effective price at signup time (historical accuracy).
            plan = (
                await db.execute(select(Plan).where(Plan.id == signup.plan_id))
            ).scalar_one_or_none()
            effective_cents = (
                plan.price_monthly_cents if plan else 0
            )
            integration_mode = (
                getattr(signup, "integration_mode", "tenant_managed")
                or "tenant_managed"
            )
            if plan is not None:
                flags = plan.feature_flags or {}
                path_pricing = (
                    flags.get("integration_path_pricing", {})
                    if isinstance(flags, dict)
                    else {}
                )
                delta = path_pricing.get(
                    f"{integration_mode}_delta_cents", 0
                )
                effective_cents = plan.price_monthly_cents + int(delta or 0)
            sub = Subscription(
                tenant_id=tenant_id,
                plan_id=signup.plan_id,
                status="TRIALING",
                seats_used=1,
                current_period_start=datetime.now(timezone.utc),
                integration_mode=integration_mode,
                effective_price_cents=effective_cents,
            )
            db.add(sub)
            await db.commit()

        # Step 4 — flip signup to PROVISIONED with tenant_id back-filled.
        signup.status = "PROVISIONED"
        signup.tenant_id = tenant_id
        await db.commit()

        await AuditService().log(
            db,
            actor_user_id=reviewer_sub,
            actor_role="SUPER_ADMIN",
            tenant_slug=slug,
            action="signup.approved",
            target_type="tenant_signup_request",
            target_id=str(signup_id),
            metadata={"tenant_id": tenant_id, "slug": slug},
        )
        logger.info(
            "platform_admin.signup_approved",
            signup_id=signup_id,
            tenant_id=tenant_id,
            slug=slug,
        )
        return {
            "signup_id": signup.id,
            "status": "PROVISIONED",
            "tenant_slug": slug,
            "tenant_id": tenant_id,
            "provisioned": True,
        }

    async def reject_signup(
        self,
        db: AsyncSession,
        signup_id: int,
        reason: str,
        reviewer_sub: str,
    ) -> dict[str, Any]:
        signup = (
            await db.execute(
                select(TenantSignupRequest).where(
                    TenantSignupRequest.id == signup_id
                )
            )
        ).scalar_one_or_none()
        if signup is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signup request not found.",
            )
        if signup.status != "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Signup is in state '{signup.status}' — cannot reject.",
            )
        signup.status = "REJECTED"
        signup.rejection_reason = reason
        signup.reviewed_at = datetime.now(timezone.utc)
        signup.reviewed_by = reviewer_sub
        await db.commit()
        await AuditService().log(
            db,
            actor_user_id=reviewer_sub,
            actor_role="SUPER_ADMIN",
            tenant_slug=None,
            action="signup.rejected",
            target_type="tenant_signup_request",
            target_id=str(signup_id),
            metadata={"reason": reason},
        )
        return {"signup_id": signup.id, "status": "REJECTED", "reason": reason}

    # ── Tenant listing with metrics ─────────────────────────────────────────

    async def list_tenants_with_metrics(
        self, db: AsyncSession
    ) -> list[dict[str, Any]]:
        """List all non-deleted tenants with their plan + seat info."""
        rows = (
            await db.execute(
                text(
                    "SELECT t.tenant_id, t.slug, t.schema_name, t.name, "
                    "t.tenant_type, t.status, t.created_at, "
                    "s.status AS sub_status, s.seats_used, "
                    "p.name AS plan_name, p.display_name AS plan_display_name, "
                    "p.seat_limit "
                    "FROM public.tenants t "
                    "LEFT JOIN public.subscriptions s ON s.tenant_id = t.tenant_id "
                    "LEFT JOIN public.plans p ON p.id = s.plan_id "
                    "WHERE t.deleted_at IS NULL "
                    "ORDER BY t.created_at DESC"
                )
            )
        ).fetchall()
        return [
            {
                "tenant_id": r.tenant_id,
                "slug": r.slug,
                "schema_name": r.schema_name,
                "name": r.name,
                "tenant_type": r.tenant_type,
                "status": r.status,
                "plan": r.plan_name,
                "plan_display_name": r.plan_display_name,
                "subscription_status": r.sub_status,
                "seats_used": r.seats_used or 0,
                "seats_limit": r.seat_limit,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    # ── Platform metrics ────────────────────────────────────────────────────

    async def platform_metrics(self, db: AsyncSession) -> dict[str, Any]:
        total_tenants = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM public.tenants "
                    "WHERE deleted_at IS NULL"
                )
            )
        ).scalar() or 0
        active_tenants = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM public.tenants "
                    "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
                )
            )
        ).scalar() or 0
        total_users = (
            await db.execute(
                text(
                    "SELECT COALESCE(SUM(seats_used), 0) FROM public.subscriptions"
                )
            )
        ).scalar() or 0
        mrr_cents = (
            await db.execute(
                text(
                    "SELECT COALESCE(SUM(p.price_monthly_cents), 0) "
                    "FROM public.subscriptions s "
                    "JOIN public.plans p ON p.id = s.plan_id "
                    "WHERE s.status IN ('ACTIVE', 'TRIALING', 'PAST_DUE')"
                )
            )
        ).scalar() or 0
        # Churn rate (rough 30-day): canceled / (active + canceled) in window.
        churn_rate = 0.0
        try:
            churn_row = (
                await db.execute(
                    text(
                        "SELECT "
                        "  SUM(CASE WHEN status='CANCELED' THEN 1 ELSE 0 END) AS canceled, "
                        "  COUNT(*) AS total "
                        "FROM public.subscriptions "
                        "WHERE updated_at > now() - interval '30 days'"
                    )
                )
            ).fetchone()
            if churn_row and churn_row.total:
                churn_rate = round((churn_row.canceled or 0) / churn_row.total, 4)
        except Exception:  # noqa: BLE001
            churn_rate = 0.0

        return {
            "total_tenants": int(total_tenants),
            "active_tenants": int(active_tenants),
            "total_users": int(total_users),
            "mrr_cents": int(mrr_cents),
            "mrr_dollars": round(int(mrr_cents) / 100.0, 2),
            "churn_rate": churn_rate,
        }

    # ── Audit-log search (passes through to AuditService) ───────────────────

    async def list_audit_logs(
        self,
        db: AsyncSession,
        *,
        limit: int = 100,
        tenant_slug: str | None = None,
        action: str | None = None,
    ) -> list[dict[str, Any]]:
        return await AuditService().list_logs(
            db,
            limit=limit,
            tenant_slug=tenant_slug,
            action=action,
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _signup_dict(r: TenantSignupRequest) -> dict[str, Any]:
        return {
            "id": r.id,
            "company_name": r.company_name,
            "subdomain": r.subdomain,
            "owner_email": r.owner_email,
            "owner_first_name": r.owner_first_name,
            "owner_last_name": r.owner_last_name,
            "plan_id": r.plan_id,
            "status": r.status,
            "rejection_reason": r.rejection_reason,
            "tenant_id": r.tenant_id,
            "reviewed_at": r.reviewed_at,
            "reviewed_by": r.reviewed_by,
            "created_at": r.created_at,
        }


__all__ = ["PlatformAdminService"]
