"""
global_llm_config.py — Platform-wide LLM provider configuration (public schema).

Replaces the per-tenant ``LlmConfig`` (tenant schema) as the PRIMARY source
of LLM provider credentials. Only SUPER_ADMIN can CRUD this table; tenant
schemas continue to hold an optional ``LlmConfig`` override layer (default
model preference, provider override) that points back to a
``GlobalLlmConfig.id`` via ``global_llm_config_id``.

Design (per SAAS2-INT-BE task spec):
  - The platform absorbs the LLM API cost; tenants never see the raw key.
  - One row per provider can be marked ``is_default=True`` (the platform-wide
    default that ``llm_service.call_llm`` falls back to when a tenant has no
    override).
  - ``api_key_encrypted`` holds a Fernet ciphertext produced by
    ``app.services.secret_service.encrypt_at_rest``.
  - The 13 providers are a free-form ``String`` (mirroring ``LlmConfig.provider``)
    but the router validates against ``llm_service.ALL_PROVIDERS``.
"""
from __future__ import annotations

from datetime import datetime

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column


class GlobalLlmConfig(Base):
    """Platform-wide LLM provider config (public schema, SUPER_ADMIN-managed)."""

    __tablename__ = "global_llm_config"
    __table_args__ = ({"schema": "public"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=2048)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.cast("true", Boolean)
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.cast("false", Boolean)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["GlobalLlmConfig"]
