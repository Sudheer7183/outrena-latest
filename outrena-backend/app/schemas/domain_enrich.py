"""domain_enrich.py — Domain enrichment contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class DomainEnrichRequest(BaseModel):
    """Body for POST /domain-enrich — fetch/cache enrichment for one domain."""
    domain: str
    forceRefresh: bool = False


class DomainEnrichmentResponse(BaseModel):
    """BUG-14 FIX: techStack coerced from JSON string to list if needed."""

    id: str
    domain: str
    companyName: str | None
    industry: str | None
    employeeCount: int | None
    revenueRange: str | None
    techStack: list[str] = []
    location: str | None
    description: str | None
    lastEnrichedAt: datetime

    model_config = {"from_attributes": True}

    @field_validator("techStack", mode="before")
    @classmethod
    def _coerce_tech_stack(cls, v: object) -> list[str]:
        """BUG-14 FIX: Parse stringified JSON array from DB TEXT column."""
        import json
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
                return []
            except (json.JSONDecodeError, ValueError):
                return [v] if v else []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []


class DomainEnrichBatchRequest(BaseModel):
    domains: list[str]


class DomainEnrichBatchResponse(BaseModel):
    enriched: list[DomainEnrichmentResponse]
    failed: list[str]


__all__ = [
    "DomainEnrichRequest",
    "DomainEnrichmentResponse",
    "DomainEnrichBatchRequest",
    "DomainEnrichBatchResponse",
]
