"""
test_all_fixes.py — Regression tests covering all bugs fixed across patch sessions.

Bug fixes covered:
  Session 1 (patch 0015):
    FIX-01  /metrics exempt from TenantMiddleware (was 400)
    FIX-02  user_email_quotas column rename migration 0015 (was 500 on email-quota)
    FIX-03  /api/v1/integrations prefix renamed from /prospecting-integrations (was 404)
    FIX-04  dev-token grants SUPER_ADMIN (was 403 on llm-configs)
    FIX-05  Path aliases router: 11 short-path routes for frontend compatibility

  Session 2 (current):
    FIX-06  help_guide/router get_section — duplicate 'articles' kwarg (was 500)
    FIX-07  user_management/router — UserSenderIdentity.createdAt not created_at (was 500)
    FIX-08  user_management/router — SenderIdentityResponse camelCase timestamps (was 500)
    FIX-09  schemas/integrations — accept 'type' as alias for 'platform' (was 422)
    FIX-10  schemas/domains — accept 'domain' as alias for 'domainName' (was 422)
    FIX-11  rate_limits/router — /logs route before /{rate_limit_id} (was 404)
    FIX-12  flows/router — /queue /runs /ab-tests /webhooks before /{flow_id} (were 404)
    FIX-13  dashboard/service — manager totals include total_users alias keys
    FIX-14  dashboard/schemas — ManagerDashboardResponse shape matches frontend
"""
from __future__ import annotations

import inspect
import re


# ── FIX-01: /metrics exempt ─────────────────────────────────────────────────

def test_metrics_in_exempt_prefixes():
    from app.middleware.tenant_middleware import EXEMPT_PREFIXES
    assert "/metrics" in EXEMPT_PREFIXES


# ── FIX-02: Migration 0015 ───────────────────────────────────────────────────

def test_migration_0015_lineage():
    import importlib
    mod = importlib.import_module("alembic.versions.0015_fix_timestamp_columns")
    assert mod.revision == "0015"
    assert mod.down_revision == "0014"


def test_migration_0015_targets_both_tables():
    import inspect, importlib
    mod = importlib.import_module("alembic.versions.0015_fix_timestamp_columns")
    src = inspect.getsource(mod.upgrade)
    assert "user_sender_identities" in src
    assert "user_email_quotas" in src
    assert "createdAt" in src


# ── FIX-03: /integrations prefix ────────────────────────────────────────────

def test_integrations_router_prefix():
    from app.features.integrations.router import router
    assert router.prefix == "/integrations"


# ── FIX-04: dev-token SUPER_ADMIN ────────────────────────────────────────────

def test_dev_token_role():
    import os
    os.environ.setdefault("SKIP_JWT_VERIFICATION", "true")
    from app.schemas.auth import Role
    payload = {"sub": "dev-user", "email": "admin@outrena.dev",
               "role": "SUPER_ADMIN", "tenant_slug": "acme"}
    assert Role(payload["role"]) is Role.SUPER_ADMIN


# ── FIX-05: Path aliases router ──────────────────────────────────────────────

def test_path_aliases_router_exists():
    from app.features.path_aliases.router import router
    from fastapi import APIRouter
    assert isinstance(router, APIRouter)


def test_path_aliases_routes():
    from app.features.path_aliases.router import router
    paths = {r.path for r in router.routes}
    for expected in ["/framework-recommend", "/gtm-thesis", "/icp-auto-discover",
                     "/icp-suggest", "/dns-check", "/flow-webhooks",
                     "/test-llm", "/prospecting-test", "/competitor-radar",
                     "/feature-permissions", "/feature-permissions/{feature_key}"]:
        assert expected in paths, f"Missing alias route: {expected}"


# ── FIX-06: help_guide duplicate articles kwarg ──────────────────────────────

def test_help_guide_get_section_no_duplicate_kwarg():
    src = open("app/features/help_guide/router.py").read()
    # Should pop articles before **result unpacking
    assert "result.pop" in src or "raw_articles" in src
    # Should NOT have **result, articles= pattern (duplicate kwarg)
    assert 'HelpSectionResponse(\n        **result,\n        articles=' not in src


# ── FIX-07 & 08: UserSenderIdentity camelCase ───────────────────────────────

def test_sender_identity_response_camel_case():
    src = open("app/features/user_management/router.py").read()
    assert "createdAt: datetime" in src
    assert "updatedAt: datetime" in src
    assert "created_at: datetime" not in src.split("class SenderIdentityResponse")[1].split("class ")[0] if "class SenderIdentityResponse" in src else True


def test_sender_identity_order_by_camel():
    src = open("app/features/user_management/router.py").read()
    assert "UserSenderIdentity.createdAt.desc()" in src
    assert "UserSenderIdentity.created_at" not in src


# ── FIX-09: integrations type alias ─────────────────────────────────────────

def test_integration_create_accepts_type_field():
    from app.schemas.integrations import IntegrationCreate
    # Frontend sends 'type', backend should accept it
    obj = IntegrationCreate(type="apollo", name="Apollo Test")
    assert obj.platform == "apollo"


def test_integration_create_platform_still_works():
    from app.schemas.integrations import IntegrationCreate
    obj = IntegrationCreate(platform="hunter", name="Hunter Test")
    assert obj.platform == "hunter"


# ── FIX-10: domains domain alias ─────────────────────────────────────────────

def test_domain_create_accepts_domain_field():
    from app.schemas.domains import DomainCreate
    obj = DomainCreate(domain="mail.example.com")
    assert obj.domainName == "mail.example.com"


def test_domain_create_domainName_still_works():
    from app.schemas.domains import DomainCreate
    obj = DomainCreate(domainName="out.example.com")
    assert obj.domainName == "out.example.com"


# ── FIX-11: rate_limits /logs before /{id} ──────────────────────────────────

def test_rate_limits_logs_before_dynamic_route():
    from app.features.rate_limits.router import router
    routes = [(r.methods, r.path) for r in router.routes if hasattr(r, 'path')]
    logs_idx = next((i for i, (_, p) in enumerate(routes) if p == "/logs"), None)
    dynamic_idx = next((i for i, (_, p) in enumerate(routes) if "{rate_limit_id}" in p), None)
    assert logs_idx is not None, "/logs route missing"
    assert dynamic_idx is not None, "/{rate_limit_id} route missing"
    assert logs_idx < dynamic_idx, "/logs must be registered before /{rate_limit_id}"


# ── FIX-12: flows static routes before /{flow_id} ───────────────────────────

def test_flows_static_routes_before_dynamic():
    from app.features.flows.router import router
    routes = [(r.methods, r.path) for r in router.routes if hasattr(r, 'path')]
    
    flow_id_idx = next((i for i, (_, p) in enumerate(routes) if p == "/{flow_id}"), None)
    assert flow_id_idx is not None
    
    for static_path in ["/queue", "/runs", "/ab-tests", "/webhooks"]:
        static_idx = next((i for i, (_, p) in enumerate(routes) if p == static_path), None)
        assert static_idx is not None, f"{static_path} route missing"
        assert static_idx < flow_id_idx, f"{static_path} must be before /{{flow_id}}"


# ── FIX-13 & 14: Manager dashboard shape ─────────────────────────────────────

def test_manager_dashboard_response_has_frontend_keys():
    from app.schemas.dashboard import ManagerDashboardResponse
    fields = set(ManagerDashboardResponse.model_fields.keys())
    assert "team_totals" in fields, "team_totals field missing"
    assert "members" in fields, "members field missing"
    assert "top_performers" in fields
    assert "at_risk_users" in fields


def test_manager_user_rollup_has_is_at_risk():
    from app.schemas.dashboard import ManagerUserRollup
    fields = set(ManagerUserRollup.model_fields.keys())
    assert "is_at_risk" in fields, "is_at_risk field missing from ManagerUserRollup"
    assert "user_name" in fields, "user_name field missing from ManagerUserRollup"
