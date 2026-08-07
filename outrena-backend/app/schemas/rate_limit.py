"""
rate_limit.py — Pydantic schemas for RateLimit + RateLimitLog.

Created by FIX-BE-1 / CRITICAL 1: the underlying ORM models in
``app/models/flow_models.py`` previously had NO service/route/schema
surface (audit §D1).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RateLimitWindow


class RateLimitCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=200)
    label: str = Field(..., min_length=1, max_length=200)
    platform: str | None = None
    window: RateLimitWindow = RateLimitWindow.HOURLY
    limit: int = Field(default=100, ge=1, le=1_000_000)
    throttleMode: str = "skip"
    isActive: bool = True


class RateLimitUpdate(BaseModel):
    label: str | None = None
    platform: str | None = None
    window: RateLimitWindow | None = None
    limit: int | None = Field(default=None, ge=1, le=1_000_000)
    count: int | None = Field(default=None, ge=0)
    throttleMode: str | None = None
    isActive: bool | None = None


class RateLimitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    label: str
    platform: str | None = None
    window: RateLimitWindow
    limit: int
    count: int
    windowStart: datetime
    throttleMode: str
    isActive: bool
    createdAt: datetime
    updatedAt: datetime


class RateLimitListResponse(BaseModel):
    items: list[RateLimitResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


class RateLimitLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    platform: str | None = None
    outcome: str
    flowRunId: str | None = None
    detail: str | None = None
    createdAt: datetime


class RateLimitLogListResponse(BaseModel):
    items: list[RateLimitLogResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


__all__ = [
    "RateLimitCreate",
    "RateLimitUpdate",
    "RateLimitResponse",
    "RateLimitListResponse",
    "RateLimitLogResponse",
    "RateLimitLogListResponse",
]
