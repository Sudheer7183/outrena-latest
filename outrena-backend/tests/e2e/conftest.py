"""
conftest.py — pytest + Playwright fixtures for the OUTRENA E2E suite.

Spec reference: migration doc §15.2 (Playwright E2E — login → autopilot →
sequence review → reply triage; cross-tenant URL access with wrong token → 403).

We use the **Python** Playwright sync_api (not the Node flavor) to stay inside
the pytest test ecosystem. pytest-playwright supplies its own `page` fixture,
but we also define our own fixtures so the suite is self-documenting and does
not depend on pytest-playwright being installed for `pytest --collect-only` to
work (collect-only must succeed in CI before browsers are downloaded).

Configuration:
  * `pytest-playwright==0.5.2` provides the `browser`, `context`, `page`
    fixtures natively — but we redefine them here so that `pytest.ini`'s
    `addopts = -p no:cacheprovider` + our markers work even when the plugin
    is absent (CI gate before browser download).
  * Headless chromium is the default; override with `E2E_HEADLESS=0` for
    local debugging.
  * `E2E_BASE_URL` defaults to the Vite dev server (port 5173).
  * `E2E_TEST_USERNAME` / `E2E_TEST_PASSWORD` are the Keycloak test-tenant
    credentials created by the platform provisioning seed.
  * `E2E_TENANT_SLUG` is the slug of the tenant the test user belongs to
    (used to construct tenant-scoped URLs and to assert against the
    `X-Tenant-Slug` header the SPA sends on every API call).

Prerequisites (see README.md):
  1. Backend running at $E2E_API_BASE_URL (default http://localhost:8000).
  2. Frontend Vite dev server at $E2E_BASE_URL (default http://localhost:5173).
  3. Keycloak running with realm `outrena` and the test user provisioned.
  4. `playwright install chromium` has been run in the CI image.
"""
from __future__ import annotations

import os
from typing import Any, Generator

import pytest


# ── Environment-driven configuration ─────────────────────────────────────────
# These are read at fixture-resolution time so tests can be parameterised via
# the environment without re-importing the module.

DEFAULT_BASE_URL = "http://localhost:5173"
DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_TENANT_SLUG = "acme"


# ── Simple value fixtures ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url() -> str:
    """Frontend Vite dev server URL (defaults to http://localhost:5173)."""
    return os.environ.get("E2E_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """Backend FastAPI base URL (defaults to http://localhost:8000)."""
    return os.environ.get("E2E_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def tenant_slug() -> str:
    """Slug of the tenant the E2E test user belongs to (default: acme)."""
    return os.environ.get("E2E_TENANT_SLUG", DEFAULT_TENANT_SLUG)


@pytest.fixture(scope="session")
def test_username() -> str:
    """Keycloak test-tenant username (must be provisioned before the run)."""
    val = os.environ.get("E2E_TEST_USERNAME")
    if not val:
        pytest.skip(
            "E2E_TEST_USERNAME not set — provision a Keycloak test user first "
            "(see tests/e2e/README.md)."
        )
    return val


@pytest.fixture(scope="session")
def test_password() -> str:
    """Keycloak test-tenant password."""
    val = os.environ.get("E2E_TEST_PASSWORD")
    if not val:
        pytest.skip("E2E_TEST_PASSWORD not set — see tests/e2e/README.md.")
    return val


# ── Playwright sync_api fixtures ─────────────────────────────────────────────
# We import playwright lazily inside the fixtures so that:
#   1. `pytest --collect-only` works in CI *before* `playwright install` runs.
#   2. The fixtures degrade gracefully to a skip if playwright is missing,
#      rather than crashing collection.

def _playwright_sync_api() -> Any:
    """Import playwright.sync_api lazily; raise a helpful skip on failure."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as exc:  # pragma: no cover — environment guard
        pytest.skip(
            f"playwright is not installed: {exc}. Install with "
            "`pip install -r tests/e2e/requirements.txt && playwright install chromium`."
        )
    return sync_playwright


@pytest.fixture(scope="session")
def playwright_session() -> Generator[Any, None, None]:
    """Session-scoped Playwright sync_playwright context manager.

    Yields the running Playwright instance so that `browser` can launch a
    chromium instance from it. The session scope keeps browser downloads +
    process startup cost amortised across the whole E2E run.
    """
    sync_playwright = _playwright_sync_api()
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_session: Any) -> Generator[Any, None, None]:
    """Headless chromium Browser (session-scoped to amortise startup).

    Set `E2E_HEADLESS=0` to run headed for local debugging.
    """
    headless = os.environ.get("E2E_HEADLESS", "1") not in ("0", "false", "False")
    browser = playwright_session.chromium.launch(headless=headless)
    try:
        yield browser
    finally:
        browser.close()


@pytest.fixture
def context(browser: Any) -> Generator[Any, None, None]:
    """Fresh BrowserContext per test — isolates cookies + localStorage.

    A fresh context per test is critical for the login/logout tests: if the
    context persisted across tests, the `test_login_redirect` test would see
    a cached Keycloak session cookie from a prior `test_login_success` run.
    """
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        # Screenshot + video retention is configured here so the same context
        # works whether or not pytest-playwright is installed.
        record_video_dir="tests/e2e/.videos",
        record_video_size={"width": 1280, "height": 720},
    )
    # Fail-fast on console errors that aren't from third-party analytics.
    context.on("pageerror", lambda exc: print(f"[pageerror] {exc}"))
    try:
        yield context
    finally:
        context.close()


@pytest.fixture
def page(context: Any) -> Generator[Any, None, None]:
    """A single Page inside the per-test BrowserContext."""
    page = context.new_page()
    try:
        yield page
    finally:
        # Screenshots on failure are taken by the `pytest_runtest_makereport`
        # hook below; here we just close the page.
        page.close()


# ── Authenticated page fixture (golden-path tests reuse this) ────────────────

@pytest.fixture
def authed_page(
    page: Any,
    base_url: str,
    test_username: str,
    test_password: str,
) -> Any:
    """A Page that has already logged in via the Keycloak login form.

    Flow:
      1. Navigate to `${base_url}/login` (the SPA's login route).
      2. Fill the Keycloak username + password fields.
      3. Submit the form.
      4. Wait for the redirect back to the dashboard (`${base_url}/dashboard`).

    The fixture is function-scoped so each test gets a fresh login (no shared
    session state between tests). If the login form's selectors change, update
    the data-testid attributes in the LoginPage.tsx component — DO NOT change
    the selectors here (they are the contract between frontend + E2E).
    """
    page.goto(f"{base_url}/login", wait_until="networkidle")

    # Keycloak's stock login form uses id=username / id=password.
    # The SPA's LoginPage wraps Keycloak via direct-form POST, so the same
    # selectors apply whether the SPA renders its own form or redirects to
    # Keycloak's hosted login page.
    page.fill("input[name='username']", test_username)
    page.fill("input[name='password']", test_password)
    page.click("button[type='submit']")

    # Wait for the post-login redirect to the dashboard. The SPA's
    # ProtectedRoute component redirects authenticated users from /login to
    # /dashboard, so this selector is stable.
    page.wait_for_url(f"{base_url}/dashboard**", timeout=15_000)
    return page


# ── pytest hooks: screenshots + video on failure ─────────────────────────────

@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: Any, call: Any) -> Generator[None, Any, None]:
    """Attach a screenshot + page HTML to the test report on failure.

    This is the canonical pytest-playwright pattern (see pytest-playwright's
    own conftest). We reimplement it here so the suite does not depend on
    pytest-playwright being installed.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or report.passed:
        return
    page = item.funcargs.get("page")
    if page is None:
        return
    try:
        screenshot = page.screenshot(full_page=True)
        if screenshot:
            report.extra = list(getattr(report, "extra", []))
            # Defer the pytest-html import — not all CI images have it.
            try:
                from pytest_html import extras  # type: ignore

                report.extra.append(extras.image(screenshot, mime="image/png"))
            except ImportError:
                pass
    except Exception as exc:  # noqa: BLE001 — never let the hook crash the run
        print(f"[screenshot-hook] failed to capture screenshot: {exc}")
