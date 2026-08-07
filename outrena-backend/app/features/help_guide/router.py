"""
help.py — Public-schema help-guide router with role-gated visibility.

Endpoints (verify_tenant, any authenticated):
  GET  /help/sections              → list sections visible to caller's role
  GET  /help/sections/{slug}       → section + its articles
  GET  /help/search?q=             → search articles by title/body ILIKE
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user, verify_tenant
from app.schemas.auth import TokenPayload
from app.features.help_guide.service import HelpService

router = APIRouter(prefix="/help", tags=["Help"])
_service = HelpService()


class HelpArticleResponse(BaseModel):
    """Article payload returned by ``GET /help/sections/{slug}`` and
    ``GET /help/search``.

    For the section-detail endpoint ``section_slug`` / ``section_title``
    are None (the caller already knows the section). For the search
    endpoint both are populated so the frontend can render the section
    badge without an extra lookup (AUDIT-HELP-1 / G-3).
    """
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    title: str
    body: str | None = None
    body_excerpt: str | None = None
    sort_order: int | None = None
    section_slug: str | None = None
    section_title: str | None = None


class HelpSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    title: str
    description: str
    sort_order: int
    created_at: datetime
    articles: list[HelpArticleResponse] | None = None


@router.get("/sections", response_model=list[HelpSectionResponse])
async def list_sections(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[HelpSectionResponse]:
    verify_tenant(request, token)
    rows = await _service.list_sections_for_role(db, token.role)
    return [HelpSectionResponse(**r) for r in rows]


@router.get("/sections/{slug}", response_model=HelpSectionResponse)
async def get_section(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> HelpSectionResponse:
    verify_tenant(request, token)
    result = await _service.get_section(db, slug, token.role)
    # Pop 'articles' from result before unpacking to avoid duplicate keyword
    # argument — the service layer already embeds articles in the dict.
    raw_articles = result.pop("articles", []) if isinstance(result, dict) else []
    return HelpSectionResponse(
        **result,
        articles=[HelpArticleResponse(**a) for a in (raw_articles or [])],
    )


@router.get("/search", response_model=list[HelpArticleResponse])
async def search_articles(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[HelpArticleResponse]:
    verify_tenant(request, token)
    rows = await _service.search_articles(db, q, token.role)
    return [HelpArticleResponse(**r) for r in rows]


__all__ = ["router"]
