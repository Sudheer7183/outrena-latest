"""
weekly_digest.py — Phase 3 /api/v1/weekly-digest router.

Endpoints:
  GET    /weekly-digest              list (most recent first)
  POST   /weekly-digest/generate     compute + persist + return current week
  GET    /weekly-digest/{id}         fetch one
  DELETE /weekly-digest/{id}         delete
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.weekly_digest import (
    WeeklyDigestGenerateRequest,
    WeeklyDigestGenerateResponse,
    WeeklyDigestResponse,
)
from app.features.weekly_digest.service import WeeklyDigestService

router = APIRouter(prefix="/weekly-digest", tags=["Weekly Digest"])
_service = WeeklyDigestService()


@router.get("", response_model=list[WeeklyDigestResponse])
async def list_digests(
    limit: int = Query(default=12, ge=1, le=52),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[WeeklyDigestResponse]:
    items = await _service.list(db, limit=limit, offset=offset)
    return [WeeklyDigestResponse.model_validate(i) for i in items]


@router.post("/generate", response_model=WeeklyDigestGenerateResponse)
async def generate_digest(
    body: WeeklyDigestGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> WeeklyDigestGenerateResponse:
    item = await _service.generate(db, body.weekStart)
    return WeeklyDigestGenerateResponse(digest=WeeklyDigestResponse.model_validate(item))


@router.get("/{digest_id}", response_model=WeeklyDigestResponse)
async def get_digest(
    digest_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> WeeklyDigestResponse:
    item = await _service.get(db, digest_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Weekly digest not found.")
    return WeeklyDigestResponse.model_validate(item)


@router.delete("/{digest_id}", response_model=None, response_class=Response, status_code=204)
async def delete_digest(
    digest_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, digest_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Weekly digest not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
