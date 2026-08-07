"""
test_reply_triage_flow.py — E2E tests for the reply triage flow.

Spec reference: migration doc §15.2 (Playwright E2E: login → autopilot →
sequence review → reply triage).

The reply triage flow is the last leg of the golden path:
  1. Prospects reply to sent emails → MailBridge webhook → reply_drafts row.
  2. The rep opens the Reply Inbox (SPA ReplyInboxPage).
  3. The rep classifies each reply (Interested / Not Interested / Out of
     Office / Auto-Reply) via the categorize endpoint.
  4. Interested replies are routed to the CRM integration (HubSpot / Salesforce).

These tests validate the view → classify → route cycle. They assume a
sent email has already generated a reply_drafts row; the
`_ensure_replies_exist` helper creates a synthetic reply via the
reply_drafts API if the inbox is empty (using the same auth + tenant headers
the SPA would send).
"""
from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_reply]


def _ensure_replies_exist(page, base_url: str, api_base_url: str, tenant_slug: str) -> None:
    """Ensure at least one reply exists in the inbox; create one if not.

    Navigates to the Reply Inbox first. If empty, POSTs a synthetic reply
    via the browser's `request` context (so the same auth + tenant headers
    the SPA uses are reused). This is preferable to hitting the API from
    Python because it keeps the test self-contained inside the browser
    session that the rest of the test exercises.
    """
    page.goto(f"{base_url}/replies", wait_until="networkidle")
    page.wait_for_selector("[data-testid='replies-list']", timeout=15_000)
    rows = page.query_selector_all("[data-testid='reply-row']")
    if rows:
        return

    # No replies — create a synthetic one. We use page.context.request so
    # the browser session's auth cookies + headers are reused.
    payload = {
        "prospect_id": None,  # The backend will create a throwaway prospect.
        "subject": f"E2E Reply {tenant_slug}",
        "body": (
            "Hi — thanks for the email. This is interesting. "
            "Can we set up a call next week?"
        ),
        "received_at": "2025-01-15T10:30:00Z",
        "from_email": "prospect@example.com",
    }
    response = page.context.request.post(
        f"{api_base_url}/api/v1/reply-drafts",
        data=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Slug": tenant_slug,
        },
    )
    if response.status not in {200, 201}:
        pytest.skip(
            f"Could not create a synthetic reply for the triage test "
            f"(POST /api/v1/reply-drafts returned {response.status}). "
            f"Ensure MailBridge or a manual reply seed is available."
        )
    # Reload the inbox so the new reply renders.
    page.reload(wait_until="networkidle")
    page.wait_for_selector("[data-testid='replies-list']", timeout=15_000)
    rows = page.query_selector_all("[data-testid='reply-row']")
    assert rows, "Synthetic reply creation did not produce an inbox row"


def test_view_replies(
    authed_page,
    base_url: str,
    api_base_url: str,
    tenant_slug: str,
) -> None:
    """Navigate to the Reply Inbox and verify the reply list renders.

    Validates: GET /api/v1/reply-drafts returns rows and the ReplyInboxPage
    renders them with from_email, subject, and a preview of the body.
    """
    _ensure_replies_exist(authed_page, base_url, api_base_url, tenant_slug)
    rows = authed_page.query_selector_all("[data-testid='reply-row']")
    assert len(rows) > 0, "Reply Inbox is empty after seeding"
    # Each row must have a non-empty sender + subject.
    first = rows[0]
    sender = first.query_selector("[data-testid='reply-from']").inner_text().strip()
    subject = first.query_selector("[data-testid='reply-subject']").inner_text().strip()
    assert sender, "Reply row is missing sender text"
    assert subject, "Reply row is missing subject text"


def test_classify_reply(
    authed_page,
    base_url: str,
    api_base_url: str,
    tenant_slug: str,
) -> None:
    """Classify a reply as 'Interested' and verify the classification saved.

    Validates: POST /api/v1/reply-drafts/{id}/reply-categorize and that the
    SPA re-renders the row with the Interested badge. This is the manual
    human-classification path (the LLM auto-categorizer runs on webhook
    ingest; the rep can override via this UI).
    """
    _ensure_replies_exist(authed_page, base_url, api_base_url, tenant_slug)
    # Open the first reply row's classify dropdown.
    authed_page.click(
        "[data-testid='reply-row']:first-child [data-testid='classify-button']"
    )
    # Click the "Interested" option.
    authed_page.click("text=/interested/i")
    # The row should now show the Interested badge.
    badge = authed_page.wait_for_selector(
        "[data-testid='reply-row']:first-child [data-testid='category-badge']",
        timeout=5_000,
    )
    badge_text = badge.inner_text().strip().lower()
    assert "interested" in badge_text, (
        f"Classify did not persist Interested category; got {badge_text!r}"
    )


def test_route_reply(
    authed_page,
    base_url: str,
    api_base_url: str,
    tenant_slug: str,
) -> None:
    """Route an 'Interested' reply to the CRM and verify routing.

    Validates: the route-to-CRM action (POSTs the reply + prospect to the
    tenant's configured CRM integration — HubSpot/Salesforce/Pipedrive). The
    test asserts that the row shows a "Routed" status and a CRM link
    appears (the SPA renders the CRM record URL returned by the backend).
    """
    _ensure_replies_exist(authed_page, base_url, api_base_url, tenant_slug)
    # Classify first (routing is only enabled for Interested replies).
    authed_page.click(
        "[data-testid='reply-row']:first-child [data-testid='classify-button']"
    )
    authed_page.click("text=/interested/i")
    authed_page.wait_for_selector(
        "[data-testid='reply-row']:first-child [data-testid='category-badge']",
        timeout=5_000,
    )
    # Click the Route button.
    authed_page.click(
        "[data-testid='reply-row']:first-child [data-testid='route-button']"
    )
    # The routing status should flip to "Routed" or "Synced" within 15s
    # (the CRM round-trip can take a few seconds).
    authed_page.wait_for_selector(
        "[data-testid='reply-row']:first-child "
        "[data-testid='routing-status']:has-text('Routed'), "
        "[data-testid='reply-row']:first-child "
        "[data-testid='routing-status']:has-text('Synced')",
        timeout=15_000,
    )
    # The CRM link should be a non-empty <a href>.
    crm_link = authed_page.query_selector(
        "[data-testid='reply-row']:first-child [data-testid='crm-link']"
    )
    assert crm_link is not None, "Routed reply is missing the CRM link element"
    href = crm_link.get_attribute("href") or ""
    assert href.startswith("http"), (
        f"CRM link should be an absolute URL; got {href!r}"
    )
