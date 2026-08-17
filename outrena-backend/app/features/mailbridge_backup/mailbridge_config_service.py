"""mailbridge_config_service.py — MailBridgeConfig CRUD (config side only)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_models import MailBridgeConfig
from app.schemas.mailbridge import (
    MailBridgeConfigCreate,
    MailBridgeConfigUpdate,
)


class MailBridgeConfigService:
    async def list(self, db: AsyncSession) -> list[MailBridgeConfig]:
        result = await db.execute(select(MailBridgeConfig))
        return list(result.scalars().all())

    async def get(
        self, db: AsyncSession, config_id: str
    ) -> MailBridgeConfig | None:
        result = await db.execute(
            select(MailBridgeConfig).where(MailBridgeConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, body: MailBridgeConfigCreate
    ) -> MailBridgeConfig:
        item = MailBridgeConfig(**body.model_dump())
        db.add(item)
        await db.commit()
        item = await db.get(MailBridgeConfig, item.id)
        return item

    async def update(
        self, db: AsyncSession, config_id: str, body: MailBridgeConfigUpdate
    ) -> MailBridgeConfig | None:
        item = await self.get(db, config_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(MailBridgeConfig, item.id)
        return item

    async def delete(self, db: AsyncSession, config_id: str) -> bool:
        item = await self.get(db, config_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True
