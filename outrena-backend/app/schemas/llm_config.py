"""
llm_config.py — Pydantic schemas for the LLM gateway.

LlmResponse is the unified return type of `app.services.llm_service.call_llm()`
regardless of which of the 13 providers served the request. Also hosts the
admin CRUD schemas for the LLM config table (Phase 2 /api/v1/llm-configs).

Phase 8 (dual-path integrations): the schemas now target the public.global_llm_config
table (SUPER_ADMIN-managed). The per-tenant LlmConfig table remains as an
optional override layer.

BUG-01 FIX: Added model_validator to accept frontend camelCase fields
  (apiKey → api_key, model → model_name, display_name derived from model_name).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LlmResponse(BaseModel):
    """
    Unified LLM gateway response (per migration doc §3.4 + §10 Phase 2).

    - content:    the generated text (empty string on parse failure)
    - usage:      token counts (prompt_tokens, completion_tokens, total_tokens)
    - model:      the model ID that served the request
    - provider:   the provider key (openai, anthropic, zai, ...)
    - raw:        the full provider JSON response (for debugging / advanced use)
    """

    model_config = ConfigDict(extra="forbid")

    content: str
    usage: dict[str, int]
    model: str
    provider: str
    raw: dict[str, Any] | None = None


# ── GlobalLlmConfig admin CRUD schemas (Phase 8 /api/v1/llm-configs) ────────


class LlmConfigCreate(BaseModel):
    """Body for POST /llm-configs (global).

    BUG-01 FIX: Accepts frontend camelCase fields via model_validator:
      - apiKey  → api_key
      - model   → model_name
      - display_name is derived from model_name if not provided
    """

    model_config = ConfigDict(extra="ignore")

    provider: str = Field(..., min_length=1)
    display_name: str = Field(default="", min_length=0)
    api_key: str = Field(default="", min_length=0)
    base_url: str | None = None
    model_name: str = Field(default="", min_length=0)
    max_tokens: int = Field(default=2048, ge=1, le=200000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    is_active: bool = True
    is_default: bool = False

    @model_validator(mode="before")
    @classmethod
    def _normalise_frontend_fields(cls, values: Any) -> Any:
        """Accept frontend camelCase field names."""
        if isinstance(values, dict):
            # apiKey → api_key
            if not values.get("api_key") and values.get("apiKey"):
                values["api_key"] = values["apiKey"]
            # model → model_name
            if not values.get("model_name") and values.get("model"):
                values["model_name"] = values["model"]
            # baseUrl → base_url
            if not values.get("base_url") and values.get("baseUrl"):
                values["base_url"] = values["baseUrl"]
            # isActive → is_active
            if "is_active" not in values and "isActive" in values:
                values["is_active"] = values["isActive"]
            # derive display_name from model_name if not provided
            if not values.get("display_name"):
                model_name = values.get("model_name") or values.get("model") or ""
                provider = values.get("provider") or ""
                values["display_name"] = f"{provider}/{model_name}" if model_name else provider
        return values


class LlmConfigUpdate(BaseModel):
    """Body for PUT /llm-configs/{config_id} (global)."""

    display_name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model_name: str | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=200000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    is_active: bool | None = None
    is_default: bool | None = None


class LlmConfigResponse(BaseModel):
    """Public LLM config — apiKey is masked in router-layer serialization."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    display_name: str
    api_key: str | None = None  # masked, never the raw value
    base_url: str | None = None
    model_name: str
    max_tokens: int
    temperature: float
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


class TestLlmRequest(BaseModel):
    """Body for POST /llm-configs/test-llm — call the LLM with a test message."""

    config_id: int | None = None
    message: str = Field(default="Hello, please confirm you are operational.")
    system_prompt: str | None = None


class TestLlmResponse(BaseModel):
    """Response from POST /llm-configs/test-llm."""

    ok: bool
    content: str
    provider: str | None = None
    model_id: str | None = None
    latency_ms: int | None = None
    error: str | None = None


__all__ = [
    "LlmResponse",
    "LlmConfigCreate",
    "LlmConfigUpdate",
    "LlmConfigResponse",
    "TestLlmRequest",
    "TestLlmResponse",
]
