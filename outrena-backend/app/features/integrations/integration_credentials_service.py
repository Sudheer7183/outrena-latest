"""
integration_credentials_service.py — Dual-path credential resolution.

Resolves integration API keys following one of two paths:

  Path A — platform-managed (``key_source="platform"``):
      The key lives in the configured SecretBackend (env / AWS SM / Azure KV)
      under ``{PLATFORM_INTEGRATION_KEY_PREFIX}/{integration_type}/api_key``
      (default prefix ``platform/integrations``). The tenant never sees the
      raw value; resolution happens at call time.

  Path B — tenant-managed (``key_source="tenant"``):
      The key lives Fernet-encrypted in the tenant schema's
      ``ProspectingIntegration.api_key_encrypted`` column (or
      ``LlmConfig.apiKey`` for LLM providers). The platform's
      ``ENCRYPTION_KEY`` is used to decrypt at call time.

This service is the ONLY place that translates between the two paths;
``IntegrationService`` and ``LlmConfigService`` delegate to it. The router
layer masks the resolved key before returning to the client.

Used by:
  - app.services.integration_service (ProspectingIntegration CRUD + test)
  - app.services.llm_config_service (GlobalLlmConfig reads + test)
  - app.api.routes.platform (integration-catalog endpoint)
"""
from __future__ import annotations

import os
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.secret_service import (
    decrypt_at_rest,
    encrypt_at_rest,
    get_secret_backend,
)

logger = structlog.get_logger(__name__)


# Env-driven config (the lead will consolidate into app/core/config.py +
# .env.example). Defaults match the conventions documented in the
# SURVEY-INT report §5.3 and SAAS2-INT-BE task spec.
_PLATFORM_KEY_PREFIX = os.getenv(
    "PLATFORM_INTEGRATION_KEY_PREFIX", "platform/integrations"
)
_PLATFORM_LLM_KEY_PREFIX = os.getenv(
    "PLATFORM_LLM_KEY_PREFIX", "platform/llm"
)
# Catalog of integration types the platform can manage keys for. Sourced
# from env so ops can extend without a code change (comma-separated).
_PLATFORM_INTEGRATION_TYPES = tuple(
    t.strip()
    for t in os.getenv(
        "PLATFORM_INTEGRATION_TYPES",
        "apollo,clay,zoominfo,clearbit,hunter,mailbridge,linkedin",
    ).split(",")
    if t.strip()
)
_PLATFORM_LLM_PROVIDERS = tuple(
    t.strip()
    for t in os.getenv(
        "PLATFORM_LLM_PROVIDERS",
        "openai,anthropic,azure_openai,google,cohere,mistral,groq",
    ).split(",")
    if t.strip()
)


_VALID_KEY_SOURCES = frozenset({"tenant", "platform"})


def _mask(value: str | None) -> str | None:
    """Return a masked view of an API key for logs / API responses."""
    if value is None:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


class IntegrationCredentialsService:
    """Resolves platform vs tenant credentials and encrypts/decrypts them.

    All methods are async-safe (no shared mutable state). The service is
    instantiated per request by the routers that need it.
    """

    # ── Resolution ─────────────────────────────────────────────────────────

    async def resolve_credentials(
        self,
        db: AsyncSession,
        *,
        integration_type: str,
        integration_id: str | None = None,
        provider: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve the active credentials for the given integration.

        ``integration_type`` is one of: "prospecting", "mailbridge",
        "linkedin", "llm". When ``integration_id`` is provided the row is
        loaded and ``key_source`` is read from it; otherwise the
        tenant_config.integration_mode is consulted as the default path.

        Returns ``{"api_key": str | None, "key_source": str,
        "base_url": str | None, "masked": str | None}``.

        The raw ``api_key`` is returned for service-layer use; the router
        is responsible for never serializing the raw value to the client.
        """
        integration_type = (integration_type or "").lower()
        if integration_type in ("llm", "global_llm"):
            return await self._resolve_llm_credentials(
                db, provider=provider, integration_id=integration_id
            )

        # Load the tenant-scoped integration row to determine key_source.
        key_source, stored_secret, base_url = await self._load_integration_row(
            db, integration_type, integration_id, user_id=user_id
        )
        if key_source is None:
            # No row found — fall back to env catalog for platform path.
            return {
                "api_key": None,
                "key_source": "tenant",
                "base_url": None,
                "masked": None,
            }

        if key_source == "platform":
            api_key = self._fetch_platform_key(integration_type, provider)
        else:
            api_key = self._decrypt_tenant_secret(stored_secret)
        return {
            "api_key": api_key,
            "key_source": key_source,
            "base_url": base_url,
            "masked": _mask(api_key),
        }

    # ── Tenant credential storage (encrypt + persist) ──────────────────────

    async def store_tenant_credentials(
        self,
        db: AsyncSession,
        *,
        integration_type: str,
        integration_id: str,
        credentials: dict[str, str | None],
    ) -> None:
        """Encrypt + persist secret fields on an integration row.

        ``credentials`` is a flat dict of ``{field_name: plaintext_value}``.
        For ProspectingIntegration the only secret field is ``api_key``;
        for MailBridgeConfig it is ``webhook_secret``; for LlmConfig it is
        ``api_key``. Each plaintext value is Fernet-encrypted via
        ``secret_service.encrypt_at_rest`` before being written.
        """
        integration_type = (integration_type or "").lower()
        encrypted: dict[str, str | None] = {}
        for k, v in credentials.items():
            if v is None or v == "":
                encrypted[k] = None
                continue
            try:
                encrypted[k] = encrypt_at_rest(v)
            except RuntimeError as exc:
                # ENCRYPTION_KEY missing — log and re-raise so the caller
                # surfaces a 500 instead of silently storing plaintext.
                logger.error(
                    "integration_credentials.encrypt_failed",
                    integration_type=integration_type,
                    field=k,
                    error=str(exc),
                )
                raise

        if integration_type == "prospecting":
            await db.execute(
                text(
                    "UPDATE \"ProspectingIntegration\" "
                    "SET api_key_encrypted = :enc, \"apiKey\" = NULL "
                    "WHERE id = :iid"
                ),
                {"enc": encrypted.get("api_key"), "iid": integration_id},
            )
        elif integration_type == "mailbridge":
            await db.execute(
                text(
                    "UPDATE \"MailBridgeConfig\" "
                    "SET \"webhookSecret\" = :sec WHERE id = :iid"
                ),
                {"sec": encrypted.get("webhook_secret"), "iid": integration_id},
            )
        elif integration_type in ("llm", "global_llm"):
            # GlobalLlmConfig lives in public; the row id is an int.
            try:
                gid = int(integration_id)
            except (TypeError, ValueError):
                return
            await db.execute(
                text(
                    "UPDATE public.global_llm_config "
                    "SET api_key_encrypted = :enc WHERE id = :gid"
                ),
                {"enc": encrypted.get("api_key"), "gid": gid},
            )
        await db.commit()

    # ── key_source mutation ─────────────────────────────────────────────────

    async def set_key_source(
        self,
        db: AsyncSession,
        *,
        integration_type: str,
        integration_id: str,
        key_source: str,
        new_api_key: str | None = None,
    ) -> None:
        """Switch an integration between platform-managed and tenant-managed.

        Validation rules:
          * ``key_source`` must be "platform" or "tenant".
          * Switching to "platform" clears ``api_key_encrypted`` (the
            platform key is resolved via SecretBackend at call time).
          * Switching to "tenant" requires either an existing
            ``api_key_encrypted`` value OR a ``new_api_key`` provided
            in this call (encrypted then persisted).
        """
        if key_source not in _VALID_KEY_SOURCES:
            raise ValueError(
                f"Invalid key_source '{key_source}'. "
                f"Must be one of: {sorted(_VALID_KEY_SOURCES)}."
            )
        integration_type = (integration_type or "").lower()
        if integration_type != "prospecting":
            # Only ProspectingIntegration supports the dual-path today.
            # MailBridgeConfig / LlmConfig routes do not expose this mutation.
            raise ValueError(
                f"key_source mutation not supported for integration_type "
                f"'{integration_type}'."
            )

        if key_source == "platform":
            await db.execute(
                text(
                    "UPDATE \"ProspectingIntegration\" "
                    "SET key_source = 'platform', api_key_encrypted = NULL, "
                    "\"apiKey\" = NULL WHERE id = :iid"
                ),
                {"iid": integration_id},
            )
            await db.commit()
            return

        # Switching to "tenant": require either a new key or an existing one.
        if new_api_key:
            encrypted = encrypt_at_rest(new_api_key)
            await db.execute(
                text(
                    "UPDATE \"ProspectingIntegration\" "
                    "SET key_source = 'tenant', api_key_encrypted = :enc, "
                    "\"apiKey\" = NULL WHERE id = :iid"
                ),
                {"enc": encrypted, "iid": integration_id},
            )
        else:
            row = (
                await db.execute(
                    text(
                        "SELECT api_key_encrypted FROM \"ProspectingIntegration\" "
                        "WHERE id = :iid"
                    ),
                    {"iid": integration_id},
                )
            ).fetchone()
            if row is None or not row.api_key_encrypted:
                raise ValueError(
                    "Cannot switch key_source to 'tenant' without an API key. "
                    "Provide new_api_key in the request body."
                )
            await db.execute(
                text(
                    "UPDATE \"ProspectingIntegration\" "
                    "SET key_source = 'tenant' WHERE id = :iid"
                ),
                {"iid": integration_id},
            )
        await db.commit()

    # ── Platform catalog ───────────────────────────────────────────────────

    async def list_platform_credentials_catalog(self) -> list[dict[str, Any]]:
        """Return the catalog of platform-managed integrations + LLM providers.

        For each entry the catalog reports:
          * ``integration_type`` — "prospecting" | "llm"
          * ``platform`` / ``provider`` — the integration slug
          * ``platform_key_available`` — True iff the SecretBackend returns
            a non-None value for the canonical secret name.
        """
        catalog: list[dict[str, Any]] = []
        backend = get_secret_backend()
        for plat in _PLATFORM_INTEGRATION_TYPES:
            secret_name = f"{_PLATFORM_KEY_PREFIX}/{plat}/api_key"
            try:
                available = backend.get_secret(secret_name) is not None
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "integration_credentials.platform_lookup_failed",
                    platform=plat,
                    error=str(exc),
                )
                available = False
            catalog.append(
                {
                    "integration_type": "prospecting",
                    "platform": plat,
                    "platform_key_available": available,
                    "secret_name": secret_name,
                }
            )
        for prov in _PLATFORM_LLM_PROVIDERS:
            secret_name = f"{_PLATFORM_LLM_KEY_PREFIX}/{prov}/api_key"
            try:
                available = backend.get_secret(secret_name) is not None
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "integration_credentials.platform_lookup_failed",
                    provider=prov,
                    error=str(exc),
                )
                available = False
            catalog.append(
                {
                    "integration_type": "llm",
                    "provider": prov,
                    "platform_key_available": available,
                    "secret_name": secret_name,
                }
            )
        return catalog

    # ── Internals ──────────────────────────────────────────────────────────

    async def _load_integration_row(
        self,
        db: AsyncSession,
        integration_type: str,
        integration_id: str | None,
        *,
        user_id: str | None = None,
    ) -> tuple[str | None, str | None, str | None]:
        """Load (key_source, stored_secret, base_url) for an integration.

        Returns ``(None, None, None)`` when the row is not found.
        """
        if not integration_id:
            return None, None, None
        if integration_type == "prospecting":
            row = (
                await db.execute(
                    text(
                        "SELECT key_source, api_key_encrypted, \"apiKey\", "
                        "settings FROM \"ProspectingIntegration\" WHERE id = :iid"
                    ),
                    {"iid": integration_id},
                )
            ).fetchone()
            if row is None:
                return None, None, None
            stored = row.api_key_encrypted or row.apiKey
            base_url = self._extract_base_url(row.settings)
            return (row.key_source or "tenant", stored, base_url)
        if integration_type == "mailbridge":
            row = (
                await db.execute(
                    text(
                        "SELECT \"webhookSecret\", \"baseUrl\", "
                        "COALESCE(owner_user_id::text, '') AS owner "
                        "FROM \"MailBridgeConfig\" WHERE id = :iid"
                    ),
                    {"iid": integration_id},
                )
            ).fetchone()
            if row is None:
                return None, None, None
            if user_id and row.owner and row.owner != user_id:
                # Per-user config owned by a different user — refuse.
                return None, None, None
            # MailBridge has no key_source column yet — treat as tenant-managed.
            return ("tenant", row.webhookSecret, row.baseUrl)
        if integration_type == "linkedin":
            # LinkedInConfig uses cookie auth, not apiKey — no secret to
            # resolve here, but we return a placeholder so callers can
            # short-circuit.
            return ("tenant", None, None)
        return None, None, None

    async def _resolve_llm_credentials(
        self,
        db: AsyncSession,
        *,
        provider: str | None,
        integration_id: str | None,
    ) -> dict[str, Any]:
        """Resolve credentials for an LLM call (global_llm_config first)."""
        if integration_id:
            try:
                gid = int(integration_id)
            except (TypeError, ValueError):
                gid = None
        else:
            gid = None
        if gid is not None:
            row = (
                await db.execute(
                    text(
                        "SELECT provider, api_key_encrypted, base_url, "
                        "is_active FROM public.global_llm_config WHERE id = :gid"
                    ),
                    {"gid": gid},
                )
            ).fetchone()
        else:
            # Fall back to the platform default for the provider.
            if provider is None:
                return {
                    "api_key": None,
                    "key_source": "platform",
                    "base_url": None,
                    "masked": None,
                }
            row = (
                await db.execute(
                    text(
                        "SELECT provider, api_key_encrypted, base_url, "
                        "is_active FROM public.global_llm_config "
                        "WHERE provider = :p AND is_active = true "
                        "ORDER BY is_default DESC, id ASC LIMIT 1"
                    ),
                    {"p": provider},
                )
            ).fetchone()
        if row is None:
            # No global config — try the platform secret backend as a last
            # resort so prod can run without any DB-backed LlmConfig rows.
            plat_key = self._fetch_platform_llm_key(provider)
            return {
                "api_key": plat_key,
                "key_source": "platform",
                "base_url": None,
                "masked": _mask(plat_key),
            }
        try:
            api_key = decrypt_at_rest(row.api_key_encrypted)
        except (RuntimeError, Exception):  # noqa: BLE001 — fall back to platform
            api_key = self._fetch_platform_llm_key(row.provider)
        return {
            "api_key": api_key,
            "key_source": "tenant" if row.api_key_encrypted else "platform",
            "base_url": row.base_url,
            "masked": _mask(api_key),
        }

    @staticmethod
    def _decrypt_tenant_secret(ciphertext: str | None) -> str | None:
        if not ciphertext:
            return None
        try:
            return decrypt_at_rest(ciphertext)
        except Exception as exc:  # noqa: BLE001
            # Could be a legacy plaintext value (pre-encryption). Return it
            # as-is so old rows keep working until they are re-encrypted on
            # the next UPDATE.
            logger.warning(
                "integration_credentials.decrypt_failed",
                error=str(exc),
                remediation="Re-save the integration to encrypt its key.",
            )
            return ciphertext

    @staticmethod
    def _fetch_platform_key(integration_type: str, provider: str | None) -> str | None:
        """Look up a platform-managed key via the SecretBackend."""
        backend = get_secret_backend()
        slug = provider or integration_type
        name = f"{_PLATFORM_KEY_PREFIX}/{slug}/api_key"
        try:
            return backend.get_secret(name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "integration_credentials.platform_key_fetch_failed",
                slug=slug,
                error=str(exc),
            )
            return None

    @staticmethod
    def _fetch_platform_llm_key(provider: str | None) -> str | None:
        if not provider:
            return None
        backend = get_secret_backend()
        name = f"{_PLATFORM_LLM_KEY_PREFIX}/{provider}/api_key"
        try:
            return backend.get_secret(name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "integration_credentials.platform_llm_key_fetch_failed",
                provider=provider,
                error=str(exc),
            )
            return None

    @staticmethod
    def _extract_base_url(settings_json: str | None) -> str | None:
        if not settings_json:
            return None
        try:
            import json

            data = json.loads(settings_json)
        except (json.JSONDecodeError, ValueError):
            return None
        return data.get("baseUrl") or data.get("url")


__all__ = ["IntegrationCredentialsService"]
