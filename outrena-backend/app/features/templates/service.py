"""template_service.py — EmailTemplate CRUD."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase3_models import EmailTemplate
from app.schemas.templates import EmailTemplateCreate, EmailTemplateUpdate


class EmailTemplateService:
    async def list(
        self,
        db: AsyncSession,
        *,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EmailTemplate]:
        stmt = select(EmailTemplate).offset(offset).limit(limit)
        if category:
            stmt = stmt.where(EmailTemplate.category == category)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, template_id: str) -> EmailTemplate | None:
        result = await db.execute(
            select(EmailTemplate).where(EmailTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, body: EmailTemplateCreate
    ) -> EmailTemplate:
        data = body.model_dump()
        data["variables"] = json.dumps(data.get("variables", []))
        item = EmailTemplate(**data)
        db.add(item)
        await db.commit()
        refreshed = await db.get(EmailTemplate, item.id)
        return refreshed  # type: ignore[return-value]

    async def update(
        self, db: AsyncSession, template_id: str, body: EmailTemplateUpdate
    ) -> EmailTemplate | None:
        item = await self.get(db, template_id)
        if item is None:
            return None
        data = body.model_dump(exclude_unset=True)
        if "variables" in data and data["variables"] is not None:
            data["variables"] = json.dumps(data["variables"])
        for key, value in data.items():
            setattr(item, key, value)
        await db.commit()
        refreshed = await db.get(EmailTemplate, item.id)
        return refreshed

    async def delete(self, db: AsyncSession, template_id: str) -> bool:
        item = await self.get(db, template_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True
