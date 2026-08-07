"""competitors.py — Competitor radar contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CompetitorCreate(BaseModel):
    prospectId: str | None = None
    name: str
    domain: str | None = None
    description: str | None = None
    positioning: str | None = None
    overlapScore: float | None = None
    threatLevel: str | None = None  # low | medium | high | critical
    source: str = "auto"


class CompetitorUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    description: str | None = None
    positioning: str | None = None
    overlapScore: float | None = None
    threatLevel: str | None = None  # low | medium | high | critical


class CompetitorResponse(BaseModel):
    id: str
    prospectId: str | None
    name: str
    domain: str | None
    description: str | None
    positioning: str | None
    overlapScore: float | None
    threatLevel: str | None  # low | medium | high | critical
    source: str
    createdAt: datetime

    model_config = {"from_attributes": True}


__all__ = [
    "CompetitorCreate",
    "CompetitorUpdate",
    "CompetitorResponse",
]
