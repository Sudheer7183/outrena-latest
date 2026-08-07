"""
prompt_management.py — Phase 2 /api/v1/prompts router.

Endpoints:
  GET    /prompts              list all PromptTemplate rows
  POST   /prompts/reset        re-seed from prompt_defs (defers to PromptService)
  GET    /prompts/{key}        get one by key
  PUT    /prompts/{key}        update template body

Role gate: Role.TENANT_ADMIN.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.prompt_management import (
    PromptResetResponse,
    PromptResponse,
    PromptUpdate,
)
from app.features.prompt_management.service import PromptManagementService

router = APIRouter(prefix="/prompts", tags=["Prompt Management"])
_service = PromptManagementService()


@router.get("", response_model=list[PromptResponse])
async def list_prompts(
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> list[PromptResponse]:
    items = await _service.list_prompts(db, category=category)
    return [PromptResponse.model_validate(i) for i in items]


# Static route declared BEFORE /{key} (Pitfall #7).
@router.post("/reset", response_model=PromptResetResponse)
async def reset_prompts(
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> PromptResetResponse:
    count = await _service.reset_all(db)
    return PromptResetResponse(
        resetCount=count,
        message=f"Reset {count} prompt template(s).",
    )


@router.get("/{key}", response_model=PromptResponse)
async def get_prompt(
    key: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> PromptResponse:
    item = await _service.get_by_key(db, key)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt not found.")
    return PromptResponse.model_validate(item)


@router.put("/{key}", response_model=PromptResponse)
async def update_prompt(
    key: str,
    body: PromptUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> PromptResponse:
    item = await _service.update_template(db, key, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt not found.")
    return PromptResponse.model_validate(item)


__all__ = ["router"]
