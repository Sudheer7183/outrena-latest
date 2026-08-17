# """
# flow_run.py — Pydantic schemas for ProspectingFlow + FlowRun + FlowRunStep
# + FlowAbTest + FlowWebhook + FlowWebhookDelivery.

# Created by FIX-BE-1 / CRITICAL 1: the underlying ORM models in
# ``app/models/flow_models.py`` previously had NO service/route/schema
# surface (audit §D1). These schemas back the new ``app/api/v1/flows.py``
# router and the FlowRun records created by ``autopilot_service``.
# """
# from __future__ import annotations

# from datetime import datetime
# from typing import Any

# from pydantic import BaseModel, ConfigDict, Field

# from app.models.enums import (
#     AutopilotQueueStatus,
#     FlowAbTestStatus,
#     FlowRunStatus,
#     FlowRunStepKind,
#     FlowRunStepStatus,
#     RateLimitWindow,
#     WebhookDeliveryStatus,
#     WebhookTriggerEvent,
# )


# # ── ProspectingFlow ────────────────────────────────────────────────────────


# class ProspectingFlowCreate(BaseModel):
#     name: str = Field(..., min_length=1, max_length=200)
#     description: str | None = None
#     isDefault: bool = False
#     isActive: bool = True
#     isTemplate: bool = False
#     templateTag: str | None = None
#     templateIcon: str | None = None
#     templateColor: str | None = None
#     sourceSteps: str = "[]"
#     enrichmentSteps: str = "[]"
#     qualityGates: str = "{}"


# class ProspectingFlowUpdate(BaseModel):
#     name: str | None = None
#     description: str | None = None
#     isDefault: bool | None = None
#     isActive: bool | None = None
#     isTemplate: bool | None = None
#     templateTag: str | None = None
#     templateIcon: str | None = None
#     templateColor: str | None = None
#     sourceSteps: str | None = None
#     enrichmentSteps: str | None = None
#     qualityGates: str | None = None


# class ProspectingFlowResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: str
#     name: str
#     description: str | None = None
#     isDefault: bool
#     isActive: bool
#     isTemplate: bool
#     templateTag: str | None = None
#     templateIcon: str | None = None
#     templateColor: str | None = None
#     sourceSteps: str
#     enrichmentSteps: str
#     qualityGates: str
#     createdAt: datetime
#     updatedAt: datetime


# class ProspectingFlowListResponse(BaseModel):
#     items: list[ProspectingFlowResponse]
#     total: int = 0
#     limit: int = 50
#     offset: int = 0


# # ── FlowRun ────────────────────────────────────────────────────────────────


# class FlowRunResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: str
#     flowId: str
#     icpProfileId: str
#     status: FlowRunStatus
#     triggeredBy: str
#     triggeredById: str | None = None
#     config: str
#     stats: str
#     importedProspectIds: str
#     errorMessage: str | None = None
#     startedAt: datetime | None = None
#     completedAt: datetime | None = None
#     createdAt: datetime
#     updatedAt: datetime
#     steps: list["FlowRunStepResponse"] = Field(default_factory=list)


# class FlowRunListResponse(BaseModel):
#     items: list[FlowRunResponse]
#     total: int = 0
#     limit: int = 50
#     offset: int = 0


# class FlowRunCreateRequest(BaseModel):
#     """Body for POST /flows/{flow_id}/runs — enqueue a flow run."""

#     icpProfileId: str = Field(..., min_length=1)
#     triggeredBy: str = "manual"
#     config: str = "{}"


# # ── FlowRunStep ────────────────────────────────────────────────────────────


# class FlowRunStepResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: str
#     runId: str
#     kind: FlowRunStepKind
#     stepKey: str
#     order: int
#     status: FlowRunStepStatus
#     metrics: str
#     durationMs: int | None = None
#     errorMessage: str | None = None
#     startedAt: datetime | None = None
#     completedAt: datetime | None = None
#     createdAt: datetime


# # ── FlowAbTest ─────────────────────────────────────────────────────────────


# class FlowAbTestCreate(BaseModel):
#     name: str = Field(..., min_length=1, max_length=200)
#     description: str | None = None
#     icpProfileId: str = Field(..., min_length=1)
#     flowAId: str = Field(..., min_length=1)
#     flowBId: str = Field(..., min_length=1)


# class FlowAbTestUpdate(BaseModel):
#     name: str | None = None
#     description: str | None = None
#     status: FlowAbTestStatus | None = None
#     significance: str | None = None
#     summary: str | None = None


# class FlowAbTestResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: str
#     name: str
#     description: str | None = None
#     icpProfileId: str
#     flowAId: str
#     flowBId: str
#     status: FlowAbTestStatus
#     significance: str
#     summary: str
#     startedAt: datetime | None = None
#     completedAt: datetime | None = None
#     createdAt: datetime
#     updatedAt: datetime


# class FlowAbTestListResponse(BaseModel):
#     items: list[FlowAbTestResponse]
#     total: int = 0
#     limit: int = 50
#     offset: int = 0


# # ── FlowWebhook ────────────────────────────────────────────────────────────


# class FlowWebhookCreate(BaseModel):
#     name: str = Field(..., min_length=1, max_length=200)
#     url: str = Field(..., min_length=1)
#     secret: str | None = None
#     events: str = "[]"
#     flowId: str | None = None
#     isActive: bool = True
#     config: str = "{}"


# class FlowWebhookUpdate(BaseModel):
#     name: str | None = None
#     url: str | None = None
#     secret: str | None = None
#     events: str | None = None
#     flowId: str | None = None
#     isActive: bool | None = None
#     config: str | None = None


# class FlowWebhookResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: str
#     name: str
#     url: str
#     secret: str | None = None
#     events: str
#     flowId: str | None = None
#     isActive: bool
#     config: str
#     createdAt: datetime
#     updatedAt: datetime


# class FlowWebhookListResponse(BaseModel):
#     items: list[FlowWebhookResponse]
#     total: int = 0
#     limit: int = 50
#     offset: int = 0


# # ── AutopilotQueue (read-only view of the queue) ───────────────────────────


# # ── FlowWebhookDelivery (audit trail) ───────────────────────────────────────


# class FlowWebhookDeliveryResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: str
#     webhookId: str
#     event: WebhookTriggerEvent
#     payload: str
#     statusCode: int | None = None
#     response: str | None = None
#     status: WebhookDeliveryStatus
#     attempts: int
#     deliveredAt: datetime | None = None
#     createdAt: datetime


# class FlowWebhookDeliveryListResponse(BaseModel):
#     items: list[FlowWebhookDeliveryResponse]
#     total: int = 0
#     limit: int = 50
#     offset: int = 0


# # ── AutopilotQueue (read-only view of the queue) ───────────────────────────


# class AutopilotQueueResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: str
#     flowId: str
#     icpProfileId: str
#     status: AutopilotQueueStatus
#     origin: str
#     config: str
#     flowRunId: str | None = None
#     errorMessage: str | None = None
#     queuedAt: datetime
#     pickedUpAt: datetime | None = None
#     completedAt: datetime | None = None
#     createdAt: datetime
#     updatedAt: datetime


# class AutopilotQueueListResponse(BaseModel):
#     items: list[AutopilotQueueResponse]
#     total: int = 0
#     limit: int = 50
#     offset: int = 0


# __all__ = [
#     "ProspectingFlowCreate",
#     "ProspectingFlowUpdate",
#     "ProspectingFlowResponse",
#     "ProspectingFlowListResponse",
#     "FlowRunResponse",
#     "FlowRunListResponse",
#     "FlowRunCreateRequest",
#     "FlowRunStepResponse",
#     "FlowAbTestCreate",
#     "FlowAbTestUpdate",
#     "FlowAbTestResponse",
#     "FlowAbTestListResponse",
#     "FlowWebhookCreate",
#     "FlowWebhookUpdate",
#     "FlowWebhookResponse",
#     "FlowWebhookListResponse",
#     "AutopilotQueueResponse",
#     "AutopilotQueueListResponse",
#     "FlowWebhookDeliveryResponse",
#     "FlowWebhookDeliveryListResponse",
# ]

"""
flow_run.py — Pydantic schemas for ProspectingFlow + FlowRun + FlowRunStep
+ FlowAbTest + FlowWebhook + FlowWebhookDelivery.

Created by FIX-BE-1 / CRITICAL 1: the underlying ORM models in
``app/models/flow_models.py`` previously had NO service/route/schema
surface (audit §D1). These schemas back the new ``app/api/v1/flows.py``
router and the FlowRun records created by ``autopilot_service``.

FIX (this revision): every JSON/list-backed column in flow_models.py is
declared ``Mapped[dict]`` or ``Mapped[list]`` (backed by a native
``PG_JSON`` column, which SQLAlchemy serializes/deserializes automatically)
- but every schema in this file had the corresponding field typed as a bare
``str``, with defaults like ``"[]"``/``"{}"`` literal strings. This caused
two classes of bugs:
  1. Response validation crashes: pydantic's ``str`` type does not coerce a
     dict/list, so ``Response.model_validate(item)`` raised
     ``ValidationError: Input should be a valid string`` the moment any of
     these fields held actual data (confirmed live on FlowAbTestResponse's
     significance/summary fields).
  2. Silent data corruption on write: passing the string literal ``"[]"``
     into a PG_JSON column doesn't produce an empty JSON array - it writes
     the JSON string value ``"[]"`` (i.e. the two characters, JSON-encoded
     as a string), not an actual array. Every Create schema's string
     defaults had this problem.
Every field below is now typed to match its real column
(``dict``/``list``), with correct defaults (``Field(default_factory=...)``
instead of string literals). No field_validator was needed anywhere in
this file - there were no existing validators handling JSON string
parsing, so this is a pure type-annotation correction, not a behavior
change beyond fixing the mismatch itself.
"""
from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    AutopilotQueueStatus,
    FlowAbTestStatus,
    FlowRunStatus,
    FlowRunStepKind,
    FlowRunStepStatus,
    WebhookDeliveryStatus,
    WebhookTriggerEvent,
)


def _coerce_dict(v: object) -> object:
    """Best-effort coercion for dict-typed fields.

    The `flow_models.py` ORM declares these columns `Mapped[dict]` with a
    native `PG_JSON` type, but the actual migration
    (`0002_initial_tenant.py`) created every one of them as plain
    `sa.Text()` with a literal string default (e.g. `server_default="'{}'"`).
    Depending on how a given row was written, the value read back has been
    observed in THREE different shapes:
      - already a real dict (fine, pass through)
      - a single JSON-encoded string, e.g. "{}" (needs one json.loads())
      - a DOUBLE JSON-encoded string, e.g. '"{}"' — a JSON string whose
        content is itself the JSON text "{}" (needs two json.loads() calls;
        confirmed live via the /api/v1/flows list endpoint)
    This loops decoding until it reaches a real dict, stops making
    progress, or hits a safety cap — so it's correct regardless of how many
    encoding layers a particular row happens to have.
    """
    seen = v
    for _ in range(5):
        if isinstance(seen, dict):
            return seen
        if not isinstance(seen, str):
            return v
        try:
            parsed = json.loads(seen)
        except (ValueError, TypeError):
            return v
        if parsed == seen:
            return v
        seen = parsed
    return seen if isinstance(seen, dict) else v


def _coerce_list(v: object) -> object:
    """Same as `_coerce_dict`, for list-typed fields (sourceSteps, events, etc.)."""
    seen = v
    for _ in range(5):
        if isinstance(seen, list):
            return seen
        if not isinstance(seen, str):
            return v
        try:
            parsed = json.loads(seen)
        except (ValueError, TypeError):
            return v
        if parsed == seen:
            return v
        seen = parsed
    return seen if isinstance(seen, list) else v


# ── ProspectingFlow ────────────────────────────────────────────────────────
# Model columns: sourceSteps: list, enrichmentSteps: list, qualityGates: dict


class ProspectingFlowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    isDefault: bool = False
    isActive: bool = True
    isTemplate: bool = False
    templateTag: str | None = None
    templateIcon: str | None = None
    templateColor: str | None = None
    sourceSteps: list = Field(default_factory=list)
    enrichmentSteps: list = Field(default_factory=list)
    qualityGates: dict = Field(default_factory=dict)


class ProspectingFlowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    isDefault: bool | None = None
    isActive: bool | None = None
    isTemplate: bool | None = None
    templateTag: str | None = None
    templateIcon: str | None = None
    templateColor: str | None = None
    sourceSteps: list | None = None
    enrichmentSteps: list | None = None
    qualityGates: dict | None = None


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
    sourceSteps: list
    enrichmentSteps: list
    qualityGates: dict
    createdAt: datetime
    updatedAt: datetime

    @field_validator("sourceSteps", "enrichmentSteps", mode="before")
    @classmethod
    def _validate_list_fields(cls, v: object) -> object:
        return _coerce_list(v)

    @field_validator("qualityGates", mode="before")
    @classmethod
    def _validate_dict_fields(cls, v: object) -> object:
        return _coerce_dict(v)


class ProspectingFlowListResponse(BaseModel):
    items: list[ProspectingFlowResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


# ── FlowRun ────────────────────────────────────────────────────────────────
# Model columns: config: dict, stats: dict, importedProspectIds: list


class FlowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    flowId: str
    icpProfileId: str
    status: FlowRunStatus
    triggeredBy: str
    triggeredById: str | None = None
    config: dict
    stats: dict
    importedProspectIds: list
    errorMessage: str | None = None
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime
    steps: list["FlowRunStepResponse"] = Field(default_factory=list)

    @field_validator("config", "stats", mode="before")
    @classmethod
    def _validate_dict_fields(cls, v: object) -> object:
        return _coerce_dict(v)

    @field_validator("importedProspectIds", mode="before")
    @classmethod
    def _validate_list_fields(cls, v: object) -> object:
        return _coerce_list(v)


class FlowRunListResponse(BaseModel):
    items: list[FlowRunResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


class FlowRunCreateRequest(BaseModel):
    """Body for POST /flows/{flow_id}/runs — enqueue a flow run."""

    icpProfileId: str = Field(..., min_length=1)
    triggeredBy: str = "manual"
    config: dict = Field(default_factory=dict)


# ── FlowRunStep ────────────────────────────────────────────────────────────
# Model column: metrics: dict


class FlowRunStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    runId: str
    kind: FlowRunStepKind
    stepKey: str
    order: int
    status: FlowRunStepStatus
    metrics: dict
    durationMs: int | None = None
    errorMessage: str | None = None
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    createdAt: datetime

    @field_validator("metrics", mode="before")
    @classmethod
    def _validate_metrics(cls, v: object) -> object:
        return _coerce_dict(v)


# ── FlowAbTest ─────────────────────────────────────────────────────────────
# Model columns: significance: dict, summary: dict


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
    significance: dict | None = None
    summary: dict | None = None


class FlowAbTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    icpProfileId: str
    flowAId: str
    flowBId: str
    status: FlowAbTestStatus
    significance: dict
    summary: dict
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime

    @field_validator("significance", "summary", mode="before")
    @classmethod
    def _validate_dict_fields(cls, v: object) -> object:
        return _coerce_dict(v)


class FlowAbTestListResponse(BaseModel):
    items: list[FlowAbTestResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


# ── FlowWebhook ────────────────────────────────────────────────────────────
# Model columns: events: list, config: dict


class FlowWebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1)
    secret: str | None = None
    events: list = Field(default_factory=list)
    flowId: str | None = None
    isActive: bool = True
    config: dict = Field(default_factory=dict)


class FlowWebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    secret: str | None = None
    events: list | None = None
    flowId: str | None = None
    isActive: bool | None = None
    config: dict | None = None


class FlowWebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url: str
    secret: str | None = None
    events: list
    flowId: str | None = None
    isActive: bool
    config: dict
    createdAt: datetime
    updatedAt: datetime

    @field_validator("events", mode="before")
    @classmethod
    def _validate_events(cls, v: object) -> object:
        return _coerce_list(v)

    @field_validator("config", mode="before")
    @classmethod
    def _validate_config(cls, v: object) -> object:
        return _coerce_dict(v)


class FlowWebhookListResponse(BaseModel):
    items: list[FlowWebhookResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


# ── FlowWebhookDelivery (audit trail) ───────────────────────────────────────
# Model column: payload: str (Text) — genuinely a string, left unchanged.


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
# Model column: config: dict


class AutopilotQueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    flowId: str
    icpProfileId: str
    status: AutopilotQueueStatus
    origin: str
    config: dict
    flowRunId: str | None = None
    errorMessage: str | None = None
    queuedAt: datetime
    pickedUpAt: datetime | None = None
    completedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime

    @field_validator("config", mode="before")
    @classmethod
    def _validate_config(cls, v: object) -> object:
        return _coerce_dict(v)


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