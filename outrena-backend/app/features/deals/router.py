"""
deals.py — Phase 3 /api/v1/deals router.

Endpoints:
  GET    /deals                 list (filter by stage / prospectId)
  POST   /deals                 create
  GET    /deals/kanban          all deals grouped by stage (Kanban UI)
  GET    /deals/{id}            fetch one
  PUT    /deals/{id}            update
  DELETE /deals/{id}            delete
  GET    /deals/{id}/health     compute + persist Deal Health
  POST   /deals/{id}/deal-suggest  LLM-suggested next step
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.deals import (
    DealCreate,
    DealHealthResponse,
    DealResponse,
    DealSuggestResponse,
    DealUpdate,
    KanbanBoardResponse,
)
from app.features.deals.service import DealService

router = APIRouter(prefix="/deals", tags=["Deals"])
_service = DealService()


@router.get("/kanban", response_model=KanbanBoardResponse)
async def kanban(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> KanbanBoardResponse:
    return await _service.kanban(db)


@router.get("", response_model=list[DealResponse])
async def list_deals(
    stage: str | None = Query(default=None),
    prospect_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[DealResponse]:
    items = await _service.list(
        db, stage=stage, prospect_id=prospect_id, limit=limit, offset=offset
    )
    return [DealResponse.model_validate(i) for i in items]


@router.post("", response_model=DealResponse, status_code=201)
async def create_deal(
    body: DealCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> DealResponse:
    item = await _service.create(db, body)
    return DealResponse.model_validate(item)


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> DealResponse:
    item = await _service.get(db, deal_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deal not found.")
    return DealResponse.model_validate(item)


@router.put("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: str,
    body: DealUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> DealResponse:
    item = await _service.update(db, deal_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deal not found.")
    return DealResponse.model_validate(item)


@router.delete("/{deal_id}", response_model=None, response_class=Response, status_code=204)
async def delete_deal(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, deal_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deal not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{deal_id}/health", response_model=DealHealthResponse)
async def deal_health(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> DealHealthResponse:
    result = await _service.compute_health(db, deal_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deal not found.")
    return result


@router.post("/{deal_id}/deal-suggest", response_model=DealSuggestResponse)
async def deal_suggest(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> DealSuggestResponse:
    result = await _service.suggest_next_step(db, deal_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deal not found.")
    return result


# ── CRM Export + CrmSyncLog (Help Guide §Deals — "Push to CRM") ──────────────

@router.post("/crm-export")
async def crm_export(
    db: AsyncSession = Depends(get_db),
    token_payload: object = Depends(require_role(Role.REP)),
) -> Response:
    """
    Push-to-CRM: streams an RFC-4180 CSV of all deals AND writes a
    CrmSyncLog row recording the export (deal count, stage breakdown,
    source breakdown, exported by, exported at).

    CSV columns (per Help Guide §Deals):
      Title, Stage, Value, Health Status, Health Reason,
      Source Intent, Next Step, Created At.

    The CrmSyncLog audit trail lets sales ops prove that a specific deal
    set was exported on a specific date by a specific user.
    """
    import csv
    import io
    import json as _json
    from datetime import datetime, timezone

    from sqlalchemy import select, text

    from app.models.campaign_models import CrmSyncLog, Deal
    from app.schemas.auth import TokenPayload

    user_id: str = getattr(token_payload, "sub", "unknown")

    result = await db.execute(select(Deal).order_by(Deal.createdAt.desc()))
    deals = list(result.scalars().all())

    # Build CSV
    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM for Excel
    writer = csv.writer(buf, dialect="excel")
    writer.writerow(
        ["Title", "Stage", "Value", "Health Status", "Health Reason",
         "Source Intent", "Next Step", "Created At"]
    )
    stage_count: dict[str, int] = {}
    source_count: dict[str, int] = {}
    for d in deals:
        stage_count[d.stage] = stage_count.get(d.stage, 0) + 1
        source = getattr(d, "sourceIntent", None) or "unknown"
        source_count[source] = source_count.get(source, 0) + 1
        writer.writerow([
            d.title,
            d.stage,
            d.value,
            getattr(d, "healthStatus", "") or "",
            getattr(d, "healthReason", "") or "",
            source,
            getattr(d, "nextStep", "") or "",
            d.createdAt.isoformat() if d.createdAt else "",
        ])

    # Write audit log
    log = CrmSyncLog(
        exportedByUserId=user_id,
        dealCount=len(deals),
        crmProvider="manual",
        stageBreakdown=_json.dumps(stage_count),
        sourceBreakdown=_json.dumps(source_count),
        exportedAt=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.commit()

    from datetime import date
    filename = f"deals-crm-export-{date.today().isoformat()}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
