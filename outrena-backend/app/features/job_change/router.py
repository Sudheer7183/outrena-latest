"""
job_change_monitor.py — Phase 3 /api/v1/job-change-monitor router.

Endpoints:
  GET    /job-change-monitor              list alerts
  POST   /job-change-monitor/scan         kick off a scan
  GET    /job-change-monitor/{id}         fetch one
  PUT    /job-change-monitor/{id}         update status/notes
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.job_change_monitor import (
    JobChangeAlertResponse,
    JobChangeAlertUpdate,
    JobChangeScanRequest,
    JobChangeScanResponse,
)
from app.features.job_change.service import JobChangeMonitorService

router = APIRouter(prefix="/job-change-monitor", tags=["Job Change Monitor"])
_service = JobChangeMonitorService()


@router.get("", response_model=list[JobChangeAlertResponse])
async def list_alerts(
    prospect_id: str | None = Query(default=None),
    alert_status: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[JobChangeAlertResponse]:
    items = await _service.list_alerts(
        db, prospect_id=prospect_id, status=alert_status
    )
    return [JobChangeAlertResponse.model_validate(i) for i in items]


@router.post("/scan", response_model=JobChangeScanResponse)
async def scan(
    body: JobChangeScanRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> JobChangeScanResponse:
    return await _service.scan(db, body.prospectIds)


@router.get("/{alert_id}", response_model=JobChangeAlertResponse)
async def get_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> JobChangeAlertResponse:
    item = await _service.get_alert(db, alert_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job-change alert not found.")
    return JobChangeAlertResponse.model_validate(item)


@router.put("/{alert_id}", response_model=JobChangeAlertResponse)
async def update_alert(
    alert_id: str,
    body: JobChangeAlertUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> JobChangeAlertResponse:
    item = await _service.update_alert(db, alert_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job-change alert not found.")
    return JobChangeAlertResponse.model_validate(item)
