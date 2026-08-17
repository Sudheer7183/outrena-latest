"""
pipeline/service.py — PipelineService: 5-stage GTM workflow orchestrator.

FIX: _get_llm_config() previously called get_default_llm_config(db) which
queries the tenant-schema LlmConfig table (empty for most tenants).
LLM configs created in the UI live in public.global_llm_config (GlobalLlmConfig).
Now mirrors the exact pattern from LlmConfigService.test_llm() and the
meeting prep service fix: open a fresh public-schema session, query
GlobalLlmConfig, decrypt the key, return a SimpleNamespace shim accepted
by call_llm().
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Optional

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect_models import Prospect
from app.schemas.llm_config import LlmResponse
from app.services.llm_service import LlmGatewayError, call_llm

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
    ):
        """Resolve LLM config from public.global_llm_config.

        Queries GlobalLlmConfig (the real table written by the LLM Config UI)
        via a fresh public-schema session. Mirrors LlmConfigService.test_llm()
        exactly. Returns a SimpleNamespace shim accepted by call_llm(), or
        None if no active config exists.

        llm_config_id is the integer PK of GlobalLlmConfig (sent as string
        from the frontend Select). When provided, loads that specific row.
        Falls back to is_default=True, then any active row.
        """
        from app.core.database import AsyncSessionLocal
        from app.models.global_llm_config import GlobalLlmConfig
        from app.services.secret_service import decrypt_at_rest

        try:
            async with AsyncSessionLocal() as pub_db:
                await pub_db.execute(text('SET search_path TO "public"'))

                global_config = None

                # Try specific config first (frontend passes integer PK as string)
                if llm_config_id:
                    try:
                        config_pk = int(llm_config_id)
                        result = await pub_db.execute(
                            select(GlobalLlmConfig)
                            .where(GlobalLlmConfig.id == config_pk)
                            .where(GlobalLlmConfig.is_active.is_(True))
                            .limit(1)
                        )
                        global_config = result.scalar_one_or_none()
                    except (ValueError, TypeError):
                        pass

                # Fall back to default
                if global_config is None:
                    result = await pub_db.execute(
                        select(GlobalLlmConfig)
                        .where(GlobalLlmConfig.is_active.is_(True))
                        .where(GlobalLlmConfig.is_default.is_(True))
                        .limit(1)
                    )
                    global_config = result.scalar_one_or_none()

                # Fall back to any active config
                if global_config is None:
                    result = await pub_db.execute(
                        select(GlobalLlmConfig)
                        .where(GlobalLlmConfig.is_active.is_(True))
                        .order_by(GlobalLlmConfig.id)
                        .limit(1)
                    )
                    global_config = result.scalar_one_or_none()

                if global_config is None:
                    return None

                try:
                    api_key = decrypt_at_rest(global_config.api_key_encrypted)
                except Exception as exc:
                    logger.warning("pipeline.llm_config.decrypt_failed", error=str(exc))
                    return None

                return SimpleNamespace(
                    provider=global_config.provider,
                    name=global_config.display_name,
                    modelId=global_config.model_name,
                    apiKey=api_key,
                    baseUrl=global_config.base_url,
                    isActive=global_config.is_active,
                    isDefault=global_config.is_default,
                    settings="{}",
                    global_llm_config_id=None,
                )

        except Exception as exc:
            logger.warning("pipeline.llm_config.fetch_failed", error=str(exc))
            return None

    # ── LLM call helper ────────────────────────────────────────────────────

    @staticmethod
    async def _call_llm_json(
        config,
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

        # Extract JSON robustly — handles:
        #   1. Preamble text before ```json fence (e.g. "Here is a thesis:\n```json\n{...}")
        #   2. Plain ```json or ``` fences with no preamble
        #   3. Raw JSON with no fences at all
        raw = raw.strip()

        # Strategy 1: extract content between ```json ... ``` or ``` ... ```
        if "```" in raw:
            # Find the first ``` fence and take everything after it
            fence_start = raw.find("```")
            after_fence = raw[fence_start + 3:]
            # Skip optional language tag (e.g. "json\n")
            if after_fence.startswith("json"):
                after_fence = after_fence[4:]
            after_fence = after_fence.lstrip("\n")
            # Find closing fence
            fence_end = after_fence.find("```")
            if fence_end != -1:
                raw = after_fence[:fence_end].strip()
            else:
                raw = after_fence.strip()

        # Strategy 2: if still not valid JSON, find first { or [ in the string
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
                success=False, stage="thesis",
                error="No LLM config available. Configure one in LLM Models."
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
                success=False, stage="signals",
                error="No LLM config available. Configure one in LLM Models."
            )

        all_signals: list[dict] = []

        for i in range(0, len(prospects), 5):
            batch = prospects[i: i + 5]
            batch_info = [
                {
                    "id": str(p.id),
                    "name": f"{p.firstName or ''} {p.lastName or ''}".strip(),
                    "company": p.company or "",
                    "title": p.title or "",
                    "domain": p.domain or "",
                }
                for p in batch
            ]

            prompt = f"""Analyze these prospects for buying signals. For each, identify the strongest buying signal.

Prospects: {json.dumps(batch_info)}

Return JSON: {{"analysis": [{{"prospect_id": "...", "signal_type": "funding|hiring|expansion|pain_point|technology_change", "description": "...", "strength": "high|medium|low", "recommended_angle": "..."}}]}}"""

            raw = await self._call_llm_json(config, prompt, timeout=_SIGNALS_TIMEOUT)
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
                success=False, stage="scoring",
                error="No LLM config available. Configure one in LLM Models."
            )

        all_scores: list[dict] = []

        for i in range(0, len(prospects), 10):
            batch = prospects[i: i + 10]
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

            raw = await self._call_llm_json(config, prompt, timeout=_SCORING_TIMEOUT)
            if raw is not None and isinstance(raw, dict) and "scores" in raw:
                for score_data in raw["scores"]:
                    p = next(
                        (x for x in batch if str(x.id) == score_data.get("prospect_id")),
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
                success=False, stage="briefs",
                error="No LLM config available. Configure one in LLM Models."
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
                raw["prospect_name"] = f"{p.firstName or ''} {p.lastName or ''}".strip()
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
        """Return current pipeline status for a given ICP."""
        return PipelineStatusResponse(
            stages_completed=[], current_stage=None
        )