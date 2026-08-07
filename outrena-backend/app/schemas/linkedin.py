"""linkedin.py — LinkedIn config + engagement + inbox contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LinkedInConfigCreate(BaseModel):
    accountName: str
    accountHandle: str | None = None
    isActive: bool = False
    cookieJar: str | None = None


class LinkedInConfigUpdate(BaseModel):
    accountName: str | None = None
    accountHandle: str | None = None
    isActive: bool | None = None
    cookieJar: str | None = None
    syncStatus: str | None = None


class LinkedInConfigResponse(BaseModel):
    id: str
    accountName: str
    accountHandle: str | None
    isActive: bool
    syncStatus: str
    lastSyncedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class LinkedInEngagementCreate(BaseModel):
    prospectId: str | None = None
    icpProfileId: str | None = None
    action: str  # connect | message | view | endorse
    note: str | None = None
    scheduledAt: datetime | None = None
    # Task 3-a / FIX 2: optional owner override. Normally the service
    # derives owner_user_id from the request's TokenPayload; this field
    # lets internal jobs (no token context) supply the owner explicitly.
    owner_user_id: str | None = None


class LinkedInEngagementUpdate(BaseModel):
    status: str | None = None
    note: str | None = None
    executedAt: datetime | None = None


class LinkedInEngagementResponse(BaseModel):
    id: str
    prospectId: str | None
    icpProfileId: str | None
    action: str
    note: str | None
    status: str
    scheduledAt: datetime | None
    executedAt: datetime | None
    # Task 3-a / FIX 2: owner_user_id (Keycloak sub of the rep who owns
    # this engagement). NULL on legacy rows created before migration 0011.
    owner_user_id: str | None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class LinkedInInboxMessageResponse(BaseModel):
    id: str
    prospectId: str | None
    senderName: str
    senderHandle: str | None
    body: str
    status: str
    receivedAt: datetime
    triagedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class LinkedInInboxTriageRequest(BaseModel):
    messageIds: list[str]
    status: str  # read | archived | converted_to_reply_draft


# ── ICP Match ─────────────────────────────────────────────────────────────────

class IcpMatchRequest(BaseModel):
    """Body for POST /linkedin/engagements/check-icp — batch ICP matching."""
    llm_config_id: str | None = None


class IcpMatchResult(BaseModel):
    engagement_id: str
    is_icp_match: bool
    icp_profile_id: str | None = None
    icp_profile_name: str | None = None
    match_reason: str | None = None
    suggested_note: str | None = None


class IcpMatchResponse(BaseModel):
    success: bool
    checked: int = 0
    matches: list[IcpMatchResult] = []
    error: str | None = None


__all__ = [
    "LinkedInConfigCreate",
    "LinkedInConfigUpdate",
    "LinkedInConfigResponse",
    "LinkedInEngagementCreate",
    "LinkedInEngagementUpdate",
    "LinkedInEngagementResponse",
    "LinkedInInboxMessageResponse",
    "LinkedInInboxTriageRequest",
    "IcpMatchRequest",
    "IcpMatchResult",
    "IcpMatchResponse",
]
