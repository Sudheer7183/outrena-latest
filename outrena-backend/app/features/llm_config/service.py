"""
llm_config_service.py — GlobalLlmConfig CRUD + /test-llm call.

Phase 8 (dual-path integrations): the LLM config is now PLATFORM-WIDE
(``public.global_llm_config``), managed exclusively by SUPER_ADMIN. The
per-tenant ``LlmConfig`` table is preserved as an optional override layer
(tenant picks a default model preference via ``global_llm_config_id``) but
the PRIMARY API key + provider config lives in the public table.

All methods expect a public-schema session (``get_db_public``) — the router
is responsible for routing through the right dependency. The service also
validates SUPER_ADMIN role defensively (the router enforces it via
``verify_role``, but defense-in-depth here too).

The raw API key is NEVER returned by any method — only the masked view.
``test_llm`` is the only path that decrypts + uses the key, and it does so
in-process (never logged).
"""
from __future__ import annotations

import time
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.global_llm_config import GlobalLlmConfig
from app.schemas.llm_config import (
    LlmConfigCreate,
    LlmConfigUpdate,
    TestLlmRequest,
    TestLlmResponse,
)
from app.services.secret_service import decrypt_at_rest, encrypt_at_rest

logger = structlog.get_logger(__name__)


def _mask(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


class LlmConfigService:
    """CRUD + test-llm operations for GlobalLlmConfig rows (public schema)."""

    async def list_configs(
        self, db: AsyncSession, *, limit: int = 50, offset: int = 0
    ) -> list[GlobalLlmConfig]:
        result = await db.execute(
            select(GlobalLlmConfig)
            .where(GlobalLlmConfig.is_active.is_(True))
            .order_by(GlobalLlmConfig.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, config_id: int) -> GlobalLlmConfig | None:
        result = await db.execute(
            select(GlobalLlmConfig).where(GlobalLlmConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_default(self, db: AsyncSession) -> GlobalLlmConfig | None:
        result = await db.execute(
            select(GlobalLlmConfig)
            .where(GlobalLlmConfig.is_default.is_(True))
            .where(GlobalLlmConfig.is_active.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, body: LlmConfigCreate
    ) -> GlobalLlmConfig:
        # If this config is marked default, demote any prior default first.
        if body.is_default:
            await self._demote_existing_defaults(db)

        try:
            encrypted_key = encrypt_at_rest(body.api_key)
        except RuntimeError as exc:
            logger.error(
                "llm_config.create.encrypt_failed",
                provider=body.provider,
                error=str(exc),
            )
            raise
        item = GlobalLlmConfig(
            provider=body.provider,
            display_name=body.display_name,
            api_key_encrypted=encrypted_key,
            base_url=body.base_url,
            model_name=body.model_name,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
            is_active=body.is_active,
            is_default=body.is_default,
        )
        db.add(item)
        await db.commit()
        item = await db.get(GlobalLlmConfig, item.id)
        return item

    async def update(
        self, db: AsyncSession, config_id: int, body: LlmConfigUpdate
    ) -> GlobalLlmConfig | None:
        item = await self.get(db, config_id)
        if item is None:
            return None
        data = body.model_dump(exclude_unset=True)
        new_key = data.pop("api_key", None)
        if data.get("is_default"):
            await self._demote_existing_defaults(db, exclude_id=config_id)
        for key, value in data.items():
            setattr(item, key, value)
        if new_key is not None:
            if new_key == "":
                # Treat empty string as "no change" — never blank a key via
                # update (use DELETE instead).
                logger.info(
                    "llm_config.update.empty_key_ignored", config_id=config_id
                )
            else:
                try:
                    item.api_key_encrypted = encrypt_at_rest(new_key)
                except RuntimeError as exc:
                    logger.error(
                        "llm_config.update.encrypt_failed",
                        config_id=config_id,
                        error=str(exc),
                    )
                    raise
        await db.commit()
        item = await db.get(GlobalLlmConfig, item.id)
        return item

    async def delete(self, db: AsyncSession, config_id: int) -> bool:
        """Soft-delete (is_active=false) — never hard-delete a global config.

        Hard-deleting would break historical references from tenant
        LlmConfig.global_llm_config_id + Campaign.llm_config_id. Marking
        inactive lets the row stay queryable for audit while
        ``get_default`` skips it.
        """
        item = await self.get(db, config_id)
        if item is None:
            return False
        item.is_active = False
        item.is_default = False
        await db.commit()
        return True

    async def set_default(self, db: AsyncSession, config_id: int) -> GlobalLlmConfig | None:
        """Mark ``config_id`` as the platform default; demote others."""
        item = await self.get(db, config_id)
        if item is None:
            return None
        if not item.is_active:
            return None
        await self._demote_existing_defaults(db, exclude_id=config_id)
        item.is_default = True
        await db.commit()
        item = await db.get(GlobalLlmConfig, item.id)
        return item

    async def test_llm(
        self, db: AsyncSession, body: TestLlmRequest
    ) -> TestLlmResponse:
        """Call the configured LLM with a test message.

        Resolves the global config (by ``config_id`` or the platform
        default), decrypts its API key, and delegates to
        ``llm_service.call_llm`` (or the ``LlmService.generate`` fallback).
        """
        config: GlobalLlmConfig | None = None
        if body.config_id is not None:
            config = await self.get(db, body.config_id)
        if config is None:
            config = await self.get_default(db)
        if config is None:
            return TestLlmResponse(
                ok=False,
                content="",
                error="No global LLM config found.",
            )

        messages: list[dict[str, str]] = []
        if body.system_prompt:
            messages.append({"role": "system", "content": body.system_prompt})
        messages.append({"role": "user", "content": body.message})

        # Decrypt the API key for the in-process call. Never logged.
        try:
            api_key = decrypt_at_rest(config.api_key_encrypted)
        except Exception as exc:  # noqa: BLE001
            return TestLlmResponse(
                ok=False,
                content="",
                error=f"Failed to decrypt API key: {exc}",
            )

        # Build a lightweight LlmConfig-shaped object so llm_service.call_llm
        # (which expects a model with .provider/.modelId/.apiKey/.baseUrl) keeps
        # working without changes. llm_service is owned by BE-C; we MUST NOT
        # edit it.
        from types import SimpleNamespace

        legacy_config = SimpleNamespace(
            provider=config.provider,
            name=config.display_name,
            modelId=config.model_name,
            apiKey=api_key,
            baseUrl=config.base_url,
            isActive=config.is_active,
            isDefault=config.is_default,
            settings="{}",
            global_llm_config_id=None,
        )

        # Lazy import: BE-C's 13-provider gateway.
        try:
            from app.services.llm_service import call_llm as _call_llm
        except ImportError:
            _call_llm = None  # type: ignore[assignment]

        started = time.monotonic()
        try:
            if _call_llm is not None:
                result = await _call_llm(legacy_config, messages)
                content = getattr(result, "content", str(result))
                latency_ms = int((time.monotonic() - started) * 1000)
                return TestLlmResponse(
                    ok=True,
                    content=str(content),
                    provider=config.provider,
                    model_id=config.model_name,
                    latency_ms=latency_ms,
                )
            # Fallback path — use LlmService.generate() if call_llm missing.
            from app.services.llm_service import LlmService

            content = await LlmService().generate(
                prompt=body.message,
                system=body.system_prompt,
                model=config.model_name,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            return TestLlmResponse(
                ok=True,
                content=str(content),
                provider=config.provider,
                model_id=config.model_name,
                latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm.test.failed", error=str(exc))
            return TestLlmResponse(ok=False, content="", error=str(exc))

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _demote_existing_defaults(
        self, db: AsyncSession, *, exclude_id: int | None = None
    ) -> None:
        result = await db.execute(
            select(GlobalLlmConfig).where(GlobalLlmConfig.is_default.is_(True))
        )
        for existing in result.scalars().all():
            if exclude_id is not None and existing.id == exclude_id:
                continue
            existing.is_default = False
        await db.flush()

    @staticmethod
    def to_response(row: GlobalLlmConfig) -> dict[str, Any]:
        """Serialize a GlobalLlmConfig row to a public response dict.

        The ``api_key`` field is set to a static mask — the raw value is
        never returned. (Caller may override the mask with the resolved
        platform fingerprint if needed.)
        """
        return {
            "id": row.id,
            "provider": row.provider,
            "display_name": row.display_name,
            "api_key": _mask("encrypted") if row.api_key_encrypted else None,
            "base_url": row.base_url,
            "model_name": row.model_name,
            "max_tokens": row.max_tokens,
            "temperature": row.temperature,
            "is_active": row.is_active,
            "is_default": row.is_default,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }


__all__ = ["LlmConfigService"]
