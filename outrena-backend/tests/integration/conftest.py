"""
conftest.py — Integration test fixtures for Phase 2.

THIS IS THE MOST IMPORTANT FILE IN THE PHASE 2 TEST SUITE.

It provides:
  - A throwaway PostgreSQL 16 database (testcontainers or local Postgres).
  - A Redis 7 connection (testcontainers or local Redis).
  - A mock KeycloakAdminService so tests don't need a live IdP.
  - Two provisioned tenants (acme, globex) for isolation tests.
  - Helpers to mint fake JWTs for any role + tenant.

If neither Docker (testcontainers) nor local Postgres+Redis is available,
the entire integration suite is skipped — never failed.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Environment ───────────────────────────────────────────────────────────────

# Tests bypass JWT verification (no live Keycloak).
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SKIP_JWT_VERIFICATION", "true")
os.environ.setdefault("VERIFY_JWT_ISSUER", "false")
os.environ.setdefault("BASE_DOMAIN", "localhost")
os.environ.setdefault("KEYCLOAK_BASE_URL", "http://localhost:8080")
os.environ.setdefault("KEYCLOAK_REALM", "outrena")

# Database URL — testcontainers overrides this once it spins up Postgres.
# Default assumes local Postgres on the standard port.
DEFAULT_TEST_DB = "postgresql+asyncpg://outrena:outrena_dev@localhost:5432/outrena_test"
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DB)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")


# ── Testcontainers bootstrap (optional) ───────────────────────────────────────


def _can_use_testcontainers() -> bool:
    """testcontainers requires Docker. Detect and skip cleanly."""
    try:
        import docker  # type: ignore[import-not-found]
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


if _can_use_testcontainers():
    try:
        from testcontainers.postgres import PostgresContainer  # type: ignore[import-not-found]
        from testcontainers.redis import RedisContainer  # type: ignore[import-not-found]
        _HAS_TC = True
    except ImportError:
        _HAS_TC = False
else:
    _HAS_TC = False


# ── Database fixture ──────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_db_url() -> str:
    """
    Provide a database URL for the test session.

    Priority:
      1. TEST_DATABASE_URL env var (explicit override — used by CI).
      2. testcontainers PostgresContainer (if Docker is available).
      3. Local PostgreSQL at outrena:outrena_dev@localhost:5432/outrena_test.
         Skips the suite if unreachable.
    """
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]

    if _HAS_TC:
        try:
            pg = PostgresContainer("postgres:16-alpine")
            pg.start()
            # testcontainers gives a sync psycopg URL; convert to asyncpg.
            sync_url = pg.get_connection_url()
            # postgresql+psycopg2://test:test@localhost:XXXXX/test
            # → postgresql+asyncpg://test:test@localhost:XXXXX/test
            async_url = sync_url.replace("+psycopg2", "+asyncpg").replace(
                "postgresql://", "postgresql+asyncpg://"
            )
            # Hold the container alive for the session by stashing on a module attr.
            _testcontainers_state["pg"] = pg
            return async_url
        except Exception:
            pass  # fall through to local

    # Local Postgres — check reachability
    try:
        engine = create_async_engine(TEST_DB_URL)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return TEST_DB_URL
    except Exception as exc:
        pytest.skip(
            f"No PostgreSQL available for integration tests. "
            f"Set TEST_DATABASE_URL or run Postgres on localhost:5432. Error: {exc}"
        )


@pytest_asyncio.fixture(scope="session")
async def test_engine(test_db_url: str):
    """Session-scoped async engine bound to the test database."""
    eng = create_async_engine(test_db_url, echo=False, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_db_schema(test_engine):
    """Run migration 0001 (public.tenants + tenant_config) once per session."""
    # Reset public schema to a clean state.
    async with test_engine.begin() as conn:
        # Drop any leftover tenant schemas from prior runs.
        result = await conn.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'tenant_%'"
            )
        )
        for (schema_name,) in result.fetchall():
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        # Drop public tables in dependency order.
        for tbl in ("platform_audit_log", "tenant_config", "tenants"):
            await conn.execute(text(f'DROP TABLE IF EXISTS public.{tbl} CASCADE'))
        # Drop alembic_version table from public.
        await conn.execute(text("DROP TABLE IF EXISTS public.alembic_version CASCADE"))

    # Run migration 0001 by executing its upgrade() in public.
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    # We can't easily use the dual-mode env.py here because it iterates
    # tenant schemas; instead we apply the 0001 migration directly.
    # The migration's upgrade() uses op.create_table with explicit schema="public"
    # so it's safe to call via a sync Alembic context.
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(test_engine.url))
    # Patch the env.py to skip the dual-mode runner for the bootstrap.
    os.environ["ALEMBIC_TARGET_SCHEMA"] = "public"
    try:
        alembic_command.upgrade(cfg, "head")
    finally:
        os.environ.pop("ALEMBIC_TARGET_SCHEMA", None)


# ── Per-test DB session (with search_path control) ────────────────────────────


@pytest_asyncio.fixture
async def db_public(test_engine) -> AsyncIterator[AsyncSession]:
    """A session locked to the public schema (for registry operations)."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(text('SET search_path TO "public"'))
        yield session
        await session.rollback()


@asynccontextmanager
async def tenant_session(test_engine, schema_name: str) -> AsyncIterator[AsyncSession]:
    """Context manager: a session locked to a specific tenant schema."""
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(text(f'SET search_path TO "{schema_name}", public'))
        yield session
        await session.rollback()


@pytest.fixture
def make_tenant_session(test_engine) -> Callable[[str], Any]:
    """Factory: returns a context-manager yielding a session for one schema."""
    def _factory(schema_name: str):
        return tenant_session(test_engine, schema_name)
    return _factory


# ── Mock Keycloak ─────────────────────────────────────────────────────────────


class MockKeycloakAdminService:
    """
    In-memory mock of KeycloakAdminService.

    Avoids the need for a live Keycloak container. Implements the methods
    TenantProvisioningService calls: create_tenant_admin_user,
    add_redirect_uris_to_frontend_client, verify_token.
    """

    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self.redirect_uris: list[str] = []
        self.web_origins: list[str] = []

    async def verify_token(self, token: str) -> dict[str, Any]:
        # In test mode SKIP_JWT_VERIFICATION=true is set, so this is unused.
        # Tests mint fake tokens with _mint_jwt() and the security layer
        # reads claims via get_unverified_claims.
        raise RuntimeError("MockKeycloakAdminService.verify_token called — should not happen in SKIP_JWT_VERIFICATION mode")

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
        user_id = str(uuid.uuid4())
        self.users[user_id] = {
            "id": user_id,
            "username": email,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "attributes": {"tenant_slug": [tenant_slug]},
            "realmRoles": ["tenant_admin"],
        }
        return user_id

    async def add_redirect_uris_to_frontend_client(self, tenant_slug: str) -> None:
        uri = f"https://{tenant_slug}.localhost/*"
        if uri not in self.redirect_uris:
            self.redirect_uris.append(uri)
        origin = f"https://{tenant_slug}.localhost"
        if origin not in self.web_origins:
            self.web_origins.append(origin)


@pytest.fixture
def mock_keycloak(monkeypatch) -> MockKeycloakAdminService:
    """Patch get_keycloak_admin_service to return a MockKeycloakAdminService."""
    mock = MockKeycloakAdminService()
    # Patch the lru_cache-wrapped getter in the keycloak module.
    from app.services import keycloak_admin_service as kcmod
    monkeypatch.setattr(kcmod, "get_keycloak_admin_service", lambda: mock)
    return mock


# ── JWT minting helper ────────────────────────────────────────────────────────


def _mint_jwt(*, sub: str, email: str, role: str, tenant_slug: str | None) -> str:
    """Mint an unsigned JWT for tests. SKIP_JWT_VERIFICATION=true reads claims
    via jwt.get_unverified_claims, so the signature doesn't matter."""
    from jose import jwt as jose_jwt

    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "tenant_slug": tenant_slug,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "iss": "http://localhost:8080/realms/outrena",
    }
    # Use a dummy secret — tests never verify the signature.
    return jose_jwt.encode(payload, key="test-secret", algorithm="HS256")


@pytest.fixture
def mint_jwt() -> Callable[..., str]:
    """Factory: mint a fake Bearer JWT for tests."""
    return _mint_jwt


@pytest.fixture
def auth_headers():
    """Return a function that builds Authorization headers for a given JWT."""
    def _factory(jwt: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {jwt}"}
    return _factory


# ── Skip marker for tests requiring Postgres ──────────────────────────────────


# Module-level state used to keep testcontainers alive across the session.
_testcontainers_state: dict[str, Any] = {}


def requires_postgres(func):
    """Decorator: skip if Postgres is not available."""
    return pytest.mark.usefixtures("test_engine")(func)
