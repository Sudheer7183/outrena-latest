"""
flow_models.py — Prospecting flow engine, autopilot queue, rate limits.

Mirrors Prisma models: ProspectingFlow, FlowRun, FlowRunStep, FlowAbTest,
FlowWebhook, FlowWebhookDelivery, AutopilotQueue, RateLimit, RateLimitLog.

The flow execution engine (SOURCE → ENRICH → GATE → SCORE → IMPORT) is
implemented as a Celery task in Phase 2; these models hold the persistent
state of each flow run and its per-step outcomes.
"""
from __future__ import annotations

from datetime import datetime

from app.models.base import Base, CuidPrimaryKey, TimestampMixin
from app.models.enums import (
    AutopilotQueueStatus,
    FlowAbTestStatus,
    FlowRunStatus,
    FlowRunStepKind,
    FlowRunStepStatus,
    RateLimitWindow,
    WebhookDeliveryStatus,
    WebhookTriggerEvent,
)
from sqlalchemy import (
    Boolean,
    DateTime,
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

# ── Prospecting Flow ────────────────────────────────────────────────────────


class ProspectingFlow(Base, CuidPrimaryKey, TimestampMixin):
    """An orchestrated multi-step pipeline defining HOW platforms work together."""

    __tablename__ = "ProspectingFlow"
    __table_args__ = (
        Index("ix_ProspectingFlow_isDefault", "isDefault"),
        Index("ix_ProspectingFlow_isActive", "isActive"),
        Index("ix_ProspectingFlow_isTemplate", "isTemplate"),
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    isDefault: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Template metadata
    isTemplate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    templateTag: Mapped[str | None] = mapped_column(String, nullable=True)
    templateIcon: Mapped[str | None] = mapped_column(String, nullable=True)
    templateColor: Mapped[str | None] = mapped_column(String, nullable=True)

    # Ordered step configs (JSON)
    sourceSteps: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    enrichmentSteps: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    qualityGates: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )

    runs: Mapped[list["FlowRun"]] = relationship(
        "FlowRun", back_populates="flow"
    )
    abTestsAsA: Mapped[list["FlowAbTest"]] = relationship(
        "FlowAbTest", back_populates="flowA", foreign_keys="FlowAbTest.flowAId"
    )
    abTestsAsB: Mapped[list["FlowAbTest"]] = relationship(
        "FlowAbTest", back_populates="flowB", foreign_keys="FlowAbTest.flowBId"
    )
    webhooks: Mapped[list["FlowWebhook"]] = relationship(
        "FlowWebhook", back_populates="flow"
    )
    autopilotQueue: Mapped[list["AutopilotQueue"]] = relationship(
        "AutopilotQueue", back_populates="flow"
    )


# ── Flow Run ────────────────────────────────────────────────────────────────


class FlowRun(Base, CuidPrimaryKey, TimestampMixin):
    """A single execution of a flow against an ICP."""

    __tablename__ = "FlowRun"
    __table_args__ = (
        Index("ix_FlowRun_flowId", "flowId"),
        Index("ix_FlowRun_icpProfileId", "icpProfileId"),
        Index("ix_FlowRun_status", "status"),
        Index("ix_FlowRun_triggeredBy", "triggeredBy"),
    )

    flowId: Mapped[str] = mapped_column(
        String, ForeignKey("ProspectingFlow.id", ondelete="CASCADE"), nullable=False
    )
    icpProfileId: Mapped[str] = mapped_column(
        String, ForeignKey("IcpProfile.id"), nullable=False
    )
    status: Mapped[FlowRunStatus] = mapped_column(
        SAEnum(FlowRunStatus, name="flow_run_status", create_type=False),
        nullable=False,
        default=FlowRunStatus.PENDING,
    )
    triggeredBy: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    triggeredById: Mapped[str | None] = mapped_column(String, nullable=True)
    config: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    stats: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    importedProspectIds: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    errorMessage: Mapped[str | None] = mapped_column(String, nullable=True)
    startedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    flow: Mapped["ProspectingFlow"] = relationship(
        "ProspectingFlow", back_populates="runs"
    )
    icpProfile: Mapped["IcpProfile"] = relationship(  # noqa: F821
        "IcpProfile", back_populates="flowRuns"
    )
    steps: Mapped[list["FlowRunStep"]] = relationship(
        "FlowRunStep", back_populates="run"
    )


class FlowRunStep(Base, CuidPrimaryKey):
    """Per-step outcome within a flow run. One row per executed step."""

    __tablename__ = "FlowRunStep"
    __table_args__ = (
        Index("ix_FlowRunStep_runId", "runId"),
        Index("ix_FlowRunStep_kind", "kind"),
    )

    runId: Mapped[str] = mapped_column(
        String, ForeignKey("FlowRun.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[FlowRunStepKind] = mapped_column(
        SAEnum(FlowRunStepKind, name="flow_run_step_kind", create_type=False),
        nullable=False,
    )
    stepKey: Mapped[str] = mapped_column(String, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[FlowRunStepStatus] = mapped_column(
        SAEnum(FlowRunStepStatus, name="flow_run_step_status", create_type=False),
        nullable=False,
        default=FlowRunStepStatus.PENDING,
    )
    metrics: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    durationMs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    errorMessage: Mapped[str | None] = mapped_column(String, nullable=True)
    startedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped["FlowRun"] = relationship(
        "FlowRun", back_populates="steps"
    )


# ── Flow A/B Testing ────────────────────────────────────────────────────────


class FlowAbTest(Base, CuidPrimaryKey, TimestampMixin):
    """Runs two flows against the same ICP and compares outcomes."""

    __tablename__ = "FlowAbTest"
    __table_args__ = (
        Index("ix_FlowAbTest_icpProfileId", "icpProfileId"),
        Index("ix_FlowAbTest_status", "status"),
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    icpProfileId: Mapped[str] = mapped_column(
        String, ForeignKey("IcpProfile.id"), nullable=False
    )
    flowAId: Mapped[str] = mapped_column(
        String, ForeignKey("ProspectingFlow.id"), nullable=False
    )
    flowBId: Mapped[str] = mapped_column(
        String, ForeignKey("ProspectingFlow.id"), nullable=False
    )
    status: Mapped[FlowAbTestStatus] = mapped_column(
        SAEnum(FlowAbTestStatus, name="flow_ab_test_status", create_type=False),
        nullable=False,
        default=FlowAbTestStatus.DRAFT,
    )
    significance: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    summary: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    startedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    icpProfile: Mapped["IcpProfile"] = relationship(  # noqa: F821
        "IcpProfile", back_populates="flowAbTests"
    )
    flowA: Mapped["ProspectingFlow"] = relationship(
        "ProspectingFlow", back_populates="abTestsAsA", foreign_keys=[flowAId]
    )
    flowB: Mapped["ProspectingFlow"] = relationship(
        "ProspectingFlow", back_populates="abTestsAsB", foreign_keys=[flowBId]
    )


# ── Flow Webhooks ───────────────────────────────────────────────────────────


class FlowWebhook(Base, CuidPrimaryKey, TimestampMixin):
    """Outbound webhook trigger config (ICP_CREATED, FLOW_RUN_COMPLETED, etc.)."""

    __tablename__ = "FlowWebhook"
    __table_args__ = (
        Index("ix_FlowWebhook_flowId", "flowId"),
        Index("ix_FlowWebhook_isActive", "isActive"),
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    secret: Mapped[str | None] = mapped_column(String, nullable=True)
    events: Mapped[list] = mapped_column(
        PG_JSON, nullable=False, default=list, server_default="[]"
    )
    flowId: Mapped[str | None] = mapped_column(
        String, ForeignKey("ProspectingFlow.id", ondelete="SET NULL"), nullable=True
    )
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )

    flow: Mapped["ProspectingFlow | None"] = relationship(
        "ProspectingFlow", back_populates="webhooks"
    )
    deliveries: Mapped[list["FlowWebhookDelivery"]] = relationship(
        "FlowWebhookDelivery", back_populates="webhook"
    )


class FlowWebhookDelivery(Base, CuidPrimaryKey):
    """Immutable log of every webhook delivery attempt."""

    __tablename__ = "FlowWebhookDelivery"
    __table_args__ = (
        Index("ix_FlowWebhookDelivery_webhookId", "webhookId"),
        Index("ix_FlowWebhookDelivery_status", "status"),
    )

    webhookId: Mapped[str] = mapped_column(
        String, ForeignKey("FlowWebhook.id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[WebhookTriggerEvent] = mapped_column(
        SAEnum(WebhookTriggerEvent, name="webhook_trigger_event", create_type=False),
        nullable=False,
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    statusCode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        SAEnum(WebhookDeliveryStatus, name="webhook_delivery_status", create_type=False),
        nullable=False,
        default=WebhookDeliveryStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deliveredAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    webhook: Mapped["FlowWebhook"] = relationship(
        "FlowWebhook", back_populates="deliveries"
    )


# ── Autopilot Queue ─────────────────────────────────────────────────────────


class AutopilotQueue(Base, CuidPrimaryKey, TimestampMixin):
    """Queue of pending autopilot flow runs (consumed by the scheduler)."""

    __tablename__ = "AutopilotQueue"
    __table_args__ = (
        Index("ix_AutopilotQueue_status", "status"),
        Index("ix_AutopilotQueue_flowId", "flowId"),
        Index("ix_AutopilotQueue_icpProfileId", "icpProfileId"),
    )

    flowId: Mapped[str] = mapped_column(
        String, ForeignKey("ProspectingFlow.id", ondelete="CASCADE"), nullable=False
    )
    icpProfileId: Mapped[str | None] = mapped_column(
        String, ForeignKey("IcpProfile.id"), nullable=True, default=None
    )
    status: Mapped[AutopilotQueueStatus] = mapped_column(
        SAEnum(AutopilotQueueStatus, name="autopilot_queue_status", create_type=False),
        nullable=False,
        default=AutopilotQueueStatus.QUEUED,
    )
    origin: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    config: Mapped[dict] = mapped_column(
        PG_JSON, nullable=False, default=dict, server_default="{}"
    )
    flowRunId: Mapped[str | None] = mapped_column(
        String, ForeignKey("FlowRun.id"), nullable=True
    )
    errorMessage: Mapped[str | None] = mapped_column(String, nullable=True)
    queuedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    pickedUpAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    flow: Mapped["ProspectingFlow"] = relationship(
        "ProspectingFlow", back_populates="autopilotQueue"
    )
    icpProfile: Mapped["IcpProfile"] = relationship(  # noqa: F821
        "IcpProfile", back_populates="autopilotQueue"
    )


# ── Rate Limit Management ───────────────────────────────────────────────────


class RateLimit(Base, CuidPrimaryKey, TimestampMixin):
    """Per-platform / per-source rate limit configuration + counter."""

    __tablename__ = "RateLimit"
    __table_args__ = (
        Index("ix_RateLimit_platform", "platform"),
        Index("ix_RateLimit_key", "key"),
    )

    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str | None] = mapped_column(String, nullable=True)
    window: Mapped[RateLimitWindow] = mapped_column(
        SAEnum(RateLimitWindow, name="rate_limit_window", create_type=False),
        nullable=False,
        default=RateLimitWindow.HOURLY,
    )
    limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    windowStart: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    throttleMode: Mapped[str] = mapped_column(String, nullable=False, default="skip")
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RateLimitLog(Base, CuidPrimaryKey):
    """Immutable log of every rate-limited API call (analytics + audit)."""

    __tablename__ = "RateLimitLog"
    __table_args__ = (
        Index("ix_RateLimitLog_key", "key"),
        Index("ix_RateLimitLog_platform", "platform"),
        Index("ix_RateLimitLog_createdAt", "createdAt"),
        Index("ix_RateLimitLog_flowRunId", "flowRunId"),
    )

    key: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    flowRunId: Mapped[str | None] = mapped_column(
        String, ForeignKey("FlowRun.id"), nullable=True
    )
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
