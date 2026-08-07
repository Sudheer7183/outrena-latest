"""
phase3_models.py — Phase 3 Outreach + Analytics domain models.

Mirrors the Prisma models that are NOT already covered by prospect_models,
campaign_models, flow_models, or config_models. These tables back the 21
Phase 3 feature modules and are seeded by migration 0002 alongside the
existing 0001 tenant-schema tables.

All tables are schema-unqualified (bound to the request's search_path),
matching the Phase 1/2 convention. JSON-typed Prisma fields are stored as
TEXT columns holding JSON strings (Phase 4+ may migrate to JSONB).

Models defined here (referenced by Phase 3 routes/services):
  - LinkedInConfig / LinkedInEngagement / LinkedInInboxMessage
  - OptimizationRule / OptimizationAction
  - ContentIdea
  - WeeklyDigest
  - EmailTemplate
  - ProspectSource / SourceConfig
  - Signal / SignalMonitor
  - DomainEnrichment
  - SchedulerStatus (single-row status mirror)
"""
from __future__ import annotations

from datetime import datetime

from app.models.base import Base, CuidPrimaryKey, TimestampMixin
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSON as PG_JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


# ── LinkedIn ────────────────────────────────────────────────────────────────


class LinkedInConfig(Base, CuidPrimaryKey, TimestampMixin):
    """Per-tenant LinkedIn Sales Navigator / API configuration."""

    __tablename__ = "LinkedInConfig"

    accountName: Mapped[str] = mapped_column(String, nullable=False)
    accountHandle: Mapped[str | None] = mapped_column(String, nullable=True)
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cookieJar: Mapped[str | None] = mapped_column(Text, nullable=True)
    lastSyncedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    syncStatus: Mapped[str] = mapped_column(String, nullable=False, default="idle")


class LinkedInEngagement(Base, CuidPrimaryKey, TimestampMixin):
    """A LinkedIn touch (connect, message, profile view) on a prospect."""

    __tablename__ = "LinkedInEngagement"
    __table_args__ = (
        Index("ix_LinkedInEngagement_prospectId", "prospectId"),
        Index("ix_LinkedInEngagement_icpProfileId", "icpProfileId"),
    )

    prospectId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=True
    )
    icpProfileId: Mapped[str | None] = mapped_column(
        String, ForeignKey("IcpProfile.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    scheduledAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    executedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Task 3-a / FIX 2: owner_user_id — the Keycloak user UUID (token.sub)
    # who owns this engagement. NULL on rows created before this column was
    # added (migration 0011 backfills it as nullable); the service falls
    # back to "system" for legacy rows so per-user usage attribution
    # degrades gracefully. Indexed so per-user engagement queries are fast.
    owner_user_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    # AI ICP match fields — populated by /linkedin/engagements/check-icp
    isIcpMatch: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    suggestedNote: Mapped[str | None] = mapped_column(Text, nullable=True)

    icpProfile: Mapped["IcpProfile | None"] = relationship(  # noqa: F821
        "IcpProfile", back_populates="linkedInEngagements", foreign_keys=[icpProfileId]
    )


class LinkedInInboxMessage(Base, CuidPrimaryKey, TimestampMixin):
    """Inbound LinkedIn DM mirrored into OUTRENA for triage."""

    __tablename__ = "LinkedInInboxMessage"
    __table_args__ = (
        Index("ix_LinkedInInboxMessage_prospectId", "prospectId"),
        Index("ix_LinkedInInboxMessage_status", "status"),
    )

    prospectId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=True
    )
    senderName: Mapped[str] = mapped_column(String, nullable=False)
    senderHandle: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="unread")
    receivedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    triagedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ── Optimization Engine ────────────────────────────────────────────────────


class OptimizationRule(Base, CuidPrimaryKey, TimestampMixin):
    """User-defined auto-trigger rule (e.g. 'pause campaign if bounce > 10%')."""

    __tablename__ = "OptimizationRule"
    __table_args__ = (
        Index("ix_OptimizationRule_isActive", "isActive"),
        Index("ix_OptimizationRule_campaignId", "campaignId"),
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    operator: Mapped[str] = mapped_column(String, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    action: Mapped[str] = mapped_column(String, nullable=False)
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    campaignId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Campaign.id", ondelete="SET NULL"), nullable=True
    )
    lastEvaluatedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    campaign: Mapped["Campaign | None"] = relationship(  # noqa: F821
        "Campaign", back_populates="optimizationRules"
    )
    actions: Mapped[list["OptimizationAction"]] = relationship(
        "OptimizationAction", back_populates="rule"
    )


class OptimizationAction(Base, CuidPrimaryKey, TimestampMixin):
    """Immutable log of every optimization rule firing."""

    __tablename__ = "OptimizationAction"
    __table_args__ = (
        Index("ix_OptimizationAction_ruleId", "ruleId"),
        Index("ix_OptimizationAction_campaignId", "campaignId"),
    )

    ruleId: Mapped[str] = mapped_column(
        String, ForeignKey("OptimizationRule.id", ondelete="CASCADE"), nullable=False
    )
    campaignId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Campaign.id"), nullable=True
    )
    metric: Mapped[str] = mapped_column(String, nullable=False)
    observedValue: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[str | None] = mapped_column(String, nullable=True)
    executedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    rule: Mapped["OptimizationRule"] = relationship(
        "OptimizationRule", back_populates="actions"
    )
    campaign: Mapped["Campaign | None"] = relationship(  # noqa: F821
        "Campaign", back_populates="optimizationActions"
    )


# ── Content Ideas ──────────────────────────────────────────────────────────


class ContentIdea(Base, CuidPrimaryKey, TimestampMixin):
    """AI-generated outreach angle / content idea per ICP."""

    __tablename__ = "ContentIdea"
    __table_args__ = (
        Index("ix_ContentIdea_icpProfileId", "icpProfileId"),
    )

    icpProfileId: Mapped[str | None] = mapped_column(
        String, ForeignKey("IcpProfile.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    angle: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    isFavorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    generatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ── Weekly Digest ──────────────────────────────────────────────────────────


class WeeklyDigest(Base, CuidPrimaryKey, TimestampMixin):
    """Auto-generated weekly performance summary."""

    __tablename__ = "WeeklyDigest"
    __table_args__ = (
        Index("ix_WeeklyDigest_weekStart", "weekStart"),
    )

    weekStart: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    weekEnd: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sentCount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    replyCount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    positiveReplyCount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    meetingCount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bounceCount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    highlights: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    # ── Three spec-required JSON columns for metrics (audit-A1 M-35) ─────────
    topProspects: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    campaignPerformance: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    generatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ── Email Templates ────────────────────────────────────────────────────────


class EmailTemplate(Base, CuidPrimaryKey, TimestampMixin):
    """Reusable email body/subject templates (frameworks, snippets)."""

    __tablename__ = "EmailTemplate"
    __table_args__ = (
        Index("ix_EmailTemplate_category", "category"),
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, default="general")
    framework: Mapped[str | None] = mapped_column(String, nullable=True)
    subjectTemplate: Mapped[str | None] = mapped_column(String, nullable=True)
    bodyTemplate: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    isShared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ── Prospect Sources ───────────────────────────────────────────────────────


class ProspectSource(Base, CuidPrimaryKey, TimestampMixin):
    """Tracks where a prospect came from (Apollo, CSV, manual, lookalike)."""

    __tablename__ = "ProspectSource"
    __table_args__ = (
        Index("ix_ProspectSource_prospectId", "prospectId"),
        Index("ix_ProspectSource_source", "source"),
    )

    prospectId: Mapped[str] = mapped_column(
        String, ForeignKey("Prospect.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    query: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rawPayload: Mapped[str | None] = mapped_column(Text, nullable=True)
    importedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceConfig(Base, CuidPrimaryKey, TimestampMixin):
    """Per-source configuration (API key, default filters, daily quota)."""

    __tablename__ = "SourceConfig"
    __table_args__ = (
        UniqueConstraint("source", name="uq_SourceConfig_source"),
    )

    source: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    apiKey: Mapped[str | None] = mapped_column(String, nullable=True)
    dailyQuota: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    usedToday: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    settings: Mapped[dict] = mapped_column(PG_JSON, nullable=False, default=dict, server_default="{}")


# ── Signals ────────────────────────────────────────────────────────────────


class Signal(Base, CuidPrimaryKey, TimestampMixin):
    """A single prospect/company signal (funding, hiring, news)."""

    __tablename__ = "Signal"
    __table_args__ = (
        Index("ix_Signal_prospectId", "prospectId"),
        Index("ix_Signal_type", "type"),
        Index("ix_Signal_detectedAt", "detectedAt"),
    )

    prospectId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Prospect.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="auto")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    detectedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SignalMonitor(Base, CuidPrimaryKey, TimestampMixin):
    """Continuous monitor config (e.g. 'alert on funding rounds > $5M')."""

    __tablename__ = "SignalMonitor"
    __table_args__ = (
        Index("ix_SignalMonitor_isActive", "isActive"),
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    signalType: Mapped[str] = mapped_column(String, nullable=False)
    conditions: Mapped[dict | None] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lastRunAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ── Domain Enrichment ──────────────────────────────────────────────────────


class DomainEnrichment(Base, CuidPrimaryKey, TimestampMixin):
    """Cached enrichment payload for a domain (firmographics, tech stack)."""

    __tablename__ = "DomainEnrichment"
    __table_args__ = (
        UniqueConstraint("domain", name="uq_DomainEnrichment_domain"),
        Index("ix_DomainEnrichment_domain", "domain"),
    )

    domain: Mapped[str] = mapped_column(String, nullable=False)
    companyName: Mapped[str | None] = mapped_column(String, nullable=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    employeeCount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenueRange: Mapped[str | None] = mapped_column(String, nullable=True)
    techStack: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    lastEnrichedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ── Scheduler status (single-row table) ────────────────────────────────────


class SchedulerStatus(Base):
    """In-process scheduler status mirror. Always exactly one row (id=1)."""

    __tablename__ = "SchedulerStatus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    lastTickAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    nextTickAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sentSinceLastTick: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skippedSinceLastTick: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    isRunning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SchedulerRun(Base, CuidPrimaryKey, TimestampMixin):
    """Log of each scheduler tick execution for the /runs endpoint."""

    __tablename__ = "SchedulerRun"
    __table_args__ = (
        Index("ix_SchedulerRun_status", "status"),
        Index("ix_SchedulerRun_startedAt", "startedAt"),
    )

    startedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="running"
    )  # running | completed | failed
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    durationMs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "LinkedInConfig",
    "LinkedInEngagement",
    "LinkedInInboxMessage",
    "OptimizationRule",
    "OptimizationAction",
    "ContentIdea",
    "WeeklyDigest",
    "EmailTemplate",
    "ProspectSource",
    "SourceConfig",
    "Signal",
    "SignalMonitor",
    "DomainEnrichment",
    "SchedulerStatus",
    "SchedulerRun",
]
