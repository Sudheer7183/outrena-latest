"""
auth.py — Role hierarchy and JWT payload contract.

Claims contract (reference model Section 3.3):
  - role         single string claim (NOT an array)
  - tenant_slug  string claim; None/absent for platform-level admins

OUTRENA operational roles (mapped from the original NextAuth 3-role model):
  - REP          sales representative (was: "rep")
  - MANAGER      sales manager (was: "manager")
  - TENANT_ADMIN tenant administrator (was: "admin")
  - SUPER_ADMIN  platform operator (NEW — structural, platform-level only)
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    MANAGER = "MANAGER"
    REP = "REP"


# Higher number = more privilege. verify_role() compares against this map.
ROLE_HIERARCHY: dict[Role, int] = {
    Role.REP: 10,
    Role.MANAGER: 20,
    Role.TENANT_ADMIN: 30,
    Role.SUPER_ADMIN: 40,
}


class TokenPayload(BaseModel):
    """Validated claims extracted from a verified JWT."""

    model_config = ConfigDict(frozen=True)

    sub: str
    email: str
    role: Role
    tenant_slug: str | None  # None ⇒ platform-level (SUPER_ADMIN) token


# ── Phase 2 — /auth/me + /auth/change-password ──────────────────────────────


class UserResponse(BaseModel):
    """Public user profile returned by GET /auth/me."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    firstName: str | None = None
    lastName: str | None = None
    role: Role
    tenant_slug: str | None = None
    displayName: str | None = None


class ChangePasswordRequest(BaseModel):
    """Body for POST /auth/change-password — proxy to Keycloak Admin API."""

    currentPassword: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8, max_length=128)


__all__ = [
    "Role",
    "ROLE_HIERARCHY",
    "TokenPayload",
    "UserResponse",
    "ChangePasswordRequest",
]
