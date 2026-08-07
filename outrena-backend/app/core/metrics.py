"""
metrics.py — Prometheus metric definitions for the OUTRENA backend.

All metrics share the ``outrena_`` prefix so they sort together in
Grafana and don't collide with the default Python / FastAPI
instrumentation when we add OpenTelemetry later.

Cardinality rules (CRITICAL — Prometheus memory grows linearly with the
number of distinct label-sets):

  1. NEVER label with raw URLs / path params — use the route pattern
     (e.g. ``/api/v1/campaigns/{id}``, NOT ``/api/v1/campaigns/c123``).
     The metrics middleware handles this normalization.
  2. NEVER label with request_id, prospect_id, or other per-request IDs.
  3. Prefer ``tenant_slug`` over ``tenant_id`` (slug is short + stable).
  4. ``user_id`` is only labeled on the emails_sent counter (it's a small
     finite set per tenant — bounded cardinality). Do NOT add user_id to
     the LLM or HTTP counters.

These metrics are scraped by Prometheus from ``GET /metrics`` (added by
main.py). The OTel collector ALSO exports equivalent metrics via OTLP —
the two paths are intentionally redundant so the dashboards keep working
if either pipeline breaks.
"""
from __future__ import annotations

import os

# Guard: if prometheus_client is not installed (e.g., during a CI lint
# pass that doesn't pip install), expose no-op shims so the import never
# crashes the app. Real installs always have prometheus_client (it's in
# requirements.txt).
try:
    from prometheus_client import Counter, Gauge, Histogram, Info, REGISTRY  # type: ignore

    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover — defensive, only hit in bare envs
    _PROMETHEUS_AVAILABLE = False

    class _NoopVec:  # type: ignore[no-redef]
        """Minimal stand-in matching the Counter/Histogram/Gauge .labels() API."""

        def __init__(self, *a, **kw) -> None:  # noqa: D401
            pass

        def labels(self, *a, **kw):  # noqa: D401, ANN001
            return self

        def inc(self, n: float = 1.0) -> None:  # noqa: D401
            pass

        def dec(self, n: float = 1.0) -> None:  # noqa: D401
            pass

        def observe(self, n: float) -> None:  # noqa: D401
            pass

        def set(self, n: float) -> None:  # noqa: D401
            pass

        def set_to_current_time(self) -> None:  # noqa: D401
            pass

        def time(self):  # noqa: D401
            from contextlib import contextmanager

            @contextmanager
            def _noop_timer():
                yield

            return _noop_timer()

        def info(self, d: dict) -> None:  # noqa: D401
            pass

    Counter = Gauge = Histogram = Info = _NoopVec  # type: ignore
    REGISTRY = None  # type: ignore


def _get_or_create(metric_cls, name: str, doc: str, labelnames=(), **kwargs):
    """Return an existing registered metric or create a new one.

    When uvicorn spawns worker sub-processes, this module is re-imported and
    the module-level Counter/Histogram/Gauge calls run again. prometheus_client
    raises ValueError('Duplicated timeseries') in that case. We catch it and
    return the already-registered collector so the rest of the app is unaffected.
    """
    if not _PROMETHEUS_AVAILABLE:
        return metric_cls()
    try:
        return metric_cls(name, doc, labelnames, **kwargs)
    except ValueError:
        # Already registered — retrieve the existing collector from the registry.
        return REGISTRY._names_to_collectors.get(name)


# ── HTTP ────────────────────────────────────────────────────────────────────
REQUEST_COUNT = _get_or_create(
    Counter,
    "outrena_http_requests_total",
    "Total HTTP requests served.",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = _get_or_create(
    Histogram,
    "outrena_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
ACTIVE_REQUESTS = _get_or_create(
    Gauge,
    "outrena_http_requests_active",
    "Number of HTTP requests currently in flight.",
)
RESPONSE_SIZE = _get_or_create(
    Histogram,
    "outrena_http_response_size_bytes",
    "HTTP response body size in bytes.",
    ["method", "endpoint"],
    buckets=(100, 1_000, 10_000, 100_000, 1_000_000),
)

# ── LLM ─────────────────────────────────────────────────────────────────────
LLM_CALLS = _get_or_create(
    Counter,
    "outrena_llm_calls_total",
    "Total LLM API calls (post-success).",
    ["provider", "model", "tenant"],
)
LLM_TOKENS = _get_or_create(
    Counter,
    "outrena_llm_tokens_total",
    "LLM tokens used (input + output).",
    ["provider", "model", "type", "tenant"],
)
LLM_COST_CENTS = _get_or_create(
    Counter,
    "outrena_llm_cost_cents_total",
    "LLM cost in integer cents (per provider × tenant).",
    ["provider", "tenant"],
)
LLM_LATENCY = _get_or_create(
    Histogram,
    "outrena_llm_duration_seconds",
    "LLM call latency (HTTP round-trip) in seconds.",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)
LLM_ERRORS = _get_or_create(
    Counter,
    "outrena_llm_errors_total",
    "Total LLM API call failures (post-retry).",
    ["provider", "model", "tenant", "error_type"],
)

# ── Email ───────────────────────────────────────────────────────────────────
EMAILS_SENT = _get_or_create(
    Counter,
    "outrena_emails_sent_total",
    "Emails sent (campaign + one-off).",
    ["tenant", "user_id"],
)
EMAIL_BOUNCES = _get_or_create(
    Counter,
    "outrena_email_bounces_total",
    "Email bounces per tenant.",
    ["tenant"],
)
EMAIL_COMPLAINTS = _get_or_create(
    Counter,
    "outrena_email_complaints_total",
    "Email complaints (unsubscribe / spam report) per tenant.",
    ["tenant"],
)

# ── Business gauges (updated by the relevant services) ─────────────────────
CAMPAIGNS_ACTIVE = _get_or_create(
    Gauge,
    "outrena_campaigns_active",
    "Currently-active campaigns per tenant.",
    ["tenant"],
)
PROSPECTS_TOTAL = _get_or_create(
    Gauge,
    "outrena_prospects_total",
    "Total prospects per tenant.",
    ["tenant"],
)

# ── Build / version info ────────────────────────────────────────────────────
BUILD_INFO = _get_or_create(
    Info,
    "outrena_build",
    "Build / version info — set once at process start.",
)
if BUILD_INFO is not None:
    try:
        BUILD_INFO.info(
            {
                "version": os.environ.get("OUTRENA_VERSION", "dev"),
                "environment": os.environ.get("ENVIRONMENT", "development"),
                "service": "outrena-backend",
            }
        )
    except Exception:
        pass  # already set in a sibling process


__all__ = [
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "ACTIVE_REQUESTS",
    "RESPONSE_SIZE",
    "LLM_CALLS",
    "LLM_TOKENS",
    "LLM_COST_CENTS",
    "LLM_LATENCY",
    "LLM_ERRORS",
    "EMAILS_SENT",
    "EMAIL_BOUNCES",
    "EMAIL_COMPLAINTS",
    "CAMPAIGNS_ACTIVE",
    "PROSPECTS_TOTAL",
    "BUILD_INFO",
]