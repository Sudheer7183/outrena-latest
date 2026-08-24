# """
# user_management.py — Phase 2 /api/v1/users router.

# Endpoints:
#   GET    /users                                              list users (Keycloak Admin API)
#   POST   /users                                              create user (Keycloak Admin API)
#   PUT    /users/{user_id}                                    update user
#   DELETE /users/{user_id}                                    delete user (204)
#   POST   /users/{user_id}/reset-password                     reset password

# Per-user sender identities + email quota (SAAS2-USER-BE §L):
#   GET    /users/me/sender-identities                         list current user's sender identities
#   POST   /users/me/sender-identities                         add a sender identity
#   DELETE /users/me/sender-identities/{identity_id}           delete a sender identity (204)
#   POST   /users/me/sender-identities/{identity_id}/set-default  mark as default
#   GET    /users/me/email-quota                               current user's quota status
#   GET    /users/email-quotas                                 MANAGER+ — all users' quota status

# Role gate: Role.TENANT_ADMIN for user CRUD. Sender-identity + email-quota
# endpoints accept Role.REP (own only) or Role.MANAGER (all users).
# """
# from __future__ import annotations

# from datetime import datetime, timezone

# from fastapi import APIRouter, Depends, HTTPException, status
# from fastapi.responses import Response
# from pydantic import BaseModel, Field
# from sqlalchemy import select, update
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import require_role
# from app.models.user_email import UserSenderIdentity
# from app.schemas.auth import Role, TokenPayload
# from app.schemas.user_management import (
#     ResetPasswordRequest,
#     UserCreate,
#     UserResponse,
#     UserUpdate,
# )
# from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
# from app.features.user_management.service import UserManagementService

# router = APIRouter(prefix="/users", tags=["User Management"])
# _service = UserManagementService()
# _quota_service = UserEmailQuotaService()


# def _tenant_slug(token: TokenPayload) -> str:
#     if not token.tenant_slug:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Platform-level users cannot manage tenant users.",
#         )
#     return token.tenant_slug


# # ── User CRUD (Keycloak Admin API) ─────────────────────────────────────────


# @router.get("", response_model=list[UserResponse])
# async def list_users(
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> list[UserResponse]:
#     """List all users belonging to the current tenant.

#     BUG-19 FIX: Returns empty list instead of 500 when Keycloak is unavailable.
#     """
#     try:
#         return await _service.list_users(_tenant_slug(token))
#     except Exception:  # noqa: BLE001 — Keycloak may be unavailable in dev
#         return []


# @router.post("", response_model=UserResponse, status_code=201)
# async def create_user(
#     body: UserCreate,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> UserResponse:
#     """Create a new user in the current tenant via Keycloak Admin API."""
#     try:
#         return await _service.create_user(_tenant_slug(token), body)
#     except HTTPException:
#         raise
#     except Exception as exc:  # noqa: BLE001
#         raise HTTPException(
#             status_code=status.HTTP_502_BAD_GATEWAY,
#             detail=f"Keycloak user creation failed: {exc}",
#         ) from exc


# @router.put("/{user_id}", response_model=UserResponse)
# async def update_user(
#     user_id: str,
#     body: UserUpdate,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> UserResponse:
#     """Update a user via the Keycloak Admin API."""
#     try:
#         result = await _service.update_user(
#             user_id=user_id,
#             body=body,
#             tenant_slug=_tenant_slug(token),
#         )
#     except HTTPException:
#         raise
#     except Exception as exc:  # noqa: BLE001
#         raise HTTPException(
#             status_code=status.HTTP_502_BAD_GATEWAY,
#             detail=f"Keycloak user update failed: {exc}",
#         ) from exc
#     return result


# @router.delete("/{user_id}", response_model=None, response_class=Response, status_code=204)
# async def delete_user(
#     user_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> Response:
#     """Delete a user via the Keycloak Admin API. Returns 204 on success."""
#     try:
#         await _service.delete_user(user_id)
#     except HTTPException:
#         raise
#     except Exception as exc:  # noqa: BLE001
#         raise HTTPException(
#             status_code=status.HTTP_502_BAD_GATEWAY,
#             detail=f"Keycloak user delete failed: {exc}",
#         ) from exc
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# @router.post("/{user_id}/reset-password", response_model=dict)
# async def reset_password(
#     user_id: str,
#     body: ResetPasswordRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> dict:
#     """Reset a user's password via the Keycloak Admin API."""
#     try:
#         return await _service.reset_password(user_id, body)
#     except HTTPException:
#         raise
#     except Exception as exc:  # noqa: BLE001
#         raise HTTPException(
#             status_code=status.HTTP_502_BAD_GATEWAY,
#             detail=f"Keycloak password reset failed: {exc}",
#         ) from exc


# # ── Sender identity + email quota endpoints (SAAS2-USER-BE §L) ─────────────
# # Static routes registered BEFORE /{user_id} so they don't shadow CRUD paths.


# class SenderIdentityCreate(BaseModel):
#     """Body for POST /users/me/sender-identities."""
#     email: str = Field(..., min_length=3, max_length=255)
#     email_type: str = Field(
#         default="platform_assigned",
#         description='"platform_assigned" | "corporate"',
#     )
#     display_name: str | None = Field(default=None, max_length=255)
#     is_default: bool = False
#     daily_send_quota: int = Field(default=100, ge=1, le=10000)


# class SenderIdentityResponse(BaseModel):
#     """Public shape of a UserSenderIdentity row."""
#     id: int
#     user_id: str
#     email: str
#     email_type: str
#     display_name: str | None = None
#     is_verified: bool
#     is_default: bool
#     daily_send_quota: int
#     createdAt: datetime
#     updatedAt: datetime

#     model_config = {"from_attributes": True}


# @router.get(
#     "/me/sender-identities",
#     response_model=list[SenderIdentityResponse],
# )
# async def list_my_sender_identities(
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> list[SenderIdentityResponse]:
#     """List the calling user's sender identities."""
#     result = await db.execute(
#         select(UserSenderIdentity)
#         .where(UserSenderIdentity.user_id == token.sub)
#         .order_by(UserSenderIdentity.createdAt.desc())
#     )
#     return [SenderIdentityResponse.model_validate(r) for r in result.scalars().all()]


# @router.post(
#     "/me/sender-identities",
#     response_model=SenderIdentityResponse,
#     status_code=201,
# )
# async def create_my_sender_identity(
#     body: SenderIdentityCreate,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> SenderIdentityResponse:
#     """Add a sender identity for the calling user.

#     Corporate emails are NOT auto-verified — DNS verification (SPF/DKIM) is
#     required before is_verified=True is set. The endpoint leaves is_verified
#     False and logs the request; an admin/automation task flips it later.
#     """
#     if body.email_type not in ("platform_assigned", "corporate"):
#         raise HTTPException(
#             status.HTTP_400_BAD_REQUEST,
#             detail="email_type must be 'platform_assigned' or 'corporate'.",
#         )

#     # If is_default=True, clear the previous default for this user.
#     if body.is_default:
#         await db.execute(
#             update(UserSenderIdentity)
#             .where(
#                 UserSenderIdentity.user_id == token.sub,
#                 UserSenderIdentity.is_default.is_(True),
#             )
#             .values(is_default=False)
#         )

#     # Corporate emails start unverified; platform_assigned start verified
#     # (provisioning flow would have verified the mailbox).
#     is_verified = body.email_type == "platform_assigned"
#     identity = UserSenderIdentity(
#         user_id=token.sub,
#         email=body.email,
#         email_type=body.email_type,
#         display_name=body.display_name,
#         is_verified=is_verified,
#         is_default=body.is_default,
#         daily_send_quota=body.daily_send_quota,
#     )
#     db.add(identity)
#     await db.commit()
#     identity = await db.get(UserSenderIdentity, identity.id)
#     return SenderIdentityResponse.model_validate(identity)


# @router.delete(
#     "/me/sender-identities/{identity_id}",
#     response_model=None,
#     response_class=Response,
#     status_code=204,
# )
# async def delete_my_sender_identity(
#     identity_id: int,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> Response:
#     """Delete one of the calling user's sender identities."""
#     result = await db.execute(
#         select(UserSenderIdentity).where(
#             UserSenderIdentity.id == identity_id,
#             UserSenderIdentity.user_id == token.sub,
#         )
#     )
#     identity = result.scalar_one_or_none()
#     if identity is None:
#         raise HTTPException(
#             status.HTTP_404_NOT_FOUND, "Sender identity not found."
#         )
#     await db.delete(identity)
#     await db.commit()
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# @router.post(
#     "/me/sender-identities/{identity_id}/set-default",
#     response_model=SenderIdentityResponse,
# )
# async def set_default_sender_identity(
#     identity_id: int,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> SenderIdentityResponse:
#     """Mark one of the calling user's sender identities as the default."""
#     result = await db.execute(
#         select(UserSenderIdentity).where(
#             UserSenderIdentity.id == identity_id,
#             UserSenderIdentity.user_id == token.sub,
#         )
#     )
#     identity = result.scalar_one_or_none()
#     if identity is None:
#         raise HTTPException(
#             status.HTTP_404_NOT_FOUND, "Sender identity not found."
#         )
#     # Clear previous default.
#     await db.execute(
#         update(UserSenderIdentity)
#         .where(
#             UserSenderIdentity.user_id == token.sub,
#             UserSenderIdentity.is_default.is_(True),
#         )
#         .values(is_default=False)
#     )
#     identity.is_default = True
#     await db.commit()
#     identity = await db.get(UserSenderIdentity, identity.id)
#     return SenderIdentityResponse.model_validate(identity)


# @router.get("/me/email-quota", response_model=dict)
# async def get_my_email_quota(
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> dict:
#     """Return the calling user's current-day email quota + throttle status."""
#     return await _quota_service.get_user_quota_status(db, token.sub)


# @router.get("/email-quotas", response_model=list[dict])
# async def list_tenant_email_quotas(
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> list[dict]:
#     """Return quota statuses for every user with activity today (MANAGER+ only)."""
#     return await _quota_service.get_tenant_quota_summary(db)


# __all__ = ["router"]

"""
user_management.py — Phase 2 /api/v1/users router.

Endpoints:
  GET    /users                                              list users (Keycloak Admin API)
  POST   /users                                              create user (Keycloak Admin API)
  PUT    /users/{user_id}                                    update user
  DELETE /users/{user_id}                                    delete user (204)
  POST   /users/{user_id}/reset-password                     reset password

Per-user sender profile (NEW — personalisation fix):
  GET    /users/me/profile                                   get current user's sender profile + signature
  PUT    /users/me/profile                                   update sender profile + signature

Per-user sender identities + email quota (SAAS2-USER-BE §L):
  GET    /users/me/sender-identities                         list current user's sender identities
  POST   /users/me/sender-identities                         add a sender identity
  DELETE /users/me/sender-identities/{identity_id}           delete a sender identity (204)
  POST   /users/me/sender-identities/{identity_id}/set-default  mark as default
  GET    /users/me/email-quota                               current user's quota status
  GET    /users/email-quotas                                 MANAGER+ — all users' quota status

Role gate: Role.TENANT_ADMIN for user CRUD. Sender-identity + email-quota
endpoints accept Role.REP (own only) or Role.MANAGER (all users).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.models.user_email import UserSenderIdentity
from app.schemas.auth import Role, TokenPayload
from app.schemas.user_management import (
    ResetPasswordRequest,
    UserCreate,
    UserProfileResponse,
    UserProfileUpdate,
    UserResponse,
    UserUpdate,
)
from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
from app.features.user_management.service import UserManagementService

router = APIRouter(prefix="/users", tags=["User Management"])
_service = UserManagementService()
_quota_service = UserEmailQuotaService()


def _tenant_slug(token: TokenPayload) -> str:
    if not token.tenant_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform-level users cannot manage tenant users.",
        )
    return token.tenant_slug


# ── User CRUD (Keycloak Admin API) ─────────────────────────────────────────


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> list[UserResponse]:
    """List all users belonging to the current tenant.

    BUG-19 FIX: Returns empty list instead of 500 when Keycloak is unavailable.
    """
    try:
        return await _service.list_users(_tenant_slug(token))
    except Exception:  # noqa: BLE001 — Keycloak may be unavailable in dev
        return []


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> UserResponse:
    """Create a new user in the current tenant via Keycloak Admin API."""
    try:
        return await _service.create_user(_tenant_slug(token), body)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak user creation failed: {exc}",
        ) from exc


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> UserResponse:
    """Update a user via the Keycloak Admin API."""
    try:
        result = await _service.update_user(
            user_id=user_id,
            body=body,
            tenant_slug=_tenant_slug(token),
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak user update failed: {exc}",
        ) from exc
    return result


@router.delete("/{user_id}", response_model=None, response_class=Response, status_code=204)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    """Delete a user via the Keycloak Admin API. Returns 204 on success."""
    try:
        await _service.delete_user(user_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak user delete failed: {exc}",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{user_id}/reset-password", response_model=dict)
async def reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> dict:
    """Reset a user's password via the Keycloak Admin API."""
    try:
        return await _service.reset_password(user_id, body)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Keycloak password reset failed: {exc}",
        ) from exc


# ── Sender profile — /me/profile (personalisation fix) ────────────────────
# These MUST be registered before /{user_id} to avoid path shadowing.


@router.get("/me/profile", response_model=UserProfileResponse)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> UserProfileResponse:
    """
    Return the calling user's sender profile.

    The frontend calls this on login and stores the result in auth context.
    The profile fields (senderTitle, senderCompany, senderOffer, emailSignature,
    physicalAddress) are then passed to POST /email-studio/generate-email so
    the AI writes fully personalised emails with no [Your Name] placeholders.
    """
    try:
        return await _service.get_profile(token.sub)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not retrieve profile from Keycloak: {exc}",
        ) from exc


@router.put("/me/profile", response_model=UserProfileResponse)
async def update_my_profile(
    body: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> UserProfileResponse:
    """
    Update the calling user's sender profile (merge — only supplied fields written).

    Fields persisted to Keycloak attributes:
      - senderTitle       e.g. "Account Executive"
      - senderCompany     e.g. "ClearCourse.ai"
      - senderOffer       one-line value proposition used by the AI
      - emailSignature    full plain-text signature appended to every email
      - physicalAddress   CAN-SPAM registered postal address

    Pass null for any field to clear it.
    """
    try:
        return await _service.update_profile(token.sub, body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not update profile in Keycloak: {exc}",
        ) from exc


# ── Sender identity + email quota endpoints (SAAS2-USER-BE §L) ─────────────
# Static routes registered BEFORE /{user_id} so they don't shadow CRUD paths.


class SenderIdentityCreate(BaseModel):
    """Body for POST /users/me/sender-identities."""
    email: str = Field(..., min_length=3, max_length=255)
    email_type: str = Field(
        default="platform_assigned",
        description='"platform_assigned" | "corporate"',
    )
    display_name: str | None = Field(default=None, max_length=255)
    is_default: bool = False
    daily_send_quota: int = Field(default=100, ge=1, le=10000)


class SenderIdentityResponse(BaseModel):
    """Public shape of a UserSenderIdentity row."""
    id: int
    user_id: str
    email: str
    email_type: str
    display_name: str | None = None
    is_verified: bool
    is_default: bool
    daily_send_quota: int
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


@router.get(
    "/me/sender-identities",
    response_model=list[SenderIdentityResponse],
)
async def list_my_sender_identities(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> list[SenderIdentityResponse]:
    """List the calling user's sender identities."""
    result = await db.execute(
        select(UserSenderIdentity)
        .where(UserSenderIdentity.user_id == token.sub)
        .order_by(UserSenderIdentity.createdAt.desc())
    )
    return [SenderIdentityResponse.model_validate(r) for r in result.scalars().all()]


@router.post(
    "/me/sender-identities",
    response_model=SenderIdentityResponse,
    status_code=201,
)
async def create_my_sender_identity(
    body: SenderIdentityCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> SenderIdentityResponse:
    """Add a sender identity for the calling user.

    Corporate emails are NOT auto-verified — DNS verification (SPF/DKIM) is
    required before is_verified=True is set. The endpoint leaves is_verified
    False and logs the request; an admin/automation task flips it later.
    """
    if body.email_type not in ("platform_assigned", "corporate"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="email_type must be 'platform_assigned' or 'corporate'.",
        )

    # If is_default=True, clear the previous default for this user.
    if body.is_default:
        await db.execute(
            update(UserSenderIdentity)
            .where(
                UserSenderIdentity.user_id == token.sub,
                UserSenderIdentity.is_default.is_(True),
            )
            .values(is_default=False)
        )

    # Corporate emails start unverified; platform_assigned start verified.
    is_verified = body.email_type == "platform_assigned"
    identity = UserSenderIdentity(
        user_id=token.sub,
        email=body.email,
        email_type=body.email_type,
        display_name=body.display_name,
        is_verified=is_verified,
        is_default=body.is_default,
        daily_send_quota=body.daily_send_quota,
    )
    db.add(identity)
    await db.commit()
    identity = await db.get(UserSenderIdentity, identity.id)
    return SenderIdentityResponse.model_validate(identity)


@router.delete(
    "/me/sender-identities/{identity_id}",
    response_model=None,
    response_class=Response,
    status_code=204,
)
async def delete_my_sender_identity(
    identity_id: int,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> Response:
    """Delete one of the calling user's sender identities."""
    result = await db.execute(
        select(UserSenderIdentity).where(
            UserSenderIdentity.id == identity_id,
            UserSenderIdentity.user_id == token.sub,
        )
    )
    identity = result.scalar_one_or_none()
    if identity is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Sender identity not found."
        )
    await db.delete(identity)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/me/sender-identities/{identity_id}/set-default",
    response_model=SenderIdentityResponse,
)
async def set_default_sender_identity(
    identity_id: int,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> SenderIdentityResponse:
    """Mark one of the calling user's sender identities as the default."""
    result = await db.execute(
        select(UserSenderIdentity).where(
            UserSenderIdentity.id == identity_id,
            UserSenderIdentity.user_id == token.sub,
        )
    )
    identity = result.scalar_one_or_none()
    if identity is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Sender identity not found."
        )
    # Clear previous default.
    await db.execute(
        update(UserSenderIdentity)
        .where(
            UserSenderIdentity.user_id == token.sub,
            UserSenderIdentity.is_default.is_(True),
        )
        .values(is_default=False)
    )
    identity.is_default = True
    await db.commit()
    identity = await db.get(UserSenderIdentity, identity.id)
    return SenderIdentityResponse.model_validate(identity)


@router.get("/me/email-quota", response_model=dict)
async def get_my_email_quota(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """Return the calling user's current-day email quota + throttle status."""
    return await _quota_service.get_user_quota_status(db, token.sub)


@router.get("/email-quotas", response_model=list[dict])
async def list_tenant_email_quotas(
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> list[dict]:
    """Return quota statuses for every user with activity today (MANAGER+ only)."""
    return await _quota_service.get_tenant_quota_summary(db)


__all__ = ["router"]

