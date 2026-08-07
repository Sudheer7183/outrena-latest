"""deal_service.py — Deal CRUD + AI deal-suggest + Deal Health computation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import Deal
from app.schemas.deals import  (
    DealCreate,
    DealHealthResponse,
    DealSuggestResponse,
    DealUpdate,
    KanbanBoardResponse,
    DealResponse,
)
from app.services.llm_service import get_llm_service


class DealService:
    async def list(
        self,
        db: AsyncSession,
        *,
        stage: str | None = None,
        prospect_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Deal]:
        stmt = select(Deal).offset(offset).limit(limit)
        if stage:
            stmt = stmt.where(Deal.stage == stage)
        if prospect_id:
            stmt = stmt.where(Deal.prospectId == prospect_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, deal_id: str) -> Deal | None:
        result = await db.execute(select(Deal).where(Deal.id == deal_id))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, body: DealCreate) -> Deal:
        deal = Deal(**body.model_dump())
        db.add(deal)
        await db.commit()
        deal = await db.get(Deal, deal.id)
        return deal

    async def update(
        self, db: AsyncSession, deal_id: str, body: DealUpdate
    ) -> Deal | None:
        deal = await self.get(db, deal_id)
        if deal is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(deal, key, value)
        await db.commit()
        deal = await db.get(Deal, deal.id)
        return deal

    async def delete(self, db: AsyncSession, deal_id: str) -> bool:
        deal = await self.get(db, deal_id)
        if deal is None:
            return False
        await db.delete(deal)
        await db.commit()
        return True

    async def kanban(self, db: AsyncSession) -> KanbanBoardResponse:
        """BUG-24 FIX: Return stages as list[KanbanStageResponse] (frontend expects array)."""
        from app.schemas.deals import KanbanStageResponse
        result = await db.execute(select(Deal))
        deals = list(result.scalars().all())
        # Group by stage preserving STAGE_ORDER
        STAGE_ORDER = ["qualified", "proposal", "negotiation", "closed_won", "closed_lost"]
        stage_map: dict[str, list] = {s: [] for s in STAGE_ORDER}
        for d in deals:
            stage_map.setdefault(d.stage, []).append(d)
        # Ensure all canonical stages are present even if empty
        stage_list = [
            KanbanStageResponse(
                id=stage_id,
                name=stage_id.replace("_", " ").title(),
                deals=[DealResponse.model_validate(d) for d in stage_map.get(stage_id, [])],
            )
            for stage_id in STAGE_ORDER
        ]
        return KanbanBoardResponse(stages=stage_list)

    async def compute_health(
        self, db: AsyncSession, deal_id: str
    ) -> DealHealthResponse | None:
        """Compute 0-100 health score for a deal with per-signal breakdown (FR-E8-003)."""
        from app.schemas.deals import DealResponse, DealHealthSignal
        deal = await self.get(db, deal_id)
        if deal is None:
            return None
        now = datetime.now(timezone.utc)
        score, signals, reason = self._score_deal(deal, now)
        # Derive traffic-light from numeric score
        if score >= 70:
            status = "green"
        elif score >= 40:
            status = "yellow"
        else:
            status = "red"
        deal.healthStatus = status
        deal.healthReason = reason
        deal.healthCheckedAt = now
        await db.commit()
        return DealHealthResponse(
            dealId=deal_id,
            score=score,
            healthStatus=status,
            healthReason=reason,
            signals=signals,
            checkedAt=now,
        )

    @staticmethod
    def _score_deal(deal: Deal, now: datetime) -> tuple[int, list, str]:
        """
        Compute a 0-100 health score from four weighted factors (FR-E8-003):
          - Close date proximity  (25 pts)
          - Stage velocity        (25 pts)
          - Activity recency      (25 pts)
          - Amount set            (25 pts)
        Returns (score, signals, summary_reason).
        """
        from app.schemas.deals import DealResponse, DealHealthSignal

        signals = []
        score = 0

        # Closed deals are always full score
        if hasattr(deal, "stage") and deal.stage in ("closed_won", "closed_lost"):
            return 100, [
                DealHealthSignal(type="stage", weight=100, description=f"Deal is {deal.stage}.", passing=True)
            ], f"Deal is {deal.stage}."

        # 1. Close-date proximity (25 pts)
        close_pts = 0
        close_desc = "No expected close date set."
        close_passing = False
        if hasattr(deal, "expectedClose") and deal.expectedClose:
            days_left = (deal.expectedClose - now).days
            if days_left < 0:
                close_pts = 0
                close_desc = f"Past expected close by {abs(days_left)} days."
            elif days_left <= 7:
                close_pts = 10
                close_desc = f"Expected close in {days_left} day(s) — urgent."
                close_passing = True
            elif days_left <= 30:
                close_pts = 20
                close_desc = f"Expected close in {days_left} days."
                close_passing = True
            else:
                close_pts = 25
                close_desc = f"Expected close in {days_left} days — on track."
                close_passing = True
        signals.append(DealHealthSignal(type="close_date", weight=close_pts, description=close_desc, passing=close_passing))
        score += close_pts

        # 2. Stage velocity (25 pts) — penalise if in same stage too long
        stage_pts = 25
        stage_desc = "Stage progression is healthy."
        stage_passing = True
        if hasattr(deal, "updatedAt") and deal.updatedAt:
            days_since_update = (now - deal.updatedAt.replace(tzinfo=now.tzinfo) if deal.updatedAt.tzinfo is None else now - deal.updatedAt).days
            if days_since_update > 30:
                stage_pts = 5
                stage_desc = f"No stage movement in {days_since_update} days."
                stage_passing = False
            elif days_since_update > 14:
                stage_pts = 15
                stage_desc = f"No stage movement in {days_since_update} days — may be stalling."
                stage_passing = False
        signals.append(DealHealthSignal(type="stage_velocity", weight=stage_pts, description=stage_desc, passing=stage_passing))
        score += stage_pts

        # 3. Activity recency (25 pts)
        activity_pts = 0
        activity_desc = "No recent activity recorded."
        activity_passing = False
        if hasattr(deal, "updatedAt") and deal.updatedAt:
            days_since = (now - (deal.updatedAt.replace(tzinfo=now.tzinfo) if deal.updatedAt.tzinfo is None else deal.updatedAt)).days
            if days_since <= 3:
                activity_pts = 25
                activity_desc = "Updated within the last 3 days."
                activity_passing = True
            elif days_since <= 7:
                activity_pts = 20
                activity_desc = "Updated within the last week."
                activity_passing = True
            elif days_since <= 14:
                activity_pts = 10
                activity_desc = "Updated within the last 2 weeks."
                activity_passing = True
        signals.append(DealHealthSignal(type="activity_recency", weight=activity_pts, description=activity_desc, passing=activity_passing))
        score += activity_pts

        # 4. Amount set (25 pts)
        amount_pts = 0
        amount_desc = "No deal value set."
        amount_passing = False
        deal_value = getattr(deal, "value", None) or getattr(deal, "amount", None)
        if deal_value and float(deal_value) > 0:
            amount_pts = 25
            amount_desc = f"Deal value ${float(deal_value):,.0f} set."
            amount_passing = True
        signals.append(DealHealthSignal(type="amount_set", weight=amount_pts, description=amount_desc, passing=amount_passing))
        score += amount_pts

        passing_count = sum(1 for s in signals if s.passing)
        reason = (
            f"Score {score}/100 — {passing_count}/{len(signals)} signals positive. "
            + next((s.description for s in signals if not s.passing), "All signals healthy.")
        )
        return score, signals, reason

    async def suggest_next_step(
        self, db: AsyncSession, deal_id: str
    ) -> DealSuggestResponse | None:
        """LLM-suggested next step for a deal."""
        deal = await self.get(db, deal_id)
        if deal is None:
            return None
        llm = get_llm_service()
        prompt = (
            f"Suggest the next best action for deal '{deal.title}' "
            f"(stage: {deal.stage}, value: ${deal.value:.2f}). "
            "Respond as JSON: {suggestion:..., nextAction:..., confidence:0.0}"
        )
        data = await llm.generate_json(prompt=prompt)
        return DealSuggestResponse(
            dealId=deal_id,
            suggestion=str(data.get("suggestion", "Follow up this week.")),
            nextAction=str(data.get("nextAction", "Send a check-in email")),
            confidence=float(data.get("confidence", 0.5)),
        )
    # _evaluate_health removed — superseded by _score_deal (numeric 0-100 scoring)
