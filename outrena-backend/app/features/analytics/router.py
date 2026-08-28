# """
# analytics.py — Phase 3 /api/v1/analytics router.

# Endpoints:
#   GET    /analytics/metrics              list campaign metrics (optional filter)
#   GET    /analytics/campaign-results     fetch latest post-mortem for a campaign
#   POST   /analytics/campaign-results     generate + persist a post-mortem
#   POST   /analytics/diagnose             run the 5-layer closed-loop diagnostic
#   GET    /analytics/time-series          daily rollup for the last N days
# """
# from __future__ import annotations

# from fastapi import APIRouter, Depends, HTTPException, Query, status
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import require_role
# from app.schemas.analytics import (
#     CampaignMetricResponse,
#     CampaignResultResponse,
#     DiagnoseRequest,
#     DiagnoseResponse,
#     TimeSeriesResponse,
# )
# from app.schemas.auth import Role
# from app.features.analytics.service import AnalyticsService

# router = APIRouter(prefix="/analytics", tags=["Analytics"])
# _service = AnalyticsService()


# @router.get("/metrics", response_model=list[CampaignMetricResponse])
# async def list_metrics(
#     campaign_id: str | None = Query(default=None),
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> list[CampaignMetricResponse]:
#     # Task 3-a / FIX 1: list_metrics now returns CampaignMetricResponse
#     # DTOs directly (aggregated from Sequence rows) — no ORM model_validate
#     # step needed. The router returns them as-is.
#     return await _service.list_metrics(db, campaign_id)


# @router.get("/campaign-results", response_model=CampaignResultResponse | None)
# async def get_campaign_result(
#     campaign_id: str = Query(...),
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> CampaignResultResponse | None:
#     item = await _service.get_result(db, campaign_id)
#     return CampaignResultResponse.model_validate(item) if item else None


# @router.post("/campaign-results", response_model=CampaignResultResponse)
# async def generate_campaign_result(
#     campaign_id: str = Query(...),
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.MANAGER)),
# ) -> CampaignResultResponse:
#     item = await _service.generate_result(db, campaign_id)
#     if item is None:
#         raise HTTPException(
#             status.HTTP_404_NOT_FOUND,
#             "No metrics found for this campaign — cannot generate result.",
#         )
#     return CampaignResultResponse.model_validate(item)


# @router.post("/diagnose", response_model=DiagnoseResponse)
# async def diagnose(
#     body: DiagnoseRequest,
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> DiagnoseResponse:
#     return await _service.diagnose(db, body.campaignId)


# @router.get("/time-series", response_model=TimeSeriesResponse)
# async def time_series(
#     days: int = Query(default=30, ge=1, le=365),
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> TimeSeriesResponse:
#     return await _service.time_series(db, days=days)


# # ── FR-062: cohort breakdowns by ICP / segment / timeframe ──────────────────


# @router.get("/cohorts")
# async def cohort_breakdown(
#     by: str = "icp",
#     days: int = 30,
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> dict:
#     """
#     Funnel metrics broken down by cohort (FR-062).

#     ``by=icp``     groups by the prospect's linked IcpProfile.
#     ``by=segment`` groups by prospect status (new/enriched/qualified/...).
#     ``days``       bounds the timeframe (sentAt within the last N days).
#     """
#     from sqlalchemy import text as _text

#     if by not in ("icp", "segment"):
#         raise HTTPException(
#             status_code=422, detail="'by' must be 'icp' or 'segment'."
#         )
#     days = max(1, min(days, 365))

#     if by == "icp":
#         group_expr = 'COALESCE(i.name, \'(no ICP)\')'
#         join = (
#             'JOIN "Prospect" p ON p.id = s."prospectId" '
#             'LEFT JOIN "IcpProfile" i ON i.id = p."icpProfileId"'
#         )
#     else:
#         group_expr = "COALESCE(p.status, '(unknown)')"
#         join = 'JOIN "Prospect" p ON p.id = s."prospectId"'

#     rows = (
#         await db.execute(
#             _text(
#                 f"SELECT {group_expr} AS cohort, "
#                 "  COUNT(*) FILTER (WHERE s.\"sentAt\" IS NOT NULL) AS sent, "
#                 "  COUNT(*) FILTER (WHERE s.\"openedAt\" IS NOT NULL) AS opened, "
#                 "  COUNT(*) FILTER (WHERE s.\"repliedAt\" IS NOT NULL) AS replied, "
#                 "  COUNT(*) FILTER (WHERE s.\"bouncedAt\" IS NOT NULL) AS bounced "
#                 f'FROM "Sequence" s {join} '
#                 "WHERE s.\"sentAt\" >= now() - make_interval(days => :days) "
#                 f"GROUP BY {group_expr} ORDER BY sent DESC"
#             ),
#             {"days": days},
#         )
#     ).all()

#     cohorts = []
#     for cohort, sent, opened, replied, bounced in rows:
#         sent = int(sent or 0)
#         cohorts.append(
#             {
#                 "cohort": cohort,
#                 "sent": sent,
#                 "opened": int(opened or 0),
#                 "replied": int(replied or 0),
#                 "bounced": int(bounced or 0),
#                 "replyRate": round(int(replied or 0) / sent, 4) if sent else 0.0,
#                 "openRate": round(int(opened or 0) / sent, 4) if sent else 0.0,
#             }
#         )
#     return {"by": by, "days": days, "cohorts": cohorts}
"""
analytics.py — Phase 3 /api/v1/analytics router.

Endpoints:
  GET    /analytics/metrics              list campaign metrics (optional filter)
  GET    /analytics/campaign-results     fetch latest post-mortem for a campaign
  POST   /analytics/campaign-results     generate + persist a post-mortem
  POST   /analytics/diagnose             run the 5-layer closed-loop diagnostic
  GET    /analytics/time-series          daily rollup for the last N days
  GET    /analytics/tracking-summary     tenant-wide sent/opened/replied/bounced summary
  GET    /analytics/cohorts              funnel breakdown by ICP or segment
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.analytics import (
    CampaignMetricResponse,
    CampaignResultResponse,
    DiagnoseRequest,
    DiagnoseResponse,
    TimeSeriesResponse,
    TrackingSummaryResponse,
)
from app.schemas.auth import Role
from app.features.analytics.service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])
_service = AnalyticsService()


@router.get("/metrics", response_model=list[CampaignMetricResponse])
async def list_metrics(
    campaign_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[CampaignMetricResponse]:
    return await _service.list_metrics(db, campaign_id)


@router.get("/campaign-results", response_model=CampaignResultResponse | None)
async def get_campaign_result(
    campaign_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> CampaignResultResponse | None:
    item = await _service.get_result(db, campaign_id)
    return CampaignResultResponse.model_validate(item) if item else None


@router.post("/campaign-results", response_model=CampaignResultResponse)
async def generate_campaign_result(
    campaign_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> CampaignResultResponse:
    item = await _service.generate_result(db, campaign_id)
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No metrics found for this campaign — cannot generate result.",
        )
    return CampaignResultResponse.model_validate(item)


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(
    body: DiagnoseRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> DiagnoseResponse:
    return await _service.diagnose(db, body.campaignId)


@router.get("/time-series", response_model=TimeSeriesResponse)
async def time_series(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> TimeSeriesResponse:
    return await _service.time_series(db, days=days)


# ── NEW: Tracking summary for Reply Inbox dashboard panel ────────────────────

@router.get("/tracking-summary", response_model=TrackingSummaryResponse)
async def tracking_summary(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> TrackingSummaryResponse:
    """Tenant-wide email tracking summary.

    Returns aggregated sent / opened / replied / bounced counts and rates
    for sequences sent within the last `days` days. Used by the Reply Inbox
    dashboard panel. No MailBridge call — reads local Sequence rows only.
    """
    return await _service.tracking_summary(db, days=days)


# ── FR-062: cohort breakdowns by ICP / segment / timeframe ──────────────────

@router.get("/cohorts")
async def cohort_breakdown(
    by: str = "icp",
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> dict:
    """
    Funnel metrics broken down by cohort (FR-062).

    ``by=icp``     groups by the prospect's linked IcpProfile.
    ``by=segment`` groups by prospect status (new/enriched/qualified/...).
    ``days``       bounds the timeframe (sentAt within the last N days).
    """
    from sqlalchemy import text as _text

    if by not in ("icp", "segment"):
        raise HTTPException(
            status_code=422, detail="'by' must be 'icp' or 'segment'."
        )
    days = max(1, min(days, 365))

    if by == "icp":
        group_expr = 'COALESCE(i.name, \'(no ICP)\')'
        join = (
            'JOIN "Prospect" p ON p.id = s."prospectId" '
            'LEFT JOIN "IcpProfile" i ON i.id = p."icpProfileId"'
        )
    else:
        group_expr = "COALESCE(p.status, '(unknown)')"
        join = 'JOIN "Prospect" p ON p.id = s."prospectId"'

    rows = (
        await db.execute(
            _text(
                f"SELECT {group_expr} AS cohort, "
                "  COUNT(*) FILTER (WHERE s.\"sentAt\" IS NOT NULL) AS sent, "
                "  COUNT(*) FILTER (WHERE s.\"openedAt\" IS NOT NULL) AS opened, "
                "  COUNT(*) FILTER (WHERE s.\"repliedAt\" IS NOT NULL) AS replied, "
                "  COUNT(*) FILTER (WHERE s.\"bouncedAt\" IS NOT NULL) AS bounced "
                f'FROM "Sequence" s {join} '
                "WHERE s.\"sentAt\" >= now() - make_interval(days => :days) "
                f"GROUP BY {group_expr} ORDER BY sent DESC"
            ),
            {"days": days},
        )
    ).all()

    cohorts = []
    for cohort, sent, opened, replied, bounced in rows:
        sent = int(sent or 0)
        cohorts.append(
            {
                "cohort": cohort,
                "sent": sent,
                "opened": int(opened or 0),
                "replied": int(replied or 0),
                "bounced": int(bounced or 0),
                "replyRate": round(int(replied or 0) / sent, 4) if sent else 0.0,
                "openRate": round(int(opened or 0) / sent, 4) if sent else 0.0,
            }
        )
    return {"by": by, "days": days, "cohorts": cohorts}