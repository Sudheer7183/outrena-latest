"""mailbridge.py — SMTP relay config + tracking + webhook contracts."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MailBridgeConfigCreate(BaseModel):
    name: str
    baseUrl: str
    provider: str = "gmail"
    fromEmail: str
    fromName: str | None = None
    isActive: bool = True
    webhookSecret: str | None = None
    domainId: str | None = None


class MailBridgeConfigUpdate(BaseModel):
    name: str | None = None
    baseUrl: str | None = None
    fromEmail: str | None = None
    fromName: str | None = None
    isActive: bool | None = None
    webhookSecret: str | None = None
    domainId: str | None = None


class MailBridgeConfigResponse(BaseModel):
    id: str
    name: str
    baseUrl: str
    provider: str
    fromEmail: str
    fromName: str | None
    isActive: bool
    webhookSecret: str | None
    domainId: str | None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class MailBridgeTrackingEvent(BaseModel):
    """Inbound webhook event from MailBridge (send/open/reply/bounce).

    Task 3-a / FIX 3: the ``payload`` field captures the raw webhook body
    (structured JSON) so downstream consumers can extract the reply body /
    headers / message metadata that MailBridge includes alongside the event
    envelope. Previously the reply body was lost because ``payload`` wasn't
    on the schema — ``_auto_create_reply_draft`` fell back to ``reason``
    (which is the bounce/error reason, not the reply text).
    MailBridge should include the reply body at ``payload.body`` or
    ``payload.text`` (and optionally ``payload.replyBody`` as an alias).
    """
    event: str  # sent | opened | replied | bounced | failed
    messageId: str
    sequenceId: str | None = None
    timestamp: datetime
    recipient: str | None = None
    reason: str | None = None
    # Raw webhook body (reply text, headers, etc.). None when MailBridge
    # doesn't include a payload (e.g. for simple open/click events).
    payload: dict[str, Any] | None = None


class MailBridgeWebhookPayload(BaseModel):
    """Body for POST /mailbridge/webhook — signed by MailBridge."""
    events: list[MailBridgeTrackingEvent]
    signature: str | None = None


class MailBridgeWebhookResponse(BaseModel):
    accepted: int
    rejected: int


class MailBridgeSendRequest(BaseModel):
    """Outbound send request to MailBridge."""
    to: str
    subject: str
    body: str
    sequenceId: str | None = None
    configId: str | None = None


class MailBridgeSendResponse(BaseModel):
    messageId: str
    status: str  # queued | sent | failed
    accepted: bool


__all__ = [
    "MailBridgeConfigCreate",
    "MailBridgeConfigUpdate",
    "MailBridgeConfigResponse",
    "MailBridgeTrackingEvent",
    "MailBridgeWebhookPayload",
    "MailBridgeWebhookResponse",
    "MailBridgeSendRequest",
    "MailBridgeSendResponse",
]
