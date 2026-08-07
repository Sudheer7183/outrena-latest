"""content_ideas_service.py — ContentIdea CRUD + LLM generation."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase3_models import ContentIdea
from app.models.prospect_models import IcpProfile
from app.schemas.content_ideas import ContentIdeaCreate, ContentIdeaUpdate
from app.services.llm_service import get_llm_service


class ContentIdeaService:
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

    async def create(
        self, db: AsyncSession, body: ContentIdeaCreate
    ) -> ContentIdea:
        item = ContentIdea(**body.model_dump())
        db.add(item)
        await db.commit()
        item = await db.get(ContentIdea, item.id)
        return item

    async def update(
        self, db: AsyncSession, idea_id: str, body: ContentIdeaUpdate
    ) -> ContentIdea | None:
        item = await self.get(db, idea_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(ContentIdea, item.id)
        return item

    async def delete(self, db: AsyncSession, idea_id: str) -> bool:
        item = await self.get(db, idea_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def generate(
        self, db: AsyncSession, icp_profile_id: str, count: int = 5
    ) -> list[ContentIdea]:
        """LLM-generate N content ideas for an ICP."""
        icp_result = await db.execute(
            select(IcpProfile).where(IcpProfile.id == icp_profile_id)
        )
        icp = icp_result.scalar_one_or_none()
        if icp is None:
            return []
        llm = get_llm_service()
        prompt = (
            f"Generate {count} outreach content ideas for the ICP "
            f"'{icp.name}' (persona: {icp.persona}). "
            "Each idea: title, angle, body (50-100 words). "
            'Respond as JSON array: [{"title":"...","angle":"...","body":"..."}]'
        )
        raw = await llm.generate(prompt=prompt)
        try:
            ideas_data = json.loads(raw)
            if not isinstance(ideas_data, list):
                ideas_data = []
        except (json.JSONDecodeError, ValueError):
            ideas_data = []
        items: list[ContentIdea] = []
        for idea in ideas_data[:count]:
            if not isinstance(idea, dict):
                continue
            item = ContentIdea(
                icpProfileId=icp_profile_id,
                title=str(idea.get("title", "Untitled")),
                angle=str(idea.get("angle", "")) or None,
                body=str(idea.get("body", "")),
                status="draft",
            )
            db.add(item)
            items.append(item)
        await db.commit()
        for item in items:
            item = await db.get(ContentIdea, item.id)
        return items
