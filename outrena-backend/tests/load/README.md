# OUTRENA — locust Load Test Suite

Load tests for the OUTRENA migration, as defined in **migration doc §15.4
(Load Testing)**:

> locust simulates:
>   - 100 concurrent tenants (each with 3 users)
>   - 1000 sequences per tick
>   - 10 autopilot pipeline runs per minute
>   - 50 CSV imports per hour (10MB each)
>
> Targets: p95 API latency < 500ms, p95 tick duration < 30s, zero
> cross-tenant data leakage (verified by post-test isolation audit).

## Layout

```
tests/load/
├── __init__.py
├── locustfile.py      # OutrenaUser (9 weighted tasks) + MultiTenantLoadShape
├── requirements.txt   # locust (pinned)
└── README.md          # this file
```

## What the suite simulates

`OutrenaUser` issues 9 weighted tasks against the live backend. The task
weights mirror the real OUTRENA production traffic mix:

| Task                      | Weight | Endpoint                              | Spec coverage                       |
|---------------------------|--------|---------------------------------------|-------------------------------------|
| `list_sequences`          | 10     | `GET /api/v1/sequences/cadence`       | 1000 sequences per tick (§15.4)     |
| `list_prospects`          | 8      | `GET /api/v1/prospects`               | Rep dashboard reads                 |
| `get_analytics`           | 6      | `GET /api/v1/analytics/overview`      | Manager dashboard reads             |
| `trigger_autopilot`       | 5      | `POST /api/v1/autopilot`              | 10 autopilot runs/min (§15.4)       |
| `list_campaigns`          | 4      | `GET /api/v1/campaigns`               | Campaign list reads                 |
| `get_autopilot_status`    | 3      | `GET /api/v1/autopilot/{task_id}`     | Front-end status polling            |
| `create_prospect`         | 2      | `POST /api/v1/prospects`              | Prospect writes (CSV import path)   |
| `mailbridge_health`       | 2      | `GET /api/v1/mailbridge/health`       | Mailbridge connectivity ping        |
| `preflight_check`         | 1      | `POST /api/v1/campaigns/preflight`    | Preflight gate (manager-only)       |

`MultiTenantLoadShape` stages the load:

```
   100 ┤                    ┌────────────────────────┐
       │                  ╱╲                          ╲
       │                ╱    ╲                          ╲
       │              ╱        ╲                          ╲
       │            ╱            ╲                          ╲
       │          ╱                ╲                          ╲
       │        ╱                    ╲                          ╲
       │      ╱                        ╲                          ╲
     0 ┤────╱                            ╲──────────────────────────┘
       └──┬───────────┬───────────────────────┬─────────────┬──────────
          0s         60s                    360s          390s
          │←─ramp up→│←──── steady state ────→│←ramp down→│
```

## Prerequisites

| Service           | Default URL                  | Env var to override        |
|-------------------|------------------------------|----------------------------|
| Backend (FastAPI) | `http://localhost:8000`      | `--host` flag              |

The backend must be running with the production-like config (real
PostgreSQL + Redis + Keycloak + Celery worker). The tenant slugs in
`LOAD_TENANT_SLUGS` must all be `ACTIVE` and migrated to head.

For a realistic 100-tenant test, provision 100 tenants via the platform
provisioning API first:

```bash
for slug in acme contoso globex ... tenant100; do
  curl -X POST http://localhost:8000/platform/tenants \
    -H "Authorization: Bearer $PLATFORM_ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"slug\":\"$slug\",\"name\":\"$slug Corp\",\"admin_email\":\"admin@$slug.test\"}"
done
```

## Installation

```bash
pip install -r tests/load/requirements.txt
```

## Environment variables

| Variable             | Default   | Required? | Description                                                                 |
|----------------------|-----------|-----------|-----------------------------------------------------------------------------|
| `LOAD_AUTH_TOKEN`    | _(none)_  | yes       | Bearer token attached to every request. Mint a manager-scoped JWT.          |
| `LOAD_TENANT_SLUG`   | `acme`    | no        | Single tenant slug (used when `LOAD_TENANT_SLUGS` is unset).                |
| `LOAD_TENANT_SLUGS`  | _(none)_  | yes (100-tenant) | Comma-separated list of 100 tenant slugs. Drives the pool-based tenant rotation. |

## Running the suite

### Single-tenant smoke test (quick — 1 min)

```bash
export LOAD_AUTH_TOKEN="$(./scripts/mint-test-jwt acme manager)"
export LOAD_TENANT_SLUG=acme

locust -f tests/load/locustfile.py \
    --host http://localhost:8000 \
    --headless -u 10 -r 2 --run-time 1m
```

### Full 100-tenant load test (spec §15.4 — 6 min)

```bash
# 1. Provision 100 tenants (see Prerequisites above).
# 2. Set the tenant pool.
export LOAD_TENANT_SLUGS=acme,contoso,globex,...,tenant100  # 100 comma-separated slugs
export LOAD_AUTH_TOKEN="$(./scripts/mint-test-jwt acme manager)"

# 3. Run with the staged load shape (NO -u / -r flags — the shape controls them).
locust -f tests/load/locustfile.py \
    --host http://localhost:8000 \
    --headless --run-time 6m \
    --csv=load-results \
    --html=load-results.html
```

The `MultiTenantLoadShape` will:
  * ramp 0 → 100 users over 60 s,
  * hold 100 users for 5 min (steady state),
  * ramp 100 → 0 users over 30 s.

### Web UI mode (local debugging)

```bash
locust -f tests/load/locustfile.py --host http://localhost:8000
# Open http://localhost:8089 in a browser.
```

## Interpreting results

### SLO targets (spec §15.4)

| Metric                          | SLO target           | Where to find it in the report        |
|---------------------------------|----------------------|---------------------------------------|
| Read API latency (p95)          | < 500 ms             | Per-request-type stats table          |
| Autopilot trigger latency (p99) | < 2 s                | `POST /autopilot` row                 |
| Scheduler tick duration (p95)   | < 30 s               | Out-of-band: check scheduler logs     |
| Cross-tenant data leakage       | 0 incidents          | Post-test: run `tests/integration/test_isolation.py` |
| Error rate                      | < 1 %                | Aggregated stats row                  |

### Failure modes to watch

* **5xx spike on `GET /sequences/cadence`** → the scheduler-tick read path
  is the hottest endpoint; a 5xx here means the connection pool is
  exhausted. Bump `DATABASE_POOL_SIZE` in the backend config.
* **p99 > 2 s on `POST /autopilot`** → the LLM gateway is the bottleneck.
  Check the LLM provider's rate-limit headers; consider enabling the
  in-process LLM response cache.
* **4xx surge on tenant-scoped endpoints** → the tenant middleware's
  slug-resolution cache is missing. Check that
  `TENANT_CACHE_TTL_SECONDS` is > 0.
* **Connection refused after ramp-up** → the backend's uvicorn workers
  can't keep up. Scale horizontally (more backend pods) or vertically
  (more workers per pod).

### CSV output columns

The `--csv=load-results` flag produces three files:

  * `load-results_stats.csv` — per-request-type stats (count, latency
    percentiles, failure rate).
  * `load-results_stats_history.csv` — time-series of the run (one row
    per 5 s window) — useful for plotting the latency-over-time curve.
  * `load-results_failures.csv` — every failure event with timestamp +
    error message.

The CI pipeline uploads all three as build artifacts and graphs the
latency-over-time curve in Grafana.

## Limitations

* The CSV import path (spec §15.4: "50 CSV imports per hour, 10MB each")
  is NOT directly simulated — `create_prospect` issues single-row POSTs
  instead. This is intentional: simulating 10MB CSV uploads in locust
  would saturate the test runner's network before the backend. The CSV
  import path is covered by `tests/integration/test_csv_import.py`
  (separate suite).
* The 100-tenant simulation is pool-based — each OutrenaUser picks a
  random slug at `on_start`. This means tenant slug assignment is
  probabilistic, not deterministic; with 100 users and 100 slugs, the
  birthday problem means ~37% of slugs will have 0 users and ~37% will
  have 2+. For deterministic per-tenant metrics, use the tag-based
  approach (100 locust processes, one per tenant) documented in the
  `MultiTenantLoadShape` class docstring.
* The shape's 5-min steady state is shorter than a real production
  load test (which would run 30+ min). Bump `STEADY_SECONDS` in
  `locustfile.py` for longer runs.
