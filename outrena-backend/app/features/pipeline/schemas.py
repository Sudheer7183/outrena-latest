"""pipeline/schemas.py — Pydantic models for the pipeline feature.

Extracted from router.py to avoid circular imports between router ↔ service.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class PipelineRunStageRequest(BaseModel):
    stage: str = Field(
        ..., description="Stage to run: thesis, signals, scoring, briefs, campaign"
    )
    icp_id: Optional[str] = None
    llm_config_id: Optional[str] = None
    # Stage-specific inputs
    product_name: Optional[str] = None
    target_industries: Optional[str] = None
    product_description: Optional[str] = None
    key_value_props: Optional[str] = None
    prospect_ids: Optional[list[str]] = None


class PipelineRunStageResponse(BaseModel):
    success: bool
    stage: str
    result: Optional[dict] = None
    error: Optional[str] = None


class PipelineStatusResponse(BaseModel):
    stages_completed: list[str]
    current_stage: Optional[str] = None
    thesis_result: Optional[dict] = None
    signals_result: Optional[dict] = None
    scoring_result: Optional[dict] = None
    briefs_result: Optional[dict] = None
