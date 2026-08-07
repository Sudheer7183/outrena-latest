"""
rate_limits.py — Phase 3 /api/v1/rate-limits router.

Created by FIX-BE-1 / CRITICAL 1 (audit §D1): the underlying ORM models
in ``app/models/flow_models.py`` previously had NO service/route surface.

Endpoints:

  ── RateLimit (per-platform rate-limit configuration + counter) ──────────
  GET    /rate-limits              list (optional platform/is_active filter)
  POST   /rate-limits              create (TENANT_ADMIN+)
  GET    /rate-limits/{id}         fetch one
  PUT    /rate-limits/{id}         update (limit / window / throttleMode)
  DELETE /rate-limits/{id}         delete (204)
  POST   /rate-limits/{id}/reset   reset the counter (count=0, windowStart=now)

  ── RateLimitLog (immutable log of every rate-limited API call) ──────────
  GET    /rate-limits/logs         list (optional key/platform/flow_run_id filter)

Role gate: Role.MANAGER for reads, Role.TENANT_ADMIN for writes. The
actual per-platform Redis-based enforcement is a separate concern (not
addressed here) — this router exposes the configuration + counter CRUD
surface so tenant admins can inspect + adjust per-platform limits.

NOTE on RateLimitWindow reset semantics: when the configured window
elapses, the scheduler is responsible for resetting ``count=0`` and
bumping ``windowStart``. The POST /rate-limits/{id}/reset endpoint
provides a manual override for ops.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.rate_limit import (
    RateLimitCreate,
    RateLimitListResponse,
    RateLimitLogListResponse,
    RateLimitLogResponse,
    RateLimitResponse,
    RateLimitUpdate,
)
from app.features.rate_limits.service import RateLimitService

router = APIRouter(prefix="/rate-limits", tags=["Rate Limits"])
_service = RateLimitService()


# ── RateLimit CRUD ────────────────────────────────────────────────────────


@router.get("", response_model=RateLimitListResponse)
async def list_rate_limits(
    platform: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> RateLimitListResponse:
    items, total = await _service.list_rate_limits(
        db,
        platform=platform,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return RateLimitListResponse(
        items=[RateLimitResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=RateLimitResponse, status_code=201)
async def create_rate_limit(
    body: RateLimitCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> RateLimitResponse:
    item = await _service.create_rate_limit(db, body)
    return RateLimitResponse.model_validate(item)


@router.get("/logs", response_model=RateLimitLogListResponse)
async def list_rate_limit_logs(
    key: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    flow_run_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> RateLimitLogListResponse:
    items, total = await _service.list_logs(
        db,
        key=key,
        platform=platform,
        flow_run_id=flow_run_id,
        limit=limit,
        offset=offset,
    )
    return RateLimitLogListResponse(
        items=[RateLimitLogResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{rate_limit_id}", response_model=RateLimitResponse)
async def get_rate_limit(
    rate_limit_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> RateLimitResponse:
    item = await _service.get_rate_limit(db, rate_limit_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rate limit not found.")
    return RateLimitResponse.model_validate(item)


@router.put("/{rate_limit_id}", response_model=RateLimitResponse)
async def update_rate_limit(
    rate_limit_id: str,
    body: RateLimitUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> RateLimitResponse:
    item = await _service.update_rate_limit(db, rate_limit_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rate limit not found.")
    return RateLimitResponse.model_validate(item)


@router.delete(
    "/{rate_limit_id}",
    response_model=None,
    response_class=Response,
    status_code=204,
)
async def delete_rate_limit(
    rate_limit_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    ok = await _service.delete_rate_limit(db, rate_limit_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rate limit not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{rate_limit_id}/reset", response_model=RateLimitResponse)
async def reset_rate_limit_counter(
    rate_limit_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> RateLimitResponse:
    """Manually reset the counter (``count=0``, ``windowStart=now``)."""
    item = await _service.reset_counter(db, rate_limit_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rate limit not found.")
    return RateLimitResponse.model_validate(item)


__all__ = ["router"]
