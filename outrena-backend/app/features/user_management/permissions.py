"""
permissions.py — Permission catalog + feature-permission map router.

Endpoints:
  GET  /permissions                          → list all catalog permissions (any auth)
  GET  /feature-permissions                  → list feature_key → permission map (any auth)
  PUT  /feature-permissions/{feature_key}    → upsert mapping (SUPER_ADMIN only)
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user, require_role
from app.schemas.auth import Role, TokenPayload
from app.services.rbac_service import RbacService

router = APIRouter(prefix="/permissions", tags=["Roles & Permissions"])
_service = RbacService()


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    display_name: str
    description: str
    category: str


class FeaturePermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    feature_key: str
    required_permission: str | None
    description: str


class FeaturePermissionUpdateRequest(BaseModel):
    required_permission: str | None = Field(default=None, max_length=80)


@router.get("", response_model=list[PermissionResponse])
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[PermissionResponse]:
    """List the full permission catalog (read-only, any authenticated user)."""
    return [PermissionResponse(**p) for p in await _service.list_permissions(db)]


@router.get("/feature-permissions", response_model=list[FeaturePermissionResponse])
async def list_feature_permissions(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[FeaturePermissionResponse]:
    return [
        FeaturePermissionResponse(**fp)
        for fp in await _service.list_feature_permissions(db)
    ]


@router.put(
    "/feature-permissions/{feature_key}",
    response_model=FeaturePermissionResponse,
)
async def set_feature_permission(
    feature_key: str,
    body: FeaturePermissionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> FeaturePermissionResponse:
    """Upsert a feature_key → required_permission mapping. SUPER_ADMIN only.

    Note: this endpoint intentionally does NOT call verify_tenant() —
    SUPER_ADMIN tokens carry tenant_slug=None and bypass tenant checks.
    The router is mounted under /api/v1 so TenantMiddleware requires a
    tenant; to make this call platform-administrable, hit it from a
    tenant subdomain using a SUPER_ADMIN token (the role check still
    gates the call).
    """
    result = await _service.set_feature_permission(
        db,
        feature_key=feature_key,
        required_permission=body.required_permission,
    )
    return FeaturePermissionResponse(**result)


__all__ = ["router"]
