"""flow_templates/schemas.py — Pydantic models for the flow_templates feature.

Extracted from router.py to avoid circular imports between router ↔ service.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class FlowTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    source_platforms: list[str]
    enrichment_platforms: list[str]
    gate_config: dict
    gate_strictness: str  # strict, medium, loose
    recommended_for: str

    class Config:
        from_attributes = True


class FlowTemplateListResponse(BaseModel):
    items: list[FlowTemplateResponse]
    total: int


class FlowTemplateCloneRequest(BaseModel):
    template_id: str
    new_name: Optional[str] = None


class FlowTemplateCloneResponse(BaseModel):
    success: bool
    flow_id: Optional[str] = None
    error: Optional[str] = None
