# OUTRENA Backend — Phase 3 (Outreach + Analytics)

> **Phase 3 goal**: Implement the 22 Outreach + Analytics feature modules
> (133 endpoints) — sequences, reply drafts, collaterals, meeting prep,
> exclusion rules, templates, deals, analytics, A/B testing, content ideas,
> weekly digest, optimization rules, LinkedIn, job-change monitor,
> competitors, MailBridge, domain enrich, prospect source, signals,
> email studio, scheduler, and dashboard.

This package contains the Python 3.11 / FastAPI / SQLAlchemy 2.0 async backend
for OUTRENA, migrated from the original Next.js 16 / Prisma / SQLite codebase
per the OUTRENA Platform Migration & Multitenancy Blueprint.

## Stack

| Layer            | Technology                              |
|------------------|-----------------------------------------|
| Runtime          | Python 3.11+                            |
| Web framework    | FastAPI 0.115                           |
| Validation       | Pydantic v2 + pydantic-settings         |
| ORM              | SQLAlchemy 2.0 async (asyncpg)          |
| Migrations       | Alembic 1.14                            |
| Database         | PostgreSQL 16                           |
| Cache / queue    | Redis 7 (redis.asyncio)                 |
| Auth             | Keycloak 24+ (RS256 JWTs via python-jose)|
| HTTP client      | httpx                                   |
| Logging          | structlog                               |
| Scheduler (Ph 6) | APScheduler + ARQ                       |
| Tests            | pytest + pytest-asyncio + httpx         |

## Phase 1 layout

```
outrena-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI factory + /health endpoint
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic settings (single source of truth)
│   │   ├── database.py              # async engine + Base + AsyncSessionLocal
│   │   ├── cache.py                 # Redis client + tenant_key namespacing
│   │   ├── logging.py               # structlog configuration
│   │   └── security.py              # JWT verify stubs (full impl: Phase 2)
│   ├── middleware/
│   │   └── tenant_middleware.py     # subdomain → tenant resolution
│   ├── schemas/
│   │   ├── auth.py                  # Role enum + TokenPayload
│   │   └── tenant.py                # tenant request/response contracts
│   ├── api/
│   │   ├── deps.py                  # FastAPI dependencies (get_db, get_current_user)
│   │   ├── security.py              # zero-trust auth guards (verify_role, verify_tenant)
│   │   └── routes/
│   │       └── platform.py          # /platform/tenants CRUD (Phase 2 activates)
│   ├── models/                      # SQLAlchemy 2.0 models (Phase 3 fills these in)
│   │   ├── base.py                  # TimestampMixin, CuidPrimaryKey
│   │   ├── tenant.py                # public.tenants registry model
│   │   ├── enums.py                 # 13 enum classes ported from Prisma
│   │   ├── prospect_models.py
│   │   ├── campaign_models.py
│   │   ├── flow_models.py
│   │   └── config_models.py
│   ├── services/                    # Business logic (Phase 2+)
│   │   ├── keycloak_admin_service.py
│   │   ├── tenant_provisioning_service.py
│   │   └── subdomain_allocation.py
│   └── utils/
│       └── slug.py
├── alembic/
│   ├── env.py                       # Phase 1: basic runner (Phase 2: dual-mode)
│   ├── script.py.mako
│   └── versions/                    # Phase 1: empty (Phase 2: 0001_initial_public.py)
├── keycloak/
│   └── realm-export.json            # realm 'outrena', 4 roles, frontend client, 5 test users
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # ASGI client fixture
│   └── test_health.py               # Phase 1 smoke test
├── pyproject.toml                   # backend deps + ruff + mypy + pytest config
├── Dockerfile                       # multi-stage: builder + slim runtime
├── .dockerignore
├── alembic.ini
├── .env.example
├── .gitignore
└── README.md                        # this file
```

## Phase 1 deliverables checklist

- [x] Monorepo structure: `outrena-backend/` + `outrena-frontend/` + `docker-compose.yml` (root)
- [x] Backend skeleton: `app/main.py`, `app/core/{config,database,cache,security,logging}.py`
- [x] Docker Compose: postgres:16, redis:7, keycloak:24, backend (uvicorn --reload), frontend (vite)
- [x] Keycloak `realm-export.json`: realm `outrena`, 4 realm roles, frontend client, 5 test users
- [x] Alembic initialized: `alembic.ini`, `alembic/env.py` (basic), empty `versions/`
- [x] CI: GitHub Actions — lint (ruff), typecheck (mypy), test (pytest), build Docker image
- [x] Health endpoint: `GET /health` → `{status, db, redis, keycloak}`

## Phase 1 exit criteria (per migration doc §6.5)

- [ ] `docker compose up` starts all 5 services (postgres, redis, keycloak, backend, frontend) cleanly
- [ ] `GET localhost:8000/health` returns `{status: 'ok'}`
- [ ] Keycloak admin console accessible at `localhost:8080` (admin/admin)
- [ ] Frontend dev server runs at `localhost:5173` (empty page, no errors)
- [ ] CI pipeline passes: ruff lint, mypy typecheck, pytest (smoke collection)
- [ ] Alembic initialized; `alembic current` returns `base` (no migrations yet)

## Quick start (local dev)

### Option A — Docker Compose (recommended)

From the migration root (parent of this folder):

```bash
cp outrena-backend/.env.example outrena-backend/.env
docker compose up -d
docker compose exec backend alembic current   # → 'base' (Phase 1)
curl http://localhost:8000/health | jq
```

### Option B — Native Python (no Docker)

```bash
cd outrena-backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Requires PostgreSQL 16 + Redis 7 + Keycloak 24+ running natively
cp .env.example .env
# adjust DATABASE_URL / REDIS_URL / KEYCLOAK_BASE_URL as needed

# Run the app
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In another shell — run the smoke test
pytest -v

# Or just hit the health endpoint
curl http://localhost:8000/health | jq
```

## Keycloak admin console

- URL: `http://localhost:8080`
- Admin user: `admin` / `admin`
- Realm: `outrena` (auto-imported on startup via `--import-realm`)

## Test users (realm `outrena`)

| Username                | Password    | Role          | tenant_slug |
|-------------------------|-------------|---------------|-------------|
| superadmin@outrena.com  | admin123    | super_admin   | (none)      |
| admin@acme.com          | admin123    | tenant_admin  | acme        |
| manager@acme.com        | manager123  | manager       | acme        |
| rep@acme.com            | rep123      | rep           | acme        |
| admin@globex.com        | admin123    | tenant_admin  | globex      |

## CI pipeline (`.github/workflows/ci.yml`)

The Phase 1 CI pipeline runs on every push / pull request:

1. **lint** — `ruff check app tests`
2. **format-check** — `ruff format --check app tests`
3. **typecheck** — `mypy app`
4. **test** — `pytest -v --cov=app`
5. **build-image** — `docker build -t outrena-backend:ci .` (Phase 1 only — no push)

## What's NOT in Phase 1

The following files exist in this folder (committed by the prior migration
session) but are NOT activated until later phases. They are included now to
preserve continuity; they compile cleanly against the Phase 1 skeleton and
will be exercised by Phase 2+ tests.

- `app/api/routes/platform.py` → activated in Phase 2 (needs public.tenants table)
- `app/api/security.py` (zero-trust guards) → activated in Phase 2 (needs JWKS)
- `app/services/keycloak_admin_service.py` → activated in Phase 2
- `app/services/tenant_provisioning_service.py` → activated in Phase 2
- `app/services/subdomain_allocation.py` → activated in Phase 2
- `app/models/{prospect,campaign,flow,config}_models.py` → activated in Phase 3
- `app/models/enums.py` → activated in Phase 3

## Architecture notes (per migration doc §4 + §5)

- **Tenancy**: schema-per-tenant (PostgreSQL). One schema per tenant
  (`tenant_{slug}`); platform registry in `public`. NO `tenant_id` columns on
  tenant-scoped tables — isolation is structural via `search_path`.
- **CORS first**: Starlette runs middleware in reverse registration order, so
  `CORSMiddleware` is registered before `TenantMiddleware` to wrap tenant
  resolution (see `app/main.py`).
- **`get_db()`** sets `search_path` per-request (Phase 2 dependency).
- **Redis namespacing**: every tenant-scoped cache key is prefixed with the
  tenant schema name (see `app/core/cache.py:tenant_key()`).
- **Zero-trust auth**: every protected endpoint applies `verify_tenant` +
  `verify_role` guards in order (see `app/api/security.py`).
- **JWT verification**: dev uses `SKIP_JWT_VERIFICATION=true`; prod uses JWKS
  fetched from Keycloak and cached in Redis for 1 hour (Phase 2).

## Migration source

This backend is a faithful migration of:
- `prisma/schema.prisma` (47 models, 13 enums) → `app/models/`
- `src/lib/*` (LLM, platform-search, mailbridge, flow-execution) → `app/services/` (Phase 4+)
- `src/app/api/**/route.ts` (95 routes) → `app/features/*/router.py` (Phase 4)
- `mini-services/scheduler/index.ts` (Bun scheduler) → APScheduler + ARQ (Phase 6)
- NextAuth v4 → Keycloak 24+ (this phase — realm-export.json)

See the migration document for the complete plan:
`/home/z/my-project/OUTRENA-Migration-Document.docx`
