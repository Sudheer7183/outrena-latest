"""deals.py — Pipeline deal + Deal Health contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DealCreate(BaseModel):
    title: str
    value: float = 0.0
    stage: str = "qualified"
    prospectId: str | None = None
    campaignId: str | None = None
    notes: str | None = None
    expectedClose: datetime | None = None
    source: str = "cold_email"


class DealUpdate(BaseModel):
    title: str | None = None
    value: float | None = None
    stage: str | None = None
    notes: str | None = None
    expectedClose: datetime | None = None
    closedAt: datetime | None = None
    healthStatus: str | None = None
    healthReason: str | None = None


class DealResponse(BaseModel):
    id: str
    title: str
    value: float
    stage: str
    prospectId: str | None
    campaignId: str | None
    notes: str | None
    expectedClose: datetime | None
    closedAt: datetime | None
    source: str
    healthStatus: str | None
    healthReason: str | None
    healthCheckedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class DealSuggestRequest(BaseModel):
    """Body for POST /deals/{id}/deal-suggest — AI next-step recommendation."""
    dealId: str


class DealSuggestResponse(BaseModel):
    dealId: str
    suggestion: str
    nextAction: str
    confidence: float


class DealHealthSignal(BaseModel):
    """A single factor contributing to the deal health score."""
    type: str         # e.g. "recency", "response_rate", "stage_velocity", "close_date"
    weight: int       # contribution points (out of 100 total)
    description: str
    passing: bool     # True = positive signal, False = risk signal


class DealHealthResponse(BaseModel):
    """Computed health for a deal — numeric score (0-100) + traffic-light + signals."""
    dealId: str
    score: int                      # 0-100 composite health score
    healthStatus: str               # red (<40) | yellow (40-69) | green (≥70)
    healthReason: str               # human-readable summary
    signals: list[DealHealthSignal] # per-factor breakdown (FR-E8-003)
    checkedAt: datetime


class KanbanStageResponse(BaseModel):
    """A single Kanban stage with its deals."""
    id: str
    name: str
    deals: list[DealResponse]


class KanbanBoardResponse(BaseModel):
    """All deals grouped by stage — for the Kanban UI.

    BUG-24 FIX: stages is now list[KanbanStageResponse] (frontend expects array, not dict).
    """
    stages: list[KanbanStageResponse]


__all__ = [
    "DealCreate",
    "DealUpdate",
    "DealResponse",
    "DealSuggestRequest",
    "DealSuggestResponse",
    "DealHealthResponse",
    "KanbanStageResponse",
    "KanbanBoardResponse",
]
