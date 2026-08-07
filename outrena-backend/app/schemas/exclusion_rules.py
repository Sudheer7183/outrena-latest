"""exclusion_rules.py — Prospect suppression list contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator


class ExclusionRuleCreate(BaseModel):
    """BUG-22 FIX: Accept 'field' as alias for 'type' (frontend sends field/operator/value)."""

    model_config = {"extra": "ignore"}

    type: str = ""  # competitor | customer | dnc | domain | email
    value: str
    reason: str | None = None
    isActive: bool = True
    # Frontend sends field/operator — map field → type
    operator: str | None = None  # accepted, ignored

    @model_validator(mode="before")
    @classmethod
    def _normalise_field_to_type(cls, values: object) -> object:
        """BUG-22 FIX: Accept frontend 'field' as alias for 'type'."""
        if isinstance(values, dict):
            if not values.get("type") and values.get("field"):
                values["type"] = values["field"]
            if not values.get("type"):
                values["type"] = "domain"  # safe default
        return values


class ExclusionRuleUpdate(BaseModel):
    reason: str | None = None
    isActive: bool | None = None


class ExclusionRuleResponse(BaseModel):
    id: str
    type: str
    value: str
    reason: str | None
    isActive: bool
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class BulkExclusionRequest(BaseModel):
    """Body for POST /exclusion-rules/bulk — upsert many at once."""
    rules: list[ExclusionRuleCreate]


class BulkExclusionResponse(BaseModel):
    inserted: int
    skipped: int  # duplicates


__all__ = [
    "ExclusionRuleCreate",
    "ExclusionRuleUpdate",
    "ExclusionRuleResponse",
    "BulkExclusionRequest",
    "BulkExclusionResponse",
]
