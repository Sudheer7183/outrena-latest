# # """sequences.py — Sequence + SubjectLine request/response contracts."""
# # from __future__ import annotations

# # from datetime import datetime

# # import json

# # from pydantic import BaseModel, Field, field_validator

# # from app.models.enums import EmailStatus, TouchAngle


# # class SubjectLineCreate(BaseModel):
# #     variant: str
# #     isSelected: bool = False


# # class SubjectLineResponse(BaseModel):
# #     id: str
# #     sequenceId: str
# #     variant: str
# #     isSelected: bool
# #     createdAt: datetime

# #     model_config = {"from_attributes": True}


# # class SequenceCreate(BaseModel):
# #     campaignId: str
# #     prospectId: str
# #     touchNumber: int = Field(ge=1, le=10)
# #     sendDay: int = Field(ge=0, le=365)
# #     channel: str = "email"
# #     angle: TouchAngle = TouchAngle.FirstTouch
# #     framework: str | None = None
# #     subjectLine: str | None = None
# #     bodyCopy: str | None = None


# # class SequenceUpdate(BaseModel):
# #     subjectLine: str | None = None
# #     bodyCopy: str | None = None
# #     qaScore: int | None = None
# #     qaDetails: str | None = None
# #     personalisationConfidence: float | None = None
# #     flagForManualReview: bool | None = None
# #     status: EmailStatus | None = None


# # class SequenceResponse(BaseModel):
# #     id: str
# #     campaignId: str
# #     prospectId: str
# #     touchNumber: int
# #     sendDay: int
# #     channel: str
# #     angle: TouchAngle
# #     framework: str | None
# #     subjectLine: str | None
# #     bodyCopy: str | None
# #     qaScore: int | None
# #     qaDetails: dict = {}
# #     personalisationConfidence: float | None
# #     flagForManualReview: bool
# #     status: EmailStatus
# #     sentAt: datetime | None
# #     openedAt: datetime | None
# #     repliedAt: datetime | None
# #     bouncedAt: datetime | None
# #     mailBridgeMessageId: str | None
# #     bounceReason: str | None
# #     createdAt: datetime
# #     updatedAt: datetime
# #     subjectLines: list[SubjectLineResponse] = []

# #     model_config = {"from_attributes": True}

# #     @field_validator("qaDetails", mode="before")
# #     @classmethod
# #     def _parse_qa_details(cls, v: object) -> dict:
# #         """Parse JSON string or dict for qaDetails."""
# #         if isinstance(v, str):
# #             try:
# #                 parsed = json.loads(v)
# #                 if isinstance(parsed, dict):
# #                     return parsed
# #                 return {}
# #             except (json.JSONDecodeError, TypeError, ValueError):
# #                 return {}
# #         if isinstance(v, dict):
# #             return v
# #         return {}


# # class ScheduledSendRequest(BaseModel):
# #     """Body for POST /sequences/{id}/scheduled-send — set status=Scheduled."""
# #     sendAt: datetime | None = None


# # class SendEmailRequest(BaseModel):
# #     """Body for POST /sequences/{id}/send-email — fire immediately via MailBridge."""
# #     force: bool = False  # bypass QA gate when true (REP cannot)


# # class SendEmailResponse(BaseModel):
# #     id: str
# #     status: EmailStatus
# #     mailBridgeMessageId: str | None
# #     sentAt: datetime | None
# #     message: str


# # class CadenceResponse(BaseModel):
# #     """The 7-touch cadence (days 1/4/9/16/25/35) — exposed to the UI."""
# #     touchNumber: int
# #     sendDay: int
# #     angle: TouchAngle
# #     defaultFramework: str


# # class SequenceListResponse(BaseModel):
# #     """Page envelope for sequence list endpoints (parity with Prisma/Next.js)."""
# #     items: list["SequenceResponse"]
# #     total: int = 0
# #     limit: int = 50
# #     offset: int = 0


# # class SubjectLineSelectRequest(BaseModel):
# #     """Body for POST /sequences/{id}/subject-lines/{sl_id}/select."""
# #     isSelected: bool = True


# # class SequenceQaRequest(BaseModel):
# #     """Body for POST /sequences/{id}/qa — re-run QA on a sequence."""
# #     framework: str | None = None


# # class SequenceQaResponse(BaseModel):
# #     """QA result for a sequence."""
# #     sequenceId: str
# #     qaScore: int
# #     qaDetails: dict
# #     flagForManualReview: bool


# # SEVEN_TOUCH_CADENCE: list[CadenceResponse] = [
# #     CadenceResponse(touchNumber=1, sendDay=1, angle=TouchAngle.FirstTouch, defaultFramework="AIDA"),
# #     CadenceResponse(touchNumber=2, sendDay=4, angle=TouchAngle.NewEvidence, defaultFramework="PAS"),
# #     CadenceResponse(touchNumber=3, sendDay=9, angle=TouchAngle.DifferentPain, defaultFramework="BAB"),
# #     CadenceResponse(touchNumber=4, sendDay=16, angle=TouchAngle.IndustryInsight, defaultFramework="Value"),
# #     CadenceResponse(touchNumber=5, sendDay=25, angle=TouchAngle.DirectQuestion, defaultFramework="Question"),
# #     CadenceResponse(touchNumber=6, sendDay=35, angle=TouchAngle.Breakup, defaultFramework="Breakup"),
# #     CadenceResponse(touchNumber=7, sendDay=35, angle=TouchAngle.Breakup, defaultFramework="Breakup-Final"),
# # ]


# # __all__ = [
# #     "SubjectLineCreate",
# #     "SubjectLineResponse",
# #     "SequenceCreate",
# #     "SequenceUpdate",
# #     "SequenceResponse",
# #     "SequenceListResponse",
# #     "ScheduledSendRequest",
# #     "SendEmailRequest",
# #     "SendEmailResponse",
# #     "CadenceResponse",
# #     "SEVEN_TOUCH_CADENCE",
# #     "SubjectLineSelectRequest",
# #     "SequenceQaRequest",
# #     "SequenceQaResponse",
# # ]

# """sequences.py — Sequence + SubjectLine request/response contracts."""
# from __future__ import annotations

# from datetime import datetime

# import json

# from pydantic import BaseModel, Field, field_validator

# from app.models.enums import EmailStatus, TouchAngle


# class SubjectLineCreate(BaseModel):
#     variant: str
#     isSelected: bool = False


# class SubjectLineResponse(BaseModel):
#     id: str
#     sequenceId: str
#     variant: str
#     isSelected: bool
#     createdAt: datetime

#     model_config = {"from_attributes": True}


# class SequenceCreate(BaseModel):
#     campaignId: str
#     prospectId: str
#     touchNumber: int = Field(ge=1, le=10)
#     sendDay: int = Field(ge=0, le=365)
#     channel: str = "email"
#     angle: TouchAngle = TouchAngle.FirstTouch
#     framework: str | None = None
#     subjectLine: str | None = None
#     bodyCopy: str | None = None


# class SequenceUpdate(BaseModel):
#     subjectLine: str | None = None
#     bodyCopy: str | None = None
#     qaScore: int | None = None
#     qaDetails: str | None = None
#     personalisationConfidence: float | None = None
#     flagForManualReview: bool | None = None
#     status: EmailStatus | None = None


# class SequenceResponse(BaseModel):
#     id: str
#     campaignId: str
#     prospectId: str
#     touchNumber: int
#     sendDay: int
#     channel: str
#     angle: TouchAngle
#     framework: str | None
#     subjectLine: str | None
#     bodyCopy: str | None
#     qaScore: int | None
#     qaDetails: dict = {}
#     personalisationConfidence: float | None
#     flagForManualReview: bool
#     status: EmailStatus
#     sentAt: datetime | None
#     openedAt: datetime | None
#     repliedAt: datetime | None
#     bouncedAt: datetime | None
#     mailBridgeMessageId: str | None
#     bounceReason: str | None
#     createdAt: datetime
#     updatedAt: datetime
#     subjectLines: list[SubjectLineResponse] = []

#     model_config = {"from_attributes": True}

#     @field_validator("qaDetails", mode="before")
#     @classmethod
#     def _parse_qa_details(cls, v: object) -> dict:
#         """Parse JSON string or dict for qaDetails."""
#         if isinstance(v, str):
#             try:
#                 parsed = json.loads(v)
#                 if isinstance(parsed, dict):
#                     return parsed
#                 return {}
#             except (json.JSONDecodeError, TypeError, ValueError):
#                 return {}
#         if isinstance(v, dict):
#             return v
#         return {}


# class ScheduledSendRequest(BaseModel):
#     """Body for POST /sequences/{id}/scheduled-send — set status=Scheduled."""
#     sendAt: datetime | None = None


# class SendEmailRequest(BaseModel):
#     """Body for POST /sequences/{id}/send-email — fire immediately via MailBridge."""
#     force: bool = False  # bypass QA gate when true (REP cannot)


# class SendEmailResponse(BaseModel):
#     id: str
#     status: EmailStatus
#     mailBridgeMessageId: str | None
#     sentAt: datetime | None
#     message: str


# class CadenceResponse(BaseModel):
#     """The 7-touch cadence (days 1/4/9/16/25/35) — exposed to the UI."""
#     touchNumber: int
#     sendDay: int
#     angle: TouchAngle
#     defaultFramework: str


# class SequenceListResponse(BaseModel):
#     """Page envelope for sequence list endpoints (parity with Prisma/Next.js)."""
#     items: list["SequenceResponse"]
#     total: int = 0
#     limit: int = 50
#     offset: int = 0


# class SubjectLineSelectRequest(BaseModel):
#     """Body for POST /sequences/{id}/subject-lines/{sl_id}/select."""
#     isSelected: bool = True


# class SequenceQaRequest(BaseModel):
#     """Body for POST /sequences/{id}/qa — re-run QA on a sequence."""
#     framework: str | None = None


# class SequenceQaResponse(BaseModel):
#     """QA result for a sequence."""
#     sequenceId: str
#     qaScore: int
#     qaDetails: dict
#     flagForManualReview: bool


# SEVEN_TOUCH_CADENCE: list[CadenceResponse] = [
#     CadenceResponse(touchNumber=1, sendDay=1, angle=TouchAngle.FirstTouch, defaultFramework="AIDA"),
#     CadenceResponse(touchNumber=2, sendDay=4, angle=TouchAngle.NewEvidence, defaultFramework="PAS"),
#     CadenceResponse(touchNumber=3, sendDay=9, angle=TouchAngle.DifferentPain, defaultFramework="BAB"),
#     CadenceResponse(touchNumber=4, sendDay=16, angle=TouchAngle.IndustryInsight, defaultFramework="Value"),
#     CadenceResponse(touchNumber=5, sendDay=25, angle=TouchAngle.DirectQuestion, defaultFramework="Question"),
#     CadenceResponse(touchNumber=6, sendDay=35, angle=TouchAngle.Breakup, defaultFramework="Breakup"),
#     CadenceResponse(touchNumber=7, sendDay=35, angle=TouchAngle.Breakup, defaultFramework="Breakup-Final"),
# ]


# class TemplateSendRequest(BaseModel):
#     """Body for POST /sequences/template-send.

#     mode=manual  — renders the template body/subject with prospect data
#                    ({{ first_name }}, {{ company }}, etc.) and creates one
#                    Draft Sequence row ready for review and send.

#     mode=llm     — passes the template body as a seed_body hint to the LLM
#                    generate-sequences flow so the LLM uses it as structural
#                    guidance while writing all 7 personalised touches.
#     """
#     campaignId: str
#     prospectId: str
#     templateId: str
#     mode: str = Field(default="manual", pattern="^(manual|llm)$")


# class TemplateSendResponse(BaseModel):
#     """Response from POST /sequences/template-send."""
#     mode: str
#     templateName: str
#     sequences: list[SequenceResponse]
#     message: str


# __all__ = [
#     "SubjectLineCreate",
#     "SubjectLineResponse",
#     "SequenceCreate",
#     "SequenceUpdate",
#     "SequenceResponse",
#     "SequenceListResponse",
#     "ScheduledSendRequest",
#     "SendEmailRequest",
#     "SendEmailResponse",
#     "CadenceResponse",
#     "SEVEN_TOUCH_CADENCE",
#     "SubjectLineSelectRequest",
#     "SequenceQaRequest",
#     "SequenceQaResponse",
#     "TemplateSendRequest",
#     "TemplateSendResponse",
# ]


"""sequences.py — Sequence + SubjectLine request/response contracts."""
from __future__ import annotations

from datetime import datetime

import json

from pydantic import BaseModel, Field, field_validator

from app.models.enums import EmailStatus, TouchAngle


class SubjectLineCreate(BaseModel):
    variant: str
    isSelected: bool = False


class SubjectLineResponse(BaseModel):
    id: str
    sequenceId: str
    variant: str
    isSelected: bool
    createdAt: datetime

    model_config = {"from_attributes": True}


class SequenceCreate(BaseModel):
    campaignId: str
    prospectId: str
    touchNumber: int = Field(ge=1, le=10)
    sendDay: int = Field(ge=0, le=365)
    channel: str = "email"
    angle: TouchAngle = TouchAngle.FirstTouch
    framework: str | None = None
    subjectLine: str | None = None
    bodyCopy: str | None = None


class SequenceUpdate(BaseModel):
    subjectLine: str | None = None
    bodyCopy: str | None = None
    qaScore: int | None = None
    qaDetails: str | None = None
    personalisationConfidence: float | None = None
    flagForManualReview: bool | None = None
    status: EmailStatus | None = None


class SequenceResponse(BaseModel):
    id: str
    campaignId: str
    prospectId: str
    touchNumber: int
    sendDay: int
    channel: str
    angle: TouchAngle
    framework: str | None
    subjectLine: str | None
    bodyCopy: str | None
    qaScore: int | None
    qaDetails: dict = {}
    personalisationConfidence: float | None
    flagForManualReview: bool
    status: EmailStatus
    sentAt: datetime | None
    openedAt: datetime | None
    repliedAt: datetime | None
    bouncedAt: datetime | None
    mailBridgeMessageId: str | None
    bounceReason: str | None
    createdAt: datetime
    updatedAt: datetime
    subjectLines: list[SubjectLineResponse] = []

    model_config = {"from_attributes": True}

    @field_validator("qaDetails", mode="before")
    @classmethod
    def _parse_qa_details(cls, v: object) -> dict:
        """Parse JSON string or dict for qaDetails."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return parsed
                return {}
            except (json.JSONDecodeError, TypeError, ValueError):
                return {}
        if isinstance(v, dict):
            return v
        return {}


class ScheduledSendRequest(BaseModel):
    """Body for POST /sequences/{id}/scheduled-send — set status=Scheduled."""
    sendAt: datetime | None = None


class SendEmailRequest(BaseModel):
    """Body for POST /sequences/{id}/send-email — fire immediately via MailBridge."""
    force: bool = False  # bypass QA gate when true (REP cannot)


class SendEmailResponse(BaseModel):
    id: str
    status: EmailStatus
    mailBridgeMessageId: str | None
    sentAt: datetime | None
    message: str


class CadenceResponse(BaseModel):
    """The 7-touch cadence (days 1/4/9/16/25/35) — exposed to the UI."""
    touchNumber: int
    sendDay: int
    angle: TouchAngle
    defaultFramework: str


class SequenceListResponse(BaseModel):
    """Page envelope for sequence list endpoints (parity with Prisma/Next.js)."""
    items: list["SequenceResponse"]
    total: int = 0
    limit: int = 50
    offset: int = 0


class SubjectLineSelectRequest(BaseModel):
    """Body for POST /sequences/{id}/subject-lines/{sl_id}/select."""
    isSelected: bool = True


class SequenceQaRequest(BaseModel):
    """Body for POST /sequences/{id}/qa — re-run QA on a sequence."""
    framework: str | None = None


class SequenceQaResponse(BaseModel):
    """QA result for a sequence."""
    sequenceId: str
    qaScore: int
    qaDetails: dict
    flagForManualReview: bool


SEVEN_TOUCH_CADENCE: list[CadenceResponse] = [
    CadenceResponse(touchNumber=1, sendDay=1, angle=TouchAngle.FirstTouch, defaultFramework="AIDA"),
    CadenceResponse(touchNumber=2, sendDay=4, angle=TouchAngle.NewEvidence, defaultFramework="PAS"),
    CadenceResponse(touchNumber=3, sendDay=9, angle=TouchAngle.DifferentPain, defaultFramework="BAB"),
    CadenceResponse(touchNumber=4, sendDay=16, angle=TouchAngle.IndustryInsight, defaultFramework="Value"),
    CadenceResponse(touchNumber=5, sendDay=25, angle=TouchAngle.DirectQuestion, defaultFramework="Question"),
    CadenceResponse(touchNumber=6, sendDay=35, angle=TouchAngle.Breakup, defaultFramework="Breakup"),
    CadenceResponse(touchNumber=7, sendDay=35, angle=TouchAngle.Breakup, defaultFramework="Breakup-Final"),
]


class TemplateSendRequest(BaseModel):
    """Body for POST /sequences/template-send.

    mode=manual  — renders the template body/subject with prospect data
                   ({{ first_name }}, {{ company }}, etc.) and creates one
                   Draft Sequence row ready for review and send.

    mode=llm     — passes the template body as a seed_body hint to the LLM
                   generate-sequences flow so the LLM uses it as structural
                   guidance while writing all 7 personalised touches.
    """
    campaignId: str
    prospectId: str
    templateId: str
    mode: str = Field(default="manual", pattern="^(manual|llm)$")
    senderName: str | None = None      # logged-in user's full name (first + last)
    senderCompany: str | None = None   # from profile.senderCompany


class TemplateSendResponse(BaseModel):
    """Response from POST /sequences/template-send."""
    mode: str
    templateName: str
    sequences: list[SequenceResponse]
    message: str


__all__ = [
    "SubjectLineCreate",
    "SubjectLineResponse",
    "SequenceCreate",
    "SequenceUpdate",
    "SequenceResponse",
    "SequenceListResponse",
    "ScheduledSendRequest",
    "SendEmailRequest",
    "SendEmailResponse",
    "CadenceResponse",
    "SEVEN_TOUCH_CADENCE",
    "SubjectLineSelectRequest",
    "SequenceQaRequest",
    "SequenceQaResponse",
    "TemplateSendRequest",
    "TemplateSendResponse",
]
