"""
signals.py — Phase 3 /api/v1/signals router.

Endpoints:
  GET    /signals                       list signals (filter prospectId / type)
  POST   /signals                       create a signal manually
  GET    /signals/monitors              list monitors
  POST   /signals/monitors              create a monitor
  PUT    /signals/monitors/{id}         update
  DELETE /signals/monitors/{id}         delete
  POST   /signals/scan                  scan prospects for new signals
  POST   /signals/lead-score            compute ICP-fit + urgency (60s timeout)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.signals import (
    LeadScoreBatchRequest,
    LeadScoreBatchResponse,
    LeadScoreRequest,
    LeadScoreResponse,
    LeadScoreStatsResponse,
    SignalMonitorCreate,
    SignalMonitorResponse,
    SignalMonitorUpdate,
    SignalResponse,
    SignalsScanRequest,
    SignalsScanResponse,
)
from app.features.signals.service import SignalsService

router = APIRouter(prefix="/signals", tags=["Signals"])
_service = SignalsService()


@router.get("", response_model=list[SignalResponse])
async def list_signals(
    prospect_id: str | None = Query(default=None),
    signal_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[SignalResponse]:
    items = await _service.list_signals(
        db, prospect_id=prospect_id, signal_type=signal_type, limit=limit
    )
    return [SignalResponse.model_validate(i) for i in items]


@router.post("", response_model=SignalResponse, status_code=201)
async def create_signal(
    prospect_id: str | None = Query(default=None),
    signal_type: str = Query(..., alias="type"),
    summary: str = Query(...),
    confidence: float = Query(default=0.8, ge=0.0, le=1.0),
    detail: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> SignalResponse:
    item = await _service.create_signal(
        db, prospect_id, signal_type, summary, confidence, detail
    )
    return SignalResponse.model_validate(item)


@router.post("/scan", response_model=SignalsScanResponse)
async def scan(
    body: SignalsScanRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> SignalsScanResponse:
    return await _service.scan(db, body.prospectIds, body.signalTypes)


@router.post("/lead-score", response_model=LeadScoreResponse)
async def lead_score(
    body: LeadScoreRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> LeadScoreResponse:
    """Compute 100-pt ICP-fit + P0/P1/P2 urgency. Hard 60s timeout."""
    return await _service.lead_score(db, body.prospectId, body.timeoutSeconds)


@router.post("/lead-score-batch", response_model=LeadScoreBatchResponse)
async def lead_score_batch(
    body: LeadScoreBatchRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> LeadScoreBatchResponse:
    """Batch LLM-based lead scoring for multiple prospects."""
    return await _service.lead_score_batch(db, body)


@router.get("/lead-score/stats", response_model=LeadScoreStatsResponse)
async def lead_score_stats(
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> LeadScoreStatsResponse:
    """Aggregate lead score statistics."""
    return await _service.get_lead_score_stats(db)


# ── Monitors ───────────────────────────────────────────────────────────────
@router.get("/monitors", response_model=list[SignalMonitorResponse])
async def list_monitors(
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[SignalMonitorResponse]:
    items = await _service.list_monitors(db, active_only=active_only)
    return [SignalMonitorResponse.model_validate(i) for i in items]


@router.post("/monitors", response_model=SignalMonitorResponse, status_code=201)
async def create_monitor(
    body: SignalMonitorCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> SignalMonitorResponse:
    item = await _service.create_monitor(db, body)
    return SignalMonitorResponse.model_validate(item)


@router.put("/monitors/{monitor_id}", response_model=SignalMonitorResponse)
async def update_monitor(
    monitor_id: str,
    body: SignalMonitorUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> SignalMonitorResponse:
    item = await _service.update_monitor(db, monitor_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Signal monitor not found.")
    return SignalMonitorResponse.model_validate(item)


@router.delete("/monitors/{monitor_id}", response_model=None, response_class=Response, status_code=204)
async def delete_monitor(
    monitor_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete_monitor(db, monitor_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Signal monitor not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
