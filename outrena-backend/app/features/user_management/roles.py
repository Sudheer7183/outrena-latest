"""
roles.py — Tenant role CRUD router.

Endpoints (verify_tenant + Role.TENANT_ADMIN):
  GET    /roles         → list roles with their permission keys
  POST   /roles         → create a custom role (201)
  PUT    /roles/{id}    → update name / description / permissions
  DELETE /roles/{id}    → delete (409 if is_system)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.services.rbac_service import RbacService

router = APIRouter(prefix="/roles", tags=["Roles & Permissions"])
_service = RbacService()


class PermissionKeyList(BaseModel):
    permission_keys: list[str] = Field(default_factory=list)


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    permission_keys: list[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    permission_keys: list[str] | None = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    is_system: bool
    permissions: list[str]
    created_at: datetime


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> list[RoleResponse]:
    return [RoleResponse(**r) for r in await _service.list_roles(db)]


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: RoleCreateRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> RoleResponse:
    result = await _service.create_role(
        db,
        name=body.name,
        description=body.description,
        permission_keys=body.permission_keys,
    )
    return RoleResponse(**result)


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    body: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> RoleResponse:
    result = await _service.update_role(
        db,
        role_id=role_id,
        name=body.name,
        description=body.description,
        permission_keys=body.permission_keys,
    )
    return RoleResponse(**result)


@router.delete("/{role_id}", response_class=Response, status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    await _service.delete_role(db, role_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
