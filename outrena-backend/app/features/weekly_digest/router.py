"""
weekly_digest.py — Phase 3 /api/v1/weekly-digest router.

FIX: WeeklyDigest ORM model stores highlights, topProspects, and
campaignPerformance as TEXT columns containing JSON strings (json.dumps).
The @field_validator in WeeklyDigestResponse was supposed to parse them,
but Pydantic v2 model_validate() on ORM objects doesn't reliably fire
mode="before" validators on TEXT column values.

Fix: pre-parse the three JSON TEXT columns before calling model_validate()
so Pydantic receives native Python types (list/dict), not raw strings.
"""
from __future__ import annotations

import json

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
from app.models.phase3_models import WeeklyDigest

router = APIRouter(prefix="/weekly-digest", tags=["Weekly Digest"])
_service = WeeklyDigestService()


def _parse_digest(item: WeeklyDigest) -> WeeklyDigestResponse:
    """Pre-parse JSON TEXT columns before Pydantic model_validate.

    highlights, topProspects, and campaignPerformance are stored as
    json.dumps() strings. Pydantic v2 mode='before' validators don't
    reliably fire when model_validate() is called with from_attributes=True
    on an ORM object. We parse manually to guarantee native types.
    """
    def _safe_parse(value: object) -> object:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value
        return value

    item.highlights = _safe_parse(item.highlights)           # type: ignore[assignment]
    item.topProspects = _safe_parse(item.topProspects)       # type: ignore[assignment]
    item.campaignPerformance = _safe_parse(item.campaignPerformance)  # type: ignore[assignment]
    return WeeklyDigestResponse.model_validate(item)


@router.get("", response_model=list[WeeklyDigestResponse])
async def list_digests(
    limit: int = Query(default=12, ge=1, le=52),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[WeeklyDigestResponse]:
    items = await _service.list(db, limit=limit, offset=offset)
    return [_parse_digest(i) for i in items]


@router.post("/generate", response_model=WeeklyDigestGenerateResponse)
async def generate_digest(
    body: WeeklyDigestGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> WeeklyDigestGenerateResponse:
    item = await _service.generate(db, body.weekStart)
    return WeeklyDigestGenerateResponse(digest=_parse_digest(item))


@router.get("/{digest_id}", response_model=WeeklyDigestResponse)
async def get_digest(
    digest_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> WeeklyDigestResponse:
    item = await _service.get(db, digest_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Weekly digest not found.")
    return _parse_digest(item)


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