# OUTRENA — Test Package README

## Test Files

| File | Tests | What it covers |
|------|-------|----------------|
| `tests/test_ai_features_e2e.py` | 22 | 5 AI prospect endpoints + 2 scheduler endpoints (Round 5) |
| `tests/test_bugfix_session.py` | 44 | BUG-01 through BUG-32 + CC-01/02/03 (this session) |
| `tests/test_all_fixes.py` | 14 | Prior fix sessions (FIX-01 through FIX-14) |
| `tests/test_health.py` | 1 | `/health` endpoint smoke test |
| `tests/test_unit.py` | varies | Scoring, CSV, GDPR, scheduler unit tests |
| `tests/contract/test_contract_all_endpoints.py` | varies | OpenAPI contract tests |
| `tests/integration/` | varies | DB isolation, RBAC, Alembic idempotency, provisioning |

**Total from prior sessions:** 165 tests  
**Added Round 5 (AI features):** 22 tests  
**Combined:** 187 tests

---

## Running the Tests

### Quick (no Docker — schema + source inspection tests only)

```bash
cd outrena-backend
pip install pytest pydantic pydantic-settings
pytest tests/test_bugfix_session.py tests/test_all_fixes.py -v
```

Expected: **58 passed** in < 1 second.

### Full suite (requires Docker Compose stack running)

```bash
# Start the stack first
docker compose up -d postgres redis

# Run full suite
cd outrena-backend
pip install -r requirements.txt
pytest tests/ -v --tb=short
```

Expected: **187 passed** (some integration tests skip without live Keycloak).

### Single bug regression

```bash
pytest tests/test_bugfix_session.py::test_bug01_llm_config_accepts_api_key_camel -v
```

---

## Test Categories

### Schema unit tests (no DB required)
Tests that instantiate Pydantic schemas and verify field aliases, validators, and coercions work correctly. These are the primary regression guards for the bug-fix session.

Covers: BUG-01, BUG-09, BUG-10, BUG-11, BUG-12, BUG-14, BUG-17, BUG-22, BUG-23, BUG-24, BUG-27

### Source inspection tests (no DB required)
Tests that read the Python source of router/service files and assert the fix is present (e.g., "try:" block exists, "celery_app is None" guard is present). These verify structural fixes without needing to run the code.

Covers: BUG-04, BUG-05, BUG-06, BUG-09 (CC-01), BUG-13, BUG-19, BUG-21, CC-02, CC-03

### Integration tests (Docker required)
Full end-to-end HTTP tests requiring live PostgreSQL and Redis. These are in `tests/integration/` and `tests/contract/`.

### AI features E2E tests (Round 5)
End-to-end tests for the 5 AI prospect endpoints and 2 scheduler endpoints.
LLM calls and web search are mocked via `unittest.mock` so no external API
keys or network are needed. Schema validation tests run without DB.

| Test class | Tests | Category |
|------------|-------|----------|
| `TestUltimateProfile` | 3 | Integration (mocked) + schema |
| `TestLookalike` | 3 | Integration (mocked) + schema |
| `TestHookGenerator` | 3 | Integration (mocked) + schema |
| `TestProspectBrief` | 3 | Integration (mocked) + schema |
| `TestNlSearch` | 2 | Integration (mocked) + schema |
| `TestSchedulerFeatures` | 3 | Integration (mocked) |
| `TestAiSchemaValidation` | 11 | Schema only (no DB) |

**Total:** 28 tests (11 schema-only, 17 integration with mocks)

#### Running AI feature tests

```bash
# Schema-only (no DB required)
cd outrena-backend
pytest tests/test_ai_features_e2e.py::TestAiSchemaValidation -v

# Full with mocks (requires DB)
pip install -r requirements.txt
pytest tests/test_ai_features_e2e.py -v
```

#### Frontend AI feature tests

```bash
cd outrena-frontend
npx vitest run tests/ai-features-e2e.test.ts
```

Covers: Ultimate Profile, Lookalike, Hook Generator, Prospect Brief,
NL Search, Rich Content Editor, Scheduler Status Page.

| Test describe block | Tests | Category |
|---------------------|-------|----------|
| `AI Prospect Features` | 15 | Payload + rendering |
| `NL Search Response` | 2 | Response structure |
| `Rich Content Editor` | 7 | Component behavior |
| `Scheduler Status Page` | 8 | Component + API |
| `API Client Integration` | 3 | API client helpers |

**Total frontend tests:** 35

---

## Environment Setup for Full Suite

```bash
# Copy example env
cp outrena-backend/.env.example outrena-backend/.env

# Generate ENCRYPTION_KEY (BUG-04 fix — required for integrations tests)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste the output into .env as ENCRYPTION_KEY=<value>

# Start dependencies
docker compose up -d postgres redis

# Run
cd outrena-backend
pytest tests/ -v
```
