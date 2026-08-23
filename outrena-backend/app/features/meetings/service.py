# """meeting_prep_service.py — Meeting-prep brief CRUD + LLM generation.

# FIX: _generate_brief() now uses GlobalLlmConfig (public.global_llm_config)
#      — the actual table written by the LLM Config UI — instead of the
#      tenant-schema LlmConfig table (which is empty for most tenants).

#      Pattern mirrors LlmConfigService.test_llm() exactly:
#        1. Open a public-schema session to query GlobalLlmConfig
#        2. Decrypt the API key with decrypt_at_rest()
#        3. Build a SimpleNamespace legacy_config shim
#        4. Call call_llm(legacy_config, messages)
# """
# from __future__ import annotations

# from types import SimpleNamespace

# import structlog
# from sqlalchemy import select, text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.prospect_models import MeetingPrep, Prospect
# from app.schemas.meeting_prep import MeetingPrepCreate
# from app.services.llm_service import call_llm, LlmGatewayError

# logger = structlog.get_logger(__name__)


# class MeetingPrepService:
#     async def list_for_prospect(
#         self, db: AsyncSession, prospect_id: str
#     ) -> list[MeetingPrep]:
#         result = await db.execute(
#             select(MeetingPrep)
#             .where(MeetingPrep.prospectId == prospect_id)
#             .order_by(MeetingPrep.createdAt.desc())
#         )
#         return list(result.scalars().all())

#     async def list_all(self, db: AsyncSession) -> list[MeetingPrep]:
#         """BUG-21 FIX: Return all meeting preps when no prospect_id filter."""
#         result = await db.execute(
#             select(MeetingPrep).order_by(MeetingPrep.createdAt.desc()).limit(100)
#         )
#         return list(result.scalars().all())

#     async def get(self, db: AsyncSession, brief_id: str) -> MeetingPrep | None:
#         result = await db.execute(
#             select(MeetingPrep).where(MeetingPrep.id == brief_id)
#         )
#         return result.scalar_one_or_none()

#     async def create(
#         self, db: AsyncSession, body: MeetingPrepCreate
#     ) -> MeetingPrep:
#         brief = body.brief
#         if brief is None:
#             brief = await self._generate_brief(db, body.prospectId, body.callType)
#         item = MeetingPrep(
#             prospectId=body.prospectId,
#             callType=body.callType,
#             brief=brief,
#         )
#         db.add(item)
#         await db.commit()
#         item = await db.get(MeetingPrep, item.id)
#         return item

#     async def delete(self, db: AsyncSession, brief_id: str) -> bool:
#         item = await self.get(db, brief_id)
#         if item is None:
#             return False
#         await db.delete(item)
#         await db.commit()
#         return True

#     async def generate(
#         self, db: AsyncSession, prospect_id: str, call_type: str
#     ) -> MeetingPrep:
#         """BUG-21 FIX: Validate prospect_id exists before INSERT to avoid FK violation."""
#         from fastapi import HTTPException
#         from sqlalchemy import select as _select

#         prospect_check = await db.execute(
#             _select(Prospect).where(Prospect.id == prospect_id)
#         )
#         if prospect_check.scalar_one_or_none() is None:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"Prospect '{prospect_id}' not found. Please select a valid prospect.",
#             )
#         brief_text = await self._generate_brief(db, prospect_id, call_type)
#         item = MeetingPrep(
#             prospectId=prospect_id, callType=call_type, brief=brief_text
#         )
#         db.add(item)
#         await db.commit()
#         item = await db.get(MeetingPrep, item.id)
#         return item

#     async def _generate_brief(
#         self, db: AsyncSession, prospect_id: str, call_type: str
#     ) -> str:
#         """Generate a meeting prep brief using the platform GlobalLlmConfig.

#         Uses the same pattern as LlmConfigService.test_llm():
#           - Query public.global_llm_config for the platform default
#           - Decrypt the API key
#           - Build a SimpleNamespace shim accepted by call_llm()
#           - Prompt for JSON output matching the frontend's ParsedBrief shape
#         """
#         # ── 1. Fetch prospect from the tenant-schema session (db) ──────────
#         prospect_result = await db.execute(
#             select(Prospect).where(Prospect.id == prospect_id)
#         )
#         prospect = prospect_result.scalar_one_or_none()
#         if prospect is None:
#             return f"[Meeting prep unavailable — prospect {prospect_id} not found]"

#         # ── 2. Fetch GlobalLlmConfig from public schema ────────────────────
#         # We CANNOT reuse `db` here — it has search_path set to the tenant
#         # schema, and GlobalLlmConfig lives in public.global_llm_config.
#         # Open a fresh public-schema session, exactly like the LLM Config
#         # router does via get_db_public().
#         from app.core.database import AsyncSessionLocal
#         from app.models.global_llm_config import GlobalLlmConfig
#         from app.services.secret_service import decrypt_at_rest

#         global_config = None
#         api_key: str | None = None

#         try:
#             async with AsyncSessionLocal() as pub_db:
#                 await pub_db.execute(text('SET search_path TO "public"'))
#                 # Try is_default=True first; fall back to any active config.
#                 result = await pub_db.execute(
#                     select(GlobalLlmConfig)
#                     .where(GlobalLlmConfig.is_active.is_(True))
#                     .where(GlobalLlmConfig.is_default.is_(True))
#                     .limit(1)
#                 )
#                 global_config = result.scalar_one_or_none()

#                 if global_config is None:
#                     result = await pub_db.execute(
#                         select(GlobalLlmConfig)
#                         .where(GlobalLlmConfig.is_active.is_(True))
#                         .order_by(GlobalLlmConfig.id)
#                         .limit(1)
#                     )
#                     global_config = result.scalar_one_or_none()

#                 if global_config is None:
#                     logger.warning("meeting_prep.no_global_llm_config")
#                     return "[Meeting prep unavailable — no active LLM config found. Configure one in LLM Models.]"

#                 # Decrypt inside the session context while the object is live.
#                 try:
#                     api_key = decrypt_at_rest(global_config.api_key_encrypted)
#                 except Exception as exc:  # noqa: BLE001
#                     logger.warning("meeting_prep.decrypt_failed", error=str(exc))
#                     return f"[Meeting prep unavailable — API key decryption failed: {exc}]"

#                 # Build the SimpleNamespace shim (same pattern as test_llm).
#                 legacy_config = SimpleNamespace(
#                     provider=global_config.provider,
#                     name=global_config.display_name,
#                     modelId=global_config.model_name,
#                     apiKey=api_key,
#                     baseUrl=global_config.base_url,
#                     isActive=global_config.is_active,
#                     isDefault=global_config.is_default,
#                     settings="{}",
#                     global_llm_config_id=None,
#                 )

#         except Exception as exc:  # noqa: BLE001
#             logger.warning("meeting_prep.global_config_fetch_failed", error=str(exc))
#             return f"[Meeting prep unavailable — could not load LLM config: {exc}]"

#         # ── 3. Build prompt requesting JSON matching ParsedBrief shape ──────
#         prospect_name = f"{prospect.firstName} {prospect.lastName}"
#         prospect_context = (
#             f"{prospect.title or 'unknown title'} at {prospect.company or 'unknown company'}"
#         )

#         messages = [
#             {
#                 "role": "system",
#                 "content": (
#                     "You are an expert B2B sales coach generating meeting prep briefs. "
#                     "Always respond with valid JSON only — no markdown fences, "
#                     "no preamble, no explanation. Raw JSON object only."
#                 ),
#             },
#             {
#                 "role": "user",
#                 "content": (
#                     f"Generate a {call_type} meeting prep brief for prospect "
#                     f"{prospect_name} ({prospect_context}).\n\n"
#                     "Return a JSON object with EXACTLY these keys:\n"
#                     "- researchSummary: string (2-3 sentences about their company/role)\n"
#                     "- approach: string (recommended sales approach for this call type)\n"
#                     "- agenda: array of objects with {time, item, detail} "
#                     "(3-5 time-blocked agenda items, e.g. time: '0:00-5:00')\n"
#                     "- talkingPoints: array of strings (3-5 key talking points)\n"
#                     "- objections: array of {objection, response} objects (2-3 common objections)\n"
#                     "- questions: array of strings (3-5 discovery questions)\n"
#                     "- nextSteps: array of strings (2-3 proposed next steps)\n\n"
#                     "No markdown. No explanation. Raw JSON only."
#                 ),
#             },
#         ]

#         # ── 4. Call the LLM via the 13-provider gateway ────────────────────
#         try:
#             response = await call_llm(legacy_config, messages)
#             content = response.content.strip()
#             # Strip accidental markdown fences if the LLM adds them despite instructions.
#             if content.startswith("```"):
#                 lines = content.splitlines()
#                 content = "\n".join(
#                     line for line in lines if not line.startswith("```")
#                 ).strip()
#             return content
#         except LlmGatewayError as exc:
#             logger.warning("meeting_prep.llm_call_failed", error=str(exc))
#             return f"[LLM error: {exc}]"
#         except Exception as exc:  # noqa: BLE001
#             logger.warning("meeting_prep.llm_unexpected_error", error=str(exc))
#             return f"[Unexpected LLM error: {exc}]"

"""meeting_prep_service.py — Meeting-prep brief CRUD + LLM generation.

FIX: _generate_brief() now uses get_default_llm_config(db) which applies
     the correct 3-tier fallback:
       Tier 1 — tenant LlmConfig (isDefault=True, isActive=True) — decrypted
       Tier 2 — any active tenant LlmConfig row — decrypted
       Tier 3 — public.global_llm_config (platform-managed)

     Previously this service ONLY queried public.global_llm_config, which is
     empty when the tenant configured their LLM via the tenant LLM Models UI
     (which writes to the tenant schema, not the public schema). This caused
     a 404/unavailable error for all tenants using tenant-managed LLM configs.
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect_models import MeetingPrep, Prospect
from app.schemas.meeting_prep import MeetingPrepCreate
from app.services.llm_service import call_llm, get_default_llm_config, LlmGatewayError

logger = structlog.get_logger(__name__)


class MeetingPrepService:
    async def list_for_prospect(
        self, db: AsyncSession, prospect_id: str
    ) -> list[MeetingPrep]:
        result = await db.execute(
            select(MeetingPrep)
            .where(MeetingPrep.prospectId == prospect_id)
            .order_by(MeetingPrep.createdAt.desc())
        )
        return list(result.scalars().all())

    async def list_all(self, db: AsyncSession) -> list[MeetingPrep]:
        """BUG-21 FIX: Return all meeting preps when no prospect_id filter."""
        result = await db.execute(
            select(MeetingPrep).order_by(MeetingPrep.createdAt.desc()).limit(100)
        )
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, brief_id: str) -> MeetingPrep | None:
        result = await db.execute(
            select(MeetingPrep).where(MeetingPrep.id == brief_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, body: MeetingPrepCreate
    ) -> MeetingPrep:
        brief = body.brief
        if brief is None:
            brief = await self._generate_brief(db, body.prospectId, body.callType)
        item = MeetingPrep(
            prospectId=body.prospectId,
            callType=body.callType,
            brief=brief,
        )
        db.add(item)
        await db.commit()
        item = await db.get(MeetingPrep, item.id)
        return item

    async def delete(self, db: AsyncSession, brief_id: str) -> bool:
        item = await self.get(db, brief_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def generate(
        self, db: AsyncSession, prospect_id: str, call_type: str
    ) -> MeetingPrep:
        """BUG-21 FIX: Validate prospect_id exists before INSERT to avoid FK violation."""
        from fastapi import HTTPException
        from sqlalchemy import select as _select

        prospect_check = await db.execute(
            _select(Prospect).where(Prospect.id == prospect_id)
        )
        if prospect_check.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=404,
                detail=f"Prospect '{prospect_id}' not found. Please select a valid prospect.",
            )
        brief_text = await self._generate_brief(db, prospect_id, call_type)
        item = MeetingPrep(
            prospectId=prospect_id, callType=call_type, brief=brief_text
        )
        db.add(item)
        await db.commit()
        item = await db.get(MeetingPrep, item.id)
        return item

    async def _generate_brief(
        self, db: AsyncSession, prospect_id: str, call_type: str
    ) -> str:
        """Generate a meeting prep brief using the tenant's configured LLM.

        Uses get_default_llm_config(db) which applies the correct 3-tier
        fallback: tenant default → any tenant active → public global config.
        The key is already decrypted by get_default_llm_config so call_llm()
        receives the plaintext API key directly.
        """
        # ── 1. Fetch prospect ─────────────────────────────────────────────
        prospect_result = await db.execute(
            select(Prospect).where(Prospect.id == prospect_id)
        )
        prospect = prospect_result.scalar_one_or_none()
        if prospect is None:
            return f"[Meeting prep unavailable — prospect {prospect_id} not found]"

        # ── 2. Resolve LLM config via the standard 3-tier fallback ────────
        llm_config = await get_default_llm_config(db)
        if llm_config is None:
            logger.warning("meeting_prep.no_llm_config", prospect_id=prospect_id)
            return (
                "[Meeting prep unavailable — no active LLM config found. "
                "Configure one in Settings → LLM Models.]"
            )

        # ── 3. Build prompt requesting JSON matching ParsedBrief shape ─────
        prospect_name = f"{prospect.firstName} {prospect.lastName}"
        prospect_context = (
            f"{prospect.title or 'unknown title'} at {prospect.company or 'unknown company'}"
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert B2B sales coach generating meeting prep briefs. "
                    "Always respond with valid JSON only — no markdown fences, "
                    "no preamble, no explanation. Raw JSON object only."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a {call_type} meeting prep brief for prospect "
                    f"{prospect_name} ({prospect_context}).\n\n"
                    "Return a JSON object with EXACTLY these keys:\n"
                    "- researchSummary: string (2-3 sentences about their company/role)\n"
                    "- approach: string (recommended sales approach for this call type)\n"
                    "- agenda: array of objects with {time, item, detail} "
                    "(3-5 time-blocked agenda items, e.g. time: '0:00-5:00')\n"
                    "- talkingPoints: array of strings (3-5 key talking points)\n"
                    "- objections: array of {objection, response} objects (2-3 common objections)\n"
                    "- questions: array of strings (3-5 discovery questions)\n"
                    "- nextSteps: array of strings (2-3 proposed next steps)\n\n"
                    "No markdown. No explanation. Raw JSON only."
                ),
            },
        ]

        # ── 4. Call the LLM via the 13-provider gateway ───────────────────
        try:
            response = await call_llm(llm_config, messages)
            content = response.content.strip()
            # Strip accidental markdown fences if the LLM adds them despite instructions.
            if content.startswith("```"):
                lines = content.splitlines()
                content = "\n".join(
                    line for line in lines if not line.startswith("```")
                ).strip()
            return content
        except LlmGatewayError as exc:
            logger.warning("meeting_prep.llm_call_failed", error=str(exc))
            return f"[LLM error: {exc}]"
        except Exception as exc:  # noqa: BLE001
            logger.warning("meeting_prep.llm_unexpected_error", error=str(exc))
            return f"[Unexpected LLM error: {exc}]"


__all__ = ["MeetingPrepService"]