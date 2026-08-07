"""meeting_prep_service.py — Meeting-prep brief CRUD + LLM generation."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect_models import MeetingPrep, Prospect
from app.schemas.meeting_prep import MeetingPrepCreate
from app.services.llm_service import get_llm_service


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
        prospect_result = await db.execute(
            select(Prospect).where(Prospect.id == prospect_id)
        )
        prospect = prospect_result.scalar_one_or_none()
        if prospect is None:
            return f"[Meeting prep unavailable — prospect {prospect_id} not found]"
        llm = get_llm_service()
        prompt = (
            f"Generate a {call_type} meeting prep brief for prospect "
            f"{prospect.firstName} {prospect.lastName} "
            f"({prospect.title or 'title unknown'} at {prospect.company or 'company unknown'}). "
            f"Include: icebreaker, key pain points to probe, suggested questions, "
            f"and a closing CTA. Keep under 300 words."
        )
        return await llm.generate(prompt=prompt)
