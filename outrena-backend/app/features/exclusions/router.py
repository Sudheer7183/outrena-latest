"""
exclusion_rules.py — Phase 3 /api/v1/exclusion-rules router.

Endpoints:
  GET    /exclusion-rules                list (filter by type, active_only)
  POST   /exclusion-rules                create
  POST   /exclusion-rules/bulk           bulk upsert (skip duplicates)
  GET    /exclusion-rules/{id}           fetch one
  PUT    /exclusion-rules/{id}           update
  DELETE /exclusion-rules/{id}           delete
  POST   /exclusion-rules/check          check a prospect against the list
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.exclusion_rules import (
    BulkExclusionRequest,
    BulkExclusionResponse,
    ExclusionRuleCreate,
    ExclusionRuleResponse,
    ExclusionRuleUpdate,
)
from app.features.exclusions.service import ExclusionRuleService

router = APIRouter(prefix="/exclusion-rules", tags=["Exclusion Rules"])
_service = ExclusionRuleService()


@router.get("", response_model=list[ExclusionRuleResponse])
async def list_rules(
    type_filter: str | None = Query(default=None, alias="type"),
    active_only: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[ExclusionRuleResponse]:
    items = await _service.list(
        db, type_filter=type_filter, active_only=active_only,
        limit=limit, offset=offset,
    )
    return [ExclusionRuleResponse.model_validate(i) for i in items]


@router.post("", response_model=ExclusionRuleResponse, status_code=201)
async def create_rule(
    body: ExclusionRuleCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> ExclusionRuleResponse:
    item = await _service.create(db, body)
    return ExclusionRuleResponse.model_validate(item)


@router.post("/bulk", response_model=BulkExclusionResponse)
async def bulk_upsert(
    body: BulkExclusionRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> BulkExclusionResponse:
    return await _service.bulk_upsert(db, body)


@router.post("/check", response_model=list[ExclusionRuleResponse])
async def check_prospect(
    email: str = "",
    domain: str | None = None,
    company: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[ExclusionRuleResponse]:
    matches = await _service.check_prospect(db, email, domain, company)
    return [ExclusionRuleResponse.model_validate(r) for r in matches]


@router.get("/{rule_id}", response_model=ExclusionRuleResponse)
async def get_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> ExclusionRuleResponse:
    item = await _service.get(db, rule_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exclusion rule not found.")
    return ExclusionRuleResponse.model_validate(item)


@router.put("/{rule_id}", response_model=ExclusionRuleResponse)
async def update_rule(
    rule_id: str,
    body: ExclusionRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> ExclusionRuleResponse:
    item = await _service.update(db, rule_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exclusion rule not found.")
    return ExclusionRuleResponse.model_validate(item)


@router.delete("/{rule_id}", response_model=None, response_class=Response, status_code=204)
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, rule_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exclusion rule not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
