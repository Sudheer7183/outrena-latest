"""
pipeline/router.py — 5-stage GTM workflow orchestrator API.

Stages: Thesis → Signals → Scoring → Briefs → Campaign

Endpoints (all under /pipeline):
  POST /pipeline/run-stage   Run a single pipeline stage
  GET  /pipeline/status      Get pipeline status for an ICP
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.features.pipeline.schemas import (
    PipelineRunStageRequest,
    PipelineRunStageResponse,
    PipelineStatusResponse,
)
from app.features.pipeline.service import PipelineService

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])
_service = PipelineService()


@router.post("/run-stage", response_model=PipelineRunStageResponse)
async def run_pipeline_stage(
    body: PipelineRunStageRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> PipelineRunStageResponse:
    """Run a single pipeline stage (thesis, signals, scoring, briefs, campaign)."""
    result = await _service.run_stage(db, body)
    if not result.success:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, result.error)
    return result


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    icp_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> PipelineStatusResponse:
    """Get pipeline status for a given ICP (which stages have been completed)."""
    return await _service.get_status(db, icp_id=icp_id)


__all__ = ["router"]
