"""
dashboard.py — Phase 3 /api/v1/dashboard router.

Endpoints:
  GET    /dashboard                 composite dashboard payload (single round-trip)
  GET    /dashboard/manager         MANAGER+ per-user rollup (SAAS2-USER-BE §J)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.dashboard import DashboardResponse, ManagerDashboardResponse
from app.features.dashboard.service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
_service = DashboardService()


def _role_value(token: TokenPayload) -> str:
    return token.role.value if hasattr(token.role, "value") else str(token.role)


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    user_id: str | None = Query(
        default=None,
        description="Filter to a specific user (MANAGER+ only). "
                    "REP tokens always see only their own data.",
    ),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> DashboardResponse:
    """Composite dashboard payload — aggregation + time series + top campaigns + pipeline.

    Per-user scoping (SAAS2-USER-BE §J):
      * REP tokens always see only their own data (user_id is forced to token.sub).
      * MANAGER+ with explicit ?user_id=... → filter to that user.
      * MANAGER+ without ?user_id= → tenant-wide.
    """
    role = _role_value(token)
    effective_user_id = user_id
    if role.upper() == "REP":
        effective_user_id = token.sub
    return await _service.get(db, user_id=effective_user_id, role=role)


@router.get("/manager", response_model=ManagerDashboardResponse)
async def get_manager_dashboard(
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> ManagerDashboardResponse:
    """Manager rollup: per-user lines + tenant-wide totals + top performers + at-risk users.

    MANAGER+ only. Returns one ManagerUserRollup per active user with their
    emails_sent, campaigns_active, prospects_contacted, replies_received,
    meetings_booked, pipeline_value, quota_used_pct, and is_throttled flag.
    """
    return await _service.get_manager_dashboard(db)


__all__ = ["router"]
