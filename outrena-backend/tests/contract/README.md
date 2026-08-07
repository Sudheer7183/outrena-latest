# OUTRENA — schemathesis Contract Test Suite

Contract tests for the OUTRENA migration OpenAPI spec, as defined in
**migration doc §15.3 (Contract Testing)**:

> schemathesis runs against the OpenAPI spec, fuzzing every endpoint with
> random valid + invalid inputs. Any 5xx response (that isn't a deliberate
> 502 from an external service) fails the build.

## Layout

```
tests/contract/
├── __init__.py
├── conftest.py                         # schema + auth + tenant header fixtures
├── test_contract_all_endpoints.py     # 3 test functions: fuzz / stateful / negative
├── requirements.txt                    # schemathesis + hypothesis (pinned)
└── README.md                           # this file
```

## What the suite validates

| Test                          | What it does                                                                  | Spec rule                                           |
|-------------------------------|-------------------------------------------------------------------------------|-----------------------------------------------------|
| `test_api_validates`          | Fuzzes EVERY endpoint with random **valid** inputs; asserts response matches the documented status + schema. | Any 5xx fails the build (§15.3).            |
| `test_stateful_flows`         | Drives multi-step flows: autopilot (POST → GET status), campaigns (POST → GET → PUT → DELETE). | Stateful flows can't be fuzzed in isolation. |
| `test_negative_cases`         | Fuzzes every endpoint with **invalid** inputs (wrong types, missing required fields, out-of-range). | 4xx expected; 5xx fails the build (§15.3).  |

Failures are **collected, not aborted-on-first** — one endpoint's 5xx does
not prevent the rest of the spec from being fuzzed. The failure report at
the end of each test lists every violation.

## Prerequisites

| Service           | Default URL                  | Env var to override        |
|-------------------|------------------------------|----------------------------|
| Backend (FastAPI) | `http://localhost:8000`      | `CONTRACT_BASE_URL`        |

The backend must be running and its `/openapi.json` endpoint must be
reachable (i.e., not in production mode where docs are disabled). The
tenant identified by `CONTRACT_TENANT_SLUG` must be `ACTIVE` and migrated
to head.

If the backend is NOT running, the suite falls back to importing
`app.main:app` in-process and calling `app.openapi()` directly — this
catches schema regressions but not middleware-induced 5xxs.

## Installation

```bash
pip install -r tests/contract/requirements.txt
```

No browser or external binary download needed (unlike the E2E suite).

## Environment variables

| Variable                 | Default                  | Required? | Description                                                                  |
|--------------------------|--------------------------|-----------|------------------------------------------------------------------------------|
| `CONTRACT_BASE_URL`      | `http://localhost:8000`  | yes       | Backend FastAPI base URL.                                                    |
| `CONTRACT_TENANT_SLUG`   | `acme`                   | yes       | Tenant slug sent as `X-Tenant-Slug` header on every fuzzed request.          |
| `CONTRACT_AUTH_TOKEN`    | _(none)_                 | no        | Pre-minted JWT. If unset, the suite tries to mint one via `app.core.security.mint_test_jwt`. |

## Running the suite

```bash
# From the backend root (outrena-backend/):
export CONTRACT_TENANT_SLUG=acme
export CONTRACT_AUTH_TOKEN="$(./scripts/mint-test-jwt acme manager)"

# Run the full contract suite:
pytest tests/contract/ -m contract

# Run only the fuzz-every-endpoint test:
pytest tests/contract/test_contract_all_endpoints.py::test_api_validates -m contract

# Run only the stateful flows:
pytest tests/contract/test_contract_all_endpoints.py::test_stateful_flows -m contract

# Run only the negative cases:
pytest tests/contract/test_contract_all_endpoints.py::test_negative_cases -m contract

# Verbose, with hypothesis stats:
pytest tests/contract/ -m contract -v --hypothesis-show-statistics
```

## CI integration

The contract suite is fast (~2 min against a live backend) and should run
on every PR. Recommended CI gate:

```bash
# 1. Start the backend (docker-compose up -d backend postgres redis keycloak).
# 2. Run alembic upgrade head against the test tenant.
# 3. Mint a manager-scoped JWT.
# 4. Run the contract suite.
pytest tests/contract/ -m contract --hypothesis-show-statistics
```

A single 5xx response from any endpoint fails the build per spec §15.3.

## Why schemathesis and not Dredd / Postman / Schemathesis 4.x?

* **schemathesis** generates inputs from the OpenAPI spec automatically —
  no manual fixture maintenance when new endpoints are added. Adding a new
  route to `app/api/v1/` automatically extends the contract suite.
* The 3.x API (`@schema.parametrize()` + `case.validate_response()`) is
  stable and well-documented; 4.x changed the public surface
  significantly. We pin 3.39.5 for stability.
* Dredd requires a separate `dredd.yml` per endpoint and drifts from the
  spec silently. Postman collections are manual and don't fuzz.
* The migration spec (§15.3) explicitly names schemathesis.

## Limitations

* The OUTRENA OpenAPI spec does not yet declare `links` between
  POST → GET endpoints, so `test_stateful_flows` drives the transitions
  manually with `httpx.Client`. Adding `links` annotations to the spec
  would let schemathesis explore stateful transitions automatically.
* The negative-case test uses `max_examples=5` per endpoint to keep the
  run under 5 min. For deeper fuzzing, bump to `max_examples=25` and run
  nightly.
* Endpoints that hit external services (LLM providers, CRMs) may return
  502 — these are the spec's "deliberate 502 from an external service"
  exception and do NOT fail the build. The test tolerates 502s but flags
  500/503/504.
