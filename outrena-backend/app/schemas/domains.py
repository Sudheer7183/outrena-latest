"""domains.py — Domain CRUD + DNS check schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainCreate(BaseModel):
    """Body for POST /domains.

    Accepts both ``domainName`` (backend canonical) and ``domain``
    (frontend DomainsPage sends this key). The validator normalises
    ``domain`` → ``domainName`` so both callers work without changes.
    """

    domainName: str = Field(default="", min_length=0)
    domain: str | None = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _normalise_domain(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if not values.get("domainName") and values.get("domain"):
                values["domainName"] = values["domain"]
        return values
    spfStatus: bool = False
    dkimStatus: bool = False
    dmarcStatus: bool = False
    dailySendLimit: int = 10
    warmingWeek: int = 1
    isActive: bool = True


class DomainUpdate(BaseModel):
    """Body for PUT /domains/{domain_id}."""

    domainName: str | None = None
    spfStatus: bool | None = None
    dkimStatus: bool | None = None
    dmarcStatus: bool | None = None
    dailySendLimit: int | None = None
    warmingWeek: int | None = None
    isActive: bool | None = None


class DomainResponse(BaseModel):
    """Public shape of a Domain row.

    BUG-06 FIX: Added `domain` as an alias for `domainName` so the frontend
    can use either field. The frontend DomainsPage uses `domain`, the DB column is `domainName`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    domainName: str
    spfStatus: bool
    dkimStatus: bool
    dmarcStatus: bool
    dailySendLimit: int
    warmingWeek: int
    isActive: bool
    lastChecked: datetime | None = None
    createdAt: datetime
    updatedAt: datetime

    @property
    def domain(self) -> str:
        """BUG-06 FIX: Alias for domainName for frontend compatibility."""
        return self.domainName

    def model_post_init(self, __context: object) -> None:
        pass  # Required for @property to serialize via model_dump

    def model_dump(self, **kwargs: object) -> dict:
        d = super().model_dump(**kwargs)
        d["domain"] = d.get("domainName", "")
        return d


class DnsCheckRequest(BaseModel):
    """Body for POST /domains/dns-check — MX/SPF/DKIM/DMARC lookup."""

    domain: str = Field(..., min_length=1)
    selector: str = "default"  # DKIM selector


class DnsRecordResult(BaseModel):
    """One DNS record outcome (MX, SPF, DKIM, DMARC)."""

    name: str
    found: bool
    records: list[str] = []
    detail: str | None = None


class DnsCheckResult(BaseModel):
    """Aggregated DNS check result for a domain."""

    domain: str
    mx: DnsRecordResult
    spf: DnsRecordResult
    dkim: DnsRecordResult
    dmarc: DnsRecordResult
    allPassed: bool


__all__ = [
    "DomainCreate",
    "DomainUpdate",
    "DomainResponse",
    "DnsCheckRequest",
    "DnsRecordResult",
    "DnsCheckResult",
]
