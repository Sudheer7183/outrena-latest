"""
optimization_rule_service.py — Auto-trigger rule CRUD + evaluation engine.

The evaluate() method runs every active rule against the current campaign
metrics and fires actions (pause / notify / adjust_send_volume) when
thresholds are breached.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import Campaign, Sequence
from app.models.phase3_models import OptimizationAction, OptimizationRule
from app.schemas.optimization_rules import (
    OptimizationEvaluateResponse,
    OptimizationRuleCreate,
    OptimizationRuleUpdate,
)


class OptimizationRuleService:
    async def list_rules(
        self,
        db: AsyncSession,
        *,
        active_only: bool = False,
        campaign_id: str | None = None,
    ) -> list[OptimizationRule]:
        stmt = select(OptimizationRule)
        if active_only:
            stmt = stmt.where(OptimizationRule.isActive.is_(True))
        if campaign_id:
            stmt = stmt.where(OptimizationRule.campaignId == campaign_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_rule(
        self, db: AsyncSession, rule_id: str
    ) -> OptimizationRule | None:
        # Try PK lookup first; fall back to name (slug-lookup pattern)
        result = await db.execute(
            select(OptimizationRule).where(OptimizationRule.id == rule_id)
        )
        item = result.scalar_one_or_none()
        if item is not None:
            return item
        result = await db.execute(
            select(OptimizationRule).where(OptimizationRule.name == rule_id)
        )
        return result.scalar_one_or_none()

    async def create_rule(
        self, db: AsyncSession, body: OptimizationRuleCreate
    ) -> OptimizationRule:
        rule = OptimizationRule(**body.model_dump())
        db.add(rule)
        await db.commit()
        rule = await db.get(OptimizationRule, rule.id)
        return rule

    async def update_rule(
        self, db: AsyncSession, rule_id: str, body: OptimizationRuleUpdate
    ) -> OptimizationRule | None:
        rule = await self.get_rule(db, rule_id)
        if rule is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(rule, key, value)
        await db.commit()
        rule = await db.get(OptimizationRule, rule.id)
        return rule

    async def delete_rule(self, db: AsyncSession, rule_id: str) -> bool:
        rule = await self.get_rule(db, rule_id)
        if rule is None:
            return False
        await db.delete(rule)
        await db.commit()
        return True

    async def list_actions(
        self,
        db: AsyncSession,
        *,
        rule_id: str | None = None,
        limit: int = 50,
    ) -> list[OptimizationAction]:
        stmt = select(OptimizationAction).limit(limit)
        if rule_id:
            stmt = stmt.where(OptimizationAction.ruleId == rule_id)
        stmt = stmt.order_by(OptimizationAction.executedAt.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def evaluate(self, db: AsyncSession) -> OptimizationEvaluateResponse:
        """Run every active rule once. Returns triggered actions + skipped count."""
        rules = await self.list_rules(db, active_only=True)
        triggered: list[OptimizationAction] = []
        skipped = 0
        for rule in rules:
            metric_value = await self._resolve_metric(db, rule)
            if metric_value is None:
                skipped += 1
                continue
            if self._breaches(metric_value, rule.operator, rule.threshold):
                action = OptimizationAction(
                    ruleId=rule.id,
                    campaignId=rule.campaignId,
                    metric=rule.metric,
                    observedValue=metric_value,
                    threshold=rule.threshold,
                    action=rule.action,
                    result=self._apply_action(rule),
                )
                db.add(action)
                triggered.append(action)
                rule.lastEvaluatedAt = datetime.now(timezone.utc)
            else:
                skipped += 1
        await db.commit()
        for a in triggered:
            a = await db.get(OptimizationAction, a.id)
        return OptimizationEvaluateResponse(triggered=triggered, skipped=skipped)

    async def _resolve_metric(
        self, db: AsyncSession, rule: OptimizationRule
    ) -> float | None:
        """Aggregate the current metric value for the rule's campaign.

        Task 3-a / FIX 1: previously this queried the latest ``CampaignMetric``
        row for the campaign — but that table is never written to, so every
        rule evaluation silently returned ``None`` and skipped. Now we
        aggregate directly from the ``Sequence`` table (the source of truth
        for send/open/reply/bounce timestamps).

        Returns ``None`` only when the campaign has zero sent sequences
        (no signal yet) — preserving the prior "skip when no data" contract.
        """
        if not rule.campaignId:
            return None
        # Aggregate send/open/reply/bounce counts from Sequence rows
        # linked to this campaign that have been sent (sentAt IS NOT NULL).
        result = await db.execute(
            select(
                func.count(Sequence.id).label("total_sent"),
                func.count(Sequence.openedAt).label("total_opened"),
                func.count(Sequence.repliedAt).label("total_replied"),
                func.count(Sequence.bouncedAt).label("total_bounced"),
            ).where(
                Sequence.campaignId == rule.campaignId,
                Sequence.sentAt.is_not(None),
            )
        )
        row = result.one()
        total_sent = int(row.total_sent or 0)
        total_opened = int(row.total_opened or 0)
        total_replied = int(row.total_replied or 0)
        total_bounced = int(row.total_bounced or 0)
        if total_sent == 0:
            # No sends yet → no signal → skip the rule (preserve prior
            # `metric is None` contract).
            return None
        open_rate = (total_opened / total_sent) if total_sent else 0.0
        reply_rate = (total_replied / total_sent) if total_sent else 0.0
        bounce_rate = (total_bounced / total_sent) if total_sent else 0.0
        attr_map = {
            "bounceRate": bounce_rate,
            "openRate": open_rate,
            "replyRate": reply_rate,
            "totalSent": float(total_sent),
            "totalBounced": float(total_bounced),
        }
        return attr_map.get(rule.metric)

    @staticmethod
    def _breaches(value: float, operator: str, threshold: float) -> bool:
        ops = {
            "gt": value > threshold,
            "lt": value < threshold,
            "gte": value >= threshold,
            "lte": value <= threshold,
            "eq": abs(value - threshold) < 1e-9,
        }
        return bool(ops.get(operator, False))

    @staticmethod
    def _apply_action(rule: OptimizationRule) -> str:
        """Stub action application — Phase 4 will mutate the campaign/sequence."""
        return f"Action '{rule.action}' queued for campaign {rule.campaignId or 'all'}."
