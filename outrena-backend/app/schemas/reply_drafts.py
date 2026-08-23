# """reply_drafts.py — Reply-draft triage + auto-pilot contracts."""
# from __future__ import annotations

# from datetime import datetime

# from pydantic import BaseModel, Field


# class ReplyDraftCreate(BaseModel):
#     sequenceId: str
#     prospectId: str
#     originalReply: str
#     category: str = "other"


# class ReplyDraftUpdate(BaseModel):
#     draftBody: str | None = None
#     status: str | None = None
#     autoPilotEligible: bool | None = None
#     confidence: float | None = None


# class ReplyDraftResponse(BaseModel):
#     id: str
#     sequenceId: str
#     prospectId: str
#     originalReply: str
#     category: str
#     summary: str | None
#     suggestedAction: str | None
#     draftBody: str | None
#     status: str
#     sentAt: datetime | None
#     autoPilotEligible: bool
#     confidence: float | None
#     autoSentAt: datetime | None
#     meetingProposedTime: datetime | None
#     meetingBookedAt: datetime | None
#     meetingCalendarLink: str | None
#     createdAt: datetime
#     updatedAt: datetime

#     model_config = {"from_attributes": True}


# class ReplyCategorizeRequest(BaseModel):
#     """Body for POST /reply-drafts/{id}/reply-categorize."""
#     originalReply: str


# class ReplyCategorizeResponse(BaseModel):
#     category: str
#     summary: str
#     suggestedAction: str
#     confidence: float


# class AutoReplyRequest(BaseModel):
#     """Body for POST /reply-drafts/{id}/auto-reply — fire the draft via MailBridge."""
#     dryRun: bool = False


# class AutoPilotEligibleResponse(BaseModel):
#     """Body for GET /reply-drafts/auto-pilot — list of eligible drafts.

#     Eligibility rule (Phase 3 deliverable):
#         positive category + confidence >= 0.8 + status == 'approved'
#     """
#     eligible: list[ReplyDraftResponse]
#     count: int


# class AutoReplyResponse(BaseModel):
#     """Body for POST /reply-drafts/{id}/auto-reply."""
#     ok: bool
#     message: str
#     draftId: str | None = None
#     messageId: str | None = None


# __all__ = [
#     "ReplyDraftCreate",
#     "ReplyDraftUpdate",
#     "ReplyDraftResponse",
#     "ReplyCategorizeRequest",
#     "ReplyCategorizeResponse",
#     "AutoReplyRequest",
#     "AutoReplyResponse",
#     "AutoPilotEligibleResponse",
# ]

"""reply_drafts.py — Reply-draft triage + auto-pilot contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReplyDraftCreate(BaseModel):
    sequenceId: str
    prospectId: str
    originalReply: str
    category: str = "other"


class ReplyDraftUpdate(BaseModel):
    draftBody: str | None = None
    status: str | None = None
    autoPilotEligible: bool | None = None
    confidence: float | None = None


class ReplyDraftResponse(BaseModel):
    id: str
    sequenceId: str
    prospectId: str
    originalReply: str
    category: str
    summary: str | None
    suggestedAction: str | None
    draftBody: str | None
    status: str
    sentAt: datetime | None
    autoPilotEligible: bool
    confidence: float | None
    autoSentAt: datetime | None
    meetingProposedTime: datetime | None
    meetingBookedAt: datetime | None
    meetingCalendarLink: str | None
    createdAt: datetime
    updatedAt: datetime

    # Enriched display fields — populated by the router from joined Sequence/Prospect rows.
    # None when the linked sequence or prospect cannot be resolved.
    prospectName: str | None = None       # "<firstName> <lastName>"
    prospectEmail: str | None = None      # prospect's email address (decrypted)
    sentEmailSubject: str | None = None   # Sequence.subjectLine (what Outrena sent)
    sentEmailBody: str | None = None      # Sequence.bodyCopy (what Outrena sent)

    model_config = {"from_attributes": True}


class ReplyCategorizeRequest(BaseModel):
    """Body for POST /reply-drafts/{id}/reply-categorize."""
    originalReply: str


class ReplyCategorizeResponse(BaseModel):
    category: str
    summary: str
    suggestedAction: str
    confidence: float


class AutoReplyRequest(BaseModel):
    """Body for POST /reply-drafts/{id}/auto-reply — fire the draft via MailBridge."""
    dryRun: bool = False


class AutoPilotEligibleResponse(BaseModel):
    """Body for GET /reply-drafts/auto-pilot — list of eligible drafts.

    Eligibility rule (Phase 3 deliverable):
        positive category + confidence >= 0.8 + status == 'approved'
    """
    eligible: list[ReplyDraftResponse]
    count: int


class AutoReplyResponse(BaseModel):
    """Body for POST /reply-drafts/{id}/auto-reply."""
    ok: bool
    message: str
    draftId: str | None = None
    messageId: str | None = None


__all__ = [
    "ReplyDraftCreate",
    "ReplyDraftUpdate",
    "ReplyDraftResponse",
    "ReplyCategorizeRequest",
    "ReplyCategorizeResponse",
    "AutoReplyRequest",
    "AutoReplyResponse",
    "AutoPilotEligibleResponse",
]
