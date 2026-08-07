"""tenant.py — Request/response contracts for the platform tenant registry."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.utils.slug import validate_slug


class TenantCreateRequest(BaseModel):
    """Body for POST /platform/tenants — triggers full provisioning."""

    slug: str
    name: str
    tenant_type: str = "STANDARD"
    admin_email: EmailStr
    admin_first_name: str
    admin_last_name: str
    temporary_password: str | None = None
    send_invitation: bool = True

    @field_validator("slug")
    @classmethod
    def _slug_rules(cls, value: str) -> str:
        return validate_slug(value)


class TenantResponse(BaseModel):
    tenant_id: int
    slug: str
    schema_name: str
    name: str
    tenant_type: str
    status: str
    created_at: datetime


class TenantCreatedResponse(BaseModel):
    slug: str
    status: str
    url: str  # the allocated tenant URL — https://{slug}.{BASE_DOMAIN}


class SlugAvailabilityResponse(BaseModel):
    slug: str
    available: bool
    reason: str | None
    url: str  # the clean URL this tenant WOULD receive


class TenantResolved(BaseModel):
    """Lightweight tenant record attached to request.state.tenant."""

    tenant_id: int
    slug: str
    schema_name: str
    status: str

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"
