"""user_management_service.py — User CRUD via the Keycloak Admin REST API."""
from __future__ import annotations

from typing import Any

import structlog

from app.api.security import verify_tenant  # noqa: F401 — kept for routers
from app.schemas.auth import Role
from app.schemas.user_management import (
    ResetPasswordRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.keycloak_admin_service import get_keycloak_admin_service

logger = structlog.get_logger(__name__)


def _project_user(raw: dict[str, Any], tenant_slug: str | None = None) -> UserResponse:
    """Project a raw Keycloak user dict into a UserResponse."""
    attributes = raw.get("attributes") or {}
    if isinstance(attributes, dict):
        slug_list = attributes.get("tenant_slug") or []
        if isinstance(slug_list, list) and slug_list:
            tenant_slug = tenant_slug or str(slug_list[0])

    realm_access = raw.get("realm_access") or {}
    roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
    role: Role | None = None
    known = {r.value.lower() for r in Role}
    for r in roles:
        if isinstance(r, str) and r.lower() in known:
            role = Role(r.upper())
            break

    first = raw.get("firstName") or ""
    last = raw.get("lastName") or ""
    display_name = (f"{first} {last}").strip() or (raw.get("username") or "")

    return UserResponse(
        id=raw.get("id", ""),
        email=raw.get("email"),
        firstName=raw.get("firstName"),
        lastName=raw.get("lastName"),
        role=role,
        enabled=bool(raw.get("enabled", True)),
        tenant_slug=tenant_slug,
        displayName=display_name or None,
    )


class UserManagementService:
    """CRUD wrapper around KeycloakAdminService for tenant users."""

    async def list_users(self, tenant_slug: str) -> list[UserResponse]:
        service = get_keycloak_admin_service()
        raw_users = await service.list_tenant_users(tenant_slug)
        return [_project_user(u, tenant_slug) for u in raw_users]

    async def create_user(
        self, tenant_slug: str, body: UserCreate
    ) -> UserResponse:
        service = get_keycloak_admin_service()
        admin_token = await service.get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}

        user_payload: dict[str, Any] = {
            "username": body.email,
            "email": body.email,
            "firstName": body.firstName,
            "lastName": body.lastName,
            "enabled": True,
            "emailVerified": not body.sendInvitation,
            "attributes": {"tenant_slug": [tenant_slug]},
            "credentials": [],
        }
        if body.temporaryPassword:
            user_payload["credentials"] = [
                {
                    "type": "password",
                    "value": body.temporaryPassword,
                    "temporary": True,
                }
            ]
        required_actions: list[str] = []
        if body.sendInvitation:
            required_actions.append("VERIFY_EMAIL")
        # NFR-015 / FR-090: MFA mandatory for admin roles — force TOTP setup.
        if str(getattr(body, "role", "") or "").upper() in ("TENANT_ADMIN", "SUPER_ADMIN"):
            required_actions.append("CONFIGURE_TOTP")
        if required_actions:
            user_payload["requiredActions"] = required_actions

        # Reuse the underlying httpx client from the service.
        resp = await service._http_client.post(  # noqa: SLF001 — internal access acceptable in this wrapper
            f"{service._admin_realm_url()}/users",
            json=user_payload,
            headers=headers,
        )
        resp.raise_for_status()
        user_id = resp.headers.get("Location", "").rstrip("/").split("/")[-1]
        if not user_id:
            raise RuntimeError("Keycloak did not return a user ID.")

        await service._assign_realm_role(admin_token, user_id, body.role)

        raw = await service.get_user(user_id)
        return _project_user(raw, tenant_slug)

    async def update_user(
        self, user_id: str, body: UserUpdate, tenant_slug: str | None = None
    ) -> UserResponse:
        service = get_keycloak_admin_service()
        payload: dict[str, Any] = {}
        if body.email is not None:
            payload["email"] = body.email
            payload["username"] = body.email
        if body.firstName is not None:
            payload["firstName"] = body.firstName
        if body.lastName is not None:
            payload["lastName"] = body.lastName
        if body.enabled is not None:
            payload["enabled"] = body.enabled

        if payload:
            await service.update_user(user_id, payload)

        # FR-087: deactivation must revoke active sessions immediately, not
        # merely wait for the 5-minute access-token expiry. Keycloak's admin
        # logout endpoint invalidates all of the user's sessions.
        if body.enabled is False:
            try:
                admin_token = await service.get_admin_token()
                await service._http_client.post(  # noqa: SLF001
                    f"{service._admin_realm_url()}/users/{user_id}/logout",  # noqa: SLF001
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
            except Exception:  # noqa: BLE001 — best-effort; disable already applied
                pass

        if body.role is not None:
            admin_token = await service.get_admin_token()
            await service._assign_realm_role(admin_token, user_id, body.role)
            # NFR-015: promotion to an admin role requires TOTP on next login.
            if str(body.role).upper() in ("TENANT_ADMIN", "SUPER_ADMIN"):
                try:
                    await service.update_user(
                        user_id, {"requiredActions": ["CONFIGURE_TOTP"]}
                    )
                except Exception:  # noqa: BLE001 — best-effort
                    pass

        raw = await service.get_user(user_id)
        return _project_user(raw, tenant_slug)

    async def delete_user(self, user_id: str) -> bool:
        service = get_keycloak_admin_service()
        await service.delete_user(user_id)
        return True

    async def reset_password(
        self, user_id: str, body: ResetPasswordRequest
    ) -> dict[str, Any]:
        service = get_keycloak_admin_service()
        await service.reset_password(
            user_id=user_id,
            new_password=body.newPassword,
            temporary=body.temporary,
        )
        return {"ok": True, "message": "Password reset."}


__all__ = ["UserManagementService"]
