"""ab_testing.py — A/B split-cohort test contracts + significance."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AbTestCreate(BaseModel):
    name: str
    campaignId: str
    description: str | None = None
    element: str = "subject"  # subject | body | sendTime
    variantALabel: str = "Variant A"
    variantBLabel: str = "Variant B"
    variantASubject: str | None = None
    variantBSubject: str | None = None
    variantABody: str | None = None
    variantBBody: str | None = None
    splitRatio: float = Field(default=0.5, ge=0.0, le=1.0)
    touchNumber: int = 1


class AbTestUpdate(BaseModel):
    status: str | None = None
    startedAt: datetime | None = None
    endedAt: datetime | None = None


class AbTestResponse(BaseModel):
    id: str
    name: str
    campaignId: str
    description: str | None
    element: str
    variantALabel: str
    variantBLabel: str
    variantASubject: str | None
    variantBSubject: str | None
    variantABody: str | None
    variantBBody: str | None
    splitRatio: float
    status: str
    touchNumber: int
    startedAt: datetime | None
    endedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class SignificanceResult(BaseModel):
    """Two-proportion z-test result for an A/B test."""
    abTestId: str
    variantACount: int
    variantBCount: int
    variantASuccesses: int
    variantBSuccesses: int
    variantARate: float
    variantBRate: float
    zScore: float
    pValue: float
    isSignificant: bool  # p < 0.05
    winner: str | None  # "A" | "B" | None


class EmailAbTestResponse(BaseModel):
    id: str
    campaignId: str
    name: str
    subjectA: str
    subjectB: str
    status: str
    winner: str | None
    startedAt: datetime
    completedAt: datetime | None

    model_config = {"from_attributes": True}


__all__ = [
    "AbTestCreate",
    "AbTestUpdate",
    "AbTestResponse",
    "SignificanceResult",
    "EmailAbTestResponse",
]
