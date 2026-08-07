"""integrations.py — ProspectingIntegration CRUD + test schemas.

Phase 8 (dual-path integrations): the create/update payloads now carry an
optional ``key_source`` field ("tenant" | "platform"). The response shape
exposes ``key_source`` + a masked ``apiKey`` (never the raw value).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IntegrationCreate(BaseModel):
    """Body for POST /integrations.

    Accepts both ``platform`` and ``type`` as the integration provider
    identifier — the frontend sends ``type``, the backend stores it as
    ``platform``. The validator normalises ``type`` → ``platform`` so
    existing frontend code works without changes.
    """

    platform: str = Field(default="", min_length=0)
    # 'type' alias accepted from frontend (IntegrationConfigPage sends this field)
    type: str | None = Field(default=None, exclude=True)
    name: str = Field(..., min_length=1)
    apiKey: str | None = None
    key_source: str = Field(default="tenant", pattern="^(tenant|platform)$")
    isActive: bool = False
    settings: dict = {}

    @field_validator("settings", mode="before")
    @classmethod
    def _parse_settings(cls, v: object) -> dict:
        """Parse JSON string or dict for settings."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return parsed
                return {}
            except (json.JSONDecodeError, TypeError, ValueError):
                return {}
        if isinstance(v, dict):
            return v
        return {}

    @model_validator(mode="before")
    @classmethod
    def _normalise_type_to_platform(cls, values: Any) -> Any:
        """Accept 'type' as an alias for 'platform'."""
        if isinstance(values, dict):
            if not values.get("platform") and values.get("type"):
                values["platform"] = values["type"]
        return values


class IntegrationUpdate(BaseModel):
    """Body for PUT /prospecting-integrations/{integration_id}."""

    name: str | None = None
    apiKey: str | None = None
    key_source: str | None = Field(default=None, pattern="^(tenant|platform)$")
    isActive: bool | None = None
    settings: dict | None = None


class IntegrationResponse(BaseModel):
    """Public shape of a ProspectingIntegration row — apiKey masked.

    Phase 8: the masked ``apiKey`` reflects the RESOLVED credential
    (decrypted tenant key OR platform key fingerprint). ``key_source``
    tells the client whether the key is tenant-owned or platform-owned.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    platform: str
    name: str
    apiKey: str | None = None
    key_source: str = "tenant"
    isActive: bool
    settings: dict = {}
    lastTestedAt: datetime | None = None
    lastTestResult: str | None = None
    createdAt: datetime
    updatedAt: datetime

    @field_validator("settings", mode="before")
    @classmethod
    def _parse_settings(cls, v: object) -> dict:
        """Parse JSON string or dict for settings."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return parsed
                return {}
            except (json.JSONDecodeError, TypeError, ValueError):
                return {}
        if isinstance(v, dict):
            return v
        return {}


class IntegrationTestRequest(BaseModel):
    """Body for POST /prospecting-integrations/test — connectivity probe."""

    integrationId: str


class IntegrationTestResponse(BaseModel):
    """Result of testing a prospecting integration."""

    integrationId: str
    ok: bool
    latencyMs: int | None = None
    detail: str | None = None


__all__ = [
    "IntegrationCreate",
    "IntegrationUpdate",
    "IntegrationResponse",
    "IntegrationTestRequest",
    "IntegrationTestResponse",
]
