"""icp.py — IcpProfile CRUD + ICP suggestion / auto-discover schemas."""
from __future__ import annotations

from datetime import datetime

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IcpCreate(BaseModel):
    """Body for POST /icp-profiles.

    BUG-10 FIX:
      - persona is now optional (frontend form may not send it)
      - painPoints, topObjections, valueProps accept list[str] OR JSON string
      - buyingSignals added as optional
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    persona: str | None = None  # BUG-10: made optional
    companyType: str | None = None
    topObjections: list[str] = []
    painPoints: list[str] = []
    valueProps: list[str] = []
    buyingSignals: list[str] = []
    senderRole: str | None = None
    senderCompany: str | None = None
    senderOffer: str | None = None
    proofMetric: str | None = None

    @field_validator("topObjections", "painPoints", "valueProps", "buyingSignals", mode="before")
    @classmethod
    def _parse_json_list(cls, v: object) -> list[str]:
        """Parse JSON string or list to list[str]."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
                return []
            except (json.JSONDecodeError, TypeError, ValueError):
                return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []


class IcpUpdate(BaseModel):
    """Body for PUT /icp-profiles/{icp_id}."""

    name: str | None = None
    persona: str | None = None
    companyType: str | None = None
    topObjections: list[str] | None = None
    painPoints: list[str] | None = None
    valueProps: list[str] | None = None
    senderRole: str | None = None
    senderCompany: str | None = None
    senderOffer: str | None = None
    proofMetric: str | None = None


class IcpResponse(BaseModel):
    """Public shape of an IcpProfile row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    persona: str | None = None
    companyType: str | None = None
    topObjections: list[str] = []
    painPoints: list[str] = []
    valueProps: list[str] = []
    senderRole: str | None = None
    senderCompany: str | None = None
    senderOffer: str | None = None
    proofMetric: str | None = None
    createdAt: datetime
    updatedAt: datetime

    @field_validator("topObjections", "painPoints", "valueProps", mode="before")
    @classmethod
    def _parse_json_list(cls, v: object) -> list[str]:
        """Parse JSON string or list to list[str]."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
                return []
            except (json.JSONDecodeError, TypeError, ValueError):
                return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []


class IcpSuggestRequest(BaseModel):
    """Body for POST /icp-profiles/suggest — LLM suggests an ICP.

    BUG-08 FIX: Frontend sends ``{ "seed": "..." }`` but the LLM prompt
    uses ``productOrService``.  ``seed`` is now an alias for
    ``productOrService`` with ``populate_by_name=True`` so both names
    are accepted.
    """

    model_config = ConfigDict(populate_by_name=True)

    productOrService: str = Field(..., min_length=1, alias="seed")
    targetMarket: str | None = None
    additionalContext: str | None = None


class IcpSuggestResponse(BaseModel):
    """LLM-suggested ICP fields; client can review + POST /icp-profiles."""

    name: str
    persona: str | None = None
    companyType: str | None = None
    painPoints: list[str] = []
    valueProps: list[str] = []
    topObjections: list[str] = []
    raw: str | None = None


class AutoDiscoverRequest(BaseModel):
    """Body for POST /icp-profiles/auto-discover — derive ICP from prospect data."""

    prospects: list[dict] = Field(..., min_length=1)
    existingIcpId: str | None = None


class AutoDiscoverResponse(BaseModel):
    """Result of auto-discovering an ICP from prospect data."""

    icpId: str | None = None
    suggestedPersona: str
    commonAttributes: dict = {}
    fitScores: list[dict] = []
    raw: str | None = None


__all__ = [
    "IcpCreate",
    "IcpUpdate",
    "IcpResponse",
    "IcpSuggestRequest",
    "IcpSuggestResponse",
    "AutoDiscoverRequest",
    "AutoDiscoverResponse",
]
