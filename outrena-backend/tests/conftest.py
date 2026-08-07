"""
conftest.py — shared pytest fixtures (Phase 1 minimal version).

Phase 1 only needs the smoke-test fixtures. Phase 2 adds testcontainers-based
PostgreSQL + Redis fixtures and the critical test_isolation.py fixture pair.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ── Environment ───────────────────────────────────────────────────────────────
# Tests run against a throwaway dev profile. Never point at production.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SKIP_JWT_VERIFICATION", "true")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://outrena:outrena_dev@localhost:5432/outrena_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")  # DB 15 for tests
os.environ.setdefault("BASE_DOMAIN", "localhost")


@pytest.fixture(scope="session")
def app() -> object:
    """Import the FastAPI app once per test session."""
    from app.main import app as _app

    return _app


@pytest_asyncio.fixture
async def client(app: object) -> AsyncIterator[AsyncClient]:
    """ASGI test client — uses httpx ASGITransport (no network)."""
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
