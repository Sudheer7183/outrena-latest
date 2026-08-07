"""job_change_monitor_service.py — Alumni tracker (detect + ack alerts)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect_models import JobChangeAlert, IcpProfile, Prospect
from app.models.campaign_models import Deal

from app.schemas.job_change_monitor import (
    JobChangeAlertUpdate,
    JobChangeScanResponse,
)
from app.services.llm_service import get_llm_service


class JobChangeMonitorService:
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
        alert = await db.get(JobChangeAlert, alert.id)
        return alert

    async def scan(
        self, db: AsyncSession, prospect_ids: list[str] | None
    ) -> JobChangeScanResponse:
        """
        Alumni Tracker scan (Help Guide §Alumni Tracker):

        1. Scope to prospects linked to CLOSED-WON deals (alumni) unless
           specific prospect_ids are provided.
        2. Skip prospects scanned for the same company within 30 days
           (dedup guard per guide: "rate-limited to avoid duplicate alerts
           within 30 days for the same person + company").
        3. Ask the LLM to detect a job change via web-search-style prompt.
        4. If a change is detected, run ICP match scoring on the new company
           against all tenant ICP profiles to surface re-engagement priority.
        """
        from datetime import timedelta
        from sqlalchemy import text as _text

        # ── Step 1: resolve prospect scope ───────────────────────────────
        if prospect_ids:
            stmt = select(Prospect).where(Prospect.id.in_(prospect_ids))
        else:
            # Default: all prospects linked to at least one closed-won deal
            closed_won_prospect_ids = (
                await db.execute(
                    select(Deal.prospectId).where(
                        Deal.stage == "closed_won",
                        Deal.prospectId.isnot(None),
                    ).distinct()
                )
            ).scalars().all()
            if not closed_won_prospect_ids:
                return JobChangeScanResponse(scanned=0, detected=0, newAlerts=[])
            stmt = select(Prospect).where(
                Prospect.id.in_(list(closed_won_prospect_ids))
            )
        result = await db.execute(stmt.limit(200))
        prospects = list(result.scalars().all())
        scanned = len(prospects)

        # ── Step 2: 30-day dedup: skip recently-scanned (same person+company) ──
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_alert_keys: set[tuple[str, str]] = set()
        recent = (
            await db.execute(
                select(JobChangeAlert.prospectId, JobChangeAlert.newCompany).where(
                    JobChangeAlert.detectedAt >= thirty_days_ago
                )
            )
        ).all()
        for pid, company in recent:
            recent_alert_keys.add((pid, (company or "").lower()))

        # Load all ICP profiles for match scoring
        icps = list((await db.execute(select(IcpProfile))).scalars().all())

        new_alerts: list[JobChangeAlert] = []
        llm = get_llm_service()

        for p in prospects:
            # ── Step 3: LLM-based job-change detection ───────────────────
            verdict = await llm.generate_json(
                prompt=(
                    f"Did {p.firstName} {p.lastName} (previously at "
                    f"{p.company or 'unknown company'}, title "
                    f"{p.title or 'unknown'}) change jobs in the last "
                    "90 days? Search the web or use your knowledge. "
                    "Reply ONLY as JSON: "
                    '{"changed":true/false,"newCompany":"string or null",'
                    '"newTitle":"string or null","confidence":0.0-1.0}'
                )
            )
            if not verdict.get("changed"):
                continue
            new_company = str(verdict.get("newCompany") or "Unknown")
            dedup_key = (p.id, new_company.lower())
            if dedup_key in recent_alert_keys:
                continue  # already alerted within 30 days
            recent_alert_keys.add(dedup_key)

            # ── Step 4: ICP match scoring on new company ─────────────────
            icp_id: str | None = None
            icp_score: float | None = None
            icp_persona: str | None = None
            match_reason: str | None = None
            if icps:
                icp_verdicts = await llm.generate_json(
                    prompt=(
                        f"Prospect {p.firstName} {p.lastName} just joined "
                        f"'{new_company}' as '{verdict.get('newTitle','')}'. "
                        "For each ICP below, score 0-100 fit and give a "
                        "one-sentence match reason. Return JSON array: "
                        '[{"icpId":"...","score":0-100,"reason":"..."}]. '
                        "ICPs: "
                        + ", ".join(
                            f'{i.id}:{i.name or i.personaDescription[:40]}'
                            for i in icps[:5]
                        )
                    )
                )
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
                newTitle=str(verdict.get("newTitle") or "") or None,
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

        await db.commit()
        for a in new_alerts:
            a = await db.get(JobChangeAlert, a.id)
        return JobChangeScanResponse(
            scanned=scanned,
            detected=len(new_alerts),
            newAlerts=new_alerts,
        )
