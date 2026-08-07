"""competitor_service.py — Competitor radar CRUD."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect_models import Competitor
from app.schemas.competitors import CompetitorCreate, CompetitorUpdate


class CompetitorService:
    async def list(
        self, db: AsyncSession, *, prospect_id: str | None = None
    ) -> list[Competitor]:
        stmt = select(Competitor)
        if prospect_id:
            stmt = stmt.where(Competitor.prospectId == prospect_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, competitor_id: str) -> Competitor | None:
        result = await db.execute(
            select(Competitor).where(Competitor.id == competitor_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, body: CompetitorCreate
    ) -> Competitor:
        item = Competitor(**body.model_dump())
        db.add(item)
        await db.commit()
        item = await db.get(Competitor, item.id)
        return item

    async def update(
        self, db: AsyncSession, competitor_id: str, body: CompetitorUpdate
    ) -> Competitor | None:
        item = await self.get(db, competitor_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(Competitor, item.id)
        return item

    async def delete(self, db: AsyncSession, competitor_id: str) -> bool:
        item = await self.get(db, competitor_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True
