"""
flow_templates/router.py — CRUD + clone endpoints for flow templates.

Templates are pre-built flow configurations (Enterprise ABM, Partner
Recruitment, PLG Volume) that can be cloned into real ProspectingFlow rows.

Endpoints (all under /flow-templates):
  GET  /flow-templates              List all built-in templates
  GET  /flow-templates/{template_id} Get a single template
  POST /flow-templates/clone        Clone a template into a new ProspectingFlow
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.features.flow_templates.schemas import (
    FlowTemplateResponse,
    FlowTemplateListResponse,
    FlowTemplateCloneRequest,
    FlowTemplateCloneResponse,
)
from app.features.flow_templates.service import FlowTemplateService

router = APIRouter(prefix="/flow-templates", tags=["Flow Templates"])
_service = FlowTemplateService()


@router.get("", response_model=FlowTemplateListResponse)
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowTemplateListResponse:
    """List all built-in flow templates."""
    items = await _service.list_templates(db)
    return FlowTemplateListResponse(items=items, total=len(items))


@router.get("/{template_id}", response_model=FlowTemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowTemplateResponse:
    """Get a single flow template by ID."""
    item = await _service.get_template(db, template_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return item


@router.post("/clone", response_model=FlowTemplateCloneResponse)
async def clone_template(
    body: FlowTemplateCloneRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowTemplateCloneResponse:
    """Clone a built-in template into a new ProspectingFlow."""
    result = await _service.clone_template(db, body)
    if not result.success:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, result.error)
    return result


__all__ = ["router"]
