# # """
# # param_defs.py — 31 seeded system parameters (per migration doc §3.5 + §10 Phase 2).

# # Transcribed from the TS ``src/lib/params.ts`` constants. Each ParamDef
# # becomes a row in the tenant's ``SystemParameter`` table at provisioning
# # (see ``app.services.param_service.ParamService.seed_params``).

# # Categories (31 total, exceeds the 30+ minimum):
# #   - email (8)        — send limits, QA threshold, cadence days, footer flag, ...
# #   - scheduler (6)    — tick_seconds, partial_cap, business hours, max_instances
# #   - llm (5)          — default provider/model, timeout, max_tokens, temperature
# #   - mailbridge (4)   — timeout, retry count/delay, HMAC enforcement
# #   - prospecting (4)  — cache TTL, max results, validation thresholds
# #   - analytics (4)    — refresh interval, retention, digest day + hour

# # The ``default_value`` is always a string (the SystemParameter.value column is
# # TEXT). Numeric/bool/JSON values are string-encoded; the service layer
# # provides typed accessors (get_param_int, get_param_bool, get_param_json).
# # """
# # from __future__ import annotations

# # from typing import Any

# # from pydantic import BaseModel, ConfigDict, Field


# # class ParamDef(BaseModel):
# #     """Static definition of one seeded system parameter."""

# #     model_config = ConfigDict(frozen=True, extra="forbid")

# #     key: str
# #     category: str
# #     description: str
# #     default_value: str = Field(min_length=1)
# #     label: str | None = None  # defaults to title-cased key segment
# #     impact: str = "Medium"  # Low | Medium | High (admin UI hint)
# #     valueType: str = "number"  # number | boolean | string | json
# #     minValue: str | None = None
# #     maxValue: str | None = None
# #     unit: str | None = None
# #     isAdvanced: bool = False

# #     def resolved_label(self) -> str:
# #         if self.label:
# #             return self.label
# #         tail = self.key.split(".")[-1]
# #         return " ".join(p.capitalize() for p in tail.split("_"))


# # # ── Email (8) ───────────────────────────────────────────────────────────────

# # _EMAIL_PARAMS: list[ParamDef] = [
# #     ParamDef(
# #         key="email.daily_send_limit_per_prospect",
# #         category="email",
# #         description="Max emails a single prospect can receive per day.",
# #         default_value="1",
# #         valueType="number",
# #         minValue="1",
# #         maxValue="3",
# #         unit="emails/day",
# #         impact="High",
# #     ),
# #     ParamDef(
# #         key="email.daily_send_limit_per_tenant",
# #         category="email",
# #         description="Max emails the entire tenant can send per day (deliverability guard).",
# #         default_value="500",
# #         valueType="number",
# #         minValue="10",
# #         maxValue="10000",
# #         unit="emails/day",
# #         impact="High",
# #     ),
# #     ParamDef(
# #         key="email.qa_score_threshold",
# #         category="email",
# #         description="Minimum QA score (0-100) for an email to auto-advance to Scheduled.",
# #         default_value="70",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="100",
# #         unit="points",
# #         impact="Medium",
# #     ),
# #     ParamDef(
# #         key="email.personalization_confidence_threshold",
# #         category="email",
# #         description="Minimum personalization confidence (0-1) for auto-send without review.",
# #         default_value="0.6",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="1",
# #         impact="Medium",
# #         isAdvanced=True,
# #     ),
# #     ParamDef(
# #         key="email.default_send_hour_local",
# #         category="email",
# #         description="Default hour (0-23, prospect's local time) to send scheduled emails.",
# #         default_value="10",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="23",
# #         unit="hour",
# #         impact="Medium",
# #     ),
# #     ParamDef(
# #         key="email.max_touches",
# #         category="email",
# #         description="Maximum touches in a cadence before the breakup email.",
# #         default_value="7",
# #         valueType="number",
# #         minValue="1",
# #         maxValue="12",
# #         unit="touches",
# #         impact="Medium",
# #     ),
# #     ParamDef(
# #         key="email.cadence_days",
# #         category="email",
# #         description="JSON array of day offsets for the default 7-touch cadence.",
# #         default_value="[1,4,9,16,25,35,49]",
# #         valueType="json",
# #         unit="days",
# #         impact="Medium",
# #         isAdvanced=True,
# #     ),
# #     ParamDef(
# #         key="email.compliance_footer_required",
# #         category="email",
# #         description="Require CAN-SPAM unsubscribe + physical address footer on every email.",
# #         default_value="true",
# #         valueType="boolean",
# #         impact="High",
# #     ),
# # ]


# # # ── Scheduler (6) ───────────────────────────────────────────────────────────

# # _SCHEDULER_PARAMS: list[ParamDef] = [
# #     ParamDef(
# #         key="scheduler.tick_seconds",
# #         category="scheduler",
# #         description="Interval (seconds) between scheduler ticks.",
# #         default_value="300",
# #         valueType="number",
# #         minValue="60",
# #         maxValue="3600",
# #         unit="seconds",
# #         impact="High",
# #     ),
# #     ParamDef(
# #         key="scheduler.partial_cap",
# #         category="scheduler",
# #         description="Max PARTIAL-tier prospects processed per tick (anti-starvation).",
# #         default_value="5",
# #         valueType="number",
# #         minValue="1",
# #         maxValue="100",
# #         unit="prospects/tick",
# #         impact="Medium",
# #         isAdvanced=True,
# #     ),
# #     ParamDef(
# #         key="scheduler.business_hours_start",
# #         category="scheduler",
# #         description="Start of business hours (local time, hour 0-23) for sending.",
# #         default_value="9",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="23",
# #         unit="hour",
# #         impact="Medium",
# #     ),
# #     ParamDef(
# #         key="scheduler.business_hours_end",
# #         category="scheduler",
# #         description="End of business hours (local time, hour 0-23) for sending.",
# #         default_value="18",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="23",
# #         unit="hour",
# #         impact="Medium",
# #     ),
# #     ParamDef(
# #         key="scheduler.business_hours_timezone_default",
# #         category="scheduler",
# #         description="Default timezone (IANA name) for prospects missing a timezone.",
# #         default_value="America/New_York",
# #         valueType="string",
# #         impact="Medium",
# #         isAdvanced=True,
# #     ),
# #     ParamDef(
# #         key="scheduler.max_instances",
# #         category="scheduler",
# #         description="Max concurrent instances of the same scheduled job (1 = serialized).",
# #         default_value="1",
# #         valueType="number",
# #         minValue="1",
# #         maxValue="10",
# #         unit="instances",
# #         impact="High",
# #         isAdvanced=True,
# #     ),
# # ]


# # # ── LLM (5) ─────────────────────────────────────────────────────────────────

# # _LLM_PARAMS: list[ParamDef] = [
# #     ParamDef(
# #         key="llm.default_provider",
# #         category="llm",
# #         description="Default LLM provider key used when a tenant has no LlmConfig rows.",
# #         default_value="zai",
# #         valueType="string",
# #         impact="High",
# #     ),
# #     ParamDef(
# #         key="llm.default_model",
# #         category="llm",
# #         description="Default model ID for the default provider.",
# #         default_value="glm-4-flash",
# #         valueType="string",
# #         impact="High",
# #     ),
# #     ParamDef(
# #         key="llm.timeout_seconds",
# #         category="llm",
# #         description="Per-call HTTP timeout for LLM gateway requests.",
# #         default_value="60",
# #         valueType="number",
# #         minValue="5",
# #         maxValue="300",
# #         unit="seconds",
# #         impact="Medium",
# #     ),
# #     ParamDef(
# #         key="llm.max_tokens_default",
# #         category="llm",
# #         description="Default max_tokens for LLM completions when not specified per-call.",
# #         default_value="1024",
# #         valueType="number",
# #         minValue="64",
# #         maxValue="32768",
# #         unit="tokens",
# #         impact="Low",
# #     ),
# #     ParamDef(
# #         key="llm.temperature_default",
# #         category="llm",
# #         description="Default temperature for LLM completions when not specified per-call.",
# #         default_value="0.7",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="2",
# #         impact="Low",
# #     ),
# # ]


# # # ── MailBridge (4) ──────────────────────────────────────────────────────────

# # _MAILBRIDGE_PARAMS: list[ParamDef] = [
# #     ParamDef(
# #         key="mailbridge.timeout_seconds",
# #         category="mailbridge",
# #         description="HTTP timeout for MailBridge send calls.",
# #         default_value="30",
# #         valueType="number",
# #         minValue="5",
# #         maxValue="120",
# #         unit="seconds",
# #         impact="Medium",
# #     ),
# #     ParamDef(
# #         key="mailbridge.retry_count",
# #         category="mailbridge",
# #         description="Number of retries on transient MailBridge failures.",
# #         default_value="3",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="10",
# #         unit="retries",
# #         impact="Medium",
# #     ),
# #     ParamDef(
# #         key="mailbridge.retry_delay_seconds",
# #         category="mailbridge",
# #         description="Base delay (seconds) between MailBridge retries (exponential backoff).",
# #         default_value="2",
# #         valueType="number",
# #         minValue="1",
# #         maxValue="60",
# #         unit="seconds",
# #         impact="Low",
# #         isAdvanced=True,
# #     ),
# #     ParamDef(
# #         key="mailbridge.webhook_hmac_secret_required",
# #         category="mailbridge",
# #         description="Reject MailBridge webhooks missing a valid HMAC signature.",
# #         default_value="true",
# #         valueType="boolean",
# #         impact="High",
# #     ),
# # ]


# # # ── Prospecting (4) ─────────────────────────────────────────────────────────

# # _PROSPECTING_PARAMS: list[ParamDef] = [
# #     ParamDef(
# #         key="prospecting.cache_ttl_seconds",
# #         category="prospecting",
# #         description="TTL for cached prospecting search results.",
# #         default_value="3600",
# #         valueType="number",
# #         minValue="60",
# #         maxValue="86400",
# #         unit="seconds",
# #         impact="Low",
# #         isAdvanced=True,
# #     ),
# #     ParamDef(
# #         key="prospecting.max_results_per_source",
# #         category="prospecting",
# #         description="Max results fetched per prospecting source per query.",
# #         default_value="100",
# #         valueType="number",
# #         minValue="10",
# #         maxValue="1000",
# #         unit="results",
# #         impact="Medium",
# #     ),
# #     ParamDef(
# #         key="prospecting.email_validation_confidence_threshold",
# #         category="prospecting",
# #         description="Minimum confidence (0-1) for an email to be marked validated.",
# #         default_value="0.85",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="1",
# #         impact="High",
# #     ),
# #     ParamDef(
# #         key="prospecting.icp_fit_score_threshold",
# #         category="prospecting",
# #         description="Minimum ICP-fit score (0-100) for a prospect to enter a campaign.",
# #         default_value="40",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="100",
# #         unit="points",
# #         impact="High",
# #     ),
# # ]


# # # ── Analytics (4) ───────────────────────────────────────────────────────────

# # _ANALYTICS_PARAMS: list[ParamDef] = [
# #     ParamDef(
# #         key="analytics.refresh_interval_seconds",
# #         category="analytics",
# #         description="Interval (seconds) between analytics dashboard refreshes.",
# #         default_value="60",
# #         valueType="number",
# #         minValue="10",
# #         maxValue="3600",
# #         unit="seconds",
# #         impact="Low",
# #     ),
# #     ParamDef(
# #         key="analytics.campaign_metric_rollup_retention_days",
# #         category="analytics",
# #         description="Days to retain per-campaign metric rollups before aggregation.",
# #         default_value="90",
# #         valueType="number",
# #         minValue="7",
# #         maxValue="3650",
# #         unit="days",
# #         impact="Medium",
# #         isAdvanced=True,
# #     ),
# #     ParamDef(
# #         key="analytics.weekly_digest_day_of_week",
# #         category="analytics",
# #         description="Day of week (0=Sunday … 6=Saturday) the weekly digest is generated.",
# #         default_value="1",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="6",
# #         unit="day-of-week",
# #         impact="Medium",
# #     ),
# #     ParamDef(
# #         key="analytics.weekly_digest_hour_utc",
# #         category="analytics",
# #         description="Hour (UTC, 0-23) the weekly digest is generated.",
# #         default_value="14",
# #         valueType="number",
# #         minValue="0",
# #         maxValue="23",
# #         unit="hour",
# #         impact="Low",
# #     ),
# # ]


# # # ── Aggregate ───────────────────────────────────────────────────────────────

# # PARAM_DEFS: list[ParamDef] = (
# #     _EMAIL_PARAMS
# #     + _SCHEDULER_PARAMS
# #     + _LLM_PARAMS
# #     + _MAILBRIDGE_PARAMS
# #     + _PROSPECTING_PARAMS
# #     + _ANALYTICS_PARAMS
# # )


# # def _post_check() -> None:
# #     """Sanity-check the param list at import time (cheap, dev-only)."""
# #     keys = [p.key for p in PARAM_DEFS]
# #     if len(keys) != len(set(keys)):
# #         dupes = sorted({k for k in keys if keys.count(k) > 1})
# #         raise RuntimeError(f"param_defs has duplicate keys: {dupes}")
# #     minimum = 30
# #     if len(PARAM_DEFS) < minimum:
# #         raise RuntimeError(
# #             f"param_defs expected >= {minimum} params, got {len(PARAM_DEFS)}"
# #         )


# # _post_check()


# # def to_param_kwargs(defn: ParamDef) -> dict[str, Any]:
# #     """
# #     Convert a ParamDef into the kwargs dict used to construct a
# #     SystemParameter row (matches the model field names exactly).
# #     """
# #     return {
# #         "key": defn.key,
# #         "category": defn.category,
# #         "label": defn.resolved_label(),
# #         "description": defn.description,
# #         "impact": defn.impact,
# #         "valueType": defn.valueType,
# #         "value": defn.default_value,
# #         "defaultValue": defn.default_value,
# #         "minValue": defn.minValue,
# #         "maxValue": defn.maxValue,
# #         "unit": defn.unit,
# #         "isAdvanced": defn.isAdvanced,
# #     }


# # __all__ = ["ParamDef", "PARAM_DEFS", "to_param_kwargs"]

# """
# param_defs.py — 61 seeded system parameters (per migration doc §3.5 + §10 Phase 2).

# Transcribed from the TS ``src/lib/params.ts`` constants, plus the 30
# health-diagnostics / A-B-testing / scheduling params transcribed from the
# Next.js reference's ``src/modules/system-params/lib/system-param-defs.ts``
# (added separately — no key overlap with the operational params below).
# Each ParamDef becomes a row in the tenant's ``SystemParameter`` table at
# provisioning (see ``app.services.param_service.ParamService.seed_params``).

# Categories — operational (31 total):
#   - email (8)        — send limits, QA threshold, cadence days, footer flag, ...
#   - scheduler (6)    — tick_seconds, partial_cap, business hours, max_instances
#   - llm (5)          — default provider/model, timeout, max_tokens, temperature
#   - mailbridge (4)   — timeout, retry count/delay, HMAC enforcement
#   - prospecting (4)  — cache TTL, max results, validation thresholds
#   - analytics (4)    — refresh interval, retention, digest day + hour

# Categories — health-diagnostics / statistics (30 total, from the Next.js
# reference; these feed Campaign Health Diagnostics, A/B significance testing,
# copy-angle decay detection, enrichment tier classification, and the
# pre-flight activation gate):
#   - Analytics Benchmarks (4)      — open/reply/bounce/positive-reply health thresholds
#   - Sample-Size Guards (4)        — min sends/leads before verdicts are trusted
#   - Copy Angle Decay (2)          — decay detection + critical-open thresholds
#   - Email Waterfall (3)           — enrichment-source confidence scores
#   - Enrichment Classification (2) — ENRICHED/PARTIAL tier + review thresholds
#   - A/B Testing (4)                — significance / high / marginal p-value thresholds
#   - Pre-Flight & Scheduling (9)    — warmup gate, send window, business hours
#   - Auto-Pilot & Replies (2)       — auto-send confidence + parse-failure fallback

# The ``default_value`` is always a string (the SystemParameter.value column is
# TEXT). Numeric/bool/JSON values are string-encoded; the service layer
# provides typed accessors (get_param_int, get_param_bool, get_param_json).
# """
# from __future__ import annotations

# from typing import Any

# from pydantic import BaseModel, ConfigDict, Field


# class ParamDef(BaseModel):
#     """Static definition of one seeded system parameter."""

#     model_config = ConfigDict(frozen=True, extra="forbid")

#     key: str
#     category: str
#     description: str
#     default_value: str = Field(min_length=1)
#     label: str | None = None  # defaults to title-cased key segment
#     impact: str = "Medium"  # Low | Medium | High (admin UI hint)
#     valueType: str = "number"  # number | boolean | string | json
#     minValue: str | None = None
#     maxValue: str | None = None
#     unit: str | None = None
#     isAdvanced: bool = False

#     def resolved_label(self) -> str:
#         if self.label:
#             return self.label
#         tail = self.key.split(".")[-1]
#         return " ".join(p.capitalize() for p in tail.split("_"))


# # ── Email (8) ───────────────────────────────────────────────────────────────

# _EMAIL_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="email.daily_send_limit_per_prospect",
#         category="email",
#         description="Max emails a single prospect can receive per day.",
#         default_value="1",
#         valueType="number",
#         minValue="1",
#         maxValue="3",
#         unit="emails/day",
#         impact="High",
#     ),
#     ParamDef(
#         key="email.daily_send_limit_per_tenant",
#         category="email",
#         description="Max emails the entire tenant can send per day (deliverability guard).",
#         default_value="500",
#         valueType="number",
#         minValue="10",
#         maxValue="10000",
#         unit="emails/day",
#         impact="High",
#     ),
#     ParamDef(
#         key="email.qa_score_threshold",
#         category="email",
#         description="Minimum QA score (0-100) for an email to auto-advance to Scheduled.",
#         default_value="70",
#         valueType="number",
#         minValue="0",
#         maxValue="100",
#         unit="points",
#         impact="Medium",
#     ),
#     ParamDef(
#         key="email.personalization_confidence_threshold",
#         category="email",
#         description="Minimum personalization confidence (0-1) for auto-send without review.",
#         default_value="0.6",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         impact="Medium",
#         isAdvanced=True,
#     ),
#     ParamDef(
#         key="email.default_send_hour_local",
#         category="email",
#         description="Default hour (0-23, prospect's local time) to send scheduled emails.",
#         default_value="10",
#         valueType="number",
#         minValue="0",
#         maxValue="23",
#         unit="hour",
#         impact="Medium",
#     ),
#     ParamDef(
#         key="email.max_touches",
#         category="email",
#         description="Maximum touches in a cadence before the breakup email.",
#         default_value="7",
#         valueType="number",
#         minValue="1",
#         maxValue="12",
#         unit="touches",
#         impact="Medium",
#     ),
#     ParamDef(
#         key="email.cadence_days",
#         category="email",
#         description="JSON array of day offsets for the default 7-touch cadence.",
#         default_value="[1,4,9,16,25,35,49]",
#         valueType="json",
#         unit="days",
#         impact="Medium",
#         isAdvanced=True,
#     ),
#     ParamDef(
#         key="email.compliance_footer_required",
#         category="email",
#         description="Require CAN-SPAM unsubscribe + physical address footer on every email.",
#         default_value="true",
#         valueType="boolean",
#         impact="High",
#     ),
# ]


# # ── Scheduler (6) ───────────────────────────────────────────────────────────

# _SCHEDULER_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="scheduler.tick_seconds",
#         category="scheduler",
#         description="Interval (seconds) between scheduler ticks.",
#         default_value="300",
#         valueType="number",
#         minValue="60",
#         maxValue="3600",
#         unit="seconds",
#         impact="High",
#     ),
#     ParamDef(
#         key="scheduler.partial_cap",
#         category="scheduler",
#         description="Max PARTIAL-tier prospects processed per tick (anti-starvation).",
#         default_value="5",
#         valueType="number",
#         minValue="1",
#         maxValue="100",
#         unit="prospects/tick",
#         impact="Medium",
#         isAdvanced=True,
#     ),
#     ParamDef(
#         key="scheduler.business_hours_start",
#         category="scheduler",
#         description="Start of business hours (local time, hour 0-23) for sending.",
#         default_value="9",
#         valueType="number",
#         minValue="0",
#         maxValue="23",
#         unit="hour",
#         impact="Medium",
#     ),
#     ParamDef(
#         key="scheduler.business_hours_end",
#         category="scheduler",
#         description="End of business hours (local time, hour 0-23) for sending.",
#         default_value="18",
#         valueType="number",
#         minValue="0",
#         maxValue="23",
#         unit="hour",
#         impact="Medium",
#     ),
#     ParamDef(
#         key="scheduler.business_hours_timezone_default",
#         category="scheduler",
#         description="Default timezone (IANA name) for prospects missing a timezone.",
#         default_value="America/New_York",
#         valueType="string",
#         impact="Medium",
#         isAdvanced=True,
#     ),
#     ParamDef(
#         key="scheduler.max_instances",
#         category="scheduler",
#         description="Max concurrent instances of the same scheduled job (1 = serialized).",
#         default_value="1",
#         valueType="number",
#         minValue="1",
#         maxValue="10",
#         unit="instances",
#         impact="High",
#         isAdvanced=True,
#     ),
# ]


# # ── LLM (5) ─────────────────────────────────────────────────────────────────

# _LLM_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="llm.default_provider",
#         category="llm",
#         description="Default LLM provider key used when a tenant has no LlmConfig rows.",
#         default_value="zai",
#         valueType="string",
#         impact="High",
#     ),
#     ParamDef(
#         key="llm.default_model",
#         category="llm",
#         description="Default model ID for the default provider.",
#         default_value="glm-4-flash",
#         valueType="string",
#         impact="High",
#     ),
#     ParamDef(
#         key="llm.timeout_seconds",
#         category="llm",
#         description="Per-call HTTP timeout for LLM gateway requests.",
#         default_value="60",
#         valueType="number",
#         minValue="5",
#         maxValue="300",
#         unit="seconds",
#         impact="Medium",
#     ),
#     ParamDef(
#         key="llm.max_tokens_default",
#         category="llm",
#         description="Default max_tokens for LLM completions when not specified per-call.",
#         default_value="1024",
#         valueType="number",
#         minValue="64",
#         maxValue="32768",
#         unit="tokens",
#         impact="Low",
#     ),
#     ParamDef(
#         key="llm.temperature_default",
#         category="llm",
#         description="Default temperature for LLM completions when not specified per-call.",
#         default_value="0.7",
#         valueType="number",
#         minValue="0",
#         maxValue="2",
#         impact="Low",
#     ),
# ]


# # ── MailBridge (4) ──────────────────────────────────────────────────────────

# _MAILBRIDGE_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="mailbridge.timeout_seconds",
#         category="mailbridge",
#         description="HTTP timeout for MailBridge send calls.",
#         default_value="30",
#         valueType="number",
#         minValue="5",
#         maxValue="120",
#         unit="seconds",
#         impact="Medium",
#     ),
#     ParamDef(
#         key="mailbridge.retry_count",
#         category="mailbridge",
#         description="Number of retries on transient MailBridge failures.",
#         default_value="3",
#         valueType="number",
#         minValue="0",
#         maxValue="10",
#         unit="retries",
#         impact="Medium",
#     ),
#     ParamDef(
#         key="mailbridge.retry_delay_seconds",
#         category="mailbridge",
#         description="Base delay (seconds) between MailBridge retries (exponential backoff).",
#         default_value="2",
#         valueType="number",
#         minValue="1",
#         maxValue="60",
#         unit="seconds",
#         impact="Low",
#         isAdvanced=True,
#     ),
#     ParamDef(
#         key="mailbridge.webhook_hmac_secret_required",
#         category="mailbridge",
#         description="Reject MailBridge webhooks missing a valid HMAC signature.",
#         default_value="true",
#         valueType="boolean",
#         impact="High",
#     ),
# ]


# # ── Prospecting (4) ─────────────────────────────────────────────────────────

# _PROSPECTING_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="prospecting.cache_ttl_seconds",
#         category="prospecting",
#         description="TTL for cached prospecting search results.",
#         default_value="3600",
#         valueType="number",
#         minValue="60",
#         maxValue="86400",
#         unit="seconds",
#         impact="Low",
#         isAdvanced=True,
#     ),
#     ParamDef(
#         key="prospecting.max_results_per_source",
#         category="prospecting",
#         description="Max results fetched per prospecting source per query.",
#         default_value="100",
#         valueType="number",
#         minValue="10",
#         maxValue="1000",
#         unit="results",
#         impact="Medium",
#     ),
#     ParamDef(
#         key="prospecting.email_validation_confidence_threshold",
#         category="prospecting",
#         description="Minimum confidence (0-1) for an email to be marked validated.",
#         default_value="0.85",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         impact="High",
#     ),
#     ParamDef(
#         key="prospecting.icp_fit_score_threshold",
#         category="prospecting",
#         description="Minimum ICP-fit score (0-100) for a prospect to enter a campaign.",
#         default_value="40",
#         valueType="number",
#         minValue="0",
#         maxValue="100",
#         unit="points",
#         impact="High",
#     ),
# ]


# # ── Analytics (4) ───────────────────────────────────────────────────────────

# _ANALYTICS_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="analytics.refresh_interval_seconds",
#         category="analytics",
#         description="Interval (seconds) between analytics dashboard refreshes.",
#         default_value="60",
#         valueType="number",
#         minValue="10",
#         maxValue="3600",
#         unit="seconds",
#         impact="Low",
#     ),
#     ParamDef(
#         key="analytics.campaign_metric_rollup_retention_days",
#         category="analytics",
#         description="Days to retain per-campaign metric rollups before aggregation.",
#         default_value="90",
#         valueType="number",
#         minValue="7",
#         maxValue="3650",
#         unit="days",
#         impact="Medium",
#         isAdvanced=True,
#     ),
#     ParamDef(
#         key="analytics.weekly_digest_day_of_week",
#         category="analytics",
#         description="Day of week (0=Sunday … 6=Saturday) the weekly digest is generated.",
#         default_value="1",
#         valueType="number",
#         minValue="0",
#         maxValue="6",
#         unit="day-of-week",
#         impact="Medium",
#     ),
#     ParamDef(
#         key="analytics.weekly_digest_hour_utc",
#         category="analytics",
#         description="Hour (UTC, 0-23) the weekly digest is generated.",
#         default_value="14",
#         valueType="number",
#         minValue="0",
#         maxValue="23",
#         unit="hour",
#         impact="Low",
#     ),
# ]


# # ── Analytics Benchmarks (4) ─────────────────────────────────────────────────
# # Transcribed from the Next.js reference (src/modules/system-params/lib/
# # system-param-defs.ts) — health-diagnostics thresholds consumed by the
# # Campaign Health Diagnostics (Layer 1) decision tree. These are additive to
# # the operational params above; there is no key overlap.

# _ANALYTICS_BENCHMARKS_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="benchmark_openRate",
#         category="Analytics Benchmarks",
#         label="Healthy Open Rate",
#         description=(
#             'The open rate threshold above which a campaign is considered '
#             '"healthy". Used in Campaign Health Diagnostics (Layer 1) to '
#             "flag warn/critical engagement issues."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.45) means fewer campaigns will be "
#             'flagged as "warn engagement" — you will get fewer alerts but '
#             "may miss real deliverability issues. Raising it (e.g., to "
#             "0.60) means more campaigns will be flagged, which could "
#             "create alert fatigue if your industry typically has lower "
#             "open rates."
#         ),
#         default_value="0.55",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="% (0-1)",
#     ),
#     ParamDef(
#         key="benchmark_replyRate",
#         category="Analytics Benchmarks",
#         label="Healthy Reply Rate",
#         description=(
#             "The reply rate threshold above which a campaign is considered "
#             '"healthy". Used in the diagnostic decision tree: if open rate '
#             "is healthy but reply rate is below this, the problem is copy "
#             "or signal quality."
#         ),
#         impact=(
#             'Lowering this means fewer "copy_or_signal" verdicts — you '
#             "will be less alerted to copy problems. Raising it means you "
#             "will be pushed to improve copy more aggressively, which may "
#             "be premature if your lists are still small."
#         ),
#         default_value="0.06",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="% (0-1)",
#     ),
#     ParamDef(
#         key="benchmark_bounceRate",
#         category="Analytics Benchmarks",
#         label="Max Healthy Bounce Rate",
#         description=(
#             "The bounce rate threshold above which a campaign is flagged "
#             'as "critical deliverability". Used in health diagnostics and '
#             "the Auto-Optimization Rules Engine default rule."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.01) means campaigns will be paused "
#             "more aggressively on bounces — safer for domain reputation "
#             "but may pause campaigns prematurely on small samples. Raising "
#             "it (e.g., to 0.03) means more tolerance for bounces, which "
#             "risks domain burn if enrichment quality is poor."
#         ),
#         default_value="0.02",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="% (0-1)",
#     ),
#     ParamDef(
#         key="benchmark_positiveReplyRate",
#         category="Analytics Benchmarks",
#         label="Healthy Positive Reply Rate",
#         description=(
#             "The positive reply rate threshold. If reply rate is healthy "
#             "but positive reply rate is below this, the diagnostic flags "
#             '"offer_mismatch" — meaning you are getting replies but they '
#             "are not the right kind."
#         ),
#         impact=(
#             'Lowering this means fewer "offer_mismatch" verdicts — less '
#             "pressure to revisit your ICP/offer. Raising it means you "
#             "will be pushed to refine your targeting sooner, which is "
#             "good for pipeline quality but may be noisy early in a "
#             "campaign."
#         ),
#         default_value="0.025",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="% (0-1)",
#     ),
# ]


# # ── Sample-Size Guards (4) ───────────────────────────────────────────────────

# _SAMPLE_SIZE_GUARDS_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="sampleGuard_campaignSends",
#         category="Sample-Size Guards",
#         label="Min Sends Per Campaign",
#         description=(
#             "Minimum number of sends a campaign needs before its metrics "
#             'are considered statistically reliable. Below this, the '
#             'campaign is flagged "insufficient_data" and verdicts are '
#             "suppressed."
#         ),
#         impact=(
#             "Lowering this (e.g., to 30) means you will get verdicts "
#             "sooner on small campaigns, but they may be based on noise. "
#             "Raising it (e.g., to 100) means more conservative "
#             "conclusions — you will wait longer for actionable "
#             "diagnostics but they will be more reliable."
#         ),
#         default_value="50",
#         valueType="number",
#         minValue="10",
#         maxValue="500",
#         unit="sends",
#     ),
#     ParamDef(
#         key="sampleGuard_stepSends",
#         category="Sample-Size Guards",
#         label="Min Sends Per Sequence Step",
#         description=(
#             "Minimum sends per touchpoint (T1-T6) before step-level reply "
#             "rate is considered reliable. Steps below this are flagged "
#             '"low n" in the Sequence Step Performance chart.'
#         ),
#         impact=(
#             "Lowering this means step metrics will show sooner, but "
#             "small-sample steps may mislead you about which email drives "
#             "replies. Raising it means you will wait longer for "
#             "step-level insights but they will be more trustworthy."
#         ),
#         default_value="30",
#         valueType="number",
#         minValue="10",
#         maxValue="200",
#         unit="sends",
#     ),
#     ParamDef(
#         key="sampleGuard_intentLeads",
#         category="Sample-Size Guards",
#         label="Min Leads Per Intent Source",
#         description=(
#             "Minimum leads an intent source needs before its conversion "
#             'rate is shown without a "low n" flag in the Intent Source '
#             "Attribution table."
#         ),
#         impact=(
#             "Lowering this means smaller intent sources will show "
#             "conversion rates without a warning, which could lead to "
#             "reallocating budget based on noise. Raising it means only "
#             "well-sampled sources will be trusted, which is safer but may "
#             "hide niche high-converting sources."
#         ),
#         default_value="50",
#         valueType="number",
#         minValue="10",
#         maxValue="200",
#         unit="leads",
#     ),
#     ParamDef(
#         key="sampleGuard_angleSends",
#         category="Sample-Size Guards",
#         label="Min Sends Per Copy Angle",
#         description=(
#             "Minimum sends per copy angle before its reply rate is "
#             "considered reliable and decay detection is enabled."
#         ),
#         impact=(
#             "Lowering this means decay will be detected sooner on new "
#             "angles, but you may rotate angles prematurely based on small "
#             "samples. Raising it means more confidence in decay detection "
#             "but slower reaction to angle fatigue."
#         ),
#         default_value="30",
#         valueType="number",
#         minValue="10",
#         maxValue="200",
#         unit="sends",
#     ),
# ]


# # ── Copy Angle Decay (2) ─────────────────────────────────────────────────────

# _COPY_ANGLE_DECAY_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="decay_relativeDeclineThreshold",
#         category="Copy Angle Decay",
#         label="Decay Detection Threshold",
#         description=(
#             "The relative decline in reply rate (this month vs last "
#             'month) above which a copy angle is flagged as "Decaying". '
#             "For example, 0.25 means a 25%+ relative drop triggers the "
#             "flag."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.15) means angles will be flagged "
#             "as decaying sooner — you will rotate copy more frequently, "
#             "which prevents fatigue but may retire angles before they "
#             "have a chance to recover. Raising it (e.g., to 0.35) means "
#             "you will tolerate more decline before acting, which lets "
#             "winners run longer but risks missing the fatigue cliff."
#         ),
#         default_value="0.25",
#         valueType="number",
#         minValue="0.05",
#         maxValue="0.75",
#         unit="% (0-1)",
#     ),
#     ParamDef(
#         key="analytics_criticalOpenThreshold",
#         category="Copy Angle Decay",
#         label="Critical Open Rate Threshold",
#         description=(
#             "Below this open rate, a campaign is flagged as "
#             '"critical_engagement" (red alert) rather than just '
#             '"warn_engagement" (yellow). Critical means: check '
#             "deliverability immediately, possibly switch sending domains."
#         ),
#         impact=(
#             "Lowering this means fewer red alerts — you will tolerate "
#             "lower open rates before triggering urgent deliverability "
#             "checks. Raising it means more campaigns will be flagged as "
#             "critical, which is safer for domain reputation but may cause "
#             "alert fatigue."
#         ),
#         default_value="0.35",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="% (0-1)",
#     ),
# ]


# # ── Email Waterfall (3) ──────────────────────────────────────────────────────

# _EMAIL_WATERFALL_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="waterfall_confidencePlatformVerified",
#         category="Email Waterfall",
#         label="Platform-Verified Confidence",
#         description=(
#             "The confidence score assigned to an email when it comes from "
#             "a verified enrichment platform (Apollo, Clearbit, etc.). 1.0 "
#             "= highest possible confidence."
#         ),
#         impact=(
#             "This should almost always be 1.0. Lowering it would make "
#             "platform-verified emails appear less reliable than they are, "
#             "which could trigger unnecessary manual review. Raising it "
#             "above 1.0 is invalid."
#         ),
#         default_value="1.0",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="confidence",
#         isAdvanced=True,
#     ),
#     ParamDef(
#         key="waterfall_confidenceMxVerified",
#         category="Email Waterfall",
#         label="MX-Verified Pattern Confidence",
#         description=(
#             "The confidence score assigned to an email that was inferred "
#             "via pattern (first.last@) and verified via MX record lookup "
#             "(domain accepts mail) but not SMTP mailbox probe."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.5) means pattern-inferred emails "
#             "will be treated as lower confidence, which could push more "
#             "prospects into the PARTIAL enrichment tier and reduce send "
#             "volume. Raising it (e.g., to 0.8) means more trust in "
#             "pattern inference, which increases send volume but risks "
#             "higher bounce rates on mis-predicted patterns."
#         ),
#         default_value="0.7",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="confidence",
#     ),
#     ParamDef(
#         key="waterfall_confidenceCatchAll",
#         category="Email Waterfall",
#         label="Catch-All Domain Confidence",
#         description=(
#             "The confidence score assigned to an email on a catch-all "
#             "domain (a domain that accepts any address, so we cannot "
#             "verify the specific mailbox exists). These are the riskiest "
#             "inferred emails."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.2) means catch-all emails will be "
#             "treated as very low confidence, likely pushing those "
#             "prospects to UNENRICHABLE and suppressing sends. Raising it "
#             "(e.g., to 0.5) means more catch-all emails will be sent, "
#             "increasing volume but risking higher bounce rates."
#         ),
#         default_value="0.4",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="confidence",
#     ),
# ]


# # ── Enrichment Classification (2) ────────────────────────────────────────────

# _ENRICHMENT_CLASSIFICATION_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="enrichment_highConfidenceThreshold",
#         category="Enrichment Classification",
#         label="High-Confidence Email Threshold",
#         description=(
#             "Email confidence at or above this value is considered "
#             '"high confidence" for the ENRICHED tier classification. '
#             "Below this (or catch-all) drops the prospect to PARTIAL."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.5) means more prospects will be "
#             "classified as ENRICHED, increasing the pool of "
#             "fully-sendable leads. Raising it (e.g., to 0.8) means "
#             "stricter quality — fewer prospects will be ENRICHED, but "
#             "those that are will have higher deliverability confidence."
#         ),
#         default_value="0.7",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="confidence",
#     ),
#     ParamDef(
#         key="enrichment_personalizationReviewThreshold",
#         category="Enrichment Classification",
#         label="Manual Review Confidence Threshold",
#         description=(
#             "If the AI-generated personalization confidence for an email "
#             "opener is below this value, the touch is automatically "
#             "flagged for manual review. The AI writes an honest cold "
#             "intro instead of pretending to have a signal it does not "
#             "have."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.4) means fewer touches will be "
#             "flagged for review — more emails will go out with "
#             'potentially thin personalization, increasing volume but '
#             'risking "creepy" or generic openers. Raising it (e.g., to '
#             "0.7) means more touches will require manual review, "
#             "improving opener quality but slowing throughput."
#         ),
#         default_value="0.6",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="confidence",
#     ),
# ]


# # ── A/B Testing (4) ──────────────────────────────────────────────────────────

# _AB_TESTING_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="abtest_minSendsPerVariant",
#         category="A/B Testing",
#         label="Min Sends Per Variant",
#         description=(
#             "Minimum sends per variant before the significance engine "
#             'will compute a result. Below this, the test returns '
#             '"Insufficient data". This prevents false conclusions from '
#             "small samples."
#         ),
#         impact=(
#             "Lowering this (e.g., to 20) means you will get significance "
#             "verdicts sooner, but the z-test may declare a winner based "
#             "on noise. Raising it (e.g., to 50) means more reliable "
#             "results but slower time-to-insight. The statistical "
#             "standard is 30 for a reason — change with caution."
#         ),
#         default_value="30",
#         valueType="number",
#         minValue="10",
#         maxValue="100",
#         unit="sends",
#     ),
#     ParamDef(
#         key="abtest_significanceThreshold",
#         category="A/B Testing",
#         label="Significance Threshold (p-value)",
#         description=(
#             'The p-value below which a test result is declared '
#             '"statistically significant". The standard is 0.05 (95% '
#             "confidence). The z-test compares the p-value to this "
#             "threshold."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.01) means you require stronger "
#             "evidence before declaring a winner — fewer false positives "
#             "but you may need more data to reach a conclusion. Raising "
#             "it (e.g., to 0.10) means you will declare winners sooner but "
#             "with higher risk of false positives (picking the wrong "
#             "variant). The scientific standard is 0.05."
#         ),
#         default_value="0.05",
#         valueType="number",
#         minValue="0.01",
#         maxValue="0.20",
#         unit="p-value",
#     ),
#     ParamDef(
#         key="abtest_highSignificanceThreshold",
#         category="A/B Testing",
#         label="High Significance Threshold",
#         description=(
#             'The p-value below which a test result is declared "highly '
#             'significant" (99% confidence). This is the gold standard — '
#             "a winner at this level is almost certainly real."
#         ),
#         impact=(
#             "This should always be lower than the significance "
#             "threshold. Lowering it means requiring even stronger "
#             'evidence for the "highly significant" label. Raising it '
#             'means more tests will be labeled "highly significant", '
#             "which could overstate confidence in marginal results."
#         ),
#         default_value="0.01",
#         valueType="number",
#         minValue="0.001",
#         maxValue="0.05",
#         unit="p-value",
#         isAdvanced=True,
#     ),
#     ParamDef(
#         key="abtest_marginalSignificanceThreshold",
#         category="A/B Testing",
#         label="Marginal Significance Threshold",
#         description=(
#             'The p-value below which a test result is declared '
#             '"marginally significant" (90% confidence). This is a yellow '
#             "zone — worth watching but not yet conclusive."
#         ),
#         impact=(
#             "This should always be between the significance and high "
#             'thresholds. Raising it (e.g., to 0.15) means more tests will '
#             'be labeled "marginal", which could encourage premature '
#             "action. Lowering it means fewer marginal results, which is "
#             "more conservative."
#         ),
#         default_value="0.10",
#         valueType="number",
#         minValue="0.05",
#         maxValue="0.20",
#         unit="p-value",
#         isAdvanced=True,
#     ),
# ]


# # ── Pre-Flight & Scheduling (9) ──────────────────────────────────────────────

# _PREFLIGHT_SCHEDULING_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="preflight_minWarmingWeeks",
#         category="Pre-Flight & Scheduling",
#         label="Min Domain Warmup Weeks",
#         description=(
#             "The minimum number of weeks a sending domain must be warmed "
#             "before a campaign can be activated. The pre-flight gate "
#             "blocks activation below this threshold to prevent domain "
#             "reputation burn."
#         ),
#         impact=(
#             "Lowering this (e.g., to 1) means campaigns can launch sooner "
#             "on new domains, but significantly increases the risk of "
#             "domain reputation damage that takes 30-60 days to recover. "
#             "Raising it (e.g., to 3) means safer sends but slower "
#             "time-to-campaign on new domains. Industry best practice is "
#             "2 weeks minimum."
#         ),
#         default_value="2",
#         valueType="number",
#         minValue="1",
#         maxValue="8",
#         unit="weeks",
#     ),
#     ParamDef(
#         key="preflight_warmingWarnThreshold",
#         category="Pre-Flight & Scheduling",
#         label="Domain Warmup Warn Threshold",
#         description=(
#             "Above the min weeks but below this threshold, the "
#             'pre-flight gate shows a "warn" (yellow) status: domain is '
#             "recently warmed, monitor bounce rate closely. At or above "
#             "this threshold, the domain is considered fully warmed "
#             "(pass/green)."
#         ),
#         impact=(
#             "Lowering this (e.g., to 3) means domains are considered "
#             '"fully warmed" sooner, reducing warnings. Raising it (e.g., '
#             "to 6) means more cautious warmup — domains will show "
#             "warnings for longer, which is safer but may delay campaigns "
#             "unnecessarily."
#         ),
#         default_value="4",
#         valueType="number",
#         minValue="2",
#         maxValue="12",
#         unit="weeks",
#     ),
#     ParamDef(
#         key="preflight_sendWindowDays",
#         category="Pre-Flight & Scheduling",
#         label="Send Capacity Window (Days)",
#         description=(
#             "The number of days over which send capacity is calculated. "
#             "Capacity = dailySendLimit x this value. If the prospect "
#             "count exceeds capacity over this window, the pre-flight gate "
#             "blocks activation."
#         ),
#         impact=(
#             "Lowering this (e.g., to 3) means tighter capacity checks — "
#             "campaigns will need higher daily limits or fewer prospects "
#             "to pass. Raising it (e.g., to 7) means more prospects can be "
#             "queued, but if the campaign sends faster than expected, you "
#             "may hit daily limits mid-campaign."
#         ),
#         default_value="5",
#         valueType="number",
#         minValue="1",
#         maxValue="14",
#         unit="days",
#     ),
#     ParamDef(
#         key="scheduler_sendHour",
#         category="Pre-Flight & Scheduling",
#         label="Default Send Hour (24h)",
#         description=(
#             "The hour of the day (in the prospect's local timezone) when "
#             "scheduled emails are sent. 9 = 9:00 AM. The scheduler sends "
#             "only during business hours (9am-5pm Mon-Fri)."
#         ),
#         impact=(
#             "Changing this affects when emails land in prospects' "
#             "inboxes. 9 AM is optimal for most B2B audiences (email is "
#             "at the top of the inbox when they start their day). Earlier "
#             "(7-8) may catch early-risers but risks being buried by the "
#             "time they check. Later (10-11) means more competition with "
#             "other emails. The full business-hours window (9-17) is "
#             "enforced separately."
#         ),
#         default_value="9",
#         valueType="number",
#         minValue="0",
#         maxValue="23",
#         unit="hour (0-23)",
#     ),
#     ParamDef(
#         key="domain_defaultDailySendLimit",
#         category="Pre-Flight & Scheduling",
#         label="Default Daily Send Limit",
#         description=(
#             "The default daily send limit assigned to new sending "
#             "domains when they are first created. This is the number of "
#             "emails per day per domain. Used in capacity calculations and "
#             "the scheduler."
#         ),
#         impact=(
#             "Lowering this (e.g., to 5) means more conservative sending "
#             "— safer for new domains but slower campaign throughput. "
#             "Raising it (e.g., to 20) means faster campaigns but higher "
#             "risk of triggering spam filters on new domains. The safe "
#             "ramp-up is: week 1 = 10/day, week 2 = 20/day, week 3 = "
#             "50/day."
#         ),
#         default_value="10",
#         valueType="number",
#         minValue="1",
#         maxValue="100",
#         unit="emails/day",
#     ),
#     ParamDef(
#         key="preflight_emailValidationMinRate",
#         category="Pre-Flight & Scheduling",
#         label="Email Validation Warn Rate",
#         description=(
#             "The minimum fraction of campaign prospects whose emails "
#             "must be validated before the pre-flight gate will pass "
#             'without a warning. Below this, the pre-flight shows a "warn" '
#             '(yellow) status recommending you run "Validate All Emails" '
#             "first."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.6) means fewer campaigns will "
#             "trigger the validation warning, so you may send to more "
#             "unvalidated addresses — higher bounce risk. Raising it "
#             "(e.g., to 0.9) means stricter validation requirements, which "
#             "reduces bounces but may delay campaigns while you wait for "
#             "validation to complete."
#         ),
#         default_value="0.8",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="% (0-1)",
#     ),
#     ParamDef(
#         key="scheduler_partialVolumeRatio",
#         category="Pre-Flight & Scheduling",
#         label="PARTIAL-tier Send Volume Ratio",
#         description=(
#             "The fraction of PARTIAL-tier prospects (catch-all or "
#             "partial enrichment) that the scheduler will send to, to "
#             "protect deliverability. 0.5 = send to half of them. A "
#             "deterministic hash on the sequence ID decides which half — "
#             "the same lead is always included or excluded consistently "
#             "across ticks."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.25) means fewer PARTIAL-tier "
#             "emails go out, which is safer for domain reputation but "
#             "wastes partially-enriched leads. Raising it (e.g., to 0.75) "
#             "means more PARTIAL emails go out, increasing volume but "
#             "risking higher bounce rates on catch-all domains. 0.5 is "
#             "the industry-standard starting point."
#         ),
#         default_value="0.5",
#         valueType="number",
#         minValue="0",
#         maxValue="1",
#         unit="ratio (0-1)",
#     ),
#     ParamDef(
#         key="scheduler_businessHoursStart",
#         category="Pre-Flight & Scheduling",
#         label="Business Hours Start (24h)",
#         description=(
#             "The hour (in the prospect's local timezone) after which the "
#             "scheduler will send emails. Combined with the End hour, "
#             "this defines the daily send window. Emails due outside this "
#             "window are held until the next business-hours tick."
#         ),
#         impact=(
#             "Lowering this (e.g., to 7) means emails can go out earlier "
#             "in the prospect's morning — may catch early-risers but "
#             "risks being buried. Raising it (e.g., to 10) means emails "
#             "land later, with more competition. 9 AM is the B2B optimal."
#         ),
#         default_value="9",
#         valueType="number",
#         minValue="0",
#         maxValue="23",
#         unit="hour (0-23)",
#     ),
#     ParamDef(
#         key="scheduler_businessHoursEnd",
#         category="Pre-Flight & Scheduling",
#         label="Business Hours End (24h)",
#         description=(
#             "The hour (in the prospect's local timezone) before which "
#             "the scheduler will send emails. After this hour, sends are "
#             "held until the next business day. Also enforces Mon-Fri "
#             "only."
#         ),
#         impact=(
#             "Lowering this (e.g., to 16) means a tighter send window — "
#             "fewer emails per day but all land during peak attention. "
#             "Raising it (e.g., to 19) means a wider window but later "
#             "emails may be ignored. 17 (5 PM) is the B2B standard."
#         ),
#         default_value="17",
#         valueType="number",
#         minValue="1",
#         maxValue="23",
#         unit="hour (0-23)",
#     ),
# ]


# # ── Auto-Pilot & Replies (2) ─────────────────────────────────────────────────

# _AUTOPILOT_REPLIES_PARAMS: list[ParamDef] = [
#     ParamDef(
#         key="autopilot_minConfidence",
#         category="Auto-Pilot & Replies",
#         label="Auto-Pilot Min Confidence",
#         description=(
#             "The minimum confidence score (0-1) a reply categorization "
#             'must have for the reply to be flagged as "auto-pilot '
#             'eligible". Replies at or above this threshold with a '
#             "positive category (interested, meeting_request) can be "
#             "auto-sent without manual review."
#         ),
#         impact=(
#             "Lowering this (e.g., to 0.6) means more replies will be "
#             "auto-answered, increasing response speed but risking "
#             "inappropriate auto-replies on borderline categorizations. "
#             "Raising it (e.g., to 0.9) means only very-high-confidence "
#             "replies are auto-sent, which is safer but means most "
#             "replies still need manual review. This is a trust vs. speed "
#             "tradeoff."
#         ),
#         default_value="0.8",
#         valueType="number",
#         minValue="0.5",
#         maxValue="1",
#         unit="confidence",
#     ),
#     ParamDef(
#         key="replydraft_defaultConfidence",
#         category="Auto-Pilot & Replies",
#         label="Fallback Confidence (on LLM parse failure)",
#         description=(
#             "When the LLM fails to return valid JSON for reply "
#             "categorization, this confidence is assigned as a fallback. "
#             "It should be low (below the auto-pilot threshold) so that "
#             "parse failures never trigger auto-send."
#         ),
#         impact=(
#             "Raising this (e.g., to 0.5) means parse-failed replies will "
#             "have higher confidence, which could accidentally trigger "
#             "auto-pilot if the category happens to be positive. Lowering "
#             "it (e.g., to 0.1) is safer — parse failures will always "
#             "require manual review. Keep this below the auto-pilot min "
#             "confidence."
#         ),
#         default_value="0.3",
#         valueType="number",
#         minValue="0",
#         maxValue="0.5",
#         unit="confidence",
#         isAdvanced=True,
#     ),
# ]


# # ── Aggregate ───────────────────────────────────────────────────────────────

# PARAM_DEFS: list[ParamDef] = (
#     _EMAIL_PARAMS
#     + _SCHEDULER_PARAMS
#     + _LLM_PARAMS
#     + _MAILBRIDGE_PARAMS
#     + _PROSPECTING_PARAMS
#     + _ANALYTICS_PARAMS
#     + _ANALYTICS_BENCHMARKS_PARAMS
#     + _SAMPLE_SIZE_GUARDS_PARAMS
#     + _COPY_ANGLE_DECAY_PARAMS
#     + _EMAIL_WATERFALL_PARAMS
#     + _ENRICHMENT_CLASSIFICATION_PARAMS
#     + _AB_TESTING_PARAMS
#     + _PREFLIGHT_SCHEDULING_PARAMS
#     + _AUTOPILOT_REPLIES_PARAMS
# )


# def _post_check() -> None:
#     """Sanity-check the param list at import time (cheap, dev-only)."""
#     keys = [p.key for p in PARAM_DEFS]
#     if len(keys) != len(set(keys)):
#         dupes = sorted({k for k in keys if keys.count(k) > 1})
#         raise RuntimeError(f"param_defs has duplicate keys: {dupes}")
#     minimum = 30
#     if len(PARAM_DEFS) < minimum:
#         raise RuntimeError(
#             f"param_defs expected >= {minimum} params, got {len(PARAM_DEFS)}"
#         )


# _post_check()


# def to_param_kwargs(defn: ParamDef) -> dict[str, Any]:
#     """
#     Convert a ParamDef into the kwargs dict used to construct a
#     SystemParameter row (matches the model field names exactly).
#     """
#     return {
#         "key": defn.key,
#         "category": defn.category,
#         "label": defn.resolved_label(),
#         "description": defn.description,
#         "impact": defn.impact,
#         "valueType": defn.valueType,
#         "value": defn.default_value,
#         "defaultValue": defn.default_value,
#         "minValue": defn.minValue,
#         "maxValue": defn.maxValue,
#         "unit": defn.unit,
#         "isAdvanced": defn.isAdvanced,
#     }


# __all__ = ["ParamDef", "PARAM_DEFS", "to_param_kwargs"]

"""
param_defs.py — 61 seeded system parameters (per migration doc §3.5 + §10 Phase 2).

Transcribed from the TS ``src/lib/params.ts`` constants, plus the 30
health-diagnostics / A-B-testing / scheduling params transcribed from the
Next.js reference's ``src/modules/system-params/lib/system-param-defs.ts``
(added separately — no key overlap with the operational params below).
Each ParamDef becomes a row in the tenant's ``SystemParameter`` table at
provisioning (see ``app.services.param_service.ParamService.seed_params``).

Categories — operational (31 total):
  - email (8)        — send limits, QA threshold, cadence days, footer flag, ...
  - scheduler (6)    — tick_seconds, partial_cap, business hours, max_instances
  - llm (5)          — default provider/model, timeout, max_tokens, temperature
  - mailbridge (4)   — timeout, retry count/delay, HMAC enforcement
  - prospecting (4)  — cache TTL, max results, validation thresholds
  - analytics (4)    — refresh interval, retention, digest day + hour

Categories — health-diagnostics / statistics (30 total, from the Next.js
reference; these feed Campaign Health Diagnostics, A/B significance testing,
copy-angle decay detection, enrichment tier classification, and the
pre-flight activation gate):
  - Analytics Benchmarks (4)      — open/reply/bounce/positive-reply health thresholds
  - Sample-Size Guards (4)        — min sends/leads before verdicts are trusted
  - Copy Angle Decay (2)          — decay detection + critical-open thresholds
  - Email Waterfall (3)           — enrichment-source confidence scores
  - Enrichment Classification (2) — ENRICHED/PARTIAL tier + review thresholds
  - A/B Testing (4)                — significance / high / marginal p-value thresholds
  - Pre-Flight & Scheduling (9)    — warmup gate, send window, business hours
  - Auto-Pilot & Replies (2)       — auto-send confidence + parse-failure fallback

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
        key="scheduler.enabled",
        category="scheduler",
        label="Scheduler Enabled",
        description=(
            "Master switch for automatic email sending. "
            "When false, the scheduler will not send any emails for this tenant "
            "even if the global SCHEDULER_ENABLED flag is true. "
            "Reply and bounce polling are not affected by this setting."
        ),
        default_value="true",
        valueType="boolean",
        impact="High",
    ),
    ParamDef(
        key="scheduler.tick_interval_minutes",
        category="scheduler",
        label="Send Interval (minutes)",
        description=(
            "How often the scheduler checks for and sends due sequences for this tenant. "
            "Lower values = more frequent sending but more DB load. "
            "5 = every 5 minutes, 15 = every 15 minutes, 60 = hourly. "
            "The global tick still fires on its own interval — this setting controls "
            "whether this tenant is processed on each global tick based on how much "
            "time has passed since the last send."
        ),
        default_value="5",
        valueType="number",
        minValue="1",
        maxValue="1440",
        unit="minutes",
        impact="High",
    ),
    ParamDef(
        key="scheduler.tick_seconds",
        category="scheduler",
        label="Tick Seconds (legacy)",
        description="Interval (seconds) between scheduler ticks. Use tick_interval_minutes instead.",
        default_value="300",
        valueType="number",
        minValue="60",
        maxValue="3600",
        unit="seconds",
        impact="High",
        isAdvanced=True,
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


# ── Analytics Benchmarks (4) ─────────────────────────────────────────────────
# Transcribed from the Next.js reference (src/modules/system-params/lib/
# system-param-defs.ts) — health-diagnostics thresholds consumed by the
# Campaign Health Diagnostics (Layer 1) decision tree. These are additive to
# the operational params above; there is no key overlap.

_ANALYTICS_BENCHMARKS_PARAMS: list[ParamDef] = [
    ParamDef(
        key="benchmark_openRate",
        category="Analytics Benchmarks",
        label="Healthy Open Rate",
        description=(
            'The open rate threshold above which a campaign is considered '
            '"healthy". Used in Campaign Health Diagnostics (Layer 1) to '
            "flag warn/critical engagement issues."
        ),
        impact=(
            "Lowering this (e.g., to 0.45) means fewer campaigns will be "
            'flagged as "warn engagement" — you will get fewer alerts but '
            "may miss real deliverability issues. Raising it (e.g., to "
            "0.60) means more campaigns will be flagged, which could "
            "create alert fatigue if your industry typically has lower "
            "open rates."
        ),
        default_value="0.55",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="% (0-1)",
    ),
    ParamDef(
        key="benchmark_replyRate",
        category="Analytics Benchmarks",
        label="Healthy Reply Rate",
        description=(
            "The reply rate threshold above which a campaign is considered "
            '"healthy". Used in the diagnostic decision tree: if open rate '
            "is healthy but reply rate is below this, the problem is copy "
            "or signal quality."
        ),
        impact=(
            'Lowering this means fewer "copy_or_signal" verdicts — you '
            "will be less alerted to copy problems. Raising it means you "
            "will be pushed to improve copy more aggressively, which may "
            "be premature if your lists are still small."
        ),
        default_value="0.06",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="% (0-1)",
    ),
    ParamDef(
        key="benchmark_bounceRate",
        category="Analytics Benchmarks",
        label="Max Healthy Bounce Rate",
        description=(
            "The bounce rate threshold above which a campaign is flagged "
            'as "critical deliverability". Used in health diagnostics and '
            "the Auto-Optimization Rules Engine default rule."
        ),
        impact=(
            "Lowering this (e.g., to 0.01) means campaigns will be paused "
            "more aggressively on bounces — safer for domain reputation "
            "but may pause campaigns prematurely on small samples. Raising "
            "it (e.g., to 0.03) means more tolerance for bounces, which "
            "risks domain burn if enrichment quality is poor."
        ),
        default_value="0.02",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="% (0-1)",
    ),
    ParamDef(
        key="benchmark_positiveReplyRate",
        category="Analytics Benchmarks",
        label="Healthy Positive Reply Rate",
        description=(
            "The positive reply rate threshold. If reply rate is healthy "
            "but positive reply rate is below this, the diagnostic flags "
            '"offer_mismatch" — meaning you are getting replies but they '
            "are not the right kind."
        ),
        impact=(
            'Lowering this means fewer "offer_mismatch" verdicts — less '
            "pressure to revisit your ICP/offer. Raising it means you "
            "will be pushed to refine your targeting sooner, which is "
            "good for pipeline quality but may be noisy early in a "
            "campaign."
        ),
        default_value="0.025",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="% (0-1)",
    ),
]


# ── Sample-Size Guards (4) ───────────────────────────────────────────────────

_SAMPLE_SIZE_GUARDS_PARAMS: list[ParamDef] = [
    ParamDef(
        key="sampleGuard_campaignSends",
        category="Sample-Size Guards",
        label="Min Sends Per Campaign",
        description=(
            "Minimum number of sends a campaign needs before its metrics "
            'are considered statistically reliable. Below this, the '
            'campaign is flagged "insufficient_data" and verdicts are '
            "suppressed."
        ),
        impact=(
            "Lowering this (e.g., to 30) means you will get verdicts "
            "sooner on small campaigns, but they may be based on noise. "
            "Raising it (e.g., to 100) means more conservative "
            "conclusions — you will wait longer for actionable "
            "diagnostics but they will be more reliable."
        ),
        default_value="50",
        valueType="number",
        minValue="10",
        maxValue="500",
        unit="sends",
    ),
    ParamDef(
        key="sampleGuard_stepSends",
        category="Sample-Size Guards",
        label="Min Sends Per Sequence Step",
        description=(
            "Minimum sends per touchpoint (T1-T6) before step-level reply "
            "rate is considered reliable. Steps below this are flagged "
            '"low n" in the Sequence Step Performance chart.'
        ),
        impact=(
            "Lowering this means step metrics will show sooner, but "
            "small-sample steps may mislead you about which email drives "
            "replies. Raising it means you will wait longer for "
            "step-level insights but they will be more trustworthy."
        ),
        default_value="30",
        valueType="number",
        minValue="10",
        maxValue="200",
        unit="sends",
    ),
    ParamDef(
        key="sampleGuard_intentLeads",
        category="Sample-Size Guards",
        label="Min Leads Per Intent Source",
        description=(
            "Minimum leads an intent source needs before its conversion "
            'rate is shown without a "low n" flag in the Intent Source '
            "Attribution table."
        ),
        impact=(
            "Lowering this means smaller intent sources will show "
            "conversion rates without a warning, which could lead to "
            "reallocating budget based on noise. Raising it means only "
            "well-sampled sources will be trusted, which is safer but may "
            "hide niche high-converting sources."
        ),
        default_value="50",
        valueType="number",
        minValue="10",
        maxValue="200",
        unit="leads",
    ),
    ParamDef(
        key="sampleGuard_angleSends",
        category="Sample-Size Guards",
        label="Min Sends Per Copy Angle",
        description=(
            "Minimum sends per copy angle before its reply rate is "
            "considered reliable and decay detection is enabled."
        ),
        impact=(
            "Lowering this means decay will be detected sooner on new "
            "angles, but you may rotate angles prematurely based on small "
            "samples. Raising it means more confidence in decay detection "
            "but slower reaction to angle fatigue."
        ),
        default_value="30",
        valueType="number",
        minValue="10",
        maxValue="200",
        unit="sends",
    ),
]


# ── Copy Angle Decay (2) ─────────────────────────────────────────────────────

_COPY_ANGLE_DECAY_PARAMS: list[ParamDef] = [
    ParamDef(
        key="decay_relativeDeclineThreshold",
        category="Copy Angle Decay",
        label="Decay Detection Threshold",
        description=(
            "The relative decline in reply rate (this month vs last "
            'month) above which a copy angle is flagged as "Decaying". '
            "For example, 0.25 means a 25%+ relative drop triggers the "
            "flag."
        ),
        impact=(
            "Lowering this (e.g., to 0.15) means angles will be flagged "
            "as decaying sooner — you will rotate copy more frequently, "
            "which prevents fatigue but may retire angles before they "
            "have a chance to recover. Raising it (e.g., to 0.35) means "
            "you will tolerate more decline before acting, which lets "
            "winners run longer but risks missing the fatigue cliff."
        ),
        default_value="0.25",
        valueType="number",
        minValue="0.05",
        maxValue="0.75",
        unit="% (0-1)",
    ),
    ParamDef(
        key="analytics_criticalOpenThreshold",
        category="Copy Angle Decay",
        label="Critical Open Rate Threshold",
        description=(
            "Below this open rate, a campaign is flagged as "
            '"critical_engagement" (red alert) rather than just '
            '"warn_engagement" (yellow). Critical means: check '
            "deliverability immediately, possibly switch sending domains."
        ),
        impact=(
            "Lowering this means fewer red alerts — you will tolerate "
            "lower open rates before triggering urgent deliverability "
            "checks. Raising it means more campaigns will be flagged as "
            "critical, which is safer for domain reputation but may cause "
            "alert fatigue."
        ),
        default_value="0.35",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="% (0-1)",
    ),
]


# ── Email Waterfall (3) ──────────────────────────────────────────────────────

_EMAIL_WATERFALL_PARAMS: list[ParamDef] = [
    ParamDef(
        key="waterfall_confidencePlatformVerified",
        category="Email Waterfall",
        label="Platform-Verified Confidence",
        description=(
            "The confidence score assigned to an email when it comes from "
            "a verified enrichment platform (Apollo, Clearbit, etc.). 1.0 "
            "= highest possible confidence."
        ),
        impact=(
            "This should almost always be 1.0. Lowering it would make "
            "platform-verified emails appear less reliable than they are, "
            "which could trigger unnecessary manual review. Raising it "
            "above 1.0 is invalid."
        ),
        default_value="1.0",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="confidence",
        isAdvanced=True,
    ),
    ParamDef(
        key="waterfall_confidenceMxVerified",
        category="Email Waterfall",
        label="MX-Verified Pattern Confidence",
        description=(
            "The confidence score assigned to an email that was inferred "
            "via pattern (first.last@) and verified via MX record lookup "
            "(domain accepts mail) but not SMTP mailbox probe."
        ),
        impact=(
            "Lowering this (e.g., to 0.5) means pattern-inferred emails "
            "will be treated as lower confidence, which could push more "
            "prospects into the PARTIAL enrichment tier and reduce send "
            "volume. Raising it (e.g., to 0.8) means more trust in "
            "pattern inference, which increases send volume but risks "
            "higher bounce rates on mis-predicted patterns."
        ),
        default_value="0.7",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="confidence",
    ),
    ParamDef(
        key="waterfall_confidenceCatchAll",
        category="Email Waterfall",
        label="Catch-All Domain Confidence",
        description=(
            "The confidence score assigned to an email on a catch-all "
            "domain (a domain that accepts any address, so we cannot "
            "verify the specific mailbox exists). These are the riskiest "
            "inferred emails."
        ),
        impact=(
            "Lowering this (e.g., to 0.2) means catch-all emails will be "
            "treated as very low confidence, likely pushing those "
            "prospects to UNENRICHABLE and suppressing sends. Raising it "
            "(e.g., to 0.5) means more catch-all emails will be sent, "
            "increasing volume but risking higher bounce rates."
        ),
        default_value="0.4",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="confidence",
    ),
]


# ── Enrichment Classification (2) ────────────────────────────────────────────

_ENRICHMENT_CLASSIFICATION_PARAMS: list[ParamDef] = [
    ParamDef(
        key="enrichment_highConfidenceThreshold",
        category="Enrichment Classification",
        label="High-Confidence Email Threshold",
        description=(
            "Email confidence at or above this value is considered "
            '"high confidence" for the ENRICHED tier classification. '
            "Below this (or catch-all) drops the prospect to PARTIAL."
        ),
        impact=(
            "Lowering this (e.g., to 0.5) means more prospects will be "
            "classified as ENRICHED, increasing the pool of "
            "fully-sendable leads. Raising it (e.g., to 0.8) means "
            "stricter quality — fewer prospects will be ENRICHED, but "
            "those that are will have higher deliverability confidence."
        ),
        default_value="0.7",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="confidence",
    ),
    ParamDef(
        key="enrichment_personalizationReviewThreshold",
        category="Enrichment Classification",
        label="Manual Review Confidence Threshold",
        description=(
            "If the AI-generated personalization confidence for an email "
            "opener is below this value, the touch is automatically "
            "flagged for manual review. The AI writes an honest cold "
            "intro instead of pretending to have a signal it does not "
            "have."
        ),
        impact=(
            "Lowering this (e.g., to 0.4) means fewer touches will be "
            "flagged for review — more emails will go out with "
            'potentially thin personalization, increasing volume but '
            'risking "creepy" or generic openers. Raising it (e.g., to '
            "0.7) means more touches will require manual review, "
            "improving opener quality but slowing throughput."
        ),
        default_value="0.6",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="confidence",
    ),
]


# ── A/B Testing (4) ──────────────────────────────────────────────────────────

_AB_TESTING_PARAMS: list[ParamDef] = [
    ParamDef(
        key="abtest_minSendsPerVariant",
        category="A/B Testing",
        label="Min Sends Per Variant",
        description=(
            "Minimum sends per variant before the significance engine "
            'will compute a result. Below this, the test returns '
            '"Insufficient data". This prevents false conclusions from '
            "small samples."
        ),
        impact=(
            "Lowering this (e.g., to 20) means you will get significance "
            "verdicts sooner, but the z-test may declare a winner based "
            "on noise. Raising it (e.g., to 50) means more reliable "
            "results but slower time-to-insight. The statistical "
            "standard is 30 for a reason — change with caution."
        ),
        default_value="30",
        valueType="number",
        minValue="10",
        maxValue="100",
        unit="sends",
    ),
    ParamDef(
        key="abtest_significanceThreshold",
        category="A/B Testing",
        label="Significance Threshold (p-value)",
        description=(
            'The p-value below which a test result is declared '
            '"statistically significant". The standard is 0.05 (95% '
            "confidence). The z-test compares the p-value to this "
            "threshold."
        ),
        impact=(
            "Lowering this (e.g., to 0.01) means you require stronger "
            "evidence before declaring a winner — fewer false positives "
            "but you may need more data to reach a conclusion. Raising "
            "it (e.g., to 0.10) means you will declare winners sooner but "
            "with higher risk of false positives (picking the wrong "
            "variant). The scientific standard is 0.05."
        ),
        default_value="0.05",
        valueType="number",
        minValue="0.01",
        maxValue="0.20",
        unit="p-value",
    ),
    ParamDef(
        key="abtest_highSignificanceThreshold",
        category="A/B Testing",
        label="High Significance Threshold",
        description=(
            'The p-value below which a test result is declared "highly '
            'significant" (99% confidence). This is the gold standard — '
            "a winner at this level is almost certainly real."
        ),
        impact=(
            "This should always be lower than the significance "
            "threshold. Lowering it means requiring even stronger "
            'evidence for the "highly significant" label. Raising it '
            'means more tests will be labeled "highly significant", '
            "which could overstate confidence in marginal results."
        ),
        default_value="0.01",
        valueType="number",
        minValue="0.001",
        maxValue="0.05",
        unit="p-value",
        isAdvanced=True,
    ),
    ParamDef(
        key="abtest_marginalSignificanceThreshold",
        category="A/B Testing",
        label="Marginal Significance Threshold",
        description=(
            'The p-value below which a test result is declared '
            '"marginally significant" (90% confidence). This is a yellow '
            "zone — worth watching but not yet conclusive."
        ),
        impact=(
            "This should always be between the significance and high "
            'thresholds. Raising it (e.g., to 0.15) means more tests will '
            'be labeled "marginal", which could encourage premature '
            "action. Lowering it means fewer marginal results, which is "
            "more conservative."
        ),
        default_value="0.10",
        valueType="number",
        minValue="0.05",
        maxValue="0.20",
        unit="p-value",
        isAdvanced=True,
    ),
]


# ── Pre-Flight & Scheduling (9) ──────────────────────────────────────────────

_PREFLIGHT_SCHEDULING_PARAMS: list[ParamDef] = [
    ParamDef(
        key="preflight_minWarmingWeeks",
        category="Pre-Flight & Scheduling",
        label="Min Domain Warmup Weeks",
        description=(
            "The minimum number of weeks a sending domain must be warmed "
            "before a campaign can be activated. The pre-flight gate "
            "blocks activation below this threshold to prevent domain "
            "reputation burn."
        ),
        impact=(
            "Lowering this (e.g., to 1) means campaigns can launch sooner "
            "on new domains, but significantly increases the risk of "
            "domain reputation damage that takes 30-60 days to recover. "
            "Raising it (e.g., to 3) means safer sends but slower "
            "time-to-campaign on new domains. Industry best practice is "
            "2 weeks minimum."
        ),
        default_value="2",
        valueType="number",
        minValue="1",
        maxValue="8",
        unit="weeks",
    ),
    ParamDef(
        key="preflight_warmingWarnThreshold",
        category="Pre-Flight & Scheduling",
        label="Domain Warmup Warn Threshold",
        description=(
            "Above the min weeks but below this threshold, the "
            'pre-flight gate shows a "warn" (yellow) status: domain is '
            "recently warmed, monitor bounce rate closely. At or above "
            "this threshold, the domain is considered fully warmed "
            "(pass/green)."
        ),
        impact=(
            "Lowering this (e.g., to 3) means domains are considered "
            '"fully warmed" sooner, reducing warnings. Raising it (e.g., '
            "to 6) means more cautious warmup — domains will show "
            "warnings for longer, which is safer but may delay campaigns "
            "unnecessarily."
        ),
        default_value="4",
        valueType="number",
        minValue="2",
        maxValue="12",
        unit="weeks",
    ),
    ParamDef(
        key="preflight_sendWindowDays",
        category="Pre-Flight & Scheduling",
        label="Send Capacity Window (Days)",
        description=(
            "The number of days over which send capacity is calculated. "
            "Capacity = dailySendLimit x this value. If the prospect "
            "count exceeds capacity over this window, the pre-flight gate "
            "blocks activation."
        ),
        impact=(
            "Lowering this (e.g., to 3) means tighter capacity checks — "
            "campaigns will need higher daily limits or fewer prospects "
            "to pass. Raising it (e.g., to 7) means more prospects can be "
            "queued, but if the campaign sends faster than expected, you "
            "may hit daily limits mid-campaign."
        ),
        default_value="5",
        valueType="number",
        minValue="1",
        maxValue="14",
        unit="days",
    ),
    ParamDef(
        key="scheduler_sendHour",
        category="Pre-Flight & Scheduling",
        label="Default Send Hour (24h)",
        description=(
            "The hour of the day (in the prospect's local timezone) when "
            "scheduled emails are sent. 9 = 9:00 AM. The scheduler sends "
            "only during business hours (9am-5pm Mon-Fri)."
        ),
        impact=(
            "Changing this affects when emails land in prospects' "
            "inboxes. 9 AM is optimal for most B2B audiences (email is "
            "at the top of the inbox when they start their day). Earlier "
            "(7-8) may catch early-risers but risks being buried by the "
            "time they check. Later (10-11) means more competition with "
            "other emails. The full business-hours window (9-17) is "
            "enforced separately."
        ),
        default_value="9",
        valueType="number",
        minValue="0",
        maxValue="23",
        unit="hour (0-23)",
    ),
    ParamDef(
        key="domain_defaultDailySendLimit",
        category="Pre-Flight & Scheduling",
        label="Default Daily Send Limit",
        description=(
            "The default daily send limit assigned to new sending "
            "domains when they are first created. This is the number of "
            "emails per day per domain. Used in capacity calculations and "
            "the scheduler."
        ),
        impact=(
            "Lowering this (e.g., to 5) means more conservative sending "
            "— safer for new domains but slower campaign throughput. "
            "Raising it (e.g., to 20) means faster campaigns but higher "
            "risk of triggering spam filters on new domains. The safe "
            "ramp-up is: week 1 = 10/day, week 2 = 20/day, week 3 = "
            "50/day."
        ),
        default_value="10",
        valueType="number",
        minValue="1",
        maxValue="100",
        unit="emails/day",
    ),
    ParamDef(
        key="preflight_emailValidationMinRate",
        category="Pre-Flight & Scheduling",
        label="Email Validation Warn Rate",
        description=(
            "The minimum fraction of campaign prospects whose emails "
            "must be validated before the pre-flight gate will pass "
            'without a warning. Below this, the pre-flight shows a "warn" '
            '(yellow) status recommending you run "Validate All Emails" '
            "first."
        ),
        impact=(
            "Lowering this (e.g., to 0.6) means fewer campaigns will "
            "trigger the validation warning, so you may send to more "
            "unvalidated addresses — higher bounce risk. Raising it "
            "(e.g., to 0.9) means stricter validation requirements, which "
            "reduces bounces but may delay campaigns while you wait for "
            "validation to complete."
        ),
        default_value="0.8",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="% (0-1)",
    ),
    ParamDef(
        key="scheduler_partialVolumeRatio",
        category="Pre-Flight & Scheduling",
        label="PARTIAL-tier Send Volume Ratio",
        description=(
            "The fraction of PARTIAL-tier prospects (catch-all or "
            "partial enrichment) that the scheduler will send to, to "
            "protect deliverability. 0.5 = send to half of them. A "
            "deterministic hash on the sequence ID decides which half — "
            "the same lead is always included or excluded consistently "
            "across ticks."
        ),
        impact=(
            "Lowering this (e.g., to 0.25) means fewer PARTIAL-tier "
            "emails go out, which is safer for domain reputation but "
            "wastes partially-enriched leads. Raising it (e.g., to 0.75) "
            "means more PARTIAL emails go out, increasing volume but "
            "risking higher bounce rates on catch-all domains. 0.5 is "
            "the industry-standard starting point."
        ),
        default_value="0.5",
        valueType="number",
        minValue="0",
        maxValue="1",
        unit="ratio (0-1)",
    ),
    ParamDef(
        key="scheduler_businessHoursStart",
        category="Pre-Flight & Scheduling",
        label="Business Hours Start (24h)",
        description=(
            "The hour (in the prospect's local timezone) after which the "
            "scheduler will send emails. Combined with the End hour, "
            "this defines the daily send window. Emails due outside this "
            "window are held until the next business-hours tick."
        ),
        impact=(
            "Lowering this (e.g., to 7) means emails can go out earlier "
            "in the prospect's morning — may catch early-risers but "
            "risks being buried. Raising it (e.g., to 10) means emails "
            "land later, with more competition. 9 AM is the B2B optimal."
        ),
        default_value="9",
        valueType="number",
        minValue="0",
        maxValue="23",
        unit="hour (0-23)",
    ),
    ParamDef(
        key="scheduler_businessHoursEnd",
        category="Pre-Flight & Scheduling",
        label="Business Hours End (24h)",
        description=(
            "The hour (in the prospect's local timezone) before which "
            "the scheduler will send emails. After this hour, sends are "
            "held until the next business day. Also enforces Mon-Fri "
            "only."
        ),
        impact=(
            "Lowering this (e.g., to 16) means a tighter send window — "
            "fewer emails per day but all land during peak attention. "
            "Raising it (e.g., to 19) means a wider window but later "
            "emails may be ignored. 17 (5 PM) is the B2B standard."
        ),
        default_value="17",
        valueType="number",
        minValue="1",
        maxValue="23",
        unit="hour (0-23)",
    ),
]


# ── Auto-Pilot & Replies (2) ─────────────────────────────────────────────────

_AUTOPILOT_REPLIES_PARAMS: list[ParamDef] = [
    ParamDef(
        key="autopilot_minConfidence",
        category="Auto-Pilot & Replies",
        label="Auto-Pilot Min Confidence",
        description=(
            "The minimum confidence score (0-1) a reply categorization "
            'must have for the reply to be flagged as "auto-pilot '
            'eligible". Replies at or above this threshold with a '
            "positive category (interested, meeting_request) can be "
            "auto-sent without manual review."
        ),
        impact=(
            "Lowering this (e.g., to 0.6) means more replies will be "
            "auto-answered, increasing response speed but risking "
            "inappropriate auto-replies on borderline categorizations. "
            "Raising it (e.g., to 0.9) means only very-high-confidence "
            "replies are auto-sent, which is safer but means most "
            "replies still need manual review. This is a trust vs. speed "
            "tradeoff."
        ),
        default_value="0.8",
        valueType="number",
        minValue="0.5",
        maxValue="1",
        unit="confidence",
    ),
    ParamDef(
        key="replydraft_defaultConfidence",
        category="Auto-Pilot & Replies",
        label="Fallback Confidence (on LLM parse failure)",
        description=(
            "When the LLM fails to return valid JSON for reply "
            "categorization, this confidence is assigned as a fallback. "
            "It should be low (below the auto-pilot threshold) so that "
            "parse failures never trigger auto-send."
        ),
        impact=(
            "Raising this (e.g., to 0.5) means parse-failed replies will "
            "have higher confidence, which could accidentally trigger "
            "auto-pilot if the category happens to be positive. Lowering "
            "it (e.g., to 0.1) is safer — parse failures will always "
            "require manual review. Keep this below the auto-pilot min "
            "confidence."
        ),
        default_value="0.3",
        valueType="number",
        minValue="0",
        maxValue="0.5",
        unit="confidence",
        isAdvanced=True,
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
    + _ANALYTICS_BENCHMARKS_PARAMS
    + _SAMPLE_SIZE_GUARDS_PARAMS
    + _COPY_ANGLE_DECAY_PARAMS
    + _EMAIL_WATERFALL_PARAMS
    + _ENRICHMENT_CLASSIFICATION_PARAMS
    + _AB_TESTING_PARAMS
    + _PREFLIGHT_SCHEDULING_PARAMS
    + _AUTOPILOT_REPLIES_PARAMS
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
