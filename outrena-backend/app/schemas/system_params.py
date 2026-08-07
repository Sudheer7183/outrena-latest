"""system_params.py — SystemParameter admin schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SystemParamResponse(BaseModel):
    """Public shape of a SystemParameter row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    category: str
    label: str
    description: str
    impact: str
    valueType: str
    value: str
    defaultValue: str
    minValue: str | None = None
    maxValue: str | None = None
    unit: str | None = None
    isAdvanced: bool
    createdAt: datetime
    updatedAt: datetime


class SystemParamUpdate(BaseModel):
    """Body for PUT /system-params/{key} — only the value is editable."""

    value: str = Field(..., min_length=1)


class SystemParamResetResponse(BaseModel):
    """Response from POST /system-params/reset — re-seed from param_defs."""

    resetCount: int
    message: str


__all__ = [
    "SystemParamResponse",
    "SystemParamUpdate",
    "SystemParamResetResponse",
]
