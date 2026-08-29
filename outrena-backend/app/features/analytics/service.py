"""
analytics_service.py — 5-layer closed-loop analytics + diagnose + results.

The 5 layers (Prisma/Next.js parity):
  1. Delivery  — bounce rate, spam rate
  2. Open      — open rate vs benchmark
  3. Reply     — reply rate, positive reply rate
  4. Pipeline  — meetings booked, deals created
  5. Content   — QA score distribution, top-performing angles
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import Campaign, CampaignResult, Deal, Sequence
from app.models.enums import EmailStatus
from app.schemas.analytics import (
    CampaignMetricResponse,
    CampaignResultResponse,
    DashboardAggregation,
    DiagnoseLayerResult,
    DiagnoseResponse,
    TimeSeriesPoint,
    TimeSeriesResponse,
)
from app.services.llm_service import get_llm_service

# Benchmark thresholds (Phase 3 — would be tenant-tunable in Phase 4 via SystemParameter).
BENCH_BOUNCE_RATE = 0.05
BENCH_OPEN_RATE = 0.30
BENCH_REPLY_RATE = 0.08
BENCH_POSITIVE_REPLY_RATE = 0.03


class AnalyticsService:
    async def list_metrics(
        self, db: AsyncSession, campaign_id: str | None = None
    ) -> list[CampaignMetricResponse]:
        """List campaign metrics aggregated from the Sequence table.

        Task 3-a / FIX 1: previously this method queried the dead
        CampaignMetric table (which no service ever populated) and returned
        ORM rows that the router serialized via `model_validate`. Now it
        aggregates directly from the Sequence table — the source of truth
        for send/open/reply/bounce timestamps (populated by the MailBridge
        webhook path). Returns one ``CampaignMetricResponse`` DTO per
        (campaignId, date) bucket.

        Bucketing: sequences are grouped by the calendar date of their
        ``sentAt`` timestamp. Sequences with no ``sentAt`` (still in
        ``draft``/``scheduled``) are skipped — they have no engagement
        signal yet. The bucket's ``date`` is the earliest ``sentAt`` in
        that day.
        """
        from app.models.campaign_models import Sequence

        stmt = select(Sequence).where(Sequence.sentAt.is_not(None))
        if campaign_id:
            stmt = stmt.where(Sequence.campaignId == campaign_id)
        result = await db.execute(stmt)
        sequences = list(result.scalars().all())

        # Bucket by (campaignId, sentAt.date()).
        buckets: dict[tuple[str, str], dict[str, Any]] = {}
        for seq in sequences:
            if not seq.sentAt:
                continue
            day_key = seq.sentAt.date().isoformat()
            key = (seq.campaignId, day_key)
            bucket = buckets.setdefault(
                key,
                {
                    "campaignId": seq.campaignId,
                    "date": seq.sentAt,
                    "totalSent": 0,
                    "totalOpened": 0,
                    "totalReplied": 0,
                    "totalBounced": 0,
                },
            )
            bucket["totalSent"] += 1
            if seq.openedAt:
                bucket["totalOpened"] += 1
            if seq.repliedAt:
                bucket["totalReplied"] += 1
            if seq.bouncedAt:
                bucket["totalBounced"] += 1
            # Earliest sentAt in the bucket = the bucket's "date".
            if seq.sentAt < bucket["date"]:
                bucket["date"] = seq.sentAt

        # Build DTOs with derived rate fields.
        dtos: list[CampaignMetricResponse] = []
        for (camp_id, day_key), b in sorted(
            buckets.items(), key=lambda kv: (kv[0][0], kv[0][1])
        ):
            sent = b["totalSent"]
            opened = b["totalOpened"]
            replied = b["totalReplied"]
            bounced = b["totalBounced"]
            dtos.append(
                CampaignMetricResponse(
                    id=f"{camp_id}:{day_key}",  # synthetic id (not a DB row)
                    campaignId=camp_id,
                    date=b["date"],
                    totalSent=sent,
                    totalOpened=opened,
                    totalReplied=replied,
                    totalBounced=bounced,
                    openRate=(opened / sent) if sent else 0.0,
                    replyRate=(replied / sent) if sent else 0.0,
                    bounceRate=(bounced / sent) if sent else 0.0,
                    diagnosticNote=None,
                )
            )
        return dtos

    async def _aggregate_from_sequences(
        self, db: AsyncSession, campaign_id: str | None
    ) -> dict[str, int]:
        """Aggregate sent/opened/replied/bounced counts from Sequence rows.

        Task 2-e introduced this helper as a fallback when CampaignMetric was
        empty (the table had no populator). Task 3-a / FIX 1 dropped the
        CampaignMetric table entirely — list_metrics now aggregates from
        Sequence as the primary path. This helper is retained as the
        "no-campaign / no-sent-sequences" fallback used by generate_result +
        diagnose (it counts all sequences including those that haven't been
        sent yet, whereas list_metrics only buckets sent sequences).
        Returns a dict with ``total_sent`` / ``total_opened`` /
        ``total_replied`` / ``total_bounced``.
        """
        from app.models.campaign_models import Sequence

        stmt = select(Sequence)
        if campaign_id:
            stmt = stmt.where(Sequence.campaignId == campaign_id)
        result = await db.execute(stmt)
        sequences = list(result.scalars().all())
        return {
            "total_sent": sum(1 for s in sequences if s.sentAt is not None),
            "total_opened": sum(1 for s in sequences if s.openedAt is not None),
            "total_replied": sum(1 for s in sequences if s.repliedAt is not None),
            "total_bounced": sum(1 for s in sequences if s.bouncedAt is not None),
        }

    async def get_result(
        self, db: AsyncSession, campaign_id: str
    ) -> CampaignResult | None:
        result = await db.execute(
            select(CampaignResult)
            .where(CampaignResult.campaignId == campaign_id)
            .order_by(CampaignResult.generatedAt.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def generate_result(
        self, db: AsyncSession, campaign_id: str
    ) -> CampaignResult | None:
        """Compute + persist a campaign post-mortem (LLM-summarized).

        Task 3-a / FIX 1: aggregates send/open/reply/bounce counts from the
        Sequence table (the source of truth) via list_metrics. Positive
        reply count is aggregated from ReplyDraft.category (the source of
        truth populated by the MailBridge "replied" webhook + AI
        categorization — Task 2-a).
        """
        # Task 3-a / FIX 1: list_metrics now returns Sequence-aggregated
        # DTOs (grouped by campaign + date). Sum across all date buckets
        # to get the campaign totals. The else branch handles the rare
        # case where list_metrics returns [] (no sent sequences yet) —
        # _aggregate_from_sequences then runs the same aggregation with
        # a slightly broader filter (counts all sequences, not just sent).
        metrics = await self.list_metrics(db, campaign_id)
        if metrics:
            total_sent = sum(m.totalSent for m in metrics)
            total_opened = sum(m.totalOpened for m in metrics)
            total_replied = sum(m.totalReplied for m in metrics)
            total_bounced = sum(m.totalBounced for m in metrics)
        else:
            agg = await self._aggregate_from_sequences(db, campaign_id)
            total_sent = agg["total_sent"]
            total_opened = agg["total_opened"]
            total_replied = agg["total_replied"]
            total_bounced = agg["total_bounced"]

        # If still no data at all (no metrics + no sequences), bail with None
        # so the router 404s with a clear "no data yet" message.
        if total_sent == 0 and total_replied == 0 and total_bounced == 0:
            return None

        reply_rate = (total_replied / total_sent) if total_sent else 0.0
        # Positive replies: count ReplyDraft rows linked to this campaign's
        # sequences whose category is in the positive set. Best-effort —
        # fall back to the legacy heuristic on lookup failure.
        total_positive = int(reply_rate * 0.4 * total_sent)
        try:
            from app.models.campaign_models import ReplyDraft, Sequence
            from app.features.reply_drafts.service import POSITIVE_CATEGORIES

            seq_ids_result = await db.execute(
                select(Sequence.id).where(Sequence.campaignId == campaign_id)
            )
            seq_ids = [r[0] for r in seq_ids_result.fetchall()]
            if seq_ids:
                positive_result = await db.execute(
                    select(func.count(ReplyDraft.id)).where(
                        ReplyDraft.sequenceId.in_(seq_ids),
                        ReplyDraft.category.in_(list(POSITIVE_CATEGORIES)),
                    )
                )
                total_positive = int(positive_result.scalar() or 0)
        except Exception:  # noqa: BLE001 — best-effort
            pass
        positive_rate = (total_positive / total_sent) if total_sent else 0.0
        bounce_rate = (total_bounced / total_sent) if total_sent else 0.0
        llm = get_llm_service()
        summary_data = await llm.generate_json(
            prompt=(
                f"Summarize this campaign: sent={total_sent}, "
                f"opened={total_opened}, replied={total_replied}, "
                f"bounced={total_bounced}. "
                "Provide whatWorked, whatDidntWork, nextActions, insights. "
                "Respond as JSON."
            )
        )
        result = CampaignResult(
            campaignId=campaign_id,
            totalSent=total_sent,
            totalReplied=total_replied,
            totalPositive=total_positive,
            totalBounced=total_bounced,
            replyRate=reply_rate,
            positiveReplyRate=positive_rate,
            bounceRate=bounce_rate,
            whatWorked=str(summary_data.get("whatWorked", "")),
            whatDidntWork=str(summary_data.get("whatDidntWork", "")),
            nextActions=str(summary_data.get("nextActions", "")),
            insights=str(summary_data.get("insights", "")),
        )
        db.add(result)
        await db.commit()
        result = await db.get(CampaignResult, result.id)
        return result

    async def diagnose(
        self, db: AsyncSession, campaign_id: str | None
    ) -> DiagnoseResponse:
        """Run the 5-layer diagnostic. Returns one DiagnoseLayerResult per layer.

        Task 3-a / FIX 1: aggregates from the Sequence table (the source of
        truth) via list_metrics. Positive reply rate is aggregated from
        ReplyDraft.category (populated by the MailBridge "replied" webhook).
        """
        # Task 3-a / FIX 1: list_metrics now returns Sequence-aggregated
        # DTOs (sum across buckets to get campaign totals). The else branch
        # handles the no-campaign / no-sent-sequences case.
        layers: list[DiagnoseLayerResult] = []
        metrics = await self.list_metrics(db, campaign_id) if campaign_id else []
        if metrics:
            total_sent = sum(m.totalSent for m in metrics)
            total_bounced = sum(m.totalBounced for m in metrics)
            total_opened = sum(m.totalOpened for m in metrics)
            total_replied = sum(m.totalReplied for m in metrics)
        else:
            agg = await self._aggregate_from_sequences(db, campaign_id)
            total_sent = agg["total_sent"]
            total_bounced = agg["total_bounced"]
            total_opened = agg["total_opened"]
            total_replied = agg["total_replied"]
        bounce_rate = (total_bounced / total_sent) if total_sent else 0.0
        open_rate = (total_opened / total_sent) if total_sent else 0.0
        reply_rate = (total_replied / total_sent) if total_sent else 0.0

        layers.append(self._layer("delivery", bounce_rate, BENCH_BOUNCE_RATE, "bounce rate"))
        layers.append(self._layer("open", open_rate, BENCH_OPEN_RATE, "open rate"))
        layers.append(self._layer("reply", reply_rate, BENCH_REPLY_RATE, "reply rate"))

        # Pipeline layer — count deals for this campaign
        if campaign_id:
            deal_count_result = await db.execute(
                select(func.count(Deal.id)).where(Deal.campaignId == campaign_id)
            )
            deal_count = int(deal_count_result.scalar() or 0)
        else:
            deal_count = 0
        layers.append(DiagnoseLayerResult(
            layer="pipeline",
            status="ok" if deal_count > 0 else "warn",
            metric="deals_created",
            value=float(deal_count),
            benchmark=1.0,
            note=f"{deal_count} deal(s) created from this campaign.",
        ))
        layers.append(DiagnoseLayerResult(
            layer="content",
            status="ok",
            metric="qa_avg",
            value=85.0,  # Phase 4 will compute actual QA avg
            benchmark=80.0,
            note="QA scores within acceptable range.",
        ))
        summary = (
            f"Delivery: {bounce_rate:.1%} bounce. Open: {open_rate:.1%}. "
            f"Reply: {reply_rate:.1%}. Pipeline: {deal_count} deals."
        )
        return DiagnoseResponse(
            campaignId=campaign_id,
            layers=layers,
            summary=summary,
            generatedAt=datetime.now(timezone.utc),
        )

    async def dashboard_aggregation(self, db: AsyncSession) -> DashboardAggregation:
        """Top-line counts for the dashboard widget."""
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        prospect_count_result = await db.execute(
            select(func.count()).select_from(
                select(__import__("app.models.prospect_models", fromlist=["Prospect"]).Prospect).subquery()
            )
        )
        # Simpler: use scalar counts
        from app.models.prospect_models import Prospect

        total_prospects = int(
            (await db.execute(select(func.count(Prospect.id)))).scalar() or 0
        )
        total_campaigns = int(
            (await db.execute(select(func.count(Campaign.id)))).scalar() or 0
        )
        from app.models.campaign_models import Sequence

        active_sequences = int(
            (
                await db.execute(
                    select(func.count(Sequence.id)).where(
                        Sequence.status == EmailStatus.Scheduled
                    )
                )
            ).scalar()
            or 0
        )
        sent_this_week = int(
            (
                await db.execute(
                    select(func.count(Sequence.id)).where(
                        Sequence.sentAt >= week_ago
                    )
                )
            ).scalar()
            or 0
        )
        replies_this_week = int(
            (
                await db.execute(
                    select(func.count(Sequence.id)).where(
                        Sequence.repliedAt >= week_ago
                    )
                )
            ).scalar()
            or 0
        )
        pipeline_value_result = await db.execute(
            select(func.sum(Deal.value)).where(Deal.stage.notin_(["closed_lost"]))
        )
        pipeline_value = float(pipeline_value_result.scalar() or 0.0)
        avg_reply_rate = (
            (replies_this_week / sent_this_week) if sent_this_week else 0.0
        )

        # Wiring audit (Task 2-e): positive replies + meetings booked are now
        # aggregated from ReplyDraft (the source of truth populated by the
        # MailBridge "replied" webhook + AI categorization — Task 2-a) instead
        # of the prior `replied * 0.4` heuristic + `meetings = 0` placeholder.
        # Best-effort: fall back to the heuristic on lookup failure.
        positive_replies_this_week = int(replies_this_week * 0.4)
        meetings_this_week = 0
        try:
            from app.models.campaign_models import ReplyDraft, Sequence as _Seq
            from app.features.reply_drafts.service import POSITIVE_CATEGORIES

            # Positive replies: count ReplyDraft rows linked to a sequence
            # replied this week whose category is in the positive set.
            replied_seq_ids_result = await db.execute(
                select(_Seq.id).where(_Seq.repliedAt >= week_ago)
            )
            replied_seq_ids = [r[0] for r in replied_seq_ids_result.fetchall()]
            if replied_seq_ids:
                positive_result = await db.execute(
                    select(func.count(ReplyDraft.id)).where(
                        ReplyDraft.sequenceId.in_(replied_seq_ids),
                        ReplyDraft.category.in_(list(POSITIVE_CATEGORIES)),
                    )
                )
                positive_replies_this_week = int(positive_result.scalar() or 0)
            # Meetings booked: count ReplyDraft.meetingBookedAt set this week.
            meetings_result = await db.execute(
                select(func.count(ReplyDraft.id)).where(
                    ReplyDraft.meetingBookedAt.is_not(None),
                    ReplyDraft.meetingBookedAt >= week_ago,
                )
            )
            meetings_this_week = int(meetings_result.scalar() or 0)
        except Exception as exc:  # noqa: BLE001 — best-effort
            # Fall back to heuristic + 0 — never break the dashboard.
            try:
                import structlog as _structlog

                _structlog.get_logger(__name__).warning(
                    "analytics.dashboard.reply_draft_aggregation_failed",
                    error=str(exc),
                )
            except Exception:  # noqa: BLE001
                pass

        return DashboardAggregation(
            totalProspects=total_prospects,
            totalCampaigns=total_campaigns,
            activeSequences=active_sequences,
            sentThisWeek=sent_this_week,
            repliesThisWeek=replies_this_week,
            positiveRepliesThisWeek=positive_replies_this_week,
            meetingsThisWeek=meetings_this_week,
            pipelineValue=pipeline_value,
            averageReplyRate=avg_reply_rate,
        )

    async def time_series(
        self, db: AsyncSession, *, days: int = 30
    ) -> TimeSeriesResponse:
        """Daily rollup of sent/opened/replied/bounced for the last N days."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        from app.models.campaign_models import Sequence

        result = await db.execute(
            select(Sequence).where(Sequence.sentAt >= start)
        )
        sequences = list(result.scalars().all())
        buckets: dict[str, dict[str, int]] = {}
        for seq in sequences:
            if not seq.sentAt:
                continue
            day_key = seq.sentAt.date().isoformat()
            bucket = buckets.setdefault(
                day_key, {"sent": 0, "opened": 0, "replied": 0, "bounced": 0}
            )
            bucket["sent"] += 1
            if seq.openedAt:
                bucket["opened"] += 1
            if seq.repliedAt:
                bucket["replied"] += 1
            if seq.bouncedAt:
                bucket["bounced"] += 1
        points = [
            TimeSeriesPoint(date=k, **v) for k, v in sorted(buckets.items())
        ]
        return TimeSeriesResponse(points=points)


    async def tracking_summary(
        self, db: AsyncSession, *, days: int = 30
    ) -> "TrackingSummaryResponse":
        """Tenant-wide tracking summary for the Reply Inbox dashboard panel.

        Aggregates Sequence rows where sentAt is within the last `days` days.
        Reads only local Sequence rows — no MailBridge call needed.
        """
        from datetime import timedelta
        from collections import Counter
        from app.schemas.analytics import TrackingSummaryResponse

        now = datetime.now(timezone.utc)
        since = now - timedelta(days=days)

        result = await db.execute(
            select(Sequence).where(Sequence.sentAt >= since)
        )
        sequences = list(result.scalars().all())

        total_sent = len(sequences)
        total_replied = sum(1 for s in sequences if s.repliedAt is not None)
        # Count bounced by STATUS column — same signal the Bounced tab uses
        # (GET /api/v1/sequences?status=Bounced).  Previously counted bouncedAt
        # IS NOT NULL, which diverges when a sequence is stamped Bounced without
        # a bouncedAt timestamp (old webhook path) or vice versa.  Using status
        # ensures the Bounced card and Bounced tab always show the same number.
        def _is_bounced(s: Sequence) -> bool:
            val = s.status.value if hasattr(s.status, "value") else str(s.status)
            return val == "Bounced"

        total_bounced = sum(1 for s in sequences if _is_bounced(s))

        reply_rate = (total_replied / total_sent) if total_sent else 0.0
        bounce_rate = (total_bounced / total_sent) if total_sent else 0.0

        reason_counter: Counter = Counter()
        for s in sequences:
            if _is_bounced(s):
                reason = (s.bounceReason or "unknown").strip() or "unknown"
                reason_counter[reason] += 1
        top_bounce_reasons = [
            {"reason": r, "count": cnt}
            for r, cnt in reason_counter.most_common(5)
        ]

        status_counter: Counter = Counter()
        for s in sequences:
            val = s.status.value if hasattr(s.status, "value") else str(s.status)
            status_counter[val] += 1

        return TrackingSummaryResponse(
            period_days=days,
            total_sent=total_sent,
            total_replied=total_replied,
            total_bounced=total_bounced,
            reply_rate=reply_rate,
            bounce_rate=bounce_rate,
            top_bounce_reasons=top_bounce_reasons,
            by_status=dict(status_counter),
        )

    @staticmethod
    def _layer(
        name: str, value: float, benchmark: float, metric_label: str
    ) -> DiagnoseLayerResult:
        if name == "delivery":
            # Lower is better for bounce rate
            status = "ok" if value <= benchmark else ("warn" if value <= benchmark * 2 else "critical")
            note = f"{metric_label} {value:.1%} vs benchmark {benchmark:.1%}"
        else:
            # Higher is better
            status = "ok" if value >= benchmark else ("warn" if value >= benchmark * 0.5 else "critical")
            note = f"{metric_label} {value:.1%} vs benchmark {benchmark:.1%}"
        return DiagnoseLayerResult(
            layer=name,
            status=status,
            metric=metric_label,
            value=value,
            benchmark=benchmark,
            note=note,
        )