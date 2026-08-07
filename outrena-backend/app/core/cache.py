"""
cache.py — Redis access with enforced tenant key namespacing.

Reference model Section 8: every tenant-scoped cache key is prefixed with the
tenant schema name; platform-wide keys (JWKS, IP rate limits) are not.

This module is the ONLY place cache keys are constructed. Enforcing the
convention in one utility prevents the "missing key segment" class of bug
that is indistinguishable from a tenant-isolation failure.
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Lazily-initialized module-level Redis client (async)."""
    global _client
    if _client is None:
        _client = redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    return _client


def tenant_key(schema_name: str, *segments: str) -> str:
    """
    Build a tenant-scoped cache key: '{schema_name}:{seg1}:{seg2}...'.

    EVERY dimension the cached payload varies by MUST appear as a segment.
    """
    if not schema_name:
        raise ValueError("tenant_key requires a non-empty schema_name")
    return ":".join([schema_name, *segments])


def platform_key(*segments: str) -> str:
    """Build a platform-wide cache key (no tenant prefix), e.g. 'jwks:keycloak'."""
    return ":".join(segments)


async def get_json(key: str) -> Any | None:
    raw = await get_redis().get(key)
    return json.loads(raw) if raw is not None else None


async def set_json(key: str, value: Any, ttl_seconds: int) -> None:
    await get_redis().set(key, json.dumps(value), ex=ttl_seconds)


async def delete_key(key: str) -> None:
    await get_redis().delete(key)


async def invalidate_tenant(schema_name: str) -> int:
    """
    Delete every cache entry for one tenant (prefix scan).
    Called on tenant-level configuration changes. Returns keys deleted.
    """
    client = get_redis()
    deleted = 0
    async for key in client.scan_iter(match=f"{schema_name}:*"):
        await client.delete(key)
        deleted += 1
    return deleted
