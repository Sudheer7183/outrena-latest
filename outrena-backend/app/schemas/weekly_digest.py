"""weekly_digest.py — Auto-generated weekly performance summary contracts."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


def _parse_json_string(value: Any) -> Any:
    """Best-effort parse a TEXT-holding-JSON column value to a Python object.

    The Phase 3 models store JSON columns as TEXT (per the migration doc's
    Phase-4+ JSONB deferral). The Pydantic response model exposes them as
    native Python types so the OpenAPI schema is correct; this validator
    converts the raw string on load. Returns the value unchanged if it is
    already a list/dict (e.g. from a hand-crafted test) or unparseable.
    """
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return value
    return value


class WeeklyDigestResponse(BaseModel):
    id: str
    weekStart: datetime
    weekEnd: datetime
    sentCount: int
    replyCount: int
    positiveReplyCount: int
    meetingCount: int
    bounceCount: int
    summary: str
    highlights: list[str]
    # Three spec-required JSON columns for metrics (audit-A1 M-35). Exposed as
    # raw JSON (Any) because the structure is provider-specific — the service
    # layer populates them with per-campaign + per-prospect rollups.
    topProspects: list[Any] | dict[str, Any] | None = None
    campaignPerformance: dict[str, Any] | None = None
    generatedAt: datetime
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}

    @field_validator("highlights", "topProspects", "campaignPerformance", mode="before")
    @classmethod
    def _parse_json_columns(cls, v: Any) -> Any:
        return _parse_json_string(v)


class WeeklyDigestGenerateRequest(BaseModel):
    """Body for POST /weekly-digest/generate — compute + persist + return."""
    weekStart: datetime | None = None  # defaults to Monday of current week


class WeeklyDigestGenerateResponse(BaseModel):
    digest: WeeklyDigestResponse


__all__ = [
    "WeeklyDigestResponse",
    "WeeklyDigestGenerateRequest",
    "WeeklyDigestGenerateResponse",
]
