# """scheduler.py — Scheduler status + manual tick + trigger + runs contracts."""
# from __future__ import annotations

# from datetime import datetime

# from pydantic import BaseModel


# class SchedulerStatusResponse(BaseModel):
#     isRunning: bool
#     lastTickAt: datetime | None
#     nextTickAt: datetime | None
#     sentSinceLastTick: int
#     skippedSinceLastTick: int
#     updatedAt: datetime

#     model_config = {"from_attributes": True}


# class ManualTickRequest(BaseModel):
#     """Body for POST /scheduler/tick — force a single scheduler tick."""
#     tenantScoped: bool = True  # only tick this tenant's sequences
#     maxSend: int = 50


# class ManualTickResponse(BaseModel):
#     sent: int
#     skipped: int
#     durationMs: int
#     tickedAt: datetime


# class TriggerResponse(BaseModel):
#     """Response for POST /scheduler/trigger."""
#     triggered: bool
#     message: str
#     runId: str | None = None


# class SchedulerRunResponse(BaseModel):
#     """Single scheduler run log entry."""
#     id: str
#     startedAt: datetime
#     completedAt: datetime | None
#     status: str  # running | completed | failed
#     sent: int
#     skipped: int
#     durationMs: int | None
#     error: str | None

#     model_config = {"from_attributes": True}


# class SchedulerRunsListResponse(BaseModel):
#     """Paginated list of scheduler runs."""
#     items: list[SchedulerRunResponse]
#     total: int


# __all__ = [
#     "SchedulerStatusResponse",
#     "ManualTickRequest",
#     "ManualTickResponse",
#     "TriggerResponse",
#     "SchedulerRunResponse",
#     "SchedulerRunsListResponse",
# ]

"""scheduler.py — Scheduler status + manual tick + trigger + runs + new drill-down contracts."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

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


# ── NEW: Campaign Schedule view ───────────────────────────────────────────────

class CampaignScheduleItem(BaseModel):
    """Summary of scheduled sequences for one campaign."""
    campaignId: str
    campaignName: str
    campaignStatus: str
    totalSequences: int
    scheduled: int
    sent: int
    skipped: int
    replied: int
    bounced: int
    failed: int
    nextSendAt: datetime | None  # earliest scheduledFor among Scheduled rows


class CampaignScheduleListResponse(BaseModel):
    items: list[CampaignScheduleItem]
    total: int


# ── NEW: Skip reason drill-down ───────────────────────────────────────────────

class SkipLogItem(BaseModel):
    """One skip event recorded during a scheduler tick."""
    id: str
    runId: Optional[str]
    sequenceId: str
    campaignId: Optional[str]
    campaignName: Optional[str]
    prospectId: Optional[str]
    prospectEmail: Optional[str]
    skipReason: str
    detail: Optional[str]
    skippedAt: datetime

    model_config = {"from_attributes": True}


class SkipLogListResponse(BaseModel):
    items: list[SkipLogItem]
    total: int

    # Aggregated breakdown by reason for the summary chart
    reasonBreakdown: dict[str, int]


# ── NEW: Daily sent log ───────────────────────────────────────────────────────

class DailySentItem(BaseModel):
    """Aggregated daily sent count per campaign."""
    campaignId: str
    campaignName: str
    sentDate: date
    sentCount: int

    model_config = {"from_attributes": True}


class DailySentListResponse(BaseModel):
    items: list[DailySentItem]
    total: int


__all__ = [
    "SchedulerStatusResponse",
    "ManualTickRequest",
    "ManualTickResponse",
    "TriggerResponse",
    "SchedulerRunResponse",
    "SchedulerRunsListResponse",
    "CampaignScheduleItem",
    "CampaignScheduleListResponse",
    "SkipLogItem",
    "SkipLogListResponse",
    "DailySentItem",
    "DailySentListResponse",
]
