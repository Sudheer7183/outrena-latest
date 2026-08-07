"""linkedin_service.py — LinkedIn config + engagement + inbox triage + ICP match."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase3_models import (
    LinkedInConfig,
    LinkedInEngagement,
    LinkedInInboxMessage,
)
from app.models.prospect_models import IcpProfile, Prospect
from app.schemas.linkedin import (
    IcpMatchRequest,
    IcpMatchResponse,
    IcpMatchResult,
    LinkedInConfigCreate,
    LinkedInConfigUpdate,
    LinkedInEngagementCreate,
    LinkedInEngagementUpdate,
    LinkedInInboxTriageRequest,
)
from app.services.llm_service import get_llm_service, get_default_llm_config
from app.utils.tenant_context import resolve_tenant_slug

logger = structlog.get_logger(__name__)


class LinkedInService:
    # ── Config ─────────────────────────────────────────────────────────────
    async def list_configs(self, db: AsyncSession) -> list[LinkedInConfig]:
        result = await db.execute(select(LinkedInConfig))
        return list(result.scalars().all())

    async def get_config(
        self, db: AsyncSession, config_id: str
    ) -> LinkedInConfig | None:
        result = await db.execute(
            select(LinkedInConfig).where(LinkedInConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def create_config(
        self, db: AsyncSession, body: LinkedInConfigCreate
    ) -> LinkedInConfig:
        item = LinkedInConfig(**body.model_dump())
        db.add(item)
        await db.commit()
        item = await db.get(LinkedInConfig, item.id)
        return item

    async def update_config(
        self, db: AsyncSession, config_id: str, body: LinkedInConfigUpdate
    ) -> LinkedInConfig | None:
        item = await self.get_config(db, config_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(LinkedInConfig, item.id)
        return item

    async def delete_config(self, db: AsyncSession, config_id: str) -> bool:
        item = await self.get_config(db, config_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    # ── Engagement ─────────────────────────────────────────────────────────
    async def list_engagements(
        self, db: AsyncSession, *, prospect_id: str | None = None
    ) -> list[LinkedInEngagement]:
        stmt = select(LinkedInEngagement)
        if prospect_id:
            stmt = stmt.where(LinkedInEngagement.prospectId == prospect_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_engagement(
        self,
        db: AsyncSession,
        body: LinkedInEngagementCreate,
        *,
        user_id: str | None = None,
    ) -> LinkedInEngagement:
        """Create a LinkedIn engagement row + record usage.

        Task 3-a / FIX 2: ``user_id`` is the Keycloak sub of the caller
        (from the request's ``TokenPayload``). It is stamped onto the new
        engagement row's ``owner_user_id`` column (added by migration 0011)
        so per-user engagement queries + usage attribution work end-to-end.

        Fallbacks (in order) when ``user_id`` is None:
          1. ``body.owner_user_id`` (if the caller explicitly passed one).
          2. ``"system"`` (legacy placeholder — preserves prior behaviour
             for callers without a token context, e.g. internal jobs).
        """
        owner_user_id = user_id or body.owner_user_id or "system"
        item = LinkedInEngagement(
            **body.model_dump(exclude={"owner_user_id"}),
            status="pending",
            owner_user_id=owner_user_id,
        )
        db.add(item)
        await db.commit()
        item = await db.get(LinkedInEngagement, item.id)
        # FIX-BE-1 / HIGH 8 (re-verification): record one usage_event
        # (linkedin_action) for per-tenant cost roll-ups. Best-effort —
        # never blocks the engagement create. Task 3-a / FIX 2: now passes
        # the real owner_user_id (instead of "system") so per-user cost
        # roll-ups attribute LinkedIn volume correctly.
        await self._record_usage(db, count=1, user_id=owner_user_id)
        return item

    async def update_engagement(
        self,
        db: AsyncSession,
        engagement_id: str,
        body: LinkedInEngagementUpdate,
    ) -> LinkedInEngagement | None:
        result = await db.execute(
            select(LinkedInEngagement).where(LinkedInEngagement.id == engagement_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None
        prior_status = item.status
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(LinkedInEngagement, item.id)
        # FIX-BE-1 / HIGH 8 (re-verification): record one usage_event
        # (linkedin_action) when an engagement transitions to a terminal
        # 'done' state — that's when the actual LinkedIn API call happens
        # (sent connection request, sent message, etc.). Best-effort.
        # Task 3-a / FIX 2: attribute to the engagement's owner_user_id
        # (falls back to "system" for legacy rows where it's NULL).
        if prior_status != "done" and item.status == "done":
            await self._record_usage(
                db, count=1, user_id=getattr(item, "owner_user_id", None)
            )
        return item

    # ── Inbox ──────────────────────────────────────────────────────────────
    async def list_inbox(
        self, db: AsyncSession, *, status: str | None = None
    ) -> list[LinkedInInboxMessage]:
        stmt = select(LinkedInInboxMessage).order_by(
            LinkedInInboxMessage.receivedAt.desc()
        )
        if status:
            stmt = stmt.where(LinkedInInboxMessage.status == status)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def triage(
        self, db: AsyncSession, body: LinkedInInboxTriageRequest
    ) -> int:
        """Bulk-update inbox message status. Returns count updated."""
        if not body.messageIds:
            return 0
        result = await db.execute(
            select(LinkedInInboxMessage).where(
                LinkedInInboxMessage.id.in_(body.messageIds)
            )
        )
        items = list(result.scalars().all())
        now = datetime.now(timezone.utc)
        for item in items:
            item.status = body.status
            item.triagedAt = now
        await db.commit()
        return len(items)

    @staticmethod
    async def _get_llm_config(db: AsyncSession, llm_config_id: str | None):
        """Resolve an LlmConfig by ID or fall back to the tenant default."""
        from app.models.config_models import LlmConfig
        if llm_config_id is not None:
            result = await db.execute(
                select(LlmConfig).where(LlmConfig.id == llm_config_id).limit(1)
            )
            return result.scalar_one_or_none()
        return await get_default_llm_config(db)

    @staticmethod
    def _parse_llm_json(raw) -> dict:
        """Parse LLM output that may be a dict or a JSON string."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(text)
        return {}

    # ── ICP Match ─────────────────────────────────────────────────────────────
    async def check_icp_matches(
        self, db: AsyncSession, body: IcpMatchRequest
    ) -> IcpMatchResponse:
        """Batch-check LinkedIn engagements against ICP profiles using LLM."""
        llm = get_llm_service()

        # Get unchecked engagements (isIcpMatch is NULL)
        stmt = select(LinkedInEngagement).where(LinkedInEngagement.isIcpMatch == None).limit(20)  # noqa: E711
        result = await db.execute(stmt)
        engagements = list(result.scalars().all())

        if not engagements:
            return IcpMatchResponse(success=True, checked=0, matches=[])

        # Get ICP profiles
        icp_stmt = select(IcpProfile)
        icp_result = await db.execute(icp_stmt)
        icp_profiles = list(icp_result.scalars().all())

        icp_descriptions = []
        for icp in icp_profiles:
            icp_descriptions.append({
                "id": str(icp.id),
                "name": icp.name,
                "persona": getattr(icp, 'persona', '') or '',
                "companyType": getattr(icp, 'companyType', '') or '',
                "painPoints": getattr(icp, 'painPoints', []) or [],
                "valueProps": getattr(icp, 'valueProps', []) or [],
            })

        # Build engagement info with prospect details via join
        engagement_ids = [e.id for e in engagements]
        prospect_ids = [e.prospectId for e in engagements if e.prospectId]

        prospect_map: dict[str, Prospect] = {}
        if prospect_ids:
            p_result = await db.execute(
                select(Prospect).where(Prospect.id.in_(prospect_ids))
            )
            for p in p_result.scalars().all():
                prospect_map[str(p.id)] = p

        batch_info = []
        for e in engagements:
            prospect = prospect_map.get(str(e.prospectId)) if e.prospectId else None
            batch_info.append({
                "id": str(e.id),
                "name": f"{prospect.firstName} {prospect.lastName}" if prospect else "Unknown",
                "title": (prospect.title or "") if prospect else "",
                "company": (prospect.company or "") if prospect else "",
            })

        prompt = f"""You are analyzing LinkedIn engagers to determine if they match any ICP profiles.

ICP Profiles: {json.dumps(icp_descriptions)}

Engagers to check: {json.dumps(batch_info)}

For each engager, determine:
1. Do they match any ICP? If yes, which one?
2. What's the match reason?
3. What connection note would you suggest?

Return JSON:
{{
  "results": [
    {{"engagement_id": "...", "is_icp_match": true, "icp_profile_id": "...", "icp_profile_name": "...", "match_reason": "...", "suggested_note": "..."}},
    ...
  ]
}}"""
        try:
            raw = await asyncio.wait_for(llm.generate_json(prompt=prompt), timeout=60)
            if isinstance(raw, str):
                raw = self._parse_llm_json(raw)

            matches = []
            for r in raw.get("results", []):
                # Update engagement in DB
                eng = next((e for e in engagements if str(e.id) == r.get("engagement_id")), None)
                if eng:
                    try:
                        eng.isIcpMatch = r.get("is_icp_match", False)
                        if r.get("icp_profile_id"):
                            eng.icpProfileId = r["icp_profile_id"]
                        eng.suggestedNote = r.get("suggested_note", "")
                    except Exception:
                        pass
                matches.append(IcpMatchResult(
                    engagement_id=r.get("engagement_id", ""),
                    is_icp_match=r.get("is_icp_match", False),
                    icp_profile_id=r.get("icp_profile_id"),
                    icp_profile_name=r.get("icp_profile_name"),
                    match_reason=r.get("match_reason"),
                    suggested_note=r.get("suggested_note"),
                ))

            await db.commit()
            return IcpMatchResponse(success=True, checked=len(engagements), matches=matches)
        except Exception as e:
            logger.error("ICP match check failed: %s", e)
            return IcpMatchResponse(success=False, error=str(e))

    @staticmethod
    async def _record_usage(
        db: AsyncSession, *, count: int = 1, user_id: str | None = None
    ) -> None:
        """Fire-and-forget: record N usage_event(linkedin_action) rows.

        FIX-BE-1 / HIGH 8 (re-verification): LinkedInService never called
        UsageService.record_linkedin_action, so LinkedIn automation volume
        never showed up in per-tenant cost roll-ups. Best-effort — failures
        are logged + swallowed.

        Task 3-a / FIX 2: ``user_id`` is now the LinkedInEngagement's
        ``owner_user_id`` (the Keycloak sub of the rep who triggered the
        action). Falls back to ``"system"`` for legacy rows where the
        column is NULL or for internal jobs that don't have a user context.
        """
        try:
            tenant = await resolve_tenant_slug(db)
            if not tenant:
                return
            from app.features.usage.service import UsageService

            await UsageService().record_linkedin_action(
                tenant=tenant,
                user_id=user_id or "system",
                action_count=count,
                metadata={"source": "linkedin_service"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "linkedin.usage_record_failed",
                count=count,
                user_id=user_id,
                error=str(exc),
            )
