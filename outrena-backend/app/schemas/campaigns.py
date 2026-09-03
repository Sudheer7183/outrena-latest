# """campaigns.py — Campaign CRUD + campaign-prospects + clone + preflight + LLM."""
# from __future__ import annotations

# from datetime import datetime

# import json

# from pydantic import BaseModel, ConfigDict, Field, field_validator


# class CampaignCreate(BaseModel):
#     """Body for POST /campaigns."""

#     name: str = Field(..., min_length=1)
#     description: str | None = None
#     framework: str | None = None
#     senderRole: str | None = None
#     senderCompany: str | None = None
#     senderOffer: str | None = None
#     proofMetric: str | None = None
#     senderProduct: str | None = None
#     targetAudience: str | None = None
#     complianceFooter: bool = False
#     unsubscribeUrl: str | None = None
#     physicalAddress: str | None = None
#     webhookUrl: str | None = None
#     brandVoiceProfile: dict | None = None
#     icpProfileId: str | None = None
#     llmConfigId: str | None = None
#     domainId: str | None = None


# class CampaignUpdate(BaseModel):
#     """Body for PUT /campaigns/{campaign_id}."""

#     name: str | None = None
#     description: str | None = None
#     status: str | None = None
#     framework: str | None = None
#     senderRole: str | None = None
#     senderCompany: str | None = None
#     senderOffer: str | None = None
#     proofMetric: str | None = None
#     senderProduct: str | None = None
#     targetAudience: str | None = None
#     complianceFooter: bool | None = None
#     unsubscribeUrl: str | None = None
#     physicalAddress: str | None = None
#     webhookUrl: str | None = None
#     brandVoiceProfile: dict | None = None
#     icpProfileId: str | None = None
#     llmConfigId: str | None = None
#     domainId: str | None = None


# class CampaignResponse(BaseModel):
#     """Public shape of a Campaign row."""

#     model_config = ConfigDict(from_attributes=True)

#     id: str
#     name: str
#     description: str | None = None
#     status: str
#     framework: str | None = None
#     senderRole: str | None = None
#     senderCompany: str | None = None
#     senderOffer: str | None = None
#     proofMetric: str | None = None
#     senderProduct: str | None = None
#     targetAudience: str | None = None
#     complianceFooter: bool
#     unsubscribeUrl: str | None = None
#     physicalAddress: str | None = None
#     webhookUrl: str | None = None
#     brandVoiceProfile: dict | None = None
#     icpProfileId: str | None = None
#     llmConfigId: str | None = None
#     domainId: str | None = None
#     createdAt: datetime
#     updatedAt: datetime

#     @field_validator("brandVoiceProfile", mode="before")
#     @classmethod
#     def _parse_json_dict(cls, v: object) -> dict | None:
#         """Parse JSON string or dict for brandVoiceProfile."""
#         if v is None:
#             return None
#         if isinstance(v, str):
#             try:
#                 parsed = json.loads(v)
#                 if isinstance(parsed, dict):
#                     return parsed
#                 return None
#             except (json.JSONDecodeError, TypeError, ValueError):
#                 return None
#         if isinstance(v, dict):
#             return v
#         return None


# class CampaignProspectLinkRequest(BaseModel):
#     """Body for POST/DELETE /campaigns/campaign-prospects — link/unlink prospect."""

#     campaignId: str
#     prospectId: str


# class CloneCampaignRequest(BaseModel):
#     """Body for POST /campaigns/clone — deep-copy a campaign."""

#     sourceCampaignId: str
#     newName: str = Field(..., min_length=1)


# class PreflightRequest(BaseModel):
#     """Body for POST /campaigns/preflight — 6-check activation gate."""

#     campaignId: str


# class PreflightCheck(BaseModel):
#     """One of the 6 preflight checks."""

#     key: str
#     label: str
#     passed: bool
#     detail: str | None = None


# class PreflightResult(BaseModel):
#     """Result of the 6-check preflight gate."""

#     campaignId: str
#     allPassed: bool
#     checks: list[PreflightCheck]


# class FrameworkRecommendRequest(BaseModel):
#     """Body for POST /campaigns/framework-recommend — LLM picks a framework."""

#     campaignId: str
#     context: str | None = None


# class FrameworkRecommendResponse(BaseModel):
#     """LLM-recommended framework + rationale."""

#     campaignId: str
#     framework: str
#     rationale: str | None = None
#     raw: str | None = None


# class GtmThesisRequest(BaseModel):
#     """Body for POST /campaigns/gtm-thesis — LLM generates a GTM thesis."""

#     campaignId: str
#     additionalContext: str | None = None


# class GtmThesisResponse(BaseModel):
#     """LLM-generated GTM thesis for a campaign."""

#     campaignId: str
#     thesis: str
#     raw: str | None = None


# class CampaignListResponse(BaseModel):
#     """Page envelope for campaign list endpoints."""

#     items: list[CampaignResponse]
#     total: int = 0
#     limit: int = 50
#     offset: int = 0


# __all__ = [
#     "CampaignCreate",
#     "CampaignUpdate",
#     "CampaignResponse",
#     "CampaignListResponse",
#     "CampaignProspectLinkRequest",
#     "CloneCampaignRequest",
#     "PreflightRequest",
#     "PreflightCheck",
#     "PreflightResult",
#     "FrameworkRecommendRequest",
#     "FrameworkRecommendResponse",
#     "GtmThesisRequest",
#     "GtmThesisResponse",
# ]

"""campaigns.py — Campaign CRUD + campaign-prospects + clone + preflight + LLM."""
from __future__ import annotations

from datetime import datetime

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CampaignCreate(BaseModel):
    """Body for POST /campaigns."""

    name: str = Field(..., min_length=1)
    description: str | None = None
    framework: str | None = None
    senderRole: str | None = None
    senderCompany: str | None = None
    senderOffer: str | None = None
    proofMetric: str | None = None
    senderProduct: str | None = None
    targetAudience: str | None = None
    complianceFooter: bool = False
    unsubscribeUrl: str | None = None
    physicalAddress: str | None = None
    webhookUrl: str | None = None
    brandVoiceProfile: dict | None = None
    icpProfileId: str | None = None
    llmConfigId: str | None = None
    domainId: str | None = None


class CampaignUpdate(BaseModel):
    """Body for PUT /campaigns/{campaign_id}."""

    name: str | None = None
    description: str | None = None
    status: str | None = None
    framework: str | None = None
    senderRole: str | None = None
    senderCompany: str | None = None
    senderOffer: str | None = None
    proofMetric: str | None = None
    senderProduct: str | None = None
    targetAudience: str | None = None
    complianceFooter: bool | None = None
    unsubscribeUrl: str | None = None
    physicalAddress: str | None = None
    webhookUrl: str | None = None
    brandVoiceProfile: dict | None = None
    icpProfileId: str | None = None
    llmConfigId: str | None = None
    domainId: str | None = None


class CampaignCountSummary(BaseModel):
    """Embedded counts for prospects, sequences, and collaterals on a campaign."""
    prospects: int = 0
    sequences: int = 0
    collaterals: int = 0


class CampaignResponse(BaseModel):
    """Public shape of a Campaign row."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    name: str
    description: str | None = None
    status: str
    framework: str | None = None
    senderRole: str | None = None
    senderCompany: str | None = None
    senderOffer: str | None = None
    proofMetric: str | None = None
    senderProduct: str | None = None
    targetAudience: str | None = None
    complianceFooter: bool
    unsubscribeUrl: str | None = None
    physicalAddress: str | None = None
    webhookUrl: str | None = None
    brandVoiceProfile: dict | None = None
    icpProfileId: str | None = None
    llmConfigId: str | None = None
    domainId: str | None = None
    createdAt: datetime
    updatedAt: datetime
    # Populated by list_campaigns via COUNT subqueries.
    # Serializes as "_count" in JSON (matching the Prisma/frontend convention).
    # Not an ORM column — always set explicitly by the router after the ORM fetch.
    count: CampaignCountSummary = Field(
        default_factory=CampaignCountSummary, alias="_count", serialization_alias="_count"
    )

    @field_validator("brandVoiceProfile", mode="before")
    @classmethod
    def _parse_json_dict(cls, v: object) -> dict | None:
        """Parse JSON string or dict for brandVoiceProfile."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return parsed
                return None
            except (json.JSONDecodeError, TypeError, ValueError):
                return None
        if isinstance(v, dict):
            return v
        return None


class CampaignProspectLinkRequest(BaseModel):
    """Body for POST/DELETE /campaigns/campaign-prospects — link/unlink prospect."""

    campaignId: str
    prospectId: str


class CloneCampaignRequest(BaseModel):
    """Body for POST /campaigns/clone — deep-copy a campaign."""

    sourceCampaignId: str
    newName: str = Field(..., min_length=1)


class PreflightRequest(BaseModel):
    """Body for POST /campaigns/preflight — 6-check activation gate."""

    campaignId: str


class PreflightCheck(BaseModel):
    """One of the 6 preflight checks."""

    key: str
    label: str
    passed: bool
    detail: str | None = None


class PreflightResult(BaseModel):
    """Result of the 6-check preflight gate."""

    campaignId: str
    allPassed: bool
    checks: list[PreflightCheck]


class FrameworkRecommendRequest(BaseModel):
    """Body for POST /campaigns/framework-recommend — LLM picks a framework."""

    campaignId: str
    context: str | None = None


class FrameworkRecommendResponse(BaseModel):
    """LLM-recommended framework + rationale."""

    campaignId: str
    framework: str
    rationale: str | None = None
    raw: str | None = None


class GtmThesisRequest(BaseModel):
    """Body for POST /campaigns/gtm-thesis — LLM generates a GTM thesis."""

    campaignId: str
    additionalContext: str | None = None


class GtmThesisResponse(BaseModel):
    """LLM-generated GTM thesis for a campaign."""

    campaignId: str
    thesis: str
    raw: str | None = None


class CampaignListResponse(BaseModel):
    """Page envelope for campaign list endpoints."""

    items: list[CampaignResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


__all__ = [
    "CampaignCreate",
    "CampaignUpdate",
    "CampaignCountSummary",
    "CampaignResponse",
    "CampaignListResponse",
    "CampaignProspectLinkRequest",
    "CloneCampaignRequest",
    "PreflightRequest",
    "PreflightCheck",
    "PreflightResult",
    "FrameworkRecommendRequest",
    "FrameworkRecommendResponse",
    "GtmThesisRequest",
    "GtmThesisResponse",
]