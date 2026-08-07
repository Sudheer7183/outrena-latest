"""
scheduler.py — Phase 3 /api/v1/scheduler router.

Endpoints:
  GET    /scheduler/status    in-process scheduler status (lastTickAt, etc.)
  POST   /scheduler/tick       force a single synchronous tick
  POST   /scheduler/trigger    trigger an immediate scheduler run (Celery or sync)
  GET    /scheduler/runs       list recent scheduler run logs
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.scheduler import (
    ManualTickRequest,
    ManualTickResponse,
    SchedulerStatusResponse,
    TriggerResponse,
    SchedulerRunsListResponse,
)
from app.features.scheduler.service import SchedulerService

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
_service = SchedulerService()


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_status(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> SchedulerStatusResponse:
    item = await _service.get_status(db)
    return SchedulerStatusResponse.model_validate(item)


@router.post("/tick", response_model=ManualTickResponse)
async def manual_tick(
    body: ManualTickRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> ManualTickResponse:
    """Force a single synchronous scheduler tick (testing/admin)."""
    return await _service.manual_tick(
        db, tenant_scoped=body.tenantScoped, max_send=body.maxSend
    )


@router.post("/trigger", response_model=TriggerResponse)
async def trigger(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> TriggerResponse:
    """Trigger an immediate scheduler run (Celery async or synchronous fallback)."""
    return await _service.trigger(db)


@router.get("/runs", response_model=SchedulerRunsListResponse)
async def list_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> SchedulerRunsListResponse:
    """List recent scheduler run logs, newest first."""
    return await _service.list_runs(db, limit=limit, offset=offset)
