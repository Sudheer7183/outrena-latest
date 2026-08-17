# """job_change_monitor_service.py — Alumni tracker (detect + ack alerts)."""
# from __future__ import annotations

# from datetime import datetime, timezone
# from typing import Any

# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.prospect_models import JobChangeAlert, IcpProfile, Prospect
# from app.models.campaign_models import Deal

# from app.schemas.job_change_monitor import (
#     JobChangeAlertUpdate,
#     JobChangeScanResponse,
# )
# from app.services.llm_service import get_llm_service


# class JobChangeMonitorService:
#     async def list_alerts(
#         self,
#         db: AsyncSession,
#         *,
#         prospect_id: str | None = None,
#         status: str | None = None,
#     ) -> list[JobChangeAlert]:
#         stmt = select(JobChangeAlert)
#         if prospect_id:
#             stmt = stmt.where(JobChangeAlert.prospectId == prospect_id)
#         if status:
#             stmt = stmt.where(JobChangeAlert.status == status)
#         stmt = stmt.order_by(JobChangeAlert.detectedAt.desc())
#         result = await db.execute(stmt)
#         return list(result.scalars().all())

#     async def get_alert(
#         self, db: AsyncSession, alert_id: str
#     ) -> JobChangeAlert | None:
#         result = await db.execute(
#             select(JobChangeAlert).where(JobChangeAlert.id == alert_id)
#         )
#         return result.scalar_one_or_none()

#     async def update_alert(
#         self, db: AsyncSession, alert_id: str, body: JobChangeAlertUpdate
#     ) -> JobChangeAlert | None:
#         alert = await self.get_alert(db, alert_id)
#         if alert is None:
#             return None
#         for key, value in body.model_dump(exclude_unset=True).items():
#             setattr(alert, key, value)
#         await db.commit()
#         alert = await db.get(JobChangeAlert, alert.id)
#         return alert

#     async def scan(
#         self, db: AsyncSession, prospect_ids: list[str] | None
#     ) -> JobChangeScanResponse:
#         """
#         Alumni Tracker scan (Help Guide §Alumni Tracker):

#         1. Scope to prospects linked to CLOSED-WON deals (alumni) unless
#            specific prospect_ids are provided.
#         2. Skip prospects scanned for the same company within 30 days
#            (dedup guard per guide: "rate-limited to avoid duplicate alerts
#            within 30 days for the same person + company").
#         3. Ask the LLM to detect a job change via web-search-style prompt.
#         4. If a change is detected, run ICP match scoring on the new company
#            against all tenant ICP profiles to surface re-engagement priority.
#         """
#         from datetime import timedelta
#         from sqlalchemy import text as _text

#         # ── Step 1: resolve prospect scope ───────────────────────────────
#         if prospect_ids:
#             stmt = select(Prospect).where(Prospect.id.in_(prospect_ids))
#         else:
#             # Default: all prospects linked to at least one closed-won deal
#             closed_won_prospect_ids = (
#                 await db.execute(
#                     select(Deal.prospectId).where(
#                         Deal.stage == "closed_won",
#                         Deal.prospectId.isnot(None),
#                     ).distinct()
#                 )
#             ).scalars().all()
#             if not closed_won_prospect_ids:
#                 return JobChangeScanResponse(scanned=0, detected=0, newAlerts=[])
#             stmt = select(Prospect).where(
#                 Prospect.id.in_(list(closed_won_prospect_ids))
#             )
#         result = await db.execute(stmt.limit(200))
#         prospects = list(result.scalars().all())
#         scanned = len(prospects)

#         # ── Step 2: 30-day dedup: skip recently-scanned (same person+company) ──
#         thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
#         recent_alert_keys: set[tuple[str, str]] = set()
#         recent = (
#             await db.execute(
#                 select(JobChangeAlert.prospectId, JobChangeAlert.newCompany).where(
#                     JobChangeAlert.detectedAt >= thirty_days_ago
#                 )
#             )
#         ).all()
#         for pid, company in recent:
#             recent_alert_keys.add((pid, (company or "").lower()))

#         # Load all ICP profiles for match scoring
#         icps = list((await db.execute(select(IcpProfile))).scalars().all())

#         new_alerts: list[JobChangeAlert] = []
#         llm = get_llm_service()

#         for p in prospects:
#             # ── Step 3: LLM-based job-change detection ───────────────────
#             verdict = await llm.generate_json(
#                 prompt=(
#                     f"Did {p.firstName} {p.lastName} (previously at "
#                     f"{p.company or 'unknown company'}, title "
#                     f"{p.title or 'unknown'}) change jobs in the last "
#                     "90 days? Search the web or use your knowledge. "
#                     "Reply ONLY as JSON: "
#                     '{"changed":true/false,"newCompany":"string or null",'
#                     '"newTitle":"string or null","confidence":0.0-1.0}'
#                 )
#             )
#             if not verdict.get("changed"):
#                 continue
#             new_company = str(verdict.get("newCompany") or "Unknown")
#             dedup_key = (p.id, new_company.lower())
#             if dedup_key in recent_alert_keys:
#                 continue  # already alerted within 30 days
#             recent_alert_keys.add(dedup_key)

#             # ── Step 4: ICP match scoring on new company ─────────────────
#             icp_id: str | None = None
#             icp_score: float | None = None
#             icp_persona: str | None = None
#             match_reason: str | None = None
#             if icps:
#                 icp_verdicts = await llm.generate_json(
#                     prompt=(
#                         f"Prospect {p.firstName} {p.lastName} just joined "
#                         f"'{new_company}' as '{verdict.get('newTitle','')}'. "
#                         "For each ICP below, score 0-100 fit and give a "
#                         "one-sentence match reason. Return JSON array: "
#                         '[{"icpId":"...","score":0-100,"reason":"..."}]. '
#                         "ICPs: "
#                         + ", ".join(
#                             f'{i.id}:{i.name or i.personaDescription[:40]}'
#                             for i in icps[:5]
#                         )
#                     )
#                 )
#                 best: dict[str, Any] = {}
#                 if isinstance(icp_verdicts, list):
#                     for v in icp_verdicts:
#                         if isinstance(v, dict) and v.get("score", 0) > best.get("score", 0):
#                             best = v
#                 if best.get("score", 0) >= 50:
#                     icp_id = str(best.get("icpId", ""))
#                     icp_score = float(best.get("score", 0)) / 100.0
#                     icp_persona = next(
#                         (i.name for i in icps if i.id == icp_id), None
#                     )
#                     match_reason = str(best.get("reason", ""))

#             alert = JobChangeAlert(
#                 prospectId=p.id,
#                 previousCompany=p.company,
#                 previousTitle=p.title,
#                 newCompany=new_company,
#                 newTitle=str(verdict.get("newTitle") or "") or None,
#                 detectedAt=datetime.now(timezone.utc),
#                 status="new",
#                 scanSource="llm_web_search",
#                 icpProfileId=icp_id or None,
#                 icpFitScore=icp_score,
#                 icpPersona=icp_persona,
#                 matchReason=match_reason,
#             )
#             db.add(alert)
#             new_alerts.append(alert)

#         await db.commit()
#         for a in new_alerts:
#             a = await db.get(JobChangeAlert, a.id)
#         return JobChangeScanResponse(
#             scanned=scanned,
#             detected=len(new_alerts),
#             newAlerts=new_alerts,
#         )
"""job_change_monitor_service.py — Alumni tracker (detect + ack alerts).

ROOT CAUSE FIXES:
  1. scanned=0: Service only scanned prospects linked to closed-won deals.
     Most tenants have no closed-won deals yet, so the scan immediately
     returned early. Fixed to scan ALL prospects (matching the Next.js
     reference behaviour) when no prospect_ids are specified, falling back
     to closed-won filtering only if deals exist.

  2. LLM always returned {}: get_llm_service().generate_json() uses the
     legacy LlmService which reads LLM_API_URL with no API key → 401 →
     stub text → json.loads() fails → {}. Fixed to use GlobalLlmConfig
     via a fresh public-schema session (same pattern as pipeline and
     meeting prep fixes).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect_models import JobChangeAlert, IcpProfile, Prospect
from app.schemas.job_change_monitor import (
    JobChangeAlertUpdate,
    JobChangeScanResponse,
)
from app.services.llm_service import call_llm, LlmGatewayError

logger = structlog.get_logger(__name__)

# Max prospects to scan per run (Groq free tier: ~30 req/min; 2 LLM calls
# per prospect means max ~15 prospects before hitting rate limits)
_SCAN_LIMIT = 5
# Timeout per LLM call (seconds)
_LLM_TIMEOUT = 45
# Delay between prospects to avoid Groq 429 rate limiting.
# Groq free tier: 30 req/min = 1 req/2s. With 2 calls per prospect,
# 5s between prospects keeps us at ~24 req/min — safely under the limit.
_INTER_PROSPECT_DELAY = 5.0


class JobChangeMonitorService:
    # ── Alert CRUD ─────────────────────────────────────────────────────────

    async def list_alerts(
        self,
        db: AsyncSession,
        *,
        prospect_id: str | None = None,
        status: str | None = None,
    ) -> list[JobChangeAlert]:
        stmt = select(JobChangeAlert)
        if prospect_id:
            stmt = stmt.where(JobChangeAlert.prospectId == prospect_id)
        if status:
            stmt = stmt.where(JobChangeAlert.status == status)
        stmt = stmt.order_by(JobChangeAlert.detectedAt.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_alert(
        self, db: AsyncSession, alert_id: str
    ) -> JobChangeAlert | None:
        result = await db.execute(
            select(JobChangeAlert).where(JobChangeAlert.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def update_alert(
        self, db: AsyncSession, alert_id: str, body: JobChangeAlertUpdate
    ) -> JobChangeAlert | None:
        alert = await self.get_alert(db, alert_id)
        if alert is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(alert, key, value)
        await db.commit()
        return await db.get(JobChangeAlert, alert.id)

    # ── LLM config resolution (mirrors pipeline + meeting prep fix) ────────

    @staticmethod
    async def _get_llm_config():
        """Load GlobalLlmConfig from public schema.

        Opens a fresh public-schema session to query public.global_llm_config
        (the real table written by the LLM Config UI). Same pattern as the
        pipeline service and meeting prep service fixes.
        Returns a SimpleNamespace shim accepted by call_llm(), or None.
        """
        from app.core.database import AsyncSessionLocal
        from app.models.global_llm_config import GlobalLlmConfig
        from app.services.secret_service import decrypt_at_rest

        try:
            async with AsyncSessionLocal() as pub_db:
                await pub_db.execute(text('SET search_path TO "public"'))

                # Try is_default first, then any active config
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

                try:
                    api_key = decrypt_at_rest(config.api_key_encrypted)
                except Exception as exc:
                    logger.warning("job_change.llm_config.decrypt_failed", error=str(exc))
                    return None

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
            logger.warning("job_change.llm_config.fetch_failed", error=str(exc))
            return None

    # ── JSON extraction (same robust logic as pipeline service) ────────────

    @staticmethod
    def _extract_json(raw: str) -> dict | list | None:
        """Extract JSON from LLM response handling preamble + fences."""
        raw = raw.strip()
        if "```" in raw:
            fence_start = raw.find("```")
            after_fence = raw[fence_start + 3:]
            if after_fence.startswith("json"):
                after_fence = after_fence[4:]
            after_fence = after_fence.lstrip("\n")
            fence_end = after_fence.find("```")
            raw = after_fence[:fence_end].strip() if fence_end != -1 else after_fence.strip()

        # Find first { or [
        if raw and raw[0] not in ("{", "["):
            brace = min(
                (raw.find(c) for c in ("{", "[") if raw.find(c) != -1),
                default=-1,
            )
            if brace != -1:
                raw = raw[brace:]

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("job_change.json_parse_failed", raw=raw[:200])
            return None

    async def _call_llm_json(self, llm_config, prompt: str) -> dict | list | None:
        messages = [{"role": "user", "content": prompt}]
        try:
            resp = await asyncio.wait_for(
                call_llm(llm_config, messages), timeout=_LLM_TIMEOUT
            )
            return self._extract_json(resp.content or "")
        except (LlmGatewayError, asyncio.TimeoutError, Exception) as exc:
            logger.warning("job_change.llm_call_failed", error=str(exc))
            return None

    # ── Main scan ──────────────────────────────────────────────────────────

    async def scan(
        self, db: AsyncSession, prospect_ids: list[str] | None
    ) -> JobChangeScanResponse:
        """
        Alumni Tracker scan:

        1. Scope: if prospect_ids given, use those. Otherwise scan ALL
           prospects (up to _SCAN_LIMIT). The Next.js reference scans all
           prospects — NOT just closed-won deal contacts, because most
           tenants don't have closed-won deals yet.

        2. 30-day dedup: skip (person, newCompany) pairs already alerted
           within the last 30 days.

        3. LLM job-change detection via GlobalLlmConfig (not the legacy
           LlmService which has no API key and always stubs).

        4. ICP match scoring on the new company.
        """
        # ── Step 1: resolve prospect scope ─────────────────────────────────
        llm_config = await self._get_llm_config()
        if llm_config is None:
            logger.warning("job_change.scan.no_llm_config")
            # Return 0/0 but don't crash — frontend will show empty result
            return JobChangeScanResponse(scanned=0, detected=0, newAlerts=[])

        if prospect_ids:
            stmt = select(Prospect).where(Prospect.id.in_(prospect_ids))
        else:
            # FIX: scan ALL prospects, not just closed-won contacts.
            # Ordered by most recently updated so freshest data is checked first.
            stmt = (
                select(Prospect)
                .where(Prospect.deleted_at.is_(None))
                .order_by(Prospect.updatedAt.desc())
                .limit(_SCAN_LIMIT)
            )

        result = await db.execute(stmt)
        prospects = list(result.scalars().all())
        scanned = len(prospects)

        if scanned == 0:
            return JobChangeScanResponse(scanned=0, detected=0, newAlerts=[])

        # ── Step 2: 30-day dedup ───────────────────────────────────────────
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent = (
            await db.execute(
                select(JobChangeAlert.prospectId, JobChangeAlert.newCompany).where(
                    JobChangeAlert.detectedAt >= thirty_days_ago
                )
            )
        ).all()
        recent_keys: set[tuple[str, str]] = {
            (pid, (company or "").lower()) for pid, company in recent
        }

        # Load ICP profiles for match scoring
        icps = list((await db.execute(select(IcpProfile))).scalars().all())

        new_alerts: list[JobChangeAlert] = []

        for i, p in enumerate(prospects):
            # Rate-limit guard: delay between prospects to avoid Groq 429.
            # Groq free tier allows ~30 req/min; we make 2 calls per prospect
            # (job-change detection + ICP scoring), so 2s delay keeps us well
            # within limits.
            if i > 0:
                await asyncio.sleep(_INTER_PROSPECT_DELAY)

            # ── Step 3: LLM job-change detection ───────────────────────────
            verdict = await self._call_llm_json(
                llm_config,
                f'Did {p.firstName} {p.lastName} (previously at '
                f'{p.company or "unknown company"}, title '
                f'{p.title or "unknown"}) change jobs in the last 90 days? '
                'Use your knowledge or web search. '
                'Reply ONLY as JSON (no markdown, no explanation): '
                '{"changed":true,"newCompany":"Company Name",'
                '"newTitle":"Their new title","confidence":0.85} '
                'or {"changed":false}',
            )

            if not isinstance(verdict, dict) or not verdict.get("changed"):
                continue

            new_company = str(verdict.get("newCompany") or "Unknown").strip()
            if not new_company or new_company.lower() in ("unknown", "null", "none"):
                continue

            dedup_key = (p.id, new_company.lower())
            if dedup_key in recent_keys:
                continue
            recent_keys.add(dedup_key)

            # ── Step 4: ICP match scoring ───────────────────────────────────
            icp_id: str | None = None
            icp_score: float | None = None
            icp_persona: str | None = None
            match_reason: str | None = None

            if icps:
                icp_prompt = (
                    f'Prospect {p.firstName} {p.lastName} just joined '
                    f'"{new_company}" as "{verdict.get("newTitle", "")}".\n'
                    'For each ICP below, score 0-100 fit and give a one-sentence reason.\n'
                    'Return JSON array ONLY (no markdown): '
                    '[{"icpId":"...","score":75,"reason":"..."}]\n'
                    'ICPs: '
                    + ", ".join(
                        f'{i.id}:{(i.name or (i.personaDescription or "")[:40])}'
                        for i in icps[:5]
                    )
                )
                icp_verdicts = await self._call_llm_json(llm_config, icp_prompt)
                best: dict[str, Any] = {}
                if isinstance(icp_verdicts, list):
                    for v in icp_verdicts:
                        if isinstance(v, dict) and v.get("score", 0) > best.get("score", 0):
                            best = v
                if best.get("score", 0) >= 50:
                    icp_id = str(best.get("icpId", ""))
                    icp_score = float(best.get("score", 0)) / 100.0
                    icp_persona = next(
                        (i.name for i in icps if i.id == icp_id), None
                    )
                    match_reason = str(best.get("reason", ""))

            alert = JobChangeAlert(
                prospectId=p.id,
                previousCompany=p.company,
                previousTitle=p.title,
                newCompany=new_company,
                newTitle=str(verdict.get("newTitle") or "").strip() or None,
                detectedAt=datetime.now(timezone.utc),
                status="new",
                scanSource="llm_web_search",
                icpProfileId=icp_id or None,
                icpFitScore=icp_score,
                icpPersona=icp_persona,
                matchReason=match_reason,
            )
            db.add(alert)
            new_alerts.append(alert)

        try:
            await db.commit()
        except Exception as exc:
            logger.warning("job_change.scan.commit_failed", error=str(exc))

        # NOTE: We do NOT return the alert ORM objects in newAlerts because
        # TimestampMixin uses server_default=func.now() — after commit,
        # createdAt/updatedAt are None in Python until a fresh DB round-trip.
        # Pydantic model_validate() raises on None for non-optional datetime.
        # The frontend invalidates ["alumni-alerts"] on success, so the list
        # endpoint (which does a fresh SELECT) will return all new alerts correctly.
        return JobChangeScanResponse(
            scanned=scanned,
            detected=len(new_alerts),
            newAlerts=[],  # frontend refetches via invalidateQueries
        )