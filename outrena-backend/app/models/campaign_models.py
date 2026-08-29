"""
campaign_models.py — Campaign, Sequence, Collateral, Deal, ReplyDraft,
A/B testing models.
 
Mirrors Prisma models: Campaign, CampaignProspect,
CampaignResult, Collateral, CampaignCollateralLink, Sequence,
SubjectLine, AbTest, AbTestAssignment, EmailAbTest, Deal, ReplyDraft.
"""
from __future__ import annotations
 
from datetime import datetime
 
from app.models.base import Base, CuidPrimaryKey, TimestampMixin
from app.models.enums import EmailStatus, TouchAngle
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
from sqlalchemy.types import Enum as SAEnum
 
# ── Campaign ────────────────────────────────────────────────────────────────
 
 
class Campaign(Base, CuidPrimaryKey, TimestampMixin):
    """Outreach campaign — sender context, ICP, LLM config, compliance."""
 
    __tablename__ = "Campaign"
    __table_args__ = (
        Index("ix_Campaign_owner_user_id", "owner_user_id"),
    )
 
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    framework: Mapped[str | None] = mapped_column(String, nullable=True)
 
    # Owner — the Keycloak user UUID (token.sub) who owns this campaign.
    # 'system' is the backfill default for rows created before per-user ownership.
    owner_user_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default="system", server_default="system"
    )
 
    # Sender override
    senderRole: Mapped[str | None] = mapped_column(String, nullable=True)
    senderCompany: Mapped[str | None] = mapped_column(String, nullable=True)
    senderOffer: Mapped[str | None] = mapped_column(String, nullable=True)
    proofMetric: Mapped[str | None] = mapped_column(String, nullable=True)
    senderProduct: Mapped[str | None] = mapped_column(String, nullable=True)
    targetAudience: Mapped[str | None] = mapped_column(String, nullable=True)
 
    # CAN-SPAM / GDPR compliance
    complianceFooter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unsubscribeUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    physicalAddress: Mapped[str | None] = mapped_column(String, nullable=True)
    webhookUrl: Mapped[str | None] = mapped_column(String, nullable=True)
 
    # Brand voice (JSON)
    brandVoiceProfile: Mapped[dict | None] = mapped_column(PG_JSON, nullable=True)
 
    icpProfileId: Mapped[str | None] = mapped_column(
        String, ForeignKey("IcpProfile.id"), nullable=True
    )
    llmConfigId: Mapped[str | None] = mapped_column(
        String, ForeignKey("LlmConfig.id"), nullable=True
    )
    domainId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Domain.id"), nullable=True
    )
 
    icpProfile: Mapped["IcpProfile | None"] = relationship(  # noqa: F821
        "IcpProfile", back_populates="campaigns"
    )
    llmConfig: Mapped["LlmConfig | None"] = relationship(  # noqa: F821
        "LlmConfig", back_populates="campaigns"
    )
    domain: Mapped["Domain | None"] = relationship(  # noqa: F821
        "Domain", back_populates="campaigns"
    )
    prospects: Mapped[list["CampaignProspect"]] = relationship(
        "CampaignProspect", back_populates="campaign"
    )
    sequences: Mapped[list["Sequence"]] = relationship(
        "Sequence", back_populates="campaign"
    )
    # NOTE (Task 3-a / FIX 1): the `metrics` relationship on CampaignMetric
    # was removed when the dead CampaignMetric model was dropped. Analytics
    # now aggregates from the Sequence table (the source of truth for
    # send/open/reply/bounce timestamps) — see AnalyticsService.
    collaterals: Mapped[list["CampaignCollateralLink"]] = relationship(
        "CampaignCollateralLink", back_populates="campaign"
    )
    campaignResults: Mapped[list["CampaignResult"]] = relationship(
        "CampaignResult", back_populates="campaign"
    )
    deals: Mapped[list["Deal"]] = relationship(
        "Deal", back_populates="campaign"
    )
    optimizationRules: Mapped[list["OptimizationRule"]] = relationship(  # noqa: F821
        "OptimizationRule", back_populates="campaign"
    )
    optimizationActions: Mapped[list["OptimizationAction"]] = relationship(  # noqa: F821
        "OptimizationAction", back_populates="campaign"
    )
    abTests: Mapped[list["AbTest"]] = relationship(
        "AbTest", back_populates="campaign"
    )
    emailAbTests: Mapped[list["EmailAbTest"]] = relationship(
        "EmailAbTest", back_populates="campaign"
    )
 
 
class CampaignProspect(Base, CuidPrimaryKey):
    """M:N junction between Campaign and Prospect."""
 
    __tablename__ = "CampaignProspect"
    __table_args__ = (
        UniqueConstraint("campaignId", "prospectId", name="uq_CampaignProspect_campaign_prospect"),
    )
 
    campaignId: Mapped[str] = mapped_column(
        String, ForeignKey("Campaign.id"), nullable=False
    )
    prospectId: Mapped[str] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
 
    campaign: Mapped["Campaign"] = relationship(
        "Campaign", back_populates="prospects"
    )
    prospect: Mapped["Prospect"] = relationship(  # noqa: F821
        "Prospect", back_populates="campaigns"
    )
 
 
# ── Collateral Library ──────────────────────────────────────────────────────
 
 
class Collateral(Base, CuidPrimaryKey, TimestampMixin):
    """Shared collateral library — case studies, decks, one-pagers, etc."""
 
    __tablename__ = "Collateral"
 
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    fileName: Mapped[str | None] = mapped_column(String, nullable=True)
    fileSize: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mimeType: Mapped[str | None] = mapped_column(String, nullable=True)
 
    campaignLinks: Mapped[list["CampaignCollateralLink"]] = relationship(
        "CampaignCollateralLink", back_populates="collateral"
    )
 
 
class CampaignCollateralLink(Base, CuidPrimaryKey):
    """M:N join between campaigns and the shared collateral library."""
 
    __tablename__ = "CampaignCollateralLink"
    __table_args__ = (
        UniqueConstraint("collateralId", "campaignId", name="uq_CampCollateral_collateral_campaign"),
        Index("ix_CampaignCollateralLink_campaignId", "campaignId"),
    )
 
    collateralId: Mapped[str] = mapped_column(
        String, ForeignKey("Collateral.id", ondelete="CASCADE"), nullable=False
    )
    campaignId: Mapped[str] = mapped_column(
        String, ForeignKey("Campaign.id", ondelete="CASCADE"), nullable=False
    )
    sortOrder: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
 
    collateral: Mapped["Collateral"] = relationship(
        "Collateral", back_populates="campaignLinks"
    )
    campaign: Mapped["Campaign"] = relationship(
        "Campaign", back_populates="collaterals"
    )
 
 
# ── Sequence (7-touch cadence) ──────────────────────────────────────────────
 
 
class Sequence(Base, CuidPrimaryKey, TimestampMixin):
    """One email touch in a 7-touch cadence (days 1/4/9/16/25/35)."""
 
    __tablename__ = "Sequence"
    __table_args__ = (
        Index("ix_Sequence_campaignId_prospectId", "campaignId", "prospectId"),
        Index("ix_Sequence_owner_user_id", "owner_user_id"),
    )
 
    campaignId: Mapped[str] = mapped_column(
        String, ForeignKey("Campaign.id"), nullable=False
    )
    prospectId: Mapped[str] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=False
    )
    # Owner — denormalized from Campaign.owner_user_id for fast per-user queries.
    # 'system' is the backfill default for rows created before per-user ownership.
    owner_user_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default="system", server_default="system"
    )
    # Sender identity — set at send-time, independent of who created the sequence.
    #
    # sent_by_user_id: Keycloak UUID of the Outrena user who actually triggered
    #   the outbound send (may differ from owner_user_id when a manager sends a
    #   sequence that an admin generated).  NULL on unsent / legacy rows.
    #
    # sent_via_external_user_id: the exact `external_user_id` value passed to
    #   MailBridge's POST /outbound/send.  This is what MailBridge used to route
    #   the email through a connected mailbox, so the reply-poller must use THIS
    #   value (not owner_user_id) when calling GET /auth/connect/replies.
    #   Usually equals sent_by_user_id; differs when a MailBridgeConfig has a
    #   static mailbridge_external_user_id override (shared SMTP account).
    #   NULL on unsent / legacy rows — poller falls back to owner_user_id.
    sent_by_user_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default=None
    )
    sent_via_external_user_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default=None
    )
    touchNumber: Mapped[int] = mapped_column(Integer, nullable=False)
    sendDay: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String, nullable=False, default="email")
    angle: Mapped[TouchAngle] = mapped_column(
        SAEnum(TouchAngle, name="touch_angle", create_type=False, native_enum=False),
        nullable=False,
        default=TouchAngle.FirstTouch,
    )
    framework: Mapped[str | None] = mapped_column(String, nullable=True)
    subjectLine: Mapped[str | None] = mapped_column(String, nullable=True)
    bodyCopy: Mapped[str | None] = mapped_column(Text, nullable=True)
    qaScore: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qaDetails: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    personalisationConfidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    flagForManualReview: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[EmailStatus] = mapped_column(
        SAEnum(EmailStatus, name="email_status", create_type=False, native_enum=False),
        nullable=False,
        default=EmailStatus.Draft,
    )
    sentAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    openedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repliedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bouncedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mailBridgeMessageId: Mapped[str | None] = mapped_column(String, nullable=True)
    bounceReason: Mapped[str | None] = mapped_column(String, nullable=True)
 
    campaign: Mapped["Campaign"] = relationship(
        "Campaign", back_populates="sequences"
    )
    prospect: Mapped["Prospect"] = relationship(  # noqa: F821
        "Prospect", back_populates="sequences"
    )
    subjectLines: Mapped[list["SubjectLine"]] = relationship(
        "SubjectLine", back_populates="sequence"
    )
    replyDrafts: Mapped[list["ReplyDraft"]] = relationship(
        "ReplyDraft", back_populates="sequence"
    )
 
 
class SubjectLine(Base, CuidPrimaryKey):
    """Subject-line variants per sequence (for A/B selection)."""
 
    __tablename__ = "SubjectLine"
 
    sequenceId: Mapped[str] = mapped_column(
        String, ForeignKey("Sequence.id"), nullable=False
    )
    variant: Mapped[str] = mapped_column(String, nullable=False)
    isSelected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
 
    sequence: Mapped["Sequence"] = relationship(
        "Sequence", back_populates="subjectLines"
    )
 
 
# ── Campaign Results ────────────────────────────────────────────────────────
# NOTE (Task 3-a / FIX 1): the dead `CampaignMetric` model was removed —
# no service ever wrote to that table. Analytics now aggregates directly
# from the Sequence table (the source of truth for send/open/reply/bounce
# timestamps). See `AnalyticsService._aggregate_from_sequences` and the
# `0010_drop_campaign_metrics` migration.
 
 
class CampaignResult(Base, CuidPrimaryKey):
    """AI-generated post-mortem summary of a campaign."""
 
    __tablename__ = "CampaignResult"
    __table_args__ = (
        Index("ix_CampaignResult_campaignId", "campaignId"),
    )
 
    campaignId: Mapped[str] = mapped_column(
        String, ForeignKey("Campaign.id", ondelete="CASCADE"), nullable=False
    )
    totalSent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalReplied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalPositive: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    totalBounced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    replyRate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    positiveReplyRate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    bounceRate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    whatWorked: Mapped[str | None] = mapped_column(String, nullable=True)
    whatDidntWork: Mapped[str | None] = mapped_column(String, nullable=True)
    nextActions: Mapped[str | None] = mapped_column(String, nullable=True)
    insights: Mapped[str | None] = mapped_column(String, nullable=True)
    generatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
 
    campaign: Mapped["Campaign"] = relationship(
        "Campaign", back_populates="campaignResults"
    )
 
 
# ── Deal / Pipeline ─────────────────────────────────────────────────────────
 
 
class Deal(Base, CuidPrimaryKey, TimestampMixin):
    """Pipeline deal — Kanban stage tracking + health monitoring."""
 
    __tablename__ = "Deal"
 
    title: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stage: Mapped[str] = mapped_column(String, nullable=False, default="qualified")
    prospectId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=True
    )
    campaignId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Campaign.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    expectedClose: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="cold_email")
    healthStatus: Mapped[str | None] = mapped_column(String, nullable=True)
    healthReason: Mapped[str | None] = mapped_column(String, nullable=True)
    healthCheckedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
 
    prospect: Mapped["Prospect | None"] = relationship(  # noqa: F821
        "Prospect", back_populates="deals"
    )
    campaign: Mapped["Campaign | None"] = relationship(
        "Campaign", back_populates="deals"
    )
 
 
# ── Reply Drafts ────────────────────────────────────────────────────────────
 
 
 
class CrmSyncLog(Base, CuidPrimaryKey, TimestampMixin):
    """
    Audit trail for every CRM export / Push-to-CRM action (Help Guide §Deals).
 
    Records: who exported, when, how many deals, and a breakdown of the
    deal stages exported — so sales ops can prove a specific deal set was
    handed off to the CRM on a specific date by a specific user.
    """
 
    __tablename__ = "CrmSyncLog"
 
    exportedByUserId: Mapped[str] = mapped_column(String, nullable=False)
    dealCount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    crmProvider: Mapped[str | None] = mapped_column(
        String, nullable=True, default="manual"
    )
    # JSON: {stage: count} breakdown — e.g. {"qualified": 3, "closed_won": 1}
    stageBreakdown: Mapped[dict | None] = mapped_column(PG_JSON, nullable=True)
    # JSON: intent source distribution — e.g. {"apollo": 2, "csv": 2}
    sourceBreakdown: Mapped[dict | None] = mapped_column(PG_JSON, nullable=True)
    exportedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
 
 
class ReplyDraft(Base, CuidPrimaryKey, TimestampMixin):
    """Auto-drafted reply to a prospect's email response."""
 
    __tablename__ = "ReplyDraft"
 
    sequenceId: Mapped[str] = mapped_column(
        String, ForeignKey("Sequence.id"), nullable=False
    )
    prospectId: Mapped[str] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=False
    )
    originalReply: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    suggestedAction: Mapped[str | None] = mapped_column(String, nullable=True)
    draftBody: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    sentAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    autoPilotEligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    autoSentAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meetingProposedTime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meetingBookedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meetingCalendarLink: Mapped[str | None] = mapped_column(String, nullable=True)
 
    sequence: Mapped["Sequence"] = relationship(
        "Sequence", back_populates="replyDrafts"
    )
    prospect: Mapped["Prospect"] = relationship(  # noqa: F821
        "Prospect", back_populates="replyDrafts"
    )
 
 
# ── A/B Split-Cohort Testing ────────────────────────────────────────────────
 
 
class AbTest(Base, CuidPrimaryKey, TimestampMixin):
    """Split-cohort test for subject/body variants on a campaign touch."""
 
    __tablename__ = "AbTest"
    __table_args__ = (
        Index("ix_AbTest_campaignId", "campaignId"),
        Index("ix_AbTest_status", "status"),
    )
 
    name: Mapped[str] = mapped_column(String, nullable=False)
    campaignId: Mapped[str] = mapped_column(
        String, ForeignKey("Campaign.id"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    element: Mapped[str] = mapped_column(String, nullable=False)
    variantALabel: Mapped[str] = mapped_column(String, nullable=False, default="Variant A")
    variantBLabel: Mapped[str] = mapped_column(String, nullable=False, default="Variant B")
    variantASubject: Mapped[str | None] = mapped_column(String, nullable=True)
    variantBSubject: Mapped[str | None] = mapped_column(String, nullable=True)
    variantABody: Mapped[str | None] = mapped_column(Text, nullable=True)
    variantBBody: Mapped[str | None] = mapped_column(Text, nullable=True)
    splitRatio: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    touchNumber: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    startedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    endedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
 
    campaign: Mapped["Campaign"] = relationship(
        "Campaign", back_populates="abTests"
    )
    assignments: Mapped[list["AbTestAssignment"]] = relationship(
        "AbTestAssignment", back_populates="abTest"
    )
 
 
class AbTestAssignment(Base, CuidPrimaryKey):
    """Per-prospect variant assignment within an AbTest."""
 
    __tablename__ = "AbTestAssignment"
    __table_args__ = (
        UniqueConstraint("abTestId", "prospectId", name="uq_AbTestAssignment_test_prospect"),
        Index("ix_AbTestAssignment_abTestId_variant", "abTestId", "variant"),
    )
 
    abTestId: Mapped[str] = mapped_column(
        String, ForeignKey("AbTest.id"), nullable=False
    )
    prospectId: Mapped[str] = mapped_column(
        String, ForeignKey("Prospect.id"), nullable=False
    )
    variant: Mapped[str] = mapped_column(String, nullable=False)
    sequenceId: Mapped[str | None] = mapped_column(
        String, ForeignKey("Sequence.id"), nullable=True
    )
    sentAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    openedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repliedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bouncedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replyCategory: Mapped[str | None] = mapped_column(String, nullable=True)
    isPositiveReply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
 
    abTest: Mapped["AbTest"] = relationship(
        "AbTest", back_populates="assignments"
    )
    prospect: Mapped["Prospect"] = relationship(  # noqa: F821
        "Prospect", back_populates="abTestAssignments", foreign_keys=[prospectId]
    )
 
 
# ── Email-level A/B Testing ─────────────────────────────────────────────────
 
 
class EmailAbTest(Base, CuidPrimaryKey, TimestampMixin):
    """Per-campaign subject-line A/B test with deterministic assignment."""
 
    __tablename__ = "EmailAbTest"
    __table_args__ = (
        Index("ix_EmailAbTest_campaignId", "campaignId"),
    )
 
    campaignId: Mapped[str] = mapped_column(
        String, ForeignKey("Campaign.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    subjectA: Mapped[str] = mapped_column(String, nullable=False)
    subjectB: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    winner: Mapped[str | None] = mapped_column(String, nullable=True)
    startedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
 
    campaign: Mapped["Campaign"] = relationship(
        "Campaign", back_populates="emailAbTests"
    )