"""
param_defs.py — 31 seeded system parameters (per migration doc §3.5 + §10 Phase 2).

Transcribed from the TS ``src/lib/params.ts`` constants. Each ParamDef
becomes a row in the tenant's ``SystemParameter`` table at provisioning
(see ``app.services.param_service.ParamService.seed_params``).

Categories (31 total, exceeds the 30+ minimum):
  - email (8)        — send limits, QA threshold, cadence days, footer flag, ...
  - scheduler (6)    — tick_seconds, partial_cap, business hours, max_instances
  - llm (5)          — default provider/model, timeout, max_tokens, temperature
  - mailbridge (4)   — timeout, retry count/delay, HMAC enforcement
  - prospecting (4)  — cache TTL, max results, validation thresholds
  - analytics (4)    — refresh interval, retention, digest day + hour

The ``default_value`` is always a string (the SystemParameter.value column is
TEXT). Numeric/bool/JSON values are string-encoded; the service layer
provides typed accessors (get_param_int, get_param_bool, get_param_json).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParamDef(BaseModel):
    """Static definition of one seeded system parameter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    category: str
    description: str
    default_value: str = Field(min_length=1)
    label: str | None = None  # defaults to title-cased key segment
    impact: str = "Medium"  # Low | Medium | High (admin UI hint)
    valueType: str = "number"  # number | boolean | string | json
    minValue: str | None = None
    maxValue: str | None = None
    unit: str | None = None
    isAdvanced: bool = False

    def resolved_label(self) -> str:
        if self.label:
            return self.label
        tail = self.key.split(".")[-1]
        return " ".join(p.capitalize() for p in tail.split("_"))


# ── Email (8) ───────────────────────────────────────────────────────────────

_EMAIL_PARAMS: list[ParamDef] = [
    ParamDef(
        key="email.daily_send_limit_per_prospect",
        category="email",
        description="Max emails a single prospect can receive per day.",
        default_value="1",
        valueType="number",
        minValue="1",
        maxValue="3",
        unit="emails/day",
        impact="High",
    ),
    ParamDef(
        key="email.daily_send_limit_per_tenant",
        category="email",
        description="Max emails the entire tenant can send per day (deliverability guard).",
        default_value="500",
        valueType="number",
        minValue="10",
        maxValue="10000",
        unit="emails/day",
        impact="High",
    ),
    ParamDef(
        key="email.qa_score_threshold",
        category="email",
        description="Minimum QA score (0-100) for an email to auto-advance to Scheduled.",
        default_value="70",
        valueType="number",
        minValue="0",
        maxValue="100",
        unit="points",
        impact="Medium",
    ),
    ParamDef(
        key="email.personalization_confidence_threshold",
        category="email",
        description="Minimum personalization confidence (0-1) for auto-send without review.",
        default_value="0.6",
        valueType="number",
        minValue="0",
        maxValue="1",
        impact="Medium",
        isAdvanced=True,
    ),
    ParamDef(
        key="email.default_send_hour_local",
        category="email",
        description="Default hour (0-23, prospect's local time) to send scheduled emails.",
        default_value="10",
        valueType="number",
        minValue="0",
        maxValue="23",
        unit="hour",
        impact="Medium",
    ),
    ParamDef(
        key="email.max_touches",
        category="email",
        description="Maximum touches in a cadence before the breakup email.",
        default_value="7",
        valueType="number",
        minValue="1",
        maxValue="12",
        unit="touches",
        impact="Medium",
    ),
    ParamDef(
        key="email.cadence_days",
        category="email",
        description="JSON array of day offsets for the default 7-touch cadence.",
        default_value="[1,4,9,16,25,35,49]",
        valueType="json",
        unit="days",
        impact="Medium",
        isAdvanced=True,
    ),
    ParamDef(
        key="email.compliance_footer_required",
        category="email",
        description="Require CAN-SPAM unsubscribe + physical address footer on every email.",
        default_value="true",
        valueType="boolean",
        impact="High",
    ),
]


# ── Scheduler (6) ───────────────────────────────────────────────────────────

_SCHEDULER_PARAMS: list[ParamDef] = [
    ParamDef(
        key="scheduler.tick_seconds",
        category="scheduler",
        description="Interval (seconds) between scheduler ticks.",
        default_value="300",
        valueType="number",
        minValue="60",
        maxValue="3600",
        unit="seconds",
        impact="High",
    ),
    ParamDef(
        key="scheduler.partial_cap",
        category="scheduler",
        description="Max PARTIAL-tier prospects processed per tick (anti-starvation).",
        default_value="5",
        valueType="number",
        minValue="1",
        maxValue="100",
        unit="prospects/tick",
        impact="Medium",
        isAdvanced=True,
    ),
    ParamDef(
        key="scheduler.business_hours_start",
        category="scheduler",
        description="Start of business hours (local time, hour 0-23) for sending.",
        default_value="9",
        valueType="number",
        minValue="0",
        maxValue="23",
        unit="hour",
        impact="Medium",
    ),
    ParamDef(
        key="scheduler.business_hours_end",
        category="scheduler",
        description="End of business hours (local time, hour 0-23) for sending.",
        default_value="18",
        valueType="number",
        minValue="0",
        maxValue="23",
        unit="hour",
        impact="Medium",
    ),
    ParamDef(
        key="scheduler.business_hours_timezone_default",
        category="scheduler",
        description="Default timezone (IANA name) for prospects missing a timezone.",
        default_value="America/New_York",
        valueType="string",
        impact="Medium",
        isAdvanced=True,
    ),
    ParamDef(
        key="scheduler.max_instances",
        category="scheduler",
        description="Max concurrent instances of the same scheduled job (1 = serialized).",
        default_value="1",
        valueType="number",
        minValue="1",
        maxValue="10",
        unit="instances",
        impact="High",
        isAdvanced=True,
    ),
]


# ── LLM (5) ─────────────────────────────────────────────────────────────────

_LLM_PARAMS: list[ParamDef] = [
    ParamDef(
        key="llm.default_provider",
        category="llm",
        description="Default LLM provider key used when a tenant has no LlmConfig rows.",
        default_value="zai",
        valueType="string",
        impact="High",
    ),
    ParamDef(
        key="llm.default_model",
        category="llm",
        description="Default model ID for the default provider.",
        default_value="glm-4-flash",
        valueType="string",
        impact="High",
    ),
    ParamDef(
        key="llm.timeout_seconds",
        category="llm",
        description="Per-call HTTP timeout for LLM gateway requests.",
        default_value="60",
        valueType="number",
        minValue="5",
        maxValue="300",
        unit="seconds",
        impact="Medium",
    ),
    ParamDef(
        key="llm.max_tokens_default",
        category="llm",
        description="Default max_tokens for LLM completions when not specified per-call.",
        default_value="1024",
        valueType="number",
        minValue="64",
        maxValue="32768",
        unit="tokens",
        impact="Low",
    ),
    ParamDef(
        key="llm.temperature_default",
        category="llm",
        description="Default temperature for LLM completions when not specified per-call.",
        default_value="0.7",
        valueType="number",
        minValue="0",
        maxValue="2",
        impact="Low",
    ),
]


# ── MailBridge (4) ──────────────────────────────────────────────────────────

_MAILBRIDGE_PARAMS: list[ParamDef] = [
    ParamDef(
        key="mailbridge.timeout_seconds",
        category="mailbridge",
        description="HTTP timeout for MailBridge send calls.",
        default_value="30",
        valueType="number",
        minValue="5",
        maxValue="120",
        unit="seconds",
        impact="Medium",
    ),
    ParamDef(
        key="mailbridge.retry_count",
        category="mailbridge",
        description="Number of retries on transient MailBridge failures.",
        default_value="3",
        valueType="number",
        minValue="0",
        maxValue="10",
        unit="retries",
        impact="Medium",
    ),
    ParamDef(
        key="mailbridge.retry_delay_seconds",
        category="mailbridge",
        description="Base delay (seconds) between MailBridge retries (exponential backoff).",
        default_value="2",
        valueType="number",
        minValue="1",
        maxValue="60",
        unit="seconds",
        impact="Low",
        isAdvanced=True,
    ),
    ParamDef(
        key="mailbridge.webhook_hmac_secret_required",
        category="mailbridge",
        description="Reject MailBridge webhooks missing a valid HMAC signature.",
        default_value="true",
        valueType="boolean",
        impact="High",
    ),
]


# ── Prospecting (4) ─────────────────────────────────────────────────────────

_PROSPECTING_PARAMS: list[ParamDef] = [
    ParamDef(
        key="prospecting.cache_ttl_seconds",
        category="prospecting",
        description="TTL for cached prospecting search results.",
        default_value="3600",
        valueType="number",
        minValue="60",
        maxValue="86400",
        unit="seconds",
        impact="Low",
        isAdvanced=True,
    ),
    ParamDef(
        key="prospecting.max_results_per_source",
        category="prospecting",
        description="Max results fetched per prospecting source per query.",
        default_value="100",
        valueType="number",
        minValue="10",
        maxValue="1000",
        unit="results",
        impact="Medium",
    ),
    ParamDef(
        key="prospecting.email_validation_confidence_threshold",
        category="prospecting",
        description="Minimum confidence (0-1) for an email to be marked validated.",
        default_value="0.85",
        valueType="number",
        minValue="0",
        maxValue="1",
        impact="High",
    ),
    ParamDef(
        key="prospecting.icp_fit_score_threshold",
        category="prospecting",
        description="Minimum ICP-fit score (0-100) for a prospect to enter a campaign.",
        default_value="40",
        valueType="number",
        minValue="0",
        maxValue="100",
        unit="points",
        impact="High",
    ),
]


# ── Analytics (4) ───────────────────────────────────────────────────────────

_ANALYTICS_PARAMS: list[ParamDef] = [
    ParamDef(
        key="analytics.refresh_interval_seconds",
        category="analytics",
        description="Interval (seconds) between analytics dashboard refreshes.",
        default_value="60",
        valueType="number",
        minValue="10",
        maxValue="3600",
        unit="seconds",
        impact="Low",
    ),
    ParamDef(
        key="analytics.campaign_metric_rollup_retention_days",
        category="analytics",
        description="Days to retain per-campaign metric rollups before aggregation.",
        default_value="90",
        valueType="number",
        minValue="7",
        maxValue="3650",
        unit="days",
        impact="Medium",
        isAdvanced=True,
    ),
    ParamDef(
        key="analytics.weekly_digest_day_of_week",
        category="analytics",
        description="Day of week (0=Sunday … 6=Saturday) the weekly digest is generated.",
        default_value="1",
        valueType="number",
        minValue="0",
        maxValue="6",
        unit="day-of-week",
        impact="Medium",
    ),
    ParamDef(
        key="analytics.weekly_digest_hour_utc",
        category="analytics",
        description="Hour (UTC, 0-23) the weekly digest is generated.",
        default_value="14",
        valueType="number",
        minValue="0",
        maxValue="23",
        unit="hour",
        impact="Low",
    ),
]


# ── Aggregate ───────────────────────────────────────────────────────────────

PARAM_DEFS: list[ParamDef] = (
    _EMAIL_PARAMS
    + _SCHEDULER_PARAMS
    + _LLM_PARAMS
    + _MAILBRIDGE_PARAMS
    + _PROSPECTING_PARAMS
    + _ANALYTICS_PARAMS
)


def _post_check() -> None:
    """Sanity-check the param list at import time (cheap, dev-only)."""
    keys = [p.key for p in PARAM_DEFS]
    if len(keys) != len(set(keys)):
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        raise RuntimeError(f"param_defs has duplicate keys: {dupes}")
    minimum = 30
    if len(PARAM_DEFS) < minimum:
        raise RuntimeError(
            f"param_defs expected >= {minimum} params, got {len(PARAM_DEFS)}"
        )


_post_check()


def to_param_kwargs(defn: ParamDef) -> dict[str, Any]:
    """
    Convert a ParamDef into the kwargs dict used to construct a
    SystemParameter row (matches the model field names exactly).
    """
    return {
        "key": defn.key,
        "category": defn.category,
        "label": defn.resolved_label(),
        "description": defn.description,
        "impact": defn.impact,
        "valueType": defn.valueType,
        "value": defn.default_value,
        "defaultValue": defn.default_value,
        "minValue": defn.minValue,
        "maxValue": defn.maxValue,
        "unit": defn.unit,
        "isAdvanced": defn.isAdvanced,
    }


__all__ = ["ParamDef", "PARAM_DEFS", "to_param_kwargs"]
