"""
optimization_rules.py — Phase 3 /api/v1/optimization-rules router.

Endpoints:
  GET    /optimization-rules              list rules (filter activeOnly / campaignId)
  POST   /optimization-rules              create
  POST   /optimization-rules/evaluate     run the engine once
  GET    /optimization-rules/actions      list recent fired actions
  GET    /optimization-rules/{id}         fetch one
  PUT    /optimization-rules/{id}         update
  DELETE /optimization-rules/{id}         delete
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.optimization_rules import (
    OptimizationActionResponse,
    OptimizationEvaluateResponse,
    OptimizationRuleCreate,
    OptimizationRuleResponse,
    OptimizationRuleUpdate,
)
from app.features.optimization.service import OptimizationRuleService

router = APIRouter(prefix="/optimization-rules", tags=["Optimization Rules"])
_service = OptimizationRuleService()


@router.get("", response_model=list[OptimizationRuleResponse])
async def list_rules(
    active_only: bool = Query(default=False),
    campaign_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[OptimizationRuleResponse]:
    items = await _service.list_rules(
        db, active_only=active_only, campaign_id=campaign_id
    )
    return [OptimizationRuleResponse.model_validate(i) for i in items]


@router.post("", response_model=OptimizationRuleResponse, status_code=201)
async def create_rule(
    body: OptimizationRuleCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> OptimizationRuleResponse:
    item = await _service.create_rule(db, body)
    return OptimizationRuleResponse.model_validate(item)


@router.post("/evaluate", response_model=OptimizationEvaluateResponse)
async def evaluate(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> OptimizationEvaluateResponse:
    return await _service.evaluate(db)


@router.get("/actions", response_model=list[OptimizationActionResponse])
async def list_actions(
    rule_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[OptimizationActionResponse]:
    items = await _service.list_actions(db, rule_id=rule_id, limit=limit)
    return [OptimizationActionResponse.model_validate(i) for i in items]


@router.get("/{rule_id}", response_model=OptimizationRuleResponse)
async def get_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> OptimizationRuleResponse:
    item = await _service.get_rule(db, rule_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Optimization rule not found.")
    return OptimizationRuleResponse.model_validate(item)


@router.put("/{rule_id}", response_model=OptimizationRuleResponse)
async def update_rule(
    rule_id: str,
    body: OptimizationRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> OptimizationRuleResponse:
    item = await _service.update_rule(db, rule_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Optimization rule not found.")
    return OptimizationRuleResponse.model_validate(item)


@router.delete("/{rule_id}", response_model=None, response_class=Response, status_code=204)
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete_rule(db, rule_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Optimization rule not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
