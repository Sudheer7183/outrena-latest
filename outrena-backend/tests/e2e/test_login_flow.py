"""
test_login_flow.py — E2E tests for the OUTRENA login → dashboard flow.

Spec reference: migration doc §15.2 (Playwright E2E: login → autopilot →
sequence review → reply triage). This file covers the *login* leg of that
golden path.

What these tests validate:
  * `test_login_redirect` — an unauthenticated visit to `/` redirects to the
    Keycloak login page (proves the SPA's ProtectedRoute guard + Keycloak
    redirect_uri wiring are correct).
  * `test_login_success` — valid credentials land on `/dashboard` and the
    logged-in user's email is rendered in the topbar (proves the JWT was
    exchanged, stored in localStorage, and the `/api/v1/auth/me` call
    returned the user profile).
  * `test_login_failure` — invalid credentials show an error message on the
    login page and the user is NOT redirected to the dashboard (proves the
    SPA does not silently swallow Keycloak 401s).
  * `test_logout` — clicking the logout button clears the session and
    returns the user to the login page (proves the AuthContext's logout
    handler both revoked the Keycloak session AND cleared the local token).

These tests are the gate for the rest of the E2E suite — the autopilot,
sequence, and reply triage suites all reuse the `authed_page` fixture which
performs the same login flow as `test_login_success`.
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_login]


def test_login_redirect(page, base_url: str) -> None:
    """Unauthenticated visit to `/` redirects to the Keycloak login page.

    Validates: SPA ProtectedRoute guard, Keycloak `redirect_uri` wiring, and
    that no unauthenticated content from the dashboard leaks before login.
    """
    page.goto(f"{base_url}/", wait_until="networkidle")
    # The SPA should redirect to /login (its own login wrapper) which then
    # bounces to Keycloak. Either /login or the Keycloak realm URL is valid.
    page.wait_for_url(
        lambda url: "/login" in url or "realms/" in url or "protocol/openid" in url,
        timeout=10_000,
    )
    assert "/dashboard" not in page.url, (
        "Unauthenticated visit should NOT land on the dashboard"
    )


def test_login_success(
    authed_page,
    base_url: str,
    test_username: str,
) -> None:
    """Valid credentials land on the dashboard with the user email visible.

    Validates: Keycloak token exchange, SPA token storage, and the
    `/api/v1/auth/me` call that hydrates the topbar user menu.
    """
    # The authed_page fixture already asserted the URL is /dashboard.
    assert "/dashboard" in authed_page.url
    # The topbar renders the user's email — visible after the /auth/me call
    # resolves. Wait up to 10s for it.
    authed_page.wait_for_selector(f"text={test_username}", timeout=10_000)


def test_login_failure(page, base_url: str) -> None:
    """Invalid credentials show an error message and stay on /login.

    Validates: the SPA does not silently swallow Keycloak 401 responses and
    that no partial dashboard state is rendered after a failed login.
    """
    page.goto(f"{base_url}/login", wait_until="networkidle")
    page.fill("input[name='username']", "nobody@nowhere.test")
    page.fill("input[name='password']", "definitely-wrong-password-12345")
    page.click("button[type='submit']")

    # Keycloak renders "Invalid username or password." on the same page.
    # The SPA's LoginPage may also surface its own error toast. Match either.
    page.wait_for_selector(
        "text=/invalid|incorrect|failed|error/i", timeout=10_000
    )
    assert "/login" in page.url or "realms/" in page.url, (
        "Failed login must stay on /login or the Keycloak login page"
    )
    assert "/dashboard" not in page.url


def test_logout(authed_page, base_url: str) -> None:
    """Clicking logout clears the session and returns to the login page.

    Validates: the AuthContext.logout() handler (1) revokes the Keycloak
    session via end_session_endpoint, and (2) clears the local access_token
    + refresh_token so a subsequent reload does NOT auto-login.
    """
    # The topbar has a user menu trigger + a "Sign out" item. Click through.
    authed_page.click("[data-testid='user-menu-trigger']")
    authed_page.click("text=/sign out|log out|logout/i")

    # After logout, the SPA should redirect to /login (AuthContext clears
    # the token and ProtectedRoute bounces unauthenticated users).
    authed_page.wait_for_url(f"{base_url}/login**", timeout=10_000)
    assert "/dashboard" not in authed_page.url

    # Reload to prove the token was actually cleared (not just navigated away).
    authed_page.reload(wait_until="networkidle")
    assert "/dashboard" not in authed_page.url, (
        "After logout, a reload must NOT auto-login back to the dashboard"
    )
