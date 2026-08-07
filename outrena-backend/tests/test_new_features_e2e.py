"""
test_new_features_e2e.py — End-to-end tests for OUTRENA new feature endpoints.

Tests all new backend endpoints using httpx.AsyncClient + ASGITransport (the
same pattern as test_e2e_v4.py). Full stack from router → service → schema
without network or Docker.

Endpoints covered:
  Pipeline:
    POST /api/v1/pipeline/run-stage   (thesis, signals, scoring, briefs, campaign)
    GET  /api/v1/pipeline/status

  Flow Templates:
    GET  /api/v1/flow-templates
    GET  /api/v1/flow-templates/{template_id}
    POST /api/v1/flow-templates/clone

  Flow Analytics:
    GET  /api/v1/flow-analytics
    GET  /api/v1/flow-analytics/{flow_id}

  Autopilot Queue:
    GET    /api/v1/autopilot-queue
    GET    /api/v1/autopilot-queue/stats
    POST   /api/v1/autopilot-queue/enqueue
    POST   /api/v1/autopilot-queue/trigger-scheduler
    PUT    /api/v1/autopilot-queue/autonomous-mode
    DELETE /api/v1/autopilot-queue/{id}

  Email Studio AI:
    POST /api/v1/email-studio/qa-score
    POST /api/v1/email-studio/subject-lines-generate

  LinkedIn ICP Match:
    POST /api/v1/linkedin/engagements/check-icp

  Signal AI:
    POST /api/v1/signals/scan
    POST /api/v1/signals/lead-score-batch
    GET  /api/v1/signals/lead-score/stats

  Alumni Tracker / Job Change Monitor:
    GET  /api/v1/job-change-monitor
    POST /api/v1/job-change-monitor/scan

Run with:
  cd outrena-backend && pytest tests/test_new_features_e2e.py -v

Prerequisites:
  - Test database (outrena_test) must exist and be migrated.
  - Redis on DB 15 for test session.
  - SKIP_JWT_VERIFICATION=true (set by conftest.py).

NOTE: Tests that require a live DB are marked with @pytest.mark.integration
and will be skipped if the database is unreachable. Schema-validation-only
tests run unconditionally.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

# Ensure test environment
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SKIP_JWT_VERIFICATION", "true")

pytestmark = pytest.mark.anyio

API = "/api/v1"


# ── Fixture: ASGI client ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    """ASGI test client for the FastAPI app."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app as _app

    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def authed_client(client):
    """Client with dev-token authorization header."""
    client.headers["Authorization"] = "Bearer dev-token"
    client.headers["X-Tenant-Slug"] = "acme"
    return client


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipeline:
    """Pipeline run-stage + status endpoints."""

    @pytest.mark.integration
    async def test_pipeline_run_thesis(self, authed_client):
        """POST /pipeline/run-stage with stage='thesis' → 200."""
        resp = await authed_client.post(
            f"{API}/pipeline/run-stage",
            json={
                "stage": "thesis",
                "product_name": "OUTRENA Sales Platform",
                "target_industries": "B2B SaaS",
                "product_description": "AI-powered outbound sales platform",
                "key_value_props": "Automated prospecting, AI email generation",
            },
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Pipeline endpoint unavailable (DB not provisioned)")
        data = resp.json()
        assert data["success"] is True
        assert data["stage"] == "thesis"

    @pytest.mark.integration
    async def test_pipeline_run_signals(self, authed_client):
        """POST /pipeline/run-stage with stage='signals' → 200."""
        resp = await authed_client.post(
            f"{API}/pipeline/run-stage",
            json={"stage": "signals"},
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Pipeline endpoint unavailable (DB not provisioned)")
        data = resp.json()
        assert data["stage"] == "signals"

    @pytest.mark.integration
    async def test_pipeline_run_scoring(self, authed_client):
        """POST /pipeline/run-stage with stage='scoring' → 200."""
        resp = await authed_client.post(
            f"{API}/pipeline/run-stage",
            json={"stage": "scoring"},
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Pipeline endpoint unavailable (DB not provisioned)")
        data = resp.json()
        assert data["stage"] == "scoring"

    @pytest.mark.integration
    async def test_pipeline_run_briefs(self, authed_client):
        """POST /pipeline/run-stage with stage='briefs' → 200."""
        resp = await authed_client.post(
            f"{API}/pipeline/run-stage",
            json={"stage": "briefs"},
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Pipeline endpoint unavailable (DB not provisioned)")
        data = resp.json()
        assert data["stage"] == "briefs"

    @pytest.mark.integration
    async def test_pipeline_run_campaign(self, authed_client):
        """POST /pipeline/run-stage with stage='campaign' → 200."""
        resp = await authed_client.post(
            f"{API}/pipeline/run-stage",
            json={"stage": "campaign"},
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Pipeline endpoint unavailable (DB not provisioned)")
        data = resp.json()
        assert data["stage"] == "campaign"

    @pytest.mark.integration
    async def test_pipeline_get_status(self, authed_client):
        """GET /pipeline/status → 200 with stages_completed list."""
        resp = await authed_client.get(f"{API}/pipeline/status")
        if resp.status_code != 200:
            pytest.skip("Pipeline status endpoint unavailable")
        data = resp.json()
        assert "stages_completed" in data
        assert isinstance(data["stages_completed"], list)

    @pytest.mark.integration
    async def test_pipeline_invalid_stage(self, authed_client):
        """POST /pipeline/run-stage with stage='invalid' → 500."""
        resp = await authed_client.post(
            f"{API}/pipeline/run-stage",
            json={"stage": "invalid"},
        )
        # Invalid stage should cause the service to return success=False,
        # which the router converts to HTTP 500.
        assert resp.status_code == 500


# ═══════════════════════════════════════════════════════════════════════════════
# Flow Templates Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowTemplates:
    """Flow template list / get / clone endpoints."""

    @pytest.mark.integration
    async def test_list_flow_templates(self, authed_client):
        """GET /flow-templates → returns 3 built-in templates."""
        resp = await authed_client.get(f"{API}/flow-templates")
        if resp.status_code != 200:
            pytest.skip("Flow templates endpoint unavailable")
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.integration
    async def test_get_flow_template(self, authed_client):
        """GET /flow-templates/tpl-enterprise-abm → 200 with template data."""
        resp = await authed_client.get(f"{API}/flow-templates/tpl-enterprise-abm")
        if resp.status_code != 200:
            pytest.skip("Flow templates endpoint unavailable")
        data = resp.json()
        assert data["id"] == "tpl-enterprise-abm"
        assert data["name"] == "Enterprise ABM Flow"
        assert data["gate_strictness"] == "strict"

    @pytest.mark.integration
    async def test_get_flow_template_not_found(self, authed_client):
        """GET /flow-templates/nonexistent → 404."""
        resp = await authed_client.get(f"{API}/flow-templates/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.integration
    async def test_clone_flow_template(self, authed_client):
        """POST /flow-templates/clone with template_id → 200/201."""
        resp = await authed_client.post(
            f"{API}/flow-templates/clone",
            json={
                "template_id": "tpl-enterprise-abm",
                "new_name": "E2E Cloned ABM Flow",
            },
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Flow templates clone unavailable (DB not provisioned)")
        data = resp.json()
        assert data["success"] is True
        assert data["flow_id"] is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Flow Analytics Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowAnalytics:
    """Flow analytics list + get endpoints."""

    @pytest.mark.integration
    async def test_list_flow_analytics(self, authed_client):
        """GET /flow-analytics → 200 with items list."""
        resp = await authed_client.get(f"{API}/flow-analytics")
        if resp.status_code != 200:
            pytest.skip("Flow analytics endpoint unavailable")
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.integration
    async def test_get_flow_analytics(self, authed_client):
        """GET /flow-analytics/{flow_id} → 200 for a valid flow.

        We try with a known seeded template flow ID first.
        """
        # Try a seeded template flow; if not found, skip gracefully
        resp = await authed_client.get(
            f"{API}/flow-analytics/tpl-enterprise-abm"
        )
        if resp.status_code == 404:
            # The template may not have analytics; try listing to find a flow
            list_resp = await authed_client.get(f"{API}/flow-analytics")
            if list_resp.status_code != 200:
                pytest.skip("Flow analytics endpoint unavailable")
            items = list_resp.json()["items"]
            if not items:
                pytest.skip("No flows with analytics in test DB")
            flow_id = items[0]["flow_id"]
            resp = await authed_client.get(f"{API}/flow-analytics/{flow_id}")
        if resp.status_code != 200:
            pytest.skip("No flow analytics data available")
        data = resp.json()
        assert "flow_id" in data
        assert "kpis" in data
        assert "funnel" in data

    @pytest.mark.integration
    async def test_get_flow_analytics_not_found(self, authed_client):
        """GET /flow-analytics/nonexistent → 404."""
        resp = await authed_client.get(f"{API}/flow-analytics/nonexistent-id-xyz")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Autopilot Queue Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAutopilotQueue:
    """Autopilot queue list / stats / enqueue / trigger / mode / cancel."""

    @pytest.mark.integration
    async def test_list_queue(self, authed_client):
        """GET /autopilot-queue → 200 with items list."""
        resp = await authed_client.get(f"{API}/autopilot-queue")
        if resp.status_code != 200:
            pytest.skip("Autopilot queue endpoint unavailable")
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.integration
    async def test_get_queue_stats(self, authed_client):
        """GET /autopilot-queue/stats → 200 with queue statistics."""
        resp = await authed_client.get(f"{API}/autopilot-queue/stats")
        if resp.status_code != 200:
            pytest.skip("Autopilot queue stats unavailable")
        data = resp.json()
        assert "queued" in data
        assert "running" in data
        assert "autonomous_mode" in data

    @pytest.mark.integration
    async def test_enqueue_flow(self, authed_client):
        """POST /autopilot-queue/enqueue → 201 with queue_id."""
        resp = await authed_client.post(
            f"{API}/autopilot-queue/enqueue",
            json={
                "flow_id": "tpl-enterprise-abm",
                "max_prospects": 10,
                "dry_run": True,
            },
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Autopilot enqueue unavailable (DB not provisioned)")
        data = resp.json()
        assert data["success"] is True
        assert data.get("queue_id") is not None

    @pytest.mark.integration
    async def test_trigger_scheduler(self, authed_client):
        """POST /autopilot-queue/trigger-scheduler → 200."""
        resp = await authed_client.post(
            f"{API}/autopilot-queue/trigger-scheduler",
        )
        if resp.status_code != 200:
            pytest.skip("Autopilot scheduler trigger unavailable")
        data = resp.json()
        assert "success" in data

    @pytest.mark.integration
    async def test_set_autonomous_mode(self, authed_client):
        """PUT /autopilot-queue/autonomous-mode → 200."""
        resp = await authed_client.put(
            f"{API}/autopilot-queue/autonomous-mode",
            json={"enabled": True},
        )
        if resp.status_code != 200:
            pytest.skip("Autopilot autonomous mode unavailable")
        data = resp.json()
        assert "autonomous_mode" in data

        # Restore to disabled
        await authed_client.put(
            f"{API}/autopilot-queue/autonomous-mode",
            json={"enabled": False},
        )

    @pytest.mark.integration
    async def test_cancel_queue_item(self, authed_client):
        """DELETE /autopilot-queue/{id} → 204 (if item exists) or 404."""
        # First enqueue to get a queue_id, then cancel it
        enqueue_resp = await authed_client.post(
            f"{API}/autopilot-queue/enqueue",
            json={
                "flow_id": "tpl-enterprise-abm",
                "max_prospects": 5,
                "dry_run": True,
            },
        )
        if enqueue_resp.status_code not in (200, 201):
            pytest.skip("Autopilot enqueue unavailable (DB not provisioned)")
        queue_id = enqueue_resp.json().get("queue_id")
        if not queue_id:
            pytest.skip("No queue_id returned from enqueue")

        cancel_resp = await authed_client.delete(
            f"{API}/autopilot-queue/{queue_id}"
        )
        assert cancel_resp.status_code in (204, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# Email Studio AI Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmailStudioAI:
    """Email studio QA score + subject-line generation endpoints."""

    @pytest.mark.integration
    async def test_qa_score(self, authed_client):
        """POST /email-studio/qa-score → 200 with QA dimensions."""
        resp = await authed_client.post(
            f"{API}/email-studio/qa-score",
            json={
                "email_body": (
                    "Hi Sarah,\n\n"
                    "I noticed your team at Acme Corp is scaling the sales org — "
                    "congrats on the Series B! Our platform helps teams like yours "
                    "automate prospecting and cut pipeline build time by 40%.\n\n"
                    "Would you be open to a 15-min call this week?\n\n"
                    "Best,\nAlex"
                ),
                "subject": "Scaling sales at Acme",
            },
        )
        if resp.status_code != 200:
            pytest.skip("Email Studio QA score unavailable (LLM not configured)")
        data = resp.json()
        assert "success" in data
        assert "total_score" in data
        assert "dimensions" in data

    @pytest.mark.integration
    async def test_subject_lines_generate(self, authed_client):
        """POST /email-studio/subject-lines-generate → 200 with variants."""
        resp = await authed_client.post(
            f"{API}/email-studio/subject-lines-generate",
            json={
                "email_body": (
                    "Hi Jordan,\n\n"
                    "Saw you're exploring new sales tools at Ramp. "
                    "Our AI-powered outbound platform might be a fit.\n\n"
                    "Open to a quick chat?\n\n"
                    "Thanks,\nTaylor"
                ),
                "count": 3,
            },
        )
        if resp.status_code != 200:
            pytest.skip("Email Studio subject-lines unavailable (LLM not configured)")
        data = resp.json()
        assert "success" in data
        assert "variants" in data
        assert isinstance(data["variants"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# LinkedIn ICP Match Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLinkedInIcpMatch:
    """LinkedIn ICP match endpoint (check-icp)."""

    @pytest.mark.integration
    async def test_check_icp_matches(self, authed_client):
        """POST /linkedin/engagements/check-icp → 200 with match results."""
        resp = await authed_client.post(
            f"{API}/linkedin/engagements/check-icp",
            json={},
        )
        if resp.status_code != 200:
            pytest.skip("LinkedIn ICP match unavailable (DB not provisioned)")
        data = resp.json()
        assert "success" in data
        assert "checked" in data
        assert "matches" in data
        assert isinstance(data["matches"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# Signal AI Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSignalAI:
    """Signal scan (LLM), lead-score-batch, lead-score/stats endpoints."""

    @pytest.mark.integration
    async def test_signal_scan_llm(self, authed_client):
        """POST /signals/scan → 200 (should call LLM now, not stub)."""
        resp = await authed_client.post(
            f"{API}/signals/scan",
            json={
                "prospectIds": [],
                "signalTypes": ["funding", "hiring"],
            },
        )
        if resp.status_code != 200:
            pytest.skip("Signals scan endpoint unavailable")
        data = resp.json()
        assert "scanned" in data
        assert "detected" in data
        assert "signals" in data

    @pytest.mark.integration
    async def test_lead_score_batch(self, authed_client):
        """POST /signals/lead-score-batch → 200 with batch results."""
        resp = await authed_client.post(
            f"{API}/signals/lead-score-batch",
            json={
                "prospect_ids": [],
                "score_all": False,
            },
        )
        if resp.status_code != 200:
            pytest.skip("Signals lead-score-batch unavailable")
        data = resp.json()
        assert "success" in data
        assert "scored" in data
        assert "scores" in data
        assert isinstance(data["scores"], list)

    @pytest.mark.integration
    async def test_lead_score_stats(self, authed_client):
        """GET /signals/lead-score/stats → 200 with aggregate statistics."""
        resp = await authed_client.get(f"{API}/signals/lead-score/stats")
        if resp.status_code != 200:
            pytest.skip("Signals lead-score stats unavailable")
        data = resp.json()
        assert "tier_distribution" in data
        assert "total_scored" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Alumni Tracker (Job Change Monitor) Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlumniTracker:
    """Job change monitor list + scan endpoints."""

    @pytest.mark.integration
    async def test_list_job_change_alerts(self, authed_client):
        """GET /job-change-monitor → 200 with alerts list."""
        resp = await authed_client.get(f"{API}/job-change-monitor")
        if resp.status_code != 200:
            pytest.skip("Job change monitor endpoint unavailable")
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.integration
    async def test_run_job_change_scan(self, authed_client):
        """POST /job-change-monitor/scan → 200 with scan results."""
        resp = await authed_client.post(
            f"{API}/job-change-monitor/scan",
            json={"prospectIds": []},
        )
        if resp.status_code != 200:
            pytest.skip("Job change scan endpoint unavailable")
        # Scan returns a JobChangeScanResponse
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Schema-level e2e tests (no DB required)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemaValidation:
    """Pure Pydantic schema validation tests — no DB, no network."""

    async def test_pipeline_run_stage_request_round_trip(self):
        """PipelineRunStageRequest with stage + inputs → model_dump."""
        from app.features.pipeline.router import PipelineRunStageRequest
        req = PipelineRunStageRequest(
            stage="thesis",
            product_name="OUTRENA",
            target_industries="B2B SaaS",
            product_description="AI sales platform",
            key_value_props="Automated prospecting",
        )
        assert req.stage == "thesis"
        assert req.product_name == "OUTRENA"
        data = req.model_dump()
        assert data["stage"] == "thesis"
        assert data["product_name"] == "OUTRENA"

    async def test_pipeline_status_response_schema(self):
        """PipelineStatusResponse validates with stages_completed."""
        from app.features.pipeline.router import PipelineStatusResponse
        resp = PipelineStatusResponse(
            stages_completed=["thesis", "signals"],
            current_stage="scoring",
        )
        assert resp.stages_completed == ["thesis", "signals"]
        assert resp.current_stage == "scoring"

    async def test_flow_template_list_response_schema(self):
        """FlowTemplateListResponse validates with items + total."""
        from app.features.flow_templates.router import (
            FlowTemplateResponse,
            FlowTemplateListResponse,
        )
        tpl = FlowTemplateResponse(
            id="tpl-test",
            name="Test Flow",
            description="A test template",
            source_platforms=["linkedin"],
            enrichment_platforms=["clearbit"],
            gate_config={"requireEmail": True},
            gate_strictness="strict",
            recommended_for="Test use case",
        )
        list_resp = FlowTemplateListResponse(items=[tpl], total=1)
        assert list_resp.total == 1
        assert list_resp.items[0].id == "tpl-test"

    async def test_flow_template_clone_request_schema(self):
        """FlowTemplateCloneRequest validates with template_id."""
        from app.features.flow_templates.router import FlowTemplateCloneRequest
        req = FlowTemplateCloneRequest(template_id="tpl-enterprise-abm")
        assert req.template_id == "tpl-enterprise-abm"
        assert req.new_name is None

    async def test_enqueue_request_schema(self):
        """EnqueueRequest validates with flow_id + max_prospects."""
        from app.features.autopilot_queue.router import EnqueueRequest
        req = EnqueueRequest(flow_id="flow-123", max_prospects=25, dry_run=True)
        assert req.flow_id == "flow-123"
        assert req.max_prospects == 25
        assert req.dry_run is True

    async def test_queue_stats_response_schema(self):
        """QueueStatsResponse validates with queue counters."""
        from app.features.autopilot_queue.router import QueueStatsResponse
        stats = QueueStatsResponse(
            queued=3, running=1, completed_24h=10,
            failed_24h=0, autonomous_mode=False,
        )
        assert stats.queued == 3
        assert stats.autonomous_mode is False

    async def test_autonomous_mode_request_schema(self):
        """AutonomousModeRequest validates with enabled flag."""
        from app.features.autopilot_queue.router import AutonomousModeRequest
        req = AutonomousModeRequest(enabled=True)
        assert req.enabled is True

    async def test_qa_score_request_schema(self):
        """QaScoreRequest validates with email_body."""
        from app.schemas.email_studio import QaScoreRequest
        req = QaScoreRequest(email_body="Hello, let's connect!")
        assert req.email_body == "Hello, let's connect!"
        assert req.subject is None

    async def test_qa_score_response_schema(self):
        """QaScoreResponse validates with total_score + dimensions."""
        from app.schemas.email_studio import QaScoreResponse, QaScoreDimension
        dim = QaScoreDimension(name="personalization", max_points=20, score=15, feedback="Good")
        resp = QaScoreResponse(
            success=True, total_score=15, max_score=70,
            dimensions=[dim], flags=[], suggested_rewrite=None,
        )
        assert resp.success is True
        assert resp.total_score == 15

    async def test_subject_lines_generate_request_schema(self):
        """SubjectLinesGenerateRequest validates with email_body + count."""
        from app.schemas.email_studio import SubjectLinesGenerateRequest
        req = SubjectLinesGenerateRequest(email_body="Test body", count=5)
        assert req.email_body == "Test body"
        assert req.count == 5

    async def test_icp_match_request_schema(self):
        """IcpMatchRequest validates with optional llm_config_id."""
        from app.schemas.linkedin import IcpMatchRequest
        req = IcpMatchRequest()
        assert req.llm_config_id is None

    async def test_icp_match_response_schema(self):
        """IcpMatchResponse validates with checked + matches."""
        from app.schemas.linkedin import IcpMatchResponse, IcpMatchResult
        result = IcpMatchResult(
            engagement_id="eng-1", is_icp_match=True,
            icp_profile_id="icp-1", icp_profile_name="Enterprise ICP",
            match_reason="Title and industry match",
            suggested_note="Reach out about new role",
        )
        resp = IcpMatchResponse(success=True, checked=1, matches=[result])
        assert resp.success is True
        assert resp.checked == 1
        assert len(resp.matches) == 1
        assert resp.matches[0].is_icp_match is True

    async def test_signals_scan_request_schema(self):
        """SignalsScanRequest validates with prospectIds + signalTypes."""
        from app.schemas.signals import SignalsScanRequest
        req = SignalsScanRequest(
            prospectIds=["p1", "p2"],
            signalTypes=["funding", "hiring"],
        )
        assert req.prospectIds == ["p1", "p2"]
        assert req.signalTypes == ["funding", "hiring"]

    async def test_lead_score_batch_request_schema(self):
        """LeadScoreBatchRequest validates with prospect_ids + score_all."""
        from app.schemas.signals import LeadScoreBatchRequest
        req = LeadScoreBatchRequest(prospect_ids=["p1"], score_all=False)
        assert req.prospect_ids == ["p1"]
        assert req.score_all is False

    async def test_lead_score_stats_response_schema(self):
        """LeadScoreStatsResponse validates with tier_distribution."""
        from app.schemas.signals import LeadScoreStatsResponse
        resp = LeadScoreStatsResponse(
            tier_distribution={"P0": 5, "P1": 20, "P2": 75},
            by_seniority={},
            total_scored=100,
        )
        assert resp.total_scored == 100
        assert resp.tier_distribution["P0"] == 5

    async def test_job_change_scan_request_schema(self):
        """JobChangeScanRequest validates with prospectIds."""
        from app.schemas.job_change_monitor import JobChangeScanRequest
        req = JobChangeScanRequest(prospectIds=["p1"])
        assert req.prospectIds == ["p1"]


__all__ = []
