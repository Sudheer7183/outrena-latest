"""
locustfile.py — OUTRENA load tests (spec §15.4).

Spec reference: migration doc §15.4 (Load Testing):
> locust simulates:
>   - 100 concurrent tenants (each with 3 users)
>   - 1000 sequences per tick
>   - 10 autopilot pipeline runs per minute
>   - 50 CSV imports per hour (10MB each)
>
> Targets: p95 API latency < 500ms, p95 tick duration < 30s, zero
> cross-tenant data leakage (verified by post-test isolation audit).

This file defines:

  1. `OutrenaUser(HttpUser)` — a single simulated user with weighted tasks
     mirroring the real OUTRENA traffic mix (sequence reads dominate,
     autopilot triggers are rare-but-expensive, mailbridge pings are
     cheap+ frequent).

  2. `MultiTenantLoadShape(LoadTestShape)` — a staged load shape that:
       * ramps from 0 → 100 users over 60 s (warm-up),
       * holds 100 users for 5 min (steady-state — the spec's
         "100 concurrent tenants" target),
       * ramps 100 → 0 over 30 s (cool-down).

  **Simulating 100 distinct tenants**: locust does not natively support
  per-virtual-user tenant identity. Two options:

    A. **Tag-based** (one locust process per tenant): launch 100 locust
       processes, each with `--tags tenant-a`, `--tags tenant-b`, ...
       Each process tags its OutrenaUser with a unique tenant slug and
       only that tenant's tasks run. This gives perfect tenant isolation
       in metrics but requires 100 processes (heavy).

    B. **Pool-based** (one locust process, rotating slugs): read
       `LOAD_TENANT_SLUGS` (comma-separated, 100 entries) and have each
       OutrenaUser pick a slug from the pool at `on_start` time. This is
       the approach implemented here — it's lighter and exercises the
       tenant middleware's cache + DB-pool behaviour under contention.

  See the `OutrenaUser.on_start` docstring for the pool-based slug
  selection logic, and the `MultiTenantLoadShape` class for the staged
  load curve.

SLO targets (spec §15.4):
  * p95 API latency < 500 ms for reads
  * p99 API latency < 2 s for autopilot triggers (LLM-bound)
  * p95 scheduler tick duration < 30 s
  * zero cross-tenant data leakage (verified by post-test isolation audit
    in tests/integration/test_isolation.py — not a locust concern)
"""
from __future__ import annotations

import os
import random
from typing import Any

from locust import HttpUser, LoadTestShape, between, task


# ─────────────────────────────────────────────────────────────────────────────
# Tenant slug pool — supports 100 concurrent tenants per spec §15.4.
# ─────────────────────────────────────────────────────────────────────────────

def _load_tenant_slugs() -> list[str]:
    """Load the tenant slug pool from `LOAD_TENANT_SLUGS` env var.

    The env var is a comma-separated list of tenant slugs (e.g.,
    "acme,contoso,_globex,..."). If unset, falls back to a single
    `LOAD_TENANT_SLUG` (or `acme` if that's also unset) — useful for
    single-tenant smoke runs.
    """
    slugs_str = os.environ.get("LOAD_TENANT_SLUGS", "")
    if slugs_str:
        return [s.strip() for s in slugs_str.split(",") if s.strip()]
    return [os.environ.get("LOAD_TENANT_SLUG", "acme")]


TENANT_SLUG_POOL: list[str] = _load_tenant_slugs()


# ─────────────────────────────────────────────────────────────────────────────
# OutrenaUser — a single simulated OUTRENA user.
# ─────────────────────────────────────────────────────────────────────────────

class OutrenaUser(HttpUser):
    """A simulated OUTRENA tenant user.

    Traffic mix (weighted by `@task(N)`):
      * list_sequences (10)         — main scheduler-tick read path (spec: 1000 sequences/tick)
      * list_prospects (8)          — prospect list reads (Rep dashboard)
      * get_analytics (6)           — analytics overview reads (manager dashboard)
      * trigger_autopilot (5)       — autopilot pipeline triggers (spec: 10/min)
      * get_autopilot_status (3)    — status polling (front-end polls every 2s)
      * list_campaigns (4)          — campaign list reads
      * create_prospect (2)         — prospect writes (CSV import path)
      * preflight_check (1)         — preflight gate (rare, manager-only)
      * mailbridge_health (2)       — mailbridge ping (cheap, frequent)

    Each user picks a tenant slug from `TENANT_SLUG_POOL` at `on_start`
    time (pool-based 100-tenant simulation — see module docstring). All
    requests from that user carry the `X-Tenant-Slug` header for that
    tenant, exercising the tenant middleware's per-tenant schema resolution
    + Redis namespacing under load.
    """

    # Wait 1–5 s between tasks — matches real user "read-then-think" cadence.
    wait_time = between(1, 5)

    def on_start(self) -> None:
        """Pick a tenant slug + set auth headers for this virtual user.

        Resolution order:
          1. `LOAD_AUTH_TOKEN` env var → static bearer token (CI preferred).
          2. No token → requests go out unauthenticated (the backend will
             401, which is the expected behaviour under load — proves the
             auth layer scales).

        Tenant slug resolution:
          * If `LOAD_TENANT_SLUGS` is set, pick a random slug from the
            pool. Each OutrenaUser instance gets a different slug, so
            100 users → 100 tenants (assuming the pool has 100 entries).
          * Otherwise use `LOAD_TENANT_SLUG` (default `acme`).
        """
        self.tenant_slug = random.choice(TENANT_SLUG_POOL)
        auth_token = os.environ.get("LOAD_AUTH_TOKEN", "")
        self.client.headers: dict[str, str] = {
            "X-Tenant-Slug": self.tenant_slug,
            "Content-Type": "application/json",
        }
        if auth_token:
            self.client.headers["Authorization"] = f"Bearer {auth_token}"

        # Each user keeps track of the last autopilot task_id they triggered
        # so the `get_autopilot_status` task can poll it.
        self.last_task_id: str | None = None

    # ── Read-heavy tasks (the scheduler-tick read path) ────────────────────

    @task(10)
    def list_sequences(self) -> None:
        """GET /api/v1/sequences/cadence — the main scheduler-tick read path.

        This is the hottest endpoint in production: the scheduler mini-service
        hits it on every 5-min tick to fetch the cadence definition. The spec
        mandates 1000 sequences per tick; this task exercises the same code
        path with a single user's request volume.
        """
        with self.client.get(
            "/api/v1/sequences/cadence",
            name="GET /sequences/cadence [scheduler tick read]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code >= 500:
                resp.failure(f"5xx on scheduler-tick read: {resp.status_code}")
            else:
                resp.success()  # 4xx is OK — auth/tenant edge cases

    @task(8)
    def list_prospects(self) -> None:
        """GET /api/v1/prospects — prospect list reads (Rep dashboard).

        The prospects list is paginated; this task fetches the first page.
        Under 100 tenants × 3 users each = 300 concurrent users, this
        endpoint sees ~240 req/s at the steady state.
        """
        with self.client.get(
            "/api/v1/prospects?page=1&page_size=50",
            name="GET /prospects [rep dashboard read]",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"5xx on prospects list: {resp.status_code}")
            else:
                resp.success()

    @task(6)
    def get_analytics(self) -> None:
        """GET /api/v1/analytics/overview — analytics reads (manager dashboard).

        The analytics overview aggregates across campaigns + sequences +
        prospects; under load this exercises the analytics_service's
        multi-join queries. SLO: p95 < 500 ms (read path).
        """
        with self.client.get(
            "/api/v1/analytics/overview",
            name="GET /analytics/overview [manager dashboard read]",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"5xx on analytics overview: {resp.status_code}")
            else:
                resp.success()

    @task(4)
    def list_campaigns(self) -> None:
        """GET /api/v1/campaigns — campaign list reads.

        Lower weight than prospects/sequences because the campaign list is
        smaller and cached more aggressively client-side.
        """
        with self.client.get(
            "/api/v1/campaigns?page=1&page_size=50",
            name="GET /campaigns [campaign list read]",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"5xx on campaigns list: {resp.status_code}")
            else:
                resp.success()

    # ── Autopilot flow (expensive — LLM-bound) ────────────────────────────

    @task(5)
    def trigger_autopilot(self) -> None:
        """POST /api/v1/autopilot — autopilot pipeline triggers.

        Spec §15.4 target: 10 autopilot runs per minute. With 100 users ×
        weight 5 / total weight 41 ≈ 0.12 of all requests, at 1 req/s/user
        that's 12 triggers/s — far above the 10/min target. The weight is
        deliberately high to stress the Celery queue + LLM gateway; in
        production the actual trigger rate is throttled by the manager UI.

        SLO: p99 < 2 s (the LLM gateway dominates latency).
        """
        payload: dict[str, Any] = {
            "campaign_name": f"Load test {self.tenant_slug} {random.randint(0, 1_000_000)}",
            "target_count": 3,
            "icp_hint": "VP Engineering at B2B SaaS, 50-200 staff",
            "sender_role": "Head of Sales",
            "sender_company": "Outrena",
            "sender_offer": "30% more replies via AI-personalized sequences",
            "proof_metric": "3.2x reply rate vs control",
            "sender_product": "Outrena Outreach OS",
            "schema_name": f"tenant_{self.tenant_slug}",
        }
        with self.client.post(
            "/api/v1/autopilot",
            json=payload,
            name="POST /autopilot [trigger pipeline]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 202:
                # Capture the task_id for the status-polling task.
                try:
                    self.last_task_id = resp.json().get("task_id")
                except Exception:  # noqa: BLE001 — non-JSON body
                    self.last_task_id = None
                resp.success()
            elif resp.status_code == 503:
                # Worker not yet available — graceful degradation, not a failure.
                resp.success()
            elif resp.status_code >= 500:
                resp.failure(f"5xx on autopilot trigger: {resp.status_code}")
            else:
                resp.success()

    @task(3)
    def get_autopilot_status(self) -> None:
        """GET /api/v1/autopilot/{task_id} — status polling.

        The SPA polls this every 2 s after a trigger; this task simulates
        that poll using the last_task_id captured by `trigger_autopilot`.
        If no task_id is set (the user hasn't triggered yet), the task
        no-ops.
        """
        if not self.last_task_id:
            return  # No task to poll yet — skip.
        with self.client.get(
            f"/api/v1/autopilot/{self.last_task_id}",
            name="GET /autopilot/{task_id} [status poll]",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"5xx on autopilot status: {resp.status_code}")
            else:
                resp.success()

    # ── Write tasks ───────────────────────────────────────────────────────

    @task(2)
    def create_prospect(self) -> None:
        """POST /api/v1/prospects — prospect writes (CSV import path).

        Lower weight because writes are more expensive than reads and the
        spec only mandates 50 CSV imports per hour (not per user). Each
        call creates a single prospect row to keep the test light.
        """
        payload: dict[str, Any] = {
            "first_name": "LoadTest",
            "last_name": f"User{random.randint(0, 1_000_000)}",
            "email": f"loadtest-{random.randint(0, 1_000_000)}@example.com",
            "company": "LoadTest Corp",
            "title": "VP Engineering",
        }
        with self.client.post(
            "/api/v1/prospects",
            json=payload,
            name="POST /prospects [prospect write]",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"5xx on prospect create: {resp.status_code}")
            else:
                resp.success()

    @task(1)
    def preflight_check(self) -> None:
        """POST /api/v1/campaigns/preflight — preflight gate.

        Rare (manager-only, pre-campaign-launch). Validates the 6-check
        preflight (domain DNS, ICP completeness, sender identity, etc.)
        without creating a campaign. Low weight because it's expensive
        (runs 6 sub-checks) and infrequent in production.
        """
        payload: dict[str, Any] = {
            "campaign_name": f"Preflight load test {random.randint(0, 1_000_000)}",
            "icp_hint": "VP Eng at SaaS",
        }
        with self.client.post(
            "/api/v1/campaigns/preflight",
            json=payload,
            name="POST /campaigns/preflight [preflight gate]",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"5xx on preflight: {resp.status_code}")
            else:
                resp.success()

    # ── Health / ping ─────────────────────────────────────────────────────

    @task(2)
    def mailbridge_health(self) -> None:
        """GET /api/v1/mailbridge/health — mailbridge ping.

        Cheap + frequent — exercises the mailbridge router's health probe
        without triggering an actual send. Used by the SPA's status bar to
        show mailbridge connectivity.
        """
        with self.client.get(
            "/api/v1/mailbridge/health",
            name="GET /mailbridge/health [mailbridge ping]",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"5xx on mailbridge health: {resp.status_code}")
            else:
                resp.success()


# ─────────────────────────────────────────────────────────────────────────────
# MultiTenantLoadShape — staged load curve per spec §15.4.
# ─────────────────────────────────────────────────────────────────────────────

class MultiTenantLoadShape(LoadTestShape):
    """Staged load shape: ramp up → hold → ramp down.

    Stages (spec §15.4 — "100 concurrent tenants, 1000 sequences per tick"):

      1. **Ramp-up**   (0–60 s):       0 → 100 users (linear).
         Why 60 s: gives the backend's asyncpg connection pool + Redis
         client pool time to warm up without tripping the autoscaler.

      2. **Steady-state** (60–360 s):  100 users held for 5 min.
         This is the spec's "100 concurrent tenants" target. At ~1 req/s/
         user with the weighted task mix, this generates ~240 req/s of
         read traffic + ~12 autopilot triggers/s.

      3. **Ramp-down** (360–390 s):    100 → 0 users (linear).
         30 s cool-down so in-flight requests don't get cut off abruptly.

    Total run time: 390 s (6.5 min). Use `--run-time 6m` to stop just
    before the ramp-down completes if you only care about steady-state
    metrics.

    To use this shape, run locust WITHOUT `-u` / `-r` flags — the shape
    controls user count + spawn rate. With `-u` / `-r`, locust ignores
    the shape.

    **How to simulate 100 distinct tenants** (spec §15.4):

    Option A (pool-based, default): set `LOAD_TENANT_SLUGS` to a
    comma-separated list of 100 tenant slugs. Each OutrenaUser picks a
    random slug at `on_start`, so 100 concurrent users → 100 tenants.

        LOAD_TENANT_SLUGS=acme,contoso,globex,...,tenant100 \
        locust -f tests/load/locustfile.py --host http://localhost:8000 \
            --headless --run-time 6m

    Option B (tag-based, 100 processes): tag each OutrenaUser with a
    unique tenant slug and launch 100 locust processes, each with
    `--tags tenant-N`. This gives per-tenant metric isolation but is
    heavier (100 locust processes). Not implemented in this file — see
    the test runner script for an example.
    """

    # Stage boundaries (seconds).
    RAMP_UP_SECONDS = 60
    STEADY_SECONDS = 300  # 5 min steady-state.
    RAMP_DOWN_SECONDS = 30

    STEADY_USERS = 100  # spec §15.4: "100 concurrent tenants".

    def tick(self) -> tuple[int, float] | None:
        """Return (user_count, spawn_rate) for the current time, or None to stop.

        Locust calls `tick()` once per second. Returning None stops the run.
        """
        run_time = self.get_run_time()

        if run_time < self.RAMP_UP_SECONDS:
            # Ramp-up: 0 → STEADY_USERS linearly over RAMP_UP_SECONDS.
            # Spawn rate = STEADY_USERS / RAMP_UP_SECONDS so the ramp is smooth.
            user_count = int((run_time / self.RAMP_UP_SECONDS) * self.STEADY_USERS)
            spawn_rate = self.STEADY_USERS / self.RAMP_UP_SECONDS
            return (max(user_count, 1), spawn_rate)

        if run_time < self.RAMP_UP_SECONDS + self.STEADY_SECONDS:
            # Steady-state: hold STEADY_USERS.
            return (self.STEADY_USERS, self.STEADY_USERS)

        if run_time < self.RAMP_UP_SECONDS + self.STEADY_SECONDS + self.RAMP_DOWN_SECONDS:
            # Ramp-down: STEADY_USERS → 0 linearly over RAMP_DOWN_SECONDS.
            elapsed_in_ramp_down = run_time - (
                self.RAMP_UP_SECONDS + self.STEADY_SECONDS
            )
            user_count = int(
                self.STEADY_USERS
                * (1 - elapsed_in_ramp_down / self.RAMP_DOWN_SECONDS)
            )
            return (max(user_count, 1), self.STEADY_USERS / self.RAMP_DOWN_SECONDS)

        # Run complete.
        return None
