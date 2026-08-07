"""
keycloak_admin_service.py — Identity-provider integration.

Implements (reference model Section 5):
  - RS256 verification against JWKS (Redis-cached, TTL 3600s)
  - Admin-token acquisition
  - Tenant-admin user creation (username = email; tenant_slug attribute;
    realm role names lowercased when talking to Keycloak)
  - Idempotent per-tenant redirect-URI registration (Pitfall #1: wildcard
    subdomain redirect URIs do NOT work — register each tenant explicitly)
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
import structlog
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.cache import get_json, platform_key, set_json
from app.core.config import Settings, get_settings
from app.schemas.auth import Role

logger = structlog.get_logger(__name__)

_JWKS_CACHE_KEY = platform_key("jwks", "keycloak")
_JWKS_TTL_SECONDS = 3600


class KeycloakAdminService:
    """Thin async wrapper around the Keycloak Admin REST API + JWKS."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http_client = httpx.AsyncClient(timeout=10.0)

    # ── Token verification ──────────────────────────────────────────────────

    async def verify_token(self, token: str) -> dict[str, Any]:
        """
        Verify an RS256 JWT against the provider's JWKS and return claims.

        Issuer verification is configurable (VERIFY_JWT_ISSUER) because the
        browser-facing issuer URL frequently differs from the Docker-internal
        address (Pitfall #2). Signature is ALWAYS verified.
        """
        jwks = await self._get_jwks()
        try:
            header = jwt.get_unverified_header(token)
            key = self._match_key(jwks, header.get("kid", ""))
            if key is None:
                # Unknown kid — bust cache and refetch once (key rotation).
                jwks = await self._get_jwks(force_refresh=True)
                key = self._match_key(jwks, header.get("kid", ""))
            if key is None:
                raise JWTError("No matching JWKS key for token 'kid'.")

            return jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                options={
                    "verify_aud": False,  # enable + set audience= in strict setups
                    "verify_iss": self._settings.VERIFY_JWT_ISSUER,
                },
                issuer=self._settings.keycloak_realm_url,
            )
        except JWTError as exc:
            logger.warning("keycloak.token.verify_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signature verification failed.",
            ) from exc

    async def _get_jwks(self, force_refresh: bool = False) -> dict[str, Any]:
        if not force_refresh:
            cached = await get_json(_JWKS_CACHE_KEY)
            if cached is not None:
                return cached
        response = await self._http_client.get(self._settings.keycloak_jwks_url)
        response.raise_for_status()
        jwks: dict[str, Any] = response.json()
        await set_json(_JWKS_CACHE_KEY, jwks, _JWKS_TTL_SECONDS)
        return jwks

    @staticmethod
    def _match_key(jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
        return None

    # ── Admin API ───────────────────────────────────────────────────────────

    async def get_admin_token(self) -> str:
        """Password-grant admin token from the master realm."""
        response = await self._http_client.post(
            f"{self._settings.KEYCLOAK_BASE_URL}/realms/master"
            "/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": self._settings.KEYCLOAK_ADMIN_CLIENT_ID,
                "username": self._settings.KEYCLOAK_ADMIN_USERNAME,
                "password": self._settings.KEYCLOAK_ADMIN_PASSWORD,
            },
        )
        response.raise_for_status()
        return str(response.json()["access_token"])

    def _admin_realm_url(self) -> str:
        return (
            f"{self._settings.KEYCLOAK_BASE_URL}/admin/realms/"
            f"{self._settings.KEYCLOAK_REALM}"
        )

    async def create_tenant_admin_user(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
        tenant_slug: str,
        temporary_password: str | None,
        send_invitation: bool,
    ) -> str:
        """
        Create the TENANT_ADMIN user. Returns the Keycloak user ID.

        Steps: create user → assign realm role → optionally set password.
        """
        admin_token = await self.get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}

        user_payload: dict[str, Any] = {
            "username": email,                       # username = email convention
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": not send_invitation,
            "attributes": {"tenant_slug": [tenant_slug]},
        }
        required_actions: list[str] = []
        if send_invitation:
            required_actions.append("VERIFY_EMAIL")
        # NFR-015 / FR-090: MFA is mandatory for TENANT_ADMIN and SUPER_ADMIN.
        # This function always creates the TENANT_ADMIN, so TOTP setup is
        # always required on first login. The realm's otpPolicy
        # (keycloak/realm-export.json) defines the TOTP parameters.
        required_actions.append("CONFIGURE_TOTP")
        if required_actions:
            user_payload["requiredActions"] = required_actions

        try:
            create_resp = await self._http_client.post(
                f"{self._admin_realm_url()}/users", json=user_payload, headers=headers
            )
            create_resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("keycloak.user.create_failed", email=email, error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to create identity-provider user for '{email}'.",
            ) from exc

        # Keycloak returns the new user's URL in the Location header.
        user_id = create_resp.headers.get("Location", "").rstrip("/").split("/")[-1]
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Identity provider did not return a user ID.",
            )

        await self._assign_realm_role(admin_token, user_id, Role.TENANT_ADMIN)

        if temporary_password is not None:
            await self._http_client.put(
                f"{self._admin_realm_url()}/users/{user_id}/reset-password",
                json={"type": "password", "value": temporary_password, "temporary": True},
                headers=headers,
            )

        return user_id

    async def _assign_realm_role(
        self, admin_token: str, user_id: str, role: Role
    ) -> None:
        """
        Assign a realm role. Keycloak realm roles are defined LOWERCASE
        ('tenant_admin') while the Role enum is uppercase — lowercase the
        name when calling the Admin API.
        """
        headers = {"Authorization": f"Bearer {admin_token}"}
        role_name = role.value.lower()

        role_resp = await self._http_client.get(
            f"{self._admin_realm_url()}/roles/{role_name}", headers=headers
        )
        role_resp.raise_for_status()

        assign_resp = await self._http_client.post(
            f"{self._admin_realm_url()}/users/{user_id}/role-mappings/realm",
            json=[role_resp.json()],
            headers=headers,
        )
        assign_resp.raise_for_status()

    async def add_redirect_uris_to_frontend_client(self, tenant_slug: str) -> None:
        """
        Idempotently append the new tenant's exact redirect URIs and web
        origins to the frontend client (GET client → merge → PUT client).

        Pitfall #1: wildcard subdomain redirect URIs are unreliable in
        Keycloak — every tenant subdomain must be registered explicitly.
        Called as a NON-FATAL provisioning step: the caller logs and
        continues on failure.
        """
        settings = self._settings
        admin_token = await self.get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}

        list_resp = await self._http_client.get(
            f"{self._admin_realm_url()}/clients",
            params={"clientId": settings.KEYCLOAK_FRONTEND_CLIENT_ID},
            headers=headers,
        )
        list_resp.raise_for_status()
        clients: list[dict[str, Any]] = list_resp.json()
        if not clients:
            raise RuntimeError(
                f"Frontend client '{settings.KEYCLOAK_FRONTEND_CLIENT_ID}' not found."
            )

        client = clients[0]
        new_redirect = f"https://{tenant_slug}.{settings.BASE_DOMAIN}/*"
        new_origin = f"https://{tenant_slug}.{settings.BASE_DOMAIN}"

        redirect_uris = list(dict.fromkeys([*client.get("redirectUris", []), new_redirect]))
        web_origins = list(dict.fromkeys([*client.get("webOrigins", []), new_origin]))

        if (
            redirect_uris == client.get("redirectUris", [])
            and web_origins == client.get("webOrigins", [])
        ):
            return  # already registered — idempotent no-op

        client["redirectUris"] = redirect_uris
        client["webOrigins"] = web_origins
        update_resp = await self._http_client.put(
            f"{self._admin_realm_url()}/clients/{client['id']}",
            json=client,
            headers=headers,
        )
        update_resp.raise_for_status()
        logger.info("keycloak.client.redirect_uris_added", tenant_slug=tenant_slug)

    # ── User management (Phase 2 — used by user_management module) ──────────

    async def list_tenant_users(self, tenant_slug: str) -> list[dict[str, Any]]:
        """List users belonging to a tenant (filtered by tenant_slug attribute)."""
        admin_token = await self.get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await self._http_client.get(
            f"{self._admin_realm_url()}/users",
            params={"q": f"tenant_slug:{tenant_slug}", "max": 500},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_user(self, user_id: str) -> dict[str, Any]:
        admin_token = await self.get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await self._http_client.get(
            f"{self._admin_realm_url()}/users/{user_id}", headers=headers
        )
        resp.raise_for_status()
        return resp.json()

    async def update_user(self, user_id: str, payload: dict[str, Any]) -> None:
        admin_token = await self.get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await self._http_client.put(
            f"{self._admin_realm_url()}/users/{user_id}",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()

    async def delete_user(self, user_id: str) -> None:
        admin_token = await self.get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await self._http_client.delete(
            f"{self._admin_realm_url()}/users/{user_id}", headers=headers
        )
        resp.raise_for_status()

    async def reset_password(self, user_id: str, new_password: str, temporary: bool = True) -> None:
        admin_token = await self.get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = await self._http_client.put(
            f"{self._admin_realm_url()}/users/{user_id}/reset-password",
            json={"type": "password", "value": new_password, "temporary": temporary},
            headers=headers,
        )
        resp.raise_for_status()


@lru_cache
def get_keycloak_admin_service() -> KeycloakAdminService:
    return KeycloakAdminService(get_settings())
