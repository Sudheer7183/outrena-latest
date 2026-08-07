"""prospect_source.py — Source + NL search + lookalike + brief contracts."""
from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator


class ProspectSourceResponse(BaseModel):
    id: str
    prospectId: str
    source: str
    query: str | None
    confidence: float | None
    rawPayload: str | None
    importedAt: datetime
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class SourceConfigCreate(BaseModel):
    """BUG-12 FIX: Accept frontend field aliases (dailyLimit → dailyQuota, etc.)."""

    model_config = {"extra": "ignore"}

    source: str  # apollo | clay | zoominfo | clearbit | hunter
    name: str
    isActive: bool = False
    apiKey: str | None = None
    dailyQuota: int = 100
    settings: dict = {}

    @field_validator("settings", mode="before")
    @classmethod
    def _parse_settings(cls, v: object) -> object:
        """BUG-09 FIX: Handle JSON string from DB for dict field."""
        if isinstance(v, str):
            return json.loads(v)
        return v

    @model_validator(mode="before")
    @classmethod
    def _normalise_aliases(cls, values: object) -> object:
        """BUG-12 FIX: Map frontend alias fields to backend names."""
        if isinstance(values, dict):
            # dailyLimit → dailyQuota
            if "dailyQuota" not in values and "dailyLimit" in values:
                values["dailyQuota"] = values["dailyLimit"]
            # apiKeyMasked → ignored (masked keys are read-only)
        return values


class SourceConfigUpdate(BaseModel):
    name: str | None = None
    isActive: bool | None = None
    apiKey: str | None = None
    dailyQuota: int | None = None
    settings: dict | None = None


class SourceConfigResponse(BaseModel):
    id: str
    source: str
    name: str
    isActive: bool
    apiKey: str | None
    dailyQuota: int
    usedToday: int
    settings: dict
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}

    @field_validator("settings", mode="before")
    @classmethod
    def _parse_settings(cls, v: object) -> object:
        """BUG-09 FIX: Handle JSON string from DB for dict field."""
        if isinstance(v, str):
            return json.loads(v)
        return v


class NaturalLanguageSearchRequest(BaseModel):
    """Body for POST /prospect-source/nl-search — NL→filter LLM."""
    query: str
    icpProfileId: str | None = None
    limit: int = 25


class ProspectSearchHit(BaseModel):
    """Lightweight prospect dict returned by NL search."""
    id: str
    firstName: str
    lastName: str
    email: str | None = None
    title: str | None = None
    company: str | None = None


class NaturalLanguageSearchResponse(BaseModel):
    interpretedFilters: dict
    prospects: list[ProspectSearchHit]
    count: int


class LookalikeRequest(BaseModel):
    """Body for POST /prospect-source/lookalike — find similar prospects."""
    prospectId: str
    limit: int = 25


class LookalikeHit(BaseModel):
    """Lookalike-prospect summary item."""
    id: str
    firstName: str | None = None
    lastName: str | None = None
    title: str | None = None
    company: str | None = None
    similarityScore: float = 0.0


class LookalikeResponse(BaseModel):
    seedProspectId: str
    lookalikes: list[LookalikeHit]
    count: int


class UltimateProfileRequest(BaseModel):
    prospectId: str


class UltimateProfileResponse(BaseModel):
    prospectId: str
    profile: dict  # enriched persona/firmographic/behavioral data


class ProspectBriefRequest(BaseModel):
    prospectId: str
    callType: str = "discovery"


class ProspectBriefResponse(BaseModel):
    prospectId: str
    brief: str


__all__ = [
    "ProspectSourceResponse",
    "SourceConfigCreate",
    "SourceConfigUpdate",
    "SourceConfigResponse",
    "NaturalLanguageSearchRequest",
    "NaturalLanguageSearchResponse",
    "ProspectSearchHit",
    "LookalikeRequest",
    "LookalikeResponse",
    "LookalikeHit",
    "UltimateProfileRequest",
    "UltimateProfileResponse",
    "ProspectBriefRequest",
    "ProspectBriefResponse",
]
