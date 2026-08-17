# # """
# # autopilot/service.py — End-to-end autopilot pipeline orchestrator.

# # MINIMAL / BULLETPROOF VERSION — FlowRun audit trail removed entirely.

# # Two previous attempts (second-session isolation, then savepoint-wrapped
# # audit trail) both still produced the identical InFailedSQLTransactionError
# # on the IcpProfile INSERT. Rather than continue debugging the audit-trail
# # code blind, this version eliminates it completely: orchestrate_pipeline()
# # now does ONLY the four core steps (ICP → prospects → campaign → sequences)
# # and touches NOTHING else in the database before them. No
# # ProspectingFlow/FlowRun/FlowRunStep code runs at all.

# # If prospects and sequences are still 0 after this version, the failure is
# # happening somewhere even more fundamental (session setup in the router/
# # Celery task, tenant schema/search_path, or the IcpProfile table itself) —
# # and this version's logs will show that clearly, since nothing else can be
# # blamed.

# # The FlowRun audit trail (visible in the "Flow Runs" admin page) is
# # DISABLED for autopilot runs until this is confirmed working. It can be
# # re-added later as a fully separate, fire-and-forget write using its own
# # connection, opened strictly AFTER the main pipeline transaction has
# # committed — never sharing a transaction with the main pipeline again.

# # OTHER FIXES RETAINED FROM PREVIOUS ITERATIONS:
# #   - LLM config resolved via payload["_llm_cfg"] (pre-resolved by the router,
# #     no second session opened here).
# #   - IcpProfile PG_JSON columns (topObjections/painPoints/valueProps) receive
# #     Python lists directly, not json.dumps() strings.
# #   - Prospect.seniority / .intentSource always given valid enum values.
# #   - Tavily web search wired into ICP discovery and prospect sourcing
# #     (pure HTTP, no DB session involved).
# # """
# # from __future__ import annotations

# # import json
# # import uuid
# # from datetime import datetime, timezone
# # from types import SimpleNamespace
# # from typing import Any

# # import httpx
# # import structlog
# # from sqlalchemy import select
# # from sqlalchemy.ext.asyncio import AsyncSession
# # import app.models.global_llm_config  # noqa: F401 — registers mapper before Campaign resolves relationships
# # import app.models.config_models  # noqa: F401 — registers LlmConfig before Campaign resolves relationships
# # from app.models.campaign_models import Campaign, CampaignProspect, Sequence
# # from app.models.enums import (
# #     EmailStatus,
# #     EnrichmentTier,
# #     IntentSource,
# #     SeniorityTier,
# # )
# # from app.models.prospect_models import IcpProfile, Prospect
# # from app.schemas.autopilot import AutopilotRequest, AutopilotResult

# # logger = structlog.get_logger(__name__)

# # _TAVILY_URL = "https://api.tavily.com/search"
# # _WEB_SEARCH_TIMEOUT = 15.0


# # # ── Web search (pure HTTP, no DB) ───────────────────────────────────────────

# # async def _web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
# #     """Tavily web search. Returns [] on any failure (missing key, timeout, quota)."""
# #     from app.core.config import get_settings
# #     api_key: str = getattr(get_settings(), "TAVILY_API_KEY", "") or ""
# #     if not api_key:
# #         logger.debug("autopilot.web_search.no_key", query=query[:60])
# #         return []
# #     try:
# #         async with httpx.AsyncClient(timeout=_WEB_SEARCH_TIMEOUT) as client:
# #             resp = await client.post(
# #                 _TAVILY_URL,
# #                 json={
# #                     "api_key": api_key,
# #                     "query": query,
# #                     "max_results": max_results,
# #                     "include_answer": False,
# #                     "search_depth": "basic",
# #                 },
# #             )
# #             resp.raise_for_status()
# #             results = resp.json().get("results", [])
# #             logger.info("autopilot.web_search.ok", query=query[:60], n=len(results))
# #             return results
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning("autopilot.web_search.failed", query=query[:60], error=str(exc))
# #         return []


# # def _format_results(results: list[dict]) -> str:
# #     if not results:
# #         return "No web results available."
# #     lines = []
# #     for i, r in enumerate(results[:10], 1):
# #         title = r.get("title", "")
# #         url = r.get("url", "")
# #         content = (r.get("content") or r.get("snippet", ""))[:400]
# #         lines.append(f"[{i}] {title}\n    {url}\n    {content}")
# #     return "\n\n".join(lines)


# # # ── LLM call helpers (pure HTTP, no DB) ─────────────────────────────────────

# # async def _llm_text(llm_cfg: SimpleNamespace, prompt: str, max_tokens: int = 1024) -> str:
# #     try:
# #         from app.services.llm_service import call_llm
# #         response = await call_llm(llm_cfg, [{"role": "user", "content": prompt}])
# #         return response.content or ""
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning("autopilot.llm_text.failed", error=str(exc))
# #         return ""


# # async def _llm_json(llm_cfg: SimpleNamespace, prompt: str) -> dict:
# #     """Call LLM and parse JSON. Handles ```json fences and leading preamble."""
# #     raw = await _llm_text(llm_cfg, prompt, max_tokens=2048)
# #     if not raw:
# #         return {}
# #     fence_idx = raw.find("```")
# #     if fence_idx != -1:
# #         after = raw[fence_idx + 3:]
# #         nl = after.find("\n")
# #         if nl != -1:
# #             after = after[nl + 1:]
# #         closing = after.rfind("```")
# #         if closing != -1:
# #             after = after[:closing]
# #         raw = after.strip()
# #     for ch in ["{", "["]:
# #         idx = raw.find(ch)
# #         if idx != -1:
# #             raw = raw[idx:]
# #             break
# #     try:
# #         parsed = json.loads(raw)
# #         return parsed if isinstance(parsed, dict) else {}
# #     except (json.JSONDecodeError, ValueError):
# #         logger.warning("autopilot.llm_json.parse_failed", preview=raw[:200])
# #         return {}


# # # ── Step 1: ICP discovery ──────────────────────────────────────────────────

# # async def _step_icp_discovery(
# #     db: AsyncSession,
# #     llm_cfg: SimpleNamespace,
# #     payload: AutopilotRequest,
# # ) -> IcpProfile:
# #     """
# #     Discover ICP from website + LLM. This is now the FIRST database
# #     operation the entire pipeline performs — nothing runs before it.
# #     """
# #     hint = payload.icp_hint or ""

# #     website_url = ""
# #     if payload.metadata:
# #         website_url = payload.metadata.get("website_url", "")
# #     if not website_url and payload.campaign_name.startswith("Autopilot — "):
# #         website_url = payload.campaign_name.replace("Autopilot — ", "").strip()

# #     clean_site = website_url
# #     for prefix in ["https://", "http://", "www."]:
# #         clean_site = clean_site.replace(prefix, "")
# #     clean_site = clean_site.rstrip("/")

# #     if hint:
# #         existing = await db.execute(
# #             select(IcpProfile).where(IcpProfile.persona == hint).limit(1)
# #         )
# #         reused = existing.scalar_one_or_none()
# #         if reused is not None:
# #             logger.info("autopilot.icp.reused", icp_id=reused.id)
# #             return reused

# #     web_results: list[dict] = []
# #     if clean_site:
# #         for q in [
# #             f'"{clean_site}" what they do products services',
# #             f'"{clean_site}" about company target customers',
# #             f"site:{clean_site} about",
# #         ]:
# #             web_results.extend(await _web_search(q, max_results=5))
# #             if len(web_results) >= 10:
# #                 break

# #     sources_text = _format_results(web_results)

# #     if clean_site and web_results:
# #         prompt = (
# #             f"ICP analyst task. Company website: {clean_site}\n\n"
# #             f"Web research results:\n{sources_text}\n\n"
# #             "Determine what this company sells and who their ideal buyers are.\n"
# #             "Return JSON only, no preamble, no markdown:\n"
# #             '{"persona": "2-3 sentence ICP description", '
# #             '"companyType": "e.g. B2B SaaS 50-200 employees", '
# #             '"topObjections": ["obj1", "obj2", "obj3"], '
# #             '"painPoints": ["pain1", "pain2", "pain3"], '
# #             '"valueProps": ["vp1", "vp2", "vp3"]}'
# #         )
# #     else:
# #         ctx = hint or f"B2B buyers for {clean_site or 'a software product'}"
# #         prompt = (
# #             f"ICP analyst task. Expand this ICP hint:\n{ctx}\n\n"
# #             "Return JSON only, no preamble:\n"
# #             '{"persona": "2-3 sentence ICP description", '
# #             '"companyType": "str", '
# #             '"topObjections": ["obj1", "obj2", "obj3"], '
# #             '"painPoints": ["pain1", "pain2", "pain3"], '
# #             '"valueProps": ["vp1", "vp2", "vp3"]}'
# #         )

# #     profile = await _llm_json(llm_cfg, prompt)
# #     persona = profile.get("persona") or hint or f"Buyers at {clean_site or 'target companies'}"

# #     def _as_list(v: Any) -> list:
# #         if isinstance(v, list):
# #             return v
# #         if isinstance(v, str) and v:
# #             return [v]
# #         return []

# #     icp = IcpProfile(
# #         name=f"Autopilot ICP — {payload.campaign_name}",
# #         persona=persona,
# #         companyType=profile.get("companyType"),
# #         topObjections=_as_list(profile.get("topObjections")),
# #         painPoints=_as_list(profile.get("painPoints")),
# #         valueProps=_as_list(profile.get("valueProps")),
# #         senderRole=payload.sender_role,
# #         senderCompany=payload.sender_company,
# #         senderOffer=payload.sender_offer,
# #         proofMetric=payload.proof_metric,
# #     )
# #     db.add(icp)
# #     await db.flush()
# #     logger.info("autopilot.icp.created", icp_id=icp.id, persona=persona[:80])
# #     return icp


# # # ── Step 2: Prospect sourcing ──────────────────────────────────────────────

# # async def _step_prospect_sourcing(
# #     db: AsyncSession,
# #     llm_cfg: SimpleNamespace,
# #     payload: AutopilotRequest,
# #     icp: IcpProfile,
# # ) -> list[Prospect]:
# #     target_count = max(1, min(payload.target_count, 500))

# #     website_url = ""
# #     if payload.metadata:
# #         website_url = payload.metadata.get("website_url", "")
# #     clean_site = website_url
# #     for prefix in ["https://", "http://", "www."]:
# #         clean_site = clean_site.replace(prefix, "")
# #     clean_site = clean_site.rstrip("/")

# #     persona_text = icp.persona or "B2B decision makers"
# #     company_type = icp.companyType or "B2B companies"

# #     web_results: list[dict] = []
# #     queries = [f"site:linkedin.com/in {persona_text[:80]}"]
# #     if clean_site:
# #         queries.append(f'"{clean_site}" customers clients decision makers')
# #     queries.append(f"{company_type} VP Director executive contact")

# #     for q in queries[:3]:
# #         web_results.extend(await _web_search(q, max_results=5))

# #     if web_results:
# #         prompt = (
# #             f"Extract {target_count} B2B prospect leads from these web results.\n\n"
# #             f"Results:\n{_format_results(web_results)}\n\n"
# #             f"Target ICP: {persona_text}\n"
# #             "Extract real people where found. Fill remaining with realistic "
# #             f"synthetic prospects matching the ICP.\n"
# #             f'Return JSON only: {{"prospects": [{{"firstName": "str", '
# #             f'"lastName": "str", "email": "first.last@company.com", '
# #             f'"title": "str", "company": "str", "domain": "company.com", '
# #             f'"seniority": "C_Suite|Director|IC"}}]}}'
# #         )
# #     else:
# #         logger.info("autopilot.sourcing.llm_only")
# #         prompt = (
# #             f"Generate {target_count} realistic B2B prospect records.\n"
# #             f"ICP: {persona_text}\nCompany type: {company_type}\n"
# #             f'Return JSON only: {{"prospects": [{{"firstName": "str", '
# #             f'"lastName": "str", "email": "first.last@company.com", '
# #             f'"title": "str", "company": "str", "domain": "company.com", '
# #             f'"seniority": "C_Suite|Director|IC"}}]}}'
# #         )

# #     sourcing = await _llm_json(llm_cfg, prompt)
# #     prospect_dicts = sourcing.get("prospects", [])

# #     if not prospect_dicts:
# #         logger.warning("autopilot.sourcing.fallback", count=target_count)
# #         prospect_dicts = [
# #             {
# #                 "firstName": "Alex", "lastName": f"Smith{i}",
# #                 "email": f"alex.smith{i}@acmecorp{i}.com",
# #                 "title": "VP of Sales", "company": f"AcmeCorp {i}",
# #                 "domain": f"acmecorp{i}.com", "seniority": "Director",
# #             }
# #             for i in range(target_count)
# #         ]

# #     seniority_map = {
# #         "c_suite": SeniorityTier.C_Suite, "c-suite": SeniorityTier.C_Suite,
# #         "csuite": SeniorityTier.C_Suite, "director": SeniorityTier.Director,
# #         "ic": SeniorityTier.IC,
# #     }

# #     prospects: list[Prospect] = []
# #     for p in prospect_dicts[:target_count]:
# #         seniority = seniority_map.get(str(p.get("seniority", "IC")).lower(), SeniorityTier.IC)
# #         prospect = Prospect(
# #             firstName=p.get("firstName") or "Unknown",
# #             lastName=p.get("lastName") or "Prospect",
# #             email=p.get("email") or None,
# #             title=p.get("title") or None,
# #             company=p.get("company") or None,
# #             domain=p.get("domain") or None,
# #             timezone=p.get("timezone") or "America/New_York",
# #             enrichmentTier=EnrichmentTier.PARTIAL,
# #             icpProfileId=icp.id,
# #             icpPersona=icp.persona[:200] if icp.persona else None,
# #             status="new",
# #             seniority=seniority,
# #             intentSource=IntentSource.OTHER,
# #         )
# #         db.add(prospect)
# #         prospects.append(prospect)

# #     await db.flush()
# #     logger.info("autopilot.sourcing.done", count=len(prospects), web=bool(web_results))
# #     return prospects


# # # ── Step 3: Campaign creation ──────────────────────────────────────────────

# # async def _step_campaign_creation(
# #     db: AsyncSession,
# #     payload: AutopilotRequest,
# #     icp: IcpProfile,
# # ) -> Campaign:
# #     campaign = Campaign(
# #         name=payload.campaign_name,
# #         description=f"Autopilot-generated campaign — ICP: {icp.name}",
# #         status="active",
# #         framework=payload.framework or "AIDA",
# #         senderRole=payload.sender_role,
# #         senderCompany=payload.sender_company,
# #         senderOffer=payload.sender_offer,
# #         proofMetric=payload.proof_metric,
# #         senderProduct=payload.sender_product,
# #         targetAudience=payload.target_audience or (icp.persona[:500] if icp.persona else None),
# #         icpProfileId=icp.id,
# #         complianceFooter=True,
# #     )
# #     db.add(campaign)
# #     await db.flush()
# #     logger.info("autopilot.campaign.created", campaign_id=campaign.id)
# #     return campaign


# # # ── Step 4: Email generation ───────────────────────────────────────────────

# # async def _step_email_generation(
# #     db: AsyncSession,
# #     llm_cfg: SimpleNamespace,
# #     payload: AutopilotRequest,
# #     icp: IcpProfile,
# #     campaign: Campaign,
# #     prospects: list[Prospect],
# # ) -> list[Sequence]:
# #     from app.schemas.sequences import SEVEN_TOUCH_CADENCE

# #     sequences: list[Sequence] = []
# #     sender_ctx = (
# #         f"Sender: {payload.sender_role or 'sales rep'} at "
# #         f"{payload.sender_company or 'our company'}. "
# #         f"Offer: {payload.sender_offer or 'our product'}."
# #     )
# #     icp_text = (icp.persona or "B2B decision makers")[:300]

# #     for prospect in prospects:
# #         db.add(CampaignProspect(
# #             campaignId=campaign.id,
# #             prospectId=prospect.id,
# #             status="pending",
# #         ))
# #         recipient = (
# #             f"{prospect.firstName} {prospect.lastName}, "
# #             f"{prospect.title or 'executive'} at {prospect.company or 'their company'}"
# #         )
# #         for touch in SEVEN_TOUCH_CADENCE:
# #             angle, framework, send_day = touch.angle, touch.defaultFramework, touch.sendDay
# #             try:
# #                 subject = (await _llm_text(
# #                     llm_cfg,
# #                     f"Cold email subject line (max 60 chars). Touch {touch.touchNumber}, "
# #                     f"angle {angle.value}, framework {framework}. Recipient: {recipient}. "
# #                     f"{sender_ctx} ICP: {icp_text}. Return ONLY the subject line.",
# #                     max_tokens=80,
# #                 )).strip() or f"Touch {touch.touchNumber}: {angle.value}"
# #             except Exception:  # noqa: BLE001
# #                 subject = f"Touch {touch.touchNumber}: {angle.value}"

# #             try:
# #                 body = (await _llm_text(
# #                     llm_cfg,
# #                     f"Cold email body (max 150 words). Touch {touch.touchNumber}, "
# #                     f"angle {angle.value}, framework {framework}. Recipient: {recipient}. "
# #                     f"{sender_ctx} ICP: {icp_text}. "
# #                     "Consultative tone, no hype. Sign off with sender first name only.",
# #                     max_tokens=400,
# #                 )).strip()
# #                 if not body:
# #                     raise ValueError("empty")
# #             except Exception:  # noqa: BLE001
# #                 body = (
# #                     f"Hi {prospect.firstName},\n\nTouch {touch.touchNumber} — "
# #                     f"{angle.value}.\n\n{sender_ctx}\n\nBest,\n"
# #                     f"{payload.sender_role or 'Sales'}"
# #                 )

# #             seq = Sequence(
# #                 campaignId=campaign.id,
# #                 prospectId=prospect.id,
# #                 touchNumber=touch.touchNumber,
# #                 sendDay=send_day,
# #                 channel="email",
# #                 angle=angle,
# #                 framework=framework,
# #                 subjectLine=subject[:500],
# #                 bodyCopy=body,
# #                 status=EmailStatus.Scheduled,
# #             )
# #             db.add(seq)
# #             sequences.append(seq)

# #     await db.flush()
# #     logger.info("autopilot.emails.generated", count=len(sequences))
# #     return sequences


# # # ── Top-level orchestrator ─────────────────────────────────────────────────

# # async def orchestrate_pipeline(
# #     db: AsyncSession,
# #     payload: dict[str, Any],
# # ) -> AutopilotResult:
# #     """
# #     Run the full autopilot pipeline. ONLY these four steps touch the
# #     database. Nothing else runs before Step 1 — no flow/audit-trail setup,
# #     no secondary sessions, nothing.
# #     """
# #     started_at = datetime.now(timezone.utc)
# #     task_id = payload.get("task_id") or str(uuid.uuid4())
# #     request = AutopilotRequest.model_validate(payload)

# #     llm_cfg_dict = payload.get("_llm_cfg") or {}
# #     if not llm_cfg_dict:
# #         return AutopilotResult(
# #             campaign_id="", prospect_count=0, sequence_count=0,
# #             task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
# #             error="LLM config not provided to orchestrator (router bug).",
# #             started_at=started_at, completed_at=datetime.now(timezone.utc),
# #         )
# #     llm_cfg = SimpleNamespace(**llm_cfg_dict)

# #     logger.info(
# #         "autopilot.pipeline.start",
# #         task_id=task_id,
# #         provider=llm_cfg.provider,
# #         model=llm_cfg.model,
# #         campaign=request.campaign_name,
# #     )

# #     # DIAGNOSTIC: prove the session is usable and see its search_path
# #     # BEFORE any pipeline logic runs. If THIS fails, the session was
# #     # already broken by whatever set it up in the router/Celery task —
# #     # not by anything in this file.
# #     try:
# #         from sqlalchemy import text
# #         diag = await db.execute(text("SHOW search_path"))
# #         logger.info("autopilot.diag.search_path", search_path=diag.scalar())
# #     except Exception as exc:  # noqa: BLE001
# #         logger.error(
# #             "autopilot.diag.session_already_broken",
# #             error=str(exc), exc_info=True,
# #         )
# #         return AutopilotResult(
# #             campaign_id="", prospect_count=0, sequence_count=0,
# #             task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
# #             error=(
# #                 "Session was already in a broken state before the pipeline "
# #                 f"started (search_path diagnostic failed): {exc}"
# #             ),
# #             started_at=started_at, completed_at=datetime.now(timezone.utc),
# #         )

# #     error: str | None = None
# #     icp: IcpProfile | None = None
# #     campaign: Campaign | None = None
# #     prospects: list[Prospect] = []
# #     sequences: list[Sequence] = []
# #     status: str = "SUCCESS"

# #     # ── Step 1: ICP discovery ────────────────────────────────────────────
# #     # This is the FIRST database statement the entire pipeline runs.
# #     try:
# #         icp = await _step_icp_discovery(db, llm_cfg, request)
# #     except Exception as exc:  # noqa: BLE001
# #         error = f"ICP discovery failed: {exc}"
# #         logger.error("autopilot.icp_failed", error=str(exc), exc_info=True)
# #         try:
# #             await db.rollback()
# #         except Exception:  # noqa: BLE001
# #             pass
# #         return AutopilotResult(
# #             campaign_id="", prospect_count=0, sequence_count=0,
# #             task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
# #             error=error, started_at=started_at,
# #             completed_at=datetime.now(timezone.utc),
# #         )

# #     # ── Step 2: Prospect sourcing ────────────────────────────────────────
# #     try:
# #         prospects = await _step_prospect_sourcing(db, llm_cfg, request, icp)
# #     except Exception as exc:  # noqa: BLE001
# #         error = f"Prospect sourcing failed: {exc}"
# #         logger.error("autopilot.sourcing_failed", error=str(exc), exc_info=True)
# #         status = "PARTIAL"
# #         try:
# #             await db.rollback()
# #         except Exception:  # noqa: BLE001
# #             pass
# #         return AutopilotResult(
# #             campaign_id="", prospect_count=0, sequence_count=0,
# #             task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
# #             error=error, started_at=started_at,
# #             completed_at=datetime.now(timezone.utc),
# #         )

# #     # ── Step 3: Campaign creation ────────────────────────────────────────
# #     try:
# #         campaign = await _step_campaign_creation(db, request, icp)
# #     except Exception as exc:  # noqa: BLE001
# #         error = f"Campaign creation failed: {exc}"
# #         logger.error("autopilot.campaign_failed", error=str(exc), exc_info=True)
# #         try:
# #             await db.rollback()
# #         except Exception:  # noqa: BLE001
# #             pass
# #         return AutopilotResult(
# #             campaign_id="", prospect_count=len(prospects), sequence_count=0,
# #             task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
# #             error=error, started_at=started_at,
# #             completed_at=datetime.now(timezone.utc),
# #         )

# #     # ── Step 4: Email generation ─────────────────────────────────────────
# #     sequence_count = 0
# #     if prospects:
# #         try:
# #             sequences = await _step_email_generation(db, llm_cfg, request, icp, campaign, prospects)
# #             sequence_count = len(sequences)
# #         except Exception as exc:  # noqa: BLE001
# #             error = f"Email generation failed: {exc}"
# #             logger.error("autopilot.email_failed", error=str(exc), exc_info=True)
# #             status = "PARTIAL"
# #             try:
# #                 await db.rollback()
# #             except Exception:  # noqa: BLE001
# #                 pass
# #     else:
# #         status = "PARTIAL"
# #         error = "No prospects sourced — campaign created with no sequences"

# #     try:
# #         await db.flush()
# #     except Exception as exc:  # noqa: BLE001
# #         error = f"Persist failed: {exc}"
# #         status = "FAILURE"
# #         try:
# #             await db.rollback()
# #         except Exception:  # noqa: BLE001
# #             pass

# #     logger.info(
# #         "autopilot.pipeline.done",
# #         task_id=task_id, status=status,
# #         prospects=len(prospects), sequences=sequence_count,
# #     )

# #     try:
# #         resolved_campaign_id = campaign.id if campaign else ""
# #     except Exception:  # noqa: BLE001
# #         resolved_campaign_id = ""

# #     return AutopilotResult(
# #         campaign_id=resolved_campaign_id,
# #         prospect_count=len(prospects),
# #         sequence_count=sequence_count,
# #         task_id=task_id,
# #         status=status,  # type: ignore[arg-type]
# #         error=error,
# #         started_at=started_at,
# #         completed_at=datetime.now(timezone.utc),
# #     )


# # __all__ = ["orchestrate_pipeline"]
# """
# autopilot/service.py — End-to-end autopilot pipeline orchestrator.

# MINIMAL / BULLETPROOF VERSION — FlowRun audit trail removed entirely.

# Two previous attempts (second-session isolation, then savepoint-wrapped
# audit trail) both still produced the identical InFailedSQLTransactionError
# on the IcpProfile INSERT. Rather than continue debugging the audit-trail
# code blind, this version eliminates it completely: orchestrate_pipeline()
# now does ONLY the four core steps (ICP → prospects → campaign → sequences)
# and touches NOTHING else in the database before them. No
# ProspectingFlow/FlowRun/FlowRunStep code runs at all.

# If prospects and sequences are still 0 after this version, the failure is
# happening somewhere even more fundamental (session setup in the router/
# Celery task, tenant schema/search_path, or the IcpProfile table itself) —
# and this version's logs will show that clearly, since nothing else can be
# blamed.

# The FlowRun audit trail (visible in the "Flow Runs" admin page) is
# DISABLED for autopilot runs until this is confirmed working. It can be
# re-added later as a fully separate, fire-and-forget write using its own
# connection, opened strictly AFTER the main pipeline transaction has
# committed — never sharing a transaction with the main pipeline again.

# OTHER FIXES RETAINED FROM PREVIOUS ITERATIONS:
#   - LLM config resolved via payload["_llm_cfg"] (pre-resolved by the router,
#     no second session opened here).
#   - IcpProfile PG_JSON columns (topObjections/painPoints/valueProps) receive
#     Python lists directly, not json.dumps() strings.
#   - Prospect.seniority / .intentSource always given valid enum values.
#   - Tavily web search wired into ICP discovery and prospect sourcing
#     (pure HTTP, no DB session involved).
# """
# from __future__ import annotations

# import asyncio
# import json
# import uuid
# from datetime import datetime, timezone
# from types import SimpleNamespace
# from typing import Any

# import httpx
# import structlog
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession
# import app.models.global_llm_config  # noqa: F401 — registers mapper before Campaign resolves relationships
# import app.models.config_models  # noqa: F401 — registers LlmConfig before Campaign resolves relationships
# from app.models.campaign_models import Campaign, CampaignProspect, Sequence
# from app.models.enums import (
#     EmailStatus,
#     EnrichmentTier,
#     IntentSource,
#     SeniorityTier,
# )
# from app.models.prospect_models import IcpProfile, Prospect
# from app.schemas.autopilot import AutopilotRequest, AutopilotResult

# logger = structlog.get_logger(__name__)

# _TAVILY_URL = "https://api.tavily.com/search"
# _WEB_SEARCH_TIMEOUT = 15.0


# # ── Web search (pure HTTP, no DB) ───────────────────────────────────────────

# async def _web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
#     """Tavily web search. Returns [] on any failure (missing key, timeout, quota)."""
#     from app.core.config import get_settings
#     api_key: str = getattr(get_settings(), "TAVILY_API_KEY", "") or ""

#     # DEBUG: print the key presence/length (never the key itself) and the
#     # exact query being sent, so you can see in `docker compose logs backend`
#     # whether Tavily is even being called with a real key.

#     if not api_key:
#         logger.debug("autopilot.web_search.no_key", query=query[:60])
#         return []
#     try:
#         async with httpx.AsyncClient(timeout=_WEB_SEARCH_TIMEOUT) as client:
#             resp = await client.post(
#                 _TAVILY_URL,
#                 json={
#                     "api_key": api_key,
#                     "query": query,
#                     "max_results": max_results,
#                     "include_answer": False,
#                     "search_depth": "basic",
#                 },
#             )
#             resp.raise_for_status()
#             body = resp.json()
#             results = body.get("results", [])

#             # DEBUG: print the FULL raw Tavily response so you can inspect
#             # exactly what came back — titles, urls, and content snippets.

#             logger.info("autopilot.web_search.ok", query=query[:60], n=len(results))
#             return results
#     except Exception as exc:  # noqa: BLE001
#         logger.warning("autopilot.web_search.failed", query=query[:60], error=str(exc))
#         return []


# def _format_results(results: list[dict]) -> str:
#     if not results:
#         return "No web results available."
#     lines = []
#     for i, r in enumerate(results[:10], 1):
#         title = r.get("title", "")
#         url = r.get("url", "")
#         content = (r.get("content") or r.get("snippet", ""))[:400]
#         lines.append(f"[{i}] {title}\n    {url}\n    {content}")
#     return "\n\n".join(lines)


# # ── LLM call helpers (pure HTTP, no DB) ─────────────────────────────────────

# async def _llm_text(llm_cfg: SimpleNamespace, prompt: str, max_tokens: int = 1024) -> str:
#     try:
#         from app.services.llm_service import call_llm
#         response = await call_llm(llm_cfg, [{"role": "user", "content": prompt}])
#         return response.content or ""
#     except Exception as exc:  # noqa: BLE001
#         logger.warning("autopilot.llm_text.failed", error=str(exc))
#         return ""


# async def _llm_json(llm_cfg: SimpleNamespace, prompt: str) -> dict:
#     """Call LLM and parse JSON. Handles ```json fences and leading preamble."""
#     raw = await _llm_text(llm_cfg, prompt, max_tokens=2048)


#     if not raw:
#         return {}
#     fence_idx = raw.find("```")
#     if fence_idx != -1:
#         after = raw[fence_idx + 3:]
#         nl = after.find("\n")
#         if nl != -1:
#             after = after[nl + 1:]
#         closing = after.rfind("```")
#         if closing != -1:
#             after = after[:closing]
#         raw = after.strip()
#     for ch in ["{", "["]:
#         idx = raw.find(ch)
#         if idx != -1:
#             raw = raw[idx:]
#             break
#     try:
#         parsed = json.loads(raw)
#         result = parsed if isinstance(parsed, dict) else {}
#         return result
#     except (json.JSONDecodeError, ValueError) as exc:
#         logger.warning("autopilot.llm_json.parse_failed", preview=raw[:200])
#         return {}


# # ── Step 1: ICP discovery ──────────────────────────────────────────────────

# async def _step_icp_discovery(
#     db: AsyncSession,
#     llm_cfg: SimpleNamespace,
#     payload: AutopilotRequest,
# ) -> IcpProfile:
#     """
#     Discover ICP from website + LLM. This is now the FIRST database
#     operation the entire pipeline performs — nothing runs before it.
#     """
#     hint = payload.icp_hint or ""

#     website_url = ""
#     if payload.metadata:
#         website_url = payload.metadata.get("website_url", "")
#     if not website_url and payload.campaign_name.startswith("Autopilot — "):
#         website_url = payload.campaign_name.replace("Autopilot — ", "").strip()

#     clean_site = website_url
#     for prefix in ["https://", "http://", "www."]:
#         clean_site = clean_site.replace(prefix, "")
#     clean_site = clean_site.rstrip("/")

#     if hint:
#         existing = await db.execute(
#             select(IcpProfile).where(IcpProfile.persona == hint).limit(1)
#         )
#         reused = existing.scalar_one_or_none()
#         if reused is not None:
#             logger.info("autopilot.icp.reused", icp_id=reused.id)
#             return reused

#     web_results: list[dict] = []
#     if clean_site:
#         for q in [
#             f'"{clean_site}" what they do products services',
#             f'"{clean_site}" about company target customers',
#             f"site:{clean_site} about",
#         ]:
#             web_results.extend(await _web_search(q, max_results=5))
#             if len(web_results) >= 10:
#                 break

#     sources_text = _format_results(web_results)

#     if clean_site and web_results:
#         prompt = (
#             f"ICP analyst task. Company website: {clean_site}\n\n"
#             f"Web research results:\n{sources_text}\n\n"
#             "Determine what this company sells and who their ideal buyers are.\n"
#             "Return JSON only, no preamble, no markdown:\n"
#             '{"persona": "2-3 sentence ICP description", '
#             '"companyType": "e.g. B2B SaaS 50-200 employees", '
#             '"topObjections": ["obj1", "obj2", "obj3"], '
#             '"painPoints": ["pain1", "pain2", "pain3"], '
#             '"valueProps": ["vp1", "vp2", "vp3"]}'
#         )
#     else:
#         ctx = hint or f"B2B buyers for {clean_site or 'a software product'}"
#         prompt = (
#             f"ICP analyst task. Expand this ICP hint:\n{ctx}\n\n"
#             "Return JSON only, no preamble:\n"
#             '{"persona": "2-3 sentence ICP description", '
#             '"companyType": "str", '
#             '"topObjections": ["obj1", "obj2", "obj3"], '
#             '"painPoints": ["pain1", "pain2", "pain3"], '
#             '"valueProps": ["vp1", "vp2", "vp3"]}'
#         )

#     profile = await _llm_json(llm_cfg, prompt)
#     persona = profile.get("persona") or hint or f"Buyers at {clean_site or 'target companies'}"

#     def _as_list(v: Any) -> list:
#         if isinstance(v, list):
#             return v
#         if isinstance(v, str) and v:
#             return [v]
#         return []

#     icp = IcpProfile(
#         name=f"Autopilot ICP — {payload.campaign_name}",
#         persona=persona,
#         companyType=profile.get("companyType"),
#         topObjections=_as_list(profile.get("topObjections")),
#         painPoints=_as_list(profile.get("painPoints")),
#         valueProps=_as_list(profile.get("valueProps")),
#         senderRole=payload.sender_role,
#         senderCompany=payload.sender_company,
#         senderOffer=payload.sender_offer,
#         proofMetric=payload.proof_metric,
#     )
#     db.add(icp)
#     await db.flush()
#     logger.info("autopilot.icp.created", icp_id=icp.id, persona=persona[:80])
#     return icp


# # ── Step 2: Prospect sourcing ──────────────────────────────────────────────

# async def _step_prospect_sourcing(
#     db: AsyncSession,
#     llm_cfg: SimpleNamespace,
#     payload: AutopilotRequest,
#     icp: IcpProfile,
# ) -> list[Prospect]:
#     target_count = max(1, min(payload.target_count, 500))

#     website_url = ""
#     if payload.metadata:
#         website_url = payload.metadata.get("website_url", "")
#     clean_site = website_url
#     for prefix in ["https://", "http://", "www."]:
#         clean_site = clean_site.replace(prefix, "")
#     clean_site = clean_site.rstrip("/")

#     persona_text = icp.persona or "B2B decision makers"
#     company_type = icp.companyType or "B2B companies"

#     web_results: list[dict] = []
#     queries = [f"site:linkedin.com/in {persona_text[:80]}"]
#     if clean_site:
#         queries.append(f'"{clean_site}" customers clients decision makers')
#     queries.append(f"{company_type} VP Director executive contact")

#     for q in queries[:3]:
#         web_results.extend(await _web_search(q, max_results=5))


#     if web_results:
#         prompt = (
#             f"Extract {target_count} B2B prospect leads from these web results.\n\n"
#             f"Results:\n{_format_results(web_results)}\n\n"
#             f"Target ICP: {persona_text}\n"
#             "Extract real people where found. Fill remaining with realistic "
#             f"synthetic prospects matching the ICP.\n"
#             f'Return JSON only: {{"prospects": [{{"firstName": "str", '
#             f'"lastName": "str", "email": "first.last@company.com", '
#             f'"title": "str", "company": "str", "domain": "company.com", '
#             f'"seniority": "C_Suite|Director|IC"}}]}}'
#         )
#     else:
#         logger.info("autopilot.sourcing.llm_only")
#         prompt = (
#             f"Generate {target_count} realistic B2B prospect records.\n"
#             f"ICP: {persona_text}\nCompany type: {company_type}\n"
#             f'Return JSON only: {{"prospects": [{{"firstName": "str", '
#             f'"lastName": "str", "email": "first.last@company.com", '
#             f'"title": "str", "company": "str", "domain": "company.com", '
#             f'"seniority": "C_Suite|Director|IC"}}]}}'
#         )

#     sourcing = await _llm_json(llm_cfg, prompt)
#     prospect_dicts = sourcing.get("prospects", [])


#     if not prospect_dicts:
#         logger.warning("autopilot.sourcing.fallback", count=target_count)
#         prospect_dicts = [
#             {
#                 "firstName": "Alex", "lastName": f"Smith{i}",
#                 "email": f"alex.smith{i}@acmecorp{i}.com",
#                 "title": "VP of Sales", "company": f"AcmeCorp {i}",
#                 "domain": f"acmecorp{i}.com", "seniority": "Director",
#             }
#             for i in range(target_count)
#         ]

#     seniority_map = {
#         "c_suite": SeniorityTier.C_Suite, "c-suite": SeniorityTier.C_Suite,
#         "csuite": SeniorityTier.C_Suite, "director": SeniorityTier.Director,
#         "ic": SeniorityTier.IC,
#     }

#     prospects: list[Prospect] = []
#     for p in prospect_dicts[:target_count]:
#         seniority = seniority_map.get(str(p.get("seniority", "IC")).lower(), SeniorityTier.IC)
#         prospect = Prospect(
#             firstName=p.get("firstName") or "Unknown",
#             lastName=p.get("lastName") or "Prospect",
#             email=p.get("email") or None,
#             title=p.get("title") or None,
#             company=p.get("company") or None,
#             domain=p.get("domain") or None,
#             timezone=p.get("timezone") or "America/New_York",
#             enrichmentTier=EnrichmentTier.PARTIAL,
#             icpProfileId=icp.id,
#             icpPersona=icp.persona[:200] if icp.persona else None,
#             status="new",
#             seniority=seniority,
#             intentSource=IntentSource.OTHER,
#         )
#         db.add(prospect)
#         prospects.append(prospect)

#     await db.flush()
#     logger.info("autopilot.sourcing.done", count=len(prospects), web=bool(web_results))
#     return prospects


# # ── Step 3: Campaign creation ──────────────────────────────────────────────

# async def _step_campaign_creation(
#     db: AsyncSession,
#     payload: AutopilotRequest,
#     icp: IcpProfile,
# ) -> Campaign:
#     campaign = Campaign(
#         name=payload.campaign_name,
#         description=f"Autopilot-generated campaign — ICP: {icp.name}",
#         status="active",
#         framework=payload.framework or "AIDA",
#         senderRole=payload.sender_role,
#         senderCompany=payload.sender_company,
#         senderOffer=payload.sender_offer,
#         proofMetric=payload.proof_metric,
#         senderProduct=payload.sender_product,
#         targetAudience=payload.target_audience or (icp.persona[:500] if icp.persona else None),
#         icpProfileId=icp.id,
#         complianceFooter=True,
#     )
#     db.add(campaign)
#     await db.flush()
#     logger.info("autopilot.campaign.created", campaign_id=campaign.id)
#     return campaign


# # ── Step 4: Email generation ───────────────────────────────────────────────

# async def _step_email_generation(
#     db: AsyncSession,
#     llm_cfg: SimpleNamespace,
#     payload: AutopilotRequest,
#     icp: IcpProfile,
#     campaign: Campaign,
#     prospects: list[Prospect],
#     on_touch_done=None,
# ) -> list[Sequence]:
#     """
#     Generate the 7-touch cadence for each prospect.

#     CALL-VOLUME FIX: subject and body are now generated in ONE combined
#     LLM call per touch (was two) — halves total call count for this step
#     from 7*N*2 to 7*N*1. Combined with the ICP + sourcing calls, a
#     10-prospect run now makes ~72 total LLM calls instead of ~142.

#     RATE-LIMIT PACING FIX: a small delay between touches spreads calls out
#     over time instead of firing them back-to-back, reducing how often the
#     provider's rate limit (e.g. Groq's per-minute cap) gets hit. Every 429
#     the provider returns forces call_llm()'s own internal retry-with-backoff
#     to kick in (up to 3 retries per call per its docstring), which is what
#     was making the pipeline look "stuck" for minutes at a time — it wasn't
#     stuck, it was quietly retrying through repeated rate-limit rejections.
#     """
#     from app.schemas.sequences import SEVEN_TOUCH_CADENCE

#     sequences: list[Sequence] = []
#     sender_ctx = (
#         f"Sender: {payload.sender_role or 'sales rep'} at "
#         f"{payload.sender_company or 'our company'}. "
#         f"Offer: {payload.sender_offer or 'our product'}."
#     )
#     icp_text = (icp.persona or "B2B decision makers")[:300]

#     total_touches = len(prospects) * len(SEVEN_TOUCH_CADENCE)
#     done_touches = 0

#     for prospect in prospects:
#         db.add(CampaignProspect(
#             campaignId=campaign.id,
#             prospectId=prospect.id,
#             status="pending",
#         ))
#         recipient = (
#             f"{prospect.firstName} {prospect.lastName}, "
#             f"{prospect.title or 'executive'} at {prospect.company or 'their company'}"
#         )
#         for touch in SEVEN_TOUCH_CADENCE:
#             angle, framework, send_day = touch.angle, touch.defaultFramework, touch.sendDay

#             prompt = (
#                 f"Write a cold email for touch {touch.touchNumber} of a 7-touch "
#                 f"cadence. Angle: {angle.value}. Framework: {framework}. "
#                 f"Recipient: {recipient}. {sender_ctx} ICP: {icp_text}. "
#                 "Consultative tone, no hype, no exclamation marks. Sign off "
#                 "with the sender's first name only.\n"
#                 'Return JSON only, no preamble, no markdown: '
#                 '{"subject": "max 60 chars, no quotes", "body": "max 150 words"}'
#             )
#             try:
#                 result = await _llm_json(llm_cfg, prompt)
#                 subject = (result.get("subject") or "").strip()
#                 body = (result.get("body") or "").strip()
#                 if not subject:
#                     raise ValueError("empty subject")
#                 if not body:
#                     raise ValueError("empty body")
#             except Exception:  # noqa: BLE001
#                 subject = f"Touch {touch.touchNumber}: {angle.value}"
#                 body = (
#                     f"Hi {prospect.firstName},\n\nTouch {touch.touchNumber} — "
#                     f"{angle.value}.\n\n{sender_ctx}\n\nBest,\n"
#                     f"{payload.sender_role or 'Sales'}"
#                 )

#             seq = Sequence(
#                 campaignId=campaign.id,
#                 prospectId=prospect.id,
#                 touchNumber=touch.touchNumber,
#                 sendDay=send_day,
#                 channel="email",
#                 angle=angle,
#                 framework=framework,
#                 subjectLine=subject[:500],
#                 bodyCopy=body,
#                 status=EmailStatus.Scheduled,
#             )
#             db.add(seq)
#             sequences.append(seq)

#             done_touches += 1
#             if on_touch_done is not None:
#                 try:
#                     on_touch_done(done_touches, total_touches)
#                 except Exception:  # noqa: BLE001
#                     pass

#             # PACING FIX: small delay between touches to avoid bursting
#             # straight into the provider's per-minute rate limit.
#             await asyncio.sleep(0.4)

#     await db.flush()
#     logger.info("autopilot.emails.generated", count=len(sequences))
#     return sequences


# # ── Top-level orchestrator ─────────────────────────────────────────────────

# async def orchestrate_pipeline(
#     db: AsyncSession,
#     payload: dict[str, Any],
#     on_progress=None,
# ) -> AutopilotResult:
#     """
#     Run the full autopilot pipeline. ONLY these four steps touch the
#     database. Nothing else runs before Step 1 — no flow/audit-trail setup,
#     no secondary sessions, nothing.

#     on_progress, if given, is called as on_progress(step: int, detail: str)
#     after each major milestone (0=starting, 1=ICP done, 2=sourcing done,
#     3=campaign done, 4=email generation in progress, 5=fully done). The
#     caller (router.py) uses this to update a shared progress dict that
#     GET /autopilot/{task_id} reads, so the frontend can show real progress
#     instead of sitting at 0% for the whole run.
#     """
#     def _report(step: int, detail: str = "") -> None:
#         if on_progress is not None:
#             try:
#                 on_progress(step, detail)
#             except Exception:  # noqa: BLE001
#                 pass

#     _report(0, "Starting pipeline")
#     started_at = datetime.now(timezone.utc)
#     task_id = payload.get("task_id") or str(uuid.uuid4())
#     request = AutopilotRequest.model_validate(payload)

#     llm_cfg_dict = payload.get("_llm_cfg") or {}
#     if not llm_cfg_dict:
#         return AutopilotResult(
#             campaign_id="", prospect_count=0, sequence_count=0,
#             task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
#             error="LLM config not provided to orchestrator (router bug).",
#             started_at=started_at, completed_at=datetime.now(timezone.utc),
#         )
#     llm_cfg = SimpleNamespace(**llm_cfg_dict)

#     logger.info(
#         "autopilot.pipeline.start",
#         task_id=task_id,
#         provider=llm_cfg.provider,
#         model=llm_cfg.modelId,   # FIX: was llm_cfg.model — attribute renamed to modelId
#         campaign=request.campaign_name,
#     )

#     # DIAGNOSTIC: prove the session is usable and see its search_path
#     # BEFORE any pipeline logic runs. If THIS fails, the session was
#     # already broken by whatever set it up in the router/Celery task —
#     # not by anything in this file.
#     try:
#         from sqlalchemy import text
#         diag = await db.execute(text("SHOW search_path"))
#         logger.info("autopilot.diag.search_path", search_path=diag.scalar())
#     except Exception as exc:  # noqa: BLE001
#         logger.error(
#             "autopilot.diag.session_already_broken",
#             error=str(exc), exc_info=True,
#         )
#         return AutopilotResult(
#             campaign_id="", prospect_count=0, sequence_count=0,
#             task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
#             error=(
#                 "Session was already in a broken state before the pipeline "
#                 f"started (search_path diagnostic failed): {exc}"
#             ),
#             started_at=started_at, completed_at=datetime.now(timezone.utc),
#         )

#     error: str | None = None
#     icp: IcpProfile | None = None
#     campaign: Campaign | None = None
#     prospects: list[Prospect] = []
#     sequences: list[Sequence] = []
#     status: str = "SUCCESS"

#     # ── Step 1: ICP discovery ────────────────────────────────────────────
#     # This is the FIRST database statement the entire pipeline runs.
#     try:
#         icp = await _step_icp_discovery(db, llm_cfg, request)
#         _report(1, "ICP analysis complete")
#     except Exception as exc:  # noqa: BLE001
#         error = f"ICP discovery failed: {exc}"
#         logger.error("autopilot.icp_failed", error=str(exc), exc_info=True)
#         try:
#             await db.rollback()
#         except Exception:  # noqa: BLE001
#             pass
#         return AutopilotResult(
#             campaign_id="", prospect_count=0, sequence_count=0,
#             task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
#             error=error, started_at=started_at,
#             completed_at=datetime.now(timezone.utc),
#         )

#     # ── Step 2: Prospect sourcing ────────────────────────────────────────
#     try:
#         prospects = await _step_prospect_sourcing(db, llm_cfg, request, icp)
#         _report(2, f"Sourced {len(prospects)} prospects")
#     except Exception as exc:  # noqa: BLE001
#         error = f"Prospect sourcing failed: {exc}"
#         logger.error("autopilot.sourcing_failed", error=str(exc), exc_info=True)
#         status = "PARTIAL"
#         try:
#             await db.rollback()
#         except Exception:  # noqa: BLE001
#             pass
#         return AutopilotResult(
#             campaign_id="", prospect_count=0, sequence_count=0,
#             task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
#             error=error, started_at=started_at,
#             completed_at=datetime.now(timezone.utc),
#         )

#     # ── Step 3: Campaign creation ────────────────────────────────────────
#     try:
#         campaign = await _step_campaign_creation(db, request, icp)
#         _report(3, f"Campaign '{campaign.name}' created")
#     except Exception as exc:  # noqa: BLE001
#         error = f"Campaign creation failed: {exc}"
#         logger.error("autopilot.campaign_failed", error=str(exc), exc_info=True)
#         try:
#             await db.rollback()
#         except Exception:  # noqa: BLE001
#             pass
#         return AutopilotResult(
#             campaign_id="", prospect_count=len(prospects), sequence_count=0,
#             task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
#             error=error, started_at=started_at,
#             completed_at=datetime.now(timezone.utc),
#         )

#     # ── Step 4: Email generation ─────────────────────────────────────────
#     sequence_count = 0
#     if prospects:
#         try:
#             def _touch_progress(done: int, total: int) -> None:
#                 _report(4, f"Writing emails: {done}/{total} touches")

#             sequences = await _step_email_generation(
#                 db, llm_cfg, request, icp, campaign, prospects,
#                 on_touch_done=_touch_progress,
#             )
#             sequence_count = len(sequences)
#             _report(5, f"Complete — {sequence_count} sequences generated")
#         except Exception as exc:  # noqa: BLE001
#             error = f"Email generation failed: {exc}"
#             logger.error("autopilot.email_failed", error=str(exc), exc_info=True)
#             status = "PARTIAL"
#             try:
#                 await db.rollback()
#             except Exception:  # noqa: BLE001
#                 pass
#     else:
#         status = "PARTIAL"
#         error = "No prospects sourced — campaign created with no sequences"

#     try:
#         await db.flush()
#     except Exception as exc:  # noqa: BLE001
#         error = f"Persist failed: {exc}"
#         status = "FAILURE"
#         try:
#             await db.rollback()
#         except Exception:  # noqa: BLE001
#             pass

#     logger.info(
#         "autopilot.pipeline.done",
#         task_id=task_id, status=status,
#         prospects=len(prospects), sequences=sequence_count,
#     )

#     try:
#         resolved_campaign_id = campaign.id if campaign else ""
#     except Exception:  # noqa: BLE001
#         resolved_campaign_id = ""

#     return AutopilotResult(
#         campaign_id=resolved_campaign_id,
#         prospect_count=len(prospects),
#         sequence_count=sequence_count,
#         task_id=task_id,
#         status=status,  # type: ignore[arg-type]
#         error=error,
#         started_at=started_at,
#         completed_at=datetime.now(timezone.utc),
#     )


# __all__ = ["orchestrate_pipeline"]

"""
autopilot/service.py — End-to-end autopilot pipeline orchestrator.

MINIMAL / BULLETPROOF VERSION — FlowRun audit trail removed entirely.

Two previous attempts (second-session isolation, then savepoint-wrapped
audit trail) both still produced the identical InFailedSQLTransactionError
on the IcpProfile INSERT. Rather than continue debugging the audit-trail
code blind, this version eliminates it completely: orchestrate_pipeline()
now does ONLY the four core steps (ICP → prospects → campaign → sequences)
and touches NOTHING else in the database before them. No
ProspectingFlow/FlowRun/FlowRunStep code runs at all.

If prospects and sequences are still 0 after this version, the failure is
happening somewhere even more fundamental (session setup in the router/
Celery task, tenant schema/search_path, or the IcpProfile table itself) —
and this version's logs will show that clearly, since nothing else can be
blamed.

The FlowRun audit trail (visible in the "Flow Runs" admin page) is
DISABLED for autopilot runs until this is confirmed working. It can be
re-added later as a fully separate, fire-and-forget write using its own
connection, opened strictly AFTER the main pipeline transaction has
committed — never sharing a transaction with the main pipeline again.

OTHER FIXES RETAINED FROM PREVIOUS ITERATIONS:
  - LLM config resolved via payload["_llm_cfg"] (pre-resolved by the router,
    no second session opened here).
  - IcpProfile PG_JSON columns (topObjections/painPoints/valueProps) receive
    Python lists directly, not json.dumps() strings.
  - Prospect.seniority / .intentSource always given valid enum values.
  - Tavily web search wired into ICP discovery and prospect sourcing
    (pure HTTP, no DB session involved).
"""
from __future__ import annotations

import asyncio
import time
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import app.models.global_llm_config  # noqa: F401 — registers mapper before Campaign resolves relationships
import app.models.config_models  # noqa: F401 — registers LlmConfig before Campaign resolves relationships
from app.models.campaign_models import Campaign, CampaignProspect, Sequence
from app.models.enums import (
    EmailStatus,
    EnrichmentTier,
    IntentSource,
    SeniorityTier,
)
from app.models.prospect_models import IcpProfile, Prospect
from app.schemas.autopilot import AutopilotRequest, AutopilotResult

logger = structlog.get_logger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"
_WEB_SEARCH_TIMEOUT = 15.0


# ── Web search (pure HTTP, no DB) ───────────────────────────────────────────

async def _web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Tavily web search. Returns [] on any failure (missing key, timeout, quota)."""
    from app.core.config import get_settings
    api_key: str = getattr(get_settings(), "TAVILY_API_KEY", "") or ""

    # DEBUG: print the key presence/length (never the key itself) and the
    # exact query being sent, so you can see in `docker compose logs backend`
    # whether Tavily is even being called with a real key.

    if not api_key:
        logger.debug("autopilot.web_search.no_key", query=query[:60])
        return []
    try:
        async with httpx.AsyncClient(timeout=_WEB_SEARCH_TIMEOUT) as client:
            resp = await client.post(
                _TAVILY_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": False,
                    "search_depth": "basic",
                },
            )
            resp.raise_for_status()
            body = resp.json()
            results = body.get("results", [])

            # DEBUG: print the FULL raw Tavily response so you can inspect
            # exactly what came back — titles, urls, and content snippets.

            logger.info("autopilot.web_search.ok", query=query[:60], n=len(results))
            return results
    except Exception as exc:  # noqa: BLE001
        logger.warning("autopilot.web_search.failed", query=query[:60], error=str(exc))
        return []


def _format_results(results: list[dict]) -> str:
    if not results:
        return "No web results available."
    lines = []
    for i, r in enumerate(results[:10], 1):
        title = r.get("title", "")
        url = r.get("url", "")
        content = (r.get("content") or r.get("snippet", ""))[:400]
        lines.append(f"[{i}] {title}\n    {url}\n    {content}")
    return "\n\n".join(lines)


# ── LLM call helpers (pure HTTP, no DB) ─────────────────────────────────────

# HARD TIMEOUT FIX: call_llm()'s own retry logic (in llm_service.py) is
# bounded — 3 attempts, exponential backoff capped at 10s between attempts,
# 60s HTTP timeout per attempt — so in theory it cannot hang forever. But
# that still allows a single call to legitimately take several minutes in
# the worst case (60s timeout x 3 attempts + backoff), and any unexpected
# edge case in that shared framework code (used by many other features,
# not something we should modify) could behave differently than documented.
# This wrapper adds our OWN hard ceiling at the call site: no single LLM
# call in the autopilot pipeline is allowed to block forward progress for
# more than _LLM_CALL_TIMEOUT seconds, full stop. If it's still running
# past that, we abandon waiting on it (asyncio.wait_for cancels the
# underlying coroutine) and move on with the fallback stub — guaranteeing
# the pipeline always finishes in bounded time, touch by touch.
_LLM_CALL_TIMEOUT = 45.0


async def _llm_text(llm_cfg: SimpleNamespace, prompt: str, max_tokens: int = 1024) -> str:
    try:
        from app.services.llm_service import call_llm
        response = await asyncio.wait_for(
            call_llm(llm_cfg, [{"role": "user", "content": prompt}]),
            timeout=_LLM_CALL_TIMEOUT,
        )
        return response.content or ""
    except asyncio.TimeoutError:
        logger.warning(
            "autopilot.llm_text.timed_out",
            timeout_seconds=_LLM_CALL_TIMEOUT,
            prompt_preview=prompt[:120],
        )
        return ""
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "autopilot.llm_text.failed",
            error_type=type(exc).__name__,
            error=str(exc),
            prompt_preview=prompt[:120],
        )
        return ""


async def _llm_json(llm_cfg: SimpleNamespace, prompt: str) -> dict:
    """Call LLM and parse JSON. Handles ```json fences and leading preamble."""
    raw = await _llm_text(llm_cfg, prompt, max_tokens=2048)


    if not raw:
        return {}
    fence_idx = raw.find("```")
    if fence_idx != -1:
        after = raw[fence_idx + 3:]
        nl = after.find("\n")
        if nl != -1:
            after = after[nl + 1:]
        closing = after.rfind("```")
        if closing != -1:
            after = after[:closing]
        raw = after.strip()
    for ch in ["{", "["]:
        idx = raw.find(ch)
        if idx != -1:
            raw = raw[idx:]
            break
    try:
        parsed = json.loads(raw)
        result = parsed if isinstance(parsed, dict) else {}
        return result
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("autopilot.llm_json.parse_failed", preview=raw[:200])
        return {}


# ── Step 1: ICP discovery ──────────────────────────────────────────────────

async def _step_icp_discovery(
    db: AsyncSession,
    llm_cfg: SimpleNamespace,
    payload: AutopilotRequest,
) -> tuple[IcpProfile, list[IcpProfile], dict, list[dict]]:
    """
    Discover ICP from website + LLM. This is now the FIRST database
    operation the entire pipeline performs — nothing runs before it.

    RICH UI FIX: previously created exactly one generic IcpProfile row.
    Now asks the LLM for a real company analysis (what they do, industry,
    offer) plus 3-4 distinct buyer personas, each with its own fit score.
    One IcpProfile row is created per persona (matching the completion
    screen's "N ICP Profiles created" — each individually viewable on the
    ICP Profiles page). The single highest-fit persona is still used as
    the "primary" ICP for prospect sourcing / campaign / email generation,
    so all downstream behavior is unchanged.

    Returns (primary_icp, all_icp_profiles, company_analysis, personas_meta).
    `personas_meta` carries {name, description, fitScore, icpProfileId} for
    each persona — used only for the completion screen, never persisted as
    a new DB column (IcpProfile has no fitScore field; adding one would
    need a migration, so this stays in-memory / in the AutopilotResult).
    """
    hint = payload.icp_hint or ""

    website_url = ""
    if payload.metadata:
        website_url = payload.metadata.get("website_url", "")
    if not website_url and payload.campaign_name.startswith("Autopilot — "):
        website_url = payload.campaign_name.replace("Autopilot — ", "").strip()

    clean_site = website_url
    for prefix in ["https://", "http://", "www."]:
        clean_site = clean_site.replace(prefix, "")
    clean_site = clean_site.rstrip("/")

    if hint:
        existing = await db.execute(
            select(IcpProfile).where(IcpProfile.persona == hint).limit(1)
        )
        reused = existing.scalar_one_or_none()
        if reused is not None:
            logger.info("autopilot.icp.reused", icp_id=reused.id)
            return reused, [reused], {}, []

    web_results: list[dict] = []
    if clean_site:
        for q in [
            f'"{clean_site}" what they do products services',
            f'"{clean_site}" about company target customers',
            f"site:{clean_site} about",
        ]:
            web_results.extend(await _web_search(q, max_results=5))
            if len(web_results) >= 10:
                break

    sources_text = _format_results(web_results)

    if clean_site and web_results:
        prompt = (
            f"ICP analyst task. Company website: {clean_site}\n\n"
            f"Web research results:\n{sources_text}\n\n"
            "Determine what this company sells and identify 3-4 DISTINCT "
            "ideal buyer personas for it (different roles/segments, not "
            "variations of the same persona).\n"
            "Return JSON only, no preamble, no markdown:\n"
            '{"companyAnalysis": {"whatTheyDo": "1 sentence", '
            '"industry": "short label", "offer": "1 sentence"}, '
            '"personas": [{"name": "short persona title e.g. Mid-Market '
            'Business Owners", "description": "2-3 sentence persona '
            'description", "fitScore": 85, "companyType": "e.g. B2B SaaS '
            '50-200 employees", "topObjections": ["obj1", "obj2", "obj3"], '
            '"painPoints": ["pain1", "pain2", "pain3"], '
            '"valueProps": ["vp1", "vp2", "vp3"]}]}'
        )
    else:
        ctx = hint or f"B2B buyers for {clean_site or 'a software product'}"
        prompt = (
            f"ICP analyst task. Expand this ICP hint into 3-4 DISTINCT "
            f"buyer personas:\n{ctx}\n\n"
            "Return JSON only, no preamble:\n"
            '{"companyAnalysis": {"whatTheyDo": "1 sentence", '
            '"industry": "short label", "offer": "1 sentence"}, '
            '"personas": [{"name": "short persona title", '
            '"description": "2-3 sentence persona description", '
            '"fitScore": 85, "companyType": "str", '
            '"topObjections": ["obj1", "obj2", "obj3"], '
            '"painPoints": ["pain1", "pain2", "pain3"], '
            '"valueProps": ["vp1", "vp2", "vp3"]}]}'
        )

    profile = await _llm_json(llm_cfg, prompt)
    company_analysis = profile.get("companyAnalysis") or {}
    if not isinstance(company_analysis, dict):
        company_analysis = {}

    def _as_list(v: Any) -> list:
        if isinstance(v, list):
            return v
        if isinstance(v, str) and v:
            return [v]
        return []

    raw_personas = profile.get("personas")
    if not isinstance(raw_personas, list) or not raw_personas:
        # LLM failed / returned nothing usable — one generic persona,
        # same behavior as before this change.
        fallback_persona = hint or f"Buyers at {clean_site or 'target companies'}"
        raw_personas = [{
            "name": "General Buyer",
            "description": fallback_persona,
            "fitScore": 50,
            "companyType": None,
            "topObjections": [],
            "painPoints": [],
            "valueProps": [],
        }]

    all_icp_profiles: list[IcpProfile] = []
    personas_meta: list[dict] = []

    for i, p in enumerate(raw_personas[:4]):  # cap at 4 personas per run
        if not isinstance(p, dict):
            continue
        persona_name = str(p.get("name") or f"Persona {i + 1}")
        persona_desc = str(p.get("description") or hint or "")
        try:
            fit_score = int(p.get("fitScore", 50))
        except (TypeError, ValueError):
            fit_score = 50
        fit_score = max(0, min(100, fit_score))

        icp = IcpProfile(
            name=f"{persona_name} — {payload.campaign_name}",
            persona=persona_desc,
            companyType=p.get("companyType"),
            topObjections=_as_list(p.get("topObjections")),
            painPoints=_as_list(p.get("painPoints")),
            valueProps=_as_list(p.get("valueProps")),
            senderRole=payload.sender_role,
            senderCompany=payload.sender_company,
            senderOffer=payload.sender_offer,
            proofMetric=payload.proof_metric,
        )
        db.add(icp)
        all_icp_profiles.append(icp)

        personas_meta.append({
            "name": persona_name,
            "description": persona_desc,
            "fitScore": fit_score,
            "_sort_key": fit_score,
        })

    await db.flush()  # populate .id on every created IcpProfile

    # Attach the real DB id now that flush has assigned one.
    for icp, meta in zip(all_icp_profiles, personas_meta):
        meta["icpProfileId"] = icp.id
        del meta["_sort_key"]

    # Highest-fit persona drives prospect sourcing / campaign / emails —
    # all downstream behavior is unchanged from before this feature.
    best_idx = max(
        range(len(all_icp_profiles)),
        key=lambda idx: personas_meta[idx]["fitScore"],
    )
    primary_icp = all_icp_profiles[best_idx]

    logger.info(
        "autopilot.icp.created",
        icp_id=primary_icp.id,
        persona_count=len(all_icp_profiles),
        primary_persona=personas_meta[best_idx]["name"],
    )
    return primary_icp, all_icp_profiles, company_analysis, personas_meta


# ── Step 2: Prospect sourcing ──────────────────────────────────────────────

async def _step_prospect_sourcing(
    db: AsyncSession,
    llm_cfg: SimpleNamespace,
    payload: AutopilotRequest,
    icp: IcpProfile,
) -> list[Prospect]:
    target_count = max(1, min(payload.target_count, 500))

    website_url = ""
    if payload.metadata:
        website_url = payload.metadata.get("website_url", "")
    clean_site = website_url
    for prefix in ["https://", "http://", "www."]:
        clean_site = clean_site.replace(prefix, "")
    clean_site = clean_site.rstrip("/")

    persona_text = icp.persona or "B2B decision makers"
    company_type = icp.companyType or "B2B companies"

    web_results: list[dict] = []
    queries = [f"site:linkedin.com/in {persona_text[:80]}"]
    if clean_site:
        queries.append(f'"{clean_site}" customers clients decision makers')
    queries.append(f"{company_type} VP Director executive contact")

    for q in queries[:3]:
        web_results.extend(await _web_search(q, max_results=5))


    if web_results:
        prompt = (
            f"Extract {target_count} B2B prospect leads from these web results.\n\n"
            f"Results:\n{_format_results(web_results)}\n\n"
            f"Target ICP: {persona_text}\n"
            "Extract real people where found. Fill remaining with realistic "
            f"synthetic prospects matching the ICP.\n"
            f'Return JSON only: {{"prospects": [{{"firstName": "str", '
            f'"lastName": "str", "email": "first.last@company.com", '
            f'"title": "str", "company": "str", "domain": "company.com", '
            f'"seniority": "C_Suite|Director|IC"}}]}}'
        )
    else:
        logger.info("autopilot.sourcing.llm_only")
        prompt = (
            f"Generate {target_count} realistic B2B prospect records.\n"
            f"ICP: {persona_text}\nCompany type: {company_type}\n"
            f'Return JSON only: {{"prospects": [{{"firstName": "str", '
            f'"lastName": "str", "email": "first.last@company.com", '
            f'"title": "str", "company": "str", "domain": "company.com", '
            f'"seniority": "C_Suite|Director|IC"}}]}}'
        )

    sourcing = await _llm_json(llm_cfg, prompt)
    prospect_dicts = sourcing.get("prospects", [])


    if not prospect_dicts:
        logger.warning("autopilot.sourcing.fallback", count=target_count)
        prospect_dicts = [
            {
                "firstName": "Alex", "lastName": f"Smith{i}",
                "email": f"alex.smith{i}@acmecorp{i}.com",
                "title": "VP of Sales", "company": f"AcmeCorp {i}",
                "domain": f"acmecorp{i}.com", "seniority": "Director",
            }
            for i in range(target_count)
        ]

    seniority_map = {
        "c_suite": SeniorityTier.C_Suite, "c-suite": SeniorityTier.C_Suite,
        "csuite": SeniorityTier.C_Suite, "director": SeniorityTier.Director,
        "ic": SeniorityTier.IC,
    }

    prospects: list[Prospect] = []
    for p in prospect_dicts[:target_count]:
        seniority = seniority_map.get(str(p.get("seniority", "IC")).lower(), SeniorityTier.IC)
        prospect = Prospect(
            firstName=p.get("firstName") or "Unknown",
            lastName=p.get("lastName") or "Prospect",
            email=p.get("email") or None,
            title=p.get("title") or None,
            company=p.get("company") or None,
            domain=p.get("domain") or None,
            timezone=p.get("timezone") or "America/New_York",
            enrichmentTier=EnrichmentTier.PARTIAL,
            icpProfileId=icp.id,
            icpPersona=icp.persona[:200] if icp.persona else None,
            status="new",
            seniority=seniority,
            intentSource=IntentSource.OTHER,
        )
        db.add(prospect)
        prospects.append(prospect)

    await db.flush()
    logger.info("autopilot.sourcing.done", count=len(prospects), web=bool(web_results))
    return prospects


# ── Step 3: Campaign creation ──────────────────────────────────────────────

async def _step_campaign_creation(
    db: AsyncSession,
    payload: AutopilotRequest,
    icp: IcpProfile,
) -> Campaign:
    campaign = Campaign(
        name=payload.campaign_name,
        description=f"Autopilot-generated campaign — ICP: {icp.name}",
        status="active",
        framework=payload.framework or "AIDA",
        senderRole=payload.sender_role,
        senderCompany=payload.sender_company,
        senderOffer=payload.sender_offer,
        proofMetric=payload.proof_metric,
        senderProduct=payload.sender_product,
        targetAudience=payload.target_audience or (icp.persona[:500] if icp.persona else None),
        icpProfileId=icp.id,
        complianceFooter=True,
    )
    db.add(campaign)
    await db.flush()
    logger.info("autopilot.campaign.created", campaign_id=campaign.id)
    return campaign


# ── Step 4: Email generation ───────────────────────────────────────────────

async def _step_email_generation(
    db: AsyncSession,
    llm_cfg: SimpleNamespace,
    payload: AutopilotRequest,
    icp: IcpProfile,
    campaign: Campaign,
    prospects: list[Prospect],
    on_touch_done=None,
) -> list[Sequence]:
    """
    Generate the 7-touch cadence for each prospect.

    CALL-VOLUME FIX: subject and body are now generated in ONE combined
    LLM call per touch (was two) — halves total call count for this step
    from 7*N*2 to 7*N*1. Combined with the ICP + sourcing calls, a
    10-prospect run now makes ~72 total LLM calls instead of ~142.

    RATE-LIMIT PACING FIX: a small delay between touches spreads calls out
    over time instead of firing them back-to-back, reducing how often the
    provider's rate limit (e.g. Groq's per-minute cap) gets hit.

    CIRCUIT BREAKER FIX: pacing alone doesn't help when the provider's
    entire QUOTA is exhausted (daily/monthly cap), as opposed to a
    momentary per-minute burst limit — in that case EVERY call fails with
    429, no matter how slowly they're sent, until the quota resets. Without
    a breaker, a 70-touch run in that state still burns through all 70
    touches, each waiting out the full ~3-4s retry/backoff cycle before
    falling back — over 4 minutes spent to produce nothing but templated
    fallback text anyway. After `_CIRCUIT_BREAKER_THRESHOLD` consecutive
    failures, we stop calling the (evidently dead) API entirely and go
    straight to the fallback template for every remaining touch — the
    run still completes with full data, just in seconds instead of minutes.
    """
    from app.schemas.sequences import SEVEN_TOUCH_CADENCE

    sequences: list[Sequence] = []
    sender_ctx = (
        f"Sender: {payload.sender_role or 'sales rep'} at "
        f"{payload.sender_company or 'our company'}. "
        f"Offer: {payload.sender_offer or 'our product'}."
    )
    icp_text = (icp.persona or "B2B decision makers")[:300]

    total_touches = len(prospects) * len(SEVEN_TOUCH_CADENCE)
    done_touches = 0

    # CIRCUIT BREAKER state
    _CIRCUIT_BREAKER_THRESHOLD = 5
    consecutive_failures = 0
    circuit_open = False  # once True, we stop calling the LLM for the rest of this run

    for prospect in prospects:
        db.add(CampaignProspect(
            campaignId=campaign.id,
            prospectId=prospect.id,
            status="pending",
        ))
        recipient = (
            f"{prospect.firstName} {prospect.lastName}, "
            f"{prospect.title or 'executive'} at {prospect.company or 'their company'}"
        )
        for touch in SEVEN_TOUCH_CADENCE:
            angle, framework, send_day = touch.angle, touch.defaultFramework, touch.sendDay

            # CIRCUIT BREAKER: once tripped, skip the LLM call entirely for
            # every remaining touch — go straight to the fallback template.
            # No network call, no wait, no point retrying a provider that
            # has failed `_CIRCUIT_BREAKER_THRESHOLD` times in a row.
            if circuit_open:
                subject = f"Touch {touch.touchNumber}: {angle.value}"
                body = (
                    f"Hi {prospect.firstName},\n\nTouch {touch.touchNumber} — "
                    f"{angle.value}.\n\n{sender_ctx}\n\nBest,\n"
                    f"{payload.sender_role or 'Sales'}"
                )
                touch_ok = False
                elapsed = 0.0
            else:
                prompt = (
                    f"Write a cold email for touch {touch.touchNumber} of a 7-touch "
                    f"cadence. Angle: {angle.value}. Framework: {framework}. "
                    f"Recipient: {recipient}. {sender_ctx} ICP: {icp_text}. "
                    "Consultative tone, no hype, no exclamation marks. Sign off "
                    "with the sender's first name only.\n"
                    'Return JSON only, no preamble, no markdown: '
                    '{"subject": "max 60 chars, no quotes", "body": "max 150 words"}'
                )

                # DIAGNOSTIC: time every touch individually. If any single
                # touch takes unusually long, this is logged loudly so a
                # future stall is immediately traceable to a specific
                # prospect/touch instead of showing up only as "it's slow"
                # with no further detail.
                touch_started = datetime.now(timezone.utc)
                try:
                    result = await _llm_json(llm_cfg, prompt)
                    subject = (result.get("subject") or "").strip()
                    body = (result.get("body") or "").strip()
                    if not subject:
                        raise ValueError("empty subject")
                    if not body:
                        raise ValueError("empty body")
                    touch_ok = True
                except Exception as exc:  # noqa: BLE001
                    subject = f"Touch {touch.touchNumber}: {angle.value}"
                    body = (
                        f"Hi {prospect.firstName},\n\nTouch {touch.touchNumber} — "
                        f"{angle.value}.\n\n{sender_ctx}\n\nBest,\n"
                        f"{payload.sender_role or 'Sales'}"
                    )
                    touch_ok = False
                    logger.warning(
                        "autopilot.email.touch_fallback",
                        prospect_id=prospect.id,
                        touch_number=touch.touchNumber,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )

                elapsed = (datetime.now(timezone.utc) - touch_started).total_seconds()

                # Update circuit breaker state based on this attempt.
                if touch_ok:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD:
                        circuit_open = True
                        remaining = total_touches - done_touches - 1
                        logger.warning(
                            "autopilot.email.circuit_breaker_tripped",
                            consecutive_failures=consecutive_failures,
                            remaining_touches_using_fallback=remaining,
                            reason=(
                                "LLM provider failed "
                                f"{consecutive_failures} times in a row — "
                                "likely quota exhausted, not a momentary "
                                "rate-limit burst. Skipping real LLM calls "
                                "for the rest of this run; remaining "
                                "sequences will use templated fallback text."
                            ),
                        )

            if elapsed > 10.0:
                # This touch took notably longer than expected (single LLM
                # call, no db work) — almost always means the provider was
                # rate-limiting/retrying on this specific call. Logged at
                # warning level regardless of success/failure so a run that
                # "feels stuck" can be diagnosed from logs: are individual
                # touches taking 30-45s each (rate-limit pressure, will
                # finish, just slowly) or is nothing happening at all
                # (genuine hang — would show as a gap in these log lines)?
                logger.warning(
                    "autopilot.email.touch_slow",
                    prospect_id=prospect.id,
                    touch_number=touch.touchNumber,
                    elapsed_seconds=round(elapsed, 1),
                    ok=touch_ok,
                )

            seq = Sequence(
                campaignId=campaign.id,
                prospectId=prospect.id,
                touchNumber=touch.touchNumber,
                sendDay=send_day,
                channel="email",
                angle=angle,
                framework=framework,
                subjectLine=subject[:500],
                bodyCopy=body,
                status=EmailStatus.Scheduled,
            )
            db.add(seq)
            sequences.append(seq)

            done_touches += 1
            if on_touch_done is not None:
                try:
                    on_touch_done(done_touches, total_touches, circuit_open)
                except Exception:  # noqa: BLE001
                    pass

            # HEARTBEAT: log every 10 touches (and always the last one) so
            # `docker compose logs -f backend | grep autopilot.emails` shows
            # a live, unmistakable trail of forward progress. If this stops
            # appearing entirely for several minutes, that's the signal of a
            # genuine hang — as opposed to individual `touch_slow` warnings,
            # which mean it's progressing but slowly through rate-limit
            # retries.
            if done_touches % 10 == 0 or done_touches == total_touches:
                logger.info(
                    "autopilot.emails.heartbeat",
                    done=done_touches,
                    total=total_touches,
                )

            # PACING FIX: delay between touches to avoid bursting straight
            # into the provider's per-minute rate limit. Skipped once the
            # circuit breaker is open — there's no live call to pace
            # against, and the whole point of tripping the breaker is to
            # finish the remaining touches FAST instead of continuing to
            # wait around for an API that has already proven itself dead.
            if not circuit_open:
                await asyncio.sleep(0.6)

    await db.flush()
    logger.info("autopilot.emails.generated", count=len(sequences))
    return sequences


# ── Top-level orchestrator ─────────────────────────────────────────────────

async def orchestrate_pipeline(
    db: AsyncSession,
    payload: dict[str, Any],
    on_progress=None,
) -> AutopilotResult:
    """
    Run the full autopilot pipeline. ONLY these four steps touch the
    database. Nothing else runs before Step 1 — no flow/audit-trail setup,
    no secondary sessions, nothing.

    on_progress, if given, is called as on_progress(step: int, detail: str)
    after each major milestone (0=starting, 1=ICP done, 2=sourcing done,
    3=campaign done, 4=email generation in progress, 5=fully done). The
    caller (router.py) uses this to update a shared progress dict that
    GET /autopilot/{task_id} reads, so the frontend can show real progress
    instead of sitting at 0% for the whole run.
    """
    def _report(step: int, detail: str = "") -> None:
        if on_progress is not None:
            try:
                on_progress(step, detail)
            except Exception:  # noqa: BLE001
                pass

    # STEP TIMING: record wall-clock elapsed seconds per step, for the
    # completion screen's per-step timing display (e.g. "16.8s").
    step_timings: dict[str, float] = {}
    _step_started_at = time.monotonic()

    def _mark_step_done(key: str) -> None:
        nonlocal _step_started_at
        now = time.monotonic()
        step_timings[key] = round(now - _step_started_at, 1)
        _step_started_at = now

    _report(0, "Starting pipeline")
    started_at = datetime.now(timezone.utc)
    task_id = payload.get("task_id") or str(uuid.uuid4())
    request = AutopilotRequest.model_validate(payload)

    llm_cfg_dict = payload.get("_llm_cfg") or {}
    if not llm_cfg_dict:
        return AutopilotResult(
            campaign_id="", prospect_count=0, sequence_count=0,
            task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
            error="LLM config not provided to orchestrator (router bug).",
            started_at=started_at, completed_at=datetime.now(timezone.utc),
        )
    llm_cfg = SimpleNamespace(**llm_cfg_dict)

    logger.info(
        "autopilot.pipeline.start",
        task_id=task_id,
        provider=llm_cfg.provider,
        model=llm_cfg.modelId,   # FIX: was llm_cfg.model — attribute renamed to modelId
        campaign=request.campaign_name,
    )

    # DIAGNOSTIC: prove the session is usable and see its search_path
    # BEFORE any pipeline logic runs. If THIS fails, the session was
    # already broken by whatever set it up in the router/Celery task —
    # not by anything in this file.
    try:
        from sqlalchemy import text
        diag = await db.execute(text("SHOW search_path"))
        logger.info("autopilot.diag.search_path", search_path=diag.scalar())
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "autopilot.diag.session_already_broken",
            error=str(exc), exc_info=True,
        )
        return AutopilotResult(
            campaign_id="", prospect_count=0, sequence_count=0,
            task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
            error=(
                "Session was already in a broken state before the pipeline "
                f"started (search_path diagnostic failed): {exc}"
            ),
            started_at=started_at, completed_at=datetime.now(timezone.utc),
        )
    _step_started_at = time.monotonic()  # start timing AFTER the diagnostic

    error: str | None = None
    icp: IcpProfile | None = None
    all_icp_profiles: list[IcpProfile] = []
    company_analysis: dict = {}
    personas_meta: list[dict] = []
    campaign: Campaign | None = None
    prospects: list[Prospect] = []
    sequences: list[Sequence] = []
    status: str = "SUCCESS"

    # ── Step 1: ICP discovery ────────────────────────────────────────────
    # This is the FIRST database statement the entire pipeline runs.
    try:
        icp, all_icp_profiles, company_analysis, personas_meta = (
            await _step_icp_discovery(db, llm_cfg, request)
        )
        _mark_step_done("icp")
        _report(1, f"{len(all_icp_profiles)} ICP personas discovered")
    except Exception as exc:  # noqa: BLE001
        error = f"ICP discovery failed: {exc}"
        logger.error("autopilot.icp_failed", error=str(exc), exc_info=True)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return AutopilotResult(
            campaign_id="", prospect_count=0, sequence_count=0,
            task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
            error=error, started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

    # ── Step 2: Prospect sourcing ────────────────────────────────────────
    prospects_preview: list[dict] = []
    try:
        prospects = await _step_prospect_sourcing(db, llm_cfg, request, icp)
        _mark_step_done("sourcing")
        _report(2, f"Sourced {len(prospects)} prospects")
        prospects_preview = [
            {
                "name": f"{p.firstName} {p.lastName}".strip(),
                "title": p.title,
                "company": p.company,
            }
            for p in prospects[:5]
        ]
    except Exception as exc:  # noqa: BLE001
        error = f"Prospect sourcing failed: {exc}"
        logger.error("autopilot.sourcing_failed", error=str(exc), exc_info=True)
        status = "PARTIAL"
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return AutopilotResult(
            campaign_id="", prospect_count=0, sequence_count=0,
            task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
            error=error, started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

    # ── Step 3: Campaign creation ────────────────────────────────────────
    try:
        campaign = await _step_campaign_creation(db, request, icp)
        _mark_step_done("campaign")
        _report(3, f"Campaign '{campaign.name}' created")
    except Exception as exc:  # noqa: BLE001
        error = f"Campaign creation failed: {exc}"
        logger.error("autopilot.campaign_failed", error=str(exc), exc_info=True)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return AutopilotResult(
            campaign_id="", prospect_count=len(prospects), sequence_count=0,
            task_id=task_id, status="FAILURE",  # type: ignore[arg-type]
            error=error, started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

    # ── Step 4: Email generation ─────────────────────────────────────────
    sequence_count = 0
    if prospects:
        try:
            def _touch_progress(done: int, total: int, circuit_open: bool) -> None:
                if circuit_open:
                    _report(4, f"Writing emails: {done}/{total} touches (LLM unavailable — using fallback text)")
                else:
                    _report(4, f"Writing emails: {done}/{total} touches")

            sequences = await _step_email_generation(
                db, llm_cfg, request, icp, campaign, prospects,
                on_touch_done=_touch_progress,
            )
            sequence_count = len(sequences)
            _mark_step_done("emails")
            _report(5, f"Complete — {sequence_count} sequences generated")
        except Exception as exc:  # noqa: BLE001
            error = f"Email generation failed: {exc}"
            logger.error("autopilot.email_failed", error=str(exc), exc_info=True)
            status = "PARTIAL"
            _mark_step_done("emails")
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass
    else:
        status = "PARTIAL"
        error = "No prospects sourced — campaign created with no sequences"

    try:
        await db.flush()
    except Exception as exc:  # noqa: BLE001
        error = f"Persist failed: {exc}"
        status = "FAILURE"
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass

    logger.info(
        "autopilot.pipeline.done",
        task_id=task_id, status=status,
        prospects=len(prospects), sequences=sequence_count,
    )

    try:
        resolved_campaign_id = campaign.id if campaign else ""
    except Exception:  # noqa: BLE001
        resolved_campaign_id = ""

    return AutopilotResult(
        campaign_id=resolved_campaign_id,
        prospect_count=len(prospects),
        sequence_count=sequence_count,
        task_id=task_id,
        status=status,  # type: ignore[arg-type]
        error=error,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        campaign_name=campaign.name if campaign else None,
        icp_profile_count=len(all_icp_profiles),
        company_analysis=company_analysis or None,
        icp_personas=personas_meta,
        prospects_preview=prospects_preview,
        step_timings=step_timings,
    )


__all__ = ["orchestrate_pipeline"]
