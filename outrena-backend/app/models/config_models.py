"""
config_models.py — Tenant-scoped admin/setup models.

Mirrors the Prisma models that hold tenant-level configuration:
LlmConfig, PromptTemplate, SystemParameter, Domain, MailBridgeConfig,
ProspectingIntegration, ExclusionRule.

All tables are schema-unqualified (bound to the request's search_path).
JSON-typed Prisma fields are kept as TEXT columns holding JSON strings
to preserve client-side JSON.parse compatibility (Phase 3+ may migrate
to JSONB).
"""
from __future__ import annotations

from datetime import datetime

from app.models.base import Base, CuidPrimaryKey, TimestampMixin
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON as PG_JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

# ── LLM Configuration ───────────────────────────────────────────────────────


class LlmConfig(Base, CuidPrimaryKey, TimestampMixin):
    """LLM provider configuration (OpenAI, Anthropic, ZAI, etc.).

    Phase 8 (dual-path integrations): the PRIMARY LLM config now lives in
    ``public.global_llm_config`` (managed by SUPER_ADMIN). This tenant-scoped
    table remains as an OPTIONAL override layer — it stores a tenant's
    preferred default model + provider override via ``global_llm_config_id``.
    The legacy ``apiKey`` column is kept for backward compatibility but
    newly-created rows should reference the global config and leave
    ``apiKey`` NULL.
    """

    __tablename__ = "LlmConfig"
    __table_args__ = (
        Index("ix_LlmConfig_isDefault_isActive", "isDefault", "isActive"),
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    modelId: Mapped[str] = mapped_column(String, nullable=False)
    apiKey: Mapped[str | None] = mapped_column(String, nullable=True)
    baseUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    isDefault: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    settings: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    modelTier: Mapped[str] = mapped_column(String, nullable=False, default="standard")
    # NEW (migration 0004) — references public.global_llm_config.id; nullable
    # so existing tenant rows continue to work without a back-fill.
    global_llm_config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("public.global_llm_config.id"), nullable=True
    )

    campaigns: Mapped[list["Campaign"]] = relationship(  # noqa: F821
        "Campaign", back_populates="llmConfig"
    )


# ── Prompt Templates ────────────────────────────────────────────────────────


class PromptTemplate(Base, CuidPrimaryKey, TimestampMixin):
    """Admin-manageable LLM prompt templates (47 seeded rows per tenant)."""

    __tablename__ = "PromptTemplate"

    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    isEditable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    defaultValue: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    sortOrder: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ── System Parameters ───────────────────────────────────────────────────────


class SystemParameter(Base, CuidPrimaryKey, TimestampMixin):
    """Admin-tunable thresholds (30+ seeded rows per tenant)."""

    __tablename__ = "SystemParameter"

    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    impact: Mapped[str] = mapped_column(String, nullable=False)
    valueType: Mapped[str] = mapped_column(String, nullable=False, default="number")
    value: Mapped[str] = mapped_column(String, nullable=False)
    defaultValue: Mapped[str] = mapped_column(String, nullable=False)
    minValue: Mapped[str | None] = mapped_column(String, nullable=True)
    maxValue: Mapped[str | None] = mapped_column(String, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    isAdvanced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# ── Domain / Deliverability ─────────────────────────────────────────────────


class Domain(Base, CuidPrimaryKey, TimestampMixin):
    """Sending domain with DNS health tracking."""

    __tablename__ = "Domain"

    domainName: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    spfStatus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dkimStatus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dmarcStatus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dailySendLimit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    warmingWeek: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lastChecked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaigns: Mapped[list["Campaign"]] = relationship(  # noqa: F821
        "Campaign", back_populates="domain"
    )
    mailBridgeConfigs: Mapped[list["MailBridgeConfig"]] = relationship(
        "MailBridgeConfig", back_populates="domain"
    )


# ── MailBridge Configuration ────────────────────────────────────────────────


class MailBridgeConfig(Base, CuidPrimaryKey, TimestampMixin):
    """Per-domain SMTP relay config (MailBridge server URL + credentials).

    Phase 8 (dual-path integrations): ``owner_user_id`` distinguishes
    tenant-level config (NULL — the default tenant-wide MailBridge) from
    per-user config (set — a specific user's override). BE-B will use this
    column to support the user-capabilities requirement (per-user mailbox
    routing). NULL remains the default so existing rows are unaffected.
    """

    __tablename__ = "MailBridgeConfig"

    name: Mapped[str] = mapped_column(String, nullable=False)
    baseUrl: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="gmail")
    fromEmail: Mapped[str] = mapped_column(String, nullable=False)
    fromName: Mapped[str | None] = mapped_column(String, nullable=True)
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    webhookSecret: Mapped[str | None] = mapped_column(String, nullable=True)
    domainId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Domain.id"), nullable=True
    )
    # NEW (migration 0004) — when NULL → tenant-level config; when set →
    # per-user override (Keycloak user UUID, String(128) parity with
    # SupportTicket.created_by_user_id).
    owner_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    domain: Mapped["Domain | None"] = relationship(
        "Domain", back_populates="mailBridgeConfigs"
    )


# ── Prospecting Integrations ────────────────────────────────────────────────


class ProspectingIntegration(Base, CuidPrimaryKey, TimestampMixin):
    """Apollo, Clay, ZoomInfo, Clearbit, Hunter, etc. — API credentials + state.

    Phase 8 (dual-path integrations): credentials now follow one of two paths:
      * ``key_source="tenant"`` (default) — the tenant owns the key; it lives
        Fernet-encrypted in ``api_key_encrypted``. The legacy ``apiKey``
        column is preserved for backward compatibility with existing rows
        (migration 0004 copies it into ``api_key_encrypted`` on first update).
      * ``key_source="platform"`` — the platform owns the key; it lives in
        the configured SecretBackend (env / AWS SM / Azure KV) under
        ``platform/integrations/{platform}/api_key``. ``api_key_encrypted``
        is NULL in this case, and the key is resolved at call time by
        ``IntegrationCredentialsService.resolve_credentials``.
    """

    __tablename__ = "ProspectingIntegration"

    platform: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    apiKey: Mapped[str | None] = mapped_column(String, nullable=True)
    # NEW (migration 0004) — Fernet ciphertext of the tenant-provided key.
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NEW (migration 0004) — "tenant" (default) | "platform".
    key_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="tenant", server_default="tenant"
    )
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settings: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    lastTestedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lastTestResult: Mapped[str | None] = mapped_column(String, nullable=True)


# ── Exclusion Rules ─────────────────────────────────────────────────────────


class ExclusionRule(Base, CuidPrimaryKey, TimestampMixin):
    """Prospect suppression list (competitors, customers, DNC, blocked domains)."""

    __tablename__ = "ExclusionRule"
    __table_args__ = (
        UniqueConstraint("type", "value", name="uq_ExclusionRule_type_value"),
        Index("ix_ExclusionRule_type", "type"),
        Index("ix_ExclusionRule_isActive", "isActive"),
    )

    type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
