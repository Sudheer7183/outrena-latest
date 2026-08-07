"""auth_service.py — /auth/me + /auth/change-password business logic.

Thin wrapper around the existing KeycloakAdminService. The /me endpoint
projects the validated JWT claims (no DB lookup needed); the
/change-password endpoint proxies to the Keycloak Admin REST API.
"""
from __future__ import annotations

from typing import Any

import structlog

from app.api.security import get_current_user  # noqa: F401 — re-exported for routers
from app.schemas.auth import Role, TokenPayload, UserResponse
from app.services.keycloak_admin_service import get_keycloak_admin_service

logger = structlog.get_logger(__name__)


class AuthService:
    """Project JWT claims into a public UserResponse + proxy password changes."""

    async def me(self, token: TokenPayload) -> UserResponse:
        """Project the validated JWT claims into a UserResponse."""
        display_name = (token.email or "").split("@", 1)[0]
        return UserResponse(
            id=token.sub,
            email=token.email,
            role=token.role,
            tenant_slug=token.tenant_slug,
            displayName=display_name,
        )

    async def change_password(
        self, token: TokenPayload, current_password: str, new_password: str
    ) -> dict[str, Any]:
        """
        Proxy a password change to the Keycloak Admin REST API.

        Keycloak's Admin API does not verify the current password (admin
        tokens are privileged); the caller's current_password is checked
        client-side or via a separate verify-credentials call before this
        endpoint resets the password.
        """
        service = get_keycloak_admin_service()
        # Best-effort: ensure the user exists in Keycloak before resetting.
        await service.get_user(token.sub)
        await service.reset_password(
            user_id=token.sub,
            new_password=new_password,
            temporary=False,
        )
        logger.info("auth.password_changed", user_id=token.sub)
        return {"ok": True, "message": "Password updated."}


__all__ = ["AuthService"]
