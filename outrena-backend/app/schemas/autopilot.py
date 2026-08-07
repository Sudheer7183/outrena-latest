"""
autopilot.py — Autopilot pipeline request / result / status contracts.

Phase 5 deliverable: a synchronous-Celery wrapper around the async
orchestrator that takes a campaign specification + ICP hint, sources N
prospects, generates a 7-touch email cadence for each, and returns a
campaign_id the caller can poll for completion (migration §6.3 L873-897).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Request ────────────────────────────────────────────────────────────────


class AutopilotRequest(BaseModel):
    """Body for POST /api/v1/autopilot — enqueue an autopilot pipeline run.

    The caller supplies enough sender/ICP context for the orchestrator to
    generate a coherent campaign; optional fields fall back to the tenant's
    default ICP / sender profile.

    BUG-09 FIX: Accepts frontend field names via model_validator:
      - productName  → campaign_name
      - icpDescription → icp_hint
    """

    model_config = ConfigDict(extra="ignore")

    campaign_name: str = Field(default="", min_length=0, max_length=200)
    target_count: int = Field(default=10, ge=1, le=500)
    icp_hint: str | None = Field(
        default=None,
        description="Free-text ICP description used for prospect sourcing + email tone.",
    )
    sender_role: str | None = None
    sender_company: str | None = None
    sender_offer: str | None = None
    proof_metric: str | None = None
    sender_product: str | None = None
    target_audience: str | None = None
    framework: str | None = Field(
        default=None,
        description="Optional copy framework override (AIDA, PAS, BAB, Value, Question, Breakup).",
    )
    schema_name: str = Field(
        default="public",
        description="Tenant schema to run the pipeline against (set by the API router).",
    )
    metadata: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_frontend_fields(cls, values: Any) -> Any:
        """BUG-09 FIX: Accept frontend camelCase field names."""
        if isinstance(values, dict):
            # productName → campaign_name
            if not values.get("campaign_name") and values.get("productName"):
                values["campaign_name"] = values["productName"]
            # icpDescription → icp_hint
            if not values.get("icp_hint") and values.get("icpDescription"):
                values["icp_hint"] = values["icpDescription"]
            # Ensure campaign_name has a fallback
            if not values.get("campaign_name"):
                values["campaign_name"] = "Autopilot Run"
        return values


# Backwards-compat alias for any caller that used the earlier name.
AutopilotCreateRequest = AutopilotRequest


# ── Result ─────────────────────────────────────────────────────────────────


class AutopilotResult(BaseModel):
    """Successful (or partially successful) pipeline run result."""

    campaign_id: str
    prospect_count: int
    sequence_count: int
    task_id: str
    status: Literal["PENDING", "STARTED", "SUCCESS", "FAILURE", "PARTIAL"] = "SUCCESS"
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


# 202 Accepted envelope used by POST /api/v1/autopilot.
class AutopilotCreateResponse(BaseModel):
    """202 Accepted response with the enqueued task_id."""

    task_id: str
    status: str = "PENDING"
    message: str = "Task enqueued."


# ── Status polling ──────────────────────────────────────────────────────────


class AutopilotStatusResponse(BaseModel):
    """Body for GET /api/v1/autopilot/{task_id} — poll Celery result backend.

    Mirrors Celery's READY_STATES: PENDING (enqueued), STARTED (executing),
    SUCCESS (complete), FAILURE (raised). `result` is populated only on
    SUCCESS; `error` is populated only on FAILURE.
    """

    task_id: str
    status: Literal["PENDING", "STARTED", "SUCCESS", "FAILURE"]
    result: AutopilotResult | None = None
    error: str | None = None


__all__ = [
    "AutopilotRequest",
    "AutopilotCreateRequest",  # backwards-compat alias
    "AutopilotResult",
    "AutopilotCreateResponse",
    "AutopilotStatusResponse",
]
