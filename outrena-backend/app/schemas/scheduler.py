"""scheduler.py — Scheduler status + manual tick + trigger + runs contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SchedulerStatusResponse(BaseModel):
    isRunning: bool
    lastTickAt: datetime | None
    nextTickAt: datetime | None
    sentSinceLastTick: int
    skippedSinceLastTick: int
    updatedAt: datetime

    model_config = {"from_attributes": True}


class ManualTickRequest(BaseModel):
    """Body for POST /scheduler/tick — force a single scheduler tick."""
    tenantScoped: bool = True  # only tick this tenant's sequences
    maxSend: int = 50


class ManualTickResponse(BaseModel):
    sent: int
    skipped: int
    durationMs: int
    tickedAt: datetime


class TriggerResponse(BaseModel):
    """Response for POST /scheduler/trigger."""
    triggered: bool
    message: str
    runId: str | None = None


class SchedulerRunResponse(BaseModel):
    """Single scheduler run log entry."""
    id: str
    startedAt: datetime
    completedAt: datetime | None
    status: str  # running | completed | failed
    sent: int
    skipped: int
    durationMs: int | None
    error: str | None

    model_config = {"from_attributes": True}


class SchedulerRunsListResponse(BaseModel):
    """Paginated list of scheduler runs."""
    items: list[SchedulerRunResponse]
    total: int


__all__ = [
    "SchedulerStatusResponse",
    "ManualTickRequest",
    "ManualTickResponse",
    "TriggerResponse",
    "SchedulerRunResponse",
    "SchedulerRunsListResponse",
]
