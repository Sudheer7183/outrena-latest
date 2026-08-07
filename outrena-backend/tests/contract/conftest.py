"""
conftest.py — pytest + schemathesis fixtures for the OUTRENA contract suite.

Spec reference: migration doc §15.3 (Contract Testing):
> schemathesis runs against the OpenAPI spec, fuzzing every endpoint with
> random valid + invalid inputs. Any 5xx response (that isn't a deliberate
> 502 from an external service) fails the build.

Two ways to load the OpenAPI schema:
  1. **From URL** (default) — `schemathesis.openapi.from_url(...)` pulls the
     live spec from `${CONTRACT_BASE_URL}/openapi.json`. This is the
     production-realistic path: the spec the test fuzzes is the spec the
     running server actually implements.
  2. **From app** (fallback) — if `CONTRACT_BASE_URL` is unset AND the test
     process can import `app.main:app`, we call `app.openapi()` directly.
     This is useful for unit-test-style contract runs that don't need a
     live server (faster CI, but doesn't catch middleware-induced 5xxs).

Auth:
  * If `CONTRACT_AUTH_TOKEN` is set, every fuzzed request gets
    `Authorization: Bearer {token}`.
  * Otherwise the fixture generates a JWT using the same RS256 keypair the
    backend's test fixtures use (see `app/core/security.py`'s test helper).
    In CI, prefer `CONTRACT_AUTH_TOKEN` — generating RS256 JWTs requires
    the realm's public key to be configured.

Tenant:
  * Every fuzzed request gets `X-Tenant-Slug: {CONTRACT_TENANT_SLUG}` so
    the TenantMiddleware resolves a real schema. Without this header, all
    tenant-scoped endpoints return 400 (tenant middleware rejection) and
    the fuzzer can't reach the route handlers.
"""
from __future__ import annotations

import os
from typing import Any, Iterator

import pytest


# ── Configuration ────────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TENANT_SLUG = "acme"


@pytest.fixture(scope="session")
def base_url() -> str:
    """Backend FastAPI base URL (defaults to http://localhost:8000)."""
    return os.environ.get("CONTRACT_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def tenant_slug() -> str:
    """Tenant slug to send in the X-Tenant-Slug header (default: acme)."""
    return os.environ.get("CONTRACT_TENANT_SLUG", DEFAULT_TENANT_SLUG)


@pytest.fixture(scope="session")
def auth_token(tenant_slug: str) -> str:
    """Bearer token to attach to every fuzzed request.

    Resolution order:
      1. `CONTRACT_AUTH_TOKEN` env var (preferred in CI).
      2. A locally-minted RS256 JWT with the manager role claim (used when
         running contract tests inside the test process without a live
         Keycloak). The mint requires the backend's `app.core.security`
         test helper to be importable.

    Returns an empty string if neither path produces a token — the tests
    then mark themselves as skipped (so the suite degrades gracefully
    rather than running 401s against every endpoint).
    """
    env_token = os.environ.get("CONTRACT_AUTH_TOKEN")
    if env_token:
        return env_token
    # Try to mint a JWT from the backend's test helper.
    try:
        from app.core.security import mint_test_jwt  # type: ignore

        return mint_test_jwt(tenant_slug=tenant_slug, role="manager")
    except Exception:  # noqa: BLE001 — fall through to empty
        return ""


@pytest.fixture(scope="session")
def auth_headers(auth_token: str) -> dict[str, str]:
    """Headers to attach to every fuzzed request for auth + tenant resolution."""
    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


@pytest.fixture(scope="session")
def tenant_headers(tenant_slug: str) -> dict[str, str]:
    """Tenant-resolution header (X-Tenant-Slug)."""
    return {"X-Tenant-Slug": tenant_slug}


@pytest.fixture(scope="session")
def default_headers(
    auth_headers: dict[str, str],
    tenant_headers: dict[str, str],
) -> dict[str, str]:
    """Combined auth + tenant headers, applied to every fuzzed request."""
    return {**auth_headers, **tenant_headers}


# ── schemathesis schema fixture ──────────────────────────────────────────────

def _import_schemathesis() -> Any:
    """Import schemathesis lazily so `pytest --collect-only` works without it."""
    try:
        import schemathesis  # type: ignore
    except ImportError as exc:  # pragma: no cover — environment guard
        pytest.skip(
            f"schemathesis is not installed: {exc}. Install with "
            "`pip install -r tests/contract/requirements.txt`."
        )
    return schemathesis


@pytest.fixture(scope="session")
def schema(base_url: str) -> Any:
    """Load the OUTRENA OpenAPI schema into a schemathesis Schema instance.

    Resolution order:
      1. Try `schemathesis.openapi.from_url(f"{base_url}/openapi.json")` —
         this is the default and catches middleware-induced spec drift.
      2. If the URL fetch fails (e.g., backend not running), fall back to
         `schemathesis.openapi.from_dict(app.openapi())` — imports the
         FastAPI app in-process and reads its generated spec.

    The schema is session-scoped so the OpenAPI parse cost is paid once.
    """
    schemathesis = _import_schemathesis()
    # Try the live URL first.
    try:
        return schemathesis.openapi.from_url(f"{base_url}/openapi.json")
    except Exception as exc:  # noqa: BLE001 — fall back to in-process
        print(
            f"[conftest] Could not fetch OpenAPI from {base_url}/openapi.json "
            f"({exc}); falling back to in-process app.openapi()."
        )
    # Fallback: import the app and call openapi() directly.
    try:
        from app.main import app  # type: ignore
    except Exception as exc:  # pragma: no cover — environment guard
        pytest.skip(
            f"Could not import app.main:app for in-process OpenAPI fallback: {exc}"
        )
    spec = app.openapi()
    return schemathesis.openapi.from_dict(spec)


@pytest.fixture
def case(schema: Any) -> Iterator[Any]:
    """A single schemathesis Case (parameterised at the test-function level via
    `@schema.parametrize()`).

    This fixture is a thin wrapper that exists so test functions can type
    their dependency as `case: Case` for IDE assistance. The actual case
    generation is driven by `@schema.parametrize()` on each test.
    """
    # The real Case is injected by schemathesis's parametrize decorator;
    # this fixture is only used by tests that want a non-parameterised
    # case for manual schema introspection.
    yield schema  # type: ignore[misc]
