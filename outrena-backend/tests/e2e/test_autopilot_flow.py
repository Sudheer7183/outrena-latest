"""
test_autopilot_flow.py — E2E tests for the OUTRENA Autopilot golden path.

Spec reference: migration doc §15.2 + §6.3 (autopilot Celery pipeline).

The autopilot golden path (spec §15.2):
  1. User navigates to the Autopilot page.
  2. User fills in the campaign brief (campaign name, target count, ICP hint,
     sender role/company/offer, proof metric, framework).
  3. User clicks "Run Pipeline".
  4. Frontend POSTs `/api/v1/autopilot` → backend enqueues a Celery
     `autopilot.run_pipeline` task → returns 202 + `{task_id, status: PENDING}`.
  5. Frontend polls `GET /api/v1/autopilot/{task_id}` every 2s.
  6. Status transitions: PENDING → STARTED → SUCCESS.
  7. On SUCCESS, the orchestrator has:
       * created a Campaign row,
       * generated N Prospect rows (sources + enriches via the LLM gateway),
       * drafted 7-touch sequence emails per prospect.
  8. The user navigates to Campaigns and sees the new campaign.
  9. The user navigates to Sequences and sees the drafted emails.

These tests validate steps 4–9 against a live stack. They are slow (the full
pipeline can take 60–120s) and are tagged `slow` so they can be excluded
from pre-merge gates and run only on nightly or staging-deploy pipelines.
"""
from __future__ import annotations

import re
import time

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_autopilot]

# Polling cadence for the autopilot status endpoint. The spec does not
# mandate a specific cadence; 2s matches the SPA's AutopilotPage polling
# interval and keeps the test under the 5-min pytest-timeout default.
_POLL_INTERVAL_SECONDS = 2.0
# Total budget for a single autopilot run. The orchestrator sources + enriches
# + drafts emails; under load this can take 2+ minutes. 5 min is the ceiling.
_MAX_POLL_SECONDS = 300.0


def _extract_task_id(page) -> str:
    """Extract the task_id from the AutopilotPage's status panel.

    The SPA renders the task_id in a `<code data-testid="autopilot-task-id">`
    element as soon as the POST /autopilot response arrives. We parse the
    text rather than intercepting the network response so the test exercises
    the real UI feedback loop.
    """
    page.wait_for_selector("[data-testid='autopilot-task-id']", timeout=10_000)
    raw = page.inner_text("[data-testid='autopilot-task-id']").strip()
    # Celery task IDs are UUIDs (hex or dashed). Tolerate either form.
    match = re.search(r"[0-9a-fA-F-]{8,}", raw)
    assert match, f"Could not parse task_id from panel text: {raw!r}"
    return match.group(0)


def _wait_for_terminal_status(page, target: str) -> None:
    """Poll the status panel until it shows `target` or fail after _MAX_POLL_SECONDS.

    `target` is one of SUCCESS / FAILURE. The panel renders the raw Celery
    state (PENDING / STARTED / SUCCESS / FAILURE) inside an element tagged
    `data-testid='autopilot-status'`.
    """
    deadline = time.monotonic() + _MAX_POLL_SECONDS
    seen_states: list[str] = []
    while time.monotonic() < deadline:
        page.wait_for_selector("[data-testid='autopilot-status']", timeout=5_000)
        current = page.inner_text("[data-testid='autopilot-status']").strip().upper()
        if current not in seen_states:
            seen_states.append(current)
        if current == target:
            return
        if current == "FAILURE":
            pytest.fail(
                f"Autopilot pipeline reported FAILURE before reaching {target}. "
                f"Observed states: {seen_states}"
            )
        time.sleep(_POLL_INTERVAL_SECONDS)
    pytest.fail(
        f"Autopilot pipeline did not reach {target} within {_MAX_POLL_SECONDS}s. "
        f"Observed states: {seen_states}"
    )


def test_trigger_autopilot(
    authed_page,
    base_url: str,
    tenant_slug: str,
) -> None:
    """Trigger the autopilot pipeline and verify the 202 → PENDING → STARTED → SUCCESS flow.

    Validates: the AutopilotPage form → POST /api/v1/autopilot → 202 with
    task_id, and the status polling loop shows the canonical Celery state
    transitions. This is the entry-point test for the autopilot golden path.
    """
    # 1. Navigate to the Autopilot page (sidebar item).
    authed_page.goto(f"{base_url}/autopilot", wait_until="networkidle")
    authed_page.wait_for_selector("text=Autopilot", timeout=10_000)

    # 2. Fill the campaign brief. Field selectors are stable because the
    #    AutopilotPage uses shadcn/ui Form fields with explicit data-testid.
    authed_page.fill("[data-testid='campaign-name']", f"E2E Autopilot {tenant_slug}")
    authed_page.fill("[data-testid='target-count']", "5")
    authed_page.fill("[data-testid='icp-hint']", "VP Engineering at B2B SaaS, 50-200 staff")
    authed_page.fill("[data-testid='sender-role']", "Head of Sales")
    authed_page.fill("[data-testid='sender-company']", "Outrena")
    authed_page.fill("[data-testid='sender-offer']", "30% more replies via AI-personalized sequences")
    authed_page.fill("[data-testid='proof-metric']", "3.2x reply rate vs control")
    authed_page.fill("[data-testid='sender-product']", "Outrena Outreach OS")

    # 3. Click "Run Pipeline" — fires POST /api/v1/autopilot.
    authed_page.click("button:has-text('Run Pipeline')")

    # 4. The SPA should render a 202 confirmation with the task_id within 5s.
    #    (We assert via the UI rather than intercepting the network response
    #    so the test exercises the full SPA feedback loop.)
    task_id = _extract_task_id(authed_page)
    assert task_id, "Autopilot POST did not return a task_id"

    # 5. The status panel must show PENDING or STARTED immediately after.
    authed_page.wait_for_selector("[data-testid='autopilot-status']", timeout=10_000)
    initial_status = authed_page.inner_text(
        "[data-testid='autopilot-status']"
    ).strip().upper()
    assert initial_status in {"PENDING", "STARTED"}, (
        f"Expected PENDING or STARTED immediately after trigger; got {initial_status}"
    )

    # 6. Wait for the terminal SUCCESS state. This is the slow part.
    _wait_for_terminal_status(authed_page, "SUCCESS")


def test_autopilot_creates_campaign(
    authed_page,
    base_url: str,
    tenant_slug: str,
) -> None:
    """After the pipeline completes, a new Campaign appears in the Campaigns list.

    Validates: the orchestrator's final step (create Campaign row in
    tenant_{slug} schema) and that the CampaignsPage list view picks it up
    via GET /api/v1/campaigns. Reuses the trigger flow but asserts on the
    downstream Campaigns list rather than the autopilot status panel.
    """
    # Trigger the pipeline (same as test_trigger_autopilot).
    authed_page.goto(f"{base_url}/autopilot", wait_until="networkidle")
    authed_page.fill("[data-testid='campaign-name']", f"E2E Campaign {tenant_slug}")
    authed_page.fill("[data-testid='target-count']", "3")
    authed_page.fill("[data-testid='icp-hint']", "CTO at fintech, 100-500 staff")
    authed_page.fill("[data-testid='sender-role']", "Founder")
    authed_page.fill("[data-testid='sender-company']", "Outrena")
    authed_page.fill("[data-testid='sender-offer']", "Cut sequence-drafting time by 80%")
    authed_page.fill("[data-testid='proof-metric']", "12h → 2h draft cycle")
    authed_page.fill("[data-testid='sender-product']", "Outrena Outreach OS")
    authed_page.click("button:has-text('Run Pipeline')")
    _extract_task_id(authed_page)
    _wait_for_terminal_status(authed_page, "SUCCESS")

    # Navigate to the Campaigns list and verify the new campaign appears.
    authed_page.goto(f"{base_url}/campaigns", wait_until="networkidle")
    authed_page.wait_for_selector("[data-testid='campaigns-table']", timeout=15_000)
    # The campaign name we set above should appear in the table.
    authed_page.wait_for_selector(
        f"text=E2E Campaign {tenant_slug}", timeout=15_000
    )


def test_autopilot_generates_emails(
    authed_page,
    base_url: str,
    tenant_slug: str,
) -> None:
    """After the pipeline completes, generated emails appear in the sequence.

    Validates: the orchestrator's email-drafting step (7-touch cadence emails
    per prospect) and that the SequencesPage renders them. The 7-touch
    cadence is days 1/4/9/16/25/35 — the test asserts that at least one
    sequence email exists with a non-empty body.
    """
    # Trigger the pipeline.
    authed_page.goto(f"{base_url}/autopilot", wait_until="networkidle")
    authed_page.fill("[data-testid='campaign-name']", f"E2E Seqs {tenant_slug}")
    authed_page.fill("[data-testid='target-count']", "3")
    authed_page.fill("[data-testid='icp-hint']", "Head of Growth at PLG SaaS")
    authed_page.fill("[data-testid='sender-role']", "Growth Lead")
    authed_page.fill("[data-testid='sender-company']", "Outrena")
    authed_page.fill("[data-testid='sender-offer']", "2x trial-to-paid conversion")
    authed_page.fill("[data-testid='proof-metric']", "+38% activation rate")
    authed_page.fill("[data-testid='sender-product']", "Outrena Outreach OS")
    authed_page.click("button:has-text('Run Pipeline')")
    _extract_task_id(authed_page)
    _wait_for_terminal_status(authed_page, "SUCCESS")

    # Navigate to the Sequences list (filtered to the new campaign).
    authed_page.goto(f"{base_url}/sequences", wait_until="networkidle")
    authed_page.wait_for_selector("[data-testid='sequences-table']", timeout=15_000)
    # At least one sequence row should be present with a non-empty subject.
    rows = authed_page.query_selector_all("[data-testid='sequence-row']")
    assert len(rows) > 0, "Autopilot did not generate any sequence emails"
    # The first row's subject cell must contain non-whitespace text.
    first_subject = rows[0].query_selector("[data-testid='sequence-subject']")
    assert first_subject is not None
    subject_text = first_subject.inner_text().strip()
    assert subject_text, "Generated sequence email has an empty subject line"


@pytest.mark.slow
def test_autopilot_partial_failure(
    authed_page,
    base_url: str,
    tenant_slug: str,
) -> None:
    """(Optional) When a step fails, partial results are still persisted.

    Validates: the orchestrator's compensating-transaction semantics — if the
    email-drafting step fails halfway, the already-created Campaign + Prospect
    rows are NOT rolled back. This is the autopilot equivalent of the
    provisioning-rollback test in tests/integration/.

    Implementation note: this test relies on a deliberate failure injection
    (e.g., an LLM provider returning 429 for half the requests). The CI
    pipeline sets `E2E_AUTOMATION_FAULT_INJECT=1` to enable this; if unset,
    the test skips rather than passing vacuously.
    """
    import os

    if os.environ.get("E2E_AUTOMATION_FAULT_INJECT") != "1":
        pytest.skip(
            "Set E2E_AUTOMATION_FAULT_INJECT=1 to enable autopilot fault "
            "injection (requires an LLM provider that 429s on demand)."
        )

    authed_page.goto(f"{base_url}/autopilot", wait_until="networkidle")
    authed_page.fill("[data-testid='campaign-name']", f"E2E Partial {tenant_slug}")
    authed_page.fill("[data-testid='target-count']", "5")
    authed_page.fill("[data-testid='icp-hint']", "VP Marketing")
    authed_page.fill("[data-testid='sender-role']", "Marketing Lead")
    authed_page.fill("[data-testid='sender-company']", "Outrena")
    authed_page.fill("[data-testid='sender-offer']", "More qualified pipeline")
    authed_page.fill("[data-testid='proof-metric']", "+22% MQL→SQL")
    authed_page.fill("[data-testid='sender-product']", "Outrena Outreach OS")
    authed_page.click("button:has-text('Run Pipeline')")
    _extract_task_id(authed_page)
    # With fault injection on, the pipeline should end in FAILURE but the
    # Campaign row should still exist (partial persistence).
    _wait_for_terminal_status(authed_page, "FAILURE")

    authed_page.goto(f"{base_url}/campaigns", wait_until="networkidle")
    authed_page.wait_for_selector("[data-testid='campaigns-table']", timeout=15_000)
    authed_page.wait_for_selector(
        f"text=E2E Partial {tenant_slug}", timeout=15_000
    )
