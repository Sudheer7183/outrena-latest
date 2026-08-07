"""
tenant_config.py — Per-tenant platform-level configuration model.

Lives in the PUBLIC schema alongside public.tenants. Holds plan, seat count,
feature flags, and shared-integration policy. One row per tenant (1:1 with
public.tenants), created by TenantProvisioningService at provisioning time.

Kept separate from tenants so the registry row stays small and fast to scan
(TenantMiddleware hits tenants on every request; tenant_config is only read
by platform-admin routes).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class TenantConfig(Base):
    """Per-tenant platform-level configuration (public schema, 1:1 with tenants)."""

    __tablename__ = "tenant_config"
    __table_args__ = ({"schema": "public"},)

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("public.tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="alpha")
    max_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    features: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=func.cast("{}", JSONB)
    )
    integrations_shared: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.cast("true", Boolean)
    )
    llm_provider_default: Mapped[str] = mapped_column(
        String(50), nullable=False, default="zai"
    )
    # NEW (migration 0004) — dual-path integrations mode.
    # "platform_managed" → integrations use platform-provided keys (resolved
    #   via secret_service at call time; tenants pay a +$49/mo delta per the
    #   Plan.feature_flags.integration_path_pricing config).
    # "tenant_managed"   → tenants provide their own keys (encrypted at rest
    #   via Fernet in the tenant schema's ProspectingIntegration.api_key_encrypted).
    integration_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="tenant_managed",
        server_default="tenant_managed",
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


__all__ = ["TenantConfig"]
