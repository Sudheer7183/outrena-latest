"""job_change_monitor.py — Alumni-tracker contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JobChangeAlertResponse(BaseModel):
    id: str
    prospectId: str
    previousCompany: str | None
    previousTitle: str | None
    newCompany: str
    newTitle: str | None
    newDomain: str | None
    newLinkedinUrl: str | None
    detectedAt: datetime
    icpProfileId: str | None
    icpFitScore: float | None
    icpPersona: str | None
    matchReason: str | None
    status: str
    notes: str | None
    scanSource: str
    lastScannedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class JobChangeAlertUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


class JobChangeScanRequest(BaseModel):
    """Body for POST /job-change-monitor/scan — kick off a scan."""
    prospectIds: list[str] | None = None  # None ⇒ all prospects


class JobChangeScanResponse(BaseModel):
    scanned: int
    detected: int
    newAlerts: list[JobChangeAlertResponse]


__all__ = [
    "JobChangeAlertResponse",
    "JobChangeAlertUpdate",
    "JobChangeScanRequest",
    "JobChangeScanResponse",
]
