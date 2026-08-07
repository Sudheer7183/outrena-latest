"""
call_log.py — Pydantic schemas for CallLog CRUD.

Created by FIX-BE-1 / Additional: the underlying CallLog model in
``app/models/prospect_models.py`` previously had NO service/route/schema
surface (audit §E1). These schemas back the new
``app/api/v1/call_logs.py`` router + ``app/services/call_log_service.py``.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CallLogCreate(BaseModel):
    """Body for POST /call-logs — log a phone call to a prospect."""

    prospectId: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=1, max_length=64)
    outcome: str = Field(default="pending", max_length=64)
    durationSec: int | None = Field(default=None, ge=0, le=86400)
    notes: str | None = Field(default=None, max_length=8000)
    calledAt: datetime | None = None  # defaults to now() server-side


class CallLogUpdate(BaseModel):
    """Body for PATCH /call-logs/{id} — partial update."""

    phone: str | None = Field(default=None, min_length=1, max_length=64)
    outcome: str | None = Field(default=None, max_length=64)
    durationSec: int | None = Field(default=None, ge=0, le=86400)
    notes: str | None = Field(default=None, max_length=8000)
    calledAt: datetime | None = None


class CallLogResponse(BaseModel):
    """Public shape of a CallLog row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    prospectId: str
    phone: str
    outcome: str
    durationSec: int | None = None
    notes: str | None = None
    calledAt: datetime
    createdAt: datetime


class CallLogListResponse(BaseModel):
    """Page envelope for call-log list endpoints."""

    items: list[CallLogResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


__all__ = [
    "CallLogCreate",
    "CallLogUpdate",
    "CallLogResponse",
    "CallLogListResponse",
]
