"""service_ai.py — 5 AI-powered prospect service methods.

  1. ultimate_profile  — Deep-research agent: web search + LLM → business profile
  2. lookalike         — Firmographic similarity search against existing prospects
  3. hook_generator    — Generate 5 cold-outreach opener hooks via LLM
  4. prospect_brief    — Generate 60-second prospect briefing via LLM
  5. nl_prospect_search — Parse NL query → structured filters → DB + web search

All methods are async, use SQLAlchemy select() queries, and delegate LLM calls
to ``app.services.llm_service.call_llm``. Web search uses httpx to call an
external search API (Tavily/SerpAPI-style); falls back gracefully when
unavailable.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import structlog
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_models import LlmConfig
from app.models.prospect_models import IcpProfile, Prospect
from app.schemas.llm_config import LlmResponse
from app.schemas.prospect_ai import (
    HookGeneratorResponse,
    LookalikeCandidate,
    LookalikeResponse,
    LookalikeSeed,
    NlSearchDbMatch,
    NlSearchResponse,
    NlSearchWebResult,
    ProspectBriefData,
    ProspectBriefResponse,
    UltimateProfileData,
    UltimateProfileResponse,
)
from app.services.llm_service import (
    LlmGatewayError,
    call_llm,
    get_default_llm_config,
    get_model_for_task,
)
from app.services.pii_service import PiiService

logger = structlog.get_logger(__name__)

_PII = PiiService()
_PII_FIELDS = ("firstName", "lastName", "email")

# Web-search config (env-driven; Tavily is the default provider).
_WEB_SEARCH_URL = "https://api.tavily.com/search"
_WEB_SEARCH_TIMEOUT = 15.0


class ProspectAiService:
    """AI-powered prospect intelligence service."""

    # ── Shared helpers ───────────────────────────────────────────────────────

    @staticmethod
    async def _get_llm_config(
        db: AsyncSession, llm_config_id: int | None
    ) -> LlmConfig | None:
        """Resolve an LlmConfig by ID or fall back to the tenant default."""
        if llm_config_id is not None:
            result = await db.execute(
                select(LlmConfig).where(LlmConfig.id == llm_config_id).limit(1)
            )
            return result.scalar_one_or_none()
        return await get_default_llm_config(db)

    @staticmethod
    async def _call_llm_safe(
        config: LlmConfig,
        messages: list[dict[str, str]],
        task: str = "prospect_brief",
    ) -> str:
        """Call the LLM and return content text; empty string on any failure."""
        try:
            # Tier-route the model for this task.
            model_override = get_model_for_task(task, config)
            resp: LlmResponse = await call_llm(config, messages)
            return resp.content or ""
        except (LlmGatewayError, Exception) as exc:  # noqa: BLE001
            logger.warning("prospect_ai.llm_call_failed", task=task, error=str(exc))
            return ""

    @staticmethod
    def _decrypt_pii(prospect: Prospect) -> None:
        """Decrypt PII fields on an in-memory Prospect object."""
        if getattr(prospect, "anonymized", False):
            return
        for field in _PII_FIELDS:
            value = getattr(prospect, field, None)
            if value:
                setattr(prospect, field, _PII.decrypt_field(value))

    @staticmethod
    async def _get_prospect(
        db: AsyncSession, prospect_id: str
    ) -> Prospect | None:
        """Fetch a non-deleted prospect and decrypt PII."""
        result = await db.execute(
            select(Prospect)
            .where(Prospect.id == prospect_id)
            .where(Prospect.deleted_at.is_(None))
            .limit(1)
        )
        item = result.scalar_one_or_none()
        if item is not None:
            ProspectAiService._decrypt_pii(item)
        return item

    @staticmethod
    async def _web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Call external web search API (Tavily). Returns list of result dicts.

        Each result has: title, url, content (snippet).
        Falls back to empty list on any failure (no API key, network error, etc.).
        """
        from app.core.config import get_settings

        settings = get_settings()
        api_key = getattr(settings, "TAVILY_API_KEY", "") or ""
        if not api_key:
            logger.debug("prospect_ai.web_search.skipped_no_key")
            return []
        try:
            async with httpx.AsyncClient(timeout=_WEB_SEARCH_TIMEOUT) as client:
                resp = await client.post(
                    _WEB_SEARCH_URL,
                    json={
                        "api_key": api_key,
                        "query": query,
                        "max_results": max_results,
                        "include_answer": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("results", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("prospect_ai.web_search.failed", error=str(exc))
            return []

    # ── 1. Ultimate Profile ─────────────────────────────────────────────────

    async def ultimate_profile(
        self,
        db: AsyncSession,
        prospect_id: str,
        llm_config_id: int | None = None,
    ) -> UltimateProfileResponse:
        """Deep-research agent: web search + LLM → comprehensive business profile.

        Steps:
          1. Fetch prospect by ID
          2. Web-search the company/domain for public information
          3. Synthesize results via LLM into a structured profile
          4. Persist to prospect.ultimateProfile (JSON string)
        """
        prospect = await self._get_prospect(db, prospect_id)
        if prospect is None:
            return UltimateProfileResponse(
                success=False, prospect_id=prospect_id
            )

        company = prospect.company or ""
        domain = prospect.domain or ""

        # Web search for company intelligence
        search_queries = [f"{company} company overview products"]
        if domain:
            search_queries.append(f"site:{domain} about products technology")
        web_results: list[dict[str, Any]] = []
        for q in search_queries:
            web_results.extend(await self._web_search(q, max_results=5))

        # Build LLM prompt
        sources_text = "\n".join(
            f"- [{r.get('title', '')}]({r.get('url', '')}): {r.get('content', '')[:500]}"
            for r in web_results[:10]
        )
        config = await self._get_llm_config(db, llm_config_id)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a deep-research business intelligence analyst. "
                    "Synthesize the provided web sources into a comprehensive "
                    "business profile. Return ONLY valid JSON matching this schema: "
                    '{"what_they_do": str, "products": [str], "target_market": str, '
                    '"tech_stack": [str], "company_size": str, "industry": str, '
                    '"pain_points": [str], "buying_signals": [str], "competitors": [str], '
                    '"icp_fit_score": int 0-100, "recommended_angle": str, '
                    '"confidence_score": float 0-1}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Company: {company}\nDomain: {domain}\n"
                    f"Prospect title: {prospect.title or 'N/A'}\n"
                    f"Prospect seniority: {prospect.seniority.value if prospect.seniority else 'N/A'}\n\n"
                    f"Web sources:\n{sources_text or 'No web sources available.'}\n\n"
                    "Generate the business profile JSON."
                ),
            },
        ]

        profile_data = UltimateProfileData()
        if config is not None:
            raw = await self._call_llm_safe(config, messages, task="ultimate_profile")
            if raw:
                try:
                    parsed = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
                    profile_data = UltimateProfileData(**{k: v for k, v in parsed.items() if k in UltimateProfileData.model_fields})
                except (json.JSONDecodeError, ValueError, TypeError) as exc:
                    logger.warning("prospect_ai.ultimate_profile.parse_failed", error=str(exc))

        # Persist to prospect.ultimateProfile
        try:
            prospect.ultimateProfile = json.dumps(profile_data.model_dump())
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("prospect_ai.ultimate_profile.persist_failed", error=str(exc))

        return UltimateProfileResponse(
            success=True,
            prospect_id=prospect_id,
            company=company,
            sources_analyzed=len(web_results),
            profile=profile_data,
        )

    # ── 2. Lookalike ────────────────────────────────────────────────────────

    async def lookalike(
        self,
        db: AsyncSession,
        seed_prospect_id: str | None = None,
        seed_company_domain: str | None = None,
        limit: int = 20,
    ) -> LookalikeResponse:
        """Find prospects similar to a seed by firmographic features.

        Matching features: industry (derived from company name), company,
        seniority, domain similarity. Scored by feature overlap count.
        """
        # Resolve seed prospect
        seed: Prospect | None = None
        if seed_prospect_id:
            seed = await self._get_prospect(db, seed_prospect_id)
        if seed is None and seed_company_domain:
            result = await db.execute(
                select(Prospect)
                .where(Prospect.domain == seed_company_domain)
                .where(Prospect.deleted_at.is_(None))
                .limit(1)
            )
            seed = result.scalar_one_or_none()
            if seed:
                self._decrypt_pii(seed)
        if seed is None:
            # Fallback: find a prospect from a won deal (status='won')
            result = await db.execute(
                select(Prospect)
                .where(Prospect.status == "won")
                .where(Prospect.deleted_at.is_(None))
                .order_by(Prospect.createdAt.desc())
                .limit(1)
            )
            seed = result.scalar_one_or_none()
            if seed:
                self._decrypt_pii(seed)

        if seed is None:
            return LookalikeResponse(success=False)

        seed_summary = LookalikeSeed(
            id=seed.id,
            name=f"{seed.firstName} {seed.lastName}".strip(),
            title=seed.title,
            company=seed.company,
            domain=seed.domain,
            seniority=seed.seniority.value if seed.seniority else None,
        )

        # Build OR conditions for candidate matching
        conditions = []
        if seed.company:
            conditions.append(Prospect.company.ilike(f"%{seed.company[:20]}%"))
        if seed.domain:
            # Match same top-level domain
            tld = seed.domain.split(".")[-1] if "." in seed.domain else ""
            if tld:
                conditions.append(Prospect.domain.ilike(f"%.{tld}"))
        if seed.seniority:
            conditions.append(Prospect.seniority == seed.seniority)

        if not conditions:
            return LookalikeResponse(success=True, seed=seed_summary, count=0)

        # Query candidates (exclude the seed itself, non-deleted)
        stmt = (
            select(Prospect)
            .where(Prospect.id != seed.id)
            .where(Prospect.deleted_at.is_(None))
            .where(or_(*conditions))
            .limit(limit * 3)  # over-fetch, then score + trim
        )
        result = await db.execute(stmt)
        candidates = list(result.scalars().all())

        # Score candidates by feature overlap
        scored: list[tuple[float, list[str], Prospect]] = []
        for c in candidates:
            self._decrypt_pii(c)
            score = 0.0
            matched: list[str] = []

            # Company similarity
            if seed.company and c.company and (
                seed.company.lower()[:15] in c.company.lower()
                or c.company.lower()[:15] in seed.company.lower()
            ):
                score += 0.3
                matched.append("company")

            # Same seniority
            if seed.seniority and c.seniority and seed.seniority == c.seniority:
                score += 0.25
                matched.append("seniority")

            # Same TLD / domain similarity
            if seed.domain and c.domain:
                seed_tld = seed.domain.split(".")[-1]
                c_tld = c.domain.split(".")[-1]
                if seed_tld == c_tld:
                    score += 0.15
                    matched.append("domain_tld")
                if seed.domain == c.domain:
                    score += 0.2
                    matched.append("domain_exact")

            # Title similarity (same level)
            if seed.title and c.title:
                seed_words = set(seed.title.lower().split())
                c_words = set(c.title.lower().split())
                overlap = seed_words & c_words
                if overlap:
                    title_sim = len(overlap) / max(len(seed_words), 1)
                    score += title_sim * 0.1
                    matched.append("title_overlap")

            if score > 0:
                scored.append((score, matched, c))

        # Sort by score desc, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        lookalikes = [
            LookalikeCandidate(
                id=c.id,
                first_name=c.firstName,
                last_name=c.lastName,
                title=c.title,
                company=c.company,
                domain=c.domain,
                email=c.email,
                similarity_score=round(s, 3),
                matched_features=m,
            )
            for s, m, c in top
        ]

        return LookalikeResponse(
            success=True,
            seed=seed_summary,
            lookalikes=lookalikes,
            count=len(lookalikes),
        )

    # ── 3. Hook Generator ───────────────────────────────────────────────────

    async def hook_generator(
        self,
        db: AsyncSession,
        prospect_id: str,
        llm_config_id: int | None = None,
    ) -> HookGeneratorResponse:
        """Generate 5 personalized cold-outreach opener hooks for a prospect.

        Hook types: intent-based, pain-point-based, pattern-interrupt,
        social-proof, direct-ask. Falls back to deterministic hooks if LLM
        is unavailable or fails.
        """
        prospect = await self._get_prospect(db, prospect_id)
        if prospect is None:
            return HookGeneratorResponse(success=False, hooks=[], source="fallback")

        # Gather ICP context
        icp_context = ""
        if prospect.icpProfileId:
            icp_result = await db.execute(
                select(IcpProfile).where(IcpProfile.id == prospect.icpProfileId).limit(1)
            )
            icp: IcpProfile | None = icp_result.scalar_one_or_none()
            if icp:
                icp_context = (
                    f"ICP Persona: {icp.persona or ''}\n"
                    f"Pain Points: {', '.join(icp.painPoints or [])}\n"
                    f"Value Props: {', '.join(icp.valueProps or [])}\n"
                    f"Sender Role: {icp.senderRole or ''} at {icp.senderCompany or ''}\n"
                    f"Offer: {icp.senderOffer or ''}\n"
                    f"Proof Metric: {icp.proofMetric or ''}"
                )

        config = await self._get_llm_config(db, llm_config_id)

        if config is not None:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a world-class cold-outreach copywriter. "
                        "Generate exactly 5 personalized opener hooks for the "
                        "given prospect. Each hook should be 1-2 sentences. "
                        "Hook types (one each): 1) intent-based, 2) pain-point-based, "
                        "3) pattern-interrupt, 4) social-proof, 5) direct-ask. "
                        "Return ONLY a JSON array of 5 strings, no other text."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Prospect: {prospect.firstName} {prospect.lastName}\n"
                        f"Title: {prospect.title or 'N/A'}\n"
                        f"Company: {prospect.company or 'N/A'}\n"
                        f"Domain: {prospect.domain or 'N/A'}\n"
                        f"Seniority: {prospect.seniority.value if prospect.seniority else 'N/A'}\n"
                        f"ICP Fit Score: {prospect.icpFitScore or 'N/A'}\n"
                        f"{icp_context}\n\n"
                        "Generate the 5 hooks as a JSON array."
                    ),
                },
            ]

            raw = await self._call_llm_safe(config, messages, task="prospect_brief")
            if raw:
                try:
                    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    hooks = json.loads(cleaned)
                    if isinstance(hooks, list) and len(hooks) >= 1:
                        return HookGeneratorResponse(
                            success=True,
                            hooks=[str(h) for h in hooks[:5]],
                            source="llm",
                        )
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

        # Deterministic fallback hooks
        first = prospect.firstName or "there"
        company = prospect.company or "your company"
        title = prospect.title or "your role"
        fallback_hooks = [
            f"Hi {first}, I noticed {company} is growing — curious if you're exploring solutions for {title.split()[0].lower() if title else 'operations'} efficiency?",
            f"{first}, I've been hearing similar pain points from {prospect.domain or 'companies in your space'} — mind if I share how we helped a peer team cut onboarding time 40%?",
            f"Quick question {first} — is {company} still evaluating tools in this space, or has that shipped?",
            f"Hi {first}, we worked with a company facing the same {title.lower() if title else 'growth'} challenges at {company} — they saw results in 2 weeks. Worth a 10-min chat?",
            f"{first}, I'll keep this short — would a 15-minute intro call be useful, or should I send a one-pager first?",
        ]
        return HookGeneratorResponse(success=True, hooks=fallback_hooks, source="fallback")

    # ── 4. Prospect Brief ───────────────────────────────────────────────────

    async def prospect_brief(
        self,
        db: AsyncSession,
        prospect_id: str,
        llm_config_id: int | None = None,
    ) -> ProspectBriefResponse:
        """Generate a 60-second prospect briefing using LLM.

        Includes summary, key insights, recommended approach, talking points,
        and risk factors.
        """
        prospect = await self._get_prospect(db, prospect_id)
        if prospect is None:
            return ProspectBriefResponse(success=False)

        # Gather ICP + signals context
        icp_context = ""
        if prospect.icpProfileId:
            icp_result = await db.execute(
                select(IcpProfile).where(IcpProfile.id == prospect.icpProfileId).limit(1)
            )
            icp: IcpProfile | None = icp_result.scalar_one_or_none()
            if icp:
                icp_context = (
                    f"ICP Persona: {icp.persona or ''}\n"
                    f"Pain Points: {', '.join(icp.painPoints or [])}\n"
                    f"Value Props: {', '.join(icp.valueProps or [])}\n"
                    f"Sender Role: {icp.senderRole or ''}\n"
                    f"Offer: {icp.senderOffer or ''}"
                )

        # Parse signals (JSON string or list)
        signals_text = ""
        try:
            sig = prospect.signals
            if isinstance(sig, str):
                sig = json.loads(sig)
            if isinstance(sig, list) and sig:
                signals_text = "\n".join(f"- {s}" for s in sig[:10])
        except (json.JSONDecodeError, TypeError):
            pass

        # Parse ultimate profile if available
        profile_context = ""
        if prospect.ultimateProfile:
            try:
                up = json.loads(prospect.ultimateProfile)
                if isinstance(up, dict):
                    profile_context = (
                        f"What they do: {up.get('what_they_do', '')}\n"
                        f"Industry: {up.get('industry', '')}\n"
                        f"Products: {', '.join(up.get('products', []))}\n"
                        f"Tech Stack: {', '.join(up.get('tech_stack', []))}\n"
                        f"Pain Points: {', '.join(up.get('pain_points', []))}\n"
                        f"Buying Signals: {', '.join(up.get('buying_signals', []))}"
                    )
            except (json.JSONDecodeError, TypeError):
                pass

        config = await self._get_llm_config(db, llm_config_id)

        if config is not None:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a sales intelligence analyst. Generate a concise "
                        "60-second prospect briefing. Return ONLY valid JSON: "
                        '{"summary": str, "key_insights": [str], '
                        '"recommended_approach": str, "talking_points": [str], '
                        '"risk_factors": [str]}'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Prospect: {prospect.firstName} {prospect.lastName}\n"
                        f"Title: {prospect.title or 'N/A'}\n"
                        f"Company: {prospect.company or 'N/A'}\n"
                        f"Domain: {prospect.domain or 'N/A'}\n"
                        f"Seniority: {prospect.seniority.value if prospect.seniority else 'N/A'}\n"
                        f"ICP Fit Score: {prospect.icpFitScore or 'N/A'}\n"
                        f"Intent Source: {prospect.intentSource.value if prospect.intentSource else 'N/A'}\n"
                        f"Intent Strength: {prospect.intentStrength or 'N/A'}\n"
                        f"Urgency Tier: {prospect.urgencyTier or 'N/A'}\n"
                        f"Status: {prospect.status}\n\n"
                        f"{icp_context}\n\n"
                        f"Signals:\n{signals_text or 'None'}\n\n"
                        f"Ultimate Profile:\n{profile_context or 'Not available'}\n\n"
                        "Generate the briefing JSON."
                    ),
                },
            ]

            raw = await self._call_llm_safe(config, messages, task="prospect_brief")
            if raw:
                try:
                    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    parsed = json.loads(cleaned)
                    brief_data = ProspectBriefData(**{
                        k: v for k, v in parsed.items()
                        if k in ProspectBriefData.model_fields
                    })
                    return ProspectBriefResponse(success=True, brief=brief_data)
                except (json.JSONDecodeError, ValueError, TypeError) as exc:
                    logger.warning("prospect_ai.brief.parse_failed", error=str(exc))

        # Fallback brief (no LLM)
        brief_data = ProspectBriefData(
            summary=f"{prospect.firstName} {prospect.lastName} is {prospect.title or 'a professional'} at {prospect.company or 'an unknown company'}.",
            key_insights=[
                f"ICP fit score: {prospect.icpFitScore or 'N/A'}",
                f"Intent: {prospect.intentSource.value if prospect.intentSource else 'N/A'}",
            ],
            recommended_approach="Research the prospect further before outreach.",
            talking_points=["Company background", "Role and responsibilities", "Current challenges"],
            risk_factors=["Limited intelligence available"],
        )
        return ProspectBriefResponse(success=True, brief=brief_data)

    # ── 5. NL Prospect Search ───────────────────────────────────────────────

    async def nl_prospect_search(
        self,
        db: AsyncSession,
        query: str,
        llm_config_id: int | None = None,
    ) -> NlSearchResponse:
        """Parse a natural-language query into structured filters, match
        against DB prospects, and optionally web-search for new leads.

        Steps:
          1. LLM parses NL query → structured filter JSON
          2. Build SQLAlchemy query from parsed filters
          3. Execute against Prospect table
          4. Optionally web search for new matches
          5. Return combined results
        """
        config = await self._get_llm_config(db, llm_config_id)

        # Step 1: Parse NL query with LLM
        interpretation: dict[str, Any] = {}
        if config is not None:
            parse_messages = [
                {
                    "role": "system",
                    "content": (
                        "Parse the user's natural-language search query into "
                        "structured filters for a prospect database. Return ONLY "
                        "valid JSON with any of these keys: "
                        '"company" (str), "title" (str), "seniority" (str: '
                        'C_Suite|Director|IC), "domain" (str), "industry" (str), '
                        '"company_size" (str), "status" (str), "min_icp_score" (int). '
                        "Omit keys you cannot confidently infer."
                    ),
                },
                {"role": "user", "content": f'Query: "{query}"'},
            ]
            raw = await self._call_llm_safe(config, parse_messages, task="prospect_brief")
            if raw:
                try:
                    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    interpretation = json.loads(cleaned)
                    if not isinstance(interpretation, dict):
                        interpretation = {}
                except (json.JSONDecodeError, ValueError, TypeError):
                    interpretation = {}

        # If no LLM or parse failed, do simple text search
        if not interpretation:
            interpretation = {"text_search": query}

        # Step 2: Build SQLAlchemy query
        stmt = select(Prospect).where(Prospect.deleted_at.is_(None))
        conditions = []

        if interpretation.get("company"):
            conditions.append(Prospect.company.ilike(f"%{interpretation['company']}%"))
        if interpretation.get("title"):
            conditions.append(Prospect.title.ilike(f"%{interpretation['title']}%"))
        if interpretation.get("domain"):
            conditions.append(Prospect.domain.ilike(f"%{interpretation['domain']}%"))
        if interpretation.get("seniority"):
            conditions.append(Prospect.seniority == interpretation["seniority"])
        if interpretation.get("status"):
            conditions.append(Prospect.status == interpretation["status"])
        if interpretation.get("min_icp_score"):
            try:
                min_score = int(interpretation["min_icp_score"])
                conditions.append(Prospect.icpFitScore >= min_score)
            except (ValueError, TypeError):
                pass
        # Text search fallback
        if interpretation.get("text_search"):
            like = f"%{interpretation['text_search']}%"
            conditions.append(
                or_(
                    Prospect.firstName.ilike(like),
                    Prospect.lastName.ilike(like),
                    Prospect.email.ilike(like),
                    Prospect.company.ilike(like),
                    Prospect.title.ilike(like),
                )
            )

        if conditions:
            stmt = stmt.where(or_(*conditions))

        stmt = stmt.order_by(Prospect.createdAt.desc()).limit(50)

        # Step 3: Execute DB query
        result = await db.execute(stmt)
        db_prospects = list(result.scalars().all())
        for p in db_prospects:
            self._decrypt_pii(p)

        db_matches = [
            NlSearchDbMatch(
                id=p.id,
                firstName=p.firstName,
                lastName=p.lastName,
                email=p.email,
                title=p.title,
                company=p.company,
                domain=p.domain,
                seniority=p.seniority.value if p.seniority else None,
                icpFitScore=p.icpFitScore,
            )
            for p in db_prospects
        ]

        # Step 4: Web search for new leads
        web_results_raw = await self._web_search(
            f"{query} contact decision maker", max_results=5
        )
        web_results = [
            NlSearchWebResult(
                name=r.get("title", ""),
                source_url=r.get("url", ""),
                snippet=r.get("content", "")[:300],
            )
            for r in web_results_raw
        ]

        return NlSearchResponse(
            success=True,
            interpretation=interpretation,
            db_matches=db_matches,
            db_match_count=len(db_matches),
            web_results=web_results,
            web_result_count=len(web_results),
        )


__all__ = ["ProspectAiService"]
