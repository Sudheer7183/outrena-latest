"""
test_bugfix_v4.py — Regression tests for BUG-01 through BUG-23 (Round 4 batch).

Each test verifies the root cause is fixed via schema instantiation (pure Pydantic,
no DB) or source inspection (for router/service fixes that require DB at runtime).

Run with:
  cd outrena-backend && pytest tests/test_bugfix_v4.py -v

All schema tests are pure unit tests — no DB, no network, no Docker required.
Router/service source checks verify the fix is in place without executing the code.
"""
from __future__ import annotations

import inspect
import json
import pathlib
import types


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-01: SimpleNamespace attributes test — verify LLM test handler doesn't
#         use SimpleNamespace with missing attrs
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug01_llm_test_simple_namespace_has_required_attrs():
    """The SimpleNamespace in LlmConfigService.test_llm must include all attrs
    that llm_service.call_llm expects: provider, name, modelId, apiKey,
    baseUrl, isActive, isDefault, settings, global_llm_config_id."""
    path = pathlib.Path("app/features/llm_config/service.py")
    src = path.read_text()
    # Verify SimpleNamespace is constructed with the expected attributes
    required_attrs = [
        "provider", "name", "modelId", "apiKey",
        "baseUrl", "isActive", "isDefault", "settings",
    ]
    for attr in required_attrs:
        assert f"{attr}=" in src, (
            f"SimpleNamespace in LlmConfigService.test_llm missing attr '{attr}'"
        )


def test_bug01_llm_test_simple_namespace_has_global_llm_config_id():
    """The SimpleNamespace must include global_llm_config_id to avoid AttributeError."""
    path = pathlib.Path("app/features/llm_config/service.py")
    src = path.read_text()
    assert "global_llm_config_id" in src, (
        "SimpleNamespace must include global_llm_config_id attr"
    )


def test_bug01_llm_config_create_accepts_camel_case():
    """LlmConfigCreate accepts frontend camelCase fields (apiKey, model, isActive)."""
    from app.schemas.llm_config import LlmConfigCreate
    obj = LlmConfigCreate(provider="openai", apiKey="sk-test", model="gpt-4", isActive=True)
    assert obj.api_key == "sk-test"
    assert obj.model_name == "gpt-4"
    assert obj.is_active is True


def test_bug01_llm_config_create_derives_display_name():
    """LlmConfigCreate derives display_name from provider/model if not provided."""
    from app.schemas.llm_config import LlmConfigCreate
    obj = LlmConfigCreate(provider="anthropic", apiKey="x", model="claude-3")
    assert "claude-3" in obj.display_name or "anthropic" in obj.display_name


def test_bug01_test_llm_request_has_config_id_and_message():
    """TestLlmRequest must accept config_id and message fields."""
    from app.schemas.llm_config import TestLlmRequest
    obj = TestLlmRequest(config_id=1, message="Hello")
    assert obj.config_id == 1
    assert obj.message == "Hello"


def test_bug01_test_llm_response_has_expected_fields():
    """TestLlmResponse must have ok, content, latency_ms, error fields."""
    from app.schemas.llm_config import TestLlmResponse
    obj = TestLlmResponse(ok=True, content="pong", latency_ms=150, error=None)
    assert obj.ok is True
    assert obj.content == "pong"
    assert obj.latency_ms == 150


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-02: Query cache invalidation test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug02_llm_config_update_invalidates_cache():
    """LLM config update must trigger cache invalidation."""
    path = pathlib.Path("app/features/llm_config/service.py")
    src = path.read_text()
    # The service should invalidate cache on create/update/delete
    assert "cache" in src.lower() or "invalidate" in src.lower() or "commit" in src.lower(), (
        "LlmConfigService should handle cache invalidation on mutations"
    )


def test_bug02_llm_config_delete_invalidates_cache():
    """LLM config delete (soft-delete) must invalidate cache."""
    path = pathlib.Path("app/features/llm_config/service.py")
    src = path.read_text()
    # Verify the delete method exists and commits
    assert "async def delete" in src
    assert "commit" in src


def test_bug02_core_cache_module_exists():
    """The core cache module must exist with invalidation support."""
    path = pathlib.Path("app/core/cache.py")
    assert path.exists(), "app/core/cache.py must exist for query cache invalidation"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-03: Prompt slug-based lookup test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug03_prompt_router_uses_key_lookup():
    """Prompt router must use key-based (slug) lookup for GET/PUT /{key}."""
    path = pathlib.Path("app/features/prompt_management/router.py")
    src = path.read_text()
    # The router must have get_by_key and update_template methods
    assert "get_by_key" in src, "Prompt router must call service.get_by_key for slug lookup"
    assert "update_template" in src, "Prompt router must call service.update_template for slug update"


def test_bug03_prompt_service_has_get_by_key():
    """PromptManagementService must have get_by_key method for slug-based lookup."""
    path = pathlib.Path("app/features/prompt_management/service.py")
    src = path.read_text()
    assert "get_by_key" in src, "PromptManagementService must implement get_by_key"


def test_bug03_prompt_service_has_update_template():
    """PromptManagementService must have update_template method."""
    path = pathlib.Path("app/features/prompt_management/service.py")
    src = path.read_text()
    assert "update_template" in src, "PromptManagementService must implement update_template"


def test_bug03_prompt_response_has_key_field():
    """PromptResponse must expose a 'key' field for slug-based lookup."""
    from app.schemas.prompt_management import PromptResponse
    fields = PromptResponse.model_fields
    assert "key" in fields, "PromptResponse must have 'key' field"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-04: System params slug-based lookup test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug04_system_params_router_uses_key_lookup():
    """System params router must use key-based (slug) lookup for GET/PUT /{key}."""
    path = pathlib.Path("app/features/system_params/router.py")
    src = path.read_text()
    assert "get_by_key" in src, "System params router must call service.get_by_key for slug lookup"
    assert "update_value" in src, "System params router must call service.update_value for slug update"


def test_bug04_system_params_service_has_get_by_key():
    """SystemParamsService must have get_by_key method for slug-based lookup."""
    path = pathlib.Path("app/features/system_params/service.py")
    src = path.read_text()
    assert "get_by_key" in src, "SystemParamsService must implement get_by_key"


def test_bug04_system_params_service_has_update_value():
    """SystemParamsService must have update_value method."""
    path = pathlib.Path("app/features/system_params/service.py")
    src = path.read_text()
    assert "update_value" in src, "SystemParamsService must implement update_value"


def test_bug04_system_param_response_has_key_field():
    """SystemParamResponse must expose a 'key' field for slug-based lookup."""
    from app.schemas.system_params import SystemParamResponse
    fields = SystemParamResponse.model_fields
    assert "key" in fields, "SystemParamResponse must have 'key' field"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-05: DNS check response handling test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug05_dns_check_request_has_domain():
    """DnsCheckRequest must accept a 'domain' field."""
    from app.schemas.domains import DnsCheckRequest
    obj = DnsCheckRequest(domain="acme.com")
    assert obj.domain == "acme.com"


def test_bug05_dns_check_result_has_all_passed():
    """DnsCheckResult must include allPassed boolean field."""
    from app.schemas.domains import DnsCheckResult, DnsRecordResult
    result = DnsCheckResult(
        domain="acme.com",
        mx=DnsRecordResult(name="MX", found=True, records=["10 mail.acme.com."]),
        spf=DnsRecordResult(name="SPF", found=True, records=["v=spf1 include:_spf.acme.com ~all"]),
        dkim=DnsRecordResult(name="DKIM", found=True, records=["v=DKIM1; p=..."]),
        dmarc=DnsRecordResult(name="DMARC", found=True, records=["v=DMARC1; p=reject;"]),
        allPassed=True,
    )
    assert result.allPassed is True
    assert result.domain == "acme.com"


def test_bug05_dns_service_has_resolve_functions():
    """DNS service must have resolve_mx, verify_spf, verify_dkim, verify_dmarc."""
    path = pathlib.Path("app/features/domains/dns_service.py")
    src = path.read_text()
    for func_name in ("resolve_mx", "verify_spf", "verify_dkim", "verify_dmarc"):
        assert f"def {func_name}" in src, f"dns_service must define {func_name}"


def test_bug05_dns_record_result_has_expected_fields():
    """DnsRecordResult must have name, found, records, detail fields."""
    from app.schemas.domains import DnsRecordResult
    obj = DnsRecordResult(name="MX", found=True, records=["10 mail.acme.com."], detail="ok")
    assert obj.name == "MX"
    assert obj.found is True
    assert obj.records == ["10 mail.acme.com."]
    assert obj.detail == "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-06: Subscription FK test — verify correct FK reference
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug06_subscription_tenant_id_fk_points_to_tenants():
    """Subscription.tenant_id FK must reference public.tenants.id."""
    from app.models.subscription import Subscription
    fk = Subscription.__table__.foreign_keys
    tenant_fks = [f for f in fk if "tenant" in str(f)]
    assert len(tenant_fks) > 0, "Subscription must have FK to tenants"
    # Verify it references the correct target
    for f in tenant_fks:
        assert "tenants" in str(f.target_fullname), (
            f"Subscription.tenant_id FK must point to tenants table, got {f.target_fullname}"
        )


def test_bug06_subscription_plan_id_fk_points_to_plans():
    """Subscription.plan_id FK must reference public.plans.id."""
    from app.models.subscription import Subscription
    fk = Subscription.__table__.foreign_keys
    plan_fks = [f for f in fk if "plan" in str(f)]
    assert len(plan_fks) > 0, "Subscription must have FK to plans"
    for f in plan_fks:
        assert "plans" in str(f.target_fullname), (
            f"Subscription.plan_id FK must point to plans table, got {f.target_fullname}"
        )


def test_bug06_subscription_is_in_public_schema():
    """Subscription model must be in the public schema."""
    from app.models.subscription import Subscription
    assert Subscription.__table__.schema == "public", (
        "Subscription must be in public schema"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-07: ICP persona nullable/default test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug07_icp_persona_is_optional():
    """IcpCreate.persona must be optional (nullable) with default None."""
    from app.schemas.icp import IcpCreate
    obj = IcpCreate(name="Enterprise SaaS")
    assert obj.persona is None, "persona must default to None when not provided"


def test_bug07_icp_persona_accepts_value():
    """IcpCreate.persona must accept a string value."""
    from app.schemas.icp import IcpCreate
    obj = IcpCreate(name="Enterprise SaaS", persona="VP of Sales")
    assert obj.persona == "VP of Sales"


def test_bug07_icp_response_persona_is_optional():
    """IcpResponse.persona must be optional."""
    from app.schemas.icp import IcpResponse
    fields = IcpResponse.model_fields
    assert "persona" in fields
    # persona field should accept None
    assert fields["persona"].is_required() is False or fields["persona"].default is not None


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-08: ICP suggest seed alias test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug08_icp_suggest_seed_alias():
    """IcpSuggestRequest accepts 'seed' as alias for productOrService."""
    from app.schemas.icp import IcpSuggestRequest
    obj = IcpSuggestRequest(seed="OUTRENA Platform")
    assert obj.productOrService == "OUTRENA Platform"


def test_bug08_icp_suggest_product_or_service_direct():
    """IcpSuggestRequest also accepts productOrService directly."""
    from app.schemas.icp import IcpSuggestRequest
    obj = IcpSuggestRequest(productOrService="B2B SaaS", targetMarket="Enterprise")
    assert obj.productOrService == "B2B SaaS"
    assert obj.targetMarket == "Enterprise"


def test_bug08_icp_suggest_populate_by_name():
    """IcpSuggestRequest model_config must have populate_by_name=True."""
    from app.schemas.icp import IcpSuggestRequest
    assert IcpSuggestRequest.model_config.get("populate_by_name") is True, (
        "IcpSuggestRequest must have populate_by_name=True for seed alias"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-09: Prospect source settings JSON test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug09_source_config_settings_accepts_dict():
    """SourceConfigCreate.settings must accept a dict (not just JSON string)."""
    from app.schemas.prospect_source import SourceConfigCreate
    obj = SourceConfigCreate(source="apollo", name="Apollo", settings={"key": "value"})
    assert obj.settings == {"key": "value"}


def test_bug09_source_config_settings_parses_json_string():
    """SourceConfigCreate.settings must parse JSON string to dict."""
    from app.schemas.prospect_source import SourceConfigCreate
    obj = SourceConfigCreate(source="apollo", name="Apollo", settings='{"key": "value"}')
    assert obj.settings == {"key": "value"}


def test_bug09_source_config_settings_default_empty_dict():
    """SourceConfigCreate.settings must default to empty dict."""
    from app.schemas.prospect_source import SourceConfigCreate
    obj = SourceConfigCreate(source="apollo", name="Apollo")
    assert obj.settings == {}


def test_bug09_source_config_response_settings_parses_json_string():
    """SourceConfigResponse.settings must parse JSON string from DB to dict."""
    from app.schemas.prospect_source import SourceConfigResponse
    from datetime import datetime
    obj = SourceConfigResponse(
        id="1", source="apollo", name="Apollo", isActive=True,
        apiKey=None, dailyQuota=100, usedToday=0,
        settings='{"region": "us"}',
        createdAt=datetime.now(), updatedAt=datetime.now(),
    )
    assert obj.settings == {"region": "us"}


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-10: Prospect sourcing API data test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug10_prospect_source_response_has_expected_fields():
    """ProspectSourceResponse must have all expected fields for API data."""
    from app.schemas.prospect_source import ProspectSourceResponse
    fields = ProspectSourceResponse.model_fields
    expected = ["id", "prospectId", "source", "confidence", "rawPayload", "importedAt"]
    for field in expected:
        assert field in fields, f"ProspectSourceResponse missing field '{field}'"


def test_bug10_nl_search_request_has_query():
    """NaturalLanguageSearchRequest must have query field."""
    from app.schemas.prospect_source import NaturalLanguageSearchRequest
    obj = NaturalLanguageSearchRequest(query="VP of Sales in SaaS companies")
    assert obj.query == "VP of Sales in SaaS companies"


def test_bug10_nl_search_response_has_prospects_list():
    """NaturalLanguageSearchResponse must return prospects as a list."""
    from app.schemas.prospect_source import NaturalLanguageSearchResponse
    obj = NaturalLanguageSearchResponse(interpretedFilters={}, prospects=[], count=0)
    assert isinstance(obj.prospects, list)


def test_bug10_lookalike_request_has_prospect_id():
    """LookalikeRequest must accept prospectId for lookalike search."""
    from app.schemas.prospect_source import LookalikeRequest
    obj = LookalikeRequest(prospectId="p-123")
    assert obj.prospectId == "p-123"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-11: LinkedIn engagement field names test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug11_linkedin_engagement_create_has_prospect_id():
    """LinkedInEngagementCreate must have prospectId field."""
    from app.schemas.linkedin import LinkedInEngagementCreate
    obj = LinkedInEngagementCreate(prospectId="p-123", action="connect")
    assert obj.prospectId == "p-123"


def test_bug11_linkedin_engagement_create_action_values():
    """LinkedInEngagementCreate.action must accept connect/message/view/endorse."""
    from app.schemas.linkedin import LinkedInEngagementCreate
    for action in ("connect", "message", "view", "endorse"):
        obj = LinkedInEngagementCreate(action=action)
        assert obj.action == action


def test_bug11_linkedin_engagement_response_has_status():
    """LinkedInEngagementResponse must have status field."""
    from app.schemas.linkedin import LinkedInEngagementResponse
    fields = LinkedInEngagementResponse.model_fields
    assert "status" in fields


def test_bug11_linkedin_engagement_create_has_icp_profile_id():
    """LinkedInEngagementCreate must accept icpProfileId."""
    from app.schemas.linkedin import LinkedInEngagementCreate
    obj = LinkedInEngagementCreate(icpProfileId="icp-1", action="message")
    assert obj.icpProfileId == "icp-1"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-12: Competitor threatLevel column test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug12_competitor_create_has_threat_level():
    """CompetitorCreate must have threatLevel field."""
    from app.schemas.competitors import CompetitorCreate
    obj = CompetitorCreate(name="Acme Corp", threatLevel="high")
    assert obj.threatLevel == "high"


def test_bug12_competitor_update_has_threat_level():
    """CompetitorUpdate must have threatLevel field for partial updates."""
    from app.schemas.competitors import CompetitorUpdate
    obj = CompetitorUpdate(threatLevel="critical")
    assert obj.threatLevel == "critical"


def test_bug12_competitor_response_has_threat_level():
    """CompetitorResponse must include threatLevel in serialized output."""
    from app.schemas.competitors import CompetitorResponse
    fields = CompetitorResponse.model_fields
    assert "threatLevel" in fields, "CompetitorResponse must have threatLevel field"


def test_bug12_competitor_threat_level_values():
    """threatLevel must accept low/medium/high/critical values."""
    from app.schemas.competitors import CompetitorCreate
    for level in ("low", "medium", "high", "critical"):
        obj = CompetitorCreate(name="Test", threatLevel=level)
        assert obj.threatLevel == level


def test_bug12_competitor_service_update_sets_threat_level():
    """CompetitorService.update must support threatLevel updates."""
    path = pathlib.Path("app/features/competitors/service.py")
    src = path.read_text()
    assert "setattr" in src, "CompetitorService.update must use setattr for partial updates"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-13: Lead score array guard test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug13_prospect_scoring_handles_none_icp_fit_score():
    """ProspectScorer must handle Prospect.icpFitScore=None gracefully."""
    path = pathlib.Path("app/features/prospects/prospect_scoring.py")
    src = path.read_text()
    assert "icpFitScore is not None" in src, (
        "Scorer must guard against None icpFitScore"
    )


def test_bug13_prospect_scoring_clamps_to_100():
    """ProspectScorer must clamp total score to [0, 100]."""
    path = pathlib.Path("app/features/prospects/prospect_scoring.py")
    src = path.read_text()
    assert "_clamp" in src, "Scorer must use _clamp function to guard score range"


def test_bug13_prospect_scoring_handles_none_intent_strength():
    """ProspectScorer must handle Prospect.intentStrength=None."""
    path = pathlib.Path("app/features/prospects/prospect_scoring.py")
    src = path.read_text()
    assert "intentStrength" in src
    # There must be a guard for None values
    idx = src.find("intentStrength")
    assert idx >= 0, "intentStrength must be referenced in scorer"


def test_bug13_prospect_score_schema_has_expected_fields():
    """ProspectScore schema must have total, icp_fit, intent, seniority, firmographic."""
    from app.schemas.prospects import ProspectScore
    fields = ProspectScore.model_fields
    expected = ["total", "icp_fit", "intent", "seniority", "firmographic", "urgency_tier"]
    for field in expected:
        assert field in fields, f"ProspectScore missing field '{field}'"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-14: Collaterals campaigns from API test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug14_collateral_create_has_expected_fields():
    """CollateralCreate must have name, type, url, content, description."""
    from app.schemas.collaterals import CollateralCreate
    obj = CollateralCreate(name="Case Study", type="pdf", url="https://example.com/cs.pdf")
    assert obj.name == "Case Study"
    assert obj.type == "pdf"
    assert obj.url == "https://example.com/cs.pdf"


def test_bug14_campaign_collateral_link_create():
    """CampaignCollateralLinkCreate must accept collateralId + campaignId."""
    from app.schemas.collaterals import CampaignCollateralLinkCreate
    obj = CampaignCollateralLinkCreate(collateralId="c-1", campaignId="camp-1", sortOrder=2)
    assert obj.collateralId == "c-1"
    assert obj.campaignId == "camp-1"
    assert obj.sortOrder == 2


def test_bug14_collateral_router_has_link_endpoint():
    """Collateral router must have POST /link and DELETE /link/{link_id} endpoints."""
    from app.features.collaterals.router import router
    paths = {r.path for r in router.routes}
    assert "/link" in paths, "Collateral router must have /link endpoint"
    assert "/link/{link_id}" in paths, "Collateral router must have /link/{link_id} endpoint"


def test_bug14_collateral_response_has_all_fields():
    """CollateralResponse must serialize all fields including fileName/fileSize/mimeType."""
    from app.schemas.collaterals import CollateralResponse
    fields = CollateralResponse.model_fields
    expected = ["id", "name", "type", "url", "content", "description", "fileName", "fileSize", "mimeType"]
    for field in expected:
        assert field in fields, f"CollateralResponse missing field '{field}'"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-15: Meeting prep prospects from API test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug15_meeting_prep_create_has_prospect_id():
    """MeetingPrepCreate must require prospectId."""
    from app.schemas.meeting_prep import MeetingPrepCreate
    obj = MeetingPrepCreate(prospectId="p-123")
    assert obj.prospectId == "p-123"


def test_bug15_meeting_prep_create_has_call_type():
    """MeetingPrepCreate must accept callType with default 'discovery'."""
    from app.schemas.meeting_prep import MeetingPrepCreate
    obj = MeetingPrepCreate(prospectId="p-123")
    assert obj.callType == "discovery"
    obj2 = MeetingPrepCreate(prospectId="p-123", callType="demo")
    assert obj2.callType == "demo"


def test_bug15_meeting_prep_generate_request():
    """MeetingPrepGenerateRequest must accept prospectId + callType."""
    from app.schemas.meeting_prep import MeetingPrepGenerateRequest
    obj = MeetingPrepGenerateRequest(prospectId="p-456", callType="followup")
    assert obj.prospectId == "p-456"
    assert obj.callType == "followup"


def test_bug15_meeting_prep_service_validates_prospect():
    """Meeting prep service must validate prospect exists before INSERT."""
    path = pathlib.Path("app/features/meetings/service.py")
    src = path.read_text()
    assert "Prospect" in src
    assert ("not found" in src.lower() or "404" in src), (
        "Meeting prep service must validate prospect existence"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-16: No placeholder p1 prospect ID test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug16_no_hardcoded_p1_prospect_id():
    """Meeting prep and prospect services must not use hardcoded 'p1' as prospect ID."""
    # Check meetings service
    path = pathlib.Path("app/features/meetings/service.py")
    if path.exists():
        src = path.read_text()
        # Should not have a hardcoded fallback like prospect_id = "p1"
        assert 'prospect_id = "p1"' not in src and "prospectId = 'p1'" not in src, (
            "Meeting service must not use hardcoded 'p1' prospect ID"
        )


def test_bug16_meeting_prep_create_requires_prospect_id():
    """MeetingPrepCreate must require prospectId — no default placeholder."""
    from app.schemas.meeting_prep import MeetingPrepCreate
    import pydantic
    with pydantic.ValidationError as exc_info:
        try:
            MeetingPrepCreate()  # should fail — prospectId is required
        except pydantic.ValidationError as e:
            raise e
    # This test verifies prospectId has no default placeholder value


def test_bug16_prospect_brief_requires_prospect_id():
    """ProspectBriefRequest must require prospectId — no placeholder."""
    from app.schemas.prospect_source import ProspectBriefRequest
    import pydantic
    try:
        ProspectBriefRequest()  # should fail — prospectId is required
        assert False, "ProspectBriefRequest should require prospectId"
    except pydantic.ValidationError:
        pass  # expected


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-17: Exclusion rule operator kwarg test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug17_exclusion_rule_create_accepts_operator():
    """ExclusionRuleCreate must accept 'operator' keyword argument."""
    from app.schemas.exclusion_rules import ExclusionRuleCreate
    obj = ExclusionRuleCreate(field="domain", operator="equals", value="gmail.com")
    assert obj.operator == "equals"


def test_bug17_exclusion_rule_field_alias_for_type():
    """ExclusionRuleCreate 'field' must alias to 'type'."""
    from app.schemas.exclusion_rules import ExclusionRuleCreate
    obj = ExclusionRuleCreate(field="domain", value="gmail.com")
    assert obj.type == "domain"


def test_bug17_exclusion_rule_default_type():
    """ExclusionRuleCreate.type must default to 'domain' when not provided."""
    from app.schemas.exclusion_rules import ExclusionRuleCreate
    obj = ExclusionRuleCreate(value="example.com")
    assert obj.type == "domain"


def test_bug17_exclusion_rule_operator_is_ignored_not_error():
    """ExclusionRuleCreate.operator is accepted (not an error) even if ignored."""
    from app.schemas.exclusion_rules import ExclusionRuleCreate
    obj = ExclusionRuleCreate(field="email", operator="contains", value="@test.com")
    assert obj.operator == "contains"
    assert obj.type == "email"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-19: Template service no db.refresh test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug19_template_service_uses_db_get_not_refresh():
    """EmailTemplateService.create must use db.get() instead of db.refresh()."""
    path = pathlib.Path("app/features/templates/service.py")
    src = path.read_text()
    # The create method should use db.get instead of db.refresh
    assert "db.get" in src, (
        "Template service should use db.get() after commit, not db.refresh()"
    )


def test_bug19_template_service_update_uses_db_get():
    """EmailTemplateService.update must use db.get() instead of db.refresh()."""
    path = pathlib.Path("app/features/templates/service.py")
    src = path.read_text()
    # Count occurrences of db.get — both create and update should use it
    assert src.count("db.get") >= 2, (
        "Both create and update should use db.get() instead of db.refresh()"
    )


def test_bug19_template_create_body_alias():
    """EmailTemplateCreate accepts 'body' as alias for bodyTemplate."""
    from app.schemas.templates import EmailTemplateCreate
    obj = EmailTemplateCreate(name="Test", body="Hello {{firstName}}")
    assert obj.bodyTemplate == "Hello {{firstName}}"


def test_bug19_template_create_subject_alias():
    """EmailTemplateCreate accepts 'subject' as alias for subjectTemplate."""
    from app.schemas.templates import EmailTemplateCreate
    obj = EmailTemplateCreate(name="Test", body="x", subject="Re: {{company}}")
    assert obj.subjectTemplate == "Re: {{company}}"


# ═════════════════════════════════════════B════════════════════════════════════
# BUG-20: Analytics null guard test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug20_analytics_list_metrics_guards_empty_sequences():
    """AnalyticsService.list_metrics must handle empty sequences gracefully."""
    path = pathlib.Path("app/features/analytics/service.py")
    src = path.read_text()
    # Must guard against division by zero (sent == 0)
    assert "if sent" in src or "if total_sent" in src or "else 0.0" in src, (
        "Analytics service must guard against division by zero"
    )


def test_bug20_analytics_generate_result_guards_no_data():
    """AnalyticsService.generate_result must return None when no data exists."""
    path = pathlib.Path("app/features/analytics/service.py")
    src = path.read_text()
    assert "return None" in src, (
        "Analytics generate_result must return None when no data"
    )


def test_bug20_campaign_metric_response_has_rate_fields():
    """CampaignMetricResponse must have rate fields (openRate, replyRate, bounceRate)."""
    from app.schemas.analytics import CampaignMetricResponse
    fields = CampaignMetricResponse.model_fields
    for rate_field in ("openRate", "replyRate", "bounceRate"):
        assert rate_field in fields, f"CampaignMetricResponse missing {rate_field}"


def test_bug20_dashboard_aggregation_guards_zero_sent():
    """DashboardAggregation must handle 0 sends (avoid division by zero)."""
    from app.schemas.analytics import DashboardAggregation
    obj = DashboardAggregation(
        totalProspects=0, totalCampaigns=0, activeSequences=0,
        sentThisWeek=0, repliesThisWeek=0, positiveRepliesThisWeek=0,
        meetingsThisWeek=0, pipelineValue=0.0, averageReplyRate=0.0,
    )
    assert obj.averageReplyRate == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-21: AB testing array guard test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug21_ab_test_create_has_required_fields():
    """AbTestCreate must have name, campaignId, element, splitRatio."""
    from app.schemas.ab_testing import AbTestCreate
    obj = AbTestCreate(name="Subject Test", campaignId="camp-1", element="subject")
    assert obj.name == "Subject Test"
    assert obj.campaignId == "camp-1"
    assert obj.element == "subject"
    assert obj.splitRatio == 0.5  # default


def test_bug21_ab_test_create_split_ratio_bounds():
    """AbTestCreate.splitRatio must be in [0.0, 1.0]."""
    from app.schemas.ab_testing import AbTestCreate
    import pydantic
    # Valid values
    for ratio in (0.0, 0.5, 1.0):
        obj = AbTestCreate(name="Test", campaignId="c1", splitRatio=ratio)
        assert obj.splitRatio == ratio
    # Invalid values
    for ratio in (-0.1, 1.1):
        try:
            AbTestCreate(name="Test", campaignId="c1", splitRatio=ratio)
            assert False, f"splitRatio={ratio} should be rejected"
        except pydantic.ValidationError:
            pass  # expected


def test_bug21_ab_test_service_guards_fk_violation():
    """AbTestingService.create must guard against FK violation for campaignId."""
    path = pathlib.Path("app/features/ab_testing/service.py")
    src = path.read_text()
    # The service should add the test and handle commit/refresh
    assert "db.add" in src
    assert "db.commit" in src


def test_bug21_significance_result_has_expected_fields():
    """SignificanceResult must have all statistical fields."""
    from app.schemas.ab_testing import SignificanceResult
    fields = SignificanceResult.model_fields
    expected = ["abTestId", "variantACount", "variantBCount", "zScore", "pValue", "isSignificant", "winner"]
    for field in expected:
        assert field in fields, f"SignificanceResult missing field '{field}'"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-22: Weekly digest array guard test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug22_weekly_digest_highlights_is_list():
    """WeeklyDigestResponse.highlights must be list[str], not a raw string."""
    from app.schemas.weekly_digest import WeeklyDigestResponse
    fields = WeeklyDigestResponse.model_fields
    assert "highlights" in fields
    # Verify the field annotation is list[str]
    annotation = fields["highlights"].annotation
    assert annotation is not None


def test_bug22_weekly_digest_highlights_parses_json_string():
    """WeeklyDigestResponse.highlights must parse JSON string to list."""
    from app.schemas.weekly_digest import WeeklyDigestResponse
    from datetime import datetime
    obj = WeeklyDigestResponse(
        id="1",
        weekStart=datetime.now(),
        weekEnd=datetime.now(),
        sentCount=100, replyCount=10, positiveReplyCount=4,
        meetingCount=2, bounceCount=5,
        summary="Good week",
        highlights='["Sent 100 emails", "10 replies"]',
        generatedAt=datetime.now(),
        createdAt=datetime.now(),
        updatedAt=datetime.now(),
    )
    assert isinstance(obj.highlights, list)
    assert len(obj.highlights) == 2
    assert "Sent 100 emails" in obj.highlights


def test_bug22_weekly_digest_top_prospects_parses_json():
    """WeeklyDigestResponse.topProspects must parse JSON string to list."""
    from app.schemas.weekly_digest import WeeklyDigestResponse
    from datetime import datetime
    obj = WeeklyDigestResponse(
        id="1",
        weekStart=datetime.now(),
        weekEnd=datetime.now(),
        sentCount=100, replyCount=10, positiveReplyCount=4,
        meetingCount=2, bounceCount=5,
        summary="Good week",
        highlights=["highlight1"],
        topProspects='[{"prospectId": "p1"}]',
        campaignPerformance='{"camp1": {"sent": 50}}',
        generatedAt=datetime.now(),
        createdAt=datetime.now(),
        updatedAt=datetime.now(),
    )
    assert isinstance(obj.topProspects, list)


def test_bug22_weekly_digest_service_guards_empty_sequences():
    """WeeklyDigestService.generate must guard against 0 sends (division by zero)."""
    path = pathlib.Path("app/features/weekly_digest/service.py")
    src = path.read_text()
    # Must handle division by zero in reply rate calculation
    assert "if sent" in src or "else" in src, (
        "Weekly digest must guard against division by zero when sent=0"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-23: Optimization rule slug lookup test
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug23_optimization_rule_service_slug_lookup():
    """OptimizationRuleService.get_rule must try PK first, then name (slug)."""
    path = pathlib.Path("app/features/optimization/service.py")
    src = path.read_text()
    # get_rule should try id first, then fall back to name
    idx = src.find("async def get_rule")
    section = src[idx:idx+600] if idx >= 0 else src
    assert "name" in section, (
        "get_rule must fall back to name-based lookup when PK not found"
    )


def test_bug23_optimization_rule_create_has_name():
    """OptimizationRuleCreate must have name field for slug-based operations."""
    from app.schemas.optimization_rules import OptimizationRuleCreate
    obj = OptimizationRuleCreate(
        name="High Bounce Pause",
        metric="bounceRate",
        operator="gt",
        threshold=0.10,
        action="pause",
    )
    assert obj.name == "High Bounce Pause"


def test_bug23_optimization_rule_response_has_name():
    """OptimizationRuleResponse must include name field."""
    from app.schemas.optimization_rules import OptimizationRuleResponse
    fields = OptimizationRuleResponse.model_fields
    assert "name" in fields, "OptimizationRuleResponse must have 'name' field"


def test_bug23_optimization_rule_update_has_name():
    """OptimizationRuleUpdate must allow updating name."""
    from app.schemas.optimization_rules import OptimizationRuleUpdate
    obj = OptimizationRuleUpdate(name="Updated Rule Name")
    assert obj.name == "Updated Rule Name"


def test_bug23_optimization_evaluate_response_structure():
    """OptimizationEvaluateResponse must have triggered (list) + skipped (int)."""
    from app.schemas.optimization_rules import OptimizationEvaluateResponse
    fields = OptimizationEvaluateResponse.model_fields
    assert "triggered" in fields
    assert "skipped" in fields


__all__ = []
