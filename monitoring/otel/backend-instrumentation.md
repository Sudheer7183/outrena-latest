# OUTRENA Phase 8 — Backend OpenTelemetry Instrumentation Guide

This document describes how the FastAPI backend (and its Celery worker) are
instrumented to emit traces + logs via OpenTelemetry. The OTel Collector
config (`collector-config.yml`) is the downstream side of this story — this
document is the SDK side.

> **Status:** OpenTelemetry is OPT-IN. The app boots + serves /metrics fine
> without any of the OTel packages installed — Prometheus (which is wired
> by default) is the primary metrics path. OTel traces are a complementary
> pipeline for distributed tracing via Tempo. Install the OTel packages
> only when you actually want traces.

---

## 1. Dependencies

Already pinned in `outrena-backend/requirements.txt`:

```
opentelemetry-sdk==1.27.0
opentelemetry-api==1.27.0
opentelemetry-exporter-otlp==1.27.0
opentelemetry-instrumentation-fastapi==0.48b0
opentelemetry-instrumentation-sqlalchemy==0.48b0
opentelemetry-instrumentation-redis==0.48b0
opentelemetry-instrumentation-httpx==0.48b0
opentelemetry-instrumentation-logging==0.48b0
```

`pip install -r requirements.txt` installs them. The app does NOT import
them at module-load time — `setup_otel()` (below) is called from a `try /
except ImportError` block at app startup, so the absence of the packages
just disables tracing without crashing.

---

## 2. Instrumentation entrypoint — `outrena-backend/app/core/otel.py`

**STATUS: not yet implemented.** This file is the next step after this
migration — it is intentionally NOT created here because the SAAS2-OBS-BE
task scope is Prometheus + cost tracking. The OTel SDK side is documented
here so the next agent has a clear blueprint.

When implemented, the file should look like this:

```python
# outrena-backend/app/core/otel.py
"""Optional OpenTelemetry SDK bootstrap.

Called once at app startup from app/main.py create_app(). Idempotent —
safe to call from both FastAPI startup + Celery worker init. NO-OPs if
the opentelemetry packages are not installed (the app still works —
Prometheus is the primary metrics path).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def setup_otel(app=None) -> None:
    """Wire OTel SDK + auto-instrumentation. Best-effort — never raises."""
    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint:
            # OTel explicitly disabled — Prometheus is the only metrics path.
            return

        resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "outrena-backend"),
            "service.version": os.environ.get("OUTRENA_VERSION", "dev"),
            "service.namespace": "outrena",
            "deployment.environment": os.environ.get("ENVIRONMENT", "dev"),
        })

        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=endpoint + "/v1/traces")
            )
        )
        trace.set_tracer_provider(tracer_provider)

        # Auto-instrumentation — wraps FastAPI routes, SQLAlchemy queries,
        # Redis calls, httpx calls (LLM!), and the stdlib logging module.
        if app is not None:
            from opentelemetry.instrumentation.fastapi import (
                FastAPIInstrumentor,
            )
            FastAPIInstrumentor.instrument_app(app)

        from opentelemetry.instrumentation.sqlalchemy import (
            SQLAlchemyInstrumentor,
        )
        SQLAlchemyInstrumentor().instrument(enable_commenter=True)

        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()

        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()

        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        LoggingInstrumentor().instrument(set_logging_format=True)

        logger.info(
            "otel.setup_complete",
            extra={"endpoint": endpoint, "service": resource.attributes.get("service.name")},
        )
    except ImportError:
        # OTel packages not installed — Prometheus is the only metrics path.
        logger.info("otel.packages_not_installed_skipping_setup")
    except Exception as exc:  # noqa: BLE001 — OTel must never crash the app
        logger.warning("otel.setup_failed", extra={"error": str(exc)})
```

Then in `app/main.py`, add this near the top of `create_app()`:

```python
# Optional OpenTelemetry — best-effort, no-op if packages missing or env unset.
try:
    from app.core.otel import setup_otel
    setup_otel(application)
except Exception:  # noqa: BLE001
    pass
```

---

## 3. Environment variables

All three runtimes (backend, worker) MUST set these env vars when OTel is
desired. In ECS Fargate / Container Apps they are passed via the task
definition; in docker-compose via the `environment:` block (see
`docker-compose.prod.yml` otel-collector service).

| Var | Example | Description |
|-----|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4318` | OTLP HTTP base URL — points at the OTel Collector sidecar. When unset, OTel is disabled and Prometheus is the only metrics path. |
| `OTEL_SERVICE_NAME` | `outrena-backend` | Used as the `service.name` resource attribute. The worker sets this to `outrena-worker`. |
| `OTEL_RESOURCE_ATTRIBUTES` | `deployment.environment=prod,service.version=abc1234` | Resource attributes appended at the SDK side. Comma-separated `key=val`. |
| `OUTRENA_VERSION` | `git-sha-abc123` | Git SHA deployed — surfaces as `service.version`. |
| `ENVIRONMENT` | `production` | Sets `deployment.environment`. |
| `OTEL_TRACES_SAMPLER` | `parentbased_traceidratio` | Always parent-based so child spans inherit sampling decisions. |
| `OTEL_TRACES_SAMPLER_ARG` | `0.1` (prod) \| `1.0` (dev) | Sampling fraction. See §4 below. |

> These env vars are NOT yet in `app/core/config.py` (which is owned by
> the lead). The lead will add them when the OTel side is wired.

---

## 4. Sampling strategy

| Environment | Sample rate | Rationale |
|-------------|-------------|-----------|
| dev         | 100% (`1.0`) | Full visibility for debugging — Tempo storage is cheap in dev. |
| staging     | 50% (`0.5`) | Balance cost vs. statistical representativeness for load tests. |
| prod        | 10% (`0.1`) | Keep Tempo storage growth bounded; 10% gives plenty of statistical signal at our request volume (~100 RPS = 10 traces/sec). Errors and slow spans are always sampled via the `tail_sampling` policy if enabled (see `collector-config.yml`). |

The sampler is `parentbased_traceidratio` — child spans inherit the parent
decision. This means a single trace is either fully captured or fully
dropped, never partially. Critical for debugging end-to-end request flows.

---

## 5. Per-tenant context propagation

The FastAPI `RequestContextMiddleware` (in `app/main.py`) already binds
`tenant_slug` + `user_id` to the structlog contextvars from the JWT
(unverified — telemetry only). To propagate these to OTel spans, the
`setup_otel()` function should be followed by a small extension to the
existing `RequestContextMiddleware.dispatch()`:

```python
# Inside RequestContextMiddleware.dispatch, after the JWT extraction:
try:
    from opentelemetry import trace

    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        if tenant_slug:
            current_span.set_attribute("tenant_slug", tenant_slug)
        if user_id:
            current_span.set_attribute("user_id", user_id)
except ImportError:
    pass  # OTel not installed
```

This makes every span in Tempo filterable by `tenant_slug` — the
``service.name = outrena-backend AND tenant_slug = acme-corp`` query
becomes a one-click filter in Grafana Explore.

---

## 6. Custom metrics — Prometheus (not OTel)

OUTRENA's custom metrics (per-user cost, LLM tokens, email sends) are
emitted via **Prometheus** (see `app/core/metrics.py`), not OTel. This
is intentional:

- Prometheus is the **default** metrics path (no extra deps, always on).
- OTel metrics are a **secondary** path that gets enabled when the OTel
  sidecar is wired. The OTel collector forwards them to Prometheus via
  the `prometheusremotewrite` exporter (see `collector-config.yml`).

So custom metric definitions live in `app/core/metrics.py` (Counter /
Histogram / Gauge from `prometheus_client`). The OTel SDK side only
handles **traces** + **logs** + **auto-instrumentation** — it does NOT
define any custom metrics.

---

## 7. Verification

After OTel is wired (post this migration), confirm instrumentation is
working end-to-end:

1. **Tempo**: hit any `/api/v1/*` endpoint, then open Grafana → Explore →
   Tempo. Search for a trace where `service.name = outrena-backend`. The
   trace should span FastAPI → SQLAlchemy (with the SQL query in the span
   attributes) → Redis → HTTPX (LLM call).
2. **Prometheus**: `count by (tenant) (outrena_llm_calls_total)` should
   return one series per active tenant. (This already works today —
   Prometheus is the default path.)
3. **Loki**: `{service="outrena-backend"} |= "ERROR" | json` should show
   structured log lines with `tenant_slug`, `request_id`, `http.route`
   fields (via the OTel logging instrumentation).
4. **Cost dashboards**: Grafana → OUTRENA folder → "OUTRENA — Cost & Usage"
   and "OUTRENA — LLM Usage" dashboards (created by this migration) should
   populate within 1 minute of the first LLM call.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| No traces in Tempo | `OTEL_EXPORTER_OTLP_ENDPOINT` not set, or collector sidecar not running | `env \| grep OTEL` on the task; check collector `/metrics` on port 8888 |
| Traces present but missing `tenant_slug` attribute | `RequestContextMiddleware` does not call `current_span.set_attribute(...)` | Apply the §5 patch — set `tenant_slug` on the current span from `RequestContextMiddleware.dispatch()` |
| High cardinality in Prometheus (memory explosion) | `tenant` label on a high-cardinality metric (e.g., per-request_id histogram) | Drop the label at the collector via `attributes` processor `action: delete` |
| Collector OOM-killed | `memory_limiter.limit_mib` too high for Fargate task memory | Reduce to 1/4 of task memory (e.g., 512Mi for 2Gi task) — see `collector-config.yml` |
| Sampling too aggressive in prod | `OTEL_TRACES_SAMPLER_ARG=0.1` but error traces dropped | Enable `tail_sampling` in `collector-config.yml` to ALWAYS keep ERROR spans |
| App boots but no traces AND no errors in log | OTel packages not installed | `pip install -r requirements.txt` — the OTel block is in requirements.txt |
| `/metrics` returns empty / 500 | `prometheus_client` not installed | `pip install prometheus-client==0.21.1` |

---

## 9. Reference

- OTel Python docs: https://opentelemetry.io/docs/languages/python/
- Collector config reference: https://opentelemetry.io/docs/collector/configuration/
- `monitoring/otel/collector-config.yml` — the OTel Collector config
- `monitoring/prometheus/prometheus.yml` — the Prometheus scrape config
- `monitoring/grafana/dashboards/backend-overview.json` — Prometheus-backed dashboard
- `monitoring/grafana/dashboards/cost-usage.json` — per-user + per-tenant cost dashboard
- `monitoring/grafana/dashboards/llm-usage.json` — LLM token + cost dashboard
- `runbooks/14-cost-management.md` — FinOps + per-tenant cost attribution runbook
- `outrena-backend/app/core/metrics.py` — Prometheus metric definitions
- `outrena-backend/app/middleware/metrics_middleware.py` — HTTP metrics middleware
- `outrena-backend/app/services/cost_service.py` — per-provider cost computation
- `outrena-backend/app/services/usage_service.py` — UsageEvent recording + aggregation
- `outrena-backend/app/models/usage.py` — UsageEvent + CostSummary ORM
- `outrena-backend/alembic/versions/0006_usage_tracking.py` — DB migration
