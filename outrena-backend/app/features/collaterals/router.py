"""
collaterals.py — Phase 3 /api/v1/collaterals router.

Endpoints:
  GET    /collaterals                list
  POST   /collaterals                create
  GET    /collaterals/{id}           fetch one
  PUT    /collaterals/{id}           update
  DELETE /collaterals/{id}           delete
  POST   /collaterals/link           link a collateral to a campaign
  DELETE /collaterals/link/{link_id} unlink
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.collaterals import (
    CampaignCollateralLinkCreate,
    CampaignCollateralLinkResponse,
    CollateralCreate,
    CollateralResponse,
    CollateralUpdate,
)
from app.features.collaterals.service import CollateralService

router = APIRouter(prefix="/collaterals", tags=["Collaterals"])
_service = CollateralService()


@router.get("", response_model=list[CollateralResponse])
async def list_collaterals(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[CollateralResponse]:
    items = await _service.list(db, limit=limit, offset=offset)
    return [CollateralResponse.model_validate(i) for i in items]


@router.post("", response_model=CollateralResponse, status_code=201)
async def create_collateral(
    body: CollateralCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> CollateralResponse:
    item = await _service.create(db, body)
    return CollateralResponse.model_validate(item)


@router.get("/{collateral_id}", response_model=CollateralResponse)
async def get_collateral(
    collateral_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> CollateralResponse:
    item = await _service.get(db, collateral_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collateral not found.")
    return CollateralResponse.model_validate(item)


@router.put("/{collateral_id}", response_model=CollateralResponse)
async def update_collateral(
    collateral_id: str,
    body: CollateralUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> CollateralResponse:
    item = await _service.update(db, collateral_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collateral not found.")
    return CollateralResponse.model_validate(item)


@router.delete("/{collateral_id}", response_model=None, response_class=Response, status_code=204)
async def delete_collateral(
    collateral_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, collateral_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collateral not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/link", response_model=CampaignCollateralLinkResponse, status_code=201)
async def link_collateral(
    body: CampaignCollateralLinkCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> CampaignCollateralLinkResponse:
    link = await _service.link_to_campaign(db, body)
    return CampaignCollateralLinkResponse.model_validate(link)


@router.delete("/link/{link_id}", response_model=None, response_class=Response, status_code=204)
async def unlink_collateral(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.unlink(db, link_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
