"""
call_log_service.py — CallLog CRUD (phone-channel tracking).

Created by FIX-BE-1 / Additional: the underlying ``CallLog`` model in
``app/models/prospect_models.py`` previously had NO service/route surface
(audit §E1 — only referenced in ``gdpr_service.py`` for DSR export).
This service backs the new ``app/api/v1/call_logs.py`` router and
unblocks the frontend Call Logs page.

All methods take an ``AsyncSession`` locked to the tenant's schema via
``Depends(get_db)`` — the search_path is set by the dependency, so we
don't need to set it here.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect_models import CallLog, Prospect
from app.schemas.call_log import CallLogCreate, CallLogUpdate

logger = structlog.get_logger(__name__)


class CallLogService:
    """CRUD for CallLog rows (tenant-scoped, Prospect-bound)."""

    async def list_call_logs(
        self,
        db: AsyncSession,
        *,
        prospect_id: str | None = None,
        outcome: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CallLog], int]:
        """List call logs with optional prospect_id + outcome filters.

        Returns ``(items, total)`` so the router can build the page envelope.
        Results are ordered by ``calledAt`` descending (most recent first).
        """
        stmt = select(CallLog)
        if prospect_id:
            stmt = stmt.where(CallLog.prospectId == prospect_id)
        if outcome:
            stmt = stmt.where(CallLog.outcome == outcome)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = int(total_result.scalar() or 0)

        result = await db.execute(
            stmt.order_by(CallLog.calledAt.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_call_log(
        self, db: AsyncSession, call_log_id: str
    ) -> CallLog | None:
        result = await db.execute(
            select(CallLog).where(CallLog.id == call_log_id)
        )
        return result.scalar_one_or_none()

    async def create_call_log(
        self, db: AsyncSession, body: CallLogCreate
    ) -> CallLog:
        """Create a CallLog row. Validates the prospect exists.

        Raises:
            ValueError: if the prospectId does not reference an existing
                Prospect row in the tenant schema.
        """
        # Validate the prospect exists in the caller's tenant schema.
        prospect_result = await db.execute(
            select(Prospect.id).where(Prospect.id == body.prospectId).limit(1)
        )
        if prospect_result.scalar_one_or_none() is None:
            raise ValueError(
                f"Prospect '{body.prospectId}' not found in this tenant."
            )

        item = CallLog(
            prospectId=body.prospectId,
            phone=body.phone,
            outcome=body.outcome or "pending",
            durationSec=body.durationSec,
            notes=body.notes,
            calledAt=body.calledAt or datetime.now(timezone.utc),
        )
        db.add(item)
        await db.commit()
        item = await db.get(CallLog, item.id)
        return item

    async def update_call_log(
        self, db: AsyncSession, call_log_id: str, body: CallLogUpdate
    ) -> CallLog | None:
        item = await self.get_call_log(db, call_log_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(CallLog, item.id)
        return item

    async def delete_call_log(
        self, db: AsyncSession, call_log_id: str
    ) -> bool:
        item = await self.get_call_log(db, call_log_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True


__all__ = ["CallLogService"]
