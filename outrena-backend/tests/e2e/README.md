# OUTRENA — Playwright E2E Test Suite

End-to-end tests for the OUTRENA migration golden path, as defined in
**migration doc §15.2 (Playwright E2E)**:

> Login → autopilot → sequence review → reply triage; cross-tenant URL
> access with wrong token → 403.

## Layout

```
tests/e2e/
├── __init__.py
├── conftest.py                      # pytest + Playwright fixtures (browser, context, page, authed_page)
├── pytest.ini                       # markers, asyncio_mode, addopts
├── requirements.txt                 # playwright + pytest-playwright (pinned)
├── test_login_flow.py               # login → dashboard, logout, failure cases
├── test_autopilot_flow.py           # autopilot pipeline: trigger → poll → SUCCESS → campaign + emails
├── test_sequence_review_flow.py     # sequence review: list, approve, reject, edit
├── test_reply_triage_flow.py        # reply triage: view, classify, route to CRM
└── README.md                        # this file
```

## Prerequisites

The E2E suite runs against a **live** stack — there are no mocks. Before
running the suite, ensure the following are up:

| Service            | Default URL                         | Env var to override        |
|--------------------|-------------------------------------|----------------------------|
| Frontend (Vite)    | `http://localhost:5173`             | `E2E_BASE_URL`             |
| Backend (FastAPI)  | `http://localhost:8000`             | `E2E_API_BASE_URL`         |
| Keycloak           | `http://localhost:8080/realms/outrena` | `KEYCLOAK_URL` (backend) |

The Keycloak realm `outrena` must have a test user provisioned with the
`manager` role (so the autopilot + sequence review flows are authorised).
The platform provisioning seed (`app/services/tenant_provisioning_service.py`)
creates this user when `E2E_TENANT_SLUG` is provisioned.

The tenant identified by `E2E_TENANT_SLUG` (default `acme`) must be
`ACTIVE` in `public.tenants` and its `tenant_acme` schema must have been
migrated to head (`alembic upgrade head` with `ALEMBIC_TARGET_SCHEMA=tenant_acme`).

## Installation

```bash
# 1. Install Python deps (pinned — see requirements.txt).
pip install -r tests/e2e/requirements.txt

# 2. Download the chromium browser binary (one-time, ~150 MB).
playwright install chromium
```

## Environment variables

| Variable                    | Default                       | Required? | Description                                           |
|-----------------------------|-------------------------------|-----------|-------------------------------------------------------|
| `E2E_BASE_URL`              | `http://localhost:5173`       | yes       | Frontend Vite dev server URL.                         |
| `E2E_API_BASE_URL`          | `http://localhost:8000`       | yes       | Backend FastAPI base URL.                             |
| `E2E_TEST_USERNAME`         | _(none)_                      | yes       | Keycloak test user (skips suite if unset).            |
| `E2E_TEST_PASSWORD`         | _(none)_                      | yes       | Keycloak test password (skips suite if unset).        |
| `E2E_TENANT_SLUG`           | `acme`                        | yes       | Tenant slug the test user belongs to.                 |
| `E2E_HEADLESS`              | `1`                           | no        | `0` = run headed (local debugging).                   |
| `E2E_AUTOMATION_FAULT_INJECT` | `0`                         | no        | `1` = enable the autopilot partial-failure test.      |

## Running the suite

```bash
# From the backend root (outrena-backend/):
export E2E_TEST_USERNAME=manager@acme.test
export E2E_TEST_PASSWORD='change-me-in-CI'
export E2E_TENANT_SLUG=acme

# Run the full E2E suite (slow — ~5–10 min against a live stack):
pytest tests/e2e/ -m e2e

# Run only the login flow (fast — ~30 s):
pytest tests/e2e/ -m e2e_login

# Run the autopilot golden path only:
pytest tests/e2e/ -m e2e_autopilot

# Exclude the slow autopilot partial-failure test (pre-merge gate):
pytest tests/e2e/ -m "e2e and not slow"

# Headed for local debugging (shows the browser):
E2E_HEADLESS=0 pytest tests/e2e/ -m e2e_login

# Verbose, single test:
pytest tests/e2e/test_login_flow.py::test_login_success -v
```

## CI integration

The recommended CI gate is two-stage:

1. **Pre-merge gate** (every PR): `pytest tests/e2e/ -m "e2e and not slow and not e2e_autopilot"`
   — login, sequence review, reply triage. ~2 min against a docker-compose stack.
2. **Nightly / staging-deploy gate**: `pytest tests/e2e/ -m e2e` — full golden
   path including the autopilot pipeline (which takes 60–120 s per run).

Screenshots + videos are captured on failure (see `conftest.py`'s
`pytest_runtest_makereport` hook) and stored as `tests/e2e/.videos/`. In CI,
upload this directory as a build artifact.

## Markers

| Marker            | Selects                                                           |
|-------------------|-------------------------------------------------------------------|
| `e2e`             | All E2E tests in this directory.                                  |
| `e2e_login`       | `test_login_flow.py` tests.                                       |
| `e2e_autopilot`   | `test_autopilot_flow.py` tests.                                   |
| `e2e_sequence`    | `test_sequence_review_flow.py` tests.                             |
| `e2e_reply`       | `test_reply_triage_flow.py` tests.                                |
| `slow`            | Tests that take > 30 s (the autopilot pipeline tests).            |

## Selectors contract

The tests use `data-testid` selectors exclusively (no CSS classes, no
visible-text matching unless unavoidable). This is the contract between
the SPA and the E2E suite — if a selector changes, update the SPA's
`data-testid` attribute, not the test. The required `data-testid`s are
documented inline in each test file.
