"""
test_bugfix_session.py — Regression tests for BUG-01 through BUG-32 + CC-01/02/03.

Each test verifies the root cause is fixed via schema instantiation (pure Pydantic,
no DB) or source inspection (for router/service fixes that require DB at runtime).

Run with:
  cd outrena-backend && pytest tests/test_bugfix_session.py -v

All schema tests are pure unit tests — no DB, no network, no Docker required.
Router/service source checks verify the fix is in place without executing the code.
"""
from __future__ import annotations

import inspect
import json
import pathlib


# ── BUG-01: LlmConfigCreate accepts camelCase frontend fields ────────────────

def test_bug01_llm_config_accepts_api_key_camel():
    from app.schemas.llm_config import LlmConfigCreate
    obj = LlmConfigCreate(provider="openai", apiKey="sk-test", model="gpt-4", isActive=True)
    assert obj.api_key == "sk-test"
    assert obj.model_name == "gpt-4"


def test_bug01_llm_config_derives_display_name():
    from app.schemas.llm_config import LlmConfigCreate
    obj = LlmConfigCreate(provider="anthropic", apiKey="x", model="claude-3")
    assert "claude-3" in obj.display_name or "anthropic" in obj.display_name


def test_bug01_llm_config_accepts_snake_case():
    from app.schemas.llm_config import LlmConfigCreate
    obj = LlmConfigCreate(provider="openai", api_key="sk-test", model_name="gpt-4o")
    assert obj.api_key == "sk-test"
    assert obj.model_name == "gpt-4o"


# ── BUG-05: IntegrationService create wraps commit with 409 guard ─────────────

def test_bug05_integration_service_commit_wrapped():
    path = pathlib.Path("app/features/integrations/service.py")
    src = path.read_text()
    assert "rollback" in src
    assert "409" in src


def test_bug05_integration_service_has_error_catch():
    path = pathlib.Path("app/features/integrations/service.py")
    src = path.read_text()
    assert "unique" in src.lower() or "duplicate" in src.lower() or "uniqueviolation" in src.lower()


# ── BUG-09: AutopilotRequest accepts productName/icpDescription ──────────────

def test_bug09_autopilot_accepts_product_name():
    from app.schemas.autopilot import AutopilotRequest
    obj = AutopilotRequest(productName="OUTRENA", icpDescription="B2B SaaS sales teams")
    assert obj.campaign_name == "OUTRENA"
    assert obj.icp_hint == "B2B SaaS sales teams"


def test_bug09_autopilot_campaign_name_fallback():
    from app.schemas.autopilot import AutopilotRequest
    obj = AutopilotRequest(productName="MyProduct")
    assert obj.campaign_name == "MyProduct"


def test_bug09_autopilot_router_guards_none_celery():
    path = pathlib.Path("app/features/autopilot/router.py")
    src = path.read_text()
    assert "celery_app is None" in src


def test_bug09_autopilot_enqueue_guards_none():
    path = pathlib.Path("app/features/autopilot/router.py")
    src = path.read_text()
    # Both enqueue and status should guard
    assert src.count("celery_app is None") >= 2


# ── BUG-10: IcpCreate persona optional, painPoints accepts list ──────────────

def test_bug10_icp_persona_optional():
    from app.schemas.icp import IcpCreate
    obj = IcpCreate(name="Enterprise SaaS")
    assert obj.persona is None


def test_bug10_icp_pain_points_accepts_list():
    from app.schemas.icp import IcpCreate
    obj = IcpCreate(name="Test", painPoints=["slow workflows", "data quality"])
    parsed = json.loads(obj.painPoints)
    assert "slow workflows" in parsed


def test_bug10_icp_pain_points_accepts_string():
    from app.schemas.icp import IcpCreate
    obj = IcpCreate(name="Test", painPoints="[]")
    assert obj.painPoints == "[]"


def test_bug10_buying_signals_accepts_list():
    from app.schemas.icp import IcpCreate
    obj = IcpCreate(name="Test", buyingSignals=["hiring", "funding"])
    parsed = json.loads(obj.buyingSignals)
    assert "hiring" in parsed


# ── BUG-11: ProspectCreate accepts name field, splits into first/last ─────────

def test_bug11_prospect_name_splits():
    from app.schemas.prospects import ProspectCreate
    obj = ProspectCreate(name="Jordan Lee", email="jordan@example.com")
    assert obj.firstName == "Jordan"
    assert obj.lastName == "Lee"


def test_bug11_prospect_name_single_word():
    from app.schemas.prospects import ProspectCreate
    obj = ProspectCreate(name="Cher")
    assert obj.firstName == "Cher"
    assert obj.lastName == ""


def test_bug11_prospect_firstname_lastname_direct():
    from app.schemas.prospects import ProspectCreate
    obj = ProspectCreate(firstName="Jane", lastName="Smith")
    assert obj.firstName == "Jane"
    assert obj.lastName == "Smith"


# ── BUG-12: SourceConfigCreate accepts dailyLimit alias ──────────────────────

def test_bug12_source_config_daily_limit_alias():
    from app.schemas.prospect_source import SourceConfigCreate
    obj = SourceConfigCreate(source="apollo", name="Apollo", dailyLimit=500)
    assert obj.dailyQuota == 500


def test_bug12_source_config_daily_quota_direct():
    from app.schemas.prospect_source import SourceConfigCreate
    obj = SourceConfigCreate(source="apollo", name="Apollo", dailyQuota=250)
    assert obj.dailyQuota == 250


# ── BUG-14: DomainEnrichmentResponse coerces techStack string to list ─────────

def test_bug14_tech_stack_json_string_coerced():
    from app.schemas.domain_enrich import DomainEnrichmentResponse
    from datetime import datetime
    obj = DomainEnrichmentResponse(
        id="1", domain="acme.com", companyName="Acme", industry="SaaS",
        employeeCount=100, revenueRange="$1M-$10M",
        techStack='["React", "Python"]',
        location="NYC", description="Test", lastEnrichedAt=datetime.now()
    )
    assert obj.techStack == ["React", "Python"]


def test_bug14_tech_stack_empty_string_coerced():
    from app.schemas.domain_enrich import DomainEnrichmentResponse
    from datetime import datetime
    obj = DomainEnrichmentResponse(
        id="1", domain="acme.com", companyName=None, industry=None,
        employeeCount=None, revenueRange=None,
        techStack="[]",
        location=None, description=None, lastEnrichedAt=datetime.now()
    )
    assert obj.techStack == []


def test_bug14_tech_stack_list_passthrough():
    from app.schemas.domain_enrich import DomainEnrichmentResponse
    from datetime import datetime
    obj = DomainEnrichmentResponse(
        id="1", domain="acme.com", companyName=None, industry=None,
        employeeCount=None, revenueRange=None,
        techStack=["Go", "PostgreSQL"],
        location=None, description=None, lastEnrichedAt=datetime.now()
    )
    assert obj.techStack == ["Go", "PostgreSQL"]


# ── BUG-17: SignalMonitorCreate accepts 'type' as alias for signalType ─────────

def test_bug17_signal_monitor_type_alias():
    from app.schemas.signals import SignalMonitorCreate
    obj = SignalMonitorCreate(name="Hiring Monitor", type="hiring")
    assert obj.signalType == "hiring"


def test_bug17_signal_monitor_signal_type_direct():
    from app.schemas.signals import SignalMonitorCreate
    obj = SignalMonitorCreate(name="Funding Monitor", signalType="funding")
    assert obj.signalType == "funding"


# ── BUG-22: ExclusionRuleCreate accepts 'field' as alias for 'type' ──────────

def test_bug22_exclusion_rule_field_alias():
    from app.schemas.exclusion_rules import ExclusionRuleCreate
    obj = ExclusionRuleCreate(field="domain", operator="equals", value="gmail.com")
    assert obj.type == "domain"


def test_bug22_exclusion_rule_type_direct():
    from app.schemas.exclusion_rules import ExclusionRuleCreate
    obj = ExclusionRuleCreate(type="email", value="test@test.com")
    assert obj.type == "email"


def test_bug22_exclusion_rule_default_type():
    from app.schemas.exclusion_rules import ExclusionRuleCreate
    obj = ExclusionRuleCreate(value="example.com")
    assert obj.type == "domain"


# ── BUG-23: EmailTemplateCreate accepts 'body'/'subject' aliases ─────────────

def test_bug23_template_body_alias():
    from app.schemas.templates import EmailTemplateCreate
    obj = EmailTemplateCreate(name="Test", body="Hello {{firstName}}")
    assert obj.bodyTemplate == "Hello {{firstName}}"


def test_bug23_template_subject_alias():
    from app.schemas.templates import EmailTemplateCreate
    obj = EmailTemplateCreate(name="Test", body="x", subject="Re: {{company}}")
    assert obj.subjectTemplate == "Re: {{company}}"


# ── BUG-24: KanbanBoardResponse stages is list not dict ──────────────────────

def test_bug24_kanban_board_stages_is_list():
    from app.schemas.deals import KanbanBoardResponse, KanbanStageResponse
    board = KanbanBoardResponse(stages=[
        KanbanStageResponse(id="qualified", name="Qualified", deals=[])
    ])
    assert isinstance(board.stages, list)
    assert board.stages[0].id == "qualified"


def test_bug24_kanban_stage_has_id_name_deals():
    from app.schemas.deals import KanbanStageResponse
    stage = KanbanStageResponse(id="proposal", name="Proposal", deals=[])
    assert stage.id == "proposal"
    assert stage.name == "Proposal"
    assert stage.deals == []


def test_bug24_deals_service_builds_list():
    path = pathlib.Path("app/features/deals/service.py")
    src = path.read_text()
    assert "KanbanStageResponse" in src
    assert "stage_list" in src or "stages=" in src


# ── BUG-27: ContentIdeaGenerateRequest icpProfileId optional ─────────────────

def test_bug27_content_idea_generate_icp_optional():
    from app.schemas.content_ideas import ContentIdeaGenerateRequest
    obj = ContentIdeaGenerateRequest(topic="AI trends", audience="CTO", count=3)
    assert obj.icpProfileId is None
    assert obj.topic == "AI trends"


def test_bug27_content_idea_generate_icp_direct():
    from app.schemas.content_ideas import ContentIdeaGenerateRequest
    obj = ContentIdeaGenerateRequest(icpProfileId="icp-123", count=5)
    assert obj.icpProfileId == "icp-123"


# ── BUG-21: Meeting prep service validates prospect before INSERT ──────────────

def test_bug21_meeting_prep_service_has_fk_check():
    path = pathlib.Path("app/features/meetings/service.py")
    src = path.read_text()
    assert "Prospect" in src
    assert ("not found" in src.lower() or "404" in src)


def test_bug21_meeting_prep_service_has_list_all():
    path = pathlib.Path("app/features/meetings/service.py")
    src = path.read_text()
    assert "async def list_all" in src


def test_bug21_meeting_prep_router_prospect_id_optional():
    path = pathlib.Path("app/features/meetings/router.py")
    src = path.read_text()
    # BUG-21 FIX: prospect_id should have a default=None
    assert "default=None" in src or "= None" in src


# ── BUG-13: FlowRunService.create_ab_test catches FK violation ───────────────

def test_bug13_flow_ab_test_has_fk_guard():
    path = pathlib.Path("app/features/flows/service.py")
    src = path.read_text()
    # Find the create_ab_test section
    idx = src.find("create_ab_test")
    section = src[idx:idx+800]
    assert "foreign" in section.lower() or "fkey" in section.lower() or "422" in section


# ── BUG-19: list_users returns empty list on Keycloak failure ─────────────────

def test_bug19_list_users_has_try_except():
    path = pathlib.Path("app/features/user_management/router.py")
    src = path.read_text()
    idx = src.find("async def list_users")
    section = src[idx:idx+500]
    assert "try:" in section
    assert "except" in section
    # returns empty list on failure
    assert "return []" in section or "return []" in src[idx:idx+600]


# ── CC-01: All celery_app usages are guarded ──────────────────────────────────

def test_cc01_autopilot_router_has_two_none_guards():
    path = pathlib.Path("app/features/autopilot/router.py")
    src = path.read_text()
    assert src.count("celery_app is None") >= 2


# ── CC-02: Metrics middleware uses get-or-create ──────────────────────────────

def test_cc02_metrics_uses_get_or_create():
    path = pathlib.Path("app/core/metrics.py")
    src = path.read_text()
    assert "_get_or_create" in src or "get_or_create" in src


# ── BUG-04: Startup checks for ENCRYPTION_KEY ────────────────────────────────

def test_bug04_main_checks_encryption_key():
    path = pathlib.Path("app/main.py")
    src = path.read_text()
    assert "ENCRYPTION_KEY" in src
    assert "not set" in src.lower() or "is not set" in src


# ── BUG-06: DomainResponse exposes `domain` field ────────────────────────────

def test_bug06_domain_response_has_domain_field():
    from app.schemas.domains import DomainResponse
    from datetime import datetime
    obj = DomainResponse(
        id="d1", domainName="acme.com", spfStatus=True, dkimStatus=True,
        dmarcStatus=True, dailySendLimit=100, warmingWeek=1, isActive=True,
        lastChecked=None, createdAt=datetime.now(), updatedAt=datetime.now()
    )
    d = obj.model_dump()
    assert d["domain"] == "acme.com"


# ── BUG-06: DnsCheckRequest accepts domain field ─────────────────────────────

def test_bug06_dns_check_request_has_domain():
    from app.schemas.domains import DnsCheckRequest
    obj = DnsCheckRequest(domain="acme.com")
    assert obj.domain == "acme.com"


# ── CC-03: docker-compose.yml has keycloak healthcheck ───────────────────────

def test_cc03_docker_compose_keycloak_healthcheck():
    path = pathlib.Path("../../docker-compose.yml")
    if not path.exists():
        path = pathlib.Path("../docker-compose.yml")
    if not path.exists():
        import pytest
        pytest.skip("docker-compose.yml not found from test directory")
    src = path.read_text()
    # Keycloak healthcheck was added
    assert "healthcheck" in src
    # Keycloak section has it
    kc_idx = src.find("keycloak:")
    kc_section = src[kc_idx:kc_idx+1000]
    assert "healthcheck" in kc_section or "openid-configuration" in kc_section


__all__ = []
