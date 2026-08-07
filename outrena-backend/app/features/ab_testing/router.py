"""
ab_testing.py — Phase 3 /api/v1/ab-testing router.

Endpoints:
  GET    /ab-testing                   list tests (optional campaignId filter)
  POST   /ab-testing                   create
  GET    /ab-testing/email             list EmailAbTest rows
  GET    /ab-testing/{id}              fetch one
  PUT    /ab-testing/{id}              update (status, startedAt, endedAt)
  DELETE /ab-testing/{id}              delete
  POST   /ab-testing/{id}/start        set status=running + startedAt
  GET    /ab-testing/{id}/significance compute two-proportion z-test
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.ab_testing import (
    AbTestCreate,
    AbTestResponse,
    AbTestUpdate,
    EmailAbTestResponse,
    SignificanceResult,
)
from app.schemas.auth import Role
from app.features.ab_testing.service import AbTestingService

router = APIRouter(prefix="/ab-testing", tags=["A/B Testing"])
_service = AbTestingService()


@router.get("", response_model=list[AbTestResponse])
async def list_tests(
    campaign_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[AbTestResponse]:
    items = await _service.list_tests(db, campaign_id=campaign_id)
    return [AbTestResponse.model_validate(i) for i in items]


@router.post("", response_model=AbTestResponse, status_code=201)
async def create_test(
    body: AbTestCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> AbTestResponse:
    item = await _service.create(db, body)
    return AbTestResponse.model_validate(item)


@router.get("/email", response_model=list[EmailAbTestResponse])
async def list_email_tests(
    campaign_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[EmailAbTestResponse]:
    items = await _service.list_email_ab_tests(db, campaign_id=campaign_id)
    return [EmailAbTestResponse.model_validate(i) for i in items]


@router.get("/{test_id}", response_model=AbTestResponse)
async def get_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> AbTestResponse:
    item = await _service.get(db, test_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
    return AbTestResponse.model_validate(item)


@router.put("/{test_id}", response_model=AbTestResponse)
async def update_test(
    test_id: str,
    body: AbTestUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> AbTestResponse:
    item = await _service.update(db, test_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
    return AbTestResponse.model_validate(item)


@router.delete("/{test_id}", response_model=None, response_class=Response, status_code=204)
async def delete_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, test_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{test_id}/start", response_model=AbTestResponse)
async def start_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> AbTestResponse:
    item = await _service.start(db, test_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
    return AbTestResponse.model_validate(item)


@router.get("/{test_id}/significance", response_model=SignificanceResult)
async def significance(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> SignificanceResult:
    result = await _service.significance(db, test_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
    return result
