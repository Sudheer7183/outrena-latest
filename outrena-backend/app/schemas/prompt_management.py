"""prompt_management.py — PromptTemplate admin schemas."""
from __future__ import annotations

from datetime import datetime

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PromptResponse(BaseModel):
    """Public shape of a PromptTemplate row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    category: str
    name: str
    description: str
    template: str
    isEditable: bool
    defaultValue: str
    variables: list[str] = []
    sortOrder: int
    createdAt: datetime
    updatedAt: datetime

    @field_validator("variables", mode="before")
    @classmethod
    def _parse_variables(cls, v: object) -> list[str]:
        """Parse JSON string or list for variables."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
                return []
            except (json.JSONDecodeError, TypeError, ValueError):
                return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []


class PromptUpdate(BaseModel):
    """Body for PUT /prompts/{key} — only the template body is editable."""

    template: str = Field(..., min_length=1)


class PromptResetResponse(BaseModel):
    """Response from POST /prompts/reset — re-seed from prompt_defs."""

    resetCount: int
    message: str


__all__ = [
    "PromptResponse",
    "PromptUpdate",
    "PromptResetResponse",
]
