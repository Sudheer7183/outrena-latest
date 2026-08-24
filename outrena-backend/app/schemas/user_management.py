# """user_management.py — User CRUD schemas (proxy to Keycloak Admin API)."""
# from __future__ import annotations

# from pydantic import BaseModel, ConfigDict, EmailStr, Field

# from app.schemas.auth import Role


# class UserCreate(BaseModel):
#     """Body for POST /users — create a Keycloak user with tenant_slug attribute."""

#     email: EmailStr
#     firstName: str = Field(..., min_length=1)
#     lastName: str = Field(..., min_length=1)
#     role: Role = Role.REP
#     temporaryPassword: str | None = Field(default=None, min_length=8, max_length=128)
#     sendInvitation: bool = False


# class UserUpdate(BaseModel):
#     """Body for PUT /users/{user_id} — partial update via Keycloak Admin API."""

#     email: EmailStr | None = None
#     firstName: str | None = None
#     lastName: str | None = None
#     role: Role | None = None
#     enabled: bool | None = None


# class ResetPasswordRequest(BaseModel):
#     """Body for POST /users/{user_id}/reset-password."""

#     newPassword: str = Field(..., min_length=8, max_length=128)
#     temporary: bool = True


# class UserResponse(BaseModel):
#     """Public user shape returned by /users endpoints (Keycloak user projection)."""

#     model_config = ConfigDict(from_attributes=True)

#     id: str
#     email: str | None = None
#     firstName: str | None = None
#     lastName: str | None = None
#     role: Role | None = None
#     enabled: bool = True
#     tenant_slug: str | None = None
#     displayName: str | None = None


# class UserListResponse(BaseModel):
#     items: list[UserResponse]
#     total: int = 0


# __all__ = [
#     "UserCreate",
#     "UserUpdate",
#     "ResetPasswordRequest",
#     "UserResponse",
#     "UserListResponse",
# ]

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


# ── User profile (sender identity + signature) ────────────────────────────────
# Stored as Keycloak user attributes.  The frontend reads /users/me/profile
# on login and passes these fields when calling POST /email-studio/generate-email.

class UserProfileUpdate(BaseModel):
    """
    Body for PUT /users/me/profile.

    All fields are optional — only supplied fields are written to Keycloak.
    """

    senderTitle: str | None = Field(
        default=None,
        max_length=128,
        description="Job title shown in outbound emails, e.g. 'Account Executive'.",
    )
    senderCompany: str | None = Field(
        default=None,
        max_length=128,
        description="Company name shown in outbound emails, e.g. 'ClearCourse.ai'.",
    )
    senderOffer: str | None = Field(
        default=None,
        max_length=256,
        description="One-line value proposition used by the AI to personalise emails.",
    )
    emailSignature: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Full plain-text email signature appended after every generated email body. "
            "Example:\n"
            "  Best,\n"
            "  Jane Doe\n"
            "  Account Executive | ClearCourse.ai\n"
            "  +1 555 000 0000\n"
            "  jane@clearcourse.ai"
        ),
    )
    physicalAddress: str | None = Field(
        default=None,
        max_length=256,
        description=(
            "Registered postal address appended in the CAN-SPAM footer. "
            "Example: '123 Main St, San Francisco, CA 94105, USA'."
        ),
    )


class UserProfileResponse(BaseModel):
    """Shape returned by GET /users/me/profile."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    displayName: str | None = None
    senderTitle: str | None = None
    senderCompany: str | None = None
    senderOffer: str | None = None
    emailSignature: str | None = None
    physicalAddress: str | None = None


__all__ = [
    "UserCreate",
    "UserUpdate",
    "ResetPasswordRequest",
    "UserResponse",
    "UserListResponse",
    "UserProfileUpdate",
    "UserProfileResponse",
]
