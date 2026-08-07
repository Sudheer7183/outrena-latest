"""
competitors.py — Phase 3 /api/v1/competitors router.

Endpoints:
  GET    /competitors              list (optional prospectId filter)
  POST   /competitors              create
  GET    /competitors/{id}         fetch one
  PUT    /competitors/{id}         update
  DELETE /competitors/{id}         delete
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.competitors import (
    CompetitorCreate,
    CompetitorResponse,
    CompetitorUpdate,
)
from app.features.competitors.service import CompetitorService

router = APIRouter(prefix="/competitors", tags=["Competitors"])
_service = CompetitorService()


@router.get("", response_model=list[CompetitorResponse])
async def list_competitors(
    prospect_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[CompetitorResponse]:
    items = await _service.list(db, prospect_id=prospect_id)
    return [CompetitorResponse.model_validate(i) for i in items]


@router.post("", response_model=CompetitorResponse, status_code=201)
async def create_competitor(
    body: CompetitorCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> CompetitorResponse:
    item = await _service.create(db, body)
    return CompetitorResponse.model_validate(item)


@router.get("/{competitor_id}", response_model=CompetitorResponse)
async def get_competitor(
    competitor_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> CompetitorResponse:
    item = await _service.get(db, competitor_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Competitor not found.")
    return CompetitorResponse.model_validate(item)


@router.put("/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(
    competitor_id: str,
    body: CompetitorUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> CompetitorResponse:
    item = await _service.update(db, competitor_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Competitor not found.")
    return CompetitorResponse.model_validate(item)


@router.delete("/{competitor_id}", response_model=None, response_class=Response, status_code=204)
async def delete_competitor(
    competitor_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, competitor_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Competitor not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
