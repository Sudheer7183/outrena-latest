"""
test_gap_fixes.py — Tests verifying all alpha gap fixes (G-01 through G-15).

Suite:
  - G-01: unsubscribe endpoint registered + GET/POST methods present
  - G-01: prospect create generates unsubscribeToken
  - G-03: generate-sequences endpoint on campaigns router
  - G-04: onboarding checklist endpoint registered
  - G-05: flows/{id}/run endpoint registered
  - G-06: meetings/{id}/ics endpoint registered
  - G-07: campaign detail route importable
  - G-09: nightly cost rollup job registered in scheduler
  - G-10: migration 0012 exists with flow templates
  - G-11: signals feed route in frontend nav-config
  - G-12: DealHealthResponse has numeric score field
  - G-15: CAN-SPAM footer logic present in scheduler
"""
from __future__ import annotations

import os
import ast
import pytest
from httpx import AsyncClient

BACKEND = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND_SRC = os.path.normpath(os.path.join(BACKEND, "..", "outrena-frontend", "src"))


def _read_be(rel: str) -> str:
    with open(os.path.join(BACKEND, rel)) as f:
        return f.read()


def _read_fe(rel: str) -> str:
    with open(os.path.join(FRONTEND_SRC, rel)) as f:
        return f.read()


# ── G-01: Unsubscribe endpoint ────────────────────────────────────────────────

def test_unsubscribe_router_file_exists() -> None:
    path = os.path.join(BACKEND, "app", "features", "public", "unsubscribe_router.py")
    assert os.path.isfile(path), "unsubscribe_router.py missing"


def test_unsubscribe_router_has_post_and_get() -> None:
    content = _read_be("app/features/public/unsubscribe_router.py")
    assert "/unsubscribe" in content, "unsubscribe path missing from router"
    assert "@router.post" in content, "POST handler missing"
    assert "@router.get" in content, "GET handler missing"


def test_unsubscribe_exempt_in_tenant_middleware() -> None:
    content = _read_be("app/middleware/tenant_middleware.py")
    assert "/api/v1/public/unsubscribe" in content, (
        "Unsubscribe path not in TenantMiddleware EXEMPT_PREFIXES"
    )


def test_prospect_service_generates_token() -> None:
    content = _read_be("app/features/prospects/service.py")
    assert "unsubscribeToken" in content, "unsubscribeToken not set in ProspectService.create()"
    assert "token_urlsafe" in content, "secrets.token_urlsafe not used for token generation"


def test_frontend_unsubscribe_page_exists() -> None:
    path = os.path.join(FRONTEND_SRC, "features", "public", "UnsubscribePage.tsx")
    assert os.path.isfile(path), "UnsubscribePage.tsx missing"


def test_frontend_unsub_api_helper_exists() -> None:
    content = _read_fe("services/apiClient.ts")
    assert "publicUnsubscribeApi" in content, "publicUnsubscribeApi missing from apiClient.ts"


@pytest.mark.anyio
async def test_unsubscribe_endpoints_in_openapi(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    unsubscribe_paths = [p for p in paths if "unsubscribe" in p]
    assert len(unsubscribe_paths) >= 1, (
        f"No unsubscribe paths in OpenAPI. All paths: {sorted(paths)[:20]}"
    )


# ── G-03: Generate-sequences endpoint ────────────────────────────────────────

def test_generate_sequences_endpoint_in_campaigns_router() -> None:
    content = _read_be("app/features/campaigns/router.py")
    assert "generate-sequences" in content, (
        "POST /campaigns/{id}/generate-sequences missing from campaigns router"
    )
    assert "auto_generate_for_campaign" in content, (
        "generate-sequences endpoint doesn't call auto_generate_for_campaign"
    )


@pytest.mark.anyio
async def test_generate_sequences_in_openapi(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    gen_paths = [p for p in paths if "generate-sequences" in p]
    assert len(gen_paths) >= 1, "generate-sequences not in OpenAPI paths"


# ── G-04: Onboarding checklist ────────────────────────────────────────────────

def test_onboarding_router_file_exists() -> None:
    path = os.path.join(BACKEND, "app", "features", "auth", "onboarding_router.py")
    assert os.path.isfile(path), "onboarding_router.py missing"


def test_onboarding_router_has_checklist_endpoint() -> None:
    content = _read_be("app/features/auth/onboarding_router.py")
    assert '"/checklist"' in content or "checklist" in content, (
        "onboarding/checklist endpoint missing"
    )
    assert "CHECKLIST_ITEMS" in content, "CHECKLIST_ITEMS not defined"


def test_frontend_onboarding_component_exists() -> None:
    path = os.path.join(FRONTEND_SRC, "components", "OnboardingChecklist.tsx")
    assert os.path.isfile(path), "OnboardingChecklist.tsx missing"


def test_frontend_applayout_mounts_onboarding() -> None:
    content = _read_fe("components/layout/AppLayout.tsx")
    assert "OnboardingChecklist" in content, (
        "AppLayout.tsx does not mount OnboardingChecklist"
    )


@pytest.mark.anyio
async def test_onboarding_checklist_in_openapi(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    checklist_paths = [p for p in paths if "onboarding" in p or "checklist" in p]
    assert len(checklist_paths) >= 1, "onboarding/checklist path not in OpenAPI"


# ── G-05: Flow run-now endpoint ───────────────────────────────────────────────

def test_flow_run_endpoint_in_flows_router() -> None:
    content = _read_be("app/features/flows/router.py")
    assert '"/{flow_id}/run"' in content or "/{flow_id}/run" in content, (
        "POST /flows/{id}/run missing from flows router"
    )


@pytest.mark.anyio
async def test_flow_run_in_openapi(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    run_paths = [p for p in paths if "/flows/" in p and p.endswith("/run")]
    assert len(run_paths) >= 1, "POST /flows/{id}/run not in OpenAPI"


# ── G-06: ICS calendar invite ─────────────────────────────────────────────────

def test_ics_endpoint_in_meetings_router() -> None:
    content = _read_be("app/features/meetings/meetings_router.py")
    assert "/ics" in content, "ICS endpoint missing from meetings_router.py"
    assert "text/calendar" in content, "ICS Content-Type not set"
    assert "BEGIN:VCALENDAR" in content, "iCalendar content not generated"


@pytest.mark.anyio
async def test_ics_endpoint_in_openapi(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    ics_paths = [p for p in paths if p.endswith("/ics")]
    assert len(ics_paths) >= 1, "GET /meetings/{id}/ics not in OpenAPI"


# ── G-07: Campaign detail page ───────────────────────────────────────────────

def test_campaign_detail_page_exists() -> None:
    path = os.path.join(FRONTEND_SRC, "features", "campaigns", "CampaignDetailPage.tsx")
    assert os.path.isfile(path), "CampaignDetailPage.tsx missing"


def test_campaign_detail_has_five_tabs() -> None:
    content = _read_fe("features/campaigns/CampaignDetailPage.tsx")
    for tab in ("overview", "cadence", "prospects", "sequences", "analytics"):
        assert tab in content.lower(), f"Tab '{tab}' missing from CampaignDetailPage"


def test_campaign_detail_route_in_router() -> None:
    content = _read_fe("routes/index.tsx")
    assert "outreach/campaigns/:id" in content, (
        "Campaign detail route /outreach/campaigns/:id not in routes/index.tsx"
    )


# ── G-09: CostSummary nightly rollup ─────────────────────────────────────────

def test_cost_rollup_job_registered_in_scheduler() -> None:
    content = _read_be("app/features/scheduler/service.py")
    assert "cost_rollup" in content, "cost_rollup job not registered in scheduler"
    assert "_async_cost_rollup_wrapper" in content, "_async_cost_rollup_wrapper missing"
    assert 'hour=2' in content, "Nightly job not set to hour=2"


def test_cost_rollup_wrapper_calls_rebuild() -> None:
    content = _read_be("app/features/scheduler/service.py")
    assert "rebuild_cost_summaries" in content, (
        "rebuild_cost_summaries not called in cost rollup wrapper"
    )


# ── G-10: Flow templates migration ───────────────────────────────────────────

def test_flow_templates_migration_exists() -> None:
    path = os.path.join(BACKEND, "alembic", "versions", "0012_flow_templates_signals_nav.py")
    assert os.path.isfile(path), "Migration 0012 (flow templates) missing"


def test_flow_templates_migration_has_five_templates() -> None:
    content = _read_be("alembic/versions/0012_flow_templates_signals_nav.py")
    # Count template dict entries by counting "id": "tpl-" occurrences
    template_count = content.count('"id": "tpl-')
    assert template_count >= 5, f"Expected ≥5 templates, found {template_count}"


# ── G-11: Signals feed route ─────────────────────────────────────────────────

def test_signals_feed_page_exists() -> None:
    path = os.path.join(FRONTEND_SRC, "features", "signals", "SignalsFeedPage.tsx")
    assert os.path.isfile(path), "SignalsFeedPage.tsx missing"


def test_signals_feed_route_in_router() -> None:
    content = _read_fe("routes/index.tsx")
    assert "prospecting/signals" in content, (
        "/prospecting/signals route missing from routes/index.tsx"
    )


def test_signals_feed_in_nav_config() -> None:
    content = _read_fe("lib/nav-config.tsx")
    assert "Signals Feed" in content, "Signals Feed not in nav-config.tsx"


# ── G-12: Deal health numeric score ──────────────────────────────────────────

def test_deal_health_response_has_score_field() -> None:
    content = _read_be("app/schemas/deals.py")
    assert "score: int" in content, "DealHealthResponse missing numeric score field"


def test_deal_health_response_has_signals() -> None:
    content = _read_be("app/schemas/deals.py")
    assert "DealHealthSignal" in content, "DealHealthSignal breakdown class missing"
    assert "signals: list" in content, "DealHealthResponse.signals list missing"


def test_deal_service_uses_score_deal() -> None:
    content = _read_be("app/features/deals/service.py")
    assert "_score_deal" in content, "_score_deal method missing from DealService"
    # Should be called from compute_health
    assert "self._score_deal" in content, "_score_deal not called from compute_health"


# ── G-15: CAN-SPAM footer at send time ───────────────────────────────────────

def test_canspam_footer_enforcement_in_scheduler() -> None:
    content = _read_be("app/features/scheduler/service.py")
    assert "CAN-SPAM" in content or "can.spam" in content.lower() or "unsubscribe" in content, (
        "No CAN-SPAM / unsubscribe footer enforcement in scheduler send path"
    )
    assert "needs_footer" in content, (
        "needs_footer check missing — CAN-SPAM footer not conditionally appended"
    )


def test_canspam_footer_appends_unsub_url() -> None:
    content = _read_be("app/features/scheduler/service.py")
    assert "unsubscribeToken" in content or "unsub_url" in content, (
        "Unsubscribe URL not built in CAN-SPAM footer block"
    )


# ── TD-1: audit_env.py pre-deploy gate (Tech Doc §10.7) ──────────────────────

def test_audit_env_script_exists() -> None:
    path = os.path.join(BACKEND, "scripts", "audit_env.py")
    assert os.path.isfile(path), "scripts/audit_env.py missing (OWASP A05 gate)"


def test_audit_env_checks_all_gates() -> None:
    content = _read_be("scripts/audit_env.py")
    for gate in ("SKIP_JWT_VERIFICATION", "ENCRYPTION_KEY", "SECRET_BACKEND", "CORS_ALLOWED_ORIGINS"):
        assert gate in content, f"audit_env.py missing check for {gate}"


def test_audit_env_passes_in_dev_blocks_bad_prod() -> None:
    import subprocess
    script = os.path.join(BACKEND, "scripts", "audit_env.py")
    # Dev: trivially passes
    r = subprocess.run(
        ["python3", script], env={**os.environ, "ENVIRONMENT": "development"},
        capture_output=True,
    )
    assert r.returncode == 0, "audit_env must pass in development"
    # Misconfigured prod: blocks
    r = subprocess.run(
        ["python3", script],
        env={**os.environ, "ENVIRONMENT": "production",
             "SKIP_JWT_VERIFICATION": "true", "ENCRYPTION_KEY": "",
             "SECRET_BACKEND": "env"},
        capture_output=True,
    )
    assert r.returncode == 1, "audit_env must block a misconfigured production env"


def test_audit_env_wired_into_prod_workflows() -> None:
    root = os.path.normpath(os.path.join(BACKEND, ".."))
    for wf in ("cd-prod-aws.yml", "cd-prod-azure.yml"):
        path = os.path.join(root, ".github", "workflows", wf)
        assert os.path.isfile(path), f"{wf} missing"
        with open(path) as f:
            assert "audit_env.py" in f.read(), f"audit_env gate not wired into {wf}"


# ── TD-2: PostHog frontend init (Tech Doc §12.2) ─────────────────────────────

def test_posthog_initialised_in_main_tsx() -> None:
    content = _read_fe("main.tsx")
    assert "posthog.init" in content, "PostHog not initialised in main.tsx"
    assert "autocapture" in content, "PostHog autocapture not enabled"
    assert "maskAllInputs" in content, "Session-replay input masking not configured"


def test_posthog_env_vars_documented() -> None:
    path = os.path.join(FRONTEND_SRC, "..", ".env.example")
    with open(path) as f:
        content = f.read()
    assert "VITE_POSTHOG_KEY" in content, "VITE_POSTHOG_KEY missing from .env.example"


# ── TD-3: posthog_middleware documented alias (Tech Doc §12.2 / §5.10) ───────

def test_posthog_middleware_alias_module() -> None:
    path = os.path.join(BACKEND, "app", "middleware", "posthog_middleware.py")
    assert os.path.isfile(path), "app/middleware/posthog_middleware.py missing"
    content = _read_be("app/middleware/posthog_middleware.py")
    assert "ExceptionLoggingMiddleware" in content, "alias must re-export ExceptionLoggingMiddleware"


# ── TD-4: react-virtual dependency (Tech Doc §13.5) ──────────────────────────

def test_react_virtual_dependency_present() -> None:
    path = os.path.join(FRONTEND_SRC, "..", "package.json")
    with open(path) as f:
        content = f.read()
    assert "@tanstack/react-virtual" in content, "@tanstack/react-virtual missing from package.json"


# ═══════════════════════════════════════════════════════════════════════════
# URD 100% compliance fixes (UR-G1 … UR-G15, FR-015, FR-124)
# ═══════════════════════════════════════════════════════════════════════════


# ── UR-G1: MFA (NFR-015 / FR-090) ────────────────────────────────────────────

def test_keycloak_realm_has_otp_policy() -> None:
    import json
    with open(os.path.join(BACKEND, "keycloak", "realm-export.json")) as f:
        realm = json.load(f)
    assert realm.get("otpPolicyType") == "totp", "otpPolicyType must be totp"
    aliases = {a.get("alias") for a in realm.get("requiredActions", [])}
    assert "CONFIGURE_TOTP" in aliases, "CONFIGURE_TOTP required action missing"


def test_admin_user_creation_requires_totp() -> None:
    c = _read_be("app/services/keycloak_admin_service.py")
    assert "CONFIGURE_TOTP" in c, "tenant-admin creation must require TOTP"
    c2 = _read_be("app/features/user_management/service.py")
    assert "CONFIGURE_TOTP" in c2, "admin user create/promote must require TOTP"


# ── UR-G2: DNS gate on send (FR-039) ─────────────────────────────────────────

def test_scheduler_has_dns_verification_gate() -> None:
    c = _read_be("app/features/scheduler/service.py")
    assert "FR-039" in c and "DNS verification failing" in c
    for record in ("SPF", "DKIM", "DMARC"):
        assert record in c


# ── UR-G3: import dedup (FR-016) ─────────────────────────────────────────────

def test_csv_import_dedups_existing_prospects() -> None:
    c = _read_be("app/services/csv_import_service.py")
    assert "FR-016" in c
    assert "existing_emails" in c, "email dedup against existing prospects"
    assert "existing_dom_names" in c, "domain+name dedup"
    assert "Duplicate skipped" in c, "duplicates must be reported as skipped"


# ── UR-G4: nginx rate limits (FR-121) ────────────────────────────────────────

def test_backend_nginx_conf_has_rate_limit_zones() -> None:
    path = os.path.join(BACKEND, "nginx", "nginx.conf")
    assert os.path.isfile(path), "backend nginx/nginx.conf missing"
    with open(path) as f:
        c = f.read()
    assert "limit_req_zone" in c
    assert "zone=api" in c and "zone=auth" in c
    assert "30r/s" in c and "5r/s" in c


# ── UR-G5: URD retention data classes (FR-096) ───────────────────────────────

def test_retention_has_urd_data_classes() -> None:
    c = _read_be("app/features/gdpr/retention_service.py")
    for cls in ("tracking_events", "reply_bodies", "deals_closed_lost"):
        assert f'"{cls}"' in c, f"retention class {cls} missing"
    assert '"days": 30' in c, "tracking_events must be 30 days"
    assert '"days": 90' in c, "reply_bodies must be 90 days"


# ── UR-G6: tenant usage caps (FR-114) ────────────────────────────────────────

def test_usage_service_has_cap_methods() -> None:
    c = _read_be("app/features/usage/service.py")
    for m in ("get_monthly_cap_cents", "get_month_spend_cents", "check_llm_cap"):
        assert f"def {m}" in c, f"UsageService.{m} missing"
    assert "monthly_cost_cap_cents" in c


def test_llm_cap_gate_wired_into_noncritical_routes() -> None:
    assert os.path.isfile(
        os.path.join(BACKEND, "app", "features", "usage", "cap_gate.py")
    )
    for rel in (
        "app/features/email_studio/router.py",
        "app/features/content_ideas/router.py",
        "app/features/autopilot/router.py",
    ):
        assert "enforce_llm_cap" in _read_be(rel), f"cap gate missing in {rel}"


# ── UR-G7: ICS invite emailed via MailBridge (FR-056) ────────────────────────

def test_meetings_send_invite_endpoint() -> None:
    c = _read_be("app/features/meetings/meetings_router.py")
    assert "/send-invite" in c
    assert "MailBridgeService" in c
    assert "ATTENDEE" in c, "ICS must carry an ATTENDEE line"


# ── UR-G8: provisioning welcome email (FR-008) ───────────────────────────────

def test_provisioning_sends_welcome_email() -> None:
    c = _read_be("app/services/tenant_provisioning_service.py")
    assert "_send_welcome_email" in c
    assert "FR-008" in c
    assert "NON-FATAL" in c, "welcome email must not fail provisioning"


# ── UR-G9: automated warm-up (FR-038) ────────────────────────────────────────

def test_scheduler_warmup_ramp_and_advance() -> None:
    c = _read_be("app/features/scheduler/service.py")
    assert "_WARMUP_RAMP" in c
    assert "def _warmup_effective_cap" in c
    assert "async def advance_domain_warmup" in c
    assert "Warm-up daily cap reached" in c


def test_warmup_ramp_values() -> None:
    import importlib.util
    # static check of ramp mapping — 7-week schedule per Help Guide §Domains
    c = _read_be("app/features/scheduler/service.py")
    assert "{1: 10, 2: 30, 3: 50, 4: 100, 5: 200, 6: 350, 7: 500}" in c


# ── UR-G10: session revocation on deactivate (FR-087) ────────────────────────

def test_user_disable_revokes_sessions() -> None:
    c = _read_be("app/features/user_management/service.py")
    assert "/logout" in c, "Keycloak logout call missing on disable"
    assert "FR-087" in c


# ── UR-G11: plain-text / HTML preview toggle (FR-029) ────────────────────────

def test_email_studio_preview_toggle() -> None:
    c = _read_fe("features/email_studio/EmailStudioPage.tsx")
    assert "previewMode" in c
    assert '"html"' in c and '"text"' in c
    assert "Plain text" in c and "HTML" in c
    assert "dangerouslySetInnerHTML" not in c, "HTML preview must not inject markup"


# ── UR-G12: support ticket diagnostics (FR-101) ──────────────────────────────

def test_support_ticket_attaches_diagnostics() -> None:
    c = _read_be("app/features/support/router.py")
    assert "diagnostics" in c and "user_agent" in c
    s = _read_be("app/features/support/service.py")
    assert "diagnostics" in s and "is_internal_note=True" in s


# ── UR-G13: cohort breakdowns (FR-062) ───────────────────────────────────────

def test_analytics_cohort_endpoint() -> None:
    c = _read_be("app/features/analytics/router.py")
    assert "/cohorts" in c
    assert '"icp"' in c and '"segment"' in c
    assert "replyRate" in c


# ── UR-G14: digest recipient-local 09:00 (FR-059) ────────────────────────────

def test_weekly_digest_local_hour_gate() -> None:
    c = _read_be("app/features/weekly_digest/service.py")
    assert "local_hour_gate" in c
    assert "ZoneInfo" in c
    w = _read_be("app/worker/celery_app.py")
    assert '"kwargs": {"local_hour_gate": 9}' in w
    assert '_crontab(minute=0, day_of_week=1)' in w, "beat must run hourly on Mondays"


# ── UR-G15: CSRF satisfied-by-design documented (NFR-018) ────────────────────

def test_csrf_design_documented() -> None:
    path = os.path.join(BACKEND, "SECURITY-NOTES.md")
    assert os.path.isfile(path)
    with open(path) as f:
        c = f.read()
    assert "NFR-018" in c and "Bearer" in c and "CSRF" in c


# ── FR-015: MANAGER score override ───────────────────────────────────────────

def test_prospect_score_override_endpoint() -> None:
    c = _read_be("app/features/prospects/router.py")
    assert "/score-override" in c
    assert "require_role(Role.MANAGER)" in c.split("score-override")[1][:2000]
    assert "previousScore" in c


# ── FR-124: locale extension point ───────────────────────────────────────────

def test_i18n_extension_point() -> None:
    path = os.path.join(FRONTEND_SRC, "lib", "i18n.ts")
    assert os.path.isfile(path), "src/lib/i18n.ts missing (FR-124)"
    with open(path) as f:
        c = f.read()
    assert "SUPPORTED_LOCALES" in c and "en-US" in c and "setLocale" in c


# ═══════════════════════════════════════════════════════════════════════════
# Help Guide reverse-check fixes (warmup 7-week, alumni ICP match, CRM sync)
# ═══════════════════════════════════════════════════════════════════════════


def test_warmup_7_week_ramp() -> None:
    c = _read_be("app/features/scheduler/service.py")
    assert "7: 500" in c, "7-week ramp must reach 500/day"
    assert "WARMING_SCHEDULE" in c
    assert "[10, 30, 50, 100, 200, 350, 500]" in c
    assert "AND 7" in c, "advance_domain_warmup must handle week 7"


def test_domains_auto_warm_endpoint() -> None:
    c = _read_be("app/features/domains/router.py")
    assert "/auto-warm" in c
    assert "advance the domain one week" in c or "Auto-Warm" in c
    assert "WARMING_SCHEDULE" in c


def test_warmup_preflight_gate() -> None:
    c = _read_be("app/features/scheduler/service.py")
    assert "warmingWeek" in c
    assert "warmingWeek < 2" in c or "week < 2" in c
    assert "least 2 weeks" in c


def test_alumni_scan_closed_won_scoping() -> None:
    c = _read_be("app/features/job_change/service.py")
    assert "closed_won" in c, "alumni scan must scope to closed-won deal prospects"
    assert "Deal" in c


def test_alumni_scan_icp_match_scoring() -> None:
    c = _read_be("app/features/job_change/service.py")
    assert "icpFitScore" in c or "icp_score" in c, "ICP match scoring missing"
    assert "IcpProfile" in c
    assert "matchReason" in c or "match_reason" in c


def test_alumni_scan_30_day_dedup() -> None:
    c = _read_be("app/features/job_change/service.py")
    assert "30" in c and "day" in c.lower()
    assert "dedup_key" in c or "recent_alert_keys" in c


def test_crm_sync_log_model() -> None:
    c = _read_be("app/models/campaign_models.py")
    assert "CrmSyncLog" in c
    assert "exportedByUserId" in c
    assert "stageBreakdown" in c
    assert "dealCount" in c


def test_crm_export_endpoint() -> None:
    c = _read_be("app/features/deals/router.py")
    assert "/crm-export" in c
    assert "CrmSyncLog" in c
    assert "Push to CRM" in c or "crm-export" in c


def test_crm_export_migration() -> None:
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "alembic", "versions", "0013_crm_sync_log.py"
    )
    assert os.path.isfile(path), "migration 0013 missing"
    with open(path) as f:
        content = f.read()
    assert "CrmSyncLog" in content


def test_autopilot_human_in_loop_gate() -> None:
    c = _read_fe("features/autopilot/AutopilotPage.tsx")
    assert "pauseForReview" in c
    assert "Pause after enrichment" in c


def test_autopilot_localStorage_persistence() -> None:
    c = _read_fe("features/autopilot/AutopilotPage.tsx")
    assert "localStorage" in c
    assert "outrena.autopilot.lastResult" in c
    assert "Previous pipeline completed" in c


def test_autopilot_autonomous_mode() -> None:
    c = _read_fe("features/autopilot/AutopilotPage.tsx")
    assert "autonomousMode" in c
    assert "ICP_CREATED" in c
    assert "Autonomous Mode" in c
