# # """campaign_service.py — Campaign CRUD + campaign-prospects + clone +
# # preflight + framework-recommend + gtm-thesis.

# # LLM-backed endpoints (framework-recommend, gtm-thesis) call LlmService.call_llm
# # (provided by Fix-3); a graceful fallback returns a structured response.
# # """
# # from __future__ import annotations

# # import copy
# # import json
# # from typing import Any

# # import structlog
# # from sqlalchemy import func, select
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.models.campaign_models import Campaign, CampaignProspect
# # from app.models.config_models import Domain, LlmConfig, MailBridgeConfig
# # from app.models.prospect_models import IcpProfile, Prospect
# # from app.schemas.campaigns import (
# #     CampaignCreate,
# #     CampaignProspectLinkRequest,
# #     CampaignUpdate,
# #     CloneCampaignRequest,
# #     FrameworkRecommendRequest,
# #     FrameworkRecommendResponse,
# #     GtmThesisRequest,
# #     GtmThesisResponse,
# #     PreflightCheck,
# #     PreflightRequest,
# #     PreflightResult,
# # )

# # logger = structlog.get_logger(__name__)


# # class CampaignService:
# #     """CRUD + aux ops for Campaign + CampaignProspect rows."""

# #     async def list_campaigns(
# #         self,
# #         db: AsyncSession,
# #         *,
# #         status: str | None = None,
# #         limit: int = 50,
# #         offset: int = 0,
# #         user_id: str | None = None,
# #         role: str | None = None,
# #     ) -> tuple[list[Campaign], int]:
# #         """List campaigns, optionally filtered by owner_user_id.

# #         Per-user scoping (SURVEY-USER §C5):
# #           * role == "REP"  → filter by owner_user_id == user_id (own only).
# #           * role == "MANAGER" or higher (or role is None) → no owner filter.
# #           * If user_id is provided but role is None, no filter is applied
# #             (callers that want explicit filtering should pass role="REP").
# #         """
# #         stmt = select(Campaign)
# #         if status:
# #             stmt = stmt.where(Campaign.status == status)
# #         if user_id is not None and role is not None and role.upper() == "REP":
# #             stmt = stmt.where(Campaign.owner_user_id == user_id)
# #         count_stmt = select(func.count()).select_from(stmt.subquery())
# #         total = int((await db.execute(count_stmt)).scalar() or 0)
# #         result = await db.execute(
# #             stmt.order_by(Campaign.createdAt.desc()).offset(offset).limit(limit)
# #         )
# #         return list(result.scalars().all()), total

# #     async def get(self, db: AsyncSession, campaign_id: str) -> Campaign | None:
# #         result = await db.execute(
# #             select(Campaign).where(Campaign.id == campaign_id)
# #         )
# #         return result.scalar_one_or_none()

# #     async def get_for_user(
# #         self,
# #         db: AsyncSession,
# #         campaign_id: str,
# #         *,
# #         user_id: str,
# #         role: str,
# #     ) -> Campaign | None:
# #         """Fetch a campaign, enforcing per-user ACL for REP role.

# #         Returns None if the campaign does not exist OR if the requester is a
# #         REP and the campaign is owned by a different user (callers should
# #         return 404 — never 403 — to avoid leaking existence).
# #         """
# #         item = await self.get(db, campaign_id)
# #         if item is None:
# #             return None
# #         if role.upper() == "REP" and item.owner_user_id != user_id:
# #             return None
# #         return item

# #     async def create(
# #         self,
# #         db: AsyncSession,
# #         body: CampaignCreate,
# #         *,
# #         owner_user_id: str | None = None,
# #     ) -> Campaign:
# #         """Create a campaign. owner_user_id is stamped from token.sub by the router.

# #         FIX-BE-1 / MEDIUM 10 (re-verification): the 7-touch cadence Sequence
# #         rows are NOT auto-generated on campaign create — the Sequence model
# #         requires prospectId (NOT NULL + FK to Prospect), and a fresh campaign
# #         has no prospects linked yet. Auto-generation runs on prospect-link
# #         instead (see link_prospect below), creating the 7 cadence Sequence
# #         rows per (campaign, prospect) pair.
# #         """
# #         data = body.model_dump()
# #         if owner_user_id is not None:
# #             data["owner_user_id"] = owner_user_id
# #         item = Campaign(**data)
# #         db.add(item)
# #         await db.commit()
# #         item = await db.get(Campaign, item.id)
# #         return item

# #     async def clone(
# #         self,
# #         db: AsyncSession,
# #         body: CloneCampaignRequest,
# #         *,
# #         owner_user_id: str | None = None,
# #     ) -> Campaign | None:
# #         src = await self.get(db, body.sourceCampaignId)
# #         if src is None:
# #             return None
# #         src_data = {
# #             c.name: getattr(src, c.name)
# #             for c in src.__table__.columns  # type: ignore[union-attr]
# #             if c.name not in ("id", "createdAt", "updatedAt", "name")
# #         }
# #         # The clone inherits the caller's owner_user_id (not the source's).
# #         if owner_user_id is not None:
# #             src_data["owner_user_id"] = owner_user_id
# #         new_item = Campaign(name=body.newName, **src_data)
# #         db.add(new_item)
# #         await db.commit()
# #         new_item = await db.get(Campaign, new_item.id)

# #         # Clone campaign-prospect links.
# #         links_result = await db.execute(
# #             select(CampaignProspect).where(
# #                 CampaignProspect.campaignId == body.sourceCampaignId
# #             )
# #         )
# #         for link in links_result.scalars().all():
# #             new_link = CampaignProspect(
# #                 campaignId=new_item.id,
# #                 prospectId=link.prospectId,
# #                 status=link.status,
# #             )
# #             db.add(new_link)
# #         await db.commit()
# #         return new_item

# #     async def update(
# #         self, db: AsyncSession, campaign_id: str, body: CampaignUpdate
# #     ) -> Campaign | None:
# #         item = await self.get(db, campaign_id)
# #         if item is None:
# #             return None
# #         for key, value in body.model_dump(exclude_unset=True).items():
# #             setattr(item, key, value)
# #         await db.commit()
# #         item = await db.get(Campaign, item.id)
# #         return item

# #     async def delete(self, db: AsyncSession, campaign_id: str) -> bool:
# #         item = await self.get(db, campaign_id)
# #         if item is None:
# #             return False
# #         await db.delete(item)
# #         await db.commit()
# #         return True

# #     # ── campaign-prospects junction ─────────────────────────────────────────

# #     async def link_prospect(
# #         self, db: AsyncSession, body: CampaignProspectLinkRequest
# #     ) -> CampaignProspect:
# #         # Upsert: return the existing link if (campaignId, prospectId) already
# #         # exists rather than crashing on the unique constraint
# #         # "uq_CampaignProspect_campaign_prospect".
# #         existing = await db.execute(
# #             select(CampaignProspect).where(
# #                 CampaignProspect.campaignId == body.campaignId,
# #                 CampaignProspect.prospectId == body.prospectId,
# #             )
# #         )
# #         link = existing.scalar_one_or_none()
# #         if link is None:
# #             link = CampaignProspect(
# #                 campaignId=body.campaignId,
# #                 prospectId=body.prospectId,
# #                 status="pending",
# #             )
# #             db.add(link)
# #             await db.commit()
# #             link = await db.get(CampaignProspect, link.id)

# #         # FIX-BE-1 / MEDIUM 10 (re-verification): auto-generate the 7-touch
# #         # cadence Sequence rows for this (campaign, prospect) pair. The
# #         # Sequence model requires prospectId (NOT NULL + FK to Prospect),
# #         # so generation happens at prospect-link time (not campaign-create
# #         # time). Idempotent: existing touches for this (campaignId,
# #         # prospectId, touchNumber) are skipped. Best-effort — failures are
# #         # logged + swallowed so a SequenceService hiccup never blocks the
# #         # link operation.
# #         #
# #         # IMPORTANT: verify the campaign row is visible in this session
# #         # before handing the session to SequenceService. If it's not found
# #         # (e.g. the campaign was deleted mid-request) we skip generation
# #         # rather than letting SequenceService produce a FK violation that
# #         # poisons the session with a PendingRollbackError.
# #         campaign = await self.get(db, body.campaignId)
# #         if campaign is not None:
# #             try:
# #                 from app.features.sequences.service import SequenceService

# #                 await SequenceService().auto_generate_for_campaign(
# #                     db,
# #                     campaign_id=body.campaignId,
# #                     prospect_id=body.prospectId,
# #                     owner_user_id=None,  # falls back to "system" in the helper
# #                 )
# #             except Exception as exc:  # noqa: BLE001
# #                 # Roll back the failed sequence INSERT so the session is
# #                 # returned to a clean state. The link itself was already
# #                 # committed above, so the prospect is still linked.
# #                 await db.rollback()
# #                 logger.warning(
# #                     "campaign.link_prospect.cadence_auto_gen_failed",
# #                     campaign_id=body.campaignId,
# #                     prospect_id=body.prospectId,
# #                     error=str(exc),
# #                 )
# #         else:
# #             logger.warning(
# #                 "campaign.link_prospect.campaign_not_found_for_sequence_gen",
# #                 campaign_id=body.campaignId,
# #                 prospect_id=body.prospectId,
# #             )
# #         return link

# #     async def unlink_prospect(
# #         self, db: AsyncSession, body: CampaignProspectLinkRequest
# #     ) -> bool:
# #         result = await db.execute(
# #             select(CampaignProspect).where(
# #                 CampaignProspect.campaignId == body.campaignId,
# #                 CampaignProspect.prospectId == body.prospectId,
# #             )
# #         )
# #         link = result.scalar_one_or_none()
# #         if link is None:
# #             return False
# #         await db.delete(link)
# #         await db.commit()
# #         return True

# #     async def count_prospects(
# #         self, db: AsyncSession, campaign_id: str
# #     ) -> int:
# #         result = await db.execute(
# #             select(func.count())
# #             .select_from(CampaignProspect)
# #             .where(CampaignProspect.campaignId == campaign_id)
# #         )
# #         return int(result.scalar() or 0)

# #     # ── preflight (6-check gate) ────────────────────────────────────────────

# #     async def preflight(
# #         self, db: AsyncSession, body: PreflightRequest
# #     ) -> PreflightResult:
# #         """6-check activation gate (per migration doc §10 Phase 3 exit)."""
# #         campaign = await self.get(db, body.campaignId)
# #         checks: list[PreflightCheck] = []
# #         if campaign is None:
# #             return PreflightResult(
# #                 campaignId=body.campaignId,
# #                 allPassed=False,
# #                 checks=[
# #                     PreflightCheck(
# #                         key="campaign_exists",
# #                         label="Campaign exists",
# #                         passed=False,
# #                         detail="Campaign not found.",
# #                     )
# #                 ],
# #             )

# #         # 1 — sender configured
# #         sender_ok = bool(
# #             campaign.senderRole
# #             and campaign.senderCompany
# #             and campaign.senderOffer
# #         )
# #         checks.append(
# #             PreflightCheck(
# #                 key="sender_configured",
# #                 label="Sender configured (role/company/offer)",
# #                 passed=sender_ok,
# #                 detail=None if sender_ok else "Set senderRole, senderCompany, senderOffer.",
# #             )
# #         )

# #         # 2 — domain verified (spf+dkim+dmarc)
# #         domain_ok = False
# #         if campaign.domainId:
# #             d_result = await db.execute(
# #                 select(Domain).where(Domain.id == campaign.domainId)
# #             )
# #             domain = d_result.scalar_one_or_none()
# #             if domain:
# #                 domain_ok = bool(domain.spfStatus and domain.dkimStatus and domain.dmarcStatus)
# #         checks.append(
# #             PreflightCheck(
# #                 key="domain_verified",
# #                 label="Domain verified (SPF+DKIM+DMARC)",
# #                 passed=domain_ok,
# #                 detail=None if domain_ok else "Domain DNS records not all verified.",
# #             )
# #         )

# #         # 3 — ICP attached
# #         icp_ok = bool(campaign.icpProfileId)
# #         if icp_ok:
# #             icp_result = await db.execute(
# #                 select(IcpProfile).where(IcpProfile.id == campaign.icpProfileId)
# #             )
# #             icp_ok = icp_result.scalar_one_or_none() is not None
# #         checks.append(
# #             PreflightCheck(
# #                 key="icp_attached",
# #                 label="ICP profile attached",
# #                 passed=icp_ok,
# #                 detail=None if icp_ok else "Attach an IcpProfile to the campaign.",
# #             )
# #         )

# #         # 4 — LLM configured
# #         llm_ok = bool(campaign.llmConfigId)
# #         if llm_ok:
# #             llm_result = await db.execute(
# #                 select(LlmConfig).where(LlmConfig.id == campaign.llmConfigId)
# #             )
# #             llm_ok = llm_result.scalar_one_or_none() is not None
# #         checks.append(
# #             PreflightCheck(
# #                 key="llm_configured",
# #                 label="LLM config attached",
# #                 passed=llm_ok,
# #                 detail=None if llm_ok else "Attach an LlmConfig to the campaign.",
# #             )
# #         )

# #         # 5 — MailBridge reachable (best-effort: any active MailBridgeConfig)
# #         mb_result = await db.execute(
# #             select(MailBridgeConfig)
# #             .where(MailBridgeConfig.isActive.is_(True))
# #             .limit(1)
# #         )
# #         mb_ok = mb_result.scalar_one_or_none() is not None
# #         checks.append(
# #             PreflightCheck(
# #                 key="mailbridge_reachable",
# #                 label="MailBridge reachable",
# #                 passed=mb_ok,
# #                 detail=None if mb_ok else "No active MailBridgeConfig found.",
# #             )
# #         )

# #         # 6 — prospects count > 0
# #         prospect_count = await self.count_prospects(db, body.campaignId)
# #         prospects_ok = prospect_count > 0
# #         checks.append(
# #             PreflightCheck(
# #                 key="prospects_count",
# #                 label="Prospects count > 0",
# #                 passed=prospects_ok,
# #                 detail=None
# #                 if prospects_ok
# #                 else f"Only {prospect_count} prospects linked.",
# #             )
# #         )

# #         all_passed = all(c.passed for c in checks)
# #         return PreflightResult(
# #             campaignId=body.campaignId,
# #             allPassed=all_passed,
# #             checks=checks,
# #         )

# #     # ── LLM-backed endpoints ────────────────────────────────────────────────

# #     async def framework_recommend(
# #         self, db: AsyncSession, body: FrameworkRecommendRequest
# #     ) -> FrameworkRecommendResponse | None:
# #         campaign = await self.get(db, body.campaignId)
# #         if campaign is None:
# #             return None
# #         config = await self._get_llm_config(db, campaign.llmConfigId)
# #         messages = [
# #             {
# #                 "role": "system",
# #                 "content": (
# #                     "You recommend a sales email framework (AIDA, PAS, BAB, "
# #                     "Value, Question, Breakup). Respond as JSON: "
# #                     '{"framework": "...", "rationale": "..."}.'
# #                 ),
# #             },
# #             {
# #                 "role": "user",
# #                 "content": (
# #                     f"Campaign: {campaign.name}\n"
# #                     f"Description: {campaign.description or 'n/a'}\n"
# #                     f"Sender offer: {campaign.senderOffer or 'n/a'}\n"
# #                     f"Context: {body.context or 'n/a'}"
# #                 ),
# #             },
# #         ]
# #         raw = await self._call_llm_safe(config, messages)
# #         parsed = self._safe_json(raw)
# #         framework = str(parsed.get("framework", "AIDA"))
# #         # Persist recommendation.
# #         campaign.framework = framework
# #         await db.commit()
# #         return FrameworkRecommendResponse(
# #             campaignId=campaign.id,
# #             framework=framework,
# #             rationale=parsed.get("rationale"),
# #             raw=raw,
# #         )

# #     async def gtm_thesis(
# #         self, db: AsyncSession, body: GtmThesisRequest
# #     ) -> GtmThesisResponse | None:
# #         campaign = await self.get(db, body.campaignId)
# #         if campaign is None:
# #             return None
# #         config = await self._get_llm_config(db, campaign.llmConfigId)
# #         messages = [
# #             {
# #                 "role": "system",
# #                 "content": (
# #                     "You generate a GTM (go-to-market) thesis for an outreach "
# #                     "campaign. Respond as JSON: "
# #                     '{"thesis": "..."}.'
# #                 ),
# #             },
# #             {
# #                 "role": "user",
# #                 "content": (
# #                     f"Campaign: {campaign.name}\n"
# #                     f"Sender: {campaign.senderRole or 'n/a'} at "
# #                     f"{campaign.senderCompany or 'n/a'}\n"
# #                     f"Offer: {campaign.senderOffer or 'n/a'}\n"
# #                     f"Target audience: {campaign.targetAudience or 'n/a'}\n"
# #                     f"Additional context: {body.additionalContext or 'n/a'}"
# #                 ),
# #             },
# #         ]
# #         raw = await self._call_llm_safe(config, messages)
# #         parsed = self._safe_json(raw)
# #         return GtmThesisResponse(
# #             campaignId=campaign.id,
# #             thesis=str(parsed.get("thesis", "")),
# #             raw=raw,
# #         )

# #     # ── Helpers ─────────────────────────────────────────────────────────────

# #     async def _get_llm_config(
# #         self, db: AsyncSession, config_id: str | None
# #     ) -> Any:
# #         if not config_id:
# #             try:
# #                 from app.services.llm_service import get_default_llm_config

# #                 return await get_default_llm_config(db)
# #             except Exception as exc:  # noqa: BLE001
# #                 logger.warning("campaign.default_llm_lookup_failed", error=str(exc))
# #                 return None
# #         result = await db.execute(
# #             select(LlmConfig).where(LlmConfig.id == config_id)
# #         )
# #         return result.scalar_one_or_none()

# #     async def _call_llm_safe(
# #         self, config: Any, messages: list[dict[str, str]]
# #     ) -> str:
# #         try:
# #             from app.services.llm_service import call_llm as _call_llm

# #             if config is None:
# #                 from app.services.llm_service import LlmService

# #                 joined = "\n\n".join(m["content"] for m in messages)
# #                 return await LlmService().generate(prompt=joined)
# #             result = await _call_llm(config, messages)
# #             return str(getattr(result, "content", result))
# #         except Exception as exc:  # noqa: BLE001
# #             logger.warning("campaign.llm_call_failed", error=str(exc))
# #             return ""

# #     @staticmethod
# #     def _safe_json(raw: str) -> dict[str, Any]:
# #         if not raw:
# #             return {}
# #         try:
# #             return json.loads(raw)
# #         except (json.JSONDecodeError, ValueError):
# #             start = raw.find("{")
# #             end = raw.rfind("}")
# #             if start >= 0 and end > start:
# #                 try:
# #                     return json.loads(raw[start : end + 1])
# #                 except (json.JSONDecodeError, ValueError):
# #                     return {}
# #             return {}


# # __all__ = ["CampaignService"]

# """campaign_service.py — Campaign CRUD + campaign-prospects + clone +
# preflight + framework-recommend + gtm-thesis.

# LLM-backed endpoints (framework-recommend, gtm-thesis) call LlmService.call_llm
# (provided by Fix-3); a graceful fallback returns a structured response.
# """
# from __future__ import annotations

# import copy
# import json
# from typing import Any

# import structlog
# from sqlalchemy import func, select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.campaign_models import Campaign, CampaignProspect
# from app.models.config_models import Domain, LlmConfig, MailBridgeConfig
# from app.models.prospect_models import IcpProfile, Prospect
# from app.schemas.campaigns import (
#     CampaignCreate,
#     CampaignProspectLinkRequest,
#     CampaignUpdate,
#     CloneCampaignRequest,
#     FrameworkRecommendRequest,
#     FrameworkRecommendResponse,
#     GtmThesisRequest,
#     GtmThesisResponse,
#     PreflightCheck,
#     PreflightRequest,
#     PreflightResult,
# )

# logger = structlog.get_logger(__name__)


# class CampaignService:
#     """CRUD + aux ops for Campaign + CampaignProspect rows."""

#     async def list_campaigns(
#         self,
#         db: AsyncSession,
#         *,
#         status: str | None = None,
#         limit: int = 50,
#         offset: int = 0,
#         user_id: str | None = None,
#         role: str | None = None,
#     ) -> tuple[list[Campaign], int]:
#         """List campaigns for the tenant.

#         All tenant roles (REP, MANAGER, TENANT_ADMIN) see all campaigns within
#         their tenant schema.  REPs are sales reps who collaborate on every
#         campaign — restricting them to owner_user_id == their own sub means
#         they see nothing when campaigns are created by a MANAGER.

#         The GET /campaigns/my endpoint exists for personal filtering when a
#         REP explicitly wants only the campaigns they created.

#         MANAGER+ filtering is preserved: no owner filter applied at any role.
#         """
#         stmt = select(Campaign)
#         if status:
#             stmt = stmt.where(Campaign.status == status)
#         count_stmt = select(func.count()).select_from(stmt.subquery())
#         total = int((await db.execute(count_stmt)).scalar() or 0)
#         result = await db.execute(
#             stmt.order_by(Campaign.createdAt.desc()).offset(offset).limit(limit)
#         )
#         return list(result.scalars().all()), total

#     async def get(self, db: AsyncSession, campaign_id: str) -> Campaign | None:
#         result = await db.execute(
#             select(Campaign).where(Campaign.id == campaign_id)
#         )
#         return result.scalar_one_or_none()

#     async def get_for_user(
#         self,
#         db: AsyncSession,
#         campaign_id: str,
#         *,
#         user_id: str,
#         role: str,
#     ) -> Campaign | None:
#         """Fetch a campaign, enforcing per-user ACL for REP role.

#         Returns None if the campaign does not exist OR if the requester is a
#         REP and the campaign is owned by a different user (callers should
#         return 404 — never 403 — to avoid leaking existence).
#         """
#         item = await self.get(db, campaign_id)
#         if item is None:
#             return None
#         if role.upper() == "REP" and item.owner_user_id != user_id:
#             return None
#         return item

#     async def create(
#         self,
#         db: AsyncSession,
#         body: CampaignCreate,
#         *,
#         owner_user_id: str | None = None,
#     ) -> Campaign:
#         """Create a campaign. owner_user_id is stamped from token.sub by the router.

#         FIX-BE-1 / MEDIUM 10 (re-verification): the 7-touch cadence Sequence
#         rows are NOT auto-generated on campaign create — the Sequence model
#         requires prospectId (NOT NULL + FK to Prospect), and a fresh campaign
#         has no prospects linked yet. Auto-generation runs on prospect-link
#         instead (see link_prospect below), creating the 7 cadence Sequence
#         rows per (campaign, prospect) pair.
#         """
#         data = body.model_dump()
#         if owner_user_id is not None:
#             data["owner_user_id"] = owner_user_id
#         item = Campaign(**data)
#         db.add(item)
#         await db.commit()
#         item = await db.get(Campaign, item.id)
#         return item

#     async def clone(
#         self,
#         db: AsyncSession,
#         body: CloneCampaignRequest,
#         *,
#         owner_user_id: str | None = None,
#     ) -> Campaign | None:
#         src = await self.get(db, body.sourceCampaignId)
#         if src is None:
#             return None
#         src_data = {
#             c.name: getattr(src, c.name)
#             for c in src.__table__.columns  # type: ignore[union-attr]
#             if c.name not in ("id", "createdAt", "updatedAt", "name")
#         }
#         # The clone inherits the caller's owner_user_id (not the source's).
#         if owner_user_id is not None:
#             src_data["owner_user_id"] = owner_user_id
#         new_item = Campaign(name=body.newName, **src_data)
#         db.add(new_item)
#         await db.commit()
#         new_item = await db.get(Campaign, new_item.id)

#         # Clone campaign-prospect links.
#         links_result = await db.execute(
#             select(CampaignProspect).where(
#                 CampaignProspect.campaignId == body.sourceCampaignId
#             )
#         )
#         for link in links_result.scalars().all():
#             new_link = CampaignProspect(
#                 campaignId=new_item.id,
#                 prospectId=link.prospectId,
#                 status=link.status,
#             )
#             db.add(new_link)
#         await db.commit()
#         return new_item

#     async def update(
#         self, db: AsyncSession, campaign_id: str, body: CampaignUpdate
#     ) -> Campaign | None:
#         item = await self.get(db, campaign_id)
#         if item is None:
#             return None
#         for key, value in body.model_dump(exclude_unset=True).items():
#             setattr(item, key, value)
#         await db.commit()
#         item = await db.get(Campaign, item.id)
#         return item

#     async def delete(self, db: AsyncSession, campaign_id: str) -> bool:
#         item = await self.get(db, campaign_id)
#         if item is None:
#             return False
#         await db.delete(item)
#         await db.commit()
#         return True

#     # ── campaign-prospects junction ─────────────────────────────────────────

#     async def link_prospect(
#         self, db: AsyncSession, body: CampaignProspectLinkRequest
#     ) -> CampaignProspect:
#         # Upsert: return the existing link if (campaignId, prospectId) already
#         # exists rather than crashing on the unique constraint
#         # "uq_CampaignProspect_campaign_prospect".
#         existing = await db.execute(
#             select(CampaignProspect).where(
#                 CampaignProspect.campaignId == body.campaignId,
#                 CampaignProspect.prospectId == body.prospectId,
#             )
#         )
#         link = existing.scalar_one_or_none()
#         if link is None:
#             link = CampaignProspect(
#                 campaignId=body.campaignId,
#                 prospectId=body.prospectId,
#                 status="pending",
#             )
#             db.add(link)
#             await db.commit()
#             link = await db.get(CampaignProspect, link.id)

#         # FIX-BE-1 / MEDIUM 10 (re-verification): auto-generate the 7-touch
#         # cadence Sequence rows for this (campaign, prospect) pair. The
#         # Sequence model requires prospectId (NOT NULL + FK to Prospect),
#         # so generation happens at prospect-link time (not campaign-create
#         # time). Idempotent: existing touches for this (campaignId,
#         # prospectId, touchNumber) are skipped. Best-effort — failures are
#         # logged + swallowed so a SequenceService hiccup never blocks the
#         # link operation.
#         #
#         # IMPORTANT: verify the campaign row is visible in this session
#         # before handing the session to SequenceService. If it's not found
#         # (e.g. the campaign was deleted mid-request) we skip generation
#         # rather than letting SequenceService produce a FK violation that
#         # poisons the session with a PendingRollbackError.
#         campaign = await self.get(db, body.campaignId)
#         if campaign is not None:
#             try:
#                 from app.features.sequences.service import SequenceService

#                 await SequenceService().auto_generate_for_campaign(
#                     db,
#                     campaign_id=body.campaignId,
#                     prospect_id=body.prospectId,
#                     owner_user_id=None,  # falls back to "system" in the helper
#                 )
#             except Exception as exc:  # noqa: BLE001
#                 # Roll back the failed sequence INSERT so the session is
#                 # returned to a clean state. The link itself was already
#                 # committed above, so the prospect is still linked.
#                 await db.rollback()
#                 logger.warning(
#                     "campaign.link_prospect.cadence_auto_gen_failed",
#                     campaign_id=body.campaignId,
#                     prospect_id=body.prospectId,
#                     error=str(exc),
#                 )
#         else:
#             logger.warning(
#                 "campaign.link_prospect.campaign_not_found_for_sequence_gen",
#                 campaign_id=body.campaignId,
#                 prospect_id=body.prospectId,
#             )
#         return link

#     async def unlink_prospect(
#         self, db: AsyncSession, body: CampaignProspectLinkRequest
#     ) -> bool:
#         result = await db.execute(
#             select(CampaignProspect).where(
#                 CampaignProspect.campaignId == body.campaignId,
#                 CampaignProspect.prospectId == body.prospectId,
#             )
#         )
#         link = result.scalar_one_or_none()
#         if link is None:
#             return False
#         await db.delete(link)
#         await db.commit()
#         return True

#     async def count_prospects(
#         self, db: AsyncSession, campaign_id: str
#     ) -> int:
#         result = await db.execute(
#             select(func.count())
#             .select_from(CampaignProspect)
#             .where(CampaignProspect.campaignId == campaign_id)
#         )
#         return int(result.scalar() or 0)

#     # ── preflight (6-check gate) ────────────────────────────────────────────

#     async def preflight(
#         self, db: AsyncSession, body: PreflightRequest
#     ) -> PreflightResult:
#         """6-check activation gate (per migration doc §10 Phase 3 exit)."""
#         campaign = await self.get(db, body.campaignId)
#         checks: list[PreflightCheck] = []
#         if campaign is None:
#             return PreflightResult(
#                 campaignId=body.campaignId,
#                 allPassed=False,
#                 checks=[
#                     PreflightCheck(
#                         key="campaign_exists",
#                         label="Campaign exists",
#                         passed=False,
#                         detail="Campaign not found.",
#                     )
#                 ],
#             )

#         # 1 — sender configured
#         sender_ok = bool(
#             campaign.senderRole
#             and campaign.senderCompany
#             and campaign.senderOffer
#         )
#         checks.append(
#             PreflightCheck(
#                 key="sender_configured",
#                 label="Sender configured (role/company/offer)",
#                 passed=sender_ok,
#                 detail=None if sender_ok else "Set senderRole, senderCompany, senderOffer.",
#             )
#         )

#         # 2 — domain verified (spf+dkim+dmarc)
#         domain_ok = False
#         if campaign.domainId:
#             d_result = await db.execute(
#                 select(Domain).where(Domain.id == campaign.domainId)
#             )
#             domain = d_result.scalar_one_or_none()
#             if domain:
#                 domain_ok = bool(domain.spfStatus and domain.dkimStatus and domain.dmarcStatus)
#         checks.append(
#             PreflightCheck(
#                 key="domain_verified",
#                 label="Domain verified (SPF+DKIM+DMARC)",
#                 passed=domain_ok,
#                 detail=None if domain_ok else "Domain DNS records not all verified.",
#             )
#         )

#         # 3 — ICP attached
#         icp_ok = bool(campaign.icpProfileId)
#         if icp_ok:
#             icp_result = await db.execute(
#                 select(IcpProfile).where(IcpProfile.id == campaign.icpProfileId)
#             )
#             icp_ok = icp_result.scalar_one_or_none() is not None
#         checks.append(
#             PreflightCheck(
#                 key="icp_attached",
#                 label="ICP profile attached",
#                 passed=icp_ok,
#                 detail=None if icp_ok else "Attach an IcpProfile to the campaign.",
#             )
#         )

#         # 4 — LLM configured
#         llm_ok = bool(campaign.llmConfigId)
#         if llm_ok:
#             llm_result = await db.execute(
#                 select(LlmConfig).where(LlmConfig.id == campaign.llmConfigId)
#             )
#             llm_ok = llm_result.scalar_one_or_none() is not None
#         checks.append(
#             PreflightCheck(
#                 key="llm_configured",
#                 label="LLM config attached",
#                 passed=llm_ok,
#                 detail=None if llm_ok else "Attach an LlmConfig to the campaign.",
#             )
#         )

#         # 5 — MailBridge reachable (best-effort: any active MailBridgeConfig)
#         mb_result = await db.execute(
#             select(MailBridgeConfig)
#             .where(MailBridgeConfig.isActive.is_(True))
#             .limit(1)
#         )
#         mb_ok = mb_result.scalar_one_or_none() is not None
#         checks.append(
#             PreflightCheck(
#                 key="mailbridge_reachable",
#                 label="MailBridge reachable",
#                 passed=mb_ok,
#                 detail=None if mb_ok else "No active MailBridgeConfig found.",
#             )
#         )

#         # 6 — prospects count > 0
#         prospect_count = await self.count_prospects(db, body.campaignId)
#         prospects_ok = prospect_count > 0
#         checks.append(
#             PreflightCheck(
#                 key="prospects_count",
#                 label="Prospects count > 0",
#                 passed=prospects_ok,
#                 detail=None
#                 if prospects_ok
#                 else f"Only {prospect_count} prospects linked.",
#             )
#         )

#         all_passed = all(c.passed for c in checks)
#         return PreflightResult(
#             campaignId=body.campaignId,
#             allPassed=all_passed,
#             checks=checks,
#         )

#     # ── LLM-backed endpoints ────────────────────────────────────────────────

#     async def framework_recommend(
#         self, db: AsyncSession, body: FrameworkRecommendRequest
#     ) -> FrameworkRecommendResponse | None:
#         campaign = await self.get(db, body.campaignId)
#         if campaign is None:
#             return None
#         config = await self._get_llm_config(db, campaign.llmConfigId)
#         messages = [
#             {
#                 "role": "system",
#                 "content": (
#                     "You recommend a sales email framework (AIDA, PAS, BAB, "
#                     "Value, Question, Breakup). Respond as JSON: "
#                     '{"framework": "...", "rationale": "..."}.'
#                 ),
#             },
#             {
#                 "role": "user",
#                 "content": (
#                     f"Campaign: {campaign.name}\n"
#                     f"Description: {campaign.description or 'n/a'}\n"
#                     f"Sender offer: {campaign.senderOffer or 'n/a'}\n"
#                     f"Context: {body.context or 'n/a'}"
#                 ),
#             },
#         ]
#         raw = await self._call_llm_safe(config, messages)
#         parsed = self._safe_json(raw)
#         framework = str(parsed.get("framework", "AIDA"))
#         # Persist recommendation.
#         campaign.framework = framework
#         await db.commit()
#         return FrameworkRecommendResponse(
#             campaignId=campaign.id,
#             framework=framework,
#             rationale=parsed.get("rationale"),
#             raw=raw,
#         )

#     async def gtm_thesis(
#         self, db: AsyncSession, body: GtmThesisRequest
#     ) -> GtmThesisResponse | None:
#         campaign = await self.get(db, body.campaignId)
#         if campaign is None:
#             return None
#         config = await self._get_llm_config(db, campaign.llmConfigId)
#         messages = [
#             {
#                 "role": "system",
#                 "content": (
#                     "You generate a GTM (go-to-market) thesis for an outreach "
#                     "campaign. Respond as JSON: "
#                     '{"thesis": "..."}.'
#                 ),
#             },
#             {
#                 "role": "user",
#                 "content": (
#                     f"Campaign: {campaign.name}\n"
#                     f"Sender: {campaign.senderRole or 'n/a'} at "
#                     f"{campaign.senderCompany or 'n/a'}\n"
#                     f"Offer: {campaign.senderOffer or 'n/a'}\n"
#                     f"Target audience: {campaign.targetAudience or 'n/a'}\n"
#                     f"Additional context: {body.additionalContext or 'n/a'}"
#                 ),
#             },
#         ]
#         raw = await self._call_llm_safe(config, messages)
#         parsed = self._safe_json(raw)
#         return GtmThesisResponse(
#             campaignId=campaign.id,
#             thesis=str(parsed.get("thesis", "")),
#             raw=raw,
#         )

#     # ── Helpers ─────────────────────────────────────────────────────────────

#     async def _get_llm_config(
#         self, db: AsyncSession, config_id: str | None
#     ) -> Any:
#         if not config_id:
#             try:
#                 from app.services.llm_service import get_default_llm_config

#                 return await get_default_llm_config(db)
#             except Exception as exc:  # noqa: BLE001
#                 logger.warning("campaign.default_llm_lookup_failed", error=str(exc))
#                 return None
#         result = await db.execute(
#             select(LlmConfig).where(LlmConfig.id == config_id)
#         )
#         return result.scalar_one_or_none()

#     async def _call_llm_safe(
#         self, config: Any, messages: list[dict[str, str]]
#     ) -> str:
#         try:
#             from app.services.llm_service import call_llm as _call_llm

#             if config is None:
#                 from app.services.llm_service import LlmService

#                 joined = "\n\n".join(m["content"] for m in messages)
#                 return await LlmService().generate(prompt=joined)
#             result = await _call_llm(config, messages)
#             return str(getattr(result, "content", result))
#         except Exception as exc:  # noqa: BLE001
#             logger.warning("campaign.llm_call_failed", error=str(exc))
#             return ""

#     @staticmethod
#     def _safe_json(raw: str) -> dict[str, Any]:
#         if not raw:
#             return {}
#         try:
#             return json.loads(raw)
#         except (json.JSONDecodeError, ValueError):
#             start = raw.find("{")
#             end = raw.rfind("}")
#             if start >= 0 and end > start:
#                 try:
#                     return json.loads(raw[start : end + 1])
#                 except (json.JSONDecodeError, ValueError):
#                     return {}
#             return {}


# __all__ = ["CampaignService"]

"""campaign_service.py — Campaign CRUD + campaign-prospects + clone +
preflight + framework-recommend + gtm-thesis.
 
LLM-backed endpoints (framework-recommend, gtm-thesis) call LlmService.call_llm
(provided by Fix-3); a graceful fallback returns a structured response.
"""
from __future__ import annotations
 
import copy
import json
from typing import Any
 
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.models.campaign_models import Campaign, CampaignProspect
from app.models.config_models import Domain, LlmConfig, MailBridgeConfig
from app.models.prospect_models import IcpProfile, Prospect
from app.schemas.campaigns import (
    CampaignCreate,
    CampaignProspectLinkRequest,
    CampaignUpdate,
    CloneCampaignRequest,
    FrameworkRecommendRequest,
    FrameworkRecommendResponse,
    GtmThesisRequest,
    GtmThesisResponse,
    PreflightCheck,
    PreflightRequest,
    PreflightResult,
)
 
logger = structlog.get_logger(__name__)
 
 
class CampaignService:
    """CRUD + aux ops for Campaign + CampaignProspect rows."""
 
    async def list_campaigns(
        self,
        db: AsyncSession,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
        role: str | None = None,
    ) -> tuple[list[Campaign], int, dict[str, dict[str, int]]]:
        """List campaigns for the tenant.
 
        Returns a tuple of (campaigns, total, counts_by_campaign_id).
        counts_by_campaign_id maps campaign_id → {prospects, sequences, collaterals}.
 
        All tenant roles (REP, MANAGER, TENANT_ADMIN) see all campaigns within
        their tenant schema.  REPs are sales reps who collaborate on every
        campaign — restricting them to owner_user_id == their own sub means
        they see nothing when campaigns are created by a MANAGER.
 
        The GET /campaigns/my endpoint exists for personal filtering when a
        REP explicitly wants only the campaigns they created.
 
        MANAGER+ filtering is preserved: no owner filter applied at any role.
        """
        from app.models.campaign_models import CampaignProspect, CampaignCollateralLink, Sequence as _Seq
 
        stmt = select(Campaign)
        if status:
            stmt = stmt.where(Campaign.status == status)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar() or 0)
        result = await db.execute(
            stmt.order_by(Campaign.createdAt.desc()).offset(offset).limit(limit)
        )
        campaigns = list(result.scalars().all())
 
        # Fetch counts for the returned campaigns in 3 bulk queries.
        counts: dict[str, dict[str, int]] = {}
        if campaigns:
            camp_ids = [c.id for c in campaigns]
 
            # Prospect count — count DISTINCT prospectIds across sequences
            # (sequences are the source of truth; CampaignProspect is a secondary
            # link table that may not be populated for all campaigns).
            # We take the MAX of the two to handle both patterns.
            prospect_via_seq = (await db.execute(
                select(_Seq.campaignId, func.count(_Seq.prospectId.distinct()))
                .where(
                    _Seq.campaignId.in_(camp_ids),
                    _Seq.prospectId.is_not(None),
                )
                .group_by(_Seq.campaignId)
            )).all()
            for camp_id, cnt in prospect_via_seq:
                counts.setdefault(camp_id, {"prospects": 0, "sequences": 0, "collaterals": 0})
                counts[camp_id]["prospects"] = int(cnt)
 
            # Also check CampaignProspect table and take the higher of the two
            prospect_via_link = (await db.execute(
                select(CampaignProspect.campaignId, func.count(CampaignProspect.id))
                .where(CampaignProspect.campaignId.in_(camp_ids))
                .group_by(CampaignProspect.campaignId)
            )).all()
            for camp_id, cnt in prospect_via_link:
                counts.setdefault(camp_id, {"prospects": 0, "sequences": 0, "collaterals": 0})
                counts[camp_id]["prospects"] = max(counts[camp_id]["prospects"], int(cnt))
 
            # Sequence count
            sequence_counts = (await db.execute(
                select(_Seq.campaignId, func.count(_Seq.id))
                .where(_Seq.campaignId.in_(camp_ids))
                .group_by(_Seq.campaignId)
            )).all()
            for camp_id, cnt in sequence_counts:
                counts.setdefault(camp_id, {"prospects": 0, "sequences": 0, "collaterals": 0})
                counts[camp_id]["sequences"] = int(cnt)
 
            # Collateral count
            collateral_counts = (await db.execute(
                select(CampaignCollateralLink.campaignId, func.count(CampaignCollateralLink.id))
                .where(CampaignCollateralLink.campaignId.in_(camp_ids))
                .group_by(CampaignCollateralLink.campaignId)
            )).all()
            for camp_id, cnt in collateral_counts:
                counts.setdefault(camp_id, {"prospects": 0, "sequences": 0, "collaterals": 0})
                counts[camp_id]["collaterals"] = int(cnt)
 
        return campaigns, total, counts
 
    async def get(self, db: AsyncSession, campaign_id: str) -> Campaign | None:
        result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        return result.scalar_one_or_none()
 
    async def get_for_user(
        self,
        db: AsyncSession,
        campaign_id: str,
        *,
        user_id: str,
        role: str,
    ) -> Campaign | None:
        """Fetch a campaign, enforcing per-user ACL for REP role.
 
        Returns None if the campaign does not exist OR if the requester is a
        REP and the campaign is owned by a different user (callers should
        return 404 — never 403 — to avoid leaking existence).
        """
        item = await self.get(db, campaign_id)
        if item is None:
            return None
        if role.upper() == "REP" and item.owner_user_id != user_id:
            return None
        return item
 
    async def create(
        self,
        db: AsyncSession,
        body: CampaignCreate,
        *,
        owner_user_id: str | None = None,
    ) -> Campaign:
        """Create a campaign. owner_user_id is stamped from token.sub by the router.
 
        FIX-BE-1 / MEDIUM 10 (re-verification): the 7-touch cadence Sequence
        rows are NOT auto-generated on campaign create — the Sequence model
        requires prospectId (NOT NULL + FK to Prospect), and a fresh campaign
        has no prospects linked yet. Auto-generation runs on prospect-link
        instead (see link_prospect below), creating the 7 cadence Sequence
        rows per (campaign, prospect) pair.
        """
        data = body.model_dump()
        if owner_user_id is not None:
            data["owner_user_id"] = owner_user_id
        item = Campaign(**data)
        db.add(item)
        await db.commit()
        item = await db.get(Campaign, item.id)
        return item
 
    async def clone(
        self,
        db: AsyncSession,
        body: CloneCampaignRequest,
        *,
        owner_user_id: str | None = None,
    ) -> Campaign | None:
        src = await self.get(db, body.sourceCampaignId)
        if src is None:
            return None
        src_data = {
            c.name: getattr(src, c.name)
            for c in src.__table__.columns  # type: ignore[union-attr]
            if c.name not in ("id", "createdAt", "updatedAt", "name")
        }
        # The clone inherits the caller's owner_user_id (not the source's).
        if owner_user_id is not None:
            src_data["owner_user_id"] = owner_user_id
        new_item = Campaign(name=body.newName, **src_data)
        db.add(new_item)
        await db.commit()
        new_item = await db.get(Campaign, new_item.id)
 
        # Clone campaign-prospect links.
        links_result = await db.execute(
            select(CampaignProspect).where(
                CampaignProspect.campaignId == body.sourceCampaignId
            )
        )
        for link in links_result.scalars().all():
            new_link = CampaignProspect(
                campaignId=new_item.id,
                prospectId=link.prospectId,
                status=link.status,
            )
            db.add(new_link)
        await db.commit()
        return new_item
 
    async def update(
        self, db: AsyncSession, campaign_id: str, body: CampaignUpdate
    ) -> Campaign | None:
        item = await self.get(db, campaign_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(Campaign, item.id)
        return item
 
    async def delete(self, db: AsyncSession, campaign_id: str) -> bool:
        item = await self.get(db, campaign_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True
 
    # ── campaign-prospects junction ─────────────────────────────────────────
 
    async def link_prospect(
        self, db: AsyncSession, body: CampaignProspectLinkRequest
    ) -> CampaignProspect:
        # Upsert: return the existing link if (campaignId, prospectId) already
        # exists rather than crashing on the unique constraint
        # "uq_CampaignProspect_campaign_prospect".
        existing = await db.execute(
            select(CampaignProspect).where(
                CampaignProspect.campaignId == body.campaignId,
                CampaignProspect.prospectId == body.prospectId,
            )
        )
        link = existing.scalar_one_or_none()
        if link is None:
            link = CampaignProspect(
                campaignId=body.campaignId,
                prospectId=body.prospectId,
                status="pending",
            )
            db.add(link)
            await db.commit()
            link = await db.get(CampaignProspect, link.id)
 
        # FIX-BE-1 / MEDIUM 10 (re-verification): auto-generate the 7-touch
        # cadence Sequence rows for this (campaign, prospect) pair. The
        # Sequence model requires prospectId (NOT NULL + FK to Prospect),
        # so generation happens at prospect-link time (not campaign-create
        # time). Idempotent: existing touches for this (campaignId,
        # prospectId, touchNumber) are skipped. Best-effort — failures are
        # logged + swallowed so a SequenceService hiccup never blocks the
        # link operation.
        #
        # IMPORTANT: verify the campaign row is visible in this session
        # before handing the session to SequenceService. If it's not found
        # (e.g. the campaign was deleted mid-request) we skip generation
        # rather than letting SequenceService produce a FK violation that
        # poisons the session with a PendingRollbackError.
        campaign = await self.get(db, body.campaignId)
        if campaign is not None:
            try:
                from app.features.sequences.service import SequenceService
 
                await SequenceService().auto_generate_for_campaign(
                    db,
                    campaign_id=body.campaignId,
                    prospect_id=body.prospectId,
                    owner_user_id=None,  # falls back to "system" in the helper
                )
            except Exception as exc:  # noqa: BLE001
                # Roll back the failed sequence INSERT so the session is
                # returned to a clean state. The link itself was already
                # committed above, so the prospect is still linked.
                await db.rollback()
                logger.warning(
                    "campaign.link_prospect.cadence_auto_gen_failed",
                    campaign_id=body.campaignId,
                    prospect_id=body.prospectId,
                    error=str(exc),
                )
        else:
            logger.warning(
                "campaign.link_prospect.campaign_not_found_for_sequence_gen",
                campaign_id=body.campaignId,
                prospect_id=body.prospectId,
            )
        return link
 
    async def unlink_prospect(
        self, db: AsyncSession, body: CampaignProspectLinkRequest
    ) -> bool:
        result = await db.execute(
            select(CampaignProspect).where(
                CampaignProspect.campaignId == body.campaignId,
                CampaignProspect.prospectId == body.prospectId,
            )
        )
        link = result.scalar_one_or_none()
        if link is None:
            return False
        await db.delete(link)
        await db.commit()
        return True
 
    async def count_prospects(
        self, db: AsyncSession, campaign_id: str
    ) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(CampaignProspect)
            .where(CampaignProspect.campaignId == campaign_id)
        )
        return int(result.scalar() or 0)
 
    # ── preflight (6-check gate) ────────────────────────────────────────────
 
    async def preflight(
        self, db: AsyncSession, body: PreflightRequest
    ) -> PreflightResult:
        """6-check activation gate (per migration doc §10 Phase 3 exit)."""
        campaign = await self.get(db, body.campaignId)
        checks: list[PreflightCheck] = []
        if campaign is None:
            return PreflightResult(
                campaignId=body.campaignId,
                allPassed=False,
                checks=[
                    PreflightCheck(
                        key="campaign_exists",
                        label="Campaign exists",
                        passed=False,
                        detail="Campaign not found.",
                    )
                ],
            )
 
        # 1 — sender configured
        sender_ok = bool(
            campaign.senderRole
            and campaign.senderCompany
            and campaign.senderOffer
        )
        checks.append(
            PreflightCheck(
                key="sender_configured",
                label="Sender configured (role/company/offer)",
                passed=sender_ok,
                detail=None if sender_ok else "Set senderRole, senderCompany, senderOffer.",
            )
        )
 
        # 2 — domain verified (spf+dkim+dmarc)
        domain_ok = False
        if campaign.domainId:
            d_result = await db.execute(
                select(Domain).where(Domain.id == campaign.domainId)
            )
            domain = d_result.scalar_one_or_none()
            if domain:
                domain_ok = bool(domain.spfStatus and domain.dkimStatus and domain.dmarcStatus)
        checks.append(
            PreflightCheck(
                key="domain_verified",
                label="Domain verified (SPF+DKIM+DMARC)",
                passed=domain_ok,
                detail=None if domain_ok else "Domain DNS records not all verified.",
            )
        )
 
        # 3 — ICP attached
        icp_ok = bool(campaign.icpProfileId)
        if icp_ok:
            icp_result = await db.execute(
                select(IcpProfile).where(IcpProfile.id == campaign.icpProfileId)
            )
            icp_ok = icp_result.scalar_one_or_none() is not None
        checks.append(
            PreflightCheck(
                key="icp_attached",
                label="ICP profile attached",
                passed=icp_ok,
                detail=None if icp_ok else "Attach an IcpProfile to the campaign.",
            )
        )
 
        # 4 — LLM configured
        llm_ok = bool(campaign.llmConfigId)
        if llm_ok:
            llm_result = await db.execute(
                select(LlmConfig).where(LlmConfig.id == campaign.llmConfigId)
            )
            llm_ok = llm_result.scalar_one_or_none() is not None
        checks.append(
            PreflightCheck(
                key="llm_configured",
                label="LLM config attached",
                passed=llm_ok,
                detail=None if llm_ok else "Attach an LlmConfig to the campaign.",
            )
        )
 
        # 5 — MailBridge reachable (best-effort: any active MailBridgeConfig)
        mb_result = await db.execute(
            select(MailBridgeConfig)
            .where(MailBridgeConfig.isActive.is_(True))
            .limit(1)
        )
        mb_ok = mb_result.scalar_one_or_none() is not None
        checks.append(
            PreflightCheck(
                key="mailbridge_reachable",
                label="MailBridge reachable",
                passed=mb_ok,
                detail=None if mb_ok else "No active MailBridgeConfig found.",
            )
        )
 
        # 6 — prospects count > 0
        prospect_count = await self.count_prospects(db, body.campaignId)
        prospects_ok = prospect_count > 0
        checks.append(
            PreflightCheck(
                key="prospects_count",
                label="Prospects count > 0",
                passed=prospects_ok,
                detail=None
                if prospects_ok
                else f"Only {prospect_count} prospects linked.",
            )
        )
 
        all_passed = all(c.passed for c in checks)
        return PreflightResult(
            campaignId=body.campaignId,
            allPassed=all_passed,
            checks=checks,
        )
 
    # ── LLM-backed endpoints ────────────────────────────────────────────────
 
    async def framework_recommend(
        self, db: AsyncSession, body: FrameworkRecommendRequest
    ) -> FrameworkRecommendResponse | None:
        campaign = await self.get(db, body.campaignId)
        if campaign is None:
            return None
        config = await self._get_llm_config(db, campaign.llmConfigId)
        messages = [
            {
                "role": "system",
                "content": (
                    "You recommend a sales email framework (AIDA, PAS, BAB, "
                    "Value, Question, Breakup). Respond as JSON: "
                    '{"framework": "...", "rationale": "..."}.'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Campaign: {campaign.name}\n"
                    f"Description: {campaign.description or 'n/a'}\n"
                    f"Sender offer: {campaign.senderOffer or 'n/a'}\n"
                    f"Context: {body.context or 'n/a'}"
                ),
            },
        ]
        raw = await self._call_llm_safe(config, messages)
        parsed = self._safe_json(raw)
        framework = str(parsed.get("framework", "AIDA"))
        # Persist recommendation.
        campaign.framework = framework
        await db.commit()
        return FrameworkRecommendResponse(
            campaignId=campaign.id,
            framework=framework,
            rationale=parsed.get("rationale"),
            raw=raw,
        )
 
    async def gtm_thesis(
        self, db: AsyncSession, body: GtmThesisRequest
    ) -> GtmThesisResponse | None:
        campaign = await self.get(db, body.campaignId)
        if campaign is None:
            return None
        config = await self._get_llm_config(db, campaign.llmConfigId)
        messages = [
            {
                "role": "system",
                "content": (
                    "You generate a GTM (go-to-market) thesis for an outreach "
                    "campaign. Respond as JSON: "
                    '{"thesis": "..."}.'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Campaign: {campaign.name}\n"
                    f"Sender: {campaign.senderRole or 'n/a'} at "
                    f"{campaign.senderCompany or 'n/a'}\n"
                    f"Offer: {campaign.senderOffer or 'n/a'}\n"
                    f"Target audience: {campaign.targetAudience or 'n/a'}\n"
                    f"Additional context: {body.additionalContext or 'n/a'}"
                ),
            },
        ]
        raw = await self._call_llm_safe(config, messages)
        parsed = self._safe_json(raw)
        return GtmThesisResponse(
            campaignId=campaign.id,
            thesis=str(parsed.get("thesis", "")),
            raw=raw,
        )
 
    # ── Helpers ─────────────────────────────────────────────────────────────
 
    async def _get_llm_config(
        self, db: AsyncSession, config_id: str | None
    ) -> Any:
        if not config_id:
            try:
                from app.services.llm_service import get_default_llm_config
 
                return await get_default_llm_config(db)
            except Exception as exc:  # noqa: BLE001
                logger.warning("campaign.default_llm_lookup_failed", error=str(exc))
                return None
        result = await db.execute(
            select(LlmConfig).where(LlmConfig.id == config_id)
        )
        return result.scalar_one_or_none()
 
    async def _call_llm_safe(
        self, config: Any, messages: list[dict[str, str]]
    ) -> str:
        try:
            from app.services.llm_service import call_llm as _call_llm
 
            if config is None:
                from app.services.llm_service import LlmService
 
                joined = "\n\n".join(m["content"] for m in messages)
                return await LlmService().generate(prompt=joined)
            result = await _call_llm(config, messages)
            return str(getattr(result, "content", result))
        except Exception as exc:  # noqa: BLE001
            logger.warning("campaign.llm_call_failed", error=str(exc))
            return ""
 
    @staticmethod
    def _safe_json(raw: str) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except (json.JSONDecodeError, ValueError):
                    return {}
            return {}
 
 
__all__ = ["CampaignService"]