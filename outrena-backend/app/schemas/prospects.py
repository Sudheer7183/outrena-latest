"""prospects.py — Prospect CRUD + CSV import/export + enrich + email-validate schemas.

Also exports ``ProspectScore`` (100-pt ICP scoring result) and ``ImportResult``
(unified CSV-import outcome) per migration doc §10 Phase 2 + §6.5.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import EnrichmentTier, IntentSource, SeniorityTier


class ProspectCreate(BaseModel):
    """Body for POST /prospects.

    BUG-11 FIX: Accepts a combined `name` field (frontend sends this) and
    splits it into firstName/lastName. Also accepts firstName/lastName directly.
    """

    model_config = ConfigDict(extra="ignore")

    firstName: str = Field(default="", min_length=0)
    lastName: str = Field(default="", min_length=0)

    @model_validator(mode="before")
    @classmethod
    def _split_name(cls, values: object) -> object:
        """BUG-11 FIX: Split combined `name` field into firstName/lastName."""
        if isinstance(values, dict):
            if not values.get("firstName") and not values.get("lastName"):
                name = values.get("name", "").strip()
                if name:
                    parts = name.split(" ", 1)
                    values["firstName"] = parts[0]
                    values["lastName"] = parts[1] if len(parts) > 1 else ""
            # Ensure non-empty
            if not values.get("firstName"):
                values["firstName"] = values.get("name", "Unknown").split()[0] if values.get("name") else "Unknown"
            if not values.get("lastName"):
                values["lastName"] = ""
        return values
    email: str | None = None
    title: str | None = None
    company: str | None = None
    domain: str | None = None
    linkedinUrl: str | None = None
    seniority: SeniorityTier = SeniorityTier.IC
    signals: list = []
    icpProfileId: str | None = None
    timezone: str | None = None
    status: str = "new"
    # GDPR fields (optional on create — defaults applied server-side if omitted).
    consent_status: str | None = None  # granted | withdrawn | pending | not_required
    lawful_basis: str | None = None    # consent | legitimate_interest | contract | legal_obligation | vital_interest | public_task


class ProspectUpdate(BaseModel):
    """Body for PUT /prospects/{prospect_id}."""

    firstName: str | None = None
    lastName: str | None = None
    email: str | None = None
    title: str | None = None
    company: str | None = None
    domain: str | None = None
    linkedinUrl: str | None = None
    seniority: SeniorityTier | None = None
    signals: list | None = None
    qaScore: int | None = None
    emailValidated: bool | None = None
    emailValidationDetail: str | None = None
    emailConfidence: float | None = None
    isCatchAll: bool | None = None
    enrichmentTier: EnrichmentTier | None = None
    intentSource: IntentSource | None = None
    intentDetail: str | None = None
    intentStrength: int | None = None
    timezone: str | None = None
    status: str | None = None
    suppressed: bool | None = None
    suppressionReason: str | None = None
    notes: str | None = None
    icpProfileId: str | None = None
    icpFitScore: int | None = None
    icpPersona: str | None = None
    icpScoreBreakdown: str | None = None
    ultimateProfile: str | None = None
    urgencyTier: str | None = None
    # GDPR fields (optional on update).
    consent_status: str | None = None
    lawful_basis: str | None = None


class ProspectResponse(BaseModel):
    """Public shape of a Prospect row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    firstName: str
    lastName: str
    email: str | None = None
    title: str | None = None
    company: str | None = None
    domain: str | None = None
    linkedinUrl: str | None = None
    seniority: SeniorityTier
    signals: list = []
    qaScore: int | None = None
    emailValidated: bool
    emailValidationDetail: str | None = None
    emailConfidence: float | None = None
    isCatchAll: bool
    enrichmentTier: EnrichmentTier
    intentSource: IntentSource
    intentDetail: str | None = None
    intentStrength: int | None = None
    timezone: str | None = None
    status: str
    suppressed: bool
    suppressionReason: str | None = None
    suppressedAt: datetime | None = None
    notes: str | None = None
    icpProfileId: str | None = None
    icpFitScore: int | None = None
    icpPersona: str | None = None
    icpScoreBreakdown: str | None = None
    ultimateProfile: str | None = None
    urgencyTier: str | None = None
    urgencyDeadline: datetime | None = None
    # GDPR compliance fields.
    consent_status: str = "pending"
    lawful_basis: str = "legitimate_interest"
    deleted_at: datetime | None = None
    anonymized: bool = False
    createdAt: datetime
    updatedAt: datetime

    @field_validator("signals", mode="before")
    @classmethod
    def _parse_signals(cls, v: object) -> list:
        """Parse JSON string or list for signals."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                return []
            except (json.JSONDecodeError, TypeError, ValueError):
                return []
        if isinstance(v, list):
            return v
        return []


class ProspectListResponse(BaseModel):
    """Page envelope for prospect list endpoints."""

    items: list[ProspectResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0


class CsvImportResult(BaseModel):
    """Result of POST /prospects/import."""

    imported: int = 0
    skipped: int = 0
    errors: list[str] = []
    totalRows: int = 0


class EmailValidateRequest(BaseModel):
    """Body for POST /prospects/email-validate — MX-based email validation."""

    email: str = Field(..., min_length=3)


class EmailValidateResponse(BaseModel):
    """Result of MX-based email validation."""

    email: str
    valid: bool
    mxFound: bool
    isCatchAll: bool = False
    detail: str | None = None


class EnrichRequest(BaseModel):
    """Body for POST /prospects/enrich — enrich prospect data."""

    prospectId: str | None = None
    email: str | None = None
    domain: str | None = None


class EnrichResponse(BaseModel):
    """Result of prospect enrichment."""

    prospectId: str | None = None
    enriched: bool
    fields: dict = {}
    detail: str | None = None


# ── Phase 2 additions: prospect scoring + unified CSV import result ─────────


UrgencyTier = Literal["P0", "P1", "P2"]
"""P0 = hottest (total >= 80 OR intentStrength >= 8); P1 = total >= 60; P2 = rest."""


class ProspectScore(BaseModel):
    """
    100-point ICP-fit score + P0/P1/P2 urgency tier.

    Weighted per migration doc §10 Phase 2:
      icp_fit:      40 pts (keyword overlap with IcpProfile)
      intent:       25 pts (intentStrength + intentSource weighting)
      seniority:    15 pts (C_Suite > Director > IC)
      firmographic: 20 pts (company size / domain / industry match)
      total:        sum (capped 0-100)

    Returned by ``app.services.prospect_scoring.ProspectScorer.score_prospect``.
    """

    model_config = ConfigDict(extra="forbid")

    total: int
    icp_fit: int
    intent: int
    seniority: int
    firmographic: int
    urgency_tier: UrgencyTier


class ImportResult(BaseModel):
    """
    Unified CSV-import outcome (per migration doc §6.5).

    Returned by ``app.services.csv_import_service.CsvImportService.import_csv``.
    Differs from ``CsvImportResult`` (the legacy endpoint shape) by using
    ``total``/``created`` (clearer naming) and dropping ``totalRows``.

    - total:   rows parsed from the CSV
    - created: Prospect rows inserted
    - skipped: rows skipped (invalid email, missing required field, etc.)
    - errors:  human-readable error messages (one per skipped row)
    """

    model_config = ConfigDict(extra="forbid")

    total: int
    created: int
    skipped: int
    errors: list[str]


__all__ = [
    # Existing (Phase 1/3)
    "ProspectCreate",
    "ProspectUpdate",
    "ProspectResponse",
    "ProspectListResponse",
    "CsvImportResult",
    "EmailValidateRequest",
    "EmailValidateResponse",
    "EnrichRequest",
    "EnrichResponse",
    # Phase 2 additions
    "UrgencyTier",
    "ProspectScore",
    "ImportResult",
]
