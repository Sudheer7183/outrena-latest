"""
flow_run.py — Pydantic schemas for ProspectingFlow + FlowRun + FlowRunStep
+ FlowAbTest + FlowWebhook + FlowWebhookDelivery.

Created by FIX-BE-1 / CRITICAL 1: the underlying ORM models in
``app/models/flow_models.py`` previously had NO service/route/schema
surface (audit §D1). These schemas back the new ``app/api/v1/flows.py``
router and the FlowRun records created by ``autopilot_service``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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


# ── ProspectingFlow ────────────────────────────────────────────────────────


class ProspectingFlowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    isDefault: bool = False
    isActive: bool = True
    isTemplate: bool = False
    templateTag: str | None = None
    templateIcon: str | None = None
    templateColor: str | None = None
    sourceSteps: str = "[]"
    enrichmentSteps: str = "[]"
    qualityGates: str = "{}"


class ProspectingFlowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    isDefault: bool | None = None
    isActive: bool | None = None
    isTemplate: bool | None = None
    templateTag: str | None = None
    templateIcon: str | None = None
    templateColor: str | None = None
    sourceSteps: str | None = None
    enrichmentSteps: str | None = None
    qualityGates: str | None = None


class ProspectingFlowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    isDefault: bool
    isActive: bool
    isTemplate: bool
    templateTag: str | None = None
    templateIcon: str | None = None
    templateColor: str | None = None
    sourceSteps: str
    enrichmentSteps: str
    qualityGates: str
    createdAt: datetime
    updatedAt: datetime


class ProspectingFlowListResponse(BaseModel):
    items: list[ProspectingFlowResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


# ── FlowRun ────────────────────────────────────────────────────────────────


class FlowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    flowId: str
    icpProfileId: str
    status: FlowRunStatus
    triggeredBy: str
    triggeredById: str | None = None
    config: str
    stats: str
    importedProspectIds: str
    errorMessage: str | None = None
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime
    steps: list["FlowRunStepResponse"] = Field(default_factory=list)


class FlowRunListResponse(BaseModel):
    items: list[FlowRunResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


class FlowRunCreateRequest(BaseModel):
    """Body for POST /flows/{flow_id}/runs — enqueue a flow run."""

    icpProfileId: str = Field(..., min_length=1)
    triggeredBy: str = "manual"
    config: str = "{}"


# ── FlowRunStep ────────────────────────────────────────────────────────────


class FlowRunStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    runId: str
    kind: FlowRunStepKind
    stepKey: str
    order: int
    status: FlowRunStepStatus
    metrics: str
    durationMs: int | None = None
    errorMessage: str | None = None
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    createdAt: datetime


# ── FlowAbTest ─────────────────────────────────────────────────────────────


class FlowAbTestCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    icpProfileId: str = Field(..., min_length=1)
    flowAId: str = Field(..., min_length=1)
    flowBId: str = Field(..., min_length=1)


class FlowAbTestUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: FlowAbTestStatus | None = None
    significance: str | None = None
    summary: str | None = None


class FlowAbTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    icpProfileId: str
    flowAId: str
    flowBId: str
    status: FlowAbTestStatus
    significance: str
    summary: str
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime


class FlowAbTestListResponse(BaseModel):
    items: list[FlowAbTestResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


# ── FlowWebhook ────────────────────────────────────────────────────────────


class FlowWebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1)
    secret: str | None = None
    events: str = "[]"
    flowId: str | None = None
    isActive: bool = True
    config: str = "{}"


class FlowWebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    secret: str | None = None
    events: str | None = None
    flowId: str | None = None
    isActive: bool | None = None
    config: str | None = None


class FlowWebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url: str
    secret: str | None = None
    events: str
    flowId: str | None = None
    isActive: bool
    config: str
    createdAt: datetime
    updatedAt: datetime


class FlowWebhookListResponse(BaseModel):
    items: list[FlowWebhookResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


# ── AutopilotQueue (read-only view of the queue) ───────────────────────────


# ── FlowWebhookDelivery (audit trail) ───────────────────────────────────────


class FlowWebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    webhookId: str
    event: WebhookTriggerEvent
    payload: str
    statusCode: int | None = None
    response: str | None = None
    status: WebhookDeliveryStatus
    attempts: int
    deliveredAt: datetime | None = None
    createdAt: datetime


class FlowWebhookDeliveryListResponse(BaseModel):
    items: list[FlowWebhookDeliveryResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


# ── AutopilotQueue (read-only view of the queue) ───────────────────────────


class AutopilotQueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    flowId: str
    icpProfileId: str
    status: AutopilotQueueStatus
    origin: str
    config: str
    flowRunId: str | None = None
    errorMessage: str | None = None
    queuedAt: datetime
    pickedUpAt: datetime | None = None
    completedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime


class AutopilotQueueListResponse(BaseModel):
    items: list[AutopilotQueueResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


__all__ = [
    "ProspectingFlowCreate",
    "ProspectingFlowUpdate",
    "ProspectingFlowResponse",
    "ProspectingFlowListResponse",
    "FlowRunResponse",
    "FlowRunListResponse",
    "FlowRunCreateRequest",
    "FlowRunStepResponse",
    "FlowAbTestCreate",
    "FlowAbTestUpdate",
    "FlowAbTestResponse",
    "FlowAbTestListResponse",
    "FlowWebhookCreate",
    "FlowWebhookUpdate",
    "FlowWebhookResponse",
    "FlowWebhookListResponse",
    "AutopilotQueueResponse",
    "AutopilotQueueListResponse",
    "FlowWebhookDeliveryResponse",
    "FlowWebhookDeliveryListResponse",
]
