"""exclusion_rule_service.py — Prospect suppression list CRUD + bulk upsert."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_models import ExclusionRule
from app.schemas.exclusion_rules import (
    BulkExclusionRequest,
    BulkExclusionResponse,
    ExclusionRuleCreate,
    ExclusionRuleUpdate,
)


class ExclusionRuleService:
    async def list(
        self,
        db: AsyncSession,
        *,
        type_filter: str | None = None,
        active_only: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> list[ExclusionRule]:
        stmt = select(ExclusionRule).offset(offset).limit(limit)
        if type_filter:
            stmt = stmt.where(ExclusionRule.type == type_filter)
        if active_only:
            stmt = stmt.where(ExclusionRule.isActive.is_(True))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, rule_id: str) -> ExclusionRule | None:
        result = await db.execute(
            select(ExclusionRule).where(ExclusionRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, body: ExclusionRuleCreate
    ) -> ExclusionRule:
        rule = ExclusionRule(**body.model_dump(exclude={"operator"}))
        db.add(rule)
        await db.commit()
        rule = await db.get(ExclusionRule, rule.id)
        return rule

    async def update(
        self, db: AsyncSession, rule_id: str, body: ExclusionRuleUpdate
    ) -> ExclusionRule | None:
        rule = await self.get(db, rule_id)
        if rule is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(rule, key, value)
        await db.commit()
        rule = await db.get(ExclusionRule, rule.id)
        return rule

    async def delete(self, db: AsyncSession, rule_id: str) -> bool:
        rule = await self.get(db, rule_id)
        if rule is None:
            return False
        await db.delete(rule)
        await db.commit()
        return True

    async def bulk_upsert(
        self, db: AsyncSession, body: BulkExclusionRequest
    ) -> BulkExclusionResponse:
        """Upsert many rules; skip duplicates (type+value already exists)."""
        inserted = 0
        skipped = 0
        for item in body.rules:
            existing = await db.execute(
                select(ExclusionRule).where(
                    ExclusionRule.type == item.type,
                    ExclusionRule.value == item.value,
                )
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue
            db.add(ExclusionRule(**item.model_dump(exclude={"operator"})))
            inserted += 1
        await db.commit()
        return BulkExclusionResponse(inserted=inserted, skipped=skipped)

    async def check_prospect(
        self, db: AsyncSession, email: str, domain: str | None, company: str | None
    ) -> list[ExclusionRule]:
        """Return all active rules that would suppress this prospect."""
        stmt = select(ExclusionRule).where(ExclusionRule.isActive.is_(True))
        result = await db.execute(stmt)
        rules = list(result.scalars().all())
        matches: list[ExclusionRule] = []
        for rule in rules:
            if rule.type == "email" and email and rule.value.lower() == email.lower():
                matches.append(rule)
            elif rule.type == "domain" and domain and rule.value.lower() == domain.lower():
                matches.append(rule)
            elif rule.type == "company" and company and rule.value.lower() in (company or "").lower():
                matches.append(rule)
            elif rule.type == "dnc" and email and rule.value.lower() == email.lower():
                matches.append(rule)
        return matches
