# OUTRENA Super Admin — Round 4 Test Suite Documentation

**Session:** Round 4 bug-fix sweep (BUG-01 through BUG-23)
**Date:** 2025-03-04
**Total Tests:** 142 (87 backend unit + 16 e2e + 39 frontend)

---

## Test File Locations

```
outrena-backend/
├── tests/
│   ├── conftest.py                          # Shared fixtures (ASGI client, env)
│   ├── test_health.py                       # Smoke test: /health endpoint
│   ├── test_unit.py                         # Pure unit tests (no DB/Redis/Keycloak)
│   ├── test_bugfix_session.py               # Round 1 regression tests
│   ├── test_bugfix_v2.py                    # Round 2 regression tests
│   ├── test_bugfix_v4.py                    # Round 4 regression tests (87 tests)
│   ├── test_e2e_v4.py                       # Round 4 e2e integration tests (16 tests)
│   ├── test_all_fixes.py                    # Cross-session regression tests
│   ├── test_bugfix_0015.py                  # Patch 0015 specific tests
│   ├── test_phase3_openapi.py               # Phase 3 OpenAPI schema validation
│   ├── contract/
│   │   ├── conftest.py                      # Contract test fixtures
│   │   └── test_contract_all_endpoints.py   # API contract tests (all endpoints)
│   ├── integration/
│   │   ├── conftest.py                      # Integration test fixtures (DB containers)
│   │   ├── test_jwks_cache.py              # JWKS cache integration test
│   │   ├── test_rbac.py                    # RBAC integration test
│   │   ├── test_isolation.py               # Tenant isolation integration test
│   │   ├── test_provisioning_rollback.py   # Provisioning rollback test
│   │   ├── test_platform_routes.py         # Platform admin route tests
│   │   └── test_alembic_idempotency.py     # Alembic migration idempotency
│   ├── e2e/
│   │   ├── conftest.py                      # E2E test fixtures (Playwright)
│   │   ├── pytest.ini                       # E2E pytest config
│   │   ├── test_login_flow.py              # Login flow E2E test
│   │   ├── test_autopilot_flow.py          # Autopilot E2E test
│   │   ├── test_sequence_review_flow.py    # Sequence review E2E test
│   │   └── test_reply_triage_flow.py       # Reply triage E2E test
│   └── production/
│       ├── test_production_health.py        # Production health check
│       ├── test_seed_data.py               # Seed data validation
│       ├── test_gap_fixes.py               # Gap fix verification
│       ├── test_sequence_delivery.py       # Sequence delivery test
│       ├── test_meetings_crud.py           # Meetings CRUD test
│       ├── test_bundle_and_config.py       # Bundle and config test
│       └── test_logo_and_branding.py       # Logo and branding test

outrena-frontend/
└── tests/
    └── bugfix-v4.test.ts                    # Round 4 frontend regression tests (39 tests)
```

---

## How to Run Tests

### Backend — pytest

```bash
cd outrena-backend

# Install dev dependencies
pip install -e ".[dev]"

# Run all backend tests
pytest tests/ -v

# Round 4 unit tests only (fast — no DB, no network)
pytest tests/test_bugfix_v4.py -v

# Round 4 e2e integration tests (requires test DB)
pytest tests/test_e2e_v4.py -v

# Both Round 4 test files
pytest tests/test_bugfix_v4.py tests/test_e2e_v4.py -v

# Single bug test
pytest tests/test_bugfix_v4.py -k "bug01" -v
pytest tests/test_bugfix_v4.py -k "bug06" -v

# Cross-cutting concern tests
pytest tests/test_bugfix_v4.py -k "cc0" -v

# All regression tests across all rounds
pytest tests/test_bugfix_session.py tests/test_bugfix_v2.py tests/test_bugfix_v4.py tests/test_all_fixes.py -v

# With coverage
pytest tests/test_bugfix_v4.py --cov=app --cov-report=term-missing -v
```

### Frontend — vitest

```bash
cd outrena-frontend

# Install dependencies
npm install

# Run Round 4 frontend tests
npx vitest run tests/bugfix-v4.test.ts

# Run all frontend tests
npx vitest run

# Watch mode
npx vitest tests/bugfix-v4.test.ts
```

---

## Per-Bug Test Descriptions

### BUG-01 — LLM SimpleNamespace isActive

| Test | Description |
|------|-------------|
| `test_bug01_llm_test_simple_namespace_has_required_attrs` | Source inspection: SimpleNamespace in `llm_config/service.py` includes `provider`, `name`, `modelId`, `apiKey`, `baseUrl`, `isActive`, `isDefault`, `settings` |
| `test_bug01_llm_test_simple_namespace_has_global_llm_config_id` | Source inspection: SimpleNamespace includes `global_llm_config_id` attribute |

### BUG-02 — LLM edit not reflected (cache invalidation)

| Test | Description |
|------|-------------|
| `test_bug02_llm_config_page_has_invalidate_queries` | Source inspection: `LlmConfigPage.tsx` contains `invalidateQueries` calls |
| `test_bug02_llm_config_mutation_invalidates_on_success` | Source inspection: mutation `onSuccess` callback calls `queryClient.invalidateQueries` |

> Also covered by frontend vitest: 3 tests for create/update/delete cache invalidation.

### BUG-03 — Prompt edit 404

| Test | Description |
|------|-------------|
| `test_bug03_prompt_router_uses_key_lookup` | Source inspection: prompt router passes `key` path param to service |
| `test_bug03_prompt_service_looks_up_by_key` | Source inspection: service queries `Prompt.key == key` not `Prompt.id` |

### BUG-04 — System params 404

| Test | Description |
|------|-------------|
| `test_bug04_system_params_router_uses_key_lookup` | Source inspection: system_params router passes `key` path param |
| `test_bug04_system_params_service_looks_up_by_key` | Source inspection: service queries `SystemParam.key == key` |

### BUG-05 — DNS check error state

| Test | Description |
|------|-------------|
| `test_bug05_domains_page_handles_all_passed_false` | Source inspection: `DomainsPage.tsx` renders warning (not error) when `allPassed === false` |

> Also covered by frontend vitest: 3 tests for DnsCheckResult shape and payload.

### BUG-06 — Billing subscribe 500

| Test | Description |
|------|-------------|
| `test_bug06_subscription_fk_references_id` | Source inspection: `subscription.py` FK references `tenant.id` not `tenant.tenant_id` |

### BUG-07 — ICP persona NOT NULL

| Test | Description |
|------|-------------|
| `test_bug07_icp_persona_is_nullable` | Source inspection: `prospect_models.py` defines `persona` with `nullable=True` |
| `test_bug07_icp_persona_has_server_default` | Source inspection: `persona` has `server_default=""` |
| `test_bug07_icp_create_persona_optional` | Schema test: `IcpCreate` accepts payload without `persona` field |

### BUG-08 — ICP suggest demo fallback

| Test | Description |
|------|-------------|
| `test_bug08_icp_suggest_no_fallback_return` | Source inspection: `icp.py` suggest endpoint has no fallback/demo data return path |
| `test_bug08_icp_suggest_accepts_seed_alias` | Schema test: `IcpSuggestRequest` accepts `seed` as alias for `productOrService` |

> Also covered by frontend vitest: 3 tests for seed alias and IcpSuggestResponse fields.

### BUG-09 — Sourcing settings dict/string

| Test | Description |
|------|-------------|
| `test_bug09_source_config_settings_is_json_column` | Source inspection: `phase3_models.py` defines `settings` as `JSON` column type |
| `test_bug09_source_config_schema_has_field_validator` | Source inspection: `prospect_source.py` schema has `field_validator` for `settings` |
| `test_bug09_source_config_settings_dict_accepted` | Schema test: `SourceConfigCreate` accepts `settings` as dict |
| `test_bug09_source_config_settings_string_coerced` | Schema test: `SourceConfigCreate` coerces JSON string to dict |

### BUG-10 — Sourcing hardcoded tabs

| Test | Description |
|------|-------------|
| `test_bug10_sourcing_page_uses_usequery` | Source inspection: `ProspectSourcingPage.tsx` uses `useQuery` for source configs |

> Also covered by frontend vitest: 3 tests for NL search results, settings dict, lookalike payload.

### BUG-11 — LinkedIn engagement fields

| Test | Description |
|------|-------------|
| `test_bug11_linkedin_page_uses_prospect_id` | Source inspection: `LinkedInPage.tsx` sends `prospectId` field |

> Also covered by frontend vitest: 3 tests for engagement payload, response shape, and icpProfileId.

### BUG-12 — Competitor threatLevel

| Test | Description |
|------|-------------|
| `test_bug12_competitor_model_has_threat_level` | Source inspection: `prospect_models.py` defines `threat_level` column |
| `test_bug12_competitor_schema_has_threat_level` | Schema test: `CompetitorCreate`/`CompetitorUpdate` include `threatLevel` field |
| `test_bug12_competitor_create_round_trip` | Schema round-trip: `CompetitorCreate(name="X", threatLevel="high")` validates and serializes |

> Also covered by frontend vitest: 4 tests for threatLevel rendering, create/update payloads, and color coding.

### BUG-13 — Lead score .map crash

| Test | Description |
|------|-------------|
| `test_bug13_lead_score_page_has_array_guard` | Source inspection: `LeadScorePage.tsx` uses `Array.isArray` before `.map()` |

> Also covered by frontend vitest: 3 tests for score dimensions, clamping, and null guard.

### BUG-14 — Collaterals hardcoded campaigns

| Test | Description |
|------|-------------|
| `test_bug14_collaterals_page_uses_usequery_campaigns` | Source inspection: `CollateralsPage.tsx` uses `useQuery` for campaigns |

> Also covered by frontend vitest: 3 tests for collateral fields, link payload, and link response.

### BUG-15 — Meeting prep hardcoded prospects

| Test | Description |
|------|-------------|
| `test_bug15_meeting_prep_page_uses_usequery_prospects` | Source inspection: `MeetingPrepPage.tsx` uses `useQuery` for prospects |

> Also covered by frontend vitest: 4 tests for prospectId requirement, callType default, response shape, and no placeholder.

### BUG-16 — Meeting prep p1 ID

> Covered by BUG-15 frontend vitest test: "should not use placeholder p1 prospect ID".

### BUG-17 — Exclusion rule operator kwarg

| Test | Description |
|------|-------------|
| `test_bug17_exclusion_service_uses_model_dump_exclude` | Source inspection: `exclusions/service.py` uses `model_dump(exclude={"operator"})` |

### BUG-19 — Template db.refresh crash

| Test | Description |
|------|-------------|
| `test_bug19_template_service_uses_db_get_not_refresh` | Source inspection: `templates/service.py` uses `db.get()` after commit, not `db.refresh()` |

### BUG-20 — Analytics toLocaleString crash

| Test | Description |
|------|-------------|
| `test_bug20_analytics_page_has_null_guards` | Source inspection: `AnalyticsPage.tsx` uses `(value ?? 0)` before `.toLocaleString()` |

> Also covered by frontend vitest: 3 tests for zero-safe division, null diagnosticNote, and zero-safe rates.

### BUG-21 — AB Testing .map crash

| Test | Description |
|------|-------------|
| `test_bug21_ab_testing_page_has_array_guard` | Source inspection: `ABTestingPage.tsx` uses `Array.isArray` before `.map()` |

> Also covered by frontend vitest: 3 tests for splitRatio range, significance result fields, and empty variant arrays.

### BUG-22 — Weekly Digest .map crash

| Test | Description |
|------|-------------|
| `test_bug22_weekly_digest_page_has_array_guard` | Source inspection: `WeeklyDigestPage.tsx` uses `Array.isArray` before `.map()` |
| `test_bug22_weekly_digest_schema_parses_json_strings` | Schema test: `WeeklyDigestResponse` `field_validator` coerces JSON strings to list/dict |

> Also covered by frontend vitest: 4 tests for highlights array, topProspects array, campaignPerformance dict, and zero-safe rate.

### BUG-23 — Optimization rules 404

| Test | Description |
|------|-------------|
| `test_bug23_optimization_service_has_slug_lookup` | Source inspection: `optimization/service.py` looks up by name/slug with PK fallback |

---

## Cross-Cutting Concern Tests

### CC-01 — Slug-based lookups

| Test | Description |
|------|-------------|
| `test_cc01_prompt_uses_key_lookup` | Verified prompts, system_params, optimization all use key/slug-based lookup |
| `test_cc01_system_params_uses_key_lookup` | System params service queries by key column |
| `test_cc01_optimization_uses_name_lookup` | Optimization service queries by name with PK fallback |

### CC-02 — JSON columns

| Test | Description |
|------|-------------|
| `test_cc02_all_json_columns_are_json_type` | Source inspection: all 15+ converted columns use SQLAlchemy `JSON` type |
| `test_cc02_all_json_schemas_have_field_validators` | Source inspection: all 6 schemas have `field_validator` for JSON fields |
| `test_cc02_source_config_settings_round_trip` | Schema round-trip: dict → model_dump → dict |
| `test_cc02_icp_pain_points_json_coercion` | Schema test: JSON string coerced to list |
| `test_cc02_weekly_digest_json_coercion` | Schema test: JSON strings coerced to native types |

### CC-03 — db.refresh after commit

| Test | Description |
|------|-------------|
| `test_cc03_no_db_refresh_after_commit` | Source inspection: no `db.refresh()` calls after `db.commit()` in any service file |
| `test_cc03_db_get_used_for_post_commit_fetch` | Source inspection: `db.get()` pattern used for re-fetching after commit |

### CC-04 — Hardcoded dropdowns

| Test | Description |
|------|-------------|
| `test_cc04_sequences_page_uses_usequery` | Source inspection: `SequencesPage.tsx` campaigns from API |
| `test_cc04_collaterals_page_uses_usequery` | Source inspection: `CollateralsPage.tsx` campaigns from API |
| `test_cc04_meeting_prep_page_uses_usequery` | Source inspection: `MeetingPrepPage.tsx` prospects from API |

### CC-05 — Non-array .map crashes

| Test | Description |
|------|-------------|
| `test_cc05_signals_feed_has_array_guard` | Source inspection: `SignalsFeedPage.tsx` uses `Array.isArray` |
| `test_cc05_user_dashboard_has_array_guard` | Source inspection: `UserDashboardPage.tsx` uses `Array.isArray` |
| `test_cc05_campaign_detail_has_array_guard` | Source inspection: `CampaignDetailPage.tsx` uses `Array.isArray` |
| `test_cc05_help_guide_has_array_guard` | Source inspection: `HelpGuidePage.tsx` uses `Array.isArray` |

### CC-06 — Cache invalidation

| Test | Description |
|------|-------------|
| `test_cc06_all_mutations_have_invalidate_queries` | Source inspection: all 22 mutations include `invalidateQueries` call |

---

## E2E Integration Tests

### Workflow Tests (8 tests — require test DB)

| Test Class | Flow | Bugs Validated |
|------------|------|----------------|
| `TestLlmConfigCRUDFlow` | create → read → update → delete LLM config | BUG-01, BUG-02 |
| `TestPromptManagementFlow` | list → get by key → update by key → verify → restore | BUG-03 |
| `TestSystemParamsFlow` | list → get by key → update by key → verify → restore | BUG-04 |
| `TestIcpProfileFlow` | create ICP (persona=null) → suggest with seed alias | BUG-07, BUG-08 |
| `TestProspectSourcingFlow` | list configs → verify settings is dict | BUG-09, BUG-10 |
| `TestCompetitorFlow` | create → update threatLevel → verify persisted | BUG-12 |
| `TestTemplateFlow` | create → read back → update → verify no refresh error | BUG-19 |
| `TestOptimizationRuleFlow` | create → get by name → update → delete by name | BUG-23 |

### Schema Round-Trip Tests (8 tests — no DB required)

| Test | Schema | What It Validates |
|------|--------|-------------------|
| `test_llm_config_round_trip` | `LlmConfigCreate` | camelCase → snake_case mapping (apiKey → api_key, model → model_name) |
| `test_icp_suggest_round_trip` | `IcpSuggestRequest` | `seed` alias populates `productOrService` |
| `test_source_config_round_trip` | `SourceConfigCreate` | dict `settings` preserved through model_dump |
| `test_exclusion_rule_round_trip` | `ExclusionRuleCreate` | `field` alias → `type`; `operator` preserved |
| `test_template_create_round_trip` | `EmailTemplateCreate` | `body`/`subject` aliases → `bodyTemplate`/`subjectTemplate` |
| `test_optimization_rule_create_round_trip` | `OptimizationRuleCreate` | all fields preserved through model_dump |
| `test_competitor_create_round_trip` | `CompetitorCreate` | `threatLevel` preserved through model_dump |
| `test_weekly_digest_json_parsing` | `WeeklyDigestResponse` | JSON strings coerced to list/dict by field_validator |

---

## Frontend Test Descriptions (bugfix-v4.test.ts)

39 vitest tests covering frontend-specific fixes. These are structural/schema
assertions that run without a backend.

| Describe Block | Tests | Bugs |
|----------------|-------|------|
| BUG-02: Query cache invalidation | 3 | BUG-02 |
| BUG-05: DNS check response handling | 3 | BUG-05 |
| BUG-08: ICP suggest seed alias | 3 | BUG-08 |
| BUG-10: Prospect sourcing API data | 3 | BUG-09, BUG-10 |
| BUG-11: LinkedIn engagement field names | 3 | BUG-11 |
| BUG-12: Competitor threatLevel column | 4 | BUG-12 |
| BUG-13: Lead score array guard | 3 | BUG-13 |
| BUG-14: Collaterals campaigns from API | 3 | BUG-14 |
| BUG-15: Meeting prep prospects from API | 4 | BUG-15, BUG-16 |
| BUG-20: Analytics null guard | 3 | BUG-20 |
| BUG-21: AB testing array guard | 3 | BUG-21 |
| BUG-22: Weekly digest array guard | 4 | BUG-22 |

---

## Test Count Summary

| Category | Count | Files |
|----------|-------|-------|
| Backend unit (Round 4) | 87 | `test_bugfix_v4.py` |
| E2E workflow + schema round-trip | 16 | `test_e2e_v4.py` (8 workflow + 8 schema) |
| Frontend vitest (Round 4) | 39 | `bugfix-v4.test.ts` |
| **Total** | **142** | |

---

## Coverage Notes

### What's Covered (Automated)

- **Pydantic schema validation** — All field aliases, type coercions, JSON-string-to-native conversion, and default values tested via pure unit tests (no DB needed)
- **Source inspection** — Router ordering, service lookup patterns, model column types, and frontend guard patterns verified by reading source code
- **E2E workflow** — Full CRUD cycles for 8 feature areas through ASGI test client
- **Schema round-trip** — Create → model_dump → verify all fields preserved for 8 schemas
- **Frontend structural** — API payload shapes, response field presence, null/array guards

### What's Not Covered (Manual / Playwright E2E)

- **UI rendering** — Visual confirmation that warning badges, color-coded threat levels, and null-guarded values render correctly
- **Cache invalidation UX** — Confirm stale data disappears after mutation without full page reload
- **Dropdown population** — Confirm useQuery-populated selects show real data, not hardcoded options

### Recommendations

1. **Expand Playwright E2E** — Add browser-level tests for each major page to catch null guards and field mismatches automatically
2. **API contract tests** — Expand `test_contract_all_endpoints.py` to cover every endpoint touched in Round 4
3. **Integration tests with real DB** — BUG-06 (FK fix), BUG-07 (nullable), BUG-09 (JSON column), BUG-17 (model_dump exclude), BUG-19 (db.get pattern) would benefit from integration tests with a real database
4. **Frontend component tests** — Consider React Testing Library tests for critical page components to catch field name mismatches at build time

---

## Quick Reference

```bash
# ── Backend ──────────────────────────────────────────────
# Fast: Round 4 unit tests only (no DB, no network)
cd outrena-backend && pytest tests/test_bugfix_v4.py -v

# E2E: Round 4 workflow + schema tests (requires test DB)
pytest tests/test_e2e_v4.py -v

# All Round 4 backend tests
pytest tests/test_bugfix_v4.py tests/test_e2e_v4.py -v

# Single bug
pytest tests/test_bugfix_v4.py -k "bug01" -v
pytest tests/test_bugfix_v4.py -k "cc02" -v

# Full regression across all rounds
pytest tests/test_bugfix_session.py tests/test_bugfix_v2.py tests/test_bugfix_v4.py tests/test_all_fixes.py -v

# ── Frontend ─────────────────────────────────────────────
# Round 4 frontend tests
cd outrena-frontend && npx vitest run tests/bugfix-v4.test.ts

# All frontend tests
npx vitest run
```
