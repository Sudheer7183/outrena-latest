"""
gdpr.py — GDPR data-subject-request + consent + retention router.

Three endpoint tiers:

  1. PUBLIC (no auth, no tenant — TenantMiddleware-exempt via prefix):
       POST /gdpr/dsr                       submit a DSR
       GET  /gdpr/dsr/{dsr_id}/status       check DSR status

  2. AUTHENTICATED (within tenant, Role.TENANT_ADMIN):
       GET   /gdpr/dsrs                     list DSRs for this tenant
       POST  /gdpr/dsrs/{id}/process        trigger DSR processing
       POST  /gdpr/dsrs/{id}/complete       mark DSR complete
       POST  /gdpr/dsrs/{id}/reject         reject DSR
       GET   /gdpr/export/{dsr_id}          download the data export
       GET   /gdpr/consent/{email}          consent status (any auth)
       POST  /gdpr/consent/grant            record consent (any auth)
       POST  /gdpr/consent/withdraw         withdraw consent (any auth)
       GET   /gdpr/retention-status         retention policy status
       POST  /gdpr/retention/enforce        trigger retention enforcement

  3. PLATFORM (SUPER_ADMIN, TenantMiddleware-exempt):
       GET   /gdpr/platform/dsrs            all DSRs across all tenants
       GET   /gdpr/platform/retention-status retention status across all tenants

The public DSR endpoints accept anonymous submissions because data subjects
exercising their rights may NOT be platform users. Identity verification is
handled by the DPO out-of-band (see runbooks/13-data-subject-requests.md).

Rate-limit note: public DSR submission is rate-limited at the infrastructure
layer (nginx / WAF). At the application layer we log every submission with
the requester IP so the operator can spot abuse.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_db_public
from app.api.security import require_role, verify_tenant
from app.models.data_subject_request import DSR_STATUSES, DSR_TYPES, DataSubjectRequest  # noqa: F401  (DataSubjectRequest re-exported for tests)
from app.schemas.auth import Role, TokenPayload
from app.features.gdpr.service import GdprService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/gdpr", tags=["GDPR"])
_service = GdprService()


# ════════════════════════════════════════════════════════════════════════════
# Schemas
# ════════════════════════════════════════════════════════════════════════════


class DsrSubmitRequest(BaseModel):
    """Public body for POST /gdpr/dsr — no auth required."""

    email: EmailStr
    tenant_slug: str | None = Field(
        default=None,
        description="If omitted, auto-detected by searching tenants for the email.",
    )
    request_type: str = Field(
        ..., description="access | portability | rectification | erasure | restriction | objection"
    )
    details: dict[str, Any] | None = Field(
        default=None, description="Free-form JSON: clarification, corrections, etc."
    )


class DsrSubmitResponse(BaseModel):
    dsr_id: int
    status: str = "pending"


class DsrStatusResponse(BaseModel):
    dsr_id: int
    status: str
    request_type: str
    created_at: datetime
    completed_at: datetime | None = None
    export_url: str | None = None
    rejection_reason: str | None = None


class DsrListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_type: str
    email: str
    tenant_slug: str
    status: str
    assigned_to: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    completion_notes: str | None = None
    rejection_reason: str | None = None
    export_url: str | None = None


class DsrProcessResponse(BaseModel):
    dsr_id: int
    status: str
    message: str
    export_url: str | None = None


class DsrCompleteRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)


class DsrRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=4000)


class ConsentGrantRequest(BaseModel):
    prospect_id: str = Field(..., min_length=1)
    lawful_basis: str = Field(
        ..., description="consent | legitimate_interest | contract | legal_obligation | vital_interest | public_task"
    )
    consent_text: str = Field(..., min_length=1, max_length=4000)


class ConsentWithdrawRequest(BaseModel):
    email: EmailStr
    lawful_basis: str | None = Field(
        default=None,
        description="Withdraw a single lawful basis; omit to withdraw all bases.",
    )


class ConsentStatusResponse(BaseModel):
    email: str
    any_granted: bool
    all_withdrawn: bool
    consents: list[dict[str, Any]]


class RetentionStatusResponse(BaseModel):
    tenant_slug: str
    policies: dict[str, dict[str, Any]]


class RetentionEnforceResponse(BaseModel):
    tenant_slug: str
    results: dict[str, int]


# ════════════════════════════════════════════════════════════════════════════
# 1 — PUBLIC endpoints (no auth, no tenant)
# ════════════════════════════════════════════════════════════════════════════


@router.post(
    "/dsr",
    response_model=DsrSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_dsr(
    body: DsrSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_public),
) -> DsrSubmitResponse:
    """Submit a GDPR data-subject request. No authentication required.

    Data subjects exercising their rights may not be platform users — the
    endpoint accepts anonymous submissions and the DPO verifies identity
    out-of-band (see runbooks/13-data-subject-requests.md §identity-verification).
    """
    if body.request_type not in DSR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"request_type must be one of {list(DSR_TYPES)}",
        )

    # Basic abuse protection: log the requester IP for every public submission.
    # Real rate-limiting is enforced at the WAF / nginx layer.
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    logger.info(
        "gdpr.dsr_submitted_public",
        email=str(body.email),
        request_type=body.request_type,
        ip=ip,
    )

    try:
        dsr = await _service.submit_dsr(
            db,
            email=str(body.email),
            tenant_slug=body.tenant_slug,
            request_type=body.request_type,
            details=body.details,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return DsrSubmitResponse(dsr_id=dsr.id, status=dsr.status)


@router.get("/dsr/{dsr_id}/status", response_model=DsrStatusResponse)
async def get_dsr_status_public(
    dsr_id: int,
    db: AsyncSession = Depends(get_db_public),
) -> DsrStatusResponse:
    """Public DSR status check — lets the data subject track their request."""
    dsr = await _service.get_dsr_status(db, dsr_id)
    if dsr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "DSR not found.")
    return DsrStatusResponse(
        dsr_id=dsr.id,
        status=dsr.status,
        request_type=dsr.request_type,
        created_at=dsr.created_at,
        completed_at=dsr.completed_at,
        export_url=dsr.export_url,
        rejection_reason=dsr.rejection_reason,
    )


# ════════════════════════════════════════════════════════════════════════════
# 2 — AUTHENTICATED endpoints (within tenant)
# ════════════════════════════════════════════════════════════════════════════


@router.get("/dsrs", response_model=list[DsrListResponse])
async def list_dsrs(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> list[DsrListResponse]:
    """List DSRs for the caller's tenant. TENANT_ADMIN only."""
    verify_tenant(request, token)
    if status_filter is not None and status_filter not in DSR_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of {list(DSR_STATUSES)}",
        )
    rows = await _service.list_dsrs(
        db, tenant_slug=token.tenant_slug, status_filter=status_filter
    )
    return [DsrListResponse.model_validate(r) for r in rows]


@router.post("/dsrs/{dsr_id}/process", response_model=DsrProcessResponse)
async def process_dsr(
    dsr_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> DsrProcessResponse:
    """Trigger processing for a DSR. Dispatches to the right processor."""
    verify_tenant(request, token)
    dsr = await _service.get_dsr_status(db, dsr_id)
    if dsr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "DSR not found.")
    if dsr.tenant_slug != token.tenant_slug and token.role is not Role.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "DSR belongs to a different tenant.")
    try:
        updated = await _service.process_dsr(db, dsr_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DSR processing failed: {exc}",
        ) from exc
    return DsrProcessResponse(
        dsr_id=updated.id,
        status=updated.status,
        message=f"DSR {updated.request_type} processed.",
        export_url=updated.export_url,
    )


@router.post("/dsrs/{dsr_id}/complete", response_model=DsrListResponse)
async def complete_dsr(
    dsr_id: int,
    body: DsrCompleteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> DsrListResponse:
    """Mark a DSR as completed with optional notes."""
    verify_tenant(request, token)
    dsr = await _service.get_dsr_status(db, dsr_id)
    if dsr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "DSR not found.")
    if dsr.tenant_slug != token.tenant_slug and token.role is not Role.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "DSR belongs to a different tenant.")
    updated = await _service.complete_dsr(db, dsr_id, notes=body.notes or "")
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "DSR not found.")
    return DsrListResponse.model_validate(updated)


@router.post("/dsrs/{dsr_id}/reject", response_model=DsrListResponse)
async def reject_dsr(
    dsr_id: int,
    body: DsrRejectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> DsrListResponse:
    """Reject a DSR with a reason."""
    verify_tenant(request, token)
    dsr = await _service.get_dsr_status(db, dsr_id)
    if dsr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "DSR not found.")
    if dsr.tenant_slug != token.tenant_slug and token.role is not Role.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "DSR belongs to a different tenant.")
    updated = await _service.reject_dsr(db, dsr_id, body.reason)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "DSR not found.")
    return DsrListResponse.model_validate(updated)


@router.get("/export/{dsr_id}", response_class=JSONResponse)
async def download_dsr_export(
    dsr_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> JSONResponse:
    """Download the data export bundle for a DSR.

    Returns the full data bundle as JSON. The export is generated on-demand
    (not pre-stored) so it always reflects the current DB state at download
    time. For access requests, the data subject receives a signed URL
    pointing to this endpoint via out-of-band email.
    """
    verify_tenant(request, token)
    dsr = await _service.get_dsr_status(db, dsr_id)
    if dsr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "DSR not found.")
    if dsr.tenant_slug != token.tenant_slug and token.role is not Role.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "DSR belongs to a different tenant.")
    if dsr.status != "completed":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"DSR is not completed (status={dsr.status}). Process it first.",
        )

    bundle = await _service.export_user_data(dsr.tenant_slug, dsr.email)
    return JSONResponse(
        content=bundle,
        headers={
            "Content-Disposition": (
                f'attachment; filename="dsr-{dsr_id}-{dsr.email.replace("@", "_at_")}.json"'
            )
        },
    )


# ── Consent (within tenant) ──────────────────────────────────────────────────


@router.get("/consent/{email}", response_model=ConsentStatusResponse)
async def get_consent_status(
    email: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> ConsentStatusResponse:
    """Get the consent status for an email (within the caller's tenant)."""
    verify_tenant(request, token)
    status_dict = await _service.get_consent_status(db, email)
    return ConsentStatusResponse(**status_dict)


@router.post("/consent/grant", response_model=dict)
async def grant_consent(
    body: ConsentGrantRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """Record a consent grant for a prospect."""
    verify_tenant(request, token)
    # Look up the prospect's email (the caller passes prospect_id; we need the
    # email for the consent record).
    from sqlalchemy import text as _text
    # Prospect is in the tenant schema (search_path already set by get_db).
    row = (
        await db.execute(
            _text('SELECT email FROM "Prospect" WHERE id = :pid'),
            {"pid": body.prospect_id},
        )
    ).fetchone()
    if row is None or not row.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        consent = await _service.record_consent(
            db,
            prospect_id=body.prospect_id,
            email=row.email,
            lawful_basis=body.lawful_basis,
            consent_text=body.consent_text,
            ip_address=ip,
            user_agent=ua,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {
        "id": consent.id,
        "prospect_id": consent.prospect_id,
        "email": consent.email,
        "lawful_basis": consent.lawful_basis,
        "consent_status": consent.consent_status,
        "granted_at": consent.granted_at.isoformat() if consent.granted_at else None,
    }


@router.post("/consent/withdraw", response_model=dict)
async def withdraw_consent(
    body: ConsentWithdrawRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """Withdraw consent for an email. Adds the prospect to the suppression list."""
    verify_tenant(request, token)
    consents = await _service.withdraw_consent(
        db, email=str(body.email), lawful_basis=body.lawful_basis
    )
    if not consents:
        return {
            "email": str(body.email),
            "withdrawn_count": 0,
            "message": "No consent records found for this email in this tenant.",
        }
    return {
        "email": str(body.email),
        "withdrawn_count": len(consents),
        "lawful_bases": [c.lawful_basis for c in consents],
    }


# ── Retention (within tenant) ────────────────────────────────────────────────


@router.get("/retention-status", response_model=RetentionStatusResponse)
async def get_retention_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> RetentionStatusResponse:
    """Get the retention policy status for the caller's tenant."""
    verify_tenant(request, token)
    if not token.tenant_slug:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tenant slug required.")
    status_dict = await _service.get_retention_status(token.tenant_slug)
    return RetentionStatusResponse(
        tenant_slug=token.tenant_slug,
        policies=status_dict,
    )


@router.post("/retention/enforce", response_model=RetentionEnforceResponse)
async def enforce_retention(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> RetentionEnforceResponse:
    """Manually trigger retention enforcement for the caller's tenant."""
    verify_tenant(request, token)
    if not token.tenant_slug:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tenant slug required.")
    results = await _service.enforce_retention(token.tenant_slug)
    return RetentionEnforceResponse(
        tenant_slug=token.tenant_slug,
        results=results,
    )


# ════════════════════════════════════════════════════════════════════════════
# 3 — PLATFORM endpoints (SUPER_ADMIN, TenantMiddleware-exempt)
# ════════════════════════════════════════════════════════════════════════════


@router.get("/platform/dsrs", response_model=list[DsrListResponse])
async def list_all_dsrs(
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db_public),
    token: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> list[DsrListResponse]:
    """List ALL DSRs across ALL tenants. SUPER_ADMIN only."""
    if status_filter is not None and status_filter not in DSR_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of {list(DSR_STATUSES)}",
        )
    rows = await _service.list_dsrs(db, tenant_slug=None, status_filter=status_filter)
    return [DsrListResponse.model_validate(r) for r in rows]


@router.get("/platform/retention-status", response_model=dict)
async def get_platform_retention_status(
    db: AsyncSession = Depends(get_db_public),
    token: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> dict:
    """Get retention policy status across ALL tenants. SUPER_ADMIN only.

    Iterates every active tenant and aggregates the per-policy affected
    counts. Used by the platform DPO dashboard.
    """
    from sqlalchemy import text as _text

    # Get the list of active tenants.
    rows = (
        await db.execute(
            _text(
                "SELECT slug FROM public.tenants "
                "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
            )
        )
    ).fetchall()

    per_tenant: dict[str, dict[str, Any]] = {}
    for row in rows:
        slug = row.slug
        try:
            per_tenant[slug] = await _service.get_retention_status(slug)
        except Exception as exc:  # noqa: BLE001 — one tenant failure must not abort
            per_tenant[slug] = {"error": str(exc)}

    return {
        "tenants_count": len(rows),
        "per_tenant": per_tenant,
    }


__all__ = ["router"]
