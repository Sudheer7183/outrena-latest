"""meeting_prep.py — Meeting-prep brief contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MeetingPrepCreate(BaseModel):
    prospectId: str
    callType: str = "discovery"
    brief: str | None = None  # if None, will be generated


class MeetingPrepResponse(BaseModel):
    id: str
    prospectId: str
    callType: str
    brief: str
    createdAt: datetime

    model_config = {"from_attributes": True}


class MeetingPrepGenerateRequest(BaseModel):
    prospectId: str
    callType: str = "discovery"


class MeetingPrepGenerateResponse(BaseModel):
    id: str
    brief: str


__all__ = [
    "MeetingPrepCreate",
    "MeetingPrepResponse",
    "MeetingPrepGenerateRequest",
    "MeetingPrepGenerateResponse",
]
