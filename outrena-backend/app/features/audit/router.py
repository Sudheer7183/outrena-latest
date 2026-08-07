"""
audit.py — Tenant audit-log read router.

Endpoints (verify_tenant + Role.TENANT_ADMIN):
  GET  /audit-logs?limit=100   → list audit log rows for the caller's tenant

Tenant-filtered: callers can only see rows tagged with their own
tenant_slug. The platform-wide view (across all tenants) lives at
/platform/admin/audit-logs and is SUPER_ADMIN-only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["Audit"])
_service = AuditService()


class AuditLogResponse(BaseModel):
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


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> list[AuditLogResponse]:
    """List audit log rows for the caller's tenant (newest first)."""
    tenant = getattr(request.state, "tenant", None)
    tenant_slug = getattr(tenant, "slug", None) if tenant else None
    rows = await _service.list_logs(
        db,
        limit=limit,
        tenant_slug=tenant_slug,
    )
    return [AuditLogResponse(**r) for r in rows]


__all__ = ["router"]
