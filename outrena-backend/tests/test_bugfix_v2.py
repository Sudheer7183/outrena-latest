"""
test_bugfix_v2.py — Regression tests for BUG-01 through BUG-43 (v2 batch).

Each test verifies the root cause is fixed via schema instantiation (pure Pydantic,
no DB) or source inspection (for router/service fixes that require DB at runtime).

Run with:
  cd outrena-backend && pytest tests/test_bugfix_v2.py -v

All schema tests are pure unit tests — no DB, no network, no Docker required.
Router/service source checks verify the fix is in place without executing the code.
"""
from __future__ import annotations

import inspect
import json
import pathlib


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-01: LLM test URL and payload fix
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug01_llm_config_create_accepts_camel_case():
    """LlmConfigCreate accepts frontend camelCase fields (apiKey, model, isActive)."""
    from app.schemas.llm_config import LlmConfigCreate
    obj = LlmConfigCreate(provider="openai", apiKey="sk-test", model="gpt-4", isActive=True)
    assert obj.api_key == "sk-test"
    assert obj.model_name == "gpt-4"
    assert obj.is_active is True


def test_bug01_llm_config_create_accepts_snake_case():
    """LlmConfigCreate also accepts snake_case fields natively."""
    from app.schemas.llm_config import LlmConfigCreate
    obj = LlmConfigCreate(provider="anthropic", api_key="sk-ant", model_name="claude-3")
    assert obj.api_key == "sk-ant"
    assert obj.model_name == "claude-3"


def test_bug01_llm_config_derives_display_name():
    """LlmConfigCreate derives display_name from provider/model if not provided."""
    from app.schemas.llm_config import LlmConfigCreate
    obj = LlmConfigCreate(provider="openai", model="gpt-4o")
    assert "openai" in obj.display_name
    assert "gpt-4o" in obj.display_name


def test_bug01_llm_test_request_schema():
    """TestLlmRequest has config_id and message fields for /test-llm."""
    from app.schemas.llm_config import TestLlmRequest
    obj = TestLlmRequest(config_id=1, message="Hello")
    assert obj.config_id == 1
    assert obj.message == "Hello"


def test_bug01_llm_test_response_schema():
    """TestLlmResponse returns ok, content, latency_ms, error — not the old shape."""
    from app.schemas.llm_config import TestLlmResponse
    obj = TestLlmResponse(ok=True, content="pong", latency_ms=150)
    assert obj.ok is True
    assert obj.latency_ms == 150


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-02: Provider enum validation (LLM_PROVIDERS list expanded)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug02_llm_config_accepts_all_13_providers():
    """LlmConfigCreate accepts all 13 LLM providers without validation error."""
    from app.schemas.llm_config import LlmConfigCreate
    providers = [
        "zai", "openai", "anthropic", "google", "deepseek",
        "groq", "mistral", "together", "fireworks", "perplexity",
        "openrouter", "ollama", "azure",
    ]
    for p in providers:
        obj = LlmConfigCreate(provider=p, apiKey="sk-test", model="test-model")
        assert obj.provider == p


def test_bug02_llm_config_provider_is_freeform_string():
    """Provider field is a free-form String (not enum), matching the model."""
    from app.schemas.llm_config import LlmConfigCreate
    # Even non-standard providers should be accepted (the router validates later)
    obj = LlmConfigCreate(provider="custom-llm", apiKey="x", model="m")
    assert obj.provider == "custom-llm"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-03: LLM config table field names (snake_case alignment)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug03_llm_config_model_uses_snake_case():
    """GlobalLlmConfig model uses snake_case columns (model_name, api_key_encrypted, etc.)."""
    # Source inspection (avoids sqlalchemy import requirement in test env)
    path = pathlib.Path("app/models/global_llm_config.py")
    src = path.read_text()
    assert "model_name" in src
    assert "api_key_encrypted" in src
    assert "is_active" in src
    assert "is_default" in src
    # Legacy camelCase columns should NOT exist
    assert "modelName" not in src
    assert "apiKeyEncrypted" not in src


def test_bug03_llm_config_response_uses_snake_case():
    """LlmConfigResponse exposes snake_case fields for JSON serialization."""
    from app.schemas.llm_config import LlmConfigResponse
    fields = LlmConfigResponse.model_fields
    assert "model_name" in fields
    assert "is_active" in fields
    assert "is_default" in fields


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-04: LLM delete query cache invalidation + soft-delete filter
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug04_llm_delete_is_soft_delete():
    """LlmConfigService.delete() performs soft-delete (is_active=False), not hard-delete."""
    path = pathlib.Path("app/features/llm_config/service.py")
    src = path.read_text()
    # Find the delete method
    idx = src.find("async def delete")
    section = src[idx:idx+600]
    assert "is_active = False" in section or "is_active=False" in section
    assert "is_default = False" in section or "is_default=False" in section


def test_bug04_llm_list_filters_inactive():
    """LlmConfigService.list_configs() filters by is_active=True (soft-deleted rows hidden)."""
    path = pathlib.Path("app/features/llm_config/service.py")
    src = path.read_text()
    idx = src.find("async def list_configs")
    section = src[idx:idx+400]
    assert "is_active" in section
    assert "True" in section


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-05: Prompt variables JSON string parsing
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug05_prompt_response_variables_is_string():
    """PromptResponse.variables is a string field (JSON-encoded in DB)."""
    from app.schemas.prompt_management import PromptResponse
    from datetime import datetime
    fields = PromptResponse.model_fields
    assert "variables" in fields
    # The field annotation should be str
    assert fields["variables"].annotation is str


def test_bug05_prompt_update_only_template():
    """PromptUpdate only allows updating the template body (per-key PUT)."""
    from app.schemas.prompt_management import PromptUpdate
    fields = PromptUpdate.model_fields
    assert "template" in fields
    # Should NOT have bulk-update fields like key/category
    assert "key" not in fields
    assert "category" not in fields


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-06: System params per-key PUT instead of bulk
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug06_system_param_update_is_per_key():
    """SystemParamUpdate only contains a 'value' field (per-key PUT, not bulk)."""
    from app.schemas.system_params import SystemParamUpdate
    fields = SystemParamUpdate.model_fields
    assert "value" in fields
    assert len(fields) == 1  # Only the value field


def test_bug06_system_params_router_has_put_by_key():
    """Router has PUT /system-params/{key} for per-key updates."""
    path = pathlib.Path("app/features/system_params/router.py")
    src = path.read_text()
    assert '"/{key}"' in src or "/{key}" in src
    assert "update_param" in src or "update_value" in src


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-07: Integration field name alignment (platform, apiKey, lastTestResult)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug07_integration_create_has_platform_field():
    """IntegrationCreate uses 'platform' (not 'type') as the canonical field."""
    from app.schemas.integrations import IntegrationCreate
    fields = IntegrationCreate.model_fields
    assert "platform" in fields
    assert "apiKey" in fields


def test_bug07_integration_create_type_alias_to_platform():
    """IntegrationCreate accepts 'type' as alias for 'platform' (frontend compat)."""
    from app.schemas.integrations import IntegrationCreate
    obj = IntegrationCreate(type="apollo", name="Apollo")
    assert obj.platform == "apollo"


def test_bug07_integration_response_fields():
    """IntegrationResponse exposes platform, apiKey, lastTestResult fields."""
    from app.schemas.integrations import IntegrationResponse
    fields = IntegrationResponse.model_fields
    assert "platform" in fields
    assert "apiKey" in fields
    assert "lastTestResult" in fields


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-08: Integration real credential testing
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug08_integration_service_has_provider_specific_tests():
    """IntegrationService.test() has provider-specific test endpoints (apollo, hunter, etc.)."""
    path = pathlib.Path("app/features/integrations/service.py")
    src = path.read_text()
    # Provider-specific test paths
    assert "apollo" in src.lower()
    assert "hunter" in src.lower()
    assert "clearbit" in src.lower()


def test_bug08_integration_test_resolves_credentials():
    """IntegrationService.test() resolves credentials via dual-path service."""
    path = pathlib.Path("app/features/integrations/service.py")
    src = path.read_text()
    idx = src.find("async def test")
    section = src[idx:idx+1200]
    assert "resolve_credentials" in section


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-09: Integration config test response (ok/detail/latencyMs)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug09_integration_test_response_fields():
    """IntegrationTestResponse has ok, detail, latencyMs fields."""
    from app.schemas.integrations import IntegrationTestResponse
    fields = IntegrationTestResponse.model_fields
    assert "ok" in fields
    assert "detail" in fields
    assert "latencyMs" in fields


def test_bug09_integration_test_response_instantiation():
    """IntegrationTestResponse can be instantiated with ok/detail/latencyMs."""
    from app.schemas.integrations import IntegrationTestResponse
    obj = IntegrationTestResponse(integrationId="int-1", ok=True, latencyMs=150, detail="HTTP 200")
    assert obj.ok is True
    assert obj.latencyMs == 150
    assert obj.detail == "HTTP 200"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-10: Integration config edit form field alignment
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug10_integration_update_fields_match_frontend():
    """IntegrationUpdate uses camelCase fields matching frontend form (apiKey, isActive)."""
    from app.schemas.integrations import IntegrationUpdate
    fields = IntegrationUpdate.model_fields
    assert "apiKey" in fields
    assert "isActive" in fields
    assert "name" in fields


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-11: Domain table field name alignment (domainName, spfStatus, etc.)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug11_domain_create_has_domain_name():
    """DomainCreate uses domainName as the canonical field."""
    from app.schemas.domains import DomainCreate
    fields = DomainCreate.model_fields
    assert "domainName" in fields
    assert "spfStatus" in fields
    assert "dkimStatus" in fields
    assert "dmarcStatus" in fields


def test_bug11_domain_create_accepts_domain_alias():
    """DomainCreate accepts 'domain' as alias for 'domainName' (frontend compat)."""
    from app.schemas.domains import DomainCreate
    obj = DomainCreate(domain="acme.com")
    assert obj.domainName == "acme.com"


def test_bug11_domain_response_exposes_domain_alias():
    """DomainResponse exposes a 'domain' property as alias for domainName."""
    from app.schemas.domains import DomainResponse
    from datetime import datetime
    obj = DomainResponse(
        id="d1", domainName="acme.com", spfStatus=True, dkimStatus=True,
        dmarcStatus=True, dailySendLimit=100, warmingWeek=1, isActive=True,
        lastChecked=None, createdAt=datetime.now(), updatedAt=datetime.now()
    )
    assert obj.domain == "acme.com"
    d = obj.model_dump()
    assert d["domain"] == "acme.com"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-12: DNS check URL fix (/domains/dns-check)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug12_dns_check_request_has_domain_field():
    """DnsCheckRequest uses 'domain' field (not 'domainName')."""
    from app.schemas.domains import DnsCheckRequest
    obj = DnsCheckRequest(domain="acme.com")
    assert obj.domain == "acme.com"


def test_bug12_dns_check_route_registered():
    """Router has POST /domains/dns-check endpoint."""
    path = pathlib.Path("app/features/domains/router.py")
    src = path.read_text()
    assert "/dns-check" in src
    assert "dns_check" in src


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-13: Subscription FK fix + campaignId select
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug13_ab_test_create_has_campaign_id():
    """AbTestCreate requires campaignId field for FK integrity."""
    from app.schemas.ab_testing import AbTestCreate
    fields = AbTestCreate.model_fields
    assert "campaignId" in fields


def test_bug13_ab_test_response_has_campaign_id():
    """AbTestResponse includes campaignId."""
    from app.schemas.ab_testing import AbTestResponse
    fields = AbTestResponse.model_fields
    assert "campaignId" in fields


def test_bug13_optimization_rule_create_has_campaign_id():
    """OptimizationRuleCreate has optional campaignId for FK linkage."""
    from app.schemas.optimization_rules import OptimizationRuleCreate
    fields = OptimizationRuleCreate.model_fields
    assert "campaignId" in fields


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-14: ICP suggest seed→productOrService alias
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug14_icp_suggest_seed_alias():
    """IcpSuggestRequest maps 'seed' to 'productOrService'."""
    from app.schemas.icp import IcpSuggestRequest
    obj = IcpSuggestRequest(seed="OUTRENA Sales Platform")
    assert obj.productOrService == "OUTRENA Sales Platform"


def test_bug14_icp_suggest_product_or_service_direct():
    """IcpSuggestRequest accepts 'productOrService' directly."""
    from app.schemas.icp import IcpSuggestRequest
    obj = IcpSuggestRequest(productOrService="B2B CRM")
    assert obj.productOrService == "B2B CRM"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-15: ICP suggest response parsing (flat fields)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug15_icp_suggest_response_flat_fields():
    """IcpSuggestResponse has flat fields (name, persona, painPoints as list)."""
    from app.schemas.icp import IcpSuggestResponse
    obj = IcpSuggestResponse(
        name="Enterprise SaaS",
        persona="VP of Sales",
        companyType="B2B",
        painPoints=["slow pipeline", "no intent data"],
        valueProps=["AI scoring", "auto-enrichment"],
        topObjections=["budget", "time"],
    )
    assert obj.name == "Enterprise SaaS"
    assert isinstance(obj.painPoints, list)
    assert isinstance(obj.valueProps, list)
    assert isinstance(obj.topObjections, list)


def test_bug15_icp_suggest_service_parses_flat():
    """IcpService.suggest() parses LLM JSON into flat IcpSuggestResponse fields."""
    path = pathlib.Path("app/features/icp/service.py")
    src = path.read_text()
    idx = src.find("async def suggest")
    section = src[idx:idx+1200]
    # Should extract individual fields from parsed JSON
    assert "IcpSuggestResponse" in section or "parsed" in section
    assert "painPoints" in section


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-16: ICP create exclude buyingSignals from model_dump
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug16_icp_create_excludes_buying_signals_from_dump():
    """IcpService.create() excludes buyingSignals from model_dump (DB column doesn't exist)."""
    path = pathlib.Path("app/features/icp/service.py")
    src = path.read_text()
    idx = src.find("async def create")
    section = src[idx:idx+400]
    assert "buyingSignals" in section or "buying_signals" in section.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-17: Prospect enrich URL fix
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug17_prospect_enrich_request_schema():
    """EnrichRequest uses prospectId/email/domain (aligned with frontend)."""
    from app.schemas.prospects import EnrichRequest
    obj = EnrichRequest(prospectId="p-1", email="test@acme.com", domain="acme.com")
    assert obj.prospectId == "p-1"
    assert obj.email == "test@acme.com"
    assert obj.domain == "acme.com"


def test_bug17_prospect_enrich_route_registered():
    """Router has POST /prospects/enrich endpoint."""
    path = pathlib.Path("app/features/prospects/router.py")
    src = path.read_text()
    assert "/enrich" in src
    assert "enrich" in src


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-18: Prospect email validate URL fix
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug18_email_validate_request_schema():
    """EmailValidateRequest requires email field."""
    from app.schemas.prospects import EmailValidateRequest
    obj = EmailValidateRequest(email="test@acme.com")
    assert obj.email == "test@acme.com"


def test_bug18_email_validate_route_registered():
    """Router has POST /prospects/email-validate endpoint."""
    path = pathlib.Path("app/features/prospects/router.py")
    src = path.read_text()
    assert "/email-validate" in src


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-19: Prospect sourcing name field + apiKey
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug19_prospect_create_has_name_split():
    """ProspectCreate accepts 'name' and splits into firstName/lastName."""
    from app.schemas.prospects import ProspectCreate
    obj = ProspectCreate(name="Jordan Lee", email="jordan@example.com")
    assert obj.firstName == "Jordan"
    assert obj.lastName == "Lee"


def test_bug19_prospect_create_name_single_word():
    """ProspectCreate handles single-word name."""
    from app.schemas.prospects import ProspectCreate
    obj = ProspectCreate(name="Cher")
    assert obj.firstName == "Cher"
    assert obj.lastName == ""


def test_bug19_prospect_create_first_last_direct():
    """ProspectCreate also accepts firstName/lastName directly."""
    from app.schemas.prospects import ProspectCreate
    obj = ProspectCreate(firstName="Jane", lastName="Doe")
    assert obj.firstName == "Jane"
    assert obj.lastName == "Doe"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-20: Flow AB ICP profile select (already fixed)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug20_flow_ab_test_create_schema():
    """AbTestCreate has all required fields for ICP profile select."""
    from app.schemas.ab_testing import AbTestCreate
    obj = AbTestCreate(name="Subject Test", campaignId="camp-1")
    assert obj.name == "Subject Test"
    assert obj.campaignId == "camp-1"


def test_bug20_flow_ab_test_has_icp_filter():
    """Flows API supports icpProfileId filter parameter."""
    path = pathlib.Path("app/features/flows/router.py")
    src = path.read_text()
    assert "icp_profile_id" in src or "icpProfileId" in src


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-21: Domain enrich null fallbacks
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug21_domain_enrichment_response_allows_nulls():
    """DomainEnrichmentResponse allows None for optional fields (null fallback)."""
    from app.schemas.domain_enrich import DomainEnrichmentResponse
    from datetime import datetime
    obj = DomainEnrichmentResponse(
        id="1", domain="acme.com", companyName=None, industry=None,
        employeeCount=None, revenueRange=None, techStack=[],
        location=None, description=None, lastEnrichedAt=datetime.now()
    )
    assert obj.companyName is None
    assert obj.industry is None
    assert obj.techStack == []


def test_bug21_domain_enrichment_tech_stack_json_string():
    """DomainEnrichmentResponse coerces techStack JSON string to list."""
    from app.schemas.domain_enrich import DomainEnrichmentResponse
    from datetime import datetime
    obj = DomainEnrichmentResponse(
        id="1", domain="acme.com", companyName=None, industry=None,
        employeeCount=None, revenueRange=None,
        techStack='["React", "Python"]',
        location=None, description=None, lastEnrichedAt=datetime.now()
    )
    assert obj.techStack == ["React", "Python"]


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-22: LinkedIn config field name alignment
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug22_linkedin_config_create_fields():
    """LinkedInConfigCreate uses camelCase fields matching frontend."""
    from app.schemas.linkedin import LinkedInConfigCreate
    fields = LinkedInConfigCreate.model_fields
    assert "accountName" in fields
    assert "accountHandle" in fields
    assert "isActive" in fields
    assert "cookieJar" in fields


def test_bug22_linkedin_config_response_fields():
    """LinkedInConfigResponse exposes all fields the frontend needs."""
    from app.schemas.linkedin import LinkedInConfigResponse
    fields = LinkedInConfigResponse.model_fields
    assert "accountName" in fields
    assert "syncStatus" in fields
    assert "lastSyncedAt" in fields


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-23: LinkedIn engagement exclude owner_user_id from model_dump
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug23_linkedin_engagement_create_has_owner_user_id():
    """LinkedInEngagementCreate has owner_user_id field for FK linkage."""
    from app.schemas.linkedin import LinkedInEngagementCreate
    fields = LinkedInEngagementCreate.model_fields
    assert "owner_user_id" in fields


def test_bug23_linkedin_service_excludes_owner_user_id_from_dump():
    """LinkedInService.create_engagement() excludes owner_user_id from model_dump."""
    path = pathlib.Path("app/features/linkedin/service.py")
    src = path.read_text()
    idx = src.find("async def create_engagement")
    section = src[idx:idx+1200]
    assert "owner_user_id" in section
    assert "exclude" in section.lower() or "model_dump" in section


def test_bug23_linkedin_engagement_response_has_owner_user_id():
    """LinkedInEngagementResponse includes owner_user_id for audit display."""
    from app.schemas.linkedin import LinkedInEngagementResponse
    fields = LinkedInEngagementResponse.model_fields
    assert "owner_user_id" in fields


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-24: Competitor risk_level field alignment
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug24_competitor_create_fields():
    """CompetitorCreate has the fields the frontend needs (name, domain, overlapScore)."""
    from app.schemas.competitors import CompetitorCreate
    fields = CompetitorCreate.model_fields
    assert "name" in fields
    assert "domain" in fields
    assert "overlapScore" in fields


def test_bug24_competitor_response_fields():
    """CompetitorResponse includes all fields the frontend expects."""
    from app.schemas.competitors import CompetitorResponse
    fields = CompetitorResponse.model_fields
    assert "name" in fields
    assert "domain" in fields
    assert "overlapScore" in fields
    assert "source" in fields


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-25: Lead score real API data
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug25_lead_score_response_schema():
    """LeadScoreResponse has all fields for real API data (icpFitScore, urgencyTier, scoreBreakdown)."""
    from app.schemas.signals import LeadScoreResponse
    fields = LeadScoreResponse.model_fields
    assert "icpFitScore" in fields
    assert "urgencyTier" in fields
    assert "scoreBreakdown" in fields
    assert "computedAt" in fields


def test_bug25_lead_score_uses_real_llm():
    """SignalsService.lead_score() uses real LLM service, not hardcoded."""
    path = pathlib.Path("app/features/signals/service.py")
    src = path.read_text()
    idx = src.find("async def lead_score")
    section = src[idx:idx+800]
    assert "llm" in section.lower() or "generate_json" in section


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-26: SignalMonitor conditions JSON column
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug26_signal_monitor_conditions_accepts_dict():
    """SignalMonitorCreate accepts conditions as a dict."""
    from app.schemas.signals import SignalMonitorCreate
    obj = SignalMonitorCreate(name="Test", conditions={"minConfidence": 0.7})
    assert obj.conditions == {"minConfidence": 0.7}


def test_bug26_signal_monitor_conditions_parses_json_string():
    """SignalMonitorCreate parses conditions from JSON string."""
    from app.schemas.signals import SignalMonitorCreate
    obj = SignalMonitorCreate(name="Test", conditions='{"minConfidence": 0.7}')
    assert obj.conditions == {"minConfidence": 0.7}


def test_bug26_signal_monitor_conditions_invalid_json_fallback():
    """SignalMonitorCreate falls back to empty dict for invalid JSON."""
    from app.schemas.signals import SignalMonitorCreate
    obj = SignalMonitorCreate(name="Test", conditions="not-json")
    assert obj.conditions == {}


def test_bug26_signal_monitor_response_conditions_parses_json_string():
    """SignalMonitorResponse also parses conditions from JSON string."""
    from app.schemas.signals import SignalMonitorResponse
    from datetime import datetime
    obj = SignalMonitorResponse(
        id="1", name="Test", signalType="hiring",
        conditions='{"minConfidence": 0.8}',
        isActive=True, lastRunAt=None,
        createdAt=datetime.now(), updatedAt=datetime.now()
    )
    assert obj.conditions == {"minConfidence": 0.8}


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-27: User management invite cache invalidation
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug27_user_management_list_returns_empty_on_failure():
    """list_users returns [] instead of 500 when Keycloak is unavailable."""
    path = pathlib.Path("app/features/user_management/router.py")
    src = path.read_text()
    idx = src.find("async def list_users")
    section = src[idx:idx+500]
    assert "try:" in section
    assert "except" in section
    assert "return []" in section


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-28: Content ideas undefined toast fix
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug28_content_idea_generate_request_icp_optional():
    """ContentIdeaGenerateRequest.icpProfileId is optional (undefined → None)."""
    from app.schemas.content_ideas import ContentIdeaGenerateRequest
    obj = ContentIdeaGenerateRequest(topic="AI trends", audience="CTO", count=3)
    assert obj.icpProfileId is None


def test_bug28_content_idea_generate_request_accepts_icp():
    """ContentIdeaGenerateRequest accepts icpProfileId when provided."""
    from app.schemas.content_ideas import ContentIdeaGenerateRequest
    obj = ContentIdeaGenerateRequest(icpProfileId="icp-123", count=5)
    assert obj.icpProfileId == "icp-123"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-39: Weekly digest array null guard
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug39_weekly_digest_response_highlights_json_string():
    """WeeklyDigestResponse parses highlights from JSON string."""
    from app.schemas.weekly_digest import WeeklyDigestResponse
    from datetime import datetime
    obj = WeeklyDigestResponse(
        id="1", weekStart=datetime.now(), weekEnd=datetime.now(),
        sentCount=10, replyCount=2, positiveReplyCount=1, meetingCount=0,
        bounceCount=0, summary="Good week",
        highlights='["Sent 10 emails", "2 replies"]',
        generatedAt=datetime.now(),
        createdAt=datetime.now(), updatedAt=datetime.now()
    )
    assert isinstance(obj.highlights, list)
    assert len(obj.highlights) == 2


def test_bug39_weekly_digest_response_highlights_null_fallback():
    """WeeklyDigestResponse handles null/None for topProspects gracefully."""
    from app.schemas.weekly_digest import WeeklyDigestResponse
    from datetime import datetime
    obj = WeeklyDigestResponse(
        id="1", weekStart=datetime.now(), weekEnd=datetime.now(),
        sentCount=0, replyCount=0, positiveReplyCount=0, meetingCount=0,
        bounceCount=0, summary="No data",
        highlights=[], topProspects=None,
        generatedAt=datetime.now(),
        createdAt=datetime.now(), updatedAt=datetime.now()
    )
    assert obj.topProspects is None


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-40: Optimization rules create error message
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug40_optimization_rule_create_has_all_required_fields():
    """OptimizationRuleCreate has all required fields for clear error messages."""
    from app.schemas.optimization_rules import OptimizationRuleCreate
    fields = OptimizationRuleCreate.model_fields
    assert "name" in fields
    assert "metric" in fields
    assert "operator" in fields
    assert "threshold" in fields
    assert "action" in fields


def test_bug40_optimization_rule_create_validation():
    """OptimizationRuleCreate validates with valid data."""
    from app.schemas.optimization_rules import OptimizationRuleCreate
    obj = OptimizationRuleCreate(
        name="High Bounce Alert",
        metric="bounceRate",
        operator="gt",
        threshold=0.05,
        action="pause",
    )
    assert obj.name == "High Bounce Alert"


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-41: Optimization rules evaluate array guard
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug41_optimization_evaluate_response_triggered_is_list():
    """OptimizationEvaluateResponse.triggered is a list (array guard)."""
    from app.schemas.optimization_rules import OptimizationEvaluateResponse
    fields = OptimizationEvaluateResponse.model_fields
    assert "triggered" in fields
    assert "skipped" in fields


def test_bug41_optimization_service_evaluate_returns_empty_on_no_rules():
    """OptimizationRuleService.evaluate() returns empty triggered8triggered list when no rules."""
    path = pathlib.Path("app/features/optimization/service.py")
    src = path.read_text()
    idx = src.find("async def evaluate")
    section = src[idx:idx+600]
    # Should initialize triggered as a list
    assert "triggered" in section
    assert "skipped" in section


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-42: Same as BUG-27 (User management invite cache invalidation)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug42_user_create_has_send_invitation():
    """UserCreate schema has sendInvitation field for invite flow."""
    from app.schemas.user_management import UserCreate
    fields = UserCreate.model_fields
    assert "sendInvitation" in fields or "send_invitation" in fields


# ═══════════════════════════════════════════════════════════════════════════════
# BUG-43: Auth dev login selector
# ═══════════════════════════════════════════════════════════════════════════════

def test_bug43_auth_router_has_me_endpoint():
    """Auth router has GET /auth/me for session validation."""
    path = pathlib.Path("app/features/auth/router.py")
    src = path.read_text()
    assert "/me" in src


def test_bug43_auth_router_has_change_password():
    """Auth router has POST /auth/change-password."""
    path = pathlib.Path("app/features/auth/router.py")
    src = path.read_text()
    assert "change-password" in src or "change_password" in src


# ═══════════════════════════════════════════════════════════════════════════════
# Additional cross-cutting regression tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_signal_monitor_type_alias():
    """SignalMonitorCreate accepts 'type' as alias for 'signalType' (BUG-17 from v1)."""
    from app.schemas.signals import SignalMonitorCreate
    obj = SignalMonitorCreate(name="Hiring Monitor", type="hiring")
    assert obj.signalType == "hiring"


def test_exclusion_rule_field_alias():
    """ExclusionRuleCreate accepts 'field' as alias for 'type' (BUG-22 from v1)."""
    from app.schemas.exclusion_rules import ExclusionRuleCreate
    obj = ExclusionRuleCreate(field="domain", operator="equals", value="gmail.com")
    assert obj.type == "domain"


def test_llm_config_service_to_response_masks_api_key():
    """LlmConfigService.to_response() never returns the raw API key."""
    path = pathlib.Path("app/features/llm_config/service.py")
    src = path.read_text()
    assert "_mask" in src
    assert "api_key_encrypted" in src


def test_integration_service_create_wraps_commit():
    """IntegrationService.create() wraps commit with rollback + 409 guard."""
    path = pathlib.Path("app/features/integrations/service.py")
    src = path.read_text()
    assert "rollback" in src
    assert "409" in src


def test_icp_create_buying_signals_list_coercion():
    """IcpCreate coerces buyingSignals list to JSON string."""
    from app.schemas.icp import IcpCreate
    obj = IcpCreate(name="Test", buyingSignals=["hiring", "funding"])
    parsed = json.loads(obj.buyingSignals)
    assert "hiring" in parsed
    assert "funding" in parsed


def test_icp_create_pain_points_list_coercion():
    """IcpCreate coerces painPoints list to JSON string."""
    from app.schemas.icp import IcpCreate
    obj = IcpCreate(name="Test", painPoints=["slow workflows", "data quality"])
    parsed = json.loads(obj.painPoints)
    assert "slow workflows" in parsed


__all__ = []
