"""content_ideas_service.py — ContentIdea CRUD + LLM generation.

FIXES:
  1. generate() now uses GlobalLlmConfig via public-schema session instead of
     the legacy get_llm_service() which hits open.bigmodel.cn with no key → stub.
  2. generate() accepts topic/audience directly (no icpProfileId required)
     matching the frontend ContentIdeaGenerateRequest {topic, audience, count}.
  3. JSON extraction uses the robust multi-strategy parser (same as pipeline fix).
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase3_models import ContentIdea
from app.models.prospect_models import IcpProfile
from app.schemas.content_ideas import ContentIdeaCreate, ContentIdeaUpdate
from app.services.llm_service import call_llm, LlmGatewayError

logger = structlog.get_logger(__name__)

_LLM_TIMEOUT = 60


class ContentIdeaService:

    # ── LLM config ─────────────────────────────────────────────────────────

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
            logger.warning("content_ideas.llm_config.fetch_failed", error=str(exc))
            return None

    @staticmethod
    def _extract_json(raw: str) -> list | dict | None:
        raw = raw.strip()
        if "```" in raw:
            fence_start = raw.find("```")
            after_fence = raw[fence_start + 3:]
            if after_fence.startswith("json"):
                after_fence = after_fence[4:]
            after_fence = after_fence.lstrip("\n")
            fence_end = after_fence.find("```")
            raw = after_fence[:fence_end].strip() if fence_end != -1 else after_fence.strip()
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
            logger.warning("content_ideas.json_parse_failed", raw=raw[:200])
            return None

    # ── CRUD ───────────────────────────────────────────────────────────────

    async def list(
        self,
        db: AsyncSession,
        *,
        icp_profile_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ContentIdea]:
        stmt = select(ContentIdea).offset(offset).limit(limit)
        if icp_profile_id:
            stmt = stmt.where(ContentIdea.icpProfileId == icp_profile_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, idea_id: str) -> ContentIdea | None:
        result = await db.execute(
            select(ContentIdea).where(ContentIdea.id == idea_id)
        )
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, body: ContentIdeaCreate) -> ContentIdea:
        item = ContentIdea(**body.model_dump())
        db.add(item)
        await db.commit()
        return await db.get(ContentIdea, item.id)

    async def update(
        self, db: AsyncSession, idea_id: str, body: ContentIdeaUpdate
    ) -> ContentIdea | None:
        item = await self.get(db, idea_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        return await db.get(ContentIdea, item.id)

    async def delete(self, db: AsyncSession, idea_id: str) -> bool:
        item = await self.get(db, idea_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def generate(
        self,
        db: AsyncSession,
        icp_profile_id: str | None,
        count: int = 5,
        topic: str | None = None,
        audience: str | None = None,
    ) -> list[ContentIdea]:
        """LLM-generate N content ideas.

        Accepts either:
          - icp_profile_id: look up ICP name/persona and use as context
          - topic + audience: use directly (frontend sends these when no ICP selected)
        Both paths now use GlobalLlmConfig (not the legacy LlmService stub).
        """
        # Build context string
        icp_context = ""
        if icp_profile_id:
            icp_result = await db.execute(
                select(IcpProfile).where(IcpProfile.id == icp_profile_id)
            )
            icp = icp_result.scalar_one_or_none()
            if icp:
                icp_context = f"ICP: '{icp.name}' (persona: {icp.personaDescription or icp.name}). "

        topic_context = ""
        if topic:
            topic_context = f"Topic: {topic}. "
        if audience:
            topic_context += f"Target audience: {audience}. "

        if not icp_context and not topic_context:
            topic_context = "Topic: B2B sales outreach. Target audience: sales professionals. "

        llm_config = await self._get_llm_config()
        if llm_config is None:
            logger.warning("content_ideas.generate.no_llm_config")
            return []

        prompt = (
            f"Generate {count} outreach content ideas. "
            f"{icp_context}{topic_context}"
            "Each idea needs: title (compelling headline), angle (e.g. Contrarian, How-to, "
            "Data-driven, Framework, Case study), body (50-100 word description of the content). "
            "Return ONLY a JSON array with no markdown, no explanation: "
            '[{"title":"...","angle":"...","body":"..."}]'
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a B2B content strategist. Generate creative, specific content ideas. "
                    "Always respond with a valid JSON array only — no markdown, no preamble."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        raw = ""
        try:
            resp = await asyncio.wait_for(
                call_llm(llm_config, messages), timeout=_LLM_TIMEOUT
            )
            raw = resp.content or ""
        except (LlmGatewayError, asyncio.TimeoutError, Exception) as exc:
            logger.warning("content_ideas.llm_call_failed", error=str(exc))
            return []

        ideas_data = self._extract_json(raw)
        if not isinstance(ideas_data, list):
            ideas_data = []

        items: list[ContentIdea] = []
        for idea in ideas_data[:count]:
            if not isinstance(idea, dict):
                continue
            item = ContentIdea(
                icpProfileId=icp_profile_id or None,
                title=str(idea.get("title", "Untitled")),
                angle=str(idea.get("angle", "")).strip() or None,
                body=str(idea.get("body", "")),
                status="idea",
            )
            db.add(item)
            items.append(item)

        if items:
            try:
                await db.commit()
            except Exception as exc:
                logger.warning("content_ideas.commit_failed", error=str(exc))
                return []

        # Refresh after commit (TimestampMixin server_default)
        refreshed: list[ContentIdea] = []
        for item in items:
            obj = await db.get(ContentIdea, item.id)
            if obj:
                refreshed.append(obj)

        return refreshed