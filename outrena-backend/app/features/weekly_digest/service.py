"""weekly_digest_service.py — Auto-generated weekly performance summary."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import Sequence
from app.models.enums import EmailStatus
from app.models.phase3_models import WeeklyDigest
from app.services.llm_service import get_llm_service

logger = structlog.get_logger(__name__)


class WeeklyDigestService:
    async def list(
        self, db: AsyncSession, *, limit: int = 12, offset: int = 0
    ) -> list[WeeklyDigest]:
        result = await db.execute(
            select(WeeklyDigest)
            .order_by(WeeklyDigest.weekStart.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, digest_id: str) -> WeeklyDigest | None:
        result = await db.execute(
            select(WeeklyDigest).where(WeeklyDigest.id == digest_id)
        )
        return result.scalar_one_or_none()

    async def generate(
        self, db: AsyncSession, week_start: datetime | None = None
    ) -> WeeklyDigest:
        """Compute + persist the weekly digest for the given (or current) week."""
        if week_start is None:
            today = datetime.now(timezone.utc)
            week_start = today - timedelta(days=today.weekday())  # Monday
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        seqs_result = await db.execute(
            select(Sequence).where(Sequence.sentAt >= week_start, Sequence.sentAt < week_end)
        )
        sequences = list(seqs_result.scalars().all())
        sent = len(sequences)
        replied = sum(1 for s in sequences if s.repliedAt is not None)
        bounced = sum(1 for s in sequences if s.bouncedAt is not None)

        # Wiring audit (Task 2-e): positive replies + meetings booked are now
        # aggregated from the ReplyDraft table instead of the prior heuristic
        # (`replied * 0.4` + `meetings = 0`). The MailBridge "replied" webhook
        # auto-creates a ReplyDraft + runs AI categorization (Task 2-a), so
        # each reply now carries a category in {interested, meeting_request,
        # demo_request, positive_reply, negative_reply, not_interested, ooo,
        # unsubscribe, other} — we count the first 4 as positive. Meetings
        # booked = count of ReplyDraft.meetingBookedAt set within the window.
        # Best-effort: fall back to the legacy heuristic if ReplyDraft rows
        # can't be loaded (e.g. table not yet provisioned on a fresh tenant).
        positive = 0
        meetings = 0
        try:
            from app.models.campaign_models import ReplyDraft
            from app.features.reply_drafts.service import POSITIVE_CATEGORIES

            replied_seq_ids = [s.id for s in sequences if s.repliedAt is not None]
            if replied_seq_ids:
                rd_result = await db.execute(
                    select(ReplyDraft).where(
                        ReplyDraft.sequenceId.in_(replied_seq_ids)
                    )
                )
                reply_drafts = list(rd_result.scalars().all())
                positive = sum(
                    1
                    for rd in reply_drafts
                    if (rd.category or "") in POSITIVE_CATEGORIES
                )
                meetings = sum(
                    1
                    for rd in reply_drafts
                    if rd.meetingBookedAt is not None
                    and week_start <= rd.meetingBookedAt < week_end
                )
        except Exception as exc:  # noqa: BLE001 — best-effort, never block the digest
            logger.warning(
                "weekly_digest.reply_draft_aggregation_failed",
                error=str(exc),
            )
            positive = int(replied * 0.4)  # legacy heuristic fallback

        llm = get_llm_service()
        summary_text = await llm.generate(
            prompt=(
                f"Write a 3-sentence weekly summary for an outreach team. "
                f"This week: {sent} sent, {replied} replied, {positive} positive, "
                f"{bounced} bounced. Be encouraging and specific."
            )
        )
        highlights = [
            f"Sent {sent} emails",
            f"{replied} replies ({(replied/sent*100):.1f}% reply rate)" if sent else "No sends",
            f"{bounced} bounces",
        ]
        # Three spec-required JSON columns for metrics (audit-A1 M-35).
        # `highlights` (above) is the first; `topProspects` + `campaignPerformance`
        # round out the trio. Phase 3 stubs these with the data we already have
        # — Phase 4 will populate them with joined Campaign + Prospect rollups.
        # Top prospects: rank by recency of reply (repliedAt not null) then sent.
        replied_seqs = [s for s in sequences if s.repliedAt is not None]
        top_prospects = [
            {
                "prospectId": s.prospectId,
                "campaignId": s.campaignId,
                "repliedAt": s.repliedAt.isoformat() if s.repliedAt else None,
                "touchNumber": s.touchNumber,
            }
            for s in replied_seqs[:10]
        ]
        # Campaign performance: per-campaign sent/replied/bounced rollup.
        campaign_perf: dict[str, Any] = {}
        for s in sequences:
            cid = s.campaignId or "uncategorized"
            entry = campaign_perf.setdefault(
                cid, {"sent": 0, "replied": 0, "bounced": 0}
            )
            entry["sent"] += 1
            if s.repliedAt is not None:
                entry["replied"] += 1
            if s.bouncedAt is not None:
                entry["bounced"] += 1
        digest = WeeklyDigest(
            weekStart=week_start,
            weekEnd=week_end,
            sentCount=sent,
            replyCount=replied,
            positiveReplyCount=positive,
            meetingCount=meetings,
            bounceCount=bounced,
            summary=summary_text,
            highlights=json.dumps(highlights),
            topProspects=json.dumps(top_prospects),
            campaignPerformance=json.dumps(campaign_perf),
        )
        db.add(digest)
        await db.commit()
        digest = await db.get(WeeklyDigest, digest.id)
        return digest

    async def delete(self, db: AsyncSession, digest_id: str) -> bool:
        item = await self.get(db, digest_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def send_pending(self, *, local_hour_gate: int | None = None) -> dict[str, Any]:
        """Auto-generate the current week's digest for every active tenant.

        Wiring audit (Task 2-e): the Celery beat task ``weekly_digest.send_pending``
        (registered in ``app.worker.celery_app``) invoked this method, but it
        didn't exist — the beat task gracefully caught the AttributeError and
        logged a no-op message, so the Monday 08:00 UTC digest never landed
        automatically. Users had to call ``POST /api/v1/weekly-digest/generate``
        manually each week.

        This implementation iterates every ACTIVE tenant in ``public.tenants``,
        opens a session bound to that tenant's schema, and calls
        ``self.generate(db, week_start=None)`` — which is idempotent in the
        sense that it always inserts a fresh row (callers can de-dupe by
        ``weekStart`` if they want a single digest per week; the model has no
        UNIQUE constraint on weekStart, so successive runs produce successive
        rows, which is acceptable for an audit trail).

        Returns a dict ``{tenant_slug: {ok, digest_id|error}}`` for observability.
        Best-effort: per-tenant failures are logged + collected — they never
        abort the entire sweep.
        """
        from datetime import datetime, timezone
        from sqlalchemy import text

        from app.core.database import AsyncSessionLocal

        results: dict[str, Any] = {}
        async with AsyncSessionLocal() as session:
            await session.execute(text('SET search_path TO "public"'))
            rows = (
                await session.execute(
                    text(
                        "SELECT slug, schema_name FROM public.tenants "
                        "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
                    )
                )
            ).fetchall()

        # FR-059: recipient-local delivery. When local_hour_gate is set (the
        # hourly Monday beat passes 9), only tenants whose configured local
        # time is currently in that hour are processed this run; the others
        # are picked up by a later hourly run. Tenant timezone comes from
        # public.tenant_config.features JSONB ("timezone", IANA name);
        # missing/invalid → UTC.
        if local_hour_gate is not None:
            from zoneinfo import ZoneInfo

            gated: list[Any] = []
            async with AsyncSessionLocal() as session:
                for row in rows:
                    tz_name = "UTC"
                    try:
                        feat = (
                            await session.execute(
                                text(
                                    "SELECT tc.features FROM public.tenant_config tc "
                                    "JOIN public.tenants t ON t.tenant_id = tc.tenant_id "
                                    "WHERE t.slug = :slug"
                                ),
                                {"slug": row.slug},
                            )
                        ).scalar()
                        if isinstance(feat, str):
                            import json as _json

                            feat = _json.loads(feat or "{}")
                        tz_name = (feat or {}).get("timezone") or "UTC"
                    except Exception:  # noqa: BLE001
                        tz_name = "UTC"
                    try:
                        local_hour = datetime.now(ZoneInfo(tz_name)).hour
                    except Exception:  # noqa: BLE001
                        local_hour = datetime.now(timezone.utc).hour
                    if local_hour == local_hour_gate:
                        gated.append(row)
                    else:
                        results[row.slug] = {
                            "ok": True,
                            "skipped": f"local hour {local_hour} != gate {local_hour_gate} (tz {tz_name})",
                        }
            rows = gated

        for row in rows:
            slug = row.slug
            schema = row.schema_name
            try:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        text(f'SET search_path TO "{schema}", public')
                    )
                    digest = await self.generate(session, week_start=None)
                    results[slug] = {
                        "ok": True,
                        "digest_id": getattr(digest, "id", None),
                        "week_start": digest.weekStart.isoformat()
                        if digest.weekStart
                        else None,
                    }
            except Exception as exc:  # noqa: BLE001 — per-tenant isolation
                logger.error(
                    "weekly_digest.send_pending.tenant_failed",
                    tenant=slug,
                    error=str(exc),
                    exc_info=True,
                )
                results[slug] = {"ok": False, "error": str(exc)}
        return results
