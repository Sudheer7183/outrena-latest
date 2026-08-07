"""
meeting_prep.py — Phase 3 /api/v1/meeting-prep router.

Endpoints:
  GET    /meeting-prep                 list briefs for a prospect
  POST   /meeting-prep                 create a brief (auto-generate if body omitted)
  POST   /meeting-prep/generate        LLM-generate a new brief on the fly
  GET    /meeting-prep/{id}            fetch one
  DELETE /meeting-prep/{id}            delete
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.meeting_prep import (
    MeetingPrepCreate,
    MeetingPrepGenerateRequest,
    MeetingPrepGenerateResponse,
    MeetingPrepResponse,
)
from app.features.meetings.service import MeetingPrepService

router = APIRouter(prefix="/meeting-prep", tags=["Meeting Prep"])
_service = MeetingPrepService()


@router.get("", response_model=list[MeetingPrepResponse])
async def list_briefs(
    prospect_id: str | None = Query(default=None),  # BUG-21 FIX: optional — returns all when omitted
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[MeetingPrepResponse]:
    """BUG-21 FIX: prospect_id is optional; returns all briefs when omitted."""
    if prospect_id:
        items = await _service.list_for_prospect(db, prospect_id)
    else:
        items = await _service.list_all(db)
    return [MeetingPrepResponse.model_validate(i) for i in items]


@router.post("", response_model=MeetingPrepResponse, status_code=201)
async def create_brief(
    body: MeetingPrepCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> MeetingPrepResponse:
    item = await _service.create(db, body)
    return MeetingPrepResponse.model_validate(item)


@router.post("/generate", response_model=MeetingPrepGenerateResponse)
async def generate_brief(
    body: MeetingPrepGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> MeetingPrepGenerateResponse:
    item = await _service.generate(db, body.prospectId, body.callType)
    return MeetingPrepGenerateResponse(id=item.id, brief=item.brief)


@router.get("/{brief_id}", response_model=MeetingPrepResponse)
async def get_brief(
    brief_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> MeetingPrepResponse:
    item = await _service.get(db, brief_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meeting prep not found.")
    return MeetingPrepResponse.model_validate(item)


@router.delete("/{brief_id}", response_model=None, response_class=Response, status_code=204)
async def delete_brief(
    brief_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, brief_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meeting prep not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
