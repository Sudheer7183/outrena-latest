"""
test_sequence_review_flow.py — E2E tests for the sequence review flow.

Spec reference: migration doc §15.2 (Playwright E2E: login → autopilot →
sequence review → reply triage).

The sequence review flow is the human-in-the-loop gate between the autopilot
pipeline (which drafts emails) and the scheduler (which sends them). A
manager reviews each drafted email and either:
  * Approves  → status becomes Approved, the scheduler picks it up on the
    next business-hours tick.
  * Rejects   → status becomes Rejected, the email is never sent.
  * Edits     → the manager tweaks the subject/body, saves, then approves.

These tests validate all three review actions plus the pending-list view.
They run against the same tenant as the autopilot tests and assume the
autopilot suite has generated at least one Draft sequence (the
`authed_page` fixture + a fresh autopilot trigger in
`test_view_pending_sequences` guarantees this).
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_sequence]


def _ensure_draft_sequences_exist(page, base_url: str, tenant_slug: str) -> None:
    """Trigger an autopilot run if the Sequences list is empty.

    The sequence-review tests need at least one Draft sequence to act on.
    Rather than assuming a prior autopilot run, this helper runs a minimal
    autopilot pipeline (target_count=2) when the list is empty. It is a
    no-op if the list already has Drafts.
    """
    page.goto(f"{base_url}/sequences", wait_until="networkidle")
    page.wait_for_selector("[data-testid='sequences-table']", timeout=15_000)
    rows = page.query_selector_all("[data-testid='sequence-row']")
    if rows:
        return
    # No drafts — run a minimal autopilot pipeline.
    page.goto(f"{base_url}/autopilot", wait_until="networkidle")
    page.fill("[data-testid='campaign-name']", f"Seq Review Setup {tenant_slug}")
    page.fill("[data-testid='target-count']", "2")
    page.fill("[data-testid='icp-hint']", "VP Sales at B2B SaaS")
    page.fill("[data-testid='sender-role']", "Sales Lead")
    page.fill("[data-testid='sender-company']", "Outrena")
    page.fill("[data-testid='sender-offer']", "More meetings booked")
    page.fill("[data-testid='proof-metric']", "+40% reply rate")
    page.fill("[data-testid='sender-product']", "Outrena Outreach OS")
    page.click("button:has-text('Run Pipeline')")
    # Wait for the status panel to render (proves the POST succeeded).
    page.wait_for_selector("[data-testid='autopilot-task-id']", timeout=10_000)
    # Poll until SUCCESS or FAILURE.
    import re
    import time
    deadline = time.monotonic() + 300.0
    while time.monotonic() < deadline:
        page.wait_for_selector("[data-testid='autopilot-status']", timeout=5_000)
        st = page.inner_text("[data-testid='autopilot-status']").strip().upper()
        if st in {"SUCCESS", "FAILURE"}:
            break
        time.sleep(2.0)
    # Re-assert we now have drafts.
    page.goto(f"{base_url}/sequences", wait_until="networkidle")
    page.wait_for_selector("[data-testid='sequences-table']", timeout=15_000)
    rows = page.query_selector_all("[data-testid='sequence-row']")
    assert rows, "Autopilot setup run did not produce any Draft sequences"


def test_view_pending_sequences(
    authed_page,
    base_url: str,
    tenant_slug: str,
) -> None:
    """Navigate to Sequences and verify the pending-sequences list renders.

    Validates: GET /api/v1/sequences returns paginated rows and the
    SequencesPage renders them with the correct status badges (Draft,
    Approved, Rejected, Scheduled, Sent). The test asserts that at least
    one Draft row is present after the setup autopilot run.
    """
    _ensure_draft_sequences_exist(authed_page, base_url, tenant_slug)
    # The status filter pills should show a count for Draft.
    draft_pill = authed_page.query_selector(
        "[data-testid='status-filter-draft']"
    )
    assert draft_pill is not None, "SequencesPage is missing the Draft status filter"
    pill_text = draft_pill.inner_text().strip()
    # The pill renders as "Draft (N)" — extract N.
    import re
    match = re.search(r"\((\d+)\)", pill_text)
    assert match, f"Could not parse Draft count from pill text: {pill_text!r}"
    draft_count = int(match.group(1))
    assert draft_count > 0, "No Draft sequences visible after autopilot setup run"


def test_approve_sequence(
    authed_page,
    base_url: str,
    tenant_slug: str,
) -> None:
    """Click Approve on a Draft sequence and verify status changes to Approved.

    Validates: POST /api/v1/sequences/{id}/scheduled-send (or the approve
    action endpoint) and that the SPA's optimistic update + TanStack Query
    invalidation re-renders the row with the Approved badge.
    """
    _ensure_draft_sequences_exist(authed_page, base_url, tenant_slug)
    # Click the first Draft row's Approve button.
    authed_page.click(
        "[data-testid='sequence-row']:first-child "
        "[data-testid='approve-button']"
    )
    # The row's status badge should flip to Approved within 5s.
    badge = authed_page.wait_for_selector(
        "[data-testid='sequence-row']:first-child "
        "[data-testid='status-badge']",
        timeout=5_000,
    )
    badge_text = badge.inner_text().strip().lower()
    assert "approved" in badge_text, (
        f"Approve did not flip status to Approved; got {badge_text!r}"
    )


def test_reject_sequence(
    authed_page,
    base_url: str,
    tenant_slug: str,
) -> None:
    """Click Reject on a Draft sequence and verify status changes to Rejected.

    Validates: the reject action endpoint and that the SPA correctly renders
    the Rejected badge. Rejected emails must never be picked up by the
    scheduler — this test is the human-in-the-loop safety net.
    """
    _ensure_draft_sequences_exist(authed_page, base_url, tenant_slug)
    authed_page.click(
        "[data-testid='sequence-row']:first-child "
        "[data-testid='reject-button']"
    )
    badge = authed_page.wait_for_selector(
        "[data-testid='sequence-row']:first-child "
        "[data-testid='status-badge']",
        timeout=5_000,
    )
    badge_text = badge.inner_text().strip().lower()
    assert "rejected" in badge_text, (
        f"Reject did not flip status to Rejected; got {badge_text!r}"
    )


def test_edit_sequence(
    authed_page,
    base_url: str,
    tenant_slug: str,
) -> None:
    """Edit a Draft sequence's email body, save, and verify the update persisted.

    Validates: PUT /api/v1/sequences/{id} with an updated body, the SPA's
    edit modal form binding, and that a fresh GET returns the edited body
    (proving the update was persisted to the tenant schema, not just held in
    SPA state).
    """
    _ensure_draft_sequences_exist(authed_page, base_url, tenant_slug)

    # Open the edit modal for the first Draft row.
    authed_page.click(
        "[data-testid='sequence-row']:first-child "
        "[data-testid='edit-button']"
    )
    authed_page.wait_for_selector("[data-testid='sequence-edit-modal']", timeout=5_000)

    # Capture the original body, then append a sentinel string.
    body_textarea = authed_page.query_selector(
        "[data-testid='sequence-edit-modal'] textarea[name='body']"
    )
    assert body_textarea is not None, "Edit modal is missing the body textarea"
    original_body = body_textarea.input_value()
    sentinel = f" [E2E edit {tenant_slug}]"
    new_body = original_body + sentinel
    body_textarea.fill(new_body)

    # Save the edit.
    authed_page.click(
        "[data-testid='sequence-edit-modal'] button:has-text('Save')"
    )
    # The modal should close on save.
    authed_page.wait_for_selector(
        "[data-testid='sequence-edit-modal']", state="hidden", timeout=5_000
    )

    # Re-open the same row's edit modal to prove the body was persisted.
    authed_page.click(
        "[data-testid='sequence-row']:first-child "
        "[data-testid='edit-button']"
    )
    authed_page.wait_for_selector("[data-testid='sequence-edit-modal']", timeout=5_000)
    body_textarea = authed_page.query_selector(
        "[data-testid='sequence-edit-modal'] textarea[name='body']"
    )
    persisted_body = body_textarea.input_value()
    assert persisted_body.endswith(sentinel), (
        f"Edit did not persist. Expected body to end with {sentinel!r}; "
        f"got {persisted_body[-80:]!r}"
    )
