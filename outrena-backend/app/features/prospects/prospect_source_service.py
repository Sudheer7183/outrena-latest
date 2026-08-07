"""
prospect_source_service.py — Source CRUD + NL search + lookalike + profile + brief.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
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
from app.services.llm_service import get_llm_service


class ProspectSourceService:
    # ── Source config ──────────────────────────────────────────────────────
    async def list_configs(self, db: AsyncSession) -> list[SourceConfig]:
        result = await db.execute(select(SourceConfig))
        return list(result.scalars().all())

    async def get_config(
        self, db: AsyncSession, source: str
    ) -> SourceConfig | None:
        result = await db.execute(
            select(SourceConfig).where(SourceConfig.source == source)
        )
        return result.scalar_one_or_none()

    async def create_config(
        self, db: AsyncSession, body: SourceConfigCreate
    ) -> SourceConfig:
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
        llm = get_llm_service()
        filters = await llm.generate_json(
            prompt=(
                f"Convert this prospect search request into filters: '{query}'. "
                "Return JSON: {company, title, seniority, industry, location}. "
                "Empty string for any unspecified field."
            )
        )
        stmt = select(Prospect).limit(limit)
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
        stmt = select(Prospect).where(Prospect.id != prospect_id).limit(limit)
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
                similarityScore=0.85,  # Phase 4 will compute real score
            )
            for p in result.scalars().all()
        ]
        return LookalikeResponse(
            seedProspectId=prospect_id, lookalikes=lookalikes, count=len(lookalikes)
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
        llm = get_llm_service()
        profile = await llm.generate_json(
            prompt=(
                f"Build an ultimate profile for {prospect.firstName} "
                f"{prospect.lastName} ({prospect.title} at {prospect.company}). "
                "Include: personalityTraits, communicationStyle, decisionFactors, "
                "likelyObjections, recommendedApproach. Respond as JSON."
            )
        )
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
        llm = get_llm_service()
        brief_text = await llm.generate(
            prompt=(
                f"Generate a {call_type} call brief for "
                f"{prospect.firstName} {prospect.lastName} "
                f"({prospect.title} at {prospect.company}). "
                "Include icebreaker, 3 probing questions, and a closing CTA."
            )
        )
        return ProspectBriefResponse(prospectId=prospect_id, brief=brief_text)
