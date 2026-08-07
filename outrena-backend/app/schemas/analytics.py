"""analytics.py — 5-layer closed-loop analytics + diagnose contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CampaignMetricResponse(BaseModel):
    """Aggregated campaign metrics computed from the Sequence table.

    Task 3-a / FIX 1: previously this schema was ORM-backed
    (``from_attributes=True``) and read directly from the now-dropped
    CampaignMetric table. The table was dead (no populator), so the
    endpoint always returned ``[]``. This is now a **plain computed DTO**
    — the analytics service aggregates from Sequence rows grouped by
    campaign + date and constructs this schema directly. The field shape
    is unchanged so the frontend API contract is preserved.
    """

    id: str  # synthetic: f"{campaignId}:{date}" — no longer a DB row id
    campaignId: str
    date: datetime
    totalSent: int
    totalOpened: int
    totalReplied: int
    totalBounced: int
    openRate: float
    replyRate: float
    bounceRate: float
    diagnosticNote: str | None


class CampaignResultResponse(BaseModel):
    id: str
    campaignId: str
    totalSent: int
    totalReplied: int
    totalPositive: int
    totalBounced: int
    replyRate: float
    positiveReplyRate: float
    bounceRate: float
    whatWorked: str | None
    whatDidntWork: str | None
    nextActions: str | None
    insights: str | None
    generatedAt: datetime

    model_config = {"from_attributes": True}


class DiagnoseRequest(BaseModel):
    """Body for POST /analytics/diagnose — runs the 5-layer closed loop."""
    campaignId: str | None = None


class DiagnoseLayerResult(BaseModel):
    layer: str  # delivery | open | reply | pipeline | content
    status: str  # ok | warn | critical
    metric: str
    value: float
    benchmark: float | None
    note: str


class DiagnoseResponse(BaseModel):
    campaignId: str | None
    layers: list[DiagnoseLayerResult]
    summary: str
    generatedAt: datetime


class DashboardAggregation(BaseModel):
    """Top-line counts used by the dashboard widget."""
    totalProspects: int
    totalCampaigns: int
    activeSequences: int
    sentThisWeek: int
    repliesThisWeek: int
    positiveRepliesThisWeek: int
    meetingsThisWeek: int
    pipelineValue: float
    averageReplyRate: float


class TimeSeriesPoint(BaseModel):
    date: str  # ISO date
    sent: int
    opened: int
    replied: int
    bounced: int


class TimeSeriesResponse(BaseModel):
    points: list[TimeSeriesPoint]


__all__ = [
    "CampaignMetricResponse",
    "CampaignResultResponse",
    "DiagnoseRequest",
    "DiagnoseLayerResult",
    "DiagnoseResponse",
    "DashboardAggregation",
    "TimeSeriesPoint",
    "TimeSeriesResponse",
]
