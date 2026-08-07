"""
enums.py — All 13 OUTRENA enums migrated from Prisma.

Each Prisma enum becomes a Python ``str, enum.Enum`` subclass AND a
PostgreSQL ``CREATE TYPE`` (handled by SQLAlchemy's ``Enum`` type at
migration time). Values match the Prisma member names exactly so the
public API contract is unchanged.

Important — per-tenant schema: ``CREATE TYPE`` runs INSIDE each tenant
schema at migration time (see alembic/versions/0001_initial.py), not
just ``public``.
"""
from __future__ import annotations

import enum


class SeniorityTier(str, enum.Enum):
    C_Suite = "C_Suite"
    Director = "Director"
    IC = "IC"


class IntentSource(str, enum.Enum):
    FUNDING_URGENCY = "FUNDING_URGENCY"
    HIRING_BUDGET = "HIRING_BUDGET"
    FORUM_PAIN = "FORUM_PAIN"
    LINKEDIN_DEMAND = "LINKEDIN_DEMAND"
    REFERRAL = "REFERRAL"
    INBOUND = "INBOUND"
    OTHER = "OTHER"


class EnrichmentTier(str, enum.Enum):
    ENRICHED = "ENRICHED"
    PARTIAL = "PARTIAL"
    UNENRICHABLE = "UNENRICHABLE"


class TouchAngle(str, enum.Enum):
    FirstTouch = "FirstTouch"
    NewEvidence = "NewEvidence"
    DifferentPain = "DifferentPain"
    IndustryInsight = "IndustryInsight"
    DirectQuestion = "DirectQuestion"
    Breakup = "Breakup"


class EmailStatus(str, enum.Enum):
    Draft = "Draft"
    QaFailed = "QaFailed"
    QaPassed = "QaPassed"
    Scheduled = "Scheduled"
    Sent = "Sent"
    Replied = "Replied"
    Bounced = "Bounced"
    Failed = "Failed"


class FlowRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RATE_LIMITED = "RATE_LIMITED"


class FlowRunStepKind(str, enum.Enum):
    SOURCE = "SOURCE"
    ENRICHMENT = "ENRICHMENT"
    GATE = "GATE"
    SCORE = "SCORE"
    IMPORT = "IMPORT"


class FlowRunStepStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    GATED_OUT = "GATED_OUT"


class FlowAbTestStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"


class WebhookTriggerEvent(str, enum.Enum):
    ICP_CREATED = "ICP_CREATED"
    FLOW_RUN_COMPLETED = "FLOW_RUN_COMPLETED"
    FLOW_RUN_FAILED = "FLOW_RUN_FAILED"
    PROSPECT_IMPORTED = "PROSPECT_IMPORTED"


class WebhookDeliveryStatus(str, enum.Enum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class AutopilotQueueStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RateLimitWindow(str, enum.Enum):
    MINUTELY = "MINUTELY"
    HOURLY = "HOURLY"
    DAILY = "DAILY"


# Registry for Alembic migration to iterate when creating types per schema.
ALL_ENUMS: tuple[type[enum.Enum], ...] = (
    SeniorityTier,
    IntentSource,
    EnrichmentTier,
    TouchAngle,
    EmailStatus,
    FlowRunStatus,
    FlowRunStepKind,
    FlowRunStepStatus,
    FlowAbTestStatus,
    WebhookTriggerEvent,
    WebhookDeliveryStatus,
    AutopilotQueueStatus,
    RateLimitWindow,
)
