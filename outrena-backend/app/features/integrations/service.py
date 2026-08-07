"""integration_service.py — ProspectingIntegration CRUD + /test connectivity.

Phase 8 (dual-path integrations): all create/update/get operations now
delegate secret handling to ``IntegrationCredentialsService``:

  * On create — if ``key_source="tenant"`` (default), the provided
    ``apiKey`` is Fernet-encrypted via ``encrypt_at_rest`` and stored in
    ``api_key_encrypted``; the legacy ``apiKey`` column is set to NULL.
    If ``key_source="platform"`` no key is stored on the row.
  * On get — the response carries ``key_source`` + a masked view of the
    resolved key (never the raw value).
  * On update — re-encrypts if a new ``apiKey`` is provided.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_models import ProspectingIntegration
from app.schemas.integrations import (
    IntegrationCreate,
    IntegrationTestRequest,
    IntegrationTestResponse,
    IntegrationUpdate,
)
from app.features.integrations.integration_credentials_service import (
    IntegrationCredentialsService,
)
from app.services.secret_service import encrypt_at_rest

logger = structlog.get_logger(__name__)
_credentials_service = IntegrationCredentialsService()


class IntegrationService:
    """CRUD + connectivity test for ProspectingIntegration rows."""

    async def list_integrations(
        self, db: AsyncSession, *, limit: int = 50, offset: int = 0
    ) -> list[ProspectingIntegration]:
        result = await db.execute(
            select(ProspectingIntegration).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def get(
        self, db: AsyncSession, integration_id: str
    ) -> ProspectingIntegration | None:
        result = await db.execute(
            select(ProspectingIntegration).where(
                ProspectingIntegration.id == integration_id
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, body: IntegrationCreate
    ) -> ProspectingIntegration:
        # Normalize key_source (default "tenant" for backward compat).
        key_source = getattr(body, "key_source", None) or "tenant"
        api_key_plain = body.apiKey
        api_key_encrypted: str | None = None
        if key_source == "tenant" and api_key_plain:
            try:
                api_key_encrypted = encrypt_at_rest(api_key_plain)
            except RuntimeError as exc:
                logger.error(
                    "integration.create.encrypt_failed",
                    platform=body.platform,
                    error=str(exc),
                )
                raise
        # Persist: never store plaintext in the legacy apiKey column for
        # newly-created rows.
        item = ProspectingIntegration(
            platform=body.platform,
            name=body.name,
            apiKey=None,
            api_key_encrypted=api_key_encrypted if key_source == "tenant" else None,
            key_source=key_source,
            isActive=body.isActive,
            settings=body.settings,
        )
        db.add(item)
        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            exc_str = str(exc).lower()
            if "unique" in exc_str or "duplicate" in exc_str or "uniqueviolation" in exc_str:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=409,
                    detail=f"An integration for platform '{body.platform}' already exists.",
                ) from exc
            raise
        item = await db.get(ProspectingIntegration, item.id)
        return item

    async def update(
        self, db: AsyncSession, integration_id: str, body: IntegrationUpdate
    ) -> ProspectingIntegration | None:
        item = await self.get(db, integration_id)
        if item is None:
            return None
        data = body.model_dump(exclude_unset=True)
        # Handle key_source mutation + apiKey re-encryption as one atomic op.
        new_key_source = data.pop("key_source", None)
        new_api_key = data.pop("apiKey", None)
        if new_key_source is not None:
            if new_key_source not in ("tenant", "platform"):
                raise ValueError(
                    f"Invalid key_source '{new_key_source}'. "
                    "Must be 'tenant' or 'platform'."
                )
            item.key_source = new_key_source
            if new_key_source == "platform":
                # Clear any tenant-side stored key.
                item.api_key_encrypted = None
                item.apiKey = None
        if new_api_key is not None:
            if item.key_source == "tenant":
                if new_api_key == "":
                    # Empty string => clear.
                    item.api_key_encrypted = None
                    item.apiKey = None
                else:
                    try:
                        item.api_key_encrypted = encrypt_at_rest(new_api_key)
                    except RuntimeError as exc:
                        logger.error(
                            "integration.update.encrypt_failed",
                            integration_id=integration_id,
                            error=str(exc),
                        )
                        raise
                    item.apiKey = None
            else:
                # Platform-managed — ignore client-supplied key (it would
                # never be used). Log so the caller knows the write was a
                # no-op.
                logger.info(
                    "integration.update.ignored_platform_key",
                    integration_id=integration_id,
                )
        # Apply remaining non-secret fields.
        for key, value in data.items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(ProspectingIntegration, item.id)
        return item

    async def delete(self, db: AsyncSession, integration_id: str) -> bool:
        item = await self.get(db, integration_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def test(
        self, db: AsyncSession, body: IntegrationTestRequest
    ) -> IntegrationTestResponse:
        """Best-effort connectivity probe — records the result on the row."""
        import time

        item = await self.get(db, body.integrationId)
        if item is None:
            return IntegrationTestResponse(
                integrationId=body.integrationId,
                ok=False,
                detail="Integration not found.",
            )

        # Resolve the active credential via the dual-path service so the
        # test exercises the same code path as production callers.
        resolved = await _credentials_service.resolve_credentials(
            db,
            integration_type="prospecting",
            integration_id=item.id,
            provider=item.platform,
        )
        api_key = resolved.get("api_key")

        # Heuristic: if the integration has a baseUrl in settings JSON, ping it.
        url: str | None = None
        try:
            settings = json.loads(item.settings or "{}")
            url = settings.get("baseUrl") or settings.get("url")
        except (json.JSONDecodeError, ValueError):
            pass

        ok = False
        latency_ms: int | None = None
        detail = "No URL configured."

        # ── Provider-specific test endpoints ──────────────────────────────
        async def _probe(test_url: str, *, headers: dict | None = None) -> tuple[bool, int, str]:
            """HTTP-GET the test_url; return (ok, latency_ms, detail)."""
            started = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(test_url, headers=headers or {})
                ms = int((time.monotonic() - started) * 1000)
                is_ok = resp.status_code < 400
                msg = f"HTTP {resp.status_code} in {ms} ms."
                return is_ok, ms, msg
            except Exception as exc:  # noqa: BLE001
                return False, 0, f"Connectivity test failed: {exc}"

        provider = (item.platform or "").lower()
        if provider == "apollo" and api_key:
            ok, latency_ms, detail = await _probe(
                "https://api.apollo.io/v1/users/search",
                headers={"Cache-Control": "no-cache", "Content-Type": "application/json"},
            )
        elif provider == "apollo-api" and api_key:
            ok, latency_ms, detail = await _probe(
                "https://api.apollo.io/v1/people/search",
                headers={"Cache-Control": "no-cache", "Content-Type": "application/json"},
            )
        elif provider == "hunter" and api_key:
            ok, latency_ms, detail = await _probe(
                f"https://api.hunter.io/v2/account?api_key={api_key}",
            )
        elif provider == "clearbit" and api_key:
            ok, latency_ms, detail = await _probe(
                "https://company.clearbit.com/v1/companies/find?domain=example.com",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        elif provider == "zoominfo" and api_key:
            # ZoomInfo has no public unauthed health endpoint; validate key
            # format and reachability of the API domain.
            if len(api_key) < 10:
                detail = "API key too short — likely invalid."
            else:
                ok, latency_ms, detail = await _probe(
                    "https://api.zoominfo.com",
                )
        elif provider == "snov" and api_key:
            ok, latency_ms, detail = await _probe(
                "https://api.snov.io/v1/get-domain-emails-count?domain=example.com",
            )
        elif provider == "sendgrid" and api_key:
            ok, latency_ms, detail = await _probe(
                "https://api.sendgrid.com/v3/user/account",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        elif provider == "postmark" and api_key:
            ok, latency_ms, detail = await _probe(
                "https://api.postmarkapp.com/server",
                headers={"X-Postmark-Server-Token": api_key},
            )
        elif url:
            # Generic URL probe (baseUrl from settings)
            ok, latency_ms, detail = await _probe(url)
        elif api_key:
            # Unknown provider with an API key but no test URL — validate
            # that the key is at least plausibly formatted (≥10 chars,
            # not a placeholder).
            if len(api_key) < 10 or api_key.lower().startswith(("xxx", "placeholder", "test")):
                detail = "API key appears invalid (too short or placeholder)."
            else:
                ok = True
                detail = (
                    f"API key present (key_source={item.key_source}). "
                    "No test endpoint available for this provider."
                )
        elif item.key_source == "platform":
            detail = (
                "No platform key resolved for "
                f"platform={item.platform!r} (check SecretBackend)."
            )

        item.lastTestedAt = datetime.now(timezone.utc)
        item.lastTestResult = "ok" if ok else "failed"
        await db.commit()

        return IntegrationTestResponse(
            integrationId=item.id,
            ok=ok,
            latencyMs=latency_ms,
            detail=detail,
        )

    async def credentials_test(
        self, db: AsyncSession, integration_id: str
    ) -> IntegrationTestResponse:
        """Resolve + verify credentials for an integration (no upstream ping).

        Used by ``GET /prospecting-integrations/{id}/credentials-test``.
        Reports whether the resolved credential is non-None and (when
        tenant-managed) decryptable.
        """
        item = await self.get(db, integration_id)
        if item is None:
            return IntegrationTestResponse(
                integrationId=integration_id,
                ok=False,
                detail="Integration not found.",
            )
        resolved = await _credentials_service.resolve_credentials(
            db,
            integration_type="prospecting",
            integration_id=item.id,
            provider=item.platform,
        )
        api_key = resolved.get("api_key")
        ok = bool(api_key)
        detail = (
            f"key_source={resolved.get('key_source')}; "
            f"key={'present' if ok else 'missing'}"
        )
        return IntegrationTestResponse(
            integrationId=item.id,
            ok=ok,
            detail=detail,
        )


__all__ = ["IntegrationService"]
