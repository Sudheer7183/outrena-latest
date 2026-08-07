"""
signals_service.py — Signal + monitor + lead-score (60s timeout) + lead-score-batch.

Lead-score: 100-pt ICP-fit + P0/P1/P2 urgency. Uses an asyncio timeout
(default 60s per Phase 3 deliverable) to bound the LLM call.
scan: LLM-based signal detection (replaces Phase 5 stub).
lead-score-batch: batch LLM scoring for multiple prospects.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase3_models import Signal, SignalMonitor
from app.models.prospect_models import Prospect
from app.schemas.signals import (
    LeadScoreBatchRequest,
    LeadScoreBatchResponse,
    LeadScoreBatchResult,
    LeadScoreResponse,
    LeadScoreStatsResponse,
    SignalMonitorCreate,
    SignalMonitorUpdate,
    SignalsScanResponse,
)
from app.services.llm_service import get_llm_service

logger = structlog.get_logger(__name__)

# 60-second hard timeout per Phase 3 deliverable.
_LEAD_SCORE_TIMEOUT_SECONDS = 60


class SignalsService:
    # ── Signals ────────────────────────────────────────────────────────────
    async def list_signals(
        self,
        db: AsyncSession,
        *,
        prospect_id: str | None = None,
        signal_type: str | None = None,
        limit: int = 100,
    ) -> list[Signal]:
        stmt = select(Signal).limit(limit)
        if prospect_id:
            stmt = stmt.where(Signal.prospectId == prospect_id)
        if signal_type:
            stmt = stmt.where(Signal.type == signal_type)
        stmt = stmt.order_by(Signal.detectedAt.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_signal(
        self, db: AsyncSession, prospect_id: str | None, signal_type: str,
        summary: str, confidence: float = 0.8, detail: str | None = None,
    ) -> Signal:
        item = Signal(
            prospectId=prospect_id,
            type=signal_type,
            summary=summary,
            detail=detail,
            confidence=confidence,
            detectedAt=datetime.now(timezone.utc),
        )
        db.add(item)
        await db.commit()
        item = await db.get(Signal, item.id)
        return item

    # ── Monitors ───────────────────────────────────────────────────────────
    async def list_monitors(
        self, db: AsyncSession, *, active_only: bool = False
    ) -> list[SignalMonitor]:
        stmt = select(SignalMonitor)
        if active_only:
            stmt = stmt.where(SignalMonitor.isActive.is_(True))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_monitor(
        self, db: AsyncSession, monitor_id: str
    ) -> SignalMonitor | None:
        result = await db.execute(
            select(SignalMonitor).where(SignalMonitor.id == monitor_id)
        )
        return result.scalar_one_or_none()

    async def create_monitor(
        self, db: AsyncSession, body: SignalMonitorCreate
    ) -> SignalMonitor:
        data = body.model_dump()
        data["conditions"] = json.dumps(data.get("conditions", {}))
        item = SignalMonitor(**data)
        db.add(item)
        await db.commit()
        item = await db.get(SignalMonitor, item.id)
        return item

    async def update_monitor(
        self, db: AsyncSession, monitor_id: str, body: SignalMonitorUpdate
    ) -> SignalMonitor | None:
        item = await self.get_monitor(db, monitor_id)
        if item is None:
            return None
        data = body.model_dump(exclude_unset=True)
        if "conditions" in data and data["conditions"] is not None:
            data["conditions"] = json.dumps(data["conditions"])
        for key, value in data.items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(SignalMonitor, item.id)
        return item

    async def delete_monitor(self, db: AsyncSession, monitor_id: str) -> bool:
        item = await self.get_monitor(db, monitor_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    # ── Scan (LLM-based signal detection) ────────────────────────────────────
    async def scan(
        self,
        db: AsyncSession,
        prospect_ids: list[str] | None,
        signal_types: list[str] | None,
    ) -> SignalsScanResponse:
        """LLM-based signal scan — analyzes prospect data for buying signals."""
        stmt = select(Prospect).limit(100)
        if prospect_ids:
            stmt = stmt.where(Prospect.id.in_(prospect_ids))
        result = await db.execute(stmt)
        prospects = list(result.scalars().all())
        scanned = len(prospects)

        if not prospects:
            return SignalsScanResponse(scanned=0, detected=0, signals=[])

        # Build prospect summary for LLM
        prospect_info = []
        for p in prospects:
            prospect_info.append({
                "id": str(p.id),
                "name": f"{p.firstName} {p.lastName}",
                "title": p.title or "",
                "company": p.company or "",
                "domain": p.domain or "",
            })

        allowed_types = signal_types or ["funding", "hiring", "news", "product_launch", "leadership_change"]
        llm = get_llm_service()
        prompt = f"""You are a B2B buying signal analyst. Analyze these prospects for buying signals.

Prospects: {json.dumps(prospect_info)}

Look for these signal types: {json.dumps(allowed_types)}

For each prospect that shows a signal, provide:
- signal type (one of: {', '.join(allowed_types)})
- summary (concise description of the signal)
- confidence (0.0-1.0)

Return JSON:
{{
  "results": [
    {{"prospect_id": "...", "signal_type": "funding", "summary": "...", "confidence": 0.8}},
    ...
  ]
}}"""
        try:
            raw = await asyncio.wait_for(llm.generate_json(prompt=prompt), timeout=60)
            if isinstance(raw, str):
                raw = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())

            detected = 0
            signals: list[Signal] = []
            for r in raw.get("results", []):
                pid = r.get("prospect_id")
                stype = r.get("signal_type", "news")
                summary = r.get("summary", "")
                confidence = float(r.get("confidence", 0.7))
                sig = await self.create_signal(
                    db, pid, stype,
                    summary=summary,
                    confidence=min(max(confidence, 0.0), 1.0),
                )
                signals.append(sig)
                detected += 1

            return SignalsScanResponse(
                scanned=scanned, detected=detected, signals=signals
            )
        except Exception as e:
            logger.error("Signal scan failed: %s", e)
            # Fallback: return empty result rather than crashing
            return SignalsScanResponse(scanned=scanned, detected=0, signals=[])

    # ── Lead score (60s timeout) ───────────────────────────────────────────
    async def lead_score(
        self,
        db: AsyncSession,
        prospect_id: str,
        timeout_seconds: int = _LEAD_SCORE_TIMEOUT_SECONDS,
    ) -> LeadScoreResponse:
        """Compute 100-pt ICP-fit + P0/P1/P2 urgency with a hard 60s timeout."""
        prospect_result = await db.execute(
            select(Prospect).where(Prospect.id == prospect_id)
        )
        prospect = prospect_result.scalar_one_or_none()
        if prospect is None:
            return LeadScoreResponse(
                prospectId=prospect_id,
                icpFitScore=0,
                urgencyTier="P2",
                urgencyDeadline=None,
                scoreBreakdown={"error": "Prospect not found"},
                computedAt=datetime.now(timezone.utc),
            )
        llm = get_llm_service()
        try:
            data = await asyncio.wait_for(
                llm.generate_json(
                    prompt=(
                        f"Score prospect {prospect.firstName} {prospect.lastName} "
                        f"({prospect.title} at {prospect.company}). "
                        "Return JSON: {icpFitScore (0-100), urgencyTier (P0/P1/P2), "
                        "urgencyDeadline (ISO date or null), scoreBreakdown: {"
                        "title: int, company: int, seniority: int, intent: int}}"
                    )
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            return LeadScoreResponse(
                prospectId=prospect_id,
                icpFitScore=50,
                urgencyTier="P2",
                urgencyDeadline=None,
                scoreBreakdown={"error": "LLM timed out after 60s"},
                computedAt=datetime.now(timezone.utc),
            )
        icp_fit = int(data.get("icpFitScore", 50))
        urgency_tier = str(data.get("urgencyTier", "P2"))
        deadline_raw = data.get("urgencyDeadline")
        deadline: datetime | None = None
        if deadline_raw and isinstance(deadline_raw, str):
            try:
                deadline = datetime.fromisoformat(deadline_raw)
            except ValueError:
                deadline = None

        # Wiring audit (Task 2-e): persist the computed score on the Prospect
        # row so downstream features (Campaigns, Analytics, Lookalike) see the
        # updated ICP fit. Previously this endpoint computed + returned the
        # score but never wrote it to the Prospect — callers had to fire a
        # separate PUT /prospects/{id} to persist. Best-effort: a persist
        # failure is logged + swallowed so the score is still returned to the
        # caller (the LLM call already succeeded).
        try:
            import json as _json

            prospect.icpFitScore = icp_fit
            prospect.urgencyTier = urgency_tier
            prospect.icpScoreBreakdown = _json.dumps(
                data.get("scoreBreakdown", {})
            )
            await db.commit()
            prospect = await db.get(Prospect, prospect.id)
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning(
                "signals.lead_score.persist_failed",
                prospect_id=prospect_id,
                error=str(exc),
            )

        return LeadScoreResponse(
            prospectId=prospect_id,
            icpFitScore=icp_fit,
            urgencyTier=urgency_tier,
            urgencyDeadline=deadline,
            scoreBreakdown=data.get("scoreBreakdown", {}),
            computedAt=datetime.now(timezone.utc),
        )

    # ── Lead Score Batch ─────────────────────────────────────────────────────
    async def lead_score_batch(
        self, db: AsyncSession, body: LeadScoreBatchRequest
    ) -> LeadScoreBatchResponse:
        """Batch LLM-based lead scoring for multiple prospects."""
        llm = get_llm_service()

        # Resolve prospects to score
        stmt = select(Prospect)
        if body.prospect_ids:
            stmt = stmt.where(Prospect.id.in_(body.prospect_ids)).limit(50)
        elif body.score_all:
            stmt = stmt.where(Prospect.icpFitScore == None).limit(50)  # noqa: E711
        else:
            return LeadScoreBatchResponse(success=True, scored=0, scores=[])

        result = await db.execute(stmt)
        prospects = list(result.scalars().all())

        if not prospects:
            return LeadScoreBatchResponse(success=True, scored=0, scores=[])

        # Build batch info for LLM
        batch_info = []
        for p in prospects:
            batch_info.append({
                "id": str(p.id),
                "name": f"{p.firstName} {p.lastName}",
                "title": p.title or "",
                "company": p.company or "",
                "domain": p.domain or "",
                "seniority": str(p.seniority) if p.seniority else "",
            })

        prompt = f"""You are a B2B lead scoring expert. Score these prospects on ICP fit.

Prospects: {json.dumps(batch_info)}

For each prospect, provide:
- score (0-100): how well they match a typical ideal customer profile
- tier (A/B/C/D): A = top ICP fit, D = poor fit
- reason: brief explanation of the score

Return JSON:
{{
  "scores": [
    {{"prospect_id": "...", "score": 85, "tier": "A", "reason": "..."}},
    ...
  ]
}}"""
        try:
            raw = await asyncio.wait_for(llm.generate_json(prompt=prompt), timeout=90)
            if isinstance(raw, str):
                raw = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())

            scores = []
            for s in raw.get("scores", []):
                pid = s.get("prospect_id", "")
                score_val = int(s.get("score", 50))
                tier = str(s.get("tier", "C"))
                reason = str(s.get("reason", ""))

                # Persist score on the Prospect row
                prospect = next((p for p in prospects if str(p.id) == pid), None)
                if prospect:
                    try:
                        prospect.icpFitScore = score_val
                        # Map tier to urgency: A->P0, B->P1, C/D->P2
                        prospect.urgencyTier = {"A": "P0", "B": "P1"}.get(tier, "P2")
                    except Exception:
                        pass

                scores.append(LeadScoreBatchResult(
                    prospect_id=pid,
                    score=score_val,
                    tier=tier,
                    reason=reason,
                ))

            await db.commit()
            return LeadScoreBatchResponse(success=True, scored=len(scores), scores=scores)
        except Exception as e:
            logger.error("Lead score batch failed: %s", e)
            return LeadScoreBatchResponse(success=False, error=str(e))

    async def get_lead_score_stats(self, db: AsyncSession) -> LeadScoreStatsResponse:
        """Aggregate lead score statistics across all scored prospects."""
        from sqlalchemy import func as sa_func

        # Tier distribution
        result = await db.execute(
            select(Prospect.urgencyTier, sa_func.count(Prospect.id))
            .where(Prospect.urgencyTier != None)  # noqa: E711
            .group_by(Prospect.urgencyTier)
        )
        tier_distribution = {row[0]: row[1] for row in result.all()}

        # By seniority
        result = await db.execute(
            select(
                Prospect.seniority,
                sa_func.count(Prospect.id),
                sa_func.avg(Prospect.icpFitScore),
            )
            .where(Prospect.icpFitScore != None)  # noqa: E711
            .group_by(Prospect.seniority)
        )
        by_seniority: dict[str, dict] = {}
        for row in result.all():
            by_seniority[str(row[0])] = {
                "count": row[1],
                "avg_icp_fit_score": round(float(row[2]), 1) if row[2] else 0,
            }

        # Total scored
        result = await db.execute(
            select(sa_func.count(Prospect.id)).where(Prospect.icpFitScore != None)  # noqa: E711
        )
        total_scored = result.scalar() or 0

        return LeadScoreStatsResponse(
            tier_distribution=tier_distribution,
            by_seniority=by_seniority,
            total_scored=total_scored,
        )
