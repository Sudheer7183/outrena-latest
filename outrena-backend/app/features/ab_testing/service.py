"""
ab_testing_service.py — A/B split-cohort test CRUD + significance calculation.

Significance test: two-proportion z-test (normal approximation of binomial).
Returns isSignificant=True when p < 0.05.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import AbTest, AbTestAssignment, EmailAbTest
from app.schemas.ab_testing import (
    AbTestCreate,
    AbTestUpdate,
    SignificanceResult,
)


class AbTestingService:
    async def list_tests(
        self, db: AsyncSession, *, campaign_id: str | None = None
    ) -> list[AbTest]:
        stmt = select(AbTest)
        if campaign_id:
            stmt = stmt.where(AbTest.campaignId == campaign_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, test_id: str) -> AbTest | None:
        result = await db.execute(select(AbTest).where(AbTest.id == test_id))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, body: AbTestCreate) -> AbTest:
        test = AbTest(**body.model_dump(), status="draft")
        db.add(test)
        await db.commit()
        test = await db.get(AbTest, test.id)
        return test

    async def update(
        self, db: AsyncSession, test_id: str, body: AbTestUpdate
    ) -> AbTest | None:
        test = await self.get(db, test_id)
        if test is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(test, key, value)
        await db.commit()
        test = await db.get(AbTest, test.id)
        return test

    async def delete(self, db: AsyncSession, test_id: str) -> bool:
        test = await self.get(db, test_id)
        if test is None:
            return False
        await db.delete(test)
        await db.commit()
        return True

    async def start(self, db: AsyncSession, test_id: str) -> AbTest | None:
        test = await self.get(db, test_id)
        if test is None:
            return None
        test.status = "running"
        test.startedAt = datetime.now(timezone.utc)
        await db.commit()
        test = await db.get(AbTest, test.id)
        return test

    async def significance(
        self, db: AsyncSession, test_id: str
    ) -> SignificanceResult | None:
        """Compute two-proportion z-test for variant A vs B."""
        test = await self.get(db, test_id)
        if test is None:
            return None
        result = await db.execute(
            select(AbTestAssignment).where(AbTestAssignment.abTestId == test_id)
        )
        assignments = list(result.scalars().all())
        a = [a for a in assignments if a.variant.upper() == "A"]
        b = [a for a in assignments if a.variant.upper() == "B"]
        a_count = len(a)
        b_count = len(b)
        a_successes = sum(1 for x in a if x.isPositiveReply)
        b_successes = sum(1 for x in b if x.isPositiveReply)
        a_rate = (a_successes / a_count) if a_count else 0.0
        b_rate = (b_successes / b_count) if b_count else 0.0
        z_score, p_value = self._two_proportion_z(
            a_successes, a_count, b_successes, b_count
        )
        winner = None
        if p_value < 0.05:
            if a_rate > b_rate:
                winner = "A"
            elif b_rate > a_rate:
                winner = "B"
        return SignificanceResult(
            abTestId=test_id,
            variantACount=a_count,
            variantBCount=b_count,
            variantASuccesses=a_successes,
            variantBSuccesses=b_successes,
            variantARate=a_rate,
            variantBRate=b_rate,
            zScore=z_score,
            pValue=p_value,
            isSignificant=p_value < 0.05,
            winner=winner,
        )

    async def list_email_ab_tests(
        self, db: AsyncSession, campaign_id: str | None = None
    ) -> list[EmailAbTest]:
        stmt = select(EmailAbTest)
        if campaign_id:
            stmt = stmt.where(EmailAbTest.campaignId == campaign_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _two_proportion_z(
        x1: int, n1: int, x2: int, n2: int
    ) -> tuple[float, float]:
        """Two-proportion z-test. Returns (z_score, two_tailed_p_value)."""
        if n1 == 0 or n2 == 0:
            return 0.0, 1.0
        p1 = x1 / n1
        p2 = x2 / n2
        p_pool = (x1 + x2) / (n1 + n2)
        if p_pool == 0 or p_pool == 1:
            return 0.0, 1.0
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
        if se == 0:
            return 0.0, 1.0
        z = (p1 - p2) / se
        # Two-tailed p-value via the standard normal CDF approximation
        p_value = 2 * (1 - _normal_cdf(abs(z)))
        return round(z, 4), round(p_value, 4)


def _normal_cdf(x: float) -> float:
    """Abramowitz & Stegun 26.2.17 approximation of the standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
