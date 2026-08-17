# # """
# # prospect_source_service.py — Source CRUD + NL search + lookalike + profile + brief.
# # """
# # from __future__ import annotations

# # import json
# # from typing import Any

# # from sqlalchemy import select
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.models.phase3_models import ProspectSource, SourceConfig
# # from app.models.prospect_models import Prospect
# # from app.schemas.prospect_source import (
# #     LookalikeHit,
# #     LookalikeResponse,
# #     NaturalLanguageSearchResponse,
# #     ProspectBriefResponse,
# #     ProspectSearchHit,
# #     SourceConfigCreate,
# #     SourceConfigUpdate,
# #     UltimateProfileResponse,
# # )
# # from app.services.llm_service import get_llm_service


# # class ProspectSourceService:
# #     # ── Source config ──────────────────────────────────────────────────────
# #     async def list_configs(self, db: AsyncSession) -> list[SourceConfig]:
# #         result = await db.execute(select(SourceConfig))
# #         return list(result.scalars().all())

# #     async def get_config(
# #         self, db: AsyncSession, source: str
# #     ) -> SourceConfig | None:
# #         result = await db.execute(
# #             select(SourceConfig).where(SourceConfig.source == source)
# #         )
# #         return result.scalar_one_or_none()

# #     async def create_config(
# #         self, db: AsyncSession, body: SourceConfigCreate
# #     ) -> SourceConfig:
# #         data = body.model_dump()
# #         data["settings"] = json.dumps(data.get("settings", {}))
# #         item = SourceConfig(**data)
# #         db.add(item)
# #         await db.commit()
# #         item = await db.get(SourceConfig, item.id)
# #         return item

# #     async def update_config(
# #         self, db: AsyncSession, source: str, body: SourceConfigUpdate
# #     ) -> SourceConfig | None:
# #         item = await self.get_config(db, source)
# #         if item is None:
# #             return None
# #         data = body.model_dump(exclude_unset=True)
# #         if "settings" in data and data["settings"] is not None:
# #             data["settings"] = json.dumps(data["settings"])
# #         for key, value in data.items():
# #             setattr(item, key, value)
# #         await db.commit()
# #         item = await db.get(SourceConfig, item.id)
# #         return item

# #     async def delete_config(self, db: AsyncSession, source: str) -> bool:
# #         item = await self.get_config(db, source)
# #         if item is None:
# #             return False
# #         await db.delete(item)
# #         await db.commit()
# #         return True

# #     # ── Prospect source records ────────────────────────────────────────────
# #     async def list_sources(
# #         self, db: AsyncSession, *, prospect_id: str | None = None
# #     ) -> list[ProspectSource]:
# #         stmt = select(ProspectSource)
# #         if prospect_id:
# #             stmt = stmt.where(ProspectSource.prospectId == prospect_id)
# #         result = await db.execute(stmt)
# #         return list(result.scalars().all())

# #     # ── Natural-language search ────────────────────────────────────────────
# #     async def natural_language_search(
# #         self, db: AsyncSession, query: str, icp_profile_id: str | None, limit: int
# #     ) -> NaturalLanguageSearchResponse:
# #         llm = get_llm_service()
# #         filters = await llm.generate_json(
# #             prompt=(
# #                 f"Convert this prospect search request into filters: '{query}'. "
# #                 "Return JSON: {company, title, seniority, industry, location}. "
# #                 "Empty string for any unspecified field."
# #             )
# #         )
# #         stmt = select(Prospect).limit(limit)
# #         if filters.get("company"):
# #             stmt = stmt.where(Prospect.company.ilike(f"%{filters['company']}%"))
# #         if filters.get("title"):
# #             stmt = stmt.where(Prospect.title.ilike(f"%{filters['title']}%"))
# #         if filters.get("seniority"):
# #             stmt = stmt.where(Prospect.seniority == filters["seniority"])
# #         result = await db.execute(stmt)
# #         prospects = [
# #             ProspectSearchHit(
# #                 id=p.id,
# #                 firstName=p.firstName,
# #                 lastName=p.lastName,
# #                 email=p.email,
# #                 title=p.title,
# #                 company=p.company,
# #             )
# #             for p in result.scalars().all()
# #         ]
# #         return NaturalLanguageSearchResponse(
# #             interpretedFilters=filters,
# #             prospects=prospects,
# #             count=len(prospects),
# #         )

# #     # ── Lookalike ──────────────────────────────────────────────────────────
# #     async def lookalike(
# #         self, db: AsyncSession, prospect_id: str, limit: int
# #     ) -> LookalikeResponse:
# #         seed_result = await db.execute(
# #             select(Prospect).where(Prospect.id == prospect_id)
# #         )
# #         seed = seed_result.scalar_one_or_none()
# #         if seed is None:
# #             return LookalikeResponse(seedProspectId=prospect_id, lookalikes=[], count=0)
# #         stmt = select(Prospect).where(Prospect.id != prospect_id).limit(limit)
# #         if seed.company:
# #             stmt = stmt.where(Prospect.company == seed.company)
# #         result = await db.execute(stmt)
# #         lookalikes = [
# #             LookalikeHit(
# #                 id=p.id,
# #                 firstName=p.firstName,
# #                 lastName=p.lastName,
# #                 title=p.title,
# #                 company=p.company,
# #                 similarityScore=0.85,  # Phase 4 will compute real score
# #             )
# #             for p in result.scalars().all()
# #         ]
# #         return LookalikeResponse(
# #             seedProspectId=prospect_id, lookalikes=lookalikes, count=len(lookalikes)
# #         )

# #     # ── Ultimate profile ───────────────────────────────────────────────────
# #     async def ultimate_profile(
# #         self, db: AsyncSession, prospect_id: str
# #     ) -> UltimateProfileResponse:
# #         prospect_result = await db.execute(
# #             select(Prospect).where(Prospect.id == prospect_id)
# #         )
# #         prospect = prospect_result.scalar_one_or_none()
# #         if prospect is None:
# #             return UltimateProfileResponse(
# #                 prospectId=prospect_id, profile={"error": "Prospect not found"}
# #             )
# #         llm = get_llm_service()
# #         profile = await llm.generate_json(
# #             prompt=(
# #                 f"Build an ultimate profile for {prospect.firstName} "
# #                 f"{prospect.lastName} ({prospect.title} at {prospect.company}). "
# #                 "Include: personalityTraits, communicationStyle, decisionFactors, "
# #                 "likelyObjections, recommendedApproach. Respond as JSON."
# #             )
# #         )
# #         return UltimateProfileResponse(prospectId=prospect_id, profile=profile)

# #     # ── Prospect brief ─────────────────────────────────────────────────────
# #     async def brief(
# #         self, db: AsyncSession, prospect_id: str, call_type: str
# #     ) -> ProspectBriefResponse:
# #         prospect_result = await db.execute(
# #             select(Prospect).where(Prospect.id == prospect_id)
# #         )
# #         prospect = prospect_result.scalar_one_or_none()
# #         if prospect is None:
# #             return ProspectBriefResponse(
# #                 prospectId=prospect_id,
# #                 brief=f"[Brief unavailable — prospect {prospect_id} not found]",
# #             )
# #         llm = get_llm_service()
# #         brief_text = await llm.generate(
# #             prompt=(
# #                 f"Generate a {call_type} call brief for "
# #                 f"{prospect.firstName} {prospect.lastName} "
# #                 f"({prospect.title} at {prospect.company}). "
# #                 "Include icebreaker, 3 probing questions, and a closing CTA."
# #             )
# #         )
# #         return ProspectBriefResponse(prospectId=prospect_id, brief=brief_text)

# """
# prospect_source_service.py — Source CRUD + NL search + lookalike + profile + brief.

# FIXES:
#   ultimate_profile(): was using get_llm_service().generate_json() → returns {}
#   brief(): was using get_llm_service().generate() → returns [LLM-STUB]
#   Both now use GlobalLlmConfig via public-schema session + call_llm(),
#   same pattern as pipeline / meeting prep / weekly digest / content ideas fixes.

#   Also: generate_json() (legacy) silently returned {} on any JSON parse failure.
#   Now using robust multi-strategy JSON extraction that handles preamble text
#   before fences (same as pipeline service fix).
# """
# from __future__ import annotations

# import asyncio
# import json
# from types import SimpleNamespace
# from typing import Any

# import structlog
# from sqlalchemy import select, text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.phase3_models import ProspectSource, SourceConfig
# from app.models.prospect_models import Prospect
# from app.schemas.prospect_source import (
#     LookalikeHit,
#     LookalikeResponse,
#     NaturalLanguageSearchResponse,
#     ProspectBriefResponse,
#     ProspectSearchHit,
#     SourceConfigCreate,
#     SourceConfigUpdate,
#     UltimateProfileResponse,
# )
# from app.services.llm_service import call_llm, LlmGatewayError

# logger = structlog.get_logger(__name__)

# _LLM_TIMEOUT = 60


# class ProspectSourceService:

#     # ── LLM config (GlobalLlmConfig, same pattern as all other services) ───

#     @staticmethod
#     async def _get_llm_config():
#         from app.core.database import AsyncSessionLocal
#         from app.models.global_llm_config import GlobalLlmConfig
#         from app.services.secret_service import decrypt_at_rest

#         try:
#             async with AsyncSessionLocal() as pub_db:
#                 await pub_db.execute(text('SET search_path TO "public"'))
#                 result = await pub_db.execute(
#                     select(GlobalLlmConfig)
#                     .where(GlobalLlmConfig.is_active.is_(True))
#                     .where(GlobalLlmConfig.is_default.is_(True))
#                     .limit(1)
#                 )
#                 config = result.scalar_one_or_none()
#                 if config is None:
#                     result = await pub_db.execute(
#                         select(GlobalLlmConfig)
#                         .where(GlobalLlmConfig.is_active.is_(True))
#                         .order_by(GlobalLlmConfig.id)
#                         .limit(1)
#                     )
#                     config = result.scalar_one_or_none()
#                 if config is None:
#                     return None
#                 api_key = decrypt_at_rest(config.api_key_encrypted)
#                 return SimpleNamespace(
#                     provider=config.provider,
#                     name=config.display_name,
#                     modelId=config.model_name,
#                     apiKey=api_key,
#                     baseUrl=config.base_url,
#                     isActive=config.is_active,
#                     isDefault=config.is_default,
#                     settings="{}",
#                     global_llm_config_id=None,
#                 )
#         except Exception as exc:
#             logger.warning("prospect_source.llm_config.fetch_failed", error=str(exc))
#             return None

#     @staticmethod
#     def _extract_json(raw: str) -> dict | list | None:
#         """Robust JSON extraction — handles preamble text and markdown fences."""
#         raw = raw.strip()
#         if "```" in raw:
#             fence_start = raw.find("```")
#             after_fence = raw[fence_start + 3:]
#             if after_fence.startswith("json"):
#                 after_fence = after_fence[4:]
#             after_fence = after_fence.lstrip("\n")
#             fence_end = after_fence.find("```")
#             raw = after_fence[:fence_end].strip() if fence_end != -1 else after_fence.strip()
#         if raw and raw[0] not in ("{", "["):
#             brace = min(
#                 (raw.find(c) for c in ("{", "[") if raw.find(c) != -1),
#                 default=-1,
#             )
#             if brace != -1:
#                 raw = raw[brace:]
#         try:
#             return json.loads(raw)
#         except json.JSONDecodeError:
#             logger.warning("prospect_source.json_parse_failed", raw=raw[:200])
#             return None

#     async def _call_llm(self, prompt: str, system: str | None = None) -> str:
#         """Call LLM via GlobalLlmConfig. Returns raw text or empty string."""
#         config = await self._get_llm_config()
#         if config is None:
#             return ""
#         messages = []
#         if system:
#             messages.append({"role": "system", "content": system})
#         messages.append({"role": "user", "content": prompt})
#         try:
#             resp = await asyncio.wait_for(
#                 call_llm(config, messages), timeout=_LLM_TIMEOUT
#             )
#             return resp.content or ""
#         except (LlmGatewayError, asyncio.TimeoutError, Exception) as exc:
#             logger.warning("prospect_source.llm_call_failed", error=str(exc))
#             return ""

#     # ── Source config ──────────────────────────────────────────────────────

#     async def list_configs(self, db: AsyncSession) -> list[SourceConfig]:
#         result = await db.execute(select(SourceConfig))
#         return list(result.scalars().all())

#     async def get_config(self, db: AsyncSession, source: str) -> SourceConfig | None:
#         result = await db.execute(
#             select(SourceConfig).where(SourceConfig.source == source)
#         )
#         return result.scalar_one_or_none()

#     async def create_config(self, db: AsyncSession, body: SourceConfigCreate) -> SourceConfig:
#         data = body.model_dump()
#         data["settings"] = json.dumps(data.get("settings", {}))
#         item = SourceConfig(**data)
#         db.add(item)
#         await db.commit()
#         item = await db.get(SourceConfig, item.id)
#         return item

#     async def update_config(
#         self, db: AsyncSession, source: str, body: SourceConfigUpdate
#     ) -> SourceConfig | None:
#         item = await self.get_config(db, source)
#         if item is None:
#             return None
#         data = body.model_dump(exclude_unset=True)
#         if "settings" in data and data["settings"] is not None:
#             data["settings"] = json.dumps(data["settings"])
#         for key, value in data.items():
#             setattr(item, key, value)
#         await db.commit()
#         item = await db.get(SourceConfig, item.id)
#         return item

#     async def delete_config(self, db: AsyncSession, source: str) -> bool:
#         item = await self.get_config(db, source)
#         if item is None:
#             return False
#         await db.delete(item)
#         await db.commit()
#         return True

#     # ── Prospect source records ────────────────────────────────────────────

#     async def list_sources(
#         self, db: AsyncSession, *, prospect_id: str | None = None
#     ) -> list[ProspectSource]:
#         stmt = select(ProspectSource)
#         if prospect_id:
#             stmt = stmt.where(ProspectSource.prospectId == prospect_id)
#         result = await db.execute(stmt)
#         return list(result.scalars().all())

#     # ── Natural-language search ────────────────────────────────────────────

#     async def natural_language_search(
#         self, db: AsyncSession, query: str, icp_profile_id: str | None, limit: int
#     ) -> NaturalLanguageSearchResponse:
#         # Use GlobalLlmConfig for NL→filter parsing
#         raw = await self._call_llm(
#             prompt=(
#                 f"Convert this prospect search request into filters: '{query}'. "
#                 "Return JSON only (no markdown): "
#                 '{"company":"","title":"","seniority":"","industry":"","location":""} '
#                 "Empty string for any unspecified field."
#             ),
#             system="You are a search query parser. Always respond with valid JSON only."
#         )
#         filters: dict[str, Any] = {}
#         if raw:
#             parsed = self._extract_json(raw)
#             if isinstance(parsed, dict):
#                 filters = parsed

#         stmt = select(Prospect).where(Prospect.deleted_at.is_(None)).limit(limit)
#         if filters.get("company"):
#             stmt = stmt.where(Prospect.company.ilike(f"%{filters['company']}%"))
#         if filters.get("title"):
#             stmt = stmt.where(Prospect.title.ilike(f"%{filters['title']}%"))
#         if filters.get("seniority"):
#             stmt = stmt.where(Prospect.seniority == filters["seniority"])

#         result = await db.execute(stmt)
#         prospects = [
#             ProspectSearchHit(
#                 id=p.id,
#                 firstName=p.firstName,
#                 lastName=p.lastName,
#                 email=p.email,
#                 title=p.title,
#                 company=p.company,
#             )
#             for p in result.scalars().all()
#         ]
#         return NaturalLanguageSearchResponse(
#             interpretedFilters=filters,
#             prospects=prospects,
#             count=len(prospects),
#         )

#     # ── Lookalike ──────────────────────────────────────────────────────────

#     async def lookalike(
#         self, db: AsyncSession, prospect_id: str, limit: int
#     ) -> LookalikeResponse:
#         seed_result = await db.execute(
#             select(Prospect).where(Prospect.id == prospect_id)
#         )
#         seed = seed_result.scalar_one_or_none()
#         if seed is None:
#             return LookalikeResponse(seedProspectId=prospect_id, lookalikes=[], count=0)

#         stmt = select(Prospect).where(
#             Prospect.id != prospect_id,
#             Prospect.deleted_at.is_(None),
#         ).limit(limit)
#         if seed.company:
#             stmt = stmt.where(Prospect.company == seed.company)

#         result = await db.execute(stmt)
#         lookalikes = [
#             LookalikeHit(
#                 id=p.id,
#                 firstName=p.firstName,
#                 lastName=p.lastName,
#                 title=p.title,
#                 company=p.company,
#                 similarityScore=0.85,
#             )
#             for p in result.scalars().all()
#         ]
#         return LookalikeResponse(
#             seedProspectId=prospect_id,
#             lookalikes=lookalikes,
#             count=len(lookalikes),
#         )

#     # ── Ultimate profile ───────────────────────────────────────────────────

#     async def ultimate_profile(
#         self, db: AsyncSession, prospect_id: str
#     ) -> UltimateProfileResponse:
#         prospect_result = await db.execute(
#             select(Prospect).where(Prospect.id == prospect_id)
#         )
#         prospect = prospect_result.scalar_one_or_none()
#         if prospect is None:
#             return UltimateProfileResponse(
#                 prospectId=prospect_id, profile={"error": "Prospect not found"}
#             )

#         # FIX: use GlobalLlmConfig + call_llm(), not get_llm_service().generate_json()
#         raw = await self._call_llm(
#             prompt=(
#                 f"Build an ultimate B2B sales profile for "
#                 f"{prospect.firstName} {prospect.lastName} "
#                 f"({prospect.title or 'unknown title'} at "
#                 f"{prospect.company or 'unknown company'}). "
#                 "Return valid JSON only (no markdown) with these keys: "
#                 "personalityTraits (list of strings), "
#                 "communicationStyle (string), "
#                 "decisionFactors (list of strings), "
#                 "likelyObjections (list of strings), "
#                 "recommendedApproach (string), "
#                 "icebreaker (string)."
#             ),
#             system=(
#                 "You are a B2B sales intelligence analyst. "
#                 "Always respond with valid JSON only — no markdown, no preamble."
#             ),
#         )

#         profile: dict[str, Any] = {}
#         if raw:
#             parsed = self._extract_json(raw)
#             if isinstance(parsed, dict):
#                 profile = parsed

#         if not profile:
#             # Fallback: return structured placeholder so UI doesn't show empty card
#             profile = {
#                 "note": "LLM profile generation unavailable — check LLM config.",
#                 "prospectName": f"{prospect.firstName} {prospect.lastName}",
#                 "title": prospect.title or "",
#                 "company": prospect.company or "",
#             }

#         return UltimateProfileResponse(prospectId=prospect_id, profile=profile)

#     # ── Prospect brief ─────────────────────────────────────────────────────

#     async def brief(
#         self, db: AsyncSession, prospect_id: str, call_type: str
#     ) -> ProspectBriefResponse:
#         prospect_result = await db.execute(
#             select(Prospect).where(Prospect.id == prospect_id)
#         )
#         prospect = prospect_result.scalar_one_or_none()
#         if prospect is None:
#             return ProspectBriefResponse(
#                 prospectId=prospect_id,
#                 brief=f"[Brief unavailable — prospect {prospect_id} not found]",
#             )

#         # FIX: use GlobalLlmConfig + call_llm(), not get_llm_service().generate()
#         brief_text = await self._call_llm(
#             prompt=(
#                 f"Generate a {call_type} call brief for "
#                 f"{prospect.firstName} {prospect.lastName} "
#                 f"({prospect.title or 'unknown title'} at "
#                 f"{prospect.company or 'unknown company'}). "
#                 "Include: 1) a personalised icebreaker, "
#                 "2) 3 probing discovery questions, "
#                 "3) key pain points to probe, "
#                 "4) a closing next-step CTA. "
#                 "Format as plain text with clear section headings."
#             ),
#             system=(
#                 "You are an expert B2B sales coach writing call prep briefs. "
#                 "Be specific, concise, and actionable. "
#                 "Write in plain text — no JSON, no markdown fences."
#             ),
#         )

#         if not brief_text:
#             brief_text = (
#                 f"Brief unavailable — LLM config not set. "
#                 f"Prospect: {prospect.firstName} {prospect.lastName}, "
#                 f"{prospect.title} at {prospect.company}."
#             )

#         return ProspectBriefResponse(prospectId=prospect_id, brief=brief_text)
"""
prospect_source_service.py — Source CRUD + NL search + lookalike + profile + brief.

FIXES:
  ultimate_profile(): was using get_llm_service().generate_json() → returns {}
  brief(): was using get_llm_service().generate() → returns [LLM-STUB]
  Both now use GlobalLlmConfig via public-schema session + call_llm(),
  same pattern as pipeline / meeting prep / weekly digest / content ideas fixes.

  Also: generate_json() (legacy) silently returned {} on any JSON parse failure.
  Now using robust multi-strategy JSON extraction that handles preamble text
  before fences (same as pipeline service fix).
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase3_models import ProspectSource, SourceConfig
from app.models.prospect_models import Prospect
from app.schemas.prospect_source import (
    LookalikeHit,
    LookalikeResponse,
    NaturalLanguageSearchResponse,
    ProspectBriefResponse,
    ProspectSearchHit,
    SourceConfigCreate,
    SourceConfigUpdate,
    UltimateProfileResponse,
)
from app.services.llm_service import call_llm, LlmGatewayError

logger = structlog.get_logger(__name__)

_LLM_TIMEOUT = 60
# Local models (Ollama on CPU) are much slower — allow 5 minutes
_LLM_TIMEOUT_LOCAL = 300


class ProspectSourceService:

    # ── LLM config (GlobalLlmConfig, same pattern as all other services) ───

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
            logger.warning("prospect_source.llm_config.fetch_failed", error=str(exc))
            return None

    @staticmethod
    def _extract_json(raw: str) -> dict | list | None:
        """Robust JSON extraction — handles preamble text and markdown fences."""
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
            logger.warning("prospect_source.json_parse_failed", raw=raw[:200])
            return None

    async def _call_llm(self, prompt: str, system: str | None = None) -> str:
        """Call LLM via GlobalLlmConfig. Returns raw text or empty string."""
        config = await self._get_llm_config()
        if config is None:
            return ""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            _timeout = _LLM_TIMEOUT_LOCAL if getattr(config, "provider", "") == "local" else _LLM_TIMEOUT
            resp = await asyncio.wait_for(
                call_llm(config, messages), timeout=_timeout
            )
            return resp.content or ""
        except (LlmGatewayError, asyncio.TimeoutError, Exception) as exc:
            logger.warning("prospect_source.llm_call_failed", error=str(exc))
            return ""

    # ── Source config ──────────────────────────────────────────────────────

    async def list_configs(self, db: AsyncSession) -> list[SourceConfig]:
        result = await db.execute(select(SourceConfig))
        return list(result.scalars().all())

    async def get_config(self, db: AsyncSession, source: str) -> SourceConfig | None:
        result = await db.execute(
            select(SourceConfig).where(SourceConfig.source == source)
        )
        return result.scalar_one_or_none()

    async def create_config(self, db: AsyncSession, body: SourceConfigCreate) -> SourceConfig:
        data = body.model_dump()
        data["settings"] = json.dumps(data.get("settings", {}))
        item = SourceConfig(**data)
        db.add(item)
        await db.commit()
        item = await db.get(SourceConfig, item.id)
        return item

    async def update_config(
        self, db: AsyncSession, source: str, body: SourceConfigUpdate
    ) -> SourceConfig | None:
        item = await self.get_config(db, source)
        if item is None:
            return None
        data = body.model_dump(exclude_unset=True)
        if "settings" in data and data["settings"] is not None:
            data["settings"] = json.dumps(data["settings"])
        for key, value in data.items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(SourceConfig, item.id)
        return item

    async def delete_config(self, db: AsyncSession, source: str) -> bool:
        item = await self.get_config(db, source)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    # ── Prospect source records ────────────────────────────────────────────

    async def list_sources(
        self, db: AsyncSession, *, prospect_id: str | None = None
    ) -> list[ProspectSource]:
        stmt = select(ProspectSource)
        if prospect_id:
            stmt = stmt.where(ProspectSource.prospectId == prospect_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ── Natural-language search ────────────────────────────────────────────

    async def natural_language_search(
        self, db: AsyncSession, query: str, icp_profile_id: str | None, limit: int
    ) -> NaturalLanguageSearchResponse:
        # Use GlobalLlmConfig for NL→filter parsing
        raw = await self._call_llm(
            prompt=(
                f"Convert this prospect search request into filters: '{query}'. "
                "Return JSON only (no markdown): "
                '{"company":"","title":"","seniority":"","industry":"","location":""} '
                "Empty string for any unspecified field."
            ),
            system="You are a search query parser. Always respond with valid JSON only."
        )
        filters: dict[str, Any] = {}
        if raw:
            parsed = self._extract_json(raw)
            if isinstance(parsed, dict):
                filters = parsed

        stmt = select(Prospect).where(Prospect.deleted_at.is_(None)).limit(limit)
        if filters.get("company"):
            stmt = stmt.where(Prospect.company.ilike(f"%{filters['company']}%"))
        if filters.get("title"):
            stmt = stmt.where(Prospect.title.ilike(f"%{filters['title']}%"))
        if filters.get("seniority"):
            stmt = stmt.where(Prospect.seniority == filters["seniority"])

        result = await db.execute(stmt)
        prospects = [
            ProspectSearchHit(
                id=p.id,
                firstName=p.firstName,
                lastName=p.lastName,
                email=p.email,
                title=p.title,
                company=p.company,
            )
            for p in result.scalars().all()
        ]
        return NaturalLanguageSearchResponse(
            interpretedFilters=filters,
            prospects=prospects,
            count=len(prospects),
        )

    # ── Lookalike ──────────────────────────────────────────────────────────

    async def lookalike(
        self, db: AsyncSession, prospect_id: str, limit: int
    ) -> LookalikeResponse:
        seed_result = await db.execute(
            select(Prospect).where(Prospect.id == prospect_id)
        )
        seed = seed_result.scalar_one_or_none()
        if seed is None:
            return LookalikeResponse(seedProspectId=prospect_id, lookalikes=[], count=0)

        stmt = select(Prospect).where(
            Prospect.id != prospect_id,
            Prospect.deleted_at.is_(None),
        ).limit(limit)
        if seed.company:
            stmt = stmt.where(Prospect.company == seed.company)

        result = await db.execute(stmt)
        lookalikes = [
            LookalikeHit(
                id=p.id,
                firstName=p.firstName,
                lastName=p.lastName,
                title=p.title,
                company=p.company,
                similarityScore=0.85,
            )
            for p in result.scalars().all()
        ]
        return LookalikeResponse(
            seedProspectId=prospect_id,
            lookalikes=lookalikes,
            count=len(lookalikes),
        )

    # ── Ultimate profile ───────────────────────────────────────────────────

    async def ultimate_profile(
        self, db: AsyncSession, prospect_id: str
    ) -> UltimateProfileResponse:
        prospect_result = await db.execute(
            select(Prospect).where(Prospect.id == prospect_id)
        )
        prospect = prospect_result.scalar_one_or_none()
        if prospect is None:
            return UltimateProfileResponse(
                prospectId=prospect_id, profile={"error": "Prospect not found"}
            )

        # FIX: use GlobalLlmConfig + call_llm(), not get_llm_service().generate_json()
        raw = await self._call_llm(
            prompt=(
                f"Build an ultimate B2B sales profile for "
                f"{prospect.firstName} {prospect.lastName} "
                f"({prospect.title or 'unknown title'} at "
                f"{prospect.company or 'unknown company'}). "
                "Return valid JSON only (no markdown) with these keys: "
                "personalityTraits (list of strings), "
                "communicationStyle (string), "
                "decisionFactors (list of strings), "
                "likelyObjections (list of strings), "
                "recommendedApproach (string), "
                "icebreaker (string)."
            ),
            system=(
                "You are a B2B sales intelligence analyst. "
                "Always respond with valid JSON only — no markdown, no preamble."
            ),
        )

        profile: dict[str, Any] = {}
        if raw:
            parsed = self._extract_json(raw)
            if isinstance(parsed, dict):
                profile = parsed

        if not profile:
            # Fallback: return structured placeholder so UI doesn't show empty card
            profile = {
                "note": "LLM profile generation unavailable — check LLM config.",
                "prospectName": f"{prospect.firstName} {prospect.lastName}",
                "title": prospect.title or "",
                "company": prospect.company or "",
            }

        return UltimateProfileResponse(prospectId=prospect_id, profile=profile)

    # ── Prospect brief ─────────────────────────────────────────────────────

    async def brief(
        self, db: AsyncSession, prospect_id: str, call_type: str
    ) -> ProspectBriefResponse:
        prospect_result = await db.execute(
            select(Prospect).where(Prospect.id == prospect_id)
        )
        prospect = prospect_result.scalar_one_or_none()
        if prospect is None:
            return ProspectBriefResponse(
                prospectId=prospect_id,
                brief=f"[Brief unavailable — prospect {prospect_id} not found]",
            )

        # FIX: use GlobalLlmConfig + call_llm(), not get_llm_service().generate()
        brief_text = await self._call_llm(
            prompt=(
                f"Generate a {call_type} call brief for "
                f"{prospect.firstName} {prospect.lastName} "
                f"({prospect.title or 'unknown title'} at "
                f"{prospect.company or 'unknown company'}). "
                "Include: 1) a personalised icebreaker, "
                "2) 3 probing discovery questions, "
                "3) key pain points to probe, "
                "4) a closing next-step CTA. "
                "Format as plain text with clear section headings."
            ),
            system=(
                "You are an expert B2B sales coach writing call prep briefs. "
                "Be specific, concise, and actionable. "
                "Write in plain text — no JSON, no markdown fences."
            ),
        )

        if not brief_text:
            brief_text = (
                f"Brief unavailable — LLM config not set. "
                f"Prospect: {prospect.firstName} {prospect.lastName}, "
                f"{prospect.title} at {prospect.company}."
            )

        return ProspectBriefResponse(prospectId=prospect_id, brief=brief_text)