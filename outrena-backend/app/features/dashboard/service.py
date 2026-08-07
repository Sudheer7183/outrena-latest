"""dashboard_service.py — Composite dashboard payload (single round-trip).

Per-user + manager-rollup support (SAAS2-USER-BE §K):
  - get(db, user_id=None, role=None) — filters all metrics by owner_user_id
    when role == "REP" or an explicit user_id is passed.
  - get_manager_dashboard(db) — returns per-user rollup lines + tenant totals.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import Campaign, Deal, Sequence
from app.models.enums import EmailStatus
from app.models.prospect_models import Prospect
from app.schemas.analytics import DashboardAggregation, TimeSeriesResponse
from app.schemas.dashboard import (
    DashboardPipelineItem,
    DashboardRecentReply,
    DashboardResponse,
    DashboardTopCampaign,
    ManagerDashboardResponse,
    ManagerUserRollup,
)
from app.features.analytics.service import AnalyticsService
from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService


class DashboardService:
    def __init__(self, analytics: AnalyticsService | None = None) -> None:
        self._analytics = analytics or AnalyticsService()
        self._quota = UserEmailQuotaService()

    async def get(
        self,
        db: AsyncSession,
        *,
        user_id: str | None = None,
        role: str | None = None,
    ) -> DashboardResponse:
        """Composite dashboard payload.

        Per-user scoping:
          * role == "REP"  → force user_id = token.sub (own only).
          * MANAGER+ with explicit user_id → filter to that user.
          * MANAGER+ without user_id → tenant-wide.
        """
        effective_user_id: str | None = None
        if role is not None and role.upper() == "REP":
            effective_user_id = user_id
        elif user_id is not None and user_id != "all":
            effective_user_id = user_id

        aggregation = await self._analytics.dashboard_aggregation(db)
        time_series = await self._analytics.time_series(db, days=30)

        # Top 5 campaigns by reply count (stub — would join metrics in Phase 4)
        campaigns_stmt = select(Campaign)
        if effective_user_id is not None:
            campaigns_stmt = campaigns_stmt.where(
                Campaign.owner_user_id == effective_user_id
            )
        campaigns_stmt = campaigns_stmt.limit(5)
        campaigns_result = await db.execute(campaigns_stmt)
        top_campaigns = [
            DashboardTopCampaign(
                id=c.id, name=c.name, status=c.status, replyRate=None
            )
            for c in campaigns_result.scalars().all()
        ]

        # Recent replies — latest 10 sequences with repliedAt set
        replies_stmt = (
            select(Sequence)
            .where(Sequence.repliedAt.is_not(None))
            .order_by(Sequence.repliedAt.desc())
            .limit(10)
        )
        if effective_user_id is not None:
            replies_stmt = replies_stmt.where(
                Sequence.owner_user_id == effective_user_id
            )
        replies_result = await db.execute(replies_stmt)
        recent_replies = [
            DashboardRecentReply(
                id=s.id,
                prospectId=s.prospectId,
                repliedAt=s.repliedAt.isoformat() if s.repliedAt else None,
            )
            for s in replies_result.scalars().all()
        ]

        # Pipeline by stage
        deals_stmt = select(Deal)
        if effective_user_id is not None:
            # Deal has no owner_user_id column — filter via the Campaign join.
            deals_stmt = deals_stmt.join(
                Campaign, Deal.campaignId == Campaign.id, isouter=True
            ).where(
                (Campaign.owner_user_id == effective_user_id)
                | (Deal.campaignId.is_(None))
            )
        deals_result = await db.execute(deals_stmt)
        deals = list(deals_result.scalars().all())
        pipeline_by_stage: dict[str, list[DashboardPipelineItem]] = {}
        for d in deals:
            pipeline_by_stage.setdefault(d.stage, []).append(
                DashboardPipelineItem(id=d.id, title=d.title, value=d.value)
            )

        return DashboardResponse(
            aggregation=aggregation,
            timeSeries=time_series,
            topCampaigns=top_campaigns,
            recentReplies=recent_replies,
            pipelineByStage=pipeline_by_stage,
            filtered_user_id=effective_user_id,
        )

    async def get_manager_dashboard(
        self, db: AsyncSession
    ) -> ManagerDashboardResponse:
        """Per-user rollup across the tenant (MANAGER+ only).

        Builds one ManagerUserRollup per distinct owner_user_id seen across
        Campaign + Sequence + UserEmailQuota today. Users with no activity
        are omitted (their rollup is trivially zero).
        """
        # Collect every user_id seen today.
        today = datetime.now(timezone.utc).date()
        since = datetime.now(timezone.utc) - timedelta(days=30)

        # Distinct owners from Campaigns.
        camp_owners_result = await db.execute(
            select(Campaign.owner_user_id).distinct()
        )
        camp_owners = {r[0] for r in camp_owners_result.fetchall() if r[0]}

        # Distinct owners from Sequences (last 30d for activity metrics).
        seq_owners_result = await db.execute(
            select(Sequence.owner_user_id)
            .where(Sequence.createdAt >= since)
            .distinct()
        )
        seq_owners = {r[0] for r in seq_owners_result.fetchall() if r[0]}

        all_owners = camp_owners | seq_owners
        # Add 'system' rollup so legacy rows are still visible.
        all_owners.add("system")

        # Campaign counts per owner.
        camp_counts_result = await db.execute(
            select(
                Campaign.owner_user_id,
                func.count().label("total"),
                func.count().filter(Campaign.status == "active").label("active"),
            ).group_by(Campaign.owner_user_id)
        )
        camp_counts: dict[str, tuple[int, int]] = {
            r[0]: (int(r[1] or 0), int(r[2] or 0))
            for r in camp_counts_result.fetchall()
        }

        # Sequence activity per owner (last 30d).
        seq_metrics_result = await db.execute(
            select(
                Sequence.owner_user_id,
                func.count().label("sent"),
                func.count().filter(Sequence.repliedAt.is_not(None)).label("replies"),
                func.count().filter(Sequence.bouncedAt.is_not(None)).label("bounced"),
                func.count().filter(Sequence.prospectId.is_not(None)).label("contacted"),
            )
            .where(Sequence.createdAt >= since)
            .group_by(Sequence.owner_user_id)
        )
        seq_metrics: dict[str, dict[str, int]] = {
            r[0]: {
                "sent": int(r[1] or 0),
                "replies": int(r[2] or 0),
                "bounced": int(r[3] or 0),
                "contacted": int(r[4] or 0),
            }
            for r in seq_metrics_result.fetchall()
        }

        # Pipeline value per owner — via Deal join to Campaign.
        pipeline_result = await db.execute(
            select(
                Campaign.owner_user_id,
                func.sum(Deal.value).label("pipeline"),
                func.count().label("meetings"),
            )
            .select_from(Deal)
            .join(Campaign, Deal.campaignId == Campaign.id, isouter=True)
            .where(Deal.stage.notin_(["closed_lost"]))
            .group_by(Campaign.owner_user_id)
        )
        pipeline: dict[str, dict[str, Any]] = {
            (r[0] or "system"): {
                "pipeline": float(r[1] or 0.0),
                # Count deals as a proxy for meetings booked (Phase 4 will
                # join ReplyDraft.meetingBookedAt here).
                "meetings": int(r[2] or 0),
            }
            for r in pipeline_result.fetchall()
        }

        # Per-user quota snapshot (today).
        quota_summary = await self._quota.get_tenant_quota_summary(db)
        quota_by_user: dict[str, dict[str, Any]] = {
            q["user_id"]: q for q in quota_summary
        }

        rollups: list[ManagerUserRollup] = []
        for owner in all_owners:
            camp_total, camp_active = camp_counts.get(owner, (0, 0))
            seq = seq_metrics.get(owner, {})
            pipe = pipeline.get(owner, {"pipeline": 0.0, "meetings": 0})
            quota = quota_by_user.get(owner, {})
            rollups.append(
                ManagerUserRollup(
                    user_id=owner,
                    emails_sent=int(quota.get("emails_sent", 0) or seq.get("sent", 0)),
                    emails_bounced=int(quota.get("emails_bounced", 0) or seq.get("bounced", 0)),
                    complaints=int(quota.get("complaints", 0)),
                    campaigns_active=camp_active,
                    campaigns_total=camp_total,
                    prospects_contacted=seq.get("contacted", 0),
                    replies_received=seq.get("replies", 0),
                    meetings_booked=pipe["meetings"],
                    pipeline_value=pipe["pipeline"],
                    quota_used_pct=float(quota.get("used_pct", 0.0)),
                    is_throttled=bool(quota.get("is_throttled", False)),
                )
            )

        # Tenant-wide totals + averages.
        user_count = len(rollups)
        totals = {
            # canonical keys
            "users": user_count,
            "emails_sent": sum(r.emails_sent for r in rollups),
            "emails_bounced": sum(r.emails_bounced for r in rollups),
            "complaints": sum(r.complaints for r in rollups),
            "campaigns_active": sum(r.campaigns_active for r in rollups),
            "campaigns_total": sum(r.campaigns_total for r in rollups),
            "prospects_contacted": sum(r.prospects_contacted for r in rollups),
            "replies_received": sum(r.replies_received for r in rollups),
            "meetings_booked": sum(r.meetings_booked for r in rollups),
            "pipeline_value": round(sum(r.pipeline_value for r in rollups), 2),
            # frontend-expected aliases (ManagerDashboardPage.tsx references these)
            "total_users": user_count,
            "total_emails_sent": sum(r.emails_sent for r in rollups),
            "total_campaigns_active": sum(r.campaigns_active for r in rollups),
            "total_pipeline_value": round(sum(r.pipeline_value for r in rollups), 2),
        }
        averages = {
            "emails_sent_per_user": (
                round(totals["emails_sent"] / max(user_count, 1), 2)
            ),
            "replies_per_user": (
                round(totals["replies_received"] / max(len(rollups), 1), 2)
            ),
            "meetings_per_user": (
                round(totals["meetings_booked"] / max(len(rollups), 1), 2)
            ),
            "quota_used_pct_avg": (
                round(sum(r.quota_used_pct for r in rollups) / max(len(rollups), 1), 2)
            ),
        }

        # Top performers — by replies_received (descending), top 5.
        top_performers = sorted(
            rollups, key=lambda r: r.replies_received, reverse=True
        )[:5]

        # Users at risk — throttled, OR quota_used_pct >= 80, OR bounce rate >= 5%.
        users_at_risk = [
            r for r in rollups
            if r.is_throttled
            or r.quota_used_pct >= 80.0
            or (
                r.emails_sent > 0
                and (r.emails_bounced / max(r.emails_sent, 1)) >= 0.05
            )
        ]

        # Annotate is_at_risk on each rollup row (mirrors users_at_risk list).
        at_risk_ids = {r.user_id for r in users_at_risk}
        for r in rollups:
            r.is_at_risk = r.user_id in at_risk_ids

        return ManagerDashboardResponse(
            # Frontend-expected keys
            team_totals=totals,
            members=rollups,
            top_performers=top_performers,
            at_risk_users=users_at_risk,
            # Legacy backward-compat keys
            users=rollups,
            totals=totals,
            averages=averages,
            users_at_risk=users_at_risk,
        )


__all__ = ["DashboardService"]
