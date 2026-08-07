"""collaterals.py — Collateral library request/response contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CollateralCreate(BaseModel):
    name: str
    type: str
    url: str | None = None
    content: str | None = None
    description: str | None = None
    fileName: str | None = None
    fileSize: int | None = None
    mimeType: str | None = None


class CollateralUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    content: str | None = None


class CollateralResponse(BaseModel):
    id: str
    name: str
    type: str
    url: str | None
    content: str | None
    description: str | None
    fileName: str | None
    fileSize: int | None
    mimeType: str | None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class CampaignCollateralLinkCreate(BaseModel):
    collateralId: str
    campaignId: str
    sortOrder: int = 0


class CampaignCollateralLinkResponse(BaseModel):
    id: str
    collateralId: str
    campaignId: str
    sortOrder: int
    createdAt: datetime

    model_config = {"from_attributes": True}


__all__ = [
    "CollateralCreate",
    "CollateralUpdate",
    "CollateralResponse",
    "CampaignCollateralLinkCreate",
    "CampaignCollateralLinkResponse",
]
