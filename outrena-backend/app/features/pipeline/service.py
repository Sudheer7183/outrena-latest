"""
pipeline/service.py — PipelineService: 5-stage GTM workflow orchestrator.

Stages:
  1. thesis   → LLM generates GTM thesis (strategy, messaging, segments)
  2. signals  → Fetches prospects, LLM analyses buying signals in batches of 5
  3. scoring  → Fetches prospects, LLM scores them in batches of 10
  4. briefs   → Takes top 5 scored prospects, LLM generates pre-call briefs
  5. campaign → Returns handoff data (redirect to Email Studio)

Uses the Phase 2 LLM gateway (call_llm / get_default_llm_config) and the
existing Prospect / IcpProfile ORM models.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_models import LlmConfig
from app.models.prospect_models import Prospect
from app.schemas.llm_config import LlmResponse
from app.services.llm_service import (
    LlmGatewayError,
    call_llm,
    get_default_llm_config,
)

from app.features.pipeline.schemas import (
    PipelineRunStageResponse,
    PipelineStatusResponse,
)

logger = structlog.get_logger(__name__)

# Hard timeouts per stage (seconds).
_THESIS_TIMEOUT = 90
_SIGNALS_TIMEOUT = 60
_SCORING_TIMEOUT = 60
_BRIEFS_TIMEOUT = 60


class PipelineService:
    """Orchestrates the 5-stage GTM pipeline."""

    # ── LLM config resolution ──────────────────────────────────────────────

    @staticmethod
    async def _get_llm_config(
        db: AsyncSession, llm_config_id: Optional[str] = None
    ) -> LlmConfig | None:
        """Resolve LLM config — specific ID or tenant default."""
        if llm_config_id:
            result = await db.execute(
                select(LlmConfig).where(LlmConfig.id == llm_config_id).limit(1)
            )
            cfg = result.scalar_one_or_none()
            if cfg:
                return cfg
        return await get_default_llm_config(db)

    # ── LLM call helper ────────────────────────────────────────────────────

    @staticmethod
    async def _call_llm_json(
        config: LlmConfig,
        prompt: str,
        timeout: float = 60,
    ) -> dict | None:
        """Call LLM with a single user prompt, parse JSON from the response.

        Returns parsed dict on success, None on failure.
        """
        messages = [{"role": "user", "content": prompt}]
        try:
            resp: LlmResponse = await asyncio.wait_for(
                call_llm(config, messages), timeout=timeout
            )
            raw = resp.content or ""
        except (LlmGatewayError, asyncio.TimeoutError, Exception) as exc:
            logger.warning("pipeline.llm_call_failed", error=str(exc))
            return None

        # Strip markdown fences if present.
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[len("```json"):]
        elif raw.startswith("```"):
            raw = raw[len("```"):]
        if raw.endswith("```"):
            raw = raw[: -len("```")]
        raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("pipeline.llm_json_parse_failed", raw=raw[:200])
            return None

    # ── Stage dispatch ─────────────────────────────────────────────────────

    async def run_stage(
        self, db: AsyncSession, body
    ) -> PipelineRunStageResponse:
        """Dispatch to the correct stage handler."""
        stage = body.stage.lower()
        handlers = {
            "thesis": self._run_thesis,
            "signals": self._run_signals,
            "scoring": self._run_scoring,
            "briefs": self._run_briefs,
            "campaign": self._run_campaign,
        }
        handler = handlers.get(stage)
        if handler is None:
            return PipelineRunStageResponse(
                success=False, stage=stage, error=f"Unknown stage: {stage}"
            )
        return await handler(db, body)

    # ── Stage 1: Thesis ────────────────────────────────────────────────────

    async def _run_thesis(self, db: AsyncSession, body) -> PipelineRunStageResponse:
        """Generate GTM thesis using LLM."""
        config = await self._get_llm_config(db, body.llm_config_id)
        if config is None:
            return PipelineRunStageResponse(
                success=False, stage="thesis", error="No LLM config available"
            )

        prompt = f"""You are a Go-To-Market strategist. Based on the following product info, generate a comprehensive GTM thesis:

Product Name: {body.product_name or 'N/A'}
Target Industries: {body.target_industries or 'N/A'}
Product Description: {body.product_description or 'N/A'}
Key Value Props: {body.key_value_props or 'N/A'}

Return a JSON object with:
- strategy_summary: 2-3 sentence strategy overview
- messaging_pillars: list of 3-4 key messaging pillars (each with title and description)
- target_segments: list of 2-3 target segments (each with name, criteria, and approach)
- competitive_positioning: 1-2 sentence competitive positioning
- recommended_channels: list of recommended outreach channels
- icp_hints: list of hints for ICP refinement"""

        raw = await self._call_llm_json(config, prompt, timeout=_THESIS_TIMEOUT)
        if raw is None:
            return PipelineRunStageResponse(
                success=False, stage="thesis", error="LLM call or JSON parse failed"
            )
        return PipelineRunStageResponse(success=True, stage="thesis", result=raw)

    # ── Stage 2: Signals ───────────────────────────────────────────────────

    async def _run_signals(self, db: AsyncSession, body) -> PipelineRunStageResponse:
        """Run signal monitoring on prospects using LLM in batches of 5."""
        # Fetch prospects (filtered by ICP if provided)
        stmt = select(Prospect).where(Prospect.deleted_at.is_(None))
        if body.icp_id:
            stmt = stmt.where(Prospect.icpProfileId == body.icp_id)
        stmt = stmt.limit(50)
        result = await db.execute(stmt)
        prospects = list(result.scalars().all())

        if not prospects:
            return PipelineRunStageResponse(
                success=True, stage="signals", result={"analyzed": 0, "signals": []}
            )

        config = await self._get_llm_config(db, body.llm_config_id)
        if config is None:
            return PipelineRunStageResponse(
                success=False, stage="signals", error="No LLM config available"
            )

        all_signals: list[dict] = []

        # Process in batches of 5
        for i in range(0, len(prospects), 5):
            batch = prospects[i : i + 5]
            batch_info = []
            for p in batch:
                batch_info.append(
                    {
                        "id": str(p.id),
                        "name": f"{p.firstName or ''} {p.lastName or ''}".strip(),
                        "company": p.company or "",
                        "title": p.title or "",
                        "domain": p.domain or "",
                    }
                )

            prompt = f"""Analyze these prospects for buying signals. For each, identify the strongest buying signal.

Prospects: {json.dumps(batch_info)}

Return JSON: {{"analysis": [{{"prospect_id": "...", "signal_type": "funding|hiring|expansion|pain_point|technology_change", "description": "...", "strength": "high|medium|low", "recommended_angle": "..."}}]}}"""

            raw = await self._call_llm_json(
                config, prompt, timeout=_SIGNALS_TIMEOUT
            )
            if raw is not None and isinstance(raw, dict) and "analysis" in raw:
                all_signals.extend(raw["analysis"])

        return PipelineRunStageResponse(
            success=True,
            stage="signals",
            result={"analyzed": len(prospects), "signals": all_signals},
        )

    # ── Stage 3: Scoring ───────────────────────────────────────────────────

    async def _run_scoring(self, db: AsyncSession, body) -> PipelineRunStageResponse:
        """Score prospects using LLM in batches of 10."""
        stmt = select(Prospect).where(Prospect.deleted_at.is_(None))
        if body.icp_id:
            stmt = stmt.where(Prospect.icpProfileId == body.icp_id)
        stmt = stmt.limit(100)
        result = await db.execute(stmt)
        prospects = list(result.scalars().all())

        if not prospects:
            return PipelineRunStageResponse(
                success=True, stage="scoring", result={"scored": 0, "scores": []}
            )

        config = await self._get_llm_config(db, body.llm_config_id)
        if config is None:
            return PipelineRunStageResponse(
                success=False, stage="scoring", error="No LLM config available"
            )

        all_scores: list[dict] = []

        for i in range(0, len(prospects), 10):
            batch = prospects[i : i + 10]
            batch_info = [
                {
                    "id": str(p.id),
                    "name": f"{p.firstName or ''} {p.lastName or ''}".strip(),
                    "company": p.company or "",
                    "title": p.title or "",
                }
                for p in batch
            ]

            prompt = f"""Score these prospects for outbound priority. Consider seniority, company fit, title relevance.

Prospects: {json.dumps(batch_info)}

Return JSON: {{"scores": [{{"prospect_id": "...", "score": 85, "tier": "TIER_1|TIER_2|TIER_3|TIER_4", "reason": "..."}}]}}"""

            raw = await self._call_llm_json(
                config, prompt, timeout=_SCORING_TIMEOUT
            )
            if raw is not None and isinstance(raw, dict) and "scores" in raw:
                # Persist scores back to prospects (qaScore + urgencyTier)
                for score_data in raw["scores"]:
                    p = next(
                        (
                            x
                            for x in batch
                            if str(x.id) == score_data.get("prospect_id")
                        ),
                        None,
                    )
                    if p:
                        try:
                            p.qaScore = score_data.get("score", 0)
                            p.urgencyTier = score_data.get("tier", "TIER_4")
                        except Exception:
                            pass
                all_scores.extend(raw["scores"])

        try:
            await db.commit()
        except Exception as exc:
            logger.warning("pipeline.scoring.persist_failed", error=str(exc))

        return PipelineRunStageResponse(
            success=True,
            stage="scoring",
            result={"scored": len(prospects), "scores": all_scores},
        )

    # ── Stage 4: Briefs ────────────────────────────────────────────────────

    async def _run_briefs(self, db: AsyncSession, body) -> PipelineRunStageResponse:
        """Generate prospect briefs for top 5 scored prospects."""
        stmt = (
            select(Prospect)
            .where(Prospect.deleted_at.is_(None), Prospect.qaScore != None)  # noqa: E711
            .order_by(Prospect.qaScore.desc())
            .limit(5)
        )
        result = await db.execute(stmt)
        prospects = list(result.scalars().all())

        if not prospects:
            return PipelineRunStageResponse(
                success=True, stage="briefs", result={"generated": 0, "briefs": []}
            )

        config = await self._get_llm_config(db, body.llm_config_id)
        if config is None:
            return PipelineRunStageResponse(
                success=False, stage="briefs", error="No LLM config available"
            )

        all_briefs: list[dict] = []

        for p in prospects:
            prompt = f"""Generate a 60-second pre-call brief for this prospect:
Name: {p.firstName or ''} {p.lastName or ''}
Company: {p.company or ''}
Title: {p.title or ''}
Domain: {p.domain or ''}

Return JSON: {{"brief": "...", "key_talking_points": ["..."], "potential_objections": ["..."], "icebreaker": "..."}}"""

            raw = await self._call_llm_json(config, prompt, timeout=_BRIEFS_TIMEOUT)
            if raw is not None:
                raw["prospect_id"] = str(p.id)
                raw["prospect_name"] = (
                    f"{p.firstName or ''} {p.lastName or ''}".strip()
                )
                all_briefs.append(raw)

        return PipelineRunStageResponse(
            success=True,
            stage="briefs",
            result={"generated": len(all_briefs), "briefs": all_briefs},
        )

    # ── Stage 5: Campaign ──────────────────────────────────────────────────

    async def _run_campaign(
        self, db: AsyncSession, body
    ) -> PipelineRunStageResponse:
        """Campaign stage — handoff to Email Studio."""
        return PipelineRunStageResponse(
            success=True,
            stage="campaign",
            result={
                "message": "Pipeline complete. Open Email Studio to build your campaign.",
                "handoff": True,
            },
        )

    # ── Status ─────────────────────────────────────────────────────────────

    async def get_status(
        self, db: AsyncSession, icp_id: Optional[str] = None
    ) -> PipelineStatusResponse:
        """Return current pipeline status for a given ICP.

        Future: persist stage results and track completion. For now returns
        an empty baseline.
        """
        return PipelineStatusResponse(
            stages_completed=[], current_stage=None
        )
