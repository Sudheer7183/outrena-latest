"""
prospect_models.py — ICP, Prospect, and prospect-adjacent models.

Mirrors Prisma models: IcpProfile, Prospect, Competitor, CallLog,
JobChangeAlert, MeetingPrep, Meeting.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.base import Base, CuidPrimaryKey, TimestampMixin
from app.models.enums import EnrichmentTier, IntentSource, SeniorityTier
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON as PG_JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

# ── ICP Profiles ────────────────────────────────────────────────────────────


class IcpProfile(Base, CuidPrimaryKey, TimestampMixin):
    """Ideal Customer Profile — target persona + messaging context."""

    __tablename__ = "IcpProfile"

    name: Mapped[str] = mapped_column(String, nullable=False)
    persona: Mapped[str | None] = mapped_column(Text, nullable=True)
    companyType: Mapped[str | None] = mapped_column(String, nullable=True)
    topObjections: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    painPoints: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    valueProps: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    senderRole: Mapped[str | None] = mapped_column(String, nullable=True)
    senderCompany: Mapped[str | None] = mapped_column(String, nullable=True)
    senderOffer: Mapped[str | None] = mapped_column(String, nullable=True)
    proofMetric: Mapped[str | None] = mapped_column(String, nullable=True)

    prospects: Mapped[list["Prospect"]] = relationship(
        "Prospect", back_populates="icpProfile"
    )
    campaigns: Mapped[list["Campaign"]] = relationship(  # noqa: F821
        "Campaign", back_populates="icpProfile"
    )
    linkedInEngagements: Mapped[list["LinkedInEngagement"]] = relationship(  # noqa: F821
        "LinkedInEngagement", back_populates="icpProfile", foreign_keys="LinkedInEngagement.icpProfileId"
    )
    flowRuns: Mapped[list["FlowRun"]] = relationship(  # noqa: F821
        "FlowRun", back_populates="icpProfile"
    )
    flowAbTests: Mapped[list["FlowAbTest"]] = relationship(  # noqa: F821
        "FlowAbTest", back_populates="icpProfile"
    )
    autopilotQueue: Mapped[list["AutopilotQueue"]] = relationship(  # noqa: F821
        "AutopilotQueue", back_populates="icpProfile"
    )


# ── Prospect ────────────────────────────────────────────────────────────────


class Prospect(Base, CuidPrimaryKey, TimestampMixin):
    """A lead — enriched, scored, and tracked through the lifecycle."""

    __tablename__ = "Prospect"
    __table_args__ = (
        Index("ix_Prospect_deleted_at", "deleted_at"),
        Index("ix_Prospect_consent_status", "consent_status"),
    )

    firstName: Mapped[str] = mapped_column(String, nullable=False)
    lastName: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    linkedinUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    seniority: Mapped[SeniorityTier] = mapped_column(
        SAEnum(SeniorityTier, name="seniority_tier", create_type=False),
        nullable=False,
        default=SeniorityTier.IC,
    )
    signals: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    qaScore: Mapped[int | None] = mapped_column(Integer, nullable=True)
    emailValidated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    emailValidationDetail: Mapped[str | None] = mapped_column(String, nullable=True)
    emailConfidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    isCatchAll: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enrichmentTier: Mapped[EnrichmentTier] = mapped_column(
        SAEnum(EnrichmentTier, name="enrichment_tier", create_type=False),
        nullable=False,
        default=EnrichmentTier.UNENRICHABLE,
    )
    intentSource: Mapped[IntentSource] = mapped_column(
        SAEnum(IntentSource, name="intent_source", create_type=False),
        nullable=False,
        default=IntentSource.OTHER,
    )
    intentDetail: Mapped[str | None] = mapped_column(String, nullable=True)
    intentStrength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="new")

    # Suppression / compliance
    suppressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    suppressionReason: Mapped[str | None] = mapped_column(String, nullable=True)
    suppressedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unsubscribeToken: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    icpFitScore: Mapped[int | None] = mapped_column(Integer, nullable=True)
    icpPersona: Mapped[str | None] = mapped_column(String, nullable=True)
    icpScoreBreakdown: Mapped[str | None] = mapped_column(String, nullable=True)
    ultimateProfile: Mapped[str | None] = mapped_column(String, nullable=True)
    urgencyTier: Mapped[str | None] = mapped_column(String, nullable=True)
    urgencyDeadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── GDPR compliance fields ──────────────────────────────────────────────
    # consent_status tracks the LATEST consent state for this prospect under
    # the prospect's primary lawful_basis. The full per-lawful-basis history
    # lives in the consents + consent_logs tables (migration 0007).
    #   granted      — explicit consent recorded
    #   withdrawn    — consent withdrawn; prospect is suppressed + all
    #                  outbound processing blocked
    #   pending      — prospect imported but no explicit consent recorded yet
    #   not_required — lawful_basis is not "consent" (e.g. legitimate_interest)
    #                  so explicit consent is not needed
    consent_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    # lawful_basis (GDPR Article 6). Default "legitimate_interest" is the
    # most common basis for B2B outreach in OUTRENA. See app.models.consent
    # for the full enumeration.
    lawful_basis: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="legitimate_interest",
        server_default="legitimate_interest",
    )
    # Soft-delete timestamp — when set, the prospect is "forgotten".
    # deleted_at IS NOT NULL rows are filtered out of all list queries by
    # default (ProspectService.list_prospects). The row is RETAINED for
    # aggregate stats (GDPR Article 17(3)(e) "right to be forgotten" carve-
    # out for stats rendered anonymous).
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # anonymized=true means PII columns have been replaced with "[anonymized]"
    # by PiiService.anonymize_prospect. The row still exists for FK integrity
    # (campaigns, sequences, deals reference it) but is no longer PII.
    anonymized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.cast("false", Boolean)
    )

    icpProfileId: Mapped[str | None] = mapped_column(
        String, ForeignKey("IcpProfile.id"), nullable=True
    )

    icpProfile: Mapped["IcpProfile | None"] = relationship(
        "IcpProfile", back_populates="prospects"
    )
    campaigns: Mapped[list["CampaignProspect"]] = relationship(  # noqa: F821
        "CampaignProspect", back_populates="prospect"
    )
    sequences: Mapped[list["Sequence"]] = relationship(  # noqa: F821
        "Sequence", back_populates="prospect"
    )
    deals: Mapped[list["Deal"]] = relationship(  # noqa: F821
        "Deal", back_populates="prospect"
    )
    replyDrafts: Mapped[list["ReplyDraft"]] = relationship(  # noqa: F821
        "ReplyDraft", back_populates="prospect"
    )
    competitors: Mapped[list["Competitor"]] = relationship(
        "Competitor", back_populates="prospect"
    )
    callLogs: Mapped[list["CallLog"]] = relationship(
        "CallLog", back_populates="prospect"
    )
    jobChangeAlerts: Mapped[list["JobChangeAlert"]] = relationship(
        "JobChangeAlert", back_populates="prospect"
    )
    abTestAssignments: Mapped[list["AbTestAssignment"]] = relationship(  # noqa: F821
        "AbTestAssignment", back_populates="prospect"
    )
    meetingPreps: Mapped[list["MeetingPrep"]] = relationship(
        "MeetingPrep", back_populates="prospect"
    )
    meetings: Mapped[list["Meeting"]] = relationship(
        "Meeting", back_populates="prospect"
    )


# ── Competitor Radar ────────────────────────────────────────────────────────


class Competitor(Base, CuidPrimaryKey):
    """Competitor of a prospect's company (radar / positioning analysis)."""

    __tablename__ = "Competitor"

    prospectId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    positioning: Mapped[str | None] = mapped_column(String, nullable=True)
    overlapScore: Mapped[float | None] = mapped_column(Float, nullable=True)
    threatLevel: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="auto")
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    prospect: Mapped["Prospect | None"] = relationship(
        "Prospect", back_populates="competitors", foreign_keys=[prospectId]
    )


# ── Call Log ────────────────────────────────────────────────────────────────


class CallLog(Base, CuidPrimaryKey):
    """Phone channel tracking — one row per call to a prospect."""

    __tablename__ = "CallLog"

    prospectId: Mapped[str] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=False
    )
    phone: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    durationSec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    calledAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    prospect: Mapped["Prospect"] = relationship(
        "Prospect", back_populates="callLogs"
    )


# ── Job-Change Monitor ──────────────────────────────────────────────────────


class JobChangeAlert(Base, CuidPrimaryKey, TimestampMixin):
    """Alumni tracker — a prospect changed jobs (new company + ICP re-fit score)."""

    __tablename__ = "JobChangeAlert"
    __table_args__ = (
        Index("ix_JobChangeAlert_prospectId", "prospectId"),
        Index("ix_JobChangeAlert_status", "status"),
    )

    prospectId: Mapped[str] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=False
    )
    previousCompany: Mapped[str | None] = mapped_column(String, nullable=True)
    previousTitle: Mapped[str | None] = mapped_column(String, nullable=True)
    newCompany: Mapped[str] = mapped_column(String, nullable=False)
    newTitle: Mapped[str | None] = mapped_column(String, nullable=True)
    newDomain: Mapped[str | None] = mapped_column(String, nullable=True)
    newLinkedinUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    detectedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    icpProfileId: Mapped[str | None] = mapped_column(
        String, ForeignKey("IcpProfile.id"), nullable=True
    )
    icpFitScore: Mapped[float | None] = mapped_column(Float, nullable=True)
    icpPersona: Mapped[str | None] = mapped_column(String, nullable=True)
    matchReason: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="new")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    scanSource: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    lastScannedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    prospect: Mapped["Prospect"] = relationship(
        "Prospect", back_populates="jobChangeAlerts", foreign_keys=[prospectId]
    )


# ── Meeting Prep Briefs ─────────────────────────────────────────────────────


class MeetingPrep(Base, CuidPrimaryKey):
    """AI-generated meeting prep brief for a prospect call."""

    __tablename__ = "MeetingPrep"
    __table_args__ = (
        Index("ix_MeetingPrep_prospectId", "prospectId"),
    )

    prospectId: Mapped[str] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=False
    )
    callType: Mapped[str] = mapped_column(String, nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    prospect: Mapped["Prospect"] = relationship(
        "Prospect", back_populates="meetingPreps"
    )


# ── Calendar / Meetings ─────────────────────────────────────────────────────


class Meeting(Base, CuidPrimaryKey, TimestampMixin):
    """Lightweight calendar entry — prospect meeting with auto-generated brief."""

    __tablename__ = "Meeting"
    __table_args__ = (
        Index("ix_Meeting_scheduledAt", "scheduledAt"),
        Index("ix_Meeting_prospectId", "prospectId"),
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    scheduledAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    durationMin: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    meetingUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="scheduled")
    prospectId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=True
    )
    meetingPrepId: Mapped[str | None] = mapped_column(
        String, ForeignKey("MeetingPrep.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    prospect: Mapped["Prospect | None"] = relationship(
        "Prospect", back_populates="meetings"
    )
