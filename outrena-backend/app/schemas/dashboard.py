"""dashboard.py — Top-line dashboard aggregation contracts."""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.analytics import DashboardAggregation, TimeSeriesResponse


class DashboardTopCampaign(BaseModel):
    """Top-campaign summary item."""
    id: str
    name: str
    status: str
    replyRate: float | None = None


class DashboardRecentReply(BaseModel):
    """Recent-reply summary item."""
    id: str
    prospectId: str | None = None
    repliedAt: str | None = None


class DashboardPipelineItem(BaseModel):
    """Pipeline-by-stage item."""
    id: str
    title: str
    value: float


class DashboardResponse(BaseModel):
    """Composite dashboard payload — single round-trip for the landing page."""
    aggregation: DashboardAggregation
    timeSeries: TimeSeriesResponse
    topCampaigns: list[DashboardTopCampaign]
    recentReplies: list[DashboardRecentReply]
    pipelineByStage: dict[str, list[DashboardPipelineItem]]
    # Per-user scope echo (SAAS2-USER-BE §K).
    # When the dashboard is filtered by owner_user_id, this is set to that
    # user_id. When tenant-wide, this is None.
    filtered_user_id: str | None = None


# ── Manager dashboard (per-user rollup) ────────────────────────────────────


class ManagerUserRollup(BaseModel):
    """One user rollup line — shape matches ManagerDashboardPage member rows."""
    user_id: str
    user_name: str = ""
    emails_sent: int = 0
    emails_bounced: int = 0
    complaints: int = 0
    campaigns_active: int = 0
    campaigns_total: int = 0
    prospects_contacted: int = 0
    replies_received: int = 0
    meetings_booked: int = 0
    pipeline_value: float = 0.0
    quota_used_pct: float = 0.0
    is_throttled: bool = False
    is_at_risk: bool = False


class ManagerDashboardResponse(BaseModel):
    """Manager rollup response matching the frontend ManagerDashboardPage shape.

    Frontend keys:  team_totals, members, top_performers, at_risk_users
    Legacy keys:    users, totals, averages, users_at_risk (kept for compat)
    """
    team_totals: dict
    members: list[ManagerUserRollup]
    top_performers: list[ManagerUserRollup] = []
    at_risk_users: list[ManagerUserRollup] = []
    # backward-compat aliases
    users: list[ManagerUserRollup] = []
    totals: dict = {}
    averages: dict = {}
    users_at_risk: list[ManagerUserRollup] = []


__all__ = [
    "DashboardResponse",
    "DashboardAggregation",
    "TimeSeriesResponse",
    "DashboardTopCampaign",
    "DashboardRecentReply",
    "DashboardPipelineItem",
    "ManagerUserRollup",
    "ManagerDashboardResponse",
]
