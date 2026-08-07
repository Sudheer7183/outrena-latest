"""templates.py — EmailTemplate request/response contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator


class EmailTemplateCreate(BaseModel):
    """BUG-23 FIX: Accept 'body' and 'subject' as aliases for bodyTemplate/subjectTemplate."""

    model_config = {"extra": "ignore"}

    name: str
    category: str = "general"
    framework: str | None = None
    subjectTemplate: str | None = None
    bodyTemplate: str = ""
    variables: list[str] = []
    isShared: bool = True

    @model_validator(mode="before")
    @classmethod
    def _normalise_aliases(cls, values: object) -> object:
        """BUG-23 FIX: Map 'body' → bodyTemplate, 'subject' → subjectTemplate."""
        if isinstance(values, dict):
            if not values.get("bodyTemplate") and values.get("body"):
                values["bodyTemplate"] = values["body"]
            if not values.get("subjectTemplate") and values.get("subject"):
                values["subjectTemplate"] = values["subject"]
        return values


class EmailTemplateUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    framework: str | None = None
    subjectTemplate: str | None = None
    bodyTemplate: str | None = None
    variables: list[str] | None = None
    isShared: bool | None = None


class EmailTemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    framework: str | None
    subjectTemplate: str | None
    bodyTemplate: str
    variables: list[str]
    isShared: bool
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


__all__ = [
    "EmailTemplateCreate",
    "EmailTemplateUpdate",
    "EmailTemplateResponse",
]
