"""icp_service.py — IcpProfile CRUD + ICP suggestion + auto-discover.

LLM-dependent endpoints (suggest, auto-discover) call LlmService.call_llm
(provided by Fix-3); a graceful fallback returns a structured empty response
if the LLM gateway is not yet wired.
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect_models import IcpProfile, Prospect
from app.schemas.icp import (
    AutoDiscoverRequest,
    AutoDiscoverResponse,
    IcpCreate,
    IcpSuggestRequest,
    IcpSuggestResponse,
    IcpUpdate,
)

logger = structlog.get_logger(__name__)


class IcpService:
    """CRUD + LLM-backed suggestion for IcpProfile rows."""

    async def list_profiles(
        self, db: AsyncSession, *, limit: int = 50, offset: int = 0
    ) -> list[IcpProfile]:
        result = await db.execute(select(IcpProfile).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, icp_id: str) -> IcpProfile | None:
        result = await db.execute(
            select(IcpProfile).where(IcpProfile.id == icp_id)
        )
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, body: IcpCreate) -> IcpProfile:
        data = body.model_dump(exclude={"buyingSignals"})
        # Supply defaults for NOT NULL columns that may be missing
        if not data.get("persona"):
            data["persona"] = data.get("name", "Default persona")
        item = IcpProfile(**data)
        db.add(item)
        await db.commit()
        item = await db.get(IcpProfile, item.id)
        return item

    async def update(
        self, db: AsyncSession, icp_id: str, body: IcpUpdate
    ) -> IcpProfile | None:
        item = await self.get(db, icp_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(IcpProfile, item.id)
        return item

    async def delete(self, db: AsyncSession, icp_id: str) -> bool:
        item = await self.get(db, icp_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    # ── LLM-backed endpoints ────────────────────────────────────────────────

    async def suggest(
        self, db: AsyncSession, body: IcpSuggestRequest
    ) -> IcpSuggestResponse:
        """Ask the LLM to suggest an ICP for the given product/service."""
        config = await self._get_default_llm_config(db)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a B2B sales strategist. Suggest an Ideal Customer "
                    "Profile for the product below. Respond as JSON with keys: "
                    "name, persona, companyType, painPoints (array), valueProps "
                    "(array), topObjections (array)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Product/Service: {body.productOrService}\n"
                    f"Target Market: {body.targetMarket or 'unspecified'}\n"
                    f"Additional Context: {body.additionalContext or 'none'}"
                ),
            },
        ]
        raw = await self._call_llm_safe(config, messages)
        parsed = self._safe_json(raw)
        return IcpSuggestResponse(
            name=str(parsed.get("name", body.productOrService[:60])),
            persona=str(parsed.get("persona", "")),
            companyType=parsed.get("companyType"),
            painPoints=list(parsed.get("painPoints", []) or []),
            valueProps=list(parsed.get("valueProps", []) or []),
            topObjections=list(parsed.get("topObjections", []) or []),
            raw=raw,
        )

    async def auto_discover(
        self, db: AsyncSession, body: AutoDiscoverRequest
    ) -> AutoDiscoverResponse:
        """Derive an ICP from prospect data via the LLM."""
        config = await self._get_default_llm_config(db)
        prospect_blob = json.dumps(body.prospects[:50], default=str)
        messages = [
            {
                "role": "system",
                "content": (
                    "You analyze prospect lists and infer a shared Ideal "
                    "Customer Profile. Respond as JSON with keys: "
                    "suggestedPersona (string), commonAttributes (object), "
                    "fitScores (array of {prospectId, score})."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Prospects: {prospect_blob}\n"
                    f"Existing ICP id: {body.existingIcpId or 'none'}"
                ),
            },
        ]
        raw = await self._call_llm_safe(config, messages)
        parsed = self._safe_json(raw)
        return AutoDiscoverResponse(
            icpId=body.existingIcpId,
            suggestedPersona=str(parsed.get("suggestedPersona", "")),
            commonAttributes=parsed.get("commonAttributes", {}) or {},
            fitScores=list(parsed.get("fitScores", []) or []),
            raw=raw,
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _get_default_llm_config(self, db: AsyncSession) -> Any:
        try:
            from app.services.llm_service import get_default_llm_config

            return await get_default_llm_config(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("icp.default_llm_lookup_failed", error=str(exc))
            return None

    async def _call_llm_safe(
        self, config: Any, messages: list[dict[str, str]]
    ) -> str:
        try:
            from app.services.llm_service import call_llm as _call_llm

            if config is None:
                # Fallback path — no config; use LlmService.generate().
                from app.services.llm_service import LlmService

                joined = "\n\n".join(m["content"] for m in messages)
                return await LlmService().generate(prompt=joined)
            result = await _call_llm(config, messages)
            return str(getattr(result, "content", result))
        except Exception as exc:  # noqa: BLE001
            logger.warning("icp.llm_call_failed", error=str(exc))
            return ""

    @staticmethod
    def _safe_json(raw: str) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            # Try to extract the first {...} block.
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except (json.JSONDecodeError, ValueError):
                    return {}
            return {}


__all__ = ["IcpService"]
