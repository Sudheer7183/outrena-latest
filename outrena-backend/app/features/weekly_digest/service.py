"""weekly_digest_service.py — Auto-generated weekly performance summary.

FIX: summary generation now uses GlobalLlmConfig via a fresh public-schema
session (same pattern as pipeline, meeting prep, and job change fixes)
instead of get_llm_service().generate() which hits open.bigmodel.cn with
no API key → 401 → [LLM-STUB].
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import Sequence
from app.models.phase3_models import WeeklyDigest
from app.services.llm_service import call_llm, LlmGatewayError

logger = structlog.get_logger(__name__)


class WeeklyDigestService:

    # ── LLM config (same pattern as pipeline / meeting prep / job change) ──

    @staticmethod
    async def _get_llm_config():
        from app.core.database import AsyncSessionLocal
        from app.models.global_llm_config import GlobalLlmConfig
        from app.services.secret_service import decrypt_at_rest

        try:
            async with AsyncSessionLocal() as pub_db:
                await pub_db.execute(text('SET search_path TO "public"'))

                result = await pub_db.execute(
                    select(GlobalLlmConfig)
                    .where(GlobalLlmConfig.is_active.is_(True))
                    .where(GlobalLlmConfig.is_default.is_(True))
                    .limit(1)
                )
                config = result.scalar_one_or_none()

                if config is None:
                    result = await pub_db.execute(
                        select(GlobalLlmConfig)
                        .where(GlobalLlmConfig.is_active.is_(True))
                        .order_by(GlobalLlmConfig.id)
                        .limit(1)
                    )
                    config = result.scalar_one_or_none()

                if config is None:
                    return None

                api_key = decrypt_at_rest(config.api_key_encrypted)
                return SimpleNamespace(
                    provider=config.provider,
                    name=config.display_name,
                    modelId=config.model_name,
                    apiKey=api_key,
                    baseUrl=config.base_url,
                    isActive=config.is_active,
                    isDefault=config.is_default,
                    settings="{}",
                    global_llm_config_id=None,
                )
        except Exception as exc:
            logger.warning("weekly_digest.llm_config.fetch_failed", error=str(exc))
            return None

    @staticmethod
    async def _generate_summary(llm_config, sent: int, replied: int,
                                 positive: int, bounced: int) -> str:
        if llm_config is None:
            return (
                f"This week: {sent} emails sent, {replied} replies "
                f"({(replied/sent*100):.1f}% reply rate), "
                f"{positive} positive replies, {bounced} bounces."
                if sent else
                f"No emails sent this week. {bounced} bounces recorded."
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a concise outreach performance analyst. "
                    "Write exactly 3 sentences. Be encouraging and specific. "
                    "No markdown, no bullet points, plain prose only."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Write a 3-sentence weekly summary for an outreach team. "
                    f"Stats: {sent} sent, {replied} replied "
                    f"({(replied/sent*100):.1f}% reply rate), "
                    f"{positive} positive replies, {bounced} bounced."
                    if sent else
                    f"Write a 3-sentence weekly summary. No emails were sent this week. "
                    f"{bounced} bounces recorded."
                ),
            },
        ]
        try:
            resp = await call_llm(llm_config, messages)
            return resp.content.strip()
        except LlmGatewayError as exc:
            logger.warning("weekly_digest.llm_summary_failed", error=str(exc))
            return (
                f"This week: {sent} emails sent, {replied} replied, "
                f"{positive} positive, {bounced} bounced."
            )

    # ── CRUD ───────────────────────────────────────────────────────────────

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

    async def delete(self, db: AsyncSession, digest_id: str) -> bool:
        item = await self.get(db, digest_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def generate(
        self, db: AsyncSession, week_start: datetime | None = None
    ) -> WeeklyDigest:
        """Compute + persist the weekly digest for the given (or current) week."""
        if week_start is None:
            today = datetime.now(timezone.utc)
            week_start = today - timedelta(days=today.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        seqs_result = await db.execute(
            select(Sequence).where(
                Sequence.sentAt >= week_start, Sequence.sentAt < week_end
            )
        )
        sequences = list(seqs_result.scalars().all())
        sent = len(sequences)
        replied = sum(1 for s in sequences if s.repliedAt is not None)
        bounced = sum(1 for s in sequences if s.bouncedAt is not None)

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
                    1 for rd in reply_drafts
                    if (rd.category or "") in POSITIVE_CATEGORIES
                )
                meetings = sum(
                    1 for rd in reply_drafts
                    if rd.meetingBookedAt is not None
                    and week_start <= rd.meetingBookedAt < week_end
                )
        except Exception as exc:
            logger.warning(
                "weekly_digest.reply_draft_aggregation_failed", error=str(exc)
            )
            positive = int(replied * 0.4)

        # Generate summary using GlobalLlmConfig (not legacy LlmService)
        llm_config = await self._get_llm_config()
        summary_text = await self._generate_summary(
            llm_config, sent, replied, positive, bounced
        )

        highlights = [
            f"Sent {sent} emails",
            f"{replied} replies ({(replied/sent*100):.1f}% reply rate)" if sent else "No sends this week",
            f"{positive} positive replies",
            f"{bounced} bounces",
        ]

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

        campaign_perf: dict[str, Any] = {}
        for s in sequences:
            cid = s.campaignId or "uncategorized"
            entry = campaign_perf.setdefault(cid, {"sent": 0, "replied": 0, "bounced": 0})
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

    async def send_pending(self, *, local_hour_gate: int | None = None) -> dict[str, Any]:
        """Auto-generate the current week's digest for every active tenant."""
        from sqlalchemy import text as _text
        from app.core.database import AsyncSessionLocal

        results: dict[str, Any] = {}
        async with AsyncSessionLocal() as session:
            await session.execute(_text('SET search_path TO "public"'))
            rows = (
                await session.execute(
                    _text(
                        "SELECT slug, schema_name FROM public.tenants "
                        "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
                    )
                )
            ).fetchall()

        if local_hour_gate is not None:
            from zoneinfo import ZoneInfo
            import json as _json

            gated: list[Any] = []
            async with AsyncSessionLocal() as session:
                for row in rows:
                    tz_name = "UTC"
                    try:
                        feat = (
                            await session.execute(
                                _text(
                                    "SELECT tc.features FROM public.tenant_config tc "
                                    "JOIN public.tenants t ON t.tenant_id = tc.tenant_id "
                                    "WHERE t.slug = :slug"
                                ),
                                {"slug": row.slug},
                            )
                        ).scalar()
                        if isinstance(feat, str):
                            feat = _json.loads(feat or "{}")
                        tz_name = (feat or {}).get("timezone") or "UTC"
                    except Exception:
                        tz_name = "UTC"
                    try:
                        local_hour = datetime.now(ZoneInfo(tz_name)).hour
                    except Exception:
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
                        _text(f'SET search_path TO "{schema}", public')
                    )
                    digest = await self.generate(session, week_start=None)
                    results[slug] = {
                        "ok": True,
                        "digest_id": getattr(digest, "id", None),
                        "week_start": digest.weekStart.isoformat()
                        if digest.weekStart else None,
                    }
            except Exception as exc:
                logger.error(
                    "weekly_digest.send_pending.tenant_failed",
                    tenant=slug,
                    error=str(exc),
                    exc_info=True,
                )
                results[slug] = {"ok": False, "error": str(exc)}
        return results