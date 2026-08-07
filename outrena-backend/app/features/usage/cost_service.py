"""
cost_service.py — Per-provider cost computation (in integer cents).

The cost table is hardcoded with documented defaults that mirror each
provider's public pricing page (Jan 2025). It can be overridden at runtime
via:

  1. ``USAGE_COST_TABLE_JSON`` env var — a JSON string with the same shape
     as ``DEFAULT_COST_TABLE``. Useful for staging/prod overrides without
     a release.
  2. ``public.cost_config`` table (created by migration 0006) — row-level
     overrides per (provider, model, event_type). The table is consulted
     on every ``compute_*`` call; missing rows fall through to the
     hardcoded defaults. Updates land immediately because the lookup is
     not cached (cost rows number in the low hundreds, so the perf cost
     is negligible).

Costs are returned as INTEGER CENTS (not float dollars) to avoid float-
rounding drift in aggregations. The LLM cost is computed as::

    cents = round(
        prompt_tokens      * input_per_1k_cents  / 1000
      + completion_tokens  * output_per_1k_cents / 1000
    )

A cost of 0 means "free / infrastructure cost" (e.g. email_send — the per-
send cost is paid to the SMTP provider and not passed through to the
tenant).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


# ── Hardcoded defaults (cents per 1K tokens for LLM, cents per call for
#    enrichment / LinkedIn). All numbers are USD × 100. Source: provider
#    pricing pages, Jan 2025. Override via USAGE_COST_TABLE_JSON or the
#    public.cost_config table.
# ──────────────────────────────────────────────────────────────────────────
DEFAULT_COST_TABLE: dict[str, Any] = {
    # LLM pricing: {provider: {model: {"input": cents/1K, "output": cents/1K}}}
    "llm": {
        "openai": {
            "gpt-4o": {"input": 2.5, "output": 10.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.6},
            "gpt-4-turbo": {"input": 10.0, "output": 30.0},
            "gpt-4": {"input": 30.0, "output": 60.0},
            "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
            "o1": {"input": 15.0, "output": 60.0},
            "o1-mini": {"input": 3.0, "output": 12.0},
            "o3-mini": {"input": 3.0, "output": 12.0},
        },
        "anthropic": {
            "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
            "claude-3-5-haiku": {"input": 0.8, "output": 4.0},
            "claude-3-opus": {"input": 15.0, "output": 75.0},
            "claude-3-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
        },
        "google": {
            "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
            "gemini-1.5-flash": {"input": 0.075, "output": 0.3},
            "gemini-2.0-flash": {"input": 0.1, "output": 0.4},
            "gemini-1.0-pro": {"input": 0.5, "output": 1.5},
        },
        "azure": {
            # Mirrors OpenAI pricing for the same models deployed via Azure
            # OpenAI. Per-deployment overrides go in public.cost_config.
            "gpt-4o": {"input": 2.5, "output": 10.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.6},
            "gpt-4": {"input": 30.0, "output": 60.0},
            "gpt-35-turbo": {"input": 0.5, "output": 1.5},
        },
        "bedrock": {
            # Anthropic on Bedrock — same pricing as direct Anthropic API.
            "anthropic.claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
            "anthropic.claude-3-haiku": {"input": 0.25, "output": 1.25},
            "anthropic.claude-3-opus": {"input": 15.0, "output": 75.0},
        },
        "cohere": {
            "command-r-plus": {"input": 2.5, "output": 10.0},
            "command-r": {"input": 0.15, "output": 0.6},
        },
        "mistral": {
            "mistral-large-latest": {"input": 2.0, "output": 6.0},
            "mistral-small-latest": {"input": 0.2, "output": 0.6},
            "open-mixtral-8x7b": {"input": 0.27, "output": 0.27},
        },
        "llama": {  # Meta Llama via Together AI
            "meta-llama/Llama-3.3-70B-Instruct-Turbo": {"input": 0.88, "output": 0.88},
            "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": {"input": 5.0, "output": 5.0},
        },
        "groq": {
            "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
            "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
        },
        "ai21": {
            "jamba-1.5-large": {"input": 2.0, "output": 8.0},
            "jamba-1.5-mini": {"input": 0.2, "output": 0.4},
        },
        "huggingface": {
            # Generic per-model pricing is set in the model card; default
            # to a conservative rate so unconfigured models don't show 0.
            "_default": {"input": 1.0, "output": 1.0},
        },
        "zai": {
            "glm-4-plus": {"input": 0.7, "output": 0.7},
            "glm-4": {"input": 0.7, "output": 0.7},
            "glm-4-flash": {"input": 0.0, "output": 0.0},  # free tier
            "glm-4-air": {"input": 0.1, "output": 0.1},
        },
        "local": {
            # Self-hosted Ollama — no per-call cost; infra cost is allocated
            # separately by the FinOps report (see runbooks/14-cost-management.md).
            "_default": {"input": 0.0, "output": 0.0},
        },
    },
    # Enrichment: cents per successful lookup
    "enrichment": {
        "apollo": 5.0,
        "zoominfo": 8.0,
        "clearbit": 3.0,
        "hunter": 2.0,
        "snov": 2.5,
        "lusha": 6.0,
        "_default": 3.0,
    },
    # LinkedIn: cents per API action (connect, message, profile view)
    "linkedin": {
        "action": 2.0,
        "_default": 2.0,
    },
}


@lru_cache(maxsize=1)
def _env_overrides() -> dict[str, Any]:
    """Load USAGE_COST_TABLE_JSON env var (a JSON string) once at startup.

    Returns an empty dict if the var is unset or invalid; the cost service
    falls through to the hardcoded defaults in that case. Cached for the
    lifetime of the process — operators must restart to pick up an env
    change. For hot reload, use the public.cost_config table instead.
    """
    raw = os.environ.get("USAGE_COST_TABLE_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("cost_service.env_overrides_parse_failed", error=str(exc))
        return {}


class CostService:
    """Compute per-event cost in integer cents.

    Stateless on the Python side (cost lookups hit the DB or the env
    override / defaults). Designed to be instantiated cheaply — no
    constructor args, no per-instance state.
    """

    # ── LLM ──────────────────────────────────────────────────────────────
    async def compute_llm_cost(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        db: AsyncSession | None = None,
    ) -> int:
        """Return integer cents for one LLM call.

        ``db`` is optional; if provided, ``public.cost_config`` is consulted
        for per-(provider, model) overrides. Missing rows fall through to
        the hardcoded defaults + env override.
        """
        provider_key = (provider or "").lower()
        model_key = (model or "").lower()

        # 1. DB override (only if a session was passed in)
        if db is not None:
            db_input, db_output = await self._db_llm_rate(db, provider_key, model_key)
            if db_input is not None and db_output is not None:
                return _llm_cents(db_input, db_output, prompt_tokens, completion_tokens)

        # 2. Env override (USAGE_COST_TABLE_JSON)
        env = _env_overrides()
        env_llm = env.get("llm") or {}
        env_provider = env_llm.get(provider_key) or {}
        env_model = env_provider.get(model_key) or env_provider.get("_default")
        if isinstance(env_model, dict) and "input" in env_model and "output" in env_model:
            return _llm_cents(
                float(env_model["input"]),
                float(env_model["output"]),
                prompt_tokens,
                completion_tokens,
            )

        # 3. Hardcoded defaults
        provider_table = DEFAULT_COST_TABLE["llm"].get(provider_key) or {}
        model_rates = provider_table.get(model_key) or provider_table.get("_default") or {}
        input_cents = float(model_rates.get("input", 0.0))
        output_cents = float(model_rates.get("output", 0.0))
        return _llm_cents(input_cents, output_cents, prompt_tokens, completion_tokens)

    # ── Enrichment ───────────────────────────────────────────────────────
    async def compute_enrichment_cost(
        self,
        provider: str,
        count: int = 1,
        db: AsyncSession | None = None,
    ) -> int:
        """Return integer cents for ``count`` enrichment lookups."""
        provider_key = (provider or "").lower()
        rate = await self._per_unit_rate(db, "enrichment", provider_key)
        return max(0, int(round(rate * count)))

    # ── LinkedIn ─────────────────────────────────────────────────────────
    async def compute_linkedin_cost(
        self,
        action_count: int = 1,
        db: AsyncSession | None = None,
    ) -> int:
        """Return integer cents for ``action_count`` LinkedIn API actions."""
        rate = await self._per_unit_rate(db, "linkedin", "action")
        return max(0, int(round(rate * action_count)))

    # ── Cost-table introspection + admin updates ─────────────────────────
    def get_cost_table(self) -> dict[str, Any]:
        """Return the effective cost table (defaults merged with env overrides).

        Used by GET /usage/cost-table. Does NOT include DB overrides —
        those are queried separately by the SUPER_ADMIN endpoint.
        """
        merged: dict[str, Any] = {"llm": {}, "enrichment": dict(DEFAULT_COST_TABLE["enrichment"]),
                                  "linkedin": dict(DEFAULT_COST_TABLE["linkedin"])}
        # LLM merge: per-provider, per-model
        env = _env_overrides()
        env_llm = env.get("llm") or {}
        for provider, models in DEFAULT_COST_TABLE["llm"].items():
            merged_models = dict(models)
            env_models = env_llm.get(provider) or {}
            if isinstance(env_models, dict):
                for m, rates in env_models.items():
                    if isinstance(rates, dict):
                        merged_models[m] = dict(rates)
            merged["llm"][provider] = merged_models
        # Enrichment / LinkedIn env overrides
        env_enrich = env.get("enrichment") or {}
        if isinstance(env_enrich, dict):
            merged["enrichment"].update(env_enrich)
        env_linkedin = env.get("linkedin") or {}
        if isinstance(env_linkedin, dict):
            merged["linkedin"].update(env_linkedin)
        return merged

    async def update_cost_table(
        self, db: AsyncSession, updates: dict[str, Any]
    ) -> None:
        """Upsert rows into public.cost_config (SUPER_ADMIN only).

        ``updates`` shape mirrors DEFAULT_COST_TABLE:
            {
              "llm": {"openai": {"gpt-4o": {"input": 2.5, "output": 10.0}}},
              "enrichment": {"apollo": 6.0},
              "linkedin": {"action": 2.5}
            }
        """
        rows: list[dict[str, Any]] = []
        for provider, models in (updates.get("llm") or {}).items():
            for model, rates in (models or {}).items():
                if not isinstance(rates, dict):
                    continue
                input_c = float(rates.get("input", 0.0))
                output_c = float(rates.get("output", 0.0))
                # Store as a single row per (provider, model) with cost_per_unit_cents
                # set to the input rate and the output rate stored in metadata.
                rows.append({
                    "event_type": "llm_call",
                    "provider": provider.lower(),
                    "model": model.lower(),
                    "cost_per_unit_cents": input_c,
                    "unit": "tokens_input",
                    "extra": json.dumps({"output_cents_per_1k": output_c}),
                })
        for provider, rate in (updates.get("enrichment") or {}).items():
            rows.append({
                "event_type": "prospect_enrich",
                "provider": provider.lower(),
                "model": None,
                "cost_per_unit_cents": float(rate),
                "unit": "calls",
                "extra": None,
            })
        for action, rate in (updates.get("linkedin") or {}).items():
            rows.append({
                "event_type": "linkedin_action",
                "provider": action.lower(),
                "model": None,
                "cost_per_unit_cents": float(rate),
                "unit": "actions",
                "extra": None,
            })

        for r in rows:
            await db.execute(
                text(
                    "INSERT INTO public.cost_config "
                    "(event_type, provider, model, cost_per_unit_cents, unit, extra) "
                    "VALUES (:et, :p, :m, :c, :u, CAST(:x AS jsonb)) "
                    "ON CONFLICT (event_type, provider, model) DO UPDATE "
                    "SET cost_per_unit_cents = EXCLUDED.cost_per_unit_cents, "
                    "    unit = EXCLUDED.unit, "
                    "    extra = EXCLUDED.extra, "
                    "    updated_at = NOW()"
                ),
                {
                    "et": r["event_type"],
                    "p": r["provider"],
                    "m": r["model"],
                    "c": r["cost_per_unit_cents"],
                    "u": r["unit"],
                    "x": r["extra"] or "null",
                },
            )
        await db.commit()

    # ── DB-override lookups ──────────────────────────────────────────────
    async def _db_llm_rate(
        self, db: AsyncSession, provider: str, model: str
    ) -> tuple[float | None, float | None]:
        """Return (input_cents_per_1k, output_cents_per_1k) from public.cost_config.

        Returns (None, None) when no row exists (caller falls through to
        the hardcoded defaults). Best-effort: any DB error is logged and
        treated as "no override".
        """
        if not provider:
            return None, None
        try:
            row = (
                await db.execute(
                    text(
                        "SELECT cost_per_unit_cents, extra "
                        "FROM public.cost_config "
                        "WHERE event_type = 'llm_call' "
                        "AND provider = :p AND COALESCE(model, '') = COALESCE(:m, '')"
                    ),
                    {"p": provider, "m": model or ""},
                )
            ).fetchone()
        except Exception as exc:  # noqa: BLE001 — cost lookup must never crash the caller
            logger.warning("cost_service.db_llm_rate_failed", error=str(exc))
            return None, None
        if row is None:
            return None, None
        input_c = float(row.cost_per_unit_cents or 0.0)
        output_c = 0.0
        extra = row.extra
        if isinstance(extra, dict):
            output_c = float(extra.get("output_cents_per_1k", 0.0))
        return input_c, output_c

    async def _per_unit_rate(
        self, db: AsyncSession | None, category: str, provider: str
    ) -> float:
        """Return the per-unit rate (cents) for ``category``/``provider``.

        Resolution order: public.cost_config → USAGE_COST_TABLE_JSON →
        DEFAULT_COST_TABLE.
        """
        # DB override
        if db is not None and provider:
            event_type = (
                "prospect_enrich" if category == "enrichment" else "linkedin_action"
            )
            try:
                row = (
                    await db.execute(
                        text(
                            "SELECT cost_per_unit_cents FROM public.cost_config "
                            "WHERE event_type = :et AND provider = :p "
                            "AND model IS NULL"
                        ),
                        {"et": event_type, "p": provider},
                    )
                ).fetchone()
                if row is not None:
                    return float(row.cost_per_unit_cents or 0.0)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cost_service.db_per_unit_failed", error=str(exc))

        # Env override
        env = _env_overrides()
        env_cat = env.get(category) or {}
        if isinstance(env_cat, dict):
            v = env_cat.get(provider) or env_cat.get("_default")
            if isinstance(v, (int, float)):
                return float(v)

        # Hardcoded defaults
        cat = DEFAULT_COST_TABLE.get(category) or {}
        v = cat.get(provider) or cat.get("_default") or 0.0
        return float(v)


def _llm_cents(
    input_cents_per_1k: float,
    output_cents_per_1k: float,
    prompt_tokens: int,
    completion_tokens: int,
) -> int:
    """Compute integer cents for one LLM call."""
    if prompt_tokens <= 0 and completion_tokens <= 0:
        return 0
    raw = (
        prompt_tokens * input_cents_per_1k / 1000.0
        + completion_tokens * output_cents_per_1k / 1000.0
    )
    return max(0, int(round(raw)))


__all__ = ["CostService", "DEFAULT_COST_TABLE"]
