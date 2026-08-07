"""prospect_ai.py — Pydantic v2 schemas for 5 AI-powered prospect endpoints.

  1. POST /prospects/ultimate-profile  — Deep-research business profile
  2. POST /prospects/lookalike          — Firmographic lookalike search
  3. POST /prospects/hook-generator     — Cold-outreach hook generation
  4. POST /prospects/prospect-brief     — 60-second prospect briefing
  5. POST /prospects/search-nl          — Natural-language prospect search
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── 1. Ultimate Profile ──────────────────────────────────────────────────────


class UltimateProfileRequest(BaseModel):
    """Body for POST /prospects/ultimate-profile."""

    prospect_id: str = Field(..., description="CUID of the prospect to profile")
    llm_config_id: int | None = Field(
        default=None, description="Optional LlmConfig.id override; uses tenant default if omitted"
    )


class UltimateProfileData(BaseModel):
    """Structured business profile returned by the deep-research agent."""

    what_they_do: str = ""
    products: list[str] = []
    target_market: str = ""
    tech_stack: list[str] = []
    company_size: str = ""
    industry: str = ""
    pain_points: list[str] = []
    buying_signals: list[str] = []
    competitors: list[str] = []
    icp_fit_score: int | None = None
    recommended_angle: str = ""
    confidence_score: float | None = None


class UltimateProfileResponse(BaseModel):
    """Response for POST /prospects/ultimate-profile."""

    success: bool
    prospect_id: str
    company: str = ""
    sources_analyzed: int = 0
    profile: UltimateProfileData = Field(default_factory=UltimateProfileData)


# ── 2. Lookalike ─────────────────────────────────────────────────────────────


class LookalikeRequest(BaseModel):
    """Body for POST /prospects/lookalike."""

    seed_prospect_id: str | None = Field(
        default=None, description="CUID of the seed prospect"
    )
    seed_company_domain: str | None = Field(
        default=None, description="Domain to use as seed if no prospect ID"
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max lookalikes to return")


class LookalikeSeed(BaseModel):
    """Summary of the seed prospect used for lookalike search."""

    id: str
    name: str
    title: str | None = None
    company: str | None = None
    domain: str | None = None
    seniority: str | None = None


class LookalikeCandidate(BaseModel):
    """One lookalike prospect with similarity metadata."""

    id: str
    first_name: str = ""
    last_name: str = ""
    title: str | None = None
    company: str | None = None
    domain: str | None = None
    email: str | None = None
    similarity_score: float = 0.0
    matched_features: list[str] = []


class LookalikeResponse(BaseModel):
    """Response for POST /prospects/lookalike."""

    success: bool
    seed: LookalikeSeed | None = None
    lookalikes: list[LookalikeCandidate] = []
    count: int = 0


# ── 3. Hook Generator ────────────────────────────────────────────────────────


class HookGeneratorRequest(BaseModel):
    """Body for POST /prospects/hook-generator."""

    prospect_id: str = Field(..., description="CUID of the prospect")
    llm_config_id: int | None = Field(
        default=None, description="Optional LlmConfig.id override"
    )


class HookGeneratorResponse(BaseModel):
    """Response for POST /prospects/hook-generator."""

    success: bool
    hooks: list[str] = []
    source: Literal["llm", "fallback"] = "fallback"


# ── 4. Prospect Brief ────────────────────────────────────────────────────────


class ProspectBriefRequest(BaseModel):
    """Body for POST /prospects/prospect-brief."""

    prospect_id: str = Field(..., description="CUID of the prospect")
    llm_config_id: int | None = Field(
        default=None, description="Optional LlmConfig.id override"
    )


class ProspectBriefData(BaseModel):
    """Structured 60-second prospect briefing."""

    summary: str = ""
    key_insights: list[str] = []
    recommended_approach: str = ""
    talking_points: list[str] = []
    risk_factors: list[str] = []


class ProspectBriefResponse(BaseModel):
    """Response for POST /prospects/prospect-brief."""

    success: bool
    brief: ProspectBriefData = Field(default_factory=ProspectBriefData)


# ── 5. NL Prospect Search ────────────────────────────────────────────────────


class NlSearchRequest(BaseModel):
    """Body for POST /prospects/search-nl."""

    query: str = Field(..., min_length=1, description="Natural-language search query")
    llm_config_id: int | None = Field(
        default=None, description="Optional LlmConfig.id override"
    )


class NlSearchDbMatch(BaseModel):
    """A prospect matched from the database."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    firstName: str = ""
    lastName: str = ""
    email: str | None = None
    title: str | None = None
    company: str | None = None
    domain: str | None = None
    seniority: str | None = None
    icpFitScore: int | None = None


class NlSearchWebResult(BaseModel):
    """A prospect lead found via web search."""

    name: str = ""
    title: str | None = None
    company: str | None = None
    domain: str | None = None
    source_url: str = ""
    snippet: str = ""


class NlSearchResponse(BaseModel):
    """Response for POST /prospects/search-nl."""

    success: bool
    interpretation: dict[str, Any] = {}
    db_matches: list[NlSearchDbMatch] = []
    db_match_count: int = 0
    web_results: list[NlSearchWebResult] = []
    web_result_count: int = 0


__all__ = [
    "UltimateProfileRequest",
    "UltimateProfileData",
    "UltimateProfileResponse",
    "LookalikeRequest",
    "LookalikeSeed",
    "LookalikeCandidate",
    "LookalikeResponse",
    "HookGeneratorRequest",
    "HookGeneratorResponse",
    "ProspectBriefRequest",
    "ProspectBriefData",
    "ProspectBriefResponse",
    "NlSearchRequest",
    "NlSearchDbMatch",
    "NlSearchWebResult",
    "NlSearchResponse",
]
