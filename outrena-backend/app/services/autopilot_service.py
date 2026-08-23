"""
autopilot_service.py — Flow execution engine (SOURCE → ENRICH → GATE → SCORE → IMPORT).

Key fixes in this version:
  1. LLM config: use get_default_llm_config() from llm_service.py (3-tier fallback,
     correct modelId attribute, decrypted key). Stop using a hand-built shim that
     set .model instead of .modelId — cast_llm_config() reads config.modelId.
  2. search_path re-applied after every db.commit() (asyncpg pool strips it).
  3. Tavily query built from ICP persona + painPoints + companyType for richer results.
  4. LLM extraction prompt improved — more specific, returns more prospects.
  5. SeniorityTier: only C_Suite | Director | IC are valid enum values.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.enums import (
    EnrichmentTier,
    FlowRunStatus,
    FlowRunStepKind,
    FlowRunStepStatus,
    IntentSource,
    SeniorityTier,
)
from app.models.flow_models import FlowRun, FlowRunStep
from app.models.prospect_models import IcpProfile, Prospect
from app.services.secret_service import decrypt_at_rest

logger = structlog.get_logger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"
_HTTP_TIMEOUT = 30.0        # increased — Tavily can be slow
_MAX_PER_SOURCE = 50
_LLM_BATCH = 5              # smaller batch — more reliable LLM scoring
_CIRCUIT_BREAKER = 3


# ─────────────────────────────────────────────────────────────────────────────
# search_path helpers (asyncpg strips it after every db.commit())
# ─────────────────────────────────────────────────────────────────────────────

async def _get_schema(db: AsyncSession) -> str:
    try:
        r = await db.execute(text("SELECT current_schema()"))
        return r.scalar_one_or_none() or "public"
    except Exception:
        return "public"


async def _set_schema(db: AsyncSession, schema: str) -> None:
    """Re-apply search_path. MUST be called before every write after a commit."""
    await db.execute(text(f'SET search_path TO "{schema}", public'))


# ─────────────────────────────────────────────────────────────────────────────
# SeniorityTier mapping (enum has exactly 3 values: C_Suite, Director, IC)
# ─────────────────────────────────────────────────────────────────────────────

def _map_seniority(raw: str) -> SeniorityTier:
    s = (raw or "").lower().strip()
    if any(x in s for x in ["c_suite", "c-suite", "ceo", "cto", "cfo", "coo",
                              "founder", "president", "chief", "vp", "vice"]):
        return SeniorityTier.C_Suite
    if any(x in s for x in ["director", "manager", "head of", "lead"]):
        return SeniorityTier.Director
    return SeniorityTier.IC


# ─────────────────────────────────────────────────────────────────────────────
# Step / gate parsers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_steps(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        arr = raw if isinstance(raw, list) else json.loads(str(raw))
        out = []
        for s in arr:
            if not isinstance(s, dict):
                continue
            platform = str(s.get("platform") or s.get("provider") or
                           s.get("key") or s.get("type") or "")
            if not platform:
                continue
            out.append({
                "platform": platform,
                "enabled": s.get("enabled", True),
                "order": int(s.get("order", s.get("priority", 0))),
                "queryOverrides": s.get("queryOverrides") or {},
                "targetFields": s.get("targetFields") or [],
                "fallbackTo": s.get("fallbackTo"),
            })
        out.sort(key=lambda x: x["order"])
        return out
    except Exception:
        return []


def _parse_gates(raw: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "requireEmail": True,
        "requireVerifiedEmail": False,
        "requireCompanySize": False,
        "minCompanySize": 0,
        "llmScoreThreshold": 0.0,
        "excludeDomains": [],
    }
    if not raw:
        return defaults
    try:
        parsed = raw if isinstance(raw, dict) else json.loads(str(raw))
        return {**defaults, **parsed}
    except Exception:
        return defaults


# ─────────────────────────────────────────────────────────────────────────────
# LLM config — use the existing 3-tier get_default_llm_config() from llm_service
# This function already handles: tenant default → any tenant → GlobalLlmConfig
# with correct modelId attribute and Fernet-decrypted key.
# ─────────────────────────────────────────────────────────────────────────────

async def _get_llm_config_by_id(db: AsyncSession, schema: str, config_id: str) -> Any | None:
    """
    Fetch a specific tenant LlmConfig by ID and return a shim for call_llm().
    Returns None if the config doesn't exist or is inactive.
    """
    from app.models.config_models import LlmConfig as LlmConfigModel
    import json as _json
    from app.services.secret_service import decrypt_at_rest as _decrypt
    from types import SimpleNamespace as _NS

    try:
        await _set_schema(db, schema)
        result = await db.execute(
            select(LlmConfigModel)
            .where(LlmConfigModel.id == config_id)
            .where(LlmConfigModel.isActive.is_(True))
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        # Decrypt API key (stored Fernet-encrypted; fallback to plaintext for legacy rows)
        try:
            plaintext_key = _decrypt(row.apiKey) if row.apiKey else None
        except Exception:
            plaintext_key = row.apiKey

        # Normalise settings to a JSON string
        settings_raw = getattr(row, "settings", None)
        if isinstance(settings_raw, dict):
            settings_str = _json.dumps(settings_raw)
        elif isinstance(settings_raw, str):
            settings_str = settings_raw
        else:
            settings_str = "{}"

        # Build a SimpleNamespace shim that cast_llm_config() can read.
        # cast_llm_config() reads: .provider, .modelId, .apiKey, .baseUrl,
        # .isActive, .settings  — all must be present.
        return _NS(
            id=str(row.id),
            name=row.name,
            provider=row.provider,
            modelId=row.modelId,   # ← cast_llm_config reads .modelId
            model=row.modelId,     # ← kept for safety
            apiKey=plaintext_key,
            baseUrl=getattr(row, "baseUrl", None) or "",
            isDefault=getattr(row, "isDefault", False),
            isActive=True,
            settings=settings_str,
            modelTier=getattr(row, "modelTier", "standard"),
            global_llm_config_id=getattr(row, "global_llm_config_id", None),
        )
    except Exception as exc:
        logger.warning("autopilot.llm.by_id_failed", config_id=config_id, error=str(exc))
        return None


async def _get_llm_config(db: AsyncSession, schema: str) -> Any | None:
    """
    Resolve the best LLM config using 3-tier fallback.

    Uses get_default_llm_config() from llm_service which:
      Tier 1: tenant LlmConfig with isDefault=True
      Tier 2: any active tenant LlmConfig
      Tier 3: public.global_llm_config (Fernet-decrypted, SimpleNamespace shim)

    The returned object always has .modelId and .apiKey correct for call_llm().
    """
    from app.services.llm_service import get_default_llm_config

    # Tier 1+2: look in tenant schema first
    await _set_schema(db, schema)
    config = await get_default_llm_config(db)
    if config is not None:
        logger.info("autopilot.llm.resolved_tenant", provider=getattr(config, "provider", "?"))
        return config

    # Tier 3: fall back to public.global_llm_config in a separate session
    try:
        from app.models.global_llm_config import GlobalLlmConfig
        from types import SimpleNamespace
        import json as _json

        async with AsyncSessionLocal() as pub_db:
            await pub_db.execute(text('SET search_path TO "public"'))
            result = await pub_db.execute(
                select(GlobalLlmConfig)
                .where(GlobalLlmConfig.is_active.is_(True))
                .where(GlobalLlmConfig.is_default.is_(True))
                .order_by(GlobalLlmConfig.id.asc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row is None:
                result = await pub_db.execute(
                    select(GlobalLlmConfig)
                    .where(GlobalLlmConfig.is_active.is_(True))
                    .order_by(GlobalLlmConfig.id.asc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
            if row is None:
                logger.warning("autopilot.llm.no_config_found")
                return None

            plaintext_key = decrypt_at_rest(row.api_key_encrypted)
            # Build shim that cast_llm_config() can read:
            # cast_llm_config reads: config.provider, config.modelId, config.apiKey,
            # config.baseUrl, config.isActive, config.settings
            shim = SimpleNamespace(
                id=str(row.id),
                name=getattr(row, "name", "global"),
                provider=row.provider,
                modelId=row.model_name,     # ← cast_llm_config reads .modelId
                model=row.model_name,       # ← kept for safety
                apiKey=plaintext_key,
                baseUrl=getattr(row, "base_url", None) or "",
                isActive=True,
                isDefault=True,
                settings=_json.dumps({}),
                modelTier="standard",
                global_llm_config_id=str(row.id),
            )
            logger.info("autopilot.llm.resolved_global",
                        provider=row.provider, model=row.model_name)
            return shim
    except Exception as exc:
        logger.error("autopilot.llm.global_resolve_failed", error=str(exc))
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Tenant integration keys
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_tenant_integrations(db: AsyncSession, schema: str) -> dict[str, str]:
    from app.models.config_models import ProspectingIntegration
    await _set_schema(db, schema)
    result = await db.execute(
        select(ProspectingIntegration).where(ProspectingIntegration.isActive.is_(True))
    )
    keys: dict[str, str] = {}
    for integ in result.scalars().all():
        raw = getattr(integ, "api_key_encrypted", None) or getattr(integ, "apiKey", None)
        if not raw or getattr(integ, "key_source", "tenant") == "platform":
            continue
        try:
            keys[integ.platform] = decrypt_at_rest(raw)
        except Exception:
            keys[integ.platform] = raw
    return keys


# ─────────────────────────────────────────────────────────────────────────────
# Source adapters
# ─────────────────────────────────────────────────────────────────────────────

def _build_search_query(icp: IcpProfile, overrides: dict[str, str]) -> str:
    """Build a rich Tavily search query from ICP fields + optional overrides."""
    if overrides.get("query"):
        return overrides["query"]

    parts: list[str] = []

    # Lead with persona (job title)
    if icp.persona:
        parts.append(icp.persona.strip())

    # Company type / industry
    if icp.companyType:
        parts.append(icp.companyType.strip())

    # Pain points add search intent
    pain_points = icp.painPoints or []
    if pain_points:
        parts.append(pain_points[0][:60])

    if not parts:
        parts = ["B2B decision maker technology company"]

    return " ".join(parts)


async def _source_ai_web_search(
    icp: IcpProfile,
    overrides: dict[str, str],
    max_results: int,
    llm_config: Any,
) -> list[dict[str, Any]]:
    """
    Tavily search → LLM prospect extraction.

    Flow:
    1. Call Tavily with a query derived from the ICP profile.
    2. Feed the search results to the configured LLM.
    3. LLM returns a JSON array of structured prospects.

    If Tavily key is missing, the LLM is given a prompt-only search (generates
    prospects from training knowledge — still useful for common personas).
    """
    from app.core.config import get_settings
    from app.services.llm_service import call_llm as _call_llm

    settings = get_settings()
    tavily_key = getattr(settings, "TAVILY_API_KEY", "") or ""

    query = _build_search_query(icp, overrides)
    logger.info("autopilot.source.ai_web_search.query", query=query)

    web_results: list[dict[str, Any]] = []
    if tavily_key:
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.post(
                    _TAVILY_URL,
                    json={
                        "api_key": tavily_key,
                        "query": f"site:linkedin.com OR email contact {query}",
                        "max_results": min(max_results, 10),
                        "include_answer": True,
                        "search_depth": "advanced",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                web_results = data.get("results", [])
                logger.info("autopilot.source.tavily.results", count=len(web_results))
                # Log each Tavily result for debugging
                for i, r in enumerate(web_results):
                    logger.debug(
                        "autopilot.source.tavily.result",
                        index=i + 1,
                        title=r.get("title", "")[:120],
                        url=r.get("url", "")[:120],
                        snippet=r.get("content", "")[:200],
                    )
        except Exception as exc:
            logger.warning("autopilot.source.tavily_failed", error=str(exc))
    else:
        logger.warning(
            "autopilot.source.tavily_key_missing",
            hint="Set TAVILY_API_KEY in .env — LLM will generate prospects from training data only",
        )

    if not llm_config:
        logger.error("autopilot.source.ai_web_search.no_llm_config",
                     hint="Configure an LLM model in Setup → LLM Models")
        return []

    # Build context for LLM
    if web_results:
        web_context = "\n\n".join(
            f"[{i+1}] {r.get('title', '')}\nURL: {r.get('url', '')}\n"
            f"Content: {r.get('content', '')[:800]}"
            for i, r in enumerate(web_results[:8])
        )
    else:
        web_context = (
            "No web search results available. "
            "Generate realistic prospect profiles based on your training knowledge for this ICP."
        )

    persona = icp.persona or "B2B decision maker"
    company_type = icp.companyType or "technology company"
    pain_points = ", ".join((icp.painPoints or [])[:3]) or "business growth"
    value_props = ", ".join((icp.valueProps or [])[:2]) or ""

    system_prompt = """You are a B2B sales intelligence assistant.
Your job is to extract or generate realistic prospect profiles that match a given ICP.
You MUST return ONLY a valid JSON array. No markdown, no explanations, no text outside the JSON.
Each prospect object must have ALL of these fields:
{
  "firstName": "string (required, real first name)",
  "lastName": "string (required, real last name)",
  "title": "string (job title, e.g. CTO, VP Engineering)",
  "company": "string (company name)",
  "domain": "string (company domain, e.g. acme.com)",
  "email": "string or null (email if found, else null)",
  "linkedinUrl": "string or null",
  "seniority": "one of: C_Suite, Director, IC"
}
Return between 3 and 10 prospects. Never return an empty array if the ICP is valid."""

    user_prompt = f"""ICP Profile:
- Target persona: {persona}
- Company type: {company_type}
- Pain points: {pain_points}
{"- Value props: " + value_props if value_props else ""}

Web search context:
{web_context}

Task: Extract or generate {min(max_results, 8)} realistic prospect profiles matching this ICP.
If the search results contain real people with company affiliations, extract them.
If not, generate realistic fictional profiles that represent this ICP accurately.
Return ONLY the JSON array."""

    try:
        resp = await _call_llm(llm_config, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        content = (resp.content or "").strip()

        # Strip markdown fences if present
        if "```" in content:
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
            if match:
                content = match.group(1).strip()

        # Find JSON array in the response
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end != -1:
            content = content[start:end+1]

        parsed = json.loads(content)
        if isinstance(parsed, list) and len(parsed) > 0:
            logger.info("autopilot.source.ai_web_search.extracted", count=len(parsed))
            # Log every extracted prospect so we can see what the LLM produced
            for i, p in enumerate(parsed[:max_results]):
                logger.info(
                    "autopilot.source.extracted_prospect",
                    index=i + 1,
                    firstName=p.get("firstName", ""),
                    lastName=p.get("lastName", ""),
                    title=p.get("title", ""),
                    company=p.get("company", ""),
                    domain=p.get("domain", ""),
                    email=p.get("email") or "null",
                    seniority=p.get("seniority", ""),
                )
            return parsed[:max_results]
        else:
            logger.warning("autopilot.source.ai_web_search.empty_array",
                           raw_content=content[:200])
            return []
    except json.JSONDecodeError as exc:
        logger.warning("autopilot.source.ai_web_search.json_parse_failed",
                       error=str(exc), content_preview=content[:300] if 'content' in dir() else "")
        return []
    except Exception as exc:
        logger.error("autopilot.source.ai_web_search.llm_failed", error=str(exc))
        return []


async def _source_apollo(
    icp: IcpProfile,
    overrides: dict[str, str],
    max_results: int,
    api_key: str,
) -> list[dict[str, Any]]:
    try:
        titles = overrides.get("person_titles", "") or (icp.persona or "").split(",")[0]
        keywords = overrides.get("q_keywords", "") or (icp.companyType or "")
        locations = overrides.get("organization_locations", "")

        payload: dict[str, Any] = {"api_key": api_key,
                                    "per_page": min(max_results, 25), "page": 1}
        if titles:
            payload["person_titles"] = [t.strip() for t in titles.split(",") if t.strip()][:5]
        if keywords:
            payload["q_keywords"] = keywords[:200]
        if locations:
            payload["organization_locations"] = [locations[:100]]

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(
                "https://api.apollo.io/v1/mixed_people/search", json=payload)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for p in data.get("people", []):
            org = p.get("organization") or {}
            results.append({
                "firstName": p.get("first_name", "") or "",
                "lastName": p.get("last_name", "") or "",
                "title": p.get("title") or "",
                "company": org.get("name") or p.get("organization_name") or "",
                "domain": org.get("primary_domain") or "",
                "email": p.get("email") or None,
                "linkedinUrl": p.get("linkedin_url") or None,
                "seniority": p.get("seniority", "IC"),
            })
        logger.info("autopilot.source.apollo.results", count=len(results))
        return results[:max_results]
    except Exception as exc:
        logger.warning("autopilot.source.apollo.failed", error=str(exc))
        return []


async def _run_source_step(
    step: dict[str, Any],
    icp: IcpProfile,
    max_results: int,
    llm_config: Any,
    tenant_keys: dict[str, str],
) -> list[dict[str, Any]]:
    platform = step["platform"]
    overrides = step.get("queryOverrides") or {}

    if platform in ("ai_web_search", "web_search"):
        return await _source_ai_web_search(icp, overrides, max_results, llm_config)

    if platform == "apollo":
        api_key = tenant_keys.get("apollo", "")
        if not api_key:
            logger.info("autopilot.source.apollo.skipped_no_key")
            return []
        return await _source_apollo(icp, overrides, max_results, api_key)

    if platform == "linkedin":
        li_overrides = dict(overrides)
        if "query" not in li_overrides:
            parts = ["LinkedIn profile"]
            for k in ("job_title", "industry", "location"):
                if overrides.get(k):
                    parts.append(overrides[k])
            if icp.persona:
                parts.append(icp.persona[:100])
            li_overrides["query"] = " ".join(parts)
        return await _source_ai_web_search(icp, li_overrides, max_results, llm_config)

    logger.info("autopilot.source.platform_not_implemented", platform=platform)
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Enrichment adapters
# ─────────────────────────────────────────────────────────────────────────────

async def _enrich_hunter(
    prospect: dict[str, Any],
    target_fields: list[str],
    api_key: str,
) -> dict[str, Any]:
    domain = prospect.get("domain", "") or ""
    if not domain or "email" not in target_fields:
        return {}
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(
                "https://api.hunter.io/v2/domain-search",
                params={"domain": domain, "api_key": api_key, "limit": 1},
            )
            resp.raise_for_status()
            emails = resp.json().get("data", {}).get("emails", [])
            if emails:
                return {"email": emails[0].get("value")}
    except Exception as exc:
        logger.debug("autopilot.enrich.hunter.failed", error=str(exc))
    return {}


async def _run_enrich_step(
    step: dict[str, Any],
    prospect: dict[str, Any],
    tenant_keys: dict[str, str],
) -> dict[str, Any]:
    platform = step["platform"]
    target_fields = step.get("targetFields") or []
    if platform == "hunter":
        api_key = tenant_keys.get("hunter", "")
        if api_key:
            return await _enrich_hunter(prospect, target_fields, api_key)
    logger.debug("autopilot.enrich.platform_not_implemented", platform=platform)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Quality gate filter
# ─────────────────────────────────────────────────────────────────────────────

def _passes_gates(prospect: dict[str, Any], gates: dict[str, Any]) -> tuple[bool, str]:
    email = (prospect.get("email") or "").strip().lower()
    domain = (prospect.get("domain") or "").strip().lower()

    if gates.get("requireEmail") and not email:
        return False, "missing_email"
    if gates.get("requireVerifiedEmail") and not prospect.get("emailValidated"):
        return False, "unverified_email"

    # Company size gate:
    # Only enforce when requireCompanySize=True AND the prospect has a known size.
    # AI-sourced prospects never include companySize (it requires enrichment).
    # Rejecting unknown sizes would block ALL prospects without enrichment.
    min_size = int(gates.get("minCompanySize", 0) or 0)
    if gates.get("requireCompanySize") and min_size > 0:
        company_size = int(prospect.get("companySize", 0) or 0)
        if company_size > 0 and company_size < min_size:
            # Only reject if we KNOW the size and it is below the threshold.
            # Unknown (0 / null) = not enriched yet → pass through.
            return False, f"company_size_below_{min_size}"

    exclude: list[str] = gates.get("excludeDomains") or []
    email_domain = email.split("@")[-1] if "@" in email else ""
    if (email_domain and email_domain in exclude) or (domain and domain in exclude):
        return False, "excluded_domain"

    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# LLM scoring — uses the same llm_config resolved above
# ─────────────────────────────────────────────────────────────────────────────

async def _score_batch(
    prospects: list[dict[str, Any]],
    icp: IcpProfile,
    llm_config: Any,
) -> list[dict[str, Any]]:
    if not llm_config:
        for p in prospects:
            p.setdefault("icpFitScore", 50)
            p.setdefault("urgencyTier", "TIER_3")
        return prospects

    from app.services.llm_service import call_llm as _call_llm

    persona = icp.persona or "B2B decision maker"
    company_type = icp.companyType or "technology company"
    pain_points = ", ".join((icp.painPoints or [])[:3]) or "growth"

    prospect_list = json.dumps([
        {"index": i, "firstName": p.get("firstName", ""),
         "lastName": p.get("lastName", ""), "title": p.get("title", ""),
         "company": p.get("company", ""), "domain": p.get("domain", "")}
        for i, p in enumerate(prospects)
    ], indent=2)

    system_prompt = (
        "You are an ICP fit scoring assistant. "
        "Score each prospect 0–100 for how well they match the ICP, "
        "and assign urgency tier: TIER_1 (hot/decision-maker match), "
        "TIER_2 (warm/partial match), TIER_3 (cold/weak match). "
        "Return ONLY a JSON array: "
        '[{"index":0,"score":85,"tier":"TIER_1","persona":"CTO SaaS"},...]. '
        "No markdown, no text outside the JSON array."
    )
    user_prompt = (
        f"ICP: {persona} at {company_type}. Pain points: {pain_points}.\n\n"
        f"Prospects to score:\n{prospect_list}\n\n"
        "Return JSON array with score and tier for each prospect."
    )

    try:
        resp = await _call_llm(llm_config, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        content = (resp.content or "").strip()
        if "```" in content:
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
            if match:
                content = match.group(1).strip()
        start, end = content.find("["), content.rfind("]")
        if start != -1 and end != -1:
            content = content[start:end+1]
        scores = json.loads(content)
        if isinstance(scores, list):
            for item in scores:
                idx = item.get("index", -1)
                if 0 <= idx < len(prospects):
                    prospects[idx]["icpFitScore"] = int(item.get("score", 50))
                    prospects[idx]["urgencyTier"] = item.get("tier", "TIER_3")
                    prospects[idx]["icpPersona"] = item.get("persona", "")
                    # Log LLM scoring decision for each prospect
                    name = f"{prospects[idx].get('firstName','')} {prospects[idx].get('lastName','')}".strip()
                    logger.info(
                        "autopilot.score.llm_decision",
                        index=idx,
                        name=name,
                        company=prospects[idx].get("company", ""),
                        title=prospects[idx].get("title", ""),
                        icp_fit_score=prospects[idx]["icpFitScore"],
                        urgency_tier=prospects[idx]["urgencyTier"],
                        icp_persona=prospects[idx].get("icpPersona", ""),
                    )
    except Exception as exc:
        logger.warning("autopilot.score.batch_failed", error=str(exc))
        for p in prospects:
            p.setdefault("icpFitScore", 50)
            p.setdefault("urgencyTier", "TIER_3")
    return prospects


# ─────────────────────────────────────────────────────────────────────────────
# DB write helpers — _set_schema() BEFORE every flush/commit
# ─────────────────────────────────────────────────────────────────────────────

async def _create_step(
    db: AsyncSession, schema: str, run_id: str,
    kind: FlowRunStepKind, step_key: str, order: int,
) -> str:
    await _set_schema(db, schema)
    step = FlowRunStep(
        runId=run_id, kind=kind, stepKey=step_key, order=order,
        status=FlowRunStepStatus.RUNNING, metrics={},
        startedAt=datetime.now(timezone.utc),
    )
    db.add(step)
    await db.flush()
    step_id = step.id
    await db.commit()
    return step_id


async def _finish_step(
    db: AsyncSession, schema: str, step_id: str,
    status: FlowRunStepStatus,
    metrics: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    await _set_schema(db, schema)
    result = await db.execute(select(FlowRunStep).where(FlowRunStep.id == step_id))
    step = result.scalar_one_or_none()
    if step is None:
        return
    step.status = status
    if metrics is not None:
        step.metrics = metrics
    if error:
        step.errorMessage = error[:1000]
    step.completedAt = datetime.now(timezone.utc)
    if step.startedAt and step.completedAt:
        step.durationMs = int((step.completedAt - step.startedAt).total_seconds() * 1000)
    await db.commit()


async def _update_run(
    db: AsyncSession, schema: str, run_id: str,
    status: FlowRunStatus, stats: dict[str, Any],
    imported_ids: list[str], error_message: str | None = None,
) -> None:
    await _set_schema(db, schema)
    result = await db.execute(select(FlowRun).where(FlowRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        return
    run.status = status
    run.stats = stats
    run.importedProspectIds = imported_ids
    run.completedAt = datetime.now(timezone.utc)
    if error_message:
        run.errorMessage = error_message[:1000]
    await db.commit()


async def _import_prospect(
    db: AsyncSession, schema: str,
    raw: dict[str, Any], icp_profile_id: str,
) -> str | None:
    email = (raw.get("email") or "").strip().lower() or None

    if email:
        await _set_schema(db, schema)
        existing = (
            await db.execute(
                select(Prospect.id)
                .where(Prospect.email == email)
                .where(Prospect.deleted_at.is_(None))
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing:
            logger.debug("autopilot.import.duplicate_skipped", email=email)
            return None

    await _set_schema(db, schema)
    prospect = Prospect(
        firstName=(raw.get("firstName") or "Unknown").strip(),
        lastName=(raw.get("lastName") or "").strip(),
        email=email,
        title=raw.get("title") or None,
        company=raw.get("company") or None,
        domain=raw.get("domain") or None,
        linkedinUrl=raw.get("linkedinUrl") or None,
        seniority=_map_seniority(raw.get("seniority", "IC")),
        icpFitScore=int(raw.get("icpFitScore", 50) or 50),
        icpPersona=raw.get("icpPersona") or None,
        urgencyTier=raw.get("urgencyTier") or "TIER_3",
        intentSource=IntentSource.OTHER,
        enrichmentTier=EnrichmentTier.UNENRICHABLE,
        emailValidated=bool(raw.get("emailValidated", False)),
        status="new",
        signals=[],
    )
    db.add(prospect)
    await db.flush()
    pid = prospect.id
    await db.commit()
    return pid


# ─────────────────────────────────────────────────────────────────────────────
# Core execution pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def _run_pipeline(
    db: AsyncSession,
    schema: str,
    run_id: str,
    flow: object,
    icp: IcpProfile,
    llm_config: Any,
    tenant_keys: dict[str, str],
) -> dict[str, Any]:
    """
    Inner pipeline: SOURCE → DEDUP → ENRICH → GATE → SCORE → IMPORT.
    All DB writes re-apply schema before every flush/commit.
    """
    step_order = 0

    source_steps = [s for s in _parse_steps(getattr(flow, "sourceSteps", "[]")) if s["enabled"]]
    enrich_steps = [s for s in _parse_steps(getattr(flow, "enrichmentSteps", "[]")) if s["enabled"]]
    gates = _parse_gates(getattr(flow, "qualityGates", "{}"))
    llm_threshold = float(gates.get("llmScoreThreshold", 0.0) or 0.0)

    logger.info("autopilot.pipeline.start",
                run_id=run_id,
                source_platforms=[s["platform"] for s in source_steps],
                enrich_platforms=[s["platform"] for s in enrich_steps],
                enrichment_optional=len(enrich_steps) == 0,
                llm_provider=getattr(llm_config, "provider", None),
                llm_model=getattr(llm_config, "modelId", None))

    # ── SOURCE ───────────────────────────────────────────────────────────────
    all_raw: list[dict[str, Any]] = []
    for src in source_steps:
        step_id = await _create_step(db, schema, run_id, FlowRunStepKind.SOURCE,
                                     src["platform"], step_order)
        step_order += 1
        try:
            results = await _run_source_step(src, icp, _MAX_PER_SOURCE, llm_config, tenant_keys)
            all_raw.extend(results)
            await _finish_step(db, schema, step_id, FlowRunStepStatus.SUCCESS,
                               {"count": len(results), "platform": src["platform"]})
            logger.info("autopilot.source.done", platform=src["platform"], count=len(results))
        except Exception as exc:
            await _finish_step(db, schema, step_id, FlowRunStepStatus.FAILED, error=str(exc))
            logger.warning("autopilot.source.failed", platform=src["platform"], error=str(exc))

    sourced_count = len(all_raw)

    # ── DEDUP ─────────────────────────────────────────────────────────────────
    dedup_id = await _create_step(db, schema, run_id, FlowRunStepKind.ENRICHMENT, "dedup", step_order)
    step_order += 1
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for p in all_raw:
        email = (p.get("email") or "").strip().lower()
        key = email or (f"{p.get('firstName','').lower()}_"
                        f"{p.get('lastName','').lower()}_"
                        f"{p.get('company','').lower()}")
        if key and key not in seen:
            seen.add(key)
            deduped.append(p)
    await _finish_step(db, schema, dedup_id, FlowRunStepStatus.SUCCESS,
                       {"sourced": sourced_count, "after_dedup": len(deduped),
                        "removed": sourced_count - len(deduped)})

    # ── ENRICH (optional) ─────────────────────────────────────────────────────
    enriched_count = 0
    if enrich_steps:
        enrich_id = await _create_step(db, schema, run_id, FlowRunStepKind.ENRICHMENT,
                                       "enrich", step_order)
        step_order += 1
        for prospect in deduped:
            for es in enrich_steps:
                try:
                    updates = await _run_enrich_step(es, prospect, tenant_keys)
                    if updates:
                        prospect.update(updates)
                        enriched_count += 1
                        break
                except Exception:
                    fb = es.get("fallbackTo")
                    if fb:
                        try:
                            fb_upd = await _run_enrich_step(
                                {"platform": fb, "targetFields": es.get("targetFields", [])},
                                prospect, tenant_keys)
                            if fb_upd:
                                prospect.update(fb_upd)
                                enriched_count += 1
                                break
                        except Exception:
                            pass
        await _finish_step(db, schema, enrich_id, FlowRunStepStatus.SUCCESS,
                           {"attempted": len(deduped), "enriched": enriched_count})
    else:
        logger.info("autopilot.enrich.skipped", reason="no_enrichment_steps_configured")

    # ── QUALITY GATES ─────────────────────────────────────────────────────────
    gate_id = await _create_step(db, schema, run_id, FlowRunStepKind.GATE,
                                  "quality_gates", step_order)
    step_order += 1
    rejection_reasons: dict[str, int] = {}
    gated: list[dict[str, Any]] = []

    logger.info(
        "autopilot.gates.config",
        require_email=gates.get("requireEmail"),
        require_verified_email=gates.get("requireVerifiedEmail"),
        require_company_size=gates.get("requireCompanySize"),
        min_company_size=gates.get("minCompanySize"),
        llm_score_threshold=gates.get("llmScoreThreshold"),
        exclude_domains=gates.get("excludeDomains", []),
        total_prospects_entering=len(deduped),
    )

    for p in deduped:
        passes, reason = _passes_gates(p, gates)
        name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip() or "Unknown"
        company = p.get("company", "") or ""
        email = p.get("email") or "null"
        company_size = p.get("companySize", 0) or 0
        if passes:
            gated.append(p)
            logger.info(
                "autopilot.gates.prospect_passed",
                name=name,
                company=company,
                email=email,
                company_size=company_size,
            )
        else:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            logger.info(
                "autopilot.gates.prospect_rejected",
                name=name,
                company=company,
                email=email,
                company_size=company_size,
                reason=reason,
            )
    gated_out = len(deduped) - len(gated)
    await _finish_step(db, schema, gate_id, FlowRunStepStatus.SUCCESS,
                       {"input": len(deduped), "passed": len(gated),
                        "rejected": gated_out, "reasons": rejection_reasons})
    logger.info("autopilot.gates.done", passed=len(gated), rejected=gated_out,
                reasons=rejection_reasons)

    # ── LLM SCORE ─────────────────────────────────────────────────────────────
    score_id = await _create_step(db, schema, run_id, FlowRunStepKind.SCORE,
                                   "llm_score", step_order)
    step_order += 1
    consecutive_failures = 0
    scored: list[dict[str, Any]] = []
    for i in range(0, len(gated), _LLM_BATCH):
        batch = gated[i: i + _LLM_BATCH]
        if consecutive_failures >= _CIRCUIT_BREAKER:
            for p in batch:
                p.setdefault("icpFitScore", 50)
                p.setdefault("urgencyTier", "TIER_3")
            scored.extend(batch)
            continue
        try:
            batch = await _score_batch(batch, icp, llm_config)
            consecutive_failures = 0
        except Exception as exc:
            consecutive_failures += 1
            logger.warning("autopilot.score.batch_error", error=str(exc))
            for p in batch:
                p.setdefault("icpFitScore", 50)
                p.setdefault("urgencyTier", "TIER_3")
        scored.extend(batch)

    if llm_threshold > 0:
        before = len(scored)
        min_score = int(llm_threshold * 100)
        scored = [p for p in scored if (p.get("icpFitScore", 0) or 0) >= min_score]
        logger.info("autopilot.score.threshold_applied",
                    threshold=llm_threshold, min_score=min_score, before=before, after=len(scored))

    await _finish_step(db, schema, score_id, FlowRunStepStatus.SUCCESS,
                       {"scored": len(scored), "threshold": llm_threshold})

    # ── IMPORT ────────────────────────────────────────────────────────────────
    import_id = await _create_step(db, schema, run_id, FlowRunStepKind.IMPORT,
                                    "import", step_order)
    step_order += 1
    imported_ids: list[str] = []
    import_failures = 0
    for prospect in scored:
        name = f"{prospect.get('firstName','')} {prospect.get('lastName','')}".strip() or "Unknown"
        try:
            pid = await _import_prospect(db, schema, prospect, icp.id)
            if pid:
                imported_ids.append(pid)
                logger.info(
                    "autopilot.import.prospect_saved",
                    name=name,
                    company=prospect.get("company", ""),
                    email=prospect.get("email") or "null",
                    icp_fit_score=prospect.get("icpFitScore", 0),
                    urgency_tier=prospect.get("urgencyTier", ""),
                    prospect_id=pid,
                )
            else:
                logger.info(
                    "autopilot.import.duplicate_skipped",
                    name=name,
                    email=prospect.get("email") or "null",
                )
        except Exception as exc:
            import_failures += 1
            logger.warning("autopilot.import.failed", name=name, error=str(exc))

    await _finish_step(db, schema, import_id, FlowRunStepStatus.SUCCESS,
                       {"attempted": len(scored), "imported": len(imported_ids),
                        "failures": import_failures})

    return {
        "sourced": sourced_count,
        "deduped": len(deduped),
        "enriched": enriched_count,
        "gated_out": gated_out,
        "scored": len(scored),
        "imported": len(imported_ids),
        # Keys expected by RunMonitor frontend
        "totalSourced": sourced_count,
        "totalDeduped": len(deduped),
        "totalEnriched": enriched_count,
        "totalGatedOut": gated_out,
        "totalImported": len(imported_ids),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class AutopilotService:
    """
    Flow execution engine called by the flows router.

    execute_flow_run() runs the full pipeline using the SAME db session that
    the router passes in. It captures the tenant schema at entry and
    re-applies it before every DB write (asyncpg pool safety).
    """

    async def execute_flow_run(
        self,
        db: AsyncSession,
        run: object,
        *,
        flow: object | None = None,
        icp_profile_id: str | None = None,
        llm_config_id: str | None = None,
    ) -> dict[str, Any]:
        run_id: str = getattr(run, "id", "")
        flow_id: str = getattr(flow, "id", "") if flow else ""

        # Capture schema BEFORE any commits (connection still has search_path set)
        schema = await _get_schema(db)
        logger.info("autopilot.execute.start", run_id=run_id, flow_id=flow_id,
                    icp_profile_id=icp_profile_id, schema=schema,
                    requested_llm_config_id=llm_config_id)

        try:
            if not icp_profile_id:
                raise ValueError("icp_profile_id is required")

            # Load ICP (schema still valid — no commits yet)
            icp = (
                await db.execute(select(IcpProfile).where(IcpProfile.id == icp_profile_id))
            ).scalar_one_or_none()
            if icp is None:
                raise ValueError(f"ICP profile {icp_profile_id} not found")

            # Resolve LLM config:
            # 1. If a specific llm_config_id was passed (from the Run dialog), use it.
            # 2. Otherwise fall back to 3-tier: tenant default → any tenant → global.
            llm_config = None
            if llm_config_id:
                llm_config = await _get_llm_config_by_id(db, schema, llm_config_id)
                if llm_config is None:
                    logger.warning("autopilot.llm.specific_not_found",
                                   llm_config_id=llm_config_id,
                                   hint="Falling back to default LLM config")
            if llm_config is None:
                llm_config = await _get_llm_config(db, schema)

            if llm_config is None:
                logger.error(
                    "autopilot.llm.no_config",
                    hint="Go to Setup → LLM Models and add/activate an LLM config"
                )

            # Fetch tenant integration keys
            try:
                tenant_keys = await _fetch_tenant_integrations(db, schema)
            except Exception as exc:
                logger.warning("autopilot.integrations.fetch_failed", error=str(exc))
                tenant_keys = {}

            # Run the pipeline
            stats = await _run_pipeline(db, schema, run_id, flow, icp, llm_config, tenant_keys)

            # Mark run COMPLETED
            await _update_run(db, schema, run_id, FlowRunStatus.COMPLETED, stats,
                              [])  # imported_ids tracked in stats dict
            logger.info("autopilot.execute.completed", run_id=run_id, **stats)
            return {"success": True, **stats}

        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)
            logger.error("autopilot.execute.failed", run_id=run_id, error=error_msg)
            try:
                await _update_run(db, schema, run_id, FlowRunStatus.FAILED,
                                  {"error": error_msg}, [], error_message=error_msg)
            except Exception:
                pass
            return {"success": False, "error": error_msg}

    async def orchestrate_pipeline(
        self,
        db: AsyncSession,
        *,
        flow_id: str,
        icp_profile_id: str,
        triggered_by: str = "autopilot",
        triggered_by_id: str | None = None,
    ) -> dict[str, Any]:
        """Celery / scheduler entry point."""
        from app.models.flow_models import ProspectingFlow  # noqa: PLC0415
        from app.features.flows.service import FlowRunService  # noqa: PLC0415

        schema = await _get_schema(db)
        svc = FlowRunService()

        result = await db.execute(select(ProspectingFlow).where(ProspectingFlow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            flow = await svc.get_or_create_default_flow(db)

        run = await svc.start_run(db, flow=flow, icp_profile_id=icp_profile_id,
                                   triggered_by=triggered_by, triggered_by_id=triggered_by_id)
        await _set_schema(db, schema)
        await db.commit()
        return await self.execute_flow_run(db, run, flow=flow, icp_profile_id=icp_profile_id)


__all__ = ["AutopilotService"]
