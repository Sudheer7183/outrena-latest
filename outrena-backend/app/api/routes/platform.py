"""
platform.py — SUPER_ADMIN registry routes.

TenantMiddleware-exempt (prefix /platform). Queries the public schema only.
SUPER_ADMIN tokens carry tenant_slug=None and never see tenant operational
data — only registry metadata.

Phase 7 (SaaS platform) extends this router with /platform/admin/* routes:
  - Signup queue review (approve / reject)
  - Tenant listing with plan + seat metrics
  - Platform-wide KPIs (MRR, churn, totals)
  - Audit-log search across all tenants

Phase 8 (dual-path integrations) adds:
  - PATCH /admin/tenants/{id}/integration-mode  → update tenant_config
  - GET  /admin/tenants/{id}/config             → fetch tenant_config
  - POST /admin/llm-configs                      → create global LLM config
  - GET  /admin/llm-configs                      → list global LLM configs
  - PUT  /admin/llm-configs/{id}                 → update
  - DELETE /admin/llm-configs/{id}               → soft-delete
  - POST /admin/llm-configs/{id}/set-default     → set platform default
  - POST /admin/llm-configs/{id}/test            → test the config's key
  - GET  /admin/integration-catalog              → platform-managed key catalog
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_public
from app.api.security import get_current_user, verify_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.llm_config import (
    LlmConfigCreate,
    LlmConfigResponse,
    LlmConfigUpdate,
    TestLlmRequest,
    TestLlmResponse,
)
from app.schemas.tenant import (
    SlugAvailabilityResponse,
    TenantCreatedResponse,
    TenantCreateRequest,
    TenantResponse,
)
from app.services.audit_service import AuditService
from app.features.integrations.integration_credentials_service import (
    IntegrationCredentialsService,
)
from app.features.llm_config.service import LlmConfigService
from app.services.platform_admin_service import PlatformAdminService
from app.features.subdomain.service import is_slug_available, tenant_url_for
from app.services.tenant_provisioning_service import TenantProvisioningService

router = APIRouter(prefix="/platform", tags=["Platform Admin"])
_admin_service = PlatformAdminService()
_llm_config_service = LlmConfigService()
_credentials_service = IntegrationCredentialsService()


# ── Inline schemas (app/schemas/* is outside ownership scope) ─────────────────


class SignupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_name: str
    subdomain: str
    owner_email: str
    owner_first_name: str
    owner_last_name: str
    plan_id: int
    status: str
    rejection_reason: str | None
    tenant_id: int | None
    reviewed_at: datetime | None
    reviewed_by: str | None
    created_at: datetime


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class ApproveResponse(BaseModel):
    signup_id: int
    status: str
    tenant_slug: str
    tenant_id: int
    provisioned: bool


class RejectResponse(BaseModel):
    signup_id: int
    status: str
    reason: str


class TenantWithMetricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tenant_id: int
    slug: str
    schema_name: str
    name: str
    tenant_type: str
    status: str
    plan: str | None
    plan_display_name: str | None
    subscription_status: str | None
    seats_used: int
    seats_limit: int | None
    created_at: datetime


class PlatformMetricsResponse(BaseModel):
    total_tenants: int
    active_tenants: int
    total_users: int
    mrr_cents: int
    mrr_dollars: float
    churn_rate: float


class AuditLogRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_sub: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    tenant_slug: str | None = None
    action: str
    target: str | None = None
    target_id: str | None = None
    metadata: dict[str, Any] | None = None
    request_id: str | None = None
    ip_address: str | None = None
    created_at: datetime


# ── Phase 8 — dual-path integrations inline schemas ─────────────────────────


class IntegrationModeRequest(BaseModel):
    """Body for PATCH /admin/tenants/{id}/integration-mode."""

    integration_mode: str = Field(
        ..., pattern="^(platform_managed|tenant_managed)$"
    )


class IntegrationModeResponse(BaseModel):
    tenant_id: int
    integration_mode: str
    updated_at: datetime


class TenantConfigResponse(BaseModel):
    """Full tenant_config row (public schema)."""

    model_config = ConfigDict(from_attributes=True)
    tenant_id: int
    plan: str
    max_seats: int
    features: dict[str, Any]
    integrations_shared: bool
    llm_provider_default: str
    integration_mode: str
    created_at: datetime
    updated_at: datetime


class PlatformIntegrationCatalogEntry(BaseModel):
    integration_type: str
    platform: str | None = None
    provider: str | None = None
    platform_key_available: bool
    secret_name: str


class PlatformIntegrationCatalogResponse(BaseModel):
    entries: list[PlatformIntegrationCatalogEntry]


# Static route BEFORE any parametric sibling (route-ordering rule).
@router.get("/tenants/slug-availability", response_model=SlugAvailabilityResponse)
async def check_slug_availability(
    slug: str,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> SlugAvailabilityResponse:
    """
    Pre-flight subdomain allocation check for the provisioning wizard.
    Lets the UI validate the clean URL while the admin types, before any
    provisioning work begins.
    """
    verify_role(Role.SUPER_ADMIN, token)
    normalized = slug.strip().lower()
    available, reason = await is_slug_available(normalized, db)
    return SlugAvailabilityResponse(
        slug=normalized,
        available=available,
        reason=reason,
        url=tenant_url_for(normalized),
    )


@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> list[TenantResponse]:
    """List all non-deleted tenants in the registry."""
    verify_role(Role.SUPER_ADMIN, token)
    result = await db.execute(
        text(
            "SELECT tenant_id, slug, schema_name, name, tenant_type, status, created_at "
            "FROM public.tenants WHERE deleted_at IS NULL ORDER BY created_at DESC"
        )
    )
    return [TenantResponse(**dict(row._mapping)) for row in result.fetchall()]


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> TenantResponse:
    """Fetch a single tenant by ID."""
    verify_role(Role.SUPER_ADMIN, token)
    result = await db.execute(
        text(
            "SELECT tenant_id, slug, schema_name, name, tenant_type, status, created_at "
            "FROM public.tenants WHERE tenant_id = :tid AND deleted_at IS NULL"
        ),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return TenantResponse(**dict(row._mapping))


@router.post("/tenants", response_model=TenantCreatedResponse, status_code=201)
async def create_tenant(
    body: TenantCreateRequest,
    request: Request,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> TenantCreatedResponse:
    """
    Provision a new tenant end to end (schema, migrations, seed, IdP user)
    and allocate its subdomain — the response carries the clean tenant URL.
    """
    verify_role(Role.SUPER_ADMIN, token)

    # Subdomain allocation gate: a taken slug is a clean 409 BEFORE any
    # provisioning work — never a mid-flight unique-constraint rollback.
    available, reason = await is_slug_available(body.slug, db)
    if not available:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)

    service = TenantProvisioningService()
    slug = await service.provision_tenant(
        tenant_slug=body.slug,
        tenant_name=body.name,
        tenant_type=body.tenant_type,
        admin_email=str(body.admin_email),
        admin_first_name=body.admin_first_name,
        admin_last_name=body.admin_last_name,
        temporary_password=body.temporary_password,
        send_invitation=body.send_invitation,
        db=db,
    )
    return TenantCreatedResponse(
        slug=slug, status="ACTIVE", url=tenant_url_for(slug)
    )


@router.post(
    "/tenants/{tenant_id}/suspend",
    response_model=TenantResponse,
)
async def suspend_tenant(
    tenant_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> TenantResponse:
    """Suspend a tenant (sets status to SUSPENDED — middleware returns 403)."""
    verify_role(Role.SUPER_ADMIN, token)
    await db.execute(
        text("UPDATE public.tenants SET status = 'SUSPENDED' WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    await db.commit()
    result = await db.execute(
        text(
            "SELECT tenant_id, slug, schema_name, name, tenant_type, status, created_at "
            "FROM public.tenants WHERE tenant_id = :tid"
        ),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return TenantResponse(**dict(row._mapping))


@router.post(
    "/tenants/{tenant_id}/reactivate",
    response_model=TenantResponse,
)
async def reactivate_tenant(
    tenant_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> TenantResponse:
    """Reactivate a suspended tenant."""
    verify_role(Role.SUPER_ADMIN, token)
    await db.execute(
        text("UPDATE public.tenants SET status = 'ACTIVE' WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    await db.commit()
    result = await db.execute(
        text(
            "SELECT tenant_id, slug, schema_name, name, tenant_type, status, created_at "
            "FROM public.tenants WHERE tenant_id = :tid"
        ),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return TenantResponse(**dict(row._mapping))


# ── Phase 7 — SaaS platform admin endpoints ─────────────────────────────────
# All gated by verify_role(Role.SUPER_ADMIN). They live under /platform/admin/*
# so the existing TenantMiddleware exemption for "/platform" applies.
#
# Endpoints:
#   GET  /admin/signups?status=pending_approval  → SignupResponse[]
#   POST /admin/signups/{id}/approve             → ApproveResponse
#   POST /admin/signups/{id}/reject              → RejectResponse
#   GET  /admin/tenants                          → TenantWithMetricsResponse[]
#   POST /admin/tenants/{id}/suspend             → 200
#   POST /admin/tenants/{id}/reactivate          → 200
#   GET  /admin/metrics                          → PlatformMetricsResponse
#   GET  /admin/audit-logs?limit=&tenant_slug=&action=  → AuditLogRow[]


@router.get("/admin/signups", response_model=list[SignupResponse])
async def admin_list_signups(
    status_filter: str | None = Query(default=None, alias="status"),
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> list[SignupResponse]:
    """List tenant signup requests, optionally filtered by status."""
    verify_role(Role.SUPER_ADMIN, token)
    rows = await _admin_service.list_signups(db, status_filter=status_filter)
    return [SignupResponse(**r) for r in rows]


@router.post("/admin/signups/{signup_id}/approve", response_model=ApproveResponse)
async def admin_approve_signup(
    signup_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> ApproveResponse:
    """Approve a signup request → provision the tenant + create subscription."""
    verify_role(Role.SUPER_ADMIN, token)
    result = await _admin_service.approve_signup(db, signup_id, token.sub)
    return ApproveResponse(**result)


@router.post("/admin/signups/{signup_id}/reject", response_model=RejectResponse)
async def admin_reject_signup(
    signup_id: int,
    body: RejectRequest,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> RejectResponse:
    """Reject a signup request with a reason."""
    verify_role(Role.SUPER_ADMIN, token)
    result = await _admin_service.reject_signup(db, signup_id, body.reason, token.sub)
    return RejectResponse(**result)


@router.get("/admin/tenants", response_model=list[TenantWithMetricsResponse])
async def admin_list_tenants(
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> list[TenantWithMetricsResponse]:
    """List all tenants with plan + seat info."""
    verify_role(Role.SUPER_ADMIN, token)
    rows = await _admin_service.list_tenants_with_metrics(db)
    return [TenantWithMetricsResponse(**r) for r in rows]


@router.post("/admin/tenants/{tenant_id}/suspend", response_model=TenantResponse)
async def admin_suspend_tenant(
    tenant_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> TenantResponse:
    """Suspend a tenant (sets status=SUSPENDED — middleware returns 403)."""
    verify_role(Role.SUPER_ADMIN, token)
    await db.execute(
        text("UPDATE public.tenants SET status = 'SUSPENDED' WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    await db.commit()
    result = await db.execute(
        text(
            "SELECT tenant_id, slug, schema_name, name, tenant_type, status, created_at "
            "FROM public.tenants WHERE tenant_id = :tid"
        ),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return TenantResponse(**dict(row._mapping))


@router.post("/admin/tenants/{tenant_id}/reactivate", response_model=TenantResponse)
async def admin_reactivate_tenant(
    tenant_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> TenantResponse:
    """Reactivate a suspended tenant (admin path)."""
    verify_role(Role.SUPER_ADMIN, token)
    await db.execute(
        text("UPDATE public.tenants SET status = 'ACTIVE' WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    await db.commit()
    result = await db.execute(
        text(
            "SELECT tenant_id, slug, schema_name, name, tenant_type, status, created_at "
            "FROM public.tenants WHERE tenant_id = :tid"
        ),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return TenantResponse(**dict(row._mapping))


@router.get("/admin/metrics", response_model=PlatformMetricsResponse)
async def admin_metrics(
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> PlatformMetricsResponse:
    """Platform-wide KPIs: total/active tenants, total users, MRR, churn."""
    verify_role(Role.SUPER_ADMIN, token)
    return PlatformMetricsResponse(**await _admin_service.platform_metrics(db))


@router.get("/admin/audit-logs", response_model=list[AuditLogRow])
async def admin_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    tenant_slug: str | None = Query(default=None),
    action: str | None = Query(default=None),
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> list[AuditLogRow]:
    """Cross-tenant audit-log search (SUPER_ADMIN only)."""
    verify_role(Role.SUPER_ADMIN, token)
    rows = await _admin_service.list_audit_logs(
        db,
        limit=limit,
        tenant_slug=tenant_slug,
        action=action,
    )
    return [AuditLogRow(**r) for r in rows]


# ── Phase 8 — Dual-path integrations admin endpoints ────────────────────────
# All SUPER_ADMIN-gated. They live under /platform/admin/* so the existing
# TenantMiddleware exemption for "/platform" applies.
#
# Endpoints:
#   PATCH /admin/tenants/{id}/integration-mode  → update tenant_config
#   GET   /admin/tenants/{id}/config            → fetch full tenant_config
#   POST  /admin/llm-configs                     → create global LLM config
#   GET   /admin/llm-configs                     → list global LLM configs
#   GET   /admin/llm-configs/{id}                → fetch one
#   PUT   /admin/llm-configs/{id}                → update
#   DELETE /admin/llm-configs/{id}               → soft-delete
#   POST  /admin/llm-configs/{id}/set-default    → set platform default
#   POST  /admin/llm-configs/{id}/test           → test the config's key
#   GET   /admin/integration-catalog             → platform-managed key catalog


@router.patch(
    "/admin/tenants/{tenant_id}/integration-mode",
    response_model=IntegrationModeResponse,
)
async def admin_set_integration_mode(
    tenant_id: int,
    body: IntegrationModeRequest,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> IntegrationModeResponse:
    """Update tenant_config.integration_mode (SUPER_ADMIN only).

    Logs the change to the platform_audit_log; returns the updated mode
    + the row's updated_at timestamp. Validates the mode is one of
    ``platform_managed`` | ``tenant_managed`` (Pydantic handles this;
    the explicit check below is defense-in-depth).
    """
    verify_role(Role.SUPER_ADMIN, token)
    if body.integration_mode not in ("platform_managed", "tenant_managed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="integration_mode must be 'platform_managed' or 'tenant_managed'.",
        )
    result = await db.execute(
        text(
            "UPDATE public.tenant_config "
            "SET integration_mode = :mode, updated_at = now() "
            "WHERE tenant_id = :tid RETURNING tenant_id, integration_mode, "
            "updated_at"
        ),
        {"mode": body.integration_mode, "tid": tenant_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant config not found.",
        )
    await db.commit()
    # Audit the change (fire-and-forget — never fails the request).
    try:
        await AuditService().log(
            db,
            actor_user_id=token.sub,
            actor_role=token.role.value,
            tenant_slug=None,
            action="tenant.integration_mode_updated",
            target_type="tenant_config",
            target_id=str(tenant_id),
            metadata={"integration_mode": body.integration_mode},
        )
    except Exception as exc:  # noqa: BLE001
        # Audit failure must not block the update.
        pass
    return IntegrationModeResponse(
        tenant_id=row.tenant_id,
        integration_mode=row.integration_mode,
        updated_at=row.updated_at,
    )


@router.get(
    "/admin/tenants/{tenant_id}/config",
    response_model=TenantConfigResponse,
)
async def admin_get_tenant_config(
    tenant_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> TenantConfigResponse:
    """Return the full public.tenant_config row for a tenant."""
    verify_role(Role.SUPER_ADMIN, token)
    result = await db.execute(
        text(
            "SELECT tenant_id, plan, max_seats, features, integrations_shared, "
            "llm_provider_default, integration_mode, created_at, updated_at "
            "FROM public.tenant_config WHERE tenant_id = :tid"
        ),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant config not found.",
        )
    return TenantConfigResponse(**dict(row._mapping))


@router.post(
    "/admin/llm-configs",
    response_model=LlmConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_llm_config(
    body: LlmConfigCreate,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> LlmConfigResponse:
    """Create a global LLM provider config (SUPER_ADMIN only)."""
    verify_role(Role.SUPER_ADMIN, token)
    try:
        item = await _llm_config_service.create(db, body)
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Encryption backend not configured: {exc}",
        ) from exc
    return LlmConfigResponse(**_llm_config_service.to_response(item))


@router.get(
    "/admin/llm-configs",
    response_model=list[LlmConfigResponse],
)
async def admin_list_llm_configs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> list[LlmConfigResponse]:
    """List global LLM provider configs (SUPER_ADMIN only)."""
    verify_role(Role.SUPER_ADMIN, token)
    items = await _llm_config_service.list_configs(db, limit=limit, offset=offset)
    return [LlmConfigResponse(**_llm_config_service.to_response(i)) for i in items]


@router.get(
    "/admin/llm-configs/{config_id}",
    response_model=LlmConfigResponse,
)
async def admin_get_llm_config(
    config_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> LlmConfigResponse:
    """Fetch one global LLM config by id (SUPER_ADMIN only)."""
    verify_role(Role.SUPER_ADMIN, token)
    item = await _llm_config_service.get(db, config_id)
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "LLM config not found."
        )
    return LlmConfigResponse(**_llm_config_service.to_response(item))


@router.put(
    "/admin/llm-configs/{config_id}",
    response_model=LlmConfigResponse,
)
async def admin_update_llm_config(
    config_id: int,
    body: LlmConfigUpdate,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> LlmConfigResponse:
    """Update a global LLM config (SUPER_ADMIN only)."""
    verify_role(Role.SUPER_ADMIN, token)
    try:
        item = await _llm_config_service.update(db, config_id, body)
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Encryption backend not configured: {exc}",
        ) from exc
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "LLM config not found."
        )
    return LlmConfigResponse(**_llm_config_service.to_response(item))


@router.delete(
    "/admin/llm-configs/{config_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_llm_config(
    config_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> None:
    """Soft-delete a global LLM config (is_active=false). SUPER_ADMIN only."""
    verify_role(Role.SUPER_ADMIN, token)
    ok = await _llm_config_service.delete(db, config_id)
    if not ok:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "LLM config not found."
        )


@router.post(
    "/admin/llm-configs/{config_id}/set-default",
    response_model=LlmConfigResponse,
)
async def admin_set_default_llm_config(
    config_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> LlmConfigResponse:
    """Mark this config as the platform default; demote others."""
    verify_role(Role.SUPER_ADMIN, token)
    item = await _llm_config_service.set_default(db, config_id)
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "LLM config not found or is inactive.",
        )
    return LlmConfigResponse(**_llm_config_service.to_response(item))


@router.post(
    "/admin/llm-configs/{config_id}/test",
    response_model=TestLlmResponse,
)
async def admin_test_llm_config(
    config_id: int,
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> TestLlmResponse:
    """Send a tiny test prompt to verify the config's API key."""
    verify_role(Role.SUPER_ADMIN, token)
    return await _llm_config_service.test_llm(
        db,
        TestLlmRequest(
            config_id=config_id,
            message="Hello, please confirm you are operational.",
        ),
    )


@router.get(
    "/admin/integration-catalog",
    response_model=PlatformIntegrationCatalogResponse,
)
async def admin_integration_catalog(
    token: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> PlatformIntegrationCatalogResponse:
    """Return the catalog of platform-managed integration + LLM keys.

    For each entry the response reports whether a platform key is
    available in the configured SecretBackend (env / AWS SM / Azure KV).
    SUPER_ADMIN uses this to decide which integrations can be switched
    to ``key_source="platform"`` for a given tenant.
    """
    verify_role(Role.SUPER_ADMIN, token)
    entries = await _credentials_service.list_platform_credentials_catalog()
    return PlatformIntegrationCatalogResponse(
        entries=[PlatformIntegrationCatalogEntry(**e) for e in entries]
    )
