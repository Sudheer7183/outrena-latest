from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.schemas.auth import TokenPayload, Role
from app.api.security import require_role
from app.features.flow_analytics.schemas import (
    FlowAnalyticsResponse,
    FlowAnalyticsListResponse,
)
from app.features.flow_analytics.service import FlowAnalyticsService

router = APIRouter(prefix="/flow-analytics", tags=["Flow Analytics"])
_service = FlowAnalyticsService()


@router.get("/{flow_id}", response_model=FlowAnalyticsResponse)
async def get_flow_analytics(
    flow_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
):
    result = await _service.get_analytics(db, flow_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow not found")
    return result


@router.get("", response_model=FlowAnalyticsListResponse)
async def list_flow_analytics(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
):
    items, total = await _service.list_analytics(db, limit=limit, offset=offset)
    return FlowAnalyticsListResponse(items=items, total=total)
