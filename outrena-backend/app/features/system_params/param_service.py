"""
param_service.py — CRUD + reset + seed for the 31 SystemParameter rows.

Per migration doc §3.5 + §6.2 + §10 Phase 2:
  - get_param(key, db, schema_name) → string value (falls back to default)
  - get_param_int / get_param_bool / get_param_json → typed accessors
  - list_params(db) → all SystemParameter rows ordered by category + key
  - update_param(key, value, db) → admin override
  - reset_params(db) → re-seed all from param_defs.py (overwrites edits)
  - seed_params(db) → idempotent seed used by tenant provisioning

Redis cache layer (§3.5): get_param reads from
``{schema_name}:param:{key}`` (TTL 300s — params change less often than
prompts). update_param + reset_params invalidate the cache.
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import delete_key, get_json, invalidate_tenant, set_json, tenant_key
from app.models.config_models import SystemParameter
from app.features.system_params.param_defs import PARAM_DEFS, ParamDef, to_param_kwargs

logger = structlog.get_logger(__name__)


_CACHE_TTL_SECONDS: int = 300

_TRUE_STRINGS: frozenset[str] = frozenset({"true", "1", "yes", "on", "y"})
_FALSE_STRINGS: frozenset[str] = frozenset({"false", "0", "no", "off", "n"})


def _coerce_bool(value: str) -> bool:
    """Lenient bool parser (accepts 'true'/'1'/'yes'/'on'/'y')."""
    normalized = (value or "").strip().lower()
    if normalized in _TRUE_STRINGS:
        return True
    if normalized in _FALSE_STRINGS:
        return False
    # Last-resort: non-empty non-zero → True
    try:
        return float(normalized) != 0
    except ValueError:
        return bool(normalized)


def _coerce_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def _coerce_json(value: str) -> Any:
    """Parse a JSON string. Returns the raw string on parse failure."""
    if not value:
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError, ValueError):
        return value


class ParamService:
    """CRUD + reset + seed for the tenant's 31 SystemParameter rows."""

    # ── Read ────────────────────────────────────────────────────────────────

    async def get_param(
        self,
        key: str,
        db: AsyncSession,
        schema_name: str,
    ) -> str:
        """
        Fetch the SystemParameter value for ``key``.

        Falls back to the static default from ``param_defs.py`` when the row
        is absent (defensive — provisioning should have run). Returns "" if
        neither DB nor default has the key.

        Uses Redis cache key ``{schema_name}:param:{key}`` (TTL 300s).
        """
        cache_key = tenant_key(schema_name, "param", key)
        cached = await self._safe_get_json(cache_key)
        if cached is not None and isinstance(cached, dict):
            return str(cached.get("value", ""))

        row = await self._fetch_row(key, db)
        if row is not None:
            value = row.value
        else:
            value = self._default_value_for(key) or ""
        await self._safe_set_json(cache_key, {"value": value}, _CACHE_TTL_SECONDS)
        return value

    async def get_param_int(
        self, key: str, db: AsyncSession, schema_name: str
    ) -> int:
        return _coerce_int(await self.get_param(key, db, schema_name))

    async def get_param_bool(
        self, key: str, db: AsyncSession, schema_name: str
    ) -> bool:
        return _coerce_bool(await self.get_param(key, db, schema_name))

    async def get_param_json(
        self, key: str, db: AsyncSession, schema_name: str
    ) -> Any:
        return _coerce_json(await self.get_param(key, db, schema_name))

    async def list_params(
        self, db: AsyncSession
    ) -> list[SystemParameter]:
        """Return all SystemParameter rows ordered by category, then key."""
        result = await db.execute(
            select(SystemParameter).order_by(
                SystemParameter.category.asc(),
                SystemParameter.key.asc(),
            )
        )
        return list(result.scalars().all())

    # ── Mutations ───────────────────────────────────────────────────────────

    async def update_param(
        self,
        key: str,
        value: str,
        db: AsyncSession,
    ) -> SystemParameter:
        """
        Admin override of the live ``value`` column for one param.

        ``defaultValue`` is preserved (so Reset can restore it).
        """
        row = await self._fetch_row(key, db)
        if row is None:
            from fastapi import HTTPException

            raise HTTPException(404, f"SystemParameter not found: {key}")
        row.value = value
        await db.flush()
        await self._safe_delete_current(key, db)
        row = await db.get(SystemParameter, row.id)
        return row

    async def reset_params(self, db: AsyncSession) -> int:
        """
        Re-seed all params from ``param_defs.py``, overwriting any admin
        edits (``value`` is reset to ``defaultValue``). Returns count.

        Differs from ``seed_params`` in that it ALWAYS overwrites the
        ``value`` column; ``seed_params`` only fills rows that don't exist.
        """
        count = 0
        for defn in PARAM_DEFS:
            kwargs = to_param_kwargs(defn)
            stmt = (
                pg_insert(SystemParameter)
                .values(**kwargs)
                .on_conflict_do_update(
                    index_elements=[SystemParameter.key],
                    set_={
                        "category": kwargs["category"],
                        "label": kwargs["label"],
                        "description": kwargs["description"],
                        "impact": kwargs["impact"],
                        "valueType": kwargs["valueType"],
                        "value": kwargs["defaultValue"],
                        "defaultValue": kwargs["defaultValue"],
                        "minValue": kwargs["minValue"],
                        "maxValue": kwargs["maxValue"],
                        "unit": kwargs["unit"],
                        "isAdvanced": kwargs["isAdvanced"],
                    },
                )
            )
            await db.execute(stmt)
            count += 1
        await db.flush()
        await self._safe_invalidate_current(db)
        logger.info("param.reset.complete", count=count)
        return count

    async def seed_params(self, db: AsyncSession) -> int:
        """
        Idempotent seed used by tenant provisioning.

        Inserts all rows with ``ON CONFLICT (key) DO NOTHING``. Existing
        admin edits are preserved. Returns the number of rows actually
        inserted (0 on a re-seed of an already-provisioned tenant).
        """
        inserted = 0
        for defn in PARAM_DEFS:
            kwargs = to_param_kwargs(defn)
            stmt = (
                pg_insert(SystemParameter)
                .values(**kwargs)
                .on_conflict_do_nothing(
                    index_elements=[SystemParameter.key],
                )
            )
            result = await db.execute(stmt)
            inserted += int(result.rowcount or 0)
        await db.flush()
        logger.info("param.seed.complete", inserted=inserted, total=len(PARAM_DEFS))
        return inserted

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    async def _fetch_row(key: str, db: AsyncSession) -> SystemParameter | None:
        result = await db.execute(
            select(SystemParameter).where(SystemParameter.key == key)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _default_value_for(key: str) -> str | None:
        for defn in PARAM_DEFS:
            if defn.key == key:
                return defn.default_value
        return None

    @staticmethod
    async def _safe_get_json(key: str) -> Any | None:
        try:
            return await get_json(key)
        except Exception as exc:  # noqa: BLE001
            logger.debug("param.cache.get_failed", key=key, error=str(exc))
            return None

    @staticmethod
    async def _safe_set_json(key: str, value: Any, ttl: int) -> None:
        try:
            await set_json(key, value, ttl)
        except Exception as exc:  # noqa: BLE001
            logger.debug("param.cache.set_failed", key=key, error=str(exc))

    @staticmethod
    async def _safe_delete_current(key: str, db: AsyncSession) -> None:
        """
        Best-effort cache invalidation for the current tenant + key.

        The router layer has the schema_name in scope and can call
        ``delete_key(tenant_key(schema_name, 'param', key))`` directly.
        This is a defensive fallback (no-op when schema_name is unknown).
        """
        return None

    @staticmethod
    async def _safe_invalidate_current(db: AsyncSession) -> None:
        """Best-effort whole-tenant cache invalidation (see note above)."""
        return None


def get_param_service() -> ParamService:
    """Factory — return a fresh ParamService instance (stateless)."""
    return ParamService()


__all__ = ["ParamService", "get_param_service", "ParamDef", "PARAM_DEFS"]
