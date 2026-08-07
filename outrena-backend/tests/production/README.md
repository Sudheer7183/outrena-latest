# OUTRENA — Production Test Suite

**Suite:** `tests/production/`  
**Version:** v1.0 Alpha  
**Covers:** All production hardening changes from Phase 6 SaaS v8 → Production Alpha v1

---

## What This Suite Tests

| File | What it covers | DB/Network? |
|---|---|---|
| `test_production_health.py` | FastAPI app startup, /health, /metrics, OpenAPI completeness, no duplicate operationIds, all 18 required route prefixes, meetings endpoint count, 500 prevention | ✅ App (no DB) |
| `test_meetings_crud.py` | New /api/v1/meetings router: registered, all 5 methods present, auth required | ✅ App (no DB) |
| `test_logo_and_branding.py` | brand-assets.ts present + exports, OutrenaLogo component exports, Sidebar uses real logo, LoginPage uses real logo, real favicon, noindex | ❌ None (static) |
| `test_seed_data.py` | All 10 required table CSVs present, required columns non-empty | ❌ None (static) |
| `test_bundle_and_config.py` | vite.config.ts has manualChunks + brand-assets isolation, .env.example has no real secrets, requirements.txt has all critical packages, docker-compose has all services | ❌ None (static) |
| `test_sequence_delivery.py` | E2 fix present (prospect email lookup), E6 fix present (7-touch cadence), 7-touch has exactly 7 entries | ❌ None (static) |

---

## Quick Run (no DB required)

The static tests (logo, seed, bundle, sequence) run with no infrastructure:

```bash
cd outrena-backend

# Install test deps
pip install pytest pytest-asyncio httpx --break-system-packages 2>/dev/null || pip install pytest pytest-asyncio httpx

# Run just the static tests
pytest tests/production/test_logo_and_branding.py \
       tests/production/test_seed_data.py \
       tests/production/test_bundle_and_config.py \
       tests/production/test_sequence_delivery.py \
       -v
```

Expected output: **22 passed** (all static tests).

---

## Full Run (app-level tests, no live DB)

The health + meetings + OpenAPI tests spin up the FastAPI app via httpx's ASGI transport. No Postgres or Redis needed — the app starts and serves non-DB paths:

```bash
cd outrena-backend

# Set test env (no real DB needed for these tests)
export ENVIRONMENT=test
export SKIP_JWT_VERIFICATION=true
export DATABASE_URL=postgresql+asyncpg://x:x@localhost/x
export REDIS_URL=redis://localhost:6379/15
export BASE_DOMAIN=localhost

pytest tests/production/ -v
```

Expected output: **81 passed** (all tests pass in CI without DB/Redis; DB-level tests pass when running against a live stack).

---

## Integration Test Run (requires docker compose)

To run the full suite including integration tests from Phase 6:

```bash
docker compose up -d postgres redis
sleep 5

cd outrena-backend
pip install -r requirements.txt
python -m alembic upgrade head

pytest tests/ -v --ignore=tests/e2e --ignore=tests/load
```

---

## Seed Data Validation

The seed data tests expect the zip to be extracted alongside this repo:

```
production/
  outrena-backend/     ← this repo
  outrena-frontend/
  seed/
    outrena-seed-data/
      02-tenant-schema/
        Prospect.csv
        Campaign.csv
        ...
```

If running from a different directory layout, set:

```bash
export SEED_DIR=/path/to/outrena-seed-data/02-tenant-schema
```

---

## Adding New Tests

All new production tests go in `tests/production/`. Follow the pattern:
- Pure static checks → no fixtures needed, just `def test_*():`
- App-level checks → use the `client: AsyncClient` fixture from `tests/conftest.py`
- DB-level checks → use the `session` fixture from `tests/integration/conftest.py`
