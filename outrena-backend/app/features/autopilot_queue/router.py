from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.schemas.auth import TokenPayload, Role
from app.api.security import require_role
from app.features.autopilot_queue.schemas import (
    QueueItemResponse,
    QueueListResponse,
    EnqueueRequest,
    EnqueueResponse,
    QueueStatsResponse,
    TriggerResponse,
    AutonomousModeRequest,
)
from app.features.autopilot_queue.service import AutopilotQueueService

router = APIRouter(prefix="/autopilot-queue", tags=["Autopilot Queue"])
_service = AutopilotQueueService()


@router.get("", response_model=QueueListResponse)
async def list_queue(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
):
    items, total = await _service.list_queue(
        db, status_filter=status_filter, limit=limit, offset=offset
    )
    return QueueListResponse(items=items, total=total)


@router.get("/stats", response_model=QueueStatsResponse)
async def get_queue_stats(
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
):
    return await _service.get_stats(db)


@router.post("/enqueue", response_model=EnqueueResponse, status_code=status.HTTP_201_CREATED)
async def enqueue_flow(
    body: EnqueueRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
):
    result = await _service.enqueue(db, body)
    if not result.success:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, result.error)
    return result


@router.post("/trigger-scheduler", response_model=TriggerResponse)
async def trigger_scheduler(
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
):
    return await _service.trigger_scheduler(db)


@router.put("/autonomous-mode", response_model=QueueStatsResponse)
async def set_autonomous_mode(
    body: AutonomousModeRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
):
    return await _service.set_autonomous_mode(db, enabled=body.enabled)


@router.delete("/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_queue_item(
    queue_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
):
    cancelled = await _service.cancel_item(db, queue_id)
    if not cancelled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Queue item not found")
