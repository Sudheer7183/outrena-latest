"""flow_templates/schemas.py — Pydantic models for the flow_templates feature."""
from __future__ import annotations

from pydantic import BaseModel
from typing import Optional


class FlowTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    source_platforms: list[str]
    enrichment_platforms: list[str]
    gate_config: dict
    gate_strictness: str   # strict, medium, loose
    recommended_for: str

    class Config:
        from_attributes = True


class FlowTemplateListResponse(BaseModel):
    items: list[FlowTemplateResponse]
    total: int


class FlowTemplateCreateRequest(BaseModel):
    name: str
    description: str = ""
    source_platforms: list[str] = []
    enrichment_platforms: list[str] = []
    gate_config: dict = {}
    gate_strictness: str = "medium"
    recommended_for: str = ""


class FlowTemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_platforms: Optional[list[str]] = None
    enrichment_platforms: Optional[list[str]] = None
    gate_config: Optional[dict] = None
    gate_strictness: Optional[str] = None
    recommended_for: Optional[str] = None


class FlowTemplateCloneRequest(BaseModel):
    template_id: str
    new_name: Optional[str] = None


class FlowTemplateCloneResponse(BaseModel):
    success: bool
    flow_id: Optional[str] = None
    name: Optional[str] = None
    error: Optional[str] = None
