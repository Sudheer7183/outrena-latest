"""user_management.py — User CRUD schemas (proxy to Keycloak Admin API)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.auth import Role


class UserCreate(BaseModel):
    """Body for POST /users — create a Keycloak user with tenant_slug attribute."""

    email: EmailStr
    firstName: str = Field(..., min_length=1)
    lastName: str = Field(..., min_length=1)
    role: Role = Role.REP
    temporaryPassword: str | None = Field(default=None, min_length=8, max_length=128)
    sendInvitation: bool = False


class UserUpdate(BaseModel):
    """Body for PUT /users/{user_id} — partial update via Keycloak Admin API."""

    email: EmailStr | None = None
    firstName: str | None = None
    lastName: str | None = None
    role: Role | None = None
    enabled: bool | None = None


class ResetPasswordRequest(BaseModel):
    """Body for POST /users/{user_id}/reset-password."""

    newPassword: str = Field(..., min_length=8, max_length=128)
    temporary: bool = True


class UserResponse(BaseModel):
    """Public user shape returned by /users endpoints (Keycloak user projection)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    role: Role | None = None
    enabled: bool = True
    tenant_slug: str | None = None
    displayName: str | None = None


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int = 0


__all__ = [
    "UserCreate",
    "UserUpdate",
    "ResetPasswordRequest",
    "UserResponse",
    "UserListResponse",
]
