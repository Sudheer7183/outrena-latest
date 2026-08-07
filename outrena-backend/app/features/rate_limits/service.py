"""
rate_limit_service.py — RateLimit + RateLimitLog CRUD.

Created by FIX-BE-1 / CRITICAL 1 (audit §D1): the underlying ORM models
in ``app/models/flow_models.py`` previously had NO service/route surface.

This service backs the new ``app/api/v1/rate_limits.py`` router. The
actual per-platform Redis-based rate-limit enforcement (migration §10
Phase 6) is a separate concern not addressed here — this service exposes
the configuration + counter CRUD surface so SUPER_ADMINs can inspect +
adjust per-platform limits.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RateLimitWindow
from app.models.flow_models import RateLimit, RateLimitLog
from app.schemas.rate_limit import (
    RateLimitCreate,
    RateLimitUpdate,
)

logger = structlog.get_logger(__name__)


class RateLimitService:
    """CRUD for RateLimit + RateLimitLog rows (tenant-scoped)."""

    # ── RateLimit CRUD ────────────────────────────────────────────────────

    async def list_rate_limits(
        self,
        db: AsyncSession,
        *,
        platform: str | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RateLimit], int]:
        stmt = select(RateLimit)
        if platform:
            stmt = stmt.where(RateLimit.platform == platform)
        if is_active is not None:
            stmt = stmt.where(RateLimit.isActive.is_(is_active))
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar() or 0)
        result = await db.execute(
            stmt.order_by(RateLimit.createdAt.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_rate_limit(
        self, db: AsyncSession, rate_limit_id: str
    ) -> RateLimit | None:
        return (
            await db.execute(
                select(RateLimit).where(RateLimit.id == rate_limit_id)
            )
        ).scalar_one_or_none()

    async def create_rate_limit(
        self, db: AsyncSession, body: RateLimitCreate
    ) -> RateLimit:
        item = RateLimit(**body.model_dump())
        db.add(item)
        await db.commit()
        item = await db.get(RateLimit, item.id)
        return item

    async def update_rate_limit(
        self,
        db: AsyncSession,
        rate_limit_id: str,
        body: RateLimitUpdate,
    ) -> RateLimit | None:
        item = await self.get_rate_limit(db, rate_limit_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(RateLimit, item.id)
        return item

    async def delete_rate_limit(
        self, db: AsyncSession, rate_limit_id: str
    ) -> bool:
        item = await self.get_rate_limit(db, rate_limit_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def reset_counter(
        self, db: AsyncSession, rate_limit_id: str
    ) -> RateLimit | None:
        """Reset ``count`` to 0 + bump ``windowStart`` to now().

        Useful when an operator wants to manually clear a throttled
        platform's counter (e.g. after a quota reset with the upstream
        provider).
        """
        item = await self.get_rate_limit(db, rate_limit_id)
        if item is None:
            return None
        item.count = 0
        item.windowStart = datetime.now(timezone.utc)
        await db.commit()
        item = await db.get(RateLimit, item.id)
        return item

    # ── RateLimitLog (read-only) ──────────────────────────────────────────

    async def list_logs(
        self,
        db: AsyncSession,
        *,
        key: str | None = None,
        platform: str | None = None,
        flow_run_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RateLimitLog], int]:
        stmt = select(RateLimitLog)
        if key:
            stmt = stmt.where(RateLimitLog.key == key)
        if platform:
            stmt = stmt.where(RateLimitLog.platform == platform)
        if flow_run_id:
            stmt = stmt.where(RateLimitLog.flowRunId == flow_run_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar() or 0)
        result = await db.execute(
            stmt.order_by(RateLimitLog.createdAt.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total


__all__ = ["RateLimitService"]
