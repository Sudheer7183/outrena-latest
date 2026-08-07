"""signals.py — Signal + monitor + lead-score contracts (60s timeout)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator


class SignalResponse(BaseModel):
    id: str
    prospectId: str | None
    type: str
    summary: str
    detail: str | None
    source: str
    confidence: float
    detectedAt: datetime
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class SignalMonitorCreate(BaseModel):
    """BUG-17 FIX: Accept frontend 'type' field as alias for signalType."""

    model_config = {"extra": "ignore"}

    name: str
    signalType: str = ""  # funding | hiring | news | product_launch | leadership_change
    conditions: dict = {}
    isActive: bool = True

    @field_validator("conditions", mode="before")
    @classmethod
    def _parse_conditions(cls, v: object) -> dict:
        """BUG-26 FIX: Handle conditions as JSON string or dict."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        if isinstance(v, dict):
            return v
        return {}

    @model_validator(mode="before")
    @classmethod
    def _normalise_type(cls, values: object) -> object:
        """BUG-17 FIX: Accept 'type' as alias for 'signalType'."""
        if isinstance(values, dict):
            if not values.get("signalType") and values.get("type"):
                values["signalType"] = values["type"]
        return values


class SignalMonitorUpdate(BaseModel):
    name: str | None = None
    conditions: dict | None = None
    isActive: bool | None = None


class SignalMonitorResponse(BaseModel):
    id: str
    name: str
    signalType: str
    conditions: dict
    isActive: bool
    lastRunAt: datetime | None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}

    @field_validator("conditions", mode="before")
    @classmethod
    def _parse_conditions(cls, v: object) -> dict:
        """BUG-26 FIX: Handle conditions stored as JSON string."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        if isinstance(v, dict):
            return v
        return {}


class LeadScoreRequest(BaseModel):
    """Body for POST /signals/lead-score — compute ICP-fit + urgency."""
    prospectId: str
    timeoutSeconds: int = 60  # 60s timeout per Phase 3 deliverable


class LeadScoreResponse(BaseModel):
    prospectId: str
    icpFitScore: int  # 0-100
    urgencyTier: str  # P0 | P1 | P2
    urgencyDeadline: datetime | None
    scoreBreakdown: dict
    computedAt: datetime


class SignalsScanRequest(BaseModel):
    prospectIds: list[str] | None = None
    signalTypes: list[str] | None = None


class SignalsScanResponse(BaseModel):
    scanned: int
    detected: int
    signals: list[SignalResponse]


# ── Lead Score Batch ─────────────────────────────────────────────────────────

class LeadScoreBatchRequest(BaseModel):
    """Body for POST /signals/lead-score-batch — batch LLM scoring."""
    prospect_ids: list[str] | None = None
    score_all: bool = False
    llm_config_id: str | None = None


class LeadScoreBatchResult(BaseModel):
    prospect_id: str
    score: int
    tier: str
    reason: str


class LeadScoreBatchResponse(BaseModel):
    success: bool
    scored: int = 0
    scores: list[LeadScoreBatchResult] = []
    error: str | None = None


class LeadScoreStatsResponse(BaseModel):
    """Aggregated lead score statistics."""
    tier_distribution: dict[str, int] = {}
    by_seniority: dict[str, dict] = {}
    total_scored: int = 0


__all__ = [
    "SignalResponse",
    "SignalMonitorCreate",
    "SignalMonitorUpdate",
    "SignalMonitorResponse",
    "LeadScoreRequest",
    "LeadScoreResponse",
    "SignalsScanRequest",
    "SignalsScanResponse",
    "LeadScoreBatchRequest",
    "LeadScoreBatchResult",
    "LeadScoreBatchResponse",
    "LeadScoreStatsResponse",
]
