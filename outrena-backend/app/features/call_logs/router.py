"""
call_logs.py — Phase 3 /api/v1/call-logs router.

Created by FIX-BE-1 / Additional (audit §E1): the underlying CallLog
model in ``app/models/prospect_models.py`` previously had NO
service/route. This router provides the CRUD surface the frontend
Call Logs page is blocked on.

Endpoints:
  GET    /call-logs              list (optional prospect_id + outcome filter)
  POST   /call-logs              create (REP+)
  GET    /call-logs/{id}         fetch one
  PATCH  /call-logs/{id}         partial update
  DELETE /call-logs/{id}         delete (204)

Role gate: Role.REP — any authenticated user can log calls to prospects
they can read. MANAGER+ sees all call logs for the tenant (no per-user
filter at the DB layer today; the Prospect they reference is the unit of
ACL).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.call_log import (
    CallLogCreate,
    CallLogListResponse,
    CallLogResponse,
    CallLogUpdate,
)
from app.features.call_logs.service import CallLogService

router = APIRouter(prefix="/call-logs", tags=["Call Logs"])
_service = CallLogService()


@router.get("", response_model=CallLogListResponse)
async def list_call_logs(
    prospect_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> CallLogListResponse:
    """List call logs (optional ``?prospect_id=`` + ``?outcome=`` filters)."""
    items, total = await _service.list_call_logs(
        db,
        prospect_id=prospect_id,
        outcome=outcome,
        limit=limit,
        offset=offset,
    )
    return CallLogListResponse(
        items=[CallLogResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=CallLogResponse, status_code=201)
async def create_call_log(
    body: CallLogCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> CallLogResponse:
    """Log a call. ``prospectId`` must reference an existing Prospect."""
    try:
        item = await _service.create_call_log(db, body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return CallLogResponse.model_validate(item)


@router.get("/{call_log_id}", response_model=CallLogResponse)
async def get_call_log(
    call_log_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> CallLogResponse:
    item = await _service.get_call_log(db, call_log_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call log not found.")
    return CallLogResponse.model_validate(item)


@router.patch("/{call_log_id}", response_model=CallLogResponse)
async def update_call_log(
    call_log_id: str,
    body: CallLogUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> CallLogResponse:
    item = await _service.update_call_log(db, call_log_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call log not found.")
    return CallLogResponse.model_validate(item)


@router.delete(
    "/{call_log_id}",
    response_model=None,
    response_class=Response,
    status_code=204,
)
async def delete_call_log(
    call_log_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete_call_log(db, call_log_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call log not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
