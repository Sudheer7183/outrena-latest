# # """
# # scheduler.py — Phase 3 /api/v1/scheduler router.

# # Endpoints:
# #   GET    /scheduler/status    in-process scheduler status (lastTickAt, etc.)
# #   POST   /scheduler/tick       force a single synchronous tick
# #   POST   /scheduler/trigger    trigger an immediate scheduler run (Celery or sync)
# #   GET    /scheduler/runs       list recent scheduler run logs
# # """
# # from __future__ import annotations

# # from fastapi import APIRouter, Depends, Query
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.api.deps import get_db
# # from app.api.security import require_role
# # from app.schemas.auth import Role
# # from app.schemas.scheduler import (
# #     ManualTickRequest,
# #     ManualTickResponse,
# #     SchedulerStatusResponse,
# #     TriggerResponse,
# #     SchedulerRunsListResponse,
# # )
# # from app.features.scheduler.service import SchedulerService

# # router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
# # _service = SchedulerService()


# # @router.get("/status", response_model=SchedulerStatusResponse)
# # async def get_status(
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.REP)),
# # ) -> SchedulerStatusResponse:
# #     item = await _service.get_status(db)
# #     return SchedulerStatusResponse.model_validate(item)


# # @router.post("/tick", response_model=ManualTickResponse)
# # async def manual_tick(
# #     body: ManualTickRequest,
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.TENANT_ADMIN)),
# # ) -> ManualTickResponse:
# #     """Force a single synchronous scheduler tick (testing/admin)."""
# #     return await _service.manual_tick(
# #         db, tenant_scoped=body.tenantScoped, max_send=body.maxSend
# #     )


# # @router.post("/trigger", response_model=TriggerResponse)
# # async def trigger(
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.TENANT_ADMIN)),
# # ) -> TriggerResponse:
# #     """Trigger an immediate scheduler run (Celery async or synchronous fallback)."""
# #     return await _service.trigger(db)


# # @router.get("/runs", response_model=SchedulerRunsListResponse)
# # async def list_runs(
# #     limit: int = Query(20, ge=1, le=100),
# #     offset: int = Query(0, ge=0),
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.REP)),
# # ) -> SchedulerRunsListResponse:
# #     """List recent scheduler run logs, newest first."""
# #     return await _service.list_runs(db, limit=limit, offset=offset)

# """
# scheduler/router.py — Phase 3 /api/v1/scheduler router.

# Endpoints:
#   GET    /scheduler/status    in-process scheduler status (lastTickAt, etc.)
#   POST   /scheduler/tick       force a single synchronous tick
#   POST   /scheduler/trigger    trigger an immediate scheduler run (Celery or sync)
#   GET    /scheduler/runs       list recent scheduler run logs

# Role matrix (after MANAGER access grant):
#   GET  /status   → REP+        (read-only; always was REP+)
#   POST /tick     → MANAGER+    (was TENANT_ADMIN; managers can now run ticks)
#   POST /trigger  → MANAGER+    (was TENANT_ADMIN; managers can now trigger)
#   GET  /runs     → REP+        (read-only; always was REP+)
# """
# from __future__ import annotations

# from fastapi import APIRouter, Depends, Query
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import require_role
# from app.schemas.auth import Role
# from app.schemas.scheduler import (
#     ManualTickRequest,
#     ManualTickResponse,
#     SchedulerStatusResponse,
#     TriggerResponse,
#     SchedulerRunsListResponse,
# )
# from app.features.scheduler.service import SchedulerService

# router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
# _service = SchedulerService()


# @router.get("/status", response_model=SchedulerStatusResponse)
# async def get_status(
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> SchedulerStatusResponse:
#     item = await _service.get_status(db)
#     return SchedulerStatusResponse.model_validate(item)


# @router.post("/tick", response_model=ManualTickResponse)
# async def manual_tick(
#     body: ManualTickRequest,
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.MANAGER)),
# ) -> ManualTickResponse:
#     """Force a single synchronous scheduler tick (testing/admin).

#     Lowered from TENANT_ADMIN → MANAGER so managers can run ticks
#     without needing platform admin access.
#     """
#     return await _service.manual_tick(
#         db, tenant_scoped=body.tenantScoped, max_send=body.maxSend
#     )


# @router.post("/trigger", response_model=TriggerResponse)
# async def trigger(
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.MANAGER)),
# ) -> TriggerResponse:
#     """Trigger an immediate scheduler run (Celery async or synchronous fallback).

#     Lowered from TENANT_ADMIN → MANAGER so managers can trigger runs
#     without needing platform admin access.
#     """
#     return await _service.trigger(db)


# @router.get("/runs", response_model=SchedulerRunsListResponse)
# async def list_runs(
#     limit: int = Query(20, ge=1, le=100),
#     offset: int = Query(0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> SchedulerRunsListResponse:
#     """List recent scheduler run logs, newest first."""
#     return await _service.list_runs(db, limit=limit, offset=offset)

"""
scheduler/router.py — /api/v1/scheduler router.

Endpoints (existing):
  GET    /scheduler/status              scheduler status (lastTickAt, counters)
  POST   /scheduler/tick                force a single synchronous tick
  POST   /scheduler/trigger             trigger an immediate scheduler run
  GET    /scheduler/runs                list recent scheduler run logs

New endpoints (Scheduler Page enhancement):
  GET    /scheduler/campaign-schedules  sequences grouped by campaign + filter
  GET    /scheduler/skipped-details     skip reason drill-down per run/campaign
  GET    /scheduler/daily-sent          daily sent count per campaign log

Role matrix:
  GET  /status                → REP+
  POST /tick                  → MANAGER+
  POST /trigger               → MANAGER+
  GET  /runs                  → REP+
  GET  /campaign-schedules    → REP+
  GET  /skipped-details       → REP+
  GET  /daily-sent            → REP+
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.scheduler import (
    CampaignScheduleListResponse,
    DailySentListResponse,
    ManualTickRequest,
    ManualTickResponse,
    SchedulerRunsListResponse,
    SchedulerStatusResponse,
    SkipLogListResponse,
    TriggerResponse,
)
from app.features.scheduler.service import SchedulerService
from app.features.scheduler.query_service import (
    get_campaign_schedules,
    get_daily_sent,
    get_skipped_details,
)

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
_service = SchedulerService()


# ── Existing endpoints (unchanged behaviour) ──────────────────────────────────

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
    _: object = Depends(require_role(Role.MANAGER)),
) -> ManualTickResponse:
    """Force a single synchronous scheduler tick (testing/admin)."""
    return await _service.manual_tick(
        db, tenant_scoped=body.tenantScoped, max_send=body.maxSend
    )


@router.post("/trigger", response_model=TriggerResponse)
async def trigger(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
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


# ── New endpoints ─────────────────────────────────────────────────────────────

@router.get("/campaign-schedules", response_model=CampaignScheduleListResponse)
async def list_campaign_schedules(
    campaign_id: Optional[str] = Query(None, description="Filter to a specific campaign"),
    status: Optional[str] = Query(None, description="Filter by campaign status (draft/active/paused/completed)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> CampaignScheduleListResponse:
    """Return Sequence counts grouped by Campaign for the Scheduler dashboard.

    Each row shows how many sequences are Scheduled / Sent / Replied / Bounced /
    Failed for that campaign, plus the next scheduled send time.

    Use ?campaign_id= to drill into a single campaign.
    Use ?status= to filter by campaign status (draft | active | paused | completed).
    """
    return await get_campaign_schedules(
        db,
        campaign_id=campaign_id,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


@router.get("/skipped-details", response_model=SkipLogListResponse)
async def list_skipped_details(
    run_id: Optional[str] = Query(None, description="Filter to a specific scheduler run"),
    campaign_id: Optional[str] = Query(None, description="Filter to a specific campaign"),
    skip_reason: Optional[str] = Query(
        None,
        description=(
            "Filter by skip reason: no_email | suppressed | business_hours "
            "| quota_exceeded | no_mailbridge_config | send_error | warmup_cap"
        ),
    ),
    since: Optional[datetime] = Query(None, description="Only return skips after this datetime (ISO 8601)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> SkipLogListResponse:
    """Return per-sequence skip events with reason categories.

    Requires migration 0022 to be applied — returns an empty list with
    empty reasonBreakdown if the SchedulerSkipLog table does not exist yet.

    Skip reasons:
      no_email          — prospect has no email address
      suppressed        — prospect is on suppression list
      business_hours    — outside 9am-5pm in prospect timezone
      quota_exceeded    — sender daily/hourly quota exhausted
      no_mailbridge_config — no MailBridge account configured
      send_error        — MailBridge send attempt failed
      warmup_cap        — domain warmup daily cap reached
    """
    return await get_skipped_details(
        db,
        run_id=run_id,
        campaign_id=campaign_id,
        skip_reason=skip_reason,
        since=since,
        limit=limit,
        offset=offset,
    )


@router.get("/daily-sent", response_model=DailySentListResponse)
async def list_daily_sent(
    campaign_id: Optional[str] = Query(None, description="Filter to a specific campaign"),
    since: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    until: Optional[date] = Query(None, description="End date inclusive (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> DailySentListResponse:
    """Return daily sent counts per campaign.

    Primary source is the SchedulerDailySent aggregation table (fast, updated
    in real-time as ticks run). Falls back to aggregating from Sequence.sentAt
    if migration 0022 has not been applied yet.

    Default date range is all time. Use ?since=2026-08-01&until=2026-08-30
    to narrow to a window.
    """
    return await get_daily_sent(
        db,
        campaign_id=campaign_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
