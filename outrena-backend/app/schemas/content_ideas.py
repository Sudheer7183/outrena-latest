"""content_ideas.py — AI-generated outreach content idea contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ContentIdeaCreate(BaseModel):
    title: str
    angle: str | None = None
    body: str
    icpProfileId: str | None = None
    isFavorite: bool = False


class ContentIdeaUpdate(BaseModel):
    title: str | None = None
    angle: str | None = None
    body: str | None = None
    status: str | None = None
    isFavorite: bool | None = None


class ContentIdeaResponse(BaseModel):
    id: str
    icpProfileId: str | None
    title: str
    angle: str | None
    body: str
    status: str
    isFavorite: bool
    generatedAt: datetime
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class ContentIdeaGenerateRequest(BaseModel):
    """Body for POST /content-ideas/generate — LLM-generate ideas for an ICP.

    BUG-27 FIX: Accept frontend {topic, audience, count} as alternative to {icpProfileId, count}.
    """

    model_config = {"extra": "ignore"}

    icpProfileId: str | None = None  # BUG-27: made optional
    count: int = 5
    topic: str | None = None    # frontend sends this
    audience: str | None = None  # frontend sends this


class ContentIdeaGenerateResponse(BaseModel):
    ideas: list[ContentIdeaResponse]


__all__ = [
    "ContentIdeaCreate",
    "ContentIdeaUpdate",
    "ContentIdeaResponse",
    "ContentIdeaGenerateRequest",
    "ContentIdeaGenerateResponse",
]
