"""
icp.py — Phase 2 /api/v1/icp-profiles router.

Endpoints:
  GET    /icp-profiles                list
  POST   /icp-profiles                create
  POST   /icp-profiles/suggest        LLM suggests an ICP
  POST   /icp-profiles/auto-discover  LLM derives an ICP from prospect data
  GET    /icp-profiles/{icp_id}       fetch one
  PUT    /icp-profiles/{icp_id}       update
  DELETE /icp-profiles/{icp_id}       delete (204)

Role gate: Role.MANAGER.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.icp import (
    AutoDiscoverRequest,
    AutoDiscoverResponse,
    IcpCreate,
    IcpResponse,
    IcpSuggestRequest,
    IcpSuggestResponse,
    IcpUpdate,
)
from app.features.icp.service import IcpService

router = APIRouter(prefix="/icp-profiles", tags=["ICP Profiles"])
_service = IcpService()


@router.get("", response_model=list[IcpResponse])
async def list_icp_profiles(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> list[IcpResponse]:
    items = await _service.list_profiles(db, limit=limit, offset=offset)
    return [IcpResponse.model_validate(i) for i in items]


@router.post("", response_model=IcpResponse, status_code=201)
async def create_icp_profile(
    body: IcpCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> IcpResponse:
    item = await _service.create(db, body)
    return IcpResponse.model_validate(item)


# Static routes declared BEFORE /{icp_id} (Pitfall #7).
@router.post("/suggest", response_model=IcpSuggestResponse)
async def suggest_icp(
    body: IcpSuggestRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> IcpSuggestResponse:
    """Ask the LLM to suggest an ICP for the given product/service."""
    return await _service.suggest(db, body)


@router.post("/auto-discover", response_model=AutoDiscoverResponse)
async def auto_discover_icp(
    body: AutoDiscoverRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> AutoDiscoverResponse:
    """Derive an ICP from prospect data via the LLM."""
    return await _service.auto_discover(db, body)


@router.get("/{icp_id}", response_model=IcpResponse)
async def get_icp_profile(
    icp_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> IcpResponse:
    item = await _service.get(db, icp_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ICP profile not found.")
    return IcpResponse.model_validate(item)


@router.put("/{icp_id}", response_model=IcpResponse)
async def update_icp_profile(
    icp_id: str,
    body: IcpUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> IcpResponse:
    item = await _service.update(db, icp_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ICP profile not found.")
    return IcpResponse.model_validate(item)


@router.delete("/{icp_id}", response_model=None, response_class=Response, status_code=204)
async def delete_icp_profile(
    icp_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, icp_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ICP profile not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
