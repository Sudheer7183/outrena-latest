"""
router_ai.py — 5 AI-powered prospect endpoints.

  POST /prospects/ultimate-profile  — Deep-research business profile
  POST /prospects/lookalike          — Firmographic lookalike search
  POST /prospects/hook-generator     — Cold-outreach hook generation
  POST /prospects/prospect-brief     — 60-second prospect briefing
  POST /prospects/search-nl          — Natural-language prospect search

All endpoints are async, require Role.REP, and use the tenant-scoped
DB session from ``app.api.deps.get_db``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.prospect_ai import (
    HookGeneratorRequest,
    HookGeneratorResponse,
    LookalikeRequest,
    LookalikeResponse,
    NlSearchRequest,
    NlSearchResponse,
    ProspectBriefRequest,
    ProspectBriefResponse,
    UltimateProfileRequest,
    UltimateProfileResponse,
)
from app.features.prospects.service_ai import ProspectAiService

router = APIRouter(prefix="/prospects", tags=["Prospects AI"])
_service = ProspectAiService()


# ── 1. Ultimate Profile ──────────────────────────────────────────────────────


@router.post("/ultimate-profile", response_model=UltimateProfileResponse)
async def ultimate_profile(
    body: UltimateProfileRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> UltimateProfileResponse:
    """Deep-research agent: web search + LLM → comprehensive business profile."""
    result = await _service.ultimate_profile(
        db, prospect_id=body.prospect_id, llm_config_id=body.llm_config_id
    )
    if not result.success:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Prospect not found."
        )
    return result


# ── 2. Lookalike ─────────────────────────────────────────────────────────────


@router.post("/lookalike", response_model=LookalikeResponse)
async def lookalike(
    body: LookalikeRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> LookalikeResponse:
    """Find prospects similar to a seed by firmographic features."""
    result = await _service.lookalike(
        db,
        seed_prospect_id=body.seed_prospect_id,
        seed_company_domain=body.seed_company_domain,
        limit=body.limit,
    )
    if not result.success:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No seed prospect found. Provide seed_prospect_id or seed_company_domain.",
        )
    return result


# ── 3. Hook Generator ────────────────────────────────────────────────────────


@router.post("/hook-generator", response_model=HookGeneratorResponse)
async def hook_generator(
    body: HookGeneratorRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> HookGeneratorResponse:
    """Generate 5 personalized cold-outreach opener hooks for a prospect."""
    result = await _service.hook_generator(
        db, prospect_id=body.prospect_id, llm_config_id=body.llm_config_id
    )
    if not result.success:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Prospect not found."
        )
    return result


# ── 4. Prospect Brief ────────────────────────────────────────────────────────


@router.post("/prospect-brief", response_model=ProspectBriefResponse)
async def prospect_brief(
    body: ProspectBriefRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> ProspectBriefResponse:
    """Generate a 60-second prospect briefing using LLM."""
    result = await _service.prospect_brief(
        db, prospect_id=body.prospect_id, llm_config_id=body.llm_config_id
    )
    if not result.success:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Prospect not found."
        )
    return result


# ── 5. NL Prospect Search ────────────────────────────────────────────────────


@router.post("/search-nl", response_model=NlSearchResponse)
async def search_nl(
    body: NlSearchRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> NlSearchResponse:
    """Parse a natural-language query into structured filters and search prospects."""
    return await _service.nl_prospect_search(
        db, query=body.query, llm_config_id=body.llm_config_id
    )


__all__ = ["router"]
