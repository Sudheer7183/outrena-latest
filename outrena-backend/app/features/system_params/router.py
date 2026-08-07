"""
system_params.py — Phase 2 /api/v1/system-params router.

Endpoints:
  GET    /system-params              list all SystemParameter rows
  POST   /system-params/reset        re-seed from param_defs (defers to ParamService)
  GET    /system-params/{key}        get one by key
  PUT    /system-params/{key}        update value

Role gate: Role.TENANT_ADMIN.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.system_params import (
    SystemParamResetResponse,
    SystemParamResponse,
    SystemParamUpdate,
)
from app.features.system_params.service import SystemParamsService

router = APIRouter(prefix="/system-params", tags=["System Params"])
_service = SystemParamsService()


@router.get("", response_model=list[SystemParamResponse])
async def list_params(
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> list[SystemParamResponse]:
    items = await _service.list_params(db, category=category)
    return [SystemParamResponse.model_validate(i) for i in items]


# Static route declared BEFORE /{key} (Pitfall #7).
@router.post("/reset", response_model=SystemParamResetResponse)
async def reset_params(
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> SystemParamResetResponse:
    count = await _service.reset_all(db)
    return SystemParamResetResponse(
        resetCount=count,
        message=f"Reset {count} system parameter(s).",
    )


@router.get("/{key}", response_model=SystemParamResponse)
async def get_param(
    key: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> SystemParamResponse:
    item = await _service.get_by_key(db, key)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "System parameter not found.")
    return SystemParamResponse.model_validate(item)


@router.put("/{key}", response_model=SystemParamResponse)
async def update_param(
    key: str,
    body: SystemParamUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> SystemParamResponse:
    item = await _service.update_value(db, key, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "System parameter not found.")
    return SystemParamResponse.model_validate(item)


__all__ = ["router"]
