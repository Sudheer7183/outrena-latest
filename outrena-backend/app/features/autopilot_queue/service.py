import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from app.models.flow_models import ProspectingFlow, AutopilotQueue
from app.models.enums import AutopilotQueueStatus
from app.features.autopilot_queue.schemas import (
    QueueItemResponse,
    QueueStatsResponse,
    EnqueueRequest,
    EnqueueResponse,
    TriggerResponse,
)

logger = logging.getLogger(__name__)


class AutopilotQueueService:
    """Autonomous execution engine: queue management + scheduler."""

    async def list_queue(
        self,
        db: AsyncSession,
        *,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        """List queue items, optionally filtered by status."""
        stmt = select(AutopilotQueue)
        if status_filter:
            try:
                status_enum = AutopilotQueueStatus(status_filter)
                stmt = stmt.where(AutopilotQueue.status == status_enum)
            except ValueError:
                pass  # ignore invalid status filter
        stmt = stmt.order_by(AutopilotQueue.queuedAt.desc())

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar() or 0)

        result = await db.execute(stmt.offset(offset).limit(limit))
        items_orm = list(result.scalars().all())

        items = []
        for q in items_orm:
            flow = await db.get(ProspectingFlow, q.flowId)
            items.append(
                QueueItemResponse(
                    id=str(q.id),
                    flow_id=str(q.flowId),
                    flow_name=flow.name if flow else "Unknown",
                    icp_id=q.icpProfileId,
                    status=q.status.value if q.status else "QUEUED",
                    max_prospects=(q.config or {}).get("maxProspects", 50),
                    dry_run=(q.config or {}).get("dryRun", False),
                    created_at=q.queuedAt.isoformat() if q.queuedAt else None,
                    started_at=q.pickedUpAt.isoformat() if q.pickedUpAt else None,
                    completed_at=q.completedAt.isoformat() if q.completedAt else None,
                    run_id=q.flowRunId,
                    error=q.errorMessage,
                )
            )

        return items, total

    async def get_stats(self, db: AsyncSession):
        """Aggregate queue stats and check autonomous mode flag."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(hours=24)

        queued = int(
            (
                await db.execute(
                    select(func.count()).where(
                        AutopilotQueue.status == AutopilotQueueStatus.QUEUED
                    )
                )
            ).scalar()
            or 0
        )
        running = int(
            (
                await db.execute(
                    select(func.count()).where(
                        AutopilotQueue.status == AutopilotQueueStatus.RUNNING
                    )
                )
            ).scalar()
            or 0
        )
        completed_24h = int(
            (
                await db.execute(
                    select(func.count()).where(
                        AutopilotQueue.status == AutopilotQueueStatus.COMPLETED,
                        AutopilotQueue.completedAt >= yesterday,
                    )
                )
            ).scalar()
            or 0
        )
        failed_24h = int(
            (
                await db.execute(
                    select(func.count()).where(
                        AutopilotQueue.status == AutopilotQueueStatus.FAILED,
                        AutopilotQueue.completedAt >= yesterday,
                    )
                )
            ).scalar()
            or 0
        )

        # Check autonomous mode from SystemParameter
        autonomous_mode = False
        try:
            from app.models.config_models import SystemParameter

            param = await db.execute(
                select(SystemParameter).where(
                    SystemParameter.key == "autopilot_autonomous_mode"
                )
            )
            p = param.scalar_one_or_none()
            if p and p.value:
                autonomous_mode = str(p.value).lower() in ("true", "1", "yes")
        except Exception:
            pass

        return QueueStatsResponse(
            queued=queued,
            running=running,
            completed_24h=completed_24h,
            failed_24h=failed_24h,
            autonomous_mode=autonomous_mode,
        )

    async def enqueue(self, db: AsyncSession, body: EnqueueRequest) -> EnqueueResponse:
        """Add a flow to the autopilot queue."""
        flow = await db.get(ProspectingFlow, body.flow_id)
        if flow is None:
            return EnqueueResponse(success=False, error="Flow not found")

        try:
            item = AutopilotQueue(
                flowId=body.flow_id,
                icpProfileId=body.icp_id,
                status=AutopilotQueueStatus.QUEUED,
                origin="manual_enqueue",
                config={
                    "maxProspects": body.max_prospects,
                    "dryRun": body.dry_run,
                },
            )
            db.add(item)
            await db.commit()
            # Re-fetch to get auto-generated ID (avoids DetachedInstanceError)
            item = await db.get(AutopilotQueue, item.id)
            return EnqueueResponse(success=True, queue_id=str(item.id))
        except Exception as e:
            logger.error("Enqueue failed: %s", e)
            return EnqueueResponse(success=False, error=str(e))

    async def trigger_scheduler(self, db: AsyncSession) -> TriggerResponse:
        """Process all QUEUED items — mark RUNNING then COMPLETED."""
        stmt = select(AutopilotQueue).where(
            AutopilotQueue.status == AutopilotQueueStatus.QUEUED
        ).limit(10)
        result = await db.execute(stmt)
        queued_items = list(result.scalars().all())

        processed = 0
        for item in queued_items:
            try:
                item.status = AutopilotQueueStatus.RUNNING
                item.pickedUpAt = datetime.now(timezone.utc)
                await db.flush()

                # In production this would dispatch a Celery task to run the flow.
                # For now, mark as completed immediately.
                item.status = AutopilotQueueStatus.COMPLETED
                item.completedAt = datetime.now(timezone.utc)
                processed += 1
            except Exception as e:
                item.status = AutopilotQueueStatus.FAILED
                item.errorMessage = str(e)
                item.completedAt = datetime.now(timezone.utc)
                logger.error("Scheduler run failed for %s: %s", item.id, e)

        await db.commit()
        return TriggerResponse(success=True, processed=processed)

    async def set_autonomous_mode(self, db: AsyncSession, enabled: bool):
        """Toggle the autopilot_autonomous_mode system parameter."""
        try:
            from app.models.config_models import SystemParameter

            stmt = select(SystemParameter).where(
                SystemParameter.key == "autopilot_autonomous_mode"
            )
            result = await db.execute(stmt)
            param = result.scalar_one_or_none()
            if param:
                param.value = str(enabled).lower()
            else:
                param = SystemParameter(
                    key="autopilot_autonomous_mode",
                    value=str(enabled).lower(),
                    category="autopilot",
                    label="Autonomous Mode",
                    description="Enable autonomous autopilot scheduling",
                    impact="high",
                    valueType="boolean",
                    defaultValue="false",
                )
                db.add(param)
            await db.commit()
        except Exception as e:
            logger.error("Failed to set autonomous mode: %s", e)

        return await self.get_stats(db)

    async def cancel_item(self, db: AsyncSession, queue_id: str) -> bool:
        """Cancel and remove a QUEUED or RUNNING queue item."""
        item = await db.get(AutopilotQueue, queue_id)
        if item is None or item.status not in (
            AutopilotQueueStatus.QUEUED,
            AutopilotQueueStatus.RUNNING,
        ):
            return False
        item.status = AutopilotQueueStatus.CANCELLED
        item.completedAt = datetime.now(timezone.utc)
        await db.commit()
        return True
