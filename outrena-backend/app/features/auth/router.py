"""
auth.py — Phase 2 /api/v1/auth router.

Endpoints:
  GET  /auth/me                return current user from JWT
  POST /auth/change-password   proxy to Keycloak Admin API
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user
from app.schemas.auth import (
    ChangePasswordRequest,
    TokenPayload,
    UserResponse,
)
from app.schemas.common import MessageResponse
from app.features.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])
_service = AuthService()


@router.get("/me", response_model=UserResponse)
async def get_me(
    token: TokenPayload = Depends(get_current_user),
    _: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Return the current user's profile projected from the validated JWT."""
    return await _service.me(token)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    token: TokenPayload = Depends(get_current_user),
    _: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Proxy a password change to the Keycloak Admin REST API."""
    try:
        result = await _service.change_password(
            token=token,
            current_password=body.currentPassword,
            new_password=body.newPassword,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to change password: {exc}",
        ) from exc
    return MessageResponse(message=str(result.get("message", "Password updated.")), id=token.sub)


__all__ = ["router"]
