# # # # # """analytics.py — 5-layer closed-loop analytics + diagnose contracts."""
# # # # # from __future__ import annotations

# # # # # from datetime import datetime

# # # # # from pydantic import BaseModel


# # # # # class CampaignMetricResponse(BaseModel):
# # # # #     """Aggregated campaign metrics computed from the Sequence table.

# # # # #     Task 3-a / FIX 1: previously this schema was ORM-backed
# # # # #     (``from_attributes=True``) and read directly from the now-dropped
# # # # #     CampaignMetric table. The table was dead (no populator), so the
# # # # #     endpoint always returned ``[]``. This is now a **plain computed DTO**
# # # # #     — the analytics service aggregates from Sequence rows grouped by
# # # # #     campaign + date and constructs this schema directly. The field shape
# # # # #     is unchanged so the frontend API contract is preserved.
# # # # #     """

# # # # #     id: str  # synthetic: f"{campaignId}:{date}" — no longer a DB row id
# # # # #     campaignId: str
# # # # #     date: datetime
# # # # #     totalSent: int
# # # # #     totalOpened: int
# # # # #     totalReplied: int
# # # # #     totalBounced: int
# # # # #     openRate: float
# # # # #     replyRate: float
# # # # #     bounceRate: float
# # # # #     diagnosticNote: str | None


# # # # # class CampaignResultResponse(BaseModel):
# # # # #     id: str
# # # # #     campaignId: str
# # # # #     totalSent: int
# # # # #     totalReplied: int
# # # # #     totalPositive: int
# # # # #     totalBounced: int
# # # # #     replyRate: float
# # # # #     positiveReplyRate: float
# # # # #     bounceRate: float
# # # # #     whatWorked: str | None
# # # # #     whatDidntWork: str | None
# # # # #     nextActions: str | None
# # # # #     insights: str | None
# # # # #     generatedAt: datetime

# # # # #     model_config = {"from_attributes": True}


# # # # # class DiagnoseRequest(BaseModel):
# # # # #     """Body for POST /analytics/diagnose — runs the 5-layer closed loop."""
# # # # #     campaignId: str | None = None


# # # # # class DiagnoseLayerResult(BaseModel):
# # # # #     layer: str  # delivery | open | reply | pipeline | content
# # # # #     status: str  # ok | warn | critical
# # # # #     metric: str
# # # # #     value: float
# # # # #     benchmark: float | None
# # # # #     note: str


# # # # # class DiagnoseResponse(BaseModel):
# # # # #     campaignId: str | None
# # # # #     layers: list[DiagnoseLayerResult]
# # # # #     summary: str
# # # # #     generatedAt: datetime


# # # # # class DashboardAggregation(BaseModel):
# # # # #     """Top-line counts used by the dashboard widget."""
# # # # #     totalProspects: int
# # # # #     totalCampaigns: int
# # # # #     activeSequences: int
# # # # #     sentThisWeek: int
# # # # #     repliesThisWeek: int
# # # # #     positiveRepliesThisWeek: int
# # # # #     meetingsThisWeek: int
# # # # #     pipelineValue: float
# # # # #     averageReplyRate: float


# # # # # class TimeSeriesPoint(BaseModel):
# # # # #     date: str  # ISO date
# # # # #     sent: int
# # # # #     opened: int
# # # # #     replied: int
# # # # #     bounced: int


# # # # # class TimeSeriesResponse(BaseModel):
# # # # #     points: list[TimeSeriesPoint]


# # # # # __all__ = [
# # # # #     "CampaignMetricResponse",
# # # # #     "CampaignResultResponse",
# # # # #     "DiagnoseRequest",
# # # # #     "DiagnoseLayerResult",
# # # # #     "DiagnoseResponse",
# # # # #     "DashboardAggregation",
# # # # #     "TimeSeriesPoint",
# # # # #     "TimeSeriesResponse",
# # # # # ]

# # # # """analytics.py — 5-layer closed-loop analytics + diagnose contracts."""
# # # # from __future__ import annotations

# # # # from datetime import datetime

# # # # from pydantic import BaseModel


# # # # class CampaignMetricResponse(BaseModel):
# # # #     """Aggregated campaign metrics computed from the Sequence table.

# # # #     Task 3-a / FIX 1: previously this schema was ORM-backed
# # # #     (``from_attributes=True``) and read directly from the now-dropped
# # # #     CampaignMetric table. The table was dead (no populator), so the
# # # #     endpoint always returned ``[]``. This is now a **plain computed DTO**
# # # #     — the analytics service aggregates from Sequence rows grouped by
# # # #     campaign + date and constructs this schema directly. The field shape
# # # #     is unchanged so the frontend API contract is preserved.
# # # #     """

# # # #     id: str  # synthetic: f"{campaignId}:{date}" — no longer a DB row id
# # # #     campaignId: str
# # # #     date: datetime
# # # #     totalSent: int
# # # #     totalOpened: int
# # # #     totalReplied: int
# # # #     totalBounced: int
# # # #     openRate: float
# # # #     replyRate: float
# # # #     bounceRate: float
# # # #     diagnosticNote: str | None


# # # # class CampaignResultResponse(BaseModel):
# # # #     id: str
# # # #     campaignId: str
# # # #     totalSent: int
# # # #     totalReplied: int
# # # #     totalPositive: int
# # # #     totalBounced: int
# # # #     replyRate: float
# # # #     positiveReplyRate: float
# # # #     bounceRate: float
# # # #     whatWorked: str | None
# # # #     whatDidntWork: str | None
# # # #     nextActions: str | None
# # # #     insights: str | None
# # # #     generatedAt: datetime

# # # #     model_config = {"from_attributes": True}


# # # # class DiagnoseRequest(BaseModel):
# # # #     """Body for POST /analytics/diagnose — runs the 5-layer closed loop."""
# # # #     campaignId: str | None = None


# # # # class DiagnoseLayerResult(BaseModel):
# # # #     layer: str  # delivery | open | reply | pipeline | content
# # # #     status: str  # ok | warn | critical
# # # #     metric: str
# # # #     value: float
# # # #     benchmark: float | None
# # # #     note: str


# # # # class DiagnoseResponse(BaseModel):
# # # #     campaignId: str | None
# # # #     layers: list[DiagnoseLayerResult]
# # # #     summary: str
# # # #     generatedAt: datetime


# # # # class DashboardAggregation(BaseModel):
# # # #     """Top-line counts used by the dashboard widget."""
# # # #     totalProspects: int
# # # #     totalCampaigns: int
# # # #     activeSequences: int
# # # #     sentThisWeek: int
# # # #     repliesThisWeek: int
# # # #     positiveRepliesThisWeek: int
# # # #     meetingsThisWeek: int
# # # #     pipelineValue: float
# # # #     averageReplyRate: float


# # # # class TimeSeriesPoint(BaseModel):
# # # #     date: str  # ISO date
# # # #     sent: int
# # # #     opened: int
# # # #     replied: int
# # # #     bounced: int


# # # # class TimeSeriesResponse(BaseModel):
# # # #     points: list[TimeSeriesPoint]


# # # # # ── NEW: Tracking summary for the Reply Inbox dashboard panel ─────────────────

# # # # class TrackingSummaryResponse(BaseModel):
# # # #     """Tenant-wide email tracking summary, aggregated from Sequence rows.

# # # #     Returned by GET /analytics/tracking-summary.
# # # #     All counts are for the requested date range (default: last 30 days).
# # # #     Rates are expressed as fractions (0.0–1.0), not percentages.
# # # #     """
# # # #     period_days: int
# # # #     total_sent: int
# # # #     total_opened: int    # populated only when MailBridge open_tracking=true
# # # #     total_replied: int
# # # #     total_bounced: int
# # # #     open_rate: float
# # # #     reply_rate: float
# # # #     bounce_rate: float
# # # #     # Breakdown by bounce reason — top 5 most common reasons
# # # #     top_bounce_reasons: list[dict[str, object]]
# # # #     # Counts by status for the funnel bar
# # # #     by_status: dict[str, int]


# # # # __all__ = [
# # # #     "CampaignMetricResponse",
# # # #     "CampaignResultResponse",
# # # #     "DiagnoseRequest",
# # # #     "DiagnoseLayerResult",
# # # #     "DiagnoseResponse",
# # # #     "DashboardAggregation",
# # # #     "TimeSeriesPoint",
# # # #     "TimeSeriesResponse",
# # # #     "TrackingSummaryResponse",
# # # # ]

# # # """analytics.py — 5-layer closed-loop analytics + diagnose contracts."""
# # # from __future__ import annotations

# # # from datetime import datetime

# # # from pydantic import BaseModel


# # # class CampaignMetricResponse(BaseModel):
# # #     """Aggregated campaign metrics computed from the Sequence table.

# # #     Task 3-a / FIX 1: previously this schema was ORM-backed
# # #     (``from_attributes=True``) and read directly from the now-dropped
# # #     CampaignMetric table. The table was dead (no populator), so the
# # #     endpoint always returned ``[]``. This is now a **plain computed DTO**
# # #     — the analytics service aggregates from Sequence rows grouped by
# # #     campaign + date and constructs this schema directly. The field shape
# # #     is unchanged so the frontend API contract is preserved.
# # #     """

# # #     id: str  # synthetic: f"{campaignId}:{date}" — no longer a DB row id
# # #     campaignId: str
# # #     date: datetime
# # #     totalSent: int
# # #     totalOpened: int
# # #     totalReplied: int
# # #     totalBounced: int
# # #     openRate: float
# # #     replyRate: float
# # #     bounceRate: float
# # #     diagnosticNote: str | None


# # # class CampaignResultResponse(BaseModel):
# # #     id: str
# # #     campaignId: str
# # #     totalSent: int
# # #     totalReplied: int
# # #     totalPositive: int
# # #     totalBounced: int
# # #     replyRate: float
# # #     positiveReplyRate: float
# # #     bounceRate: float
# # #     whatWorked: str | None
# # #     whatDidntWork: str | None
# # #     nextActions: str | None
# # #     insights: str | None
# # #     generatedAt: datetime

# # #     model_config = {"from_attributes": True}


# # # class DiagnoseRequest(BaseModel):
# # #     """Body for POST /analytics/diagnose — runs the 5-layer closed loop."""
# # #     campaignId: str | None = None


# # # class DiagnoseLayerResult(BaseModel):
# # #     layer: str  # delivery | open | reply | pipeline | content
# # #     status: str  # ok | warn | critical
# # #     metric: str
# # #     value: float
# # #     benchmark: float | None
# # #     note: str


# # # class DiagnoseResponse(BaseModel):
# # #     campaignId: str | None
# # #     layers: list[DiagnoseLayerResult]
# # #     summary: str
# # #     generatedAt: datetime


# # # class DashboardAggregation(BaseModel):
# # #     """Top-line counts used by the dashboard widget."""
# # #     totalProspects: int
# # #     totalCampaigns: int
# # #     activeSequences: int
# # #     sentThisWeek: int
# # #     repliesThisWeek: int
# # #     positiveRepliesThisWeek: int
# # #     meetingsThisWeek: int
# # #     pipelineValue: float
# # #     averageReplyRate: float


# # # class TimeSeriesPoint(BaseModel):
# # #     date: str  # ISO date
# # #     sent: int
# # #     opened: int
# # #     replied: int
# # #     bounced: int


# # # class TimeSeriesResponse(BaseModel):
# # #     points: list[TimeSeriesPoint]


# # # # ── NEW: Tracking summary for the Reply Inbox dashboard panel ─────────────────

# # # class TrackingSummaryResponse(BaseModel):
# # #     """Tenant-wide email tracking summary, aggregated from Sequence rows.

# # #     Returned by GET /analytics/tracking-summary.
# # #     All counts are for the requested date range (default: last 30 days).
# # #     Rates are expressed as fractions (0.0–1.0), not percentages.
# # #     """
# # #     period_days: int
# # #     total_sent: int
# # #     total_opened: int    # populated only when MailBridge open_tracking=true
# # #     total_replied: int
# # #     total_bounced: int
# # #     open_rate: float
# # #     reply_rate: float
# # #     bounce_rate: float
# # #     # Breakdown by bounce reason — top 5 most common reasons
# # #     top_bounce_reasons: list[dict[str, object]]
# # #     # Counts by status for the funnel bar
# # #     by_status: dict[str, int]


# # # __all__ = [
# # #     "CampaignMetricResponse",
# # #     "CampaignResultResponse",
# # #     "DiagnoseRequest",
# # #     "DiagnoseLayerResult",
# # #     "DiagnoseResponse",
# # #     "DashboardAggregation",
# # #     "TimeSeriesPoint",
# # #     "TimeSeriesResponse",
# # #     "TrackingSummaryResponse",
# # # ]
# # """analytics.py — 5-layer closed-loop analytics + diagnose contracts."""
# # from __future__ import annotations

# # from datetime import datetime

# # from pydantic import BaseModel


# # class CampaignMetricResponse(BaseModel):
# #     """Aggregated campaign metrics computed from the Sequence table.

# #     Task 3-a / FIX 1: previously this schema was ORM-backed
# #     (``from_attributes=True``) and read directly from the now-dropped
# #     CampaignMetric table. The table was dead (no populator), so the
# #     endpoint always returned ``[]``. This is now a **plain computed DTO**
# #     — the analytics service aggregates from Sequence rows grouped by
# #     campaign + date and constructs this schema directly. The field shape
# #     is unchanged so the frontend API contract is preserved.
# #     """

# #     id: str  # synthetic: f"{campaignId}:{date}" — no longer a DB row id
# #     campaignId: str
# #     date: datetime
# #     totalSent: int
# #     totalOpened: int
# #     totalReplied: int
# #     totalBounced: int
# #     openRate: float
# #     replyRate: float
# #     bounceRate: float
# #     diagnosticNote: str | None


# # class CampaignResultResponse(BaseModel):
# #     id: str
# #     campaignId: str
# #     totalSent: int
# #     totalReplied: int
# #     totalPositive: int
# #     totalBounced: int
# #     replyRate: float
# #     positiveReplyRate: float
# #     bounceRate: float
# #     whatWorked: str | None
# #     whatDidntWork: str | None
# #     nextActions: str | None
# #     insights: str | None
# #     generatedAt: datetime

# #     model_config = {"from_attributes": True}


# # class DiagnoseRequest(BaseModel):
# #     """Body for POST /analytics/diagnose — runs the 5-layer closed loop."""
# #     campaignId: str | None = None


# # class DiagnoseLayerResult(BaseModel):
# #     layer: str  # delivery | open | reply | pipeline | content
# #     status: str  # ok | warn | critical
# #     metric: str
# #     value: float
# #     benchmark: float | None
# #     note: str


# # class DiagnoseResponse(BaseModel):
# #     campaignId: str | None
# #     layers: list[DiagnoseLayerResult]
# #     summary: str
# #     generatedAt: datetime


# # class DashboardAggregation(BaseModel):
# #     """Top-line counts used by the dashboard widget."""
# #     totalProspects: int
# #     totalCampaigns: int
# #     activeSequences: int
# #     sentThisWeek: int
# #     repliesThisWeek: int
# #     positiveRepliesThisWeek: int
# #     meetingsThisWeek: int
# #     pipelineValue: float
# #     averageReplyRate: float


# # class TimeSeriesPoint(BaseModel):
# #     date: str  # ISO date
# #     sent: int
# #     opened: int
# #     replied: int
# #     bounced: int


# # class TimeSeriesResponse(BaseModel):
# #     points: list[TimeSeriesPoint]


# # __all__ = [
# #     "CampaignMetricResponse",
# #     "CampaignResultResponse",
# #     "DiagnoseRequest",
# #     "DiagnoseLayerResult",
# #     "DiagnoseResponse",
# #     "DashboardAggregation",
# #     "TimeSeriesPoint",
# #     "TimeSeriesResponse",
# # ]
# """analytics.py — 5-layer closed-loop analytics + diagnose contracts."""
# from __future__ import annotations

# from datetime import datetime

# from pydantic import BaseModel


# class CampaignMetricResponse(BaseModel):
#     """Aggregated campaign metrics computed from the Sequence table.

#     Task 3-a / FIX 1: previously this schema was ORM-backed
#     (``from_attributes=True``) and read directly from the now-dropped
#     CampaignMetric table. The table was dead (no populator), so the
#     endpoint always returned ``[]``. This is now a **plain computed DTO**
#     — the analytics service aggregates from Sequence rows grouped by
#     campaign + date and constructs this schema directly. The field shape
#     is unchanged so the frontend API contract is preserved.
#     """

#     id: str  # synthetic: f"{campaignId}:{date}" — no longer a DB row id
#     campaignId: str
#     date: datetime
#     totalSent: int
#     totalOpened: int
#     totalReplied: int
#     totalBounced: int
#     openRate: float
#     replyRate: float
#     bounceRate: float
#     diagnosticNote: str | None


# class CampaignResultResponse(BaseModel):
#     id: str
#     campaignId: str
#     totalSent: int
#     totalReplied: int
#     totalPositive: int
#     totalBounced: int
#     replyRate: float
#     positiveReplyRate: float
#     bounceRate: float
#     whatWorked: str | None
#     whatDidntWork: str | None
#     nextActions: str | None
#     insights: str | None
#     generatedAt: datetime

#     model_config = {"from_attributes": True}


# class DiagnoseRequest(BaseModel):
#     """Body for POST /analytics/diagnose — runs the 5-layer closed loop."""
#     campaignId: str | None = None


# class DiagnoseLayerResult(BaseModel):
#     layer: str  # delivery | open | reply | pipeline | content
#     status: str  # ok | warn | critical
#     metric: str
#     value: float
#     benchmark: float | None
#     note: str


# class DiagnoseResponse(BaseModel):
#     campaignId: str | None
#     layers: list[DiagnoseLayerResult]
#     summary: str
#     generatedAt: datetime


# class DashboardAggregation(BaseModel):
#     """Top-line counts used by the dashboard widget."""
#     totalProspects: int
#     totalCampaigns: int
#     activeSequences: int
#     sentThisWeek: int
#     repliesThisWeek: int
#     positiveRepliesThisWeek: int
#     meetingsThisWeek: int
#     pipelineValue: float
#     averageReplyRate: float


# class TimeSeriesPoint(BaseModel):
#     date: str  # ISO date
#     sent: int
#     opened: int
#     replied: int
#     bounced: int


# class TimeSeriesResponse(BaseModel):
#     points: list[TimeSeriesPoint]




# # ── Tracking summary for Reply Inbox dashboard ────────────────────────────────

# class TrackingSummaryResponse(BaseModel):
#     """Tenant-wide email tracking summary aggregated from Sequence rows.

#     Returned by GET /api/v1/analytics/tracking-summary.
#     Rates are fractions (0.0–1.0). period_days is the requested window.
#     """
#     period_days: int
#     total_sent: int
#     total_replied: int
#     total_bounced: int
#     reply_rate: float
#     bounce_rate: float
#     top_bounce_reasons: list[dict]   # [{"reason": str, "count": int}]
#     by_status: dict[str, int]        # {"Sent": N, "Replied": M, ...}

# __all__ = [
#     "CampaignMetricResponse",
#     "CampaignResultResponse",
#     "DiagnoseRequest",
#     "DiagnoseLayerResult",
#     "DiagnoseResponse",
#     "DashboardAggregation",
#     "TimeSeriesPoint",
#     "TimeSeriesResponse",
# ]

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
    activeCampaigns: int = 0   # campaigns with status == "active"
    activeSequences: int
    sentThisWeek: int
    repliesThisWeek: int
    positiveRepliesThisWeek: int
    meetingsThisWeek: int
    pipelineValue: float
    averageReplyRate: float
    # Email quota fields — populated from domain warming schedule when a fully
    # DNS-verified domain exists, else from the env DEFAULT_USER_DAILY_EMAIL_QUOTA.
    emailQuotaDaily: int = 0   # daily send cap
    emailQuotaSource: str = "env"  # "domain_warming" | "env"


class TimeSeriesPoint(BaseModel):
    date: str  # ISO date
    sent: int
    opened: int
    replied: int
    bounced: int


class TimeSeriesResponse(BaseModel):
    points: list[TimeSeriesPoint]




# ── Tracking summary for Reply Inbox dashboard ────────────────────────────────

class TrackingSummaryResponse(BaseModel):
    """Tenant-wide email tracking summary aggregated from Sequence rows.

    Returned by GET /api/v1/analytics/tracking-summary.
    Rates are fractions (0.0–1.0). period_days is the requested window.
    """
    period_days: int
    total_sent: int
    total_replied: int
    total_bounced: int
    reply_rate: float
    bounce_rate: float
    top_bounce_reasons: list[dict]   # [{"reason": str, "count": int}]
    by_status: dict[str, int]        # {"Sent": N, "Replied": M, ...}

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