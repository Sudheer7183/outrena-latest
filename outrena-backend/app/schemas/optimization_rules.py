"""optimization_rules.py — Auto-trigger rule + action log contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OptimizationRuleCreate(BaseModel):
    name: str
    description: str | None = None
    metric: str  # bounceRate | replyRate | openRate | positiveReplyRate
    operator: str  # gt | lt | gte | lte | eq
    threshold: float
    action: str  # pause | notify | adjust_send_volume
    isActive: bool = True
    campaignId: str | None = None


class OptimizationRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    metric: str | None = None
    operator: str | None = None
    threshold: float | None = None
    action: str | None = None
    isActive: bool | None = None


class OptimizationRuleResponse(BaseModel):
    id: str
    name: str
    description: str | None
    metric: str
    operator: str
    threshold: float
    action: str
    isActive: bool
    campaignId: str | None
    lastEvaluatedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class OptimizationActionResponse(BaseModel):
    id: str
    ruleId: str
    campaignId: str | None
    metric: str
    observedValue: float
    threshold: float
    action: str
    result: str | None
    executedAt: datetime

    model_config = {"from_attributes": True}


class OptimizationEvaluateResponse(BaseModel):
    """Body for POST /optimization-rules/evaluate — run the engine once."""
    triggered: list[OptimizationActionResponse]
    skipped: int


__all__ = [
    "OptimizationRuleCreate",
    "OptimizationRuleUpdate",
    "OptimizationRuleResponse",
    "OptimizationActionResponse",
    "OptimizationEvaluateResponse",
]
