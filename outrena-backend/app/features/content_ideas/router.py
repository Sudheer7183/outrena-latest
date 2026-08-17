"""
content_ideas.py — Phase 3 /api/v1/content-ideas router.

FIX: generate endpoint now passes topic and audience from the request body
to the service, so the frontend's {topic, audience, count} payload works
correctly without requiring an icpProfileId.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.content_ideas import (
    ContentIdeaCreate,
    ContentIdeaGenerateRequest,
    ContentIdeaGenerateResponse,
    ContentIdeaResponse,
    ContentIdeaUpdate,
)
from app.features.content_ideas.service import ContentIdeaService
from app.features.usage.cap_gate import enforce_llm_cap

router = APIRouter(prefix="/content-ideas", tags=["Content Ideas"])
_service = ContentIdeaService()


@router.get("", response_model=list[ContentIdeaResponse])
async def list_ideas(
    icp_profile_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[ContentIdeaResponse]:
    items = await _service.list(
        db, icp_profile_id=icp_profile_id, limit=limit, offset=offset
    )
    return [ContentIdeaResponse.model_validate(i) for i in items]


@router.post("", response_model=ContentIdeaResponse, status_code=201)
async def create_idea(
    body: ContentIdeaCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> ContentIdeaResponse:
    item = await _service.create(db, body)
    return ContentIdeaResponse.model_validate(item)


@router.post(
    "/generate",
    response_model=ContentIdeaGenerateResponse,
    dependencies=[Depends(enforce_llm_cap)],
)
async def generate_ideas(
    body: ContentIdeaGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> ContentIdeaGenerateResponse:
    # FIX: pass topic and audience so generate() works without icpProfileId
    items = await _service.generate(
        db,
        icp_profile_id=body.icpProfileId,
        count=body.count,
        topic=body.topic,
        audience=body.audience,
    )
    return ContentIdeaGenerateResponse(
        ideas=[ContentIdeaResponse.model_validate(i) for i in items]
    )


@router.get("/{idea_id}", response_model=ContentIdeaResponse)
async def get_idea(
    idea_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> ContentIdeaResponse:
    item = await _service.get(db, idea_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content idea not found.")
    return ContentIdeaResponse.model_validate(item)


@router.put("/{idea_id}", response_model=ContentIdeaResponse)
async def update_idea(
    idea_id: str,
    body: ContentIdeaUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> ContentIdeaResponse:
    item = await _service.update(db, idea_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content idea not found.")
    return ContentIdeaResponse.model_validate(item)


@router.delete("/{idea_id}", response_model=None, response_class=Response, status_code=204)
async def delete_idea(
    idea_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, idea_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content idea not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)