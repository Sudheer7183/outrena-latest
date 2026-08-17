"""
tenant_service.py — Per-tenant LlmConfig CRUD + test-llm.

FIX: Replaces the global LlmConfigService (which read/wrote
public.global_llm_config with no tenant_id filter) with this service
that targets the per-tenant LlmConfig table (tenant schema).

The tenant schema is set by get_db() via SET search_path, so all queries
here are automatically scoped to the calling tenant — no tenant_id column
or filter needed.

Field mapping (API snake_case  ↔  model camelCase):
  api_key       ↔  apiKey
  model_name    ↔  modelId
  display_name  ↔  name
  is_active     ↔  isActive
  is_default    ↔  isDefault
  base_url      ↔  baseUrl
"""
from __future__ import annotations

import time
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_models import LlmConfig
from app.schemas.llm_config import (
    LlmConfigCreate,
    LlmConfigResponse,
    LlmConfigUpdate,
    TestLlmRequest,
    TestLlmResponse,
)

logger = structlog.get_logger(__name__)


def _mask(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


class TenantLlmConfigService:
    """CRUD + test-llm for the per-tenant LlmConfig table."""

    async def list_configs(
        self, db: AsyncSession, *, limit: int = 50, offset: int = 0
    ) -> list[LlmConfig]:
        result = await db.execute(
            select(LlmConfig)
            .where(LlmConfig.isActive.is_(True))
            .order_by(LlmConfig.createdAt.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, config_id: str) -> LlmConfig | None:
        result = await db.execute(
            select(LlmConfig).where(LlmConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_default(self, db: AsyncSession) -> LlmConfig | None:
        result = await db.execute(
            select(LlmConfig)
            .where(LlmConfig.isDefault.is_(True))
            .where(LlmConfig.isActive.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, body: LlmConfigCreate) -> LlmConfig:
        if body.is_default:
            await self._demote_existing_defaults(db)

        # Encrypt the API key if one was provided.
        encrypted_key: str | None = None
        if body.api_key:
            try:
                from app.services.secret_service import encrypt_at_rest
                encrypted_key = encrypt_at_rest(body.api_key)
            except RuntimeError as exc:
                logger.error("tenant_llm.create.encrypt_failed", error=str(exc))
                raise

        item = LlmConfig(
            name=body.display_name or f"{body.provider}/{body.model_name}",
            provider=body.provider,
            modelId=body.model_name,
            # Store encrypted key in apiKey column (same Fernet ciphertext).
            # decrypt_at_rest() is the inverse in llm_service.
            apiKey=encrypted_key,
            baseUrl=body.base_url,
            isDefault=body.is_default,
            isActive=body.is_active,
            settings={},
            modelTier="standard",
        )
        db.add(item)
        await db.commit()
        # Refresh via fresh SELECT to avoid db.refresh() after commit
        # (search_path would be lost on re-pooled connection).
        refreshed = await db.get(LlmConfig, item.id)
        return refreshed  # type: ignore[return-value]

    async def update(
        self, db: AsyncSession, config_id: str, body: LlmConfigUpdate
    ) -> LlmConfig | None:
        item = await self.get(db, config_id)
        if item is None:
            return None

        data = body.model_dump(exclude_unset=True)
        new_api_key = data.pop("api_key", None)
        new_model_name = data.pop("model_name", None)
        new_display_name = data.pop("display_name", None)
        new_base_url = data.pop("base_url", None)
        new_is_active = data.pop("is_active", None)
        new_is_default = data.pop("is_default", None)
        new_max_tokens = data.pop("max_tokens", None)
        new_temperature = data.pop("temperature", None)

        if new_is_default:
            await self._demote_existing_defaults(db, exclude_id=config_id)

        if new_display_name is not None:
            item.name = new_display_name
        if new_model_name is not None:
            item.modelId = new_model_name
        if new_base_url is not None:
            item.baseUrl = new_base_url
        if new_is_active is not None:
            item.isActive = new_is_active
        if new_is_default is not None:
            item.isDefault = new_is_default
        if new_max_tokens is not None:
            settings = dict(item.settings or {})
            settings["max_tokens"] = new_max_tokens
            item.settings = settings
        if new_temperature is not None:
            settings = dict(item.settings or {})
            settings["temperature"] = new_temperature
            item.settings = settings

        if new_api_key:
            try:
                from app.services.secret_service import encrypt_at_rest
                item.apiKey = encrypt_at_rest(new_api_key)
            except RuntimeError as exc:
                logger.error("tenant_llm.update.encrypt_failed", config_id=config_id, error=str(exc))
                raise

        await db.commit()
        refreshed = await db.get(LlmConfig, item.id)
        return refreshed  # type: ignore[return-value]

    async def delete(self, db: AsyncSession, config_id: str) -> bool:
        """Soft-delete: set isActive=False. Never hard-delete."""
        item = await self.get(db, config_id)
        if item is None:
            return False
        item.isActive = False
        item.isDefault = False
        await db.commit()
        return True

    async def set_default(
        self, db: AsyncSession, config_id: str
    ) -> LlmConfig | None:
        item = await self.get(db, config_id)
        if item is None or not item.isActive:
            return None
        await self._demote_existing_defaults(db, exclude_id=config_id)
        item.isDefault = True
        await db.commit()
        refreshed = await db.get(LlmConfig, item.id)
        return refreshed  # type: ignore[return-value]

    async def test_llm(
        self, db: AsyncSession, body: TestLlmRequest
    ) -> TestLlmResponse:
        """Test a tenant LLM config by calling its provider."""
        config: LlmConfig | None = None
        if body.config_id is not None:
            config = await self.get(db, str(body.config_id))
        if config is None:
            config = await self.get_default(db)
        if config is None:
            return TestLlmResponse(
                ok=False, content="", error="No LLM config found for this tenant."
            )
        if not config.apiKey:
            return TestLlmResponse(
                ok=False, content="", error="No API key stored for this config."
            )

        # Decrypt the stored key.
        try:
            from app.services.secret_service import decrypt_at_rest
            api_key = decrypt_at_rest(config.apiKey)
        except Exception as exc:  # noqa: BLE001
            return TestLlmResponse(
                ok=False, content="", error=f"Failed to decrypt API key: {exc}"
            )

        messages: list[dict[str, str]] = []
        if body.system_prompt:
            messages.append({"role": "system", "content": body.system_prompt})
        messages.append({"role": "user", "content": body.message})

        from types import SimpleNamespace

        legacy_config = SimpleNamespace(
            provider=config.provider,
            name=config.name,
            modelId=config.modelId,
            apiKey=api_key,
            baseUrl=config.baseUrl,
            isActive=config.isActive,
            isDefault=config.isDefault,
            settings="{}",
            global_llm_config_id=None,
        )

        try:
            from app.services.llm_service import call_llm as _call_llm
        except ImportError:
            _call_llm = None  # type: ignore[assignment]

        started = time.monotonic()
        try:
            if _call_llm is not None:
                result = await _call_llm(legacy_config, messages)
                content = getattr(result, "content", str(result))
            else:
                from app.services.llm_service import LlmService
                content = await LlmService().generate(
                    prompt=body.message,
                    system=body.system_prompt,
                    model=config.modelId,
                )
            latency_ms = int((time.monotonic() - started) * 1000)
            return TestLlmResponse(
                ok=True,
                content=str(content),
                provider=config.provider,
                model_id=config.modelId,
                latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("tenant_llm.test.failed", error=str(exc))
            return TestLlmResponse(ok=False, content="", error=str(exc))

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _demote_existing_defaults(
        self, db: AsyncSession, *, exclude_id: str | None = None
    ) -> None:
        result = await db.execute(
            select(LlmConfig).where(LlmConfig.isDefault.is_(True))
        )
        for existing in result.scalars().all():
            if exclude_id is not None and existing.id == exclude_id:
                continue
            existing.isDefault = False
        await db.flush()

    @staticmethod
    def to_response(row: LlmConfig) -> LlmConfigResponse:
        """Map per-tenant LlmConfig row → LlmConfigResponse (snake_case API shape).

        LlmConfig.settings is declared PG_JSON but existing rows may have
        the value stored as a raw JSON string (e.g. '{}') when the column was
        written before SQLAlchemy's JSON type-coercion was active.  Parse
        defensively so both shapes work.
        """
        from datetime import datetime, timezone
        import json as _json

        raw_settings = row.settings
        if isinstance(raw_settings, str):
            try:
                settings: dict = _json.loads(raw_settings)
            except (ValueError, TypeError):
                settings = {}
        elif isinstance(raw_settings, dict):
            settings = raw_settings
        else:
            settings = {}

        return LlmConfigResponse(
            id=str(row.id),
            provider=row.provider,
            display_name=row.name,
            api_key=_mask("set") if row.apiKey else None,
            base_url=row.baseUrl,
            model_name=row.modelId,
            max_tokens=int(settings.get("max_tokens", 2048)),
            temperature=float(settings.get("temperature", 0.7)),
            is_active=bool(row.isActive),
            is_default=bool(row.isDefault),
            created_at=getattr(row, "createdAt", None) or datetime.now(timezone.utc),
            updated_at=getattr(row, "updatedAt", None) or datetime.now(timezone.utc),
        )



__all__ = ["TenantLlmConfigService"]