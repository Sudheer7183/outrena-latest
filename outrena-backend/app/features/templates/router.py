"""
templates.py — Phase 3 /api/v1/templates router (email templates).

Endpoints:
  GET    /templates              list (filter by category)
  POST   /templates              create
  GET    /templates/{id}         fetch one
  PUT    /templates/{id}         update
  DELETE /templates/{id}         delete
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.templates import (
    EmailTemplateCreate,
    EmailTemplateResponse,
    EmailTemplateUpdate,
)
from app.features.templates.service import EmailTemplateService

router = APIRouter(prefix="/templates", tags=["Email Templates"])
_service = EmailTemplateService()


@router.get("", response_model=list[EmailTemplateResponse])
async def list_templates(
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[EmailTemplateResponse]:
    items = await _service.list(
        db, category=category, limit=limit, offset=offset
    )
    return [EmailTemplateResponse.model_validate(i) for i in items]


@router.post("", response_model=EmailTemplateResponse, status_code=201)
async def create_template(
    body: EmailTemplateCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> EmailTemplateResponse:
    item = await _service.create(db, body)
    return EmailTemplateResponse.model_validate(item)


@router.get("/{template_id}", response_model=EmailTemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> EmailTemplateResponse:
    item = await _service.get(db, template_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found.")
    return EmailTemplateResponse.model_validate(item)


@router.put("/{template_id}", response_model=EmailTemplateResponse)
async def update_template(
    template_id: str,
    body: EmailTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> EmailTemplateResponse:
    item = await _service.update(db, template_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found.")
    return EmailTemplateResponse.model_validate(item)


@router.delete("/{template_id}", response_model=None, response_class=Response, status_code=204)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, template_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
