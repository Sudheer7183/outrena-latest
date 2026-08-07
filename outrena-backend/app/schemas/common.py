"""
common.py — Shared request/response contracts for Phase 3 feature modules.

Includes pagination envelopes, CSV-export helpers, and the standard
message/error payload used by the 21 feature routers.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Cursor-free page envelope used by every list endpoint."""

    items: list[T]
    total: int = 0
    limit: int = 50
    offset: int = 0


class MessageResponse(BaseModel):
    """Generic message payload returned by POST/PUT/DELETE endpoints."""

    message: str
    id: str | None = None


class ErrorResponse(BaseModel):
    """RFC-7807-style error body."""

    detail: str
    code: str | None = None


class PageParams(BaseModel):
    """Query params parsed from the request URL by dependency injection."""

    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


__all__ = ["Page", "MessageResponse", "ErrorResponse", "PageParams"]
