"""collateral_service.py — Collateral library CRUD + campaign link management."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import CampaignCollateralLink, Collateral
from app.schemas.collaterals import (
    CampaignCollateralLinkCreate,
    CollateralCreate,
    CollateralUpdate,
)


class CollateralService:
    async def list(
        self, db: AsyncSession, *, limit: int = 50, offset: int = 0
    ) -> list[Collateral]:
        result = await db.execute(select(Collateral).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, collateral_id: str) -> Collateral | None:
        result = await db.execute(
            select(Collateral).where(Collateral.id == collateral_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, body: CollateralCreate
    ) -> Collateral:
        item = Collateral(**body.model_dump())
        db.add(item)
        await db.commit()
        item = await db.get(Collateral, item.id)
        return item

    async def update(
        self, db: AsyncSession, collateral_id: str, body: CollateralUpdate
    ) -> Collateral | None:
        item = await self.get(db, collateral_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(Collateral, item.id)
        return item

    async def delete(self, db: AsyncSession, collateral_id: str) -> bool:
        item = await self.get(db, collateral_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def link_to_campaign(
        self, db: AsyncSession, body: CampaignCollateralLinkCreate
    ) -> CampaignCollateralLink:
        link = CampaignCollateralLink(**body.model_dump())
        db.add(link)
        await db.commit()
        link = await db.get(CampaignCollateralLink, link.id)
        return link

    async def unlink(self, db: AsyncSession, link_id: str) -> bool:
        result = await db.execute(
            select(CampaignCollateralLink).where(
                CampaignCollateralLink.id == link_id
            )
        )
        link = result.scalar_one_or_none()
        if link is None:
            return False
        await db.delete(link)
        await db.commit()
        return True
