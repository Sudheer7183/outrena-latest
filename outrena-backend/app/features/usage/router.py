"""
usage.py — Per-user / per-tenant / per-manager / per-platform usage + cost.

Endpoints:

  GET  /usage/me                      → current user's own usage + cost (REP+)
  GET  /usage/user/{user_id}          → specific user's usage (MANAGER+)
  GET  /usage/tenant                  → tenant rollup (MANAGER+)
  GET  /usage/manager                 → per-user breakdown (MANAGER+)
  GET  /usage/platform                → cross-tenant rollup (SUPER_ADMIN)
  GET  /usage/cost-table              → current cost table (SUPER_ADMIN)
  PUT  /usage/cost-table              → update cost table (SUPER_ADMIN)

Period format: "YYYY-MM" (monthly, default = current month) or "YYYY-MM-DD"
(daily). The service converts the period to a (start, end) window.

For SUPER_ADMIN platform-wide rollups, the service queries every active
tenant schema on a fresh session per tenant (search_path isolation).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_db_public
from app.api.security import require_role
from app.core.database import AsyncSessionLocal
from app.schemas.auth import Role, TokenPayload
from app.features.usage.cost_service import CostService
from app.features.usage.service import UsageService, _period_bounds

router = APIRouter(prefix="/usage", tags=["Usage & Cost"])
_service = UsageService()
_cost = CostService()


# ── Inline response schemas (app/schemas/* is shared with other agents —
#    keep these local to avoid stepping on ownership boundaries).
# ─────────────────────────────────────────────────────────────────────────


class UsageBreakdownRow(BaseModel):
    event_type: str
    provider: str | None = None
    total_quantity: int
    total_cost_cents: int
    event_count: int


class UsageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: str | None = None
    period_start: str
    period_end: str
    breakdown: list[UsageBreakdownRow] = Field(default_factory=list)
    total_cost_cents: int = 0


class ManagerUsageRow(BaseModel):
    user_id: str
    total_quantity: int
    total_cost_cents: int
    event_count: int
    event_types: int


class ManagerUsageResponse(BaseModel):
    period_start: str
    period_end: str
    users: list[ManagerUsageRow]


class PlatformTenantRow(BaseModel):
    tenant_slug: str
    total_cost_cents: int
    event_count: int


class PlatformUsageResponse(BaseModel):
    period_start: str
    period_end: str
    total_cost_cents: int
    total_event_count: int
    per_tenant: list[PlatformTenantRow]


class CostTableResponse(BaseModel):
    cost_table: dict[str, Any]


class CostTableUpdateRequest(BaseModel):
    llm: dict[str, dict[str, dict[str, float]]] | None = None
    enrichment: dict[str, float] | None = None
    linkedin: dict[str, float] | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────


def _resolve_period(period: str | None) -> tuple[str, datetime, datetime]:
    """Return ``(period, period_start, period_end)`` for a query param."""
    p = (period or "").strip() or datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        start, end = _period_bounds(p)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return p, start, end


@router.get("/me", response_model=UsageResponse)
async def get_my_usage(
    request: Request,
    period: str | None = Query(default=None, description="YYYY-MM or YYYY-MM-DD (default: current month)"),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> UsageResponse:
    """Current user's own usage + cost breakdown for the period."""
    _p, start, end = _resolve_period(period)
    payload = await _service.get_user_usage(db, token.sub, start, end)
    return UsageResponse(**payload)


@router.get("/user/{user_id}", response_model=UsageResponse)
async def get_user_usage(
    user_id: str,
    period: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> UsageResponse:
    """Specific user's usage (MANAGER+)."""
    _p, start, end = _resolve_period(period)
    payload = await _service.get_user_usage(db, user_id, start, end)
    return UsageResponse(**payload)


@router.get("/tenant", response_model=UsageResponse)
async def get_tenant_usage(
    period: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> UsageResponse:
    """Tenant-level rollup for the period (MANAGER+)."""
    _p, start, end = _resolve_period(period)
    payload = await _service.get_tenant_usage(db, start, end)
    return UsageResponse(**payload)


@router.get("/manager", response_model=ManagerUsageResponse)
async def get_manager_usage(
    period: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> ManagerUsageResponse:
    """Per-user breakdown for the manager dashboard (MANAGER+)."""
    _p, start, end = _resolve_period(period)
    rows = await _service.get_manager_usage(db, start, end)
    return ManagerUsageResponse(
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        users=[ManagerUsageRow(**r) for r in rows],
    )


@router.get("/platform", response_model=PlatformUsageResponse)
async def get_platform_usage(
    request: Request,
    period: str | None = Query(default=None),
    token: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> PlatformUsageResponse:
    """Cross-tenant rollup (SUPER_ADMIN only).

    Bypasses the per-tenant search_path lock — queries every active
    tenant schema on a fresh session per tenant.
    """
    _p, start, end = _resolve_period(period)
    payload = await _service.get_platform_usage(start, end)
    return PlatformUsageResponse(
        period_start=payload["period_start"],
        period_end=payload["period_end"],
        total_cost_cents=payload["total_cost_cents"],
        total_event_count=payload["total_event_count"],
        per_tenant=[PlatformTenantRow(**t) for t in payload["per_tenant"]],
    )


@router.get("/cost-table", response_model=CostTableResponse)
async def get_cost_table(
    token: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> CostTableResponse:
    """Return the current effective cost table (SUPER_ADMIN only)."""
    return CostTableResponse(cost_table=_cost.get_cost_table())


class CostSummaryRebuildResponse(BaseModel):
    """Result of a /usage/rebuild-cost-summaries invocation."""
    period: str
    per_tenant: dict[str, int] = Field(default_factory=dict)


@router.post(
    "/rebuild-cost-summaries",
    response_model=CostSummaryRebuildResponse,
    status_code=200,
)
async def rebuild_cost_summaries(
    period: str | None = Query(
        default=None,
        description="YYYY-MM or YYYY-MM-DD (default: current month). "
        "Materializes cost_summaries rows for every active tenant.",
    ),
    token: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> CostSummaryRebuildResponse:
    """Manually trigger the nightly cost-summary roll-up (SUPER_ADMIN).

    FIX-BE-1 / HIGH 7 (re-verification): UsageService.rebuild_cost_summaries
    + rebuild_all_tenants were defined but only invoked by the nightly
    Celery beat task (app.worker.celery_app:usage.rebuild_cost_summaries).
    This endpoint exposes the same operation for ad-hoc invocation (e.g.
    after back-filling usage_events rows or testing a cost-table change).

    Idempotent: existing rows for the period are DELETEd before re-insert
    (per UsageService.rebuild_cost_summaries).
    """
    p = (period or "").strip() or datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        # Validate the period shape without using the bounds directly.
        _start, _end = _period_bounds(p)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    per_tenant = await _service.rebuild_all_tenants(p)
    return CostSummaryRebuildResponse(period=p, per_tenant=per_tenant)


@router.put("/cost-table", response_model=CostTableResponse)
async def update_cost_table(
    body: CostTableUpdateRequest,
    db: AsyncSession = Depends(get_db_public),
    token: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> CostTableResponse:
    """Upsert per-(provider, model) cost overrides into public.cost_config.

    SUPER_ADMIN only. Existing rows are updated (ON CONFLICT). The
    effective cost table is re-read after the update and returned.
    """
    updates: dict[str, Any] = {}
    if body.llm is not None:
        updates["llm"] = body.llm
    if body.enrichment is not None:
        updates["enrichment"] = body.enrichment
    if body.linkedin is not None:
        updates["linkedin"] = body.linkedin
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of {llm, enrichment, linkedin} must be provided.",
        )
    await _cost.update_cost_table(db, updates)
    # Re-read the merged cost table (defaults + env + DB overrides)
    return CostTableResponse(cost_table=_cost.get_cost_table())


__all__ = ["router"]
