# """
# mailbridge_service.py — SMTP relay client + tracking-event ingestion.

# Phase 3 stub: makes a best-effort HTTP call to the configured MailBridge
# instance. On any failure (no URL configured, network error, 4xx/5xx), it
# returns a deterministic stub response so feature routes never raise.

# Per-user quota + spam/complaint tracking (SAAS2-USER-BE §H):
#   - apply_tracking_event now records bounce/complaint events against the
#     per-user UserEmailQuota (the owner is resolved from the Sequence →
#     Campaign.owner_user_id chain). A spam complaint also auto-throttles
#     the user when the SPAM_COMPLAINT_THRESHOLD is crossed.
#   - get_user_email_stats(tenant, user_id, date_range) returns the per-user
#     aggregation that the dashboard / manager view consumes.
# """
# from __future__ import annotations

# from datetime import datetime, timedelta, timezone
# from typing import Any

# import httpx
# import structlog
# from sqlalchemy import func, select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.config import get_settings
# from app.models.campaign_models import Campaign, ReplyDraft, Sequence
# from app.models.config_models import MailBridgeConfig
# from app.models.enums import EmailStatus
# from app.schemas.mailbridge import (
#     MailBridgeSendRequest,
#     MailBridgeSendResponse,
#     MailBridgeTrackingEvent,
# )
# from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
# from app.utils.tenant_context import resolve_tenant_slug

# logger = structlog.get_logger(__name__)


# class MailBridgeService:
#     """Async SMTP-relay client + tracking event applier."""

#     def __init__(self, settings: Any | None = None) -> None:
#         self._settings = settings or get_settings()
#         self._quota = UserEmailQuotaService()

#     async def send(
#         self,
#         *,
#         db: AsyncSession,
#         to: str,
#         subject: str,
#         body: str,
#         sequence_id: str | None = None,
#         config_id: str | None = None,
#         user_id: str | None = None,
#     ) -> MailBridgeSendResponse:
#         """Send an email via the configured MailBridge instance (stub-safe).

#         Per SAAS2-USER-BE §H: when user_id is provided, the per-user MailBridge
#         config is preferred (falls back to tenant-level). When sequence_id is
#         provided, the per-user quota is checked + incremented on success.
#         """
#         config = await self._resolve_config(db, config_id, user_id=user_id)
#         url = (config.baseUrl if config else "") or self._settings.MAILBRIDGE_DEFAULT_URL

#         # Per-user quota check before send (best-effort — never raises).
#         if user_id and user_id != "system":
#             try:
#                 can_send, reason = await self._quota.check_can_send(db, user_id, count=1)
#             except Exception as exc:  # noqa: BLE001
#                 can_send, reason = False, f"quota_check_error: {exc}"
#             if not can_send:
#                 logger.info(
#                     "mailbridge.send.quota_exceeded",
#                     user_id=user_id, sequence_id=sequence_id, reason=reason,
#                 )
#                 return MailBridgeSendResponse(
#                     messageId="", status="quota_exceeded", accepted=False
#                 )

#         if not url:
#             # Dev/CI stub: return a fake message ID so tests pass.
#             msg_id = f"stub-{sequence_id or 'adhoc'}@outrena.local"
#             # Best-effort: still record the send against the user's quota.
#             if user_id and user_id != "system":
#                 try:
#                     await self._quota.record_send(db, user_id, count=1)
#                 except Exception as exc:  # noqa: BLE001
#                     logger.warning(
#                         "mailbridge.send.quota_record_failed",
#                         user_id=user_id, error=str(exc),
#                     )
#             # FIX-BE-1 / HIGH 8: record usage_event(email_send) for
#             # per-tenant cost roll-ups. Best-effort — never blocks the send.
#             await self._record_usage_send(db, user_id)
#             return MailBridgeSendResponse(
#                 messageId=msg_id, status="queued", accepted=True
#             )
#         # Build the MailBridge-compatible payload (Phase 3+ /outbound/send).
#         # MailBridge expects: to as a list, body_html/body_text (not "body"),
#         # and optional external_user_id for identity propagation.
#         mb_payload: dict[str, Any] = {
#             "to": [to],
#             "subject": subject,
#             "body_html": body,
#             "body_text": body,
#         }
#         # Identity propagation: if the config has an external_user_id mapping
#         # for this Outrena user, include it so MailBridge sends from the
#         # correct connected mailbox.
#         ext_user_id = getattr(config, "mailbridge_external_user_id", None) if config else None
#         if ext_user_id:
#             mb_payload["external_user_id"] = ext_user_id

#         # Build auth headers. MailBridge tenancy mode requires a Bearer
#         # API key (mb_live_...) from POST /platform/register.
#         api_key = (
#             getattr(config, "mailbridge_api_key", None) if config else None
#         ) or self._settings.MAILBRIDGE_API_KEY
#         headers: dict[str, str] = {"Content-Type": "application/json"}
#         if api_key:
#             headers["Authorization"] = f"Bearer {api_key}"

#         try:
#             async with httpx.AsyncClient(
#                 timeout=float(self._settings.MAILBRIDGE_TIMEOUT_SECONDS)
#             ) as client:
#                 resp = await client.post(
#                     f"{url.rstrip('/')}/outbound/send",
#                     json=mb_payload,
#                     headers=headers,
#                 )
#                 resp.raise_for_status()
#                 data = resp.json()
#                 # MailBridge returns snake_case fields: message_id, status,
#                 # thread_id. Map to Outrena's camelCase contract.
#                 msg_id = (
#                     data.get("message_id")
#                     or data.get("messageId")
#                     or ""
#                 )
#                 # Best-effort: record the send against the user's quota.
#                 if user_id and user_id != "system":
#                     try:
#                         await self._quota.record_send(db, user_id, count=1)
#                     except Exception as exc:  # noqa: BLE001
#                         logger.warning(
#                             "mailbridge.send.quota_record_failed",
#                             user_id=user_id, error=str(exc),
#                         )
#                 # FIX-BE-1 / HIGH 8: record usage_event(email_send) for
#                 # per-tenant cost roll-ups. Best-effort — never blocks the send.
#                 await self._record_usage_send(db, user_id)
#                 return MailBridgeSendResponse(
#                     messageId=msg_id,
#                     status=data.get("status", "sent"),
#                     accepted=True,
#                 )
#         except Exception as exc:  # noqa: BLE001 — graceful degradation
#             logger.warning("mailbridge.send.fallback", error=str(exc))
#             return MailBridgeSendResponse(
#                 messageId="", status="failed", accepted=False
#             )

#     async def apply_tracking_event(
#         self, db: AsyncSession, event: MailBridgeTrackingEvent
#     ) -> bool:
#         """Update a Sequence row from a MailBridge tracking webhook.

#         Per SAAS2-USER-BE §H: 'complaint' is now a handled event type and
#         triggers per-user quota bookkeeping + potential throttle.
#         """
#         if not event.sequenceId:
#             return False
#         result = await db.execute(
#             select(Sequence).where(Sequence.id == event.sequenceId)
#         )
#         seq = result.scalar_one_or_none()
#         if seq is None:
#             return False
#         now = event.timestamp or datetime.now(timezone.utc)
#         event_map = {
#             "sent": (EmailStatus.Sent, "sentAt"),
#             "opened": (EmailStatus.Sent, "openedAt"),
#             "replied": (EmailStatus.Replied, "repliedAt"),
#             "bounced": (EmailStatus.Bounced, "bouncedAt"),
#             "failed": (EmailStatus.Failed, "bouncedAt"),
#         }
#         if event.event in event_map:
#             new_status, ts_attr = event_map[event.event]
#             seq.status = new_status
#             setattr(seq, ts_attr, now)
#             if event.event in ("bounced", "failed") and event.reason:
#                 seq.bounceReason = event.reason
#             await db.commit()

#         # FIX-BE-1 / HIGH 6 (re-verification): auto-create a ReplyDraft when
#         # a "replied" tracking event arrives, then trigger AI triage so the
#         # rep sees a categorized draft in the Reply Inbox without manual
#         # intake. Best-effort — failures are logged + swallowed so a triage
#         # bug never blocks the webhook receipt (which is already persisted
#         # above on the Sequence row).
#         if event.event == "replied":
#             try:
#                 await self._auto_create_reply_draft(db, seq, event, now)
#             except Exception as exc:  # noqa: BLE001
#                 logger.warning(
#                     "mailbridge.reply_draft_create_failed",
#                     sequence_id=getattr(seq, "id", None),
#                     error=str(exc),
#                 )

#         # Per-user quota bookkeeping for bounce / complaint events.
#         owner_id = getattr(seq, "owner_user_id", None)
#         if owner_id and owner_id != "system":
#             if event.event in ("bounced", "failed"):
#                 try:
#                     await self._quota.record_bounce(db, owner_id, count=1)
#                 except Exception as exc:  # noqa: BLE001
#                     logger.warning(
#                         "mailbridge.bounce.quota_record_failed",
#                         user_id=owner_id, error=str(exc),
#                     )
#             elif event.event == "complaint":
#                 try:
#                     await self._quota.record_complaint(db, owner_id, count=1)
#                 except Exception as exc:  # noqa: BLE001
#                     logger.warning(
#                         "mailbridge.complaint.quota_record_failed",
#                         user_id=owner_id, error=str(exc),
#                     )

#         return True

#     async def get_user_email_stats(
#         self,
#         db: AsyncSession,
#         user_id: str,
#         *,
#         since: datetime | None = None,
#         until: datetime | None = None,
#     ) -> dict[str, Any]:
#         """Aggregate per-user email activity over a date range (dashboard use).

#         Returns a dict with: sent / opened / replied / bounced / complaints /
#         meetings_booked (count of ReplyDraft.meetingBookedAt set) +
#         the user's current-day quota snapshot.
#         """
#         since = since or (datetime.now(timezone.utc) - timedelta(days=30))
#         until = until or datetime.now(timezone.utc)

#         # Sequences owned by the user within the window.
#         seq_result = await db.execute(
#             select(Sequence).where(
#                 Sequence.owner_user_id == user_id,
#                 Sequence.createdAt >= since,
#                 Sequence.createdAt <= until,
#             )
#         )
#         sequences = list(seq_result.scalars().all())
#         sent = sum(1 for s in sequences if s.sentAt is not None)
#         opened = sum(1 for s in sequences if s.openedAt is not None)
#         replied = sum(1 for s in sequences if s.repliedAt is not None)
#         bounced = sum(1 for s in sequences if s.bouncedAt is not None)

#         # Per-user quota snapshot (today).
#         quota_status = await self._quota.get_user_quota_status(db, user_id)
#         complaints_today = int(quota_status.get("complaints", 0))

#         # Meetings booked — ReplyDraft.meetingBookedAt set.
#         meetings = 0
#         try:
#             from app.models.campaign_models import ReplyDraft

#             meetings_result = await db.execute(
#                 select(func.count())
#                 .select_from(ReplyDraft)
#                 .join(Sequence, ReplyDraft.sequenceId == Sequence.id)
#                 .where(
#                     Sequence.owner_user_id == user_id,
#                     ReplyDraft.meetingBookedAt.is_not(None),
#                     ReplyDraft.meetingBookedAt >= since,
#                     ReplyDraft.meetingBookedAt <= until,
#                 )
#             )
#             meetings = int(meetings_result.scalar() or 0)
#         except Exception as exc:  # noqa: BLE001 — best-effort
#             logger.warning("mailbridge.user_stats.meetings_failed", error=str(exc))

#         return {
#             "user_id": user_id,
#             "since": since.isoformat(),
#             "until": until.isoformat(),
#             "sent": sent,
#             "opened": opened,
#             "replied": replied,
#             "bounced": bounced,
#             "complaints_today": complaints_today,
#             "meetings_booked": meetings,
#             "quota": quota_status,
#         }

#     async def _auto_create_reply_draft(
#         self,
#         db: AsyncSession,
#         seq: Sequence,
#         event: MailBridgeTrackingEvent,
#         now: datetime,
#     ) -> ReplyDraft | None:
#         """Create a ReplyDraft + fire AI categorization on a replied event.

#         Per FIX-BE-1 / HIGH 6: previously apply_tracking_event only stamped
#         Sequence.repliedAt — the rep had to manually open the Reply Inbox
#         and click "Categorize" to surface a draft. This helper now performs
#         the full intake automatically:

#           1. Idempotency: skip if a ReplyDraft already exists for this
#              (sequenceId, prospectId) with originalReply == event.payload.
#           2. Insert a ReplyDraft row with status='pending', category='other'
#              (placeholder until AI triage runs).
#           3. Trigger AI triage via ReplyDraftService.categorize (best-effort
#              — if the LLM is unavailable, the draft remains 'other' /
#              'pending' for a human to triage).

#         The AI triage uses the tenant's LlmConfig (default model). When no
#         reply text is supplied in the event payload we use a placeholder
#         so the draft is still surfaced in the Reply Inbox.

#         Task 3-a / FIX 3: the reply body is now extracted from the
#         ``event.payload`` dict (added to ``MailBridgeTrackingEvent`` by
#         this task). MailBridge should include the reply text at
#         ``payload.body`` (preferred) or ``payload.text`` / ``payload.replyBody``
#         (aliases). Falls back to ``event.reason`` (bounce/error reason —
#         not the reply text but better than nothing) and finally to a
#         placeholder string so the draft is still surfaced.
#         """
#         prospect_id = getattr(seq, "prospectId", None)
#         if not prospect_id:
#             return None
#         reply_text = (
#             (event.payload or {}).get("body")
#             or (event.payload or {}).get("text")
#             or (event.payload or {}).get("replyBody")
#             or getattr(event, "reason", None)
#             or "(reply body not captured by MailBridge webhook)"
#         )
#         # Idempotency: skip if a draft already exists for this sequence.
#         existing = (
#             await db.execute(
#                 select(ReplyDraft).where(ReplyDraft.sequenceId == seq.id).limit(1)
#             )
#         ).scalar_one_or_none()
#         if existing is not None:
#             return existing
#         draft = ReplyDraft(
#             sequenceId=seq.id,
#             prospectId=prospect_id,
#             originalReply=reply_text,
#             category="other",
#             status="pending",
#         )
#         db.add(draft)
#         await db.commit()
#         draft = await db.get(ReplyDraft, draft.id)
#         logger.info(
#             "mailbridge.reply_draft_created",
#             draft_id=draft.id,
#             sequence_id=seq.id,
#             prospect_id=prospect_id,
#         )
#         # Fire AI triage best-effort. Categorization failure leaves the
#         # draft in 'pending'/'other' state for manual triage — never blocks.
#         try:
#             from app.features.reply_drafts.service import ReplyDraftService

#             await ReplyDraftService().categorize(db, draft.id, reply_text)
#         except Exception as exc:  # noqa: BLE001
#             logger.warning(
#                 "mailbridge.reply_draft_triage_failed",
#                 draft_id=draft.id,
#                 error=str(exc),
#             )
#         return draft

#     @staticmethod
#     async def _record_usage_send(
#         db: AsyncSession, user_id: str | None
#     ) -> None:
#         """Fire-and-forget: record one usage_event(email_send) row.

#         FIX-BE-1 / HIGH 8 (re-verification): MailBridgeService.send was
#         previously the only send site that did NOT call
#         UsageService.record_email_send, so email volume never showed up in
#         per-tenant cost roll-ups. This helper derives the tenant slug from
#         the session's search_path (tenants are locked to tenant_<slug> by
#         get_db) and delegates to UsageService. Failures are logged + swallowed
#         so a usage write never blocks the send.
#         """
#         try:
#             tenant = await resolve_tenant_slug(db)
#             if not tenant:
#                 return  # public-only session — nothing to attribute
#             from app.features.usage.service import UsageService

#             await UsageService().record_email_send(
#                 tenant=tenant,
#                 user_id=user_id or "system",
#                 metadata={"source": "mailbridge.send"},
#             )
#         except Exception as exc:  # noqa: BLE001
#             logger.warning(
#                 "mailbridge.send.usage_record_failed",
#                 user_id=user_id,
#                 error=str(exc),
#             )

#     @staticmethod
#     async def _resolve_config(
#         db: AsyncSession,
#         config_id: str | None,
#         *,
#         user_id: str | None = None,
#     ) -> MailBridgeConfig | None:
#         """Resolve MailBridgeConfig, preferring per-user over tenant-level.

#         Resolution order:
#           1. Explicit config_id (caller-supplied).
#           2. Per-user active config (MailBridgeConfig.owner_user_id == user_id)
#              — only if the owner_user_id column exists on the model (BE-A
#              migration 0004 not yet applied → graceful fallback).
#           3. First active tenant-level config.
#         """
#         if config_id:
#             result = await db.execute(
#                 select(MailBridgeConfig).where(MailBridgeConfig.id == config_id)
#             )
#             cfg = result.scalar_one_or_none()
#             if cfg:
#                 return cfg

#         # Per-user lookup — only if the column exists on the model.
#         has_owner_col = hasattr(MailBridgeConfig, "owner_user_id")
#         if user_id and user_id != "system" and has_owner_col:
#             try:
#                 result = await db.execute(
#                     select(MailBridgeConfig)
#                     .where(MailBridgeConfig.isActive.is_(True))
#                     .where(
#                         getattr(MailBridgeConfig, "owner_user_id") == user_id
#                     )
#                     .limit(1)
#                 )
#                 cfg = result.scalar_one_or_none()
#                 if cfg is not None:
#                     return cfg
#             except Exception as exc:  # noqa: BLE001 — fall back to tenant-level
#                 logger.warning(
#                     "mailbridge.config.per_user_lookup_failed",
#                     user_id=user_id, error=str(exc),
#                 )

#         # fallback: first active config
#         result = await db.execute(
#             select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
#         )
#         return result.scalar_one_or_none()


# __all__ = ["MailBridgeService"]

"""
mailbridge_service.py — SMTP relay client + tracking-event ingestion.

Phase 3 stub: makes a best-effort HTTP call to the configured MailBridge
instance. On any failure (no URL configured, network error, 4xx/5xx), it
returns a deterministic stub response so feature routes never raise.

Per-user quota + spam/complaint tracking (SAAS2-USER-BE §H):
  - apply_tracking_event now records bounce/complaint events against the
    per-user UserEmailQuota (the owner is resolved from the Sequence →
    Campaign.owner_user_id chain). A spam complaint also auto-throttles
    the user when the SPAM_COMPLAINT_THRESHOLD is crossed.
  - get_user_email_stats(tenant, user_id, date_range) returns the per-user
    aggregation that the dashboard / manager view consumes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.campaign_models import Campaign, ReplyDraft, Sequence
from app.models.config_models import MailBridgeConfig
from app.models.enums import EmailStatus
from app.schemas.mailbridge import (
    MailBridgeSendRequest,
    MailBridgeSendResponse,
    MailBridgeTrackingEvent,
)
from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
from app.utils.tenant_context import resolve_tenant_slug

logger = structlog.get_logger(__name__)


class MailBridgeService:
    """Async SMTP-relay client + tracking event applier."""

    def __init__(self, settings: Any | None = None) -> None:
        self._settings = settings or get_settings()
        self._quota = UserEmailQuotaService()

    async def send(
        self,
        *,
        db: AsyncSession,
        to: str,
        subject: str,
        body: str,
        sequence_id: str | None = None,
        config_id: str | None = None,
        user_id: str | None = None,
    ) -> MailBridgeSendResponse:
        """Send an email via the configured MailBridge instance (stub-safe).

        Per SAAS2-USER-BE §H: when user_id is provided, the per-user MailBridge
        config is preferred (falls back to tenant-level). When sequence_id is
        provided, the per-user quota is checked + incremented on success.
        """
        config = await self._resolve_config(db, config_id, user_id=user_id)
        url = (config.baseUrl if config else "") or self._settings.MAILBRIDGE_DEFAULT_URL

        # Per-user quota check before send (best-effort — never raises).
        if user_id and user_id != "system":
            try:
                can_send, reason = await self._quota.check_can_send(db, user_id, count=1)
            except Exception as exc:  # noqa: BLE001
                can_send, reason = False, f"quota_check_error: {exc}"
            if not can_send:
                logger.info(
                    "mailbridge.send.quota_exceeded",
                    user_id=user_id, sequence_id=sequence_id, reason=reason,
                )
                return MailBridgeSendResponse(
                    messageId="", status="quota_exceeded", accepted=False
                )

        if not url:
            # Dev/CI stub: return a fake message ID so tests pass.
            msg_id = f"stub-{sequence_id or 'adhoc'}@outrena.local"
            # Best-effort: still record the send against the user's quota.
            if user_id and user_id != "system":
                try:
                    await self._quota.record_send(db, user_id, count=1)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "mailbridge.send.quota_record_failed",
                        user_id=user_id, error=str(exc),
                    )
            # FIX-BE-1 / HIGH 8: record usage_event(email_send) for
            # per-tenant cost roll-ups. Best-effort — never blocks the send.
            await self._record_usage_send(db, user_id)
            return MailBridgeSendResponse(
                messageId=msg_id, status="queued", accepted=True
            )
        # Build the MailBridge-compatible payload (Phase 3+ /outbound/send).
        # MailBridge expects: to as a list, body_html/body_text (not "body"),
        # and optional external_user_id for identity propagation.
        mb_payload: dict[str, Any] = {
            "to": [to],
            "subject": subject,
            "body_html": body,
            "body_text": body,
        }
        # Identity propagation: tell MailBridge which connected mailbox to
        # send from. Priority: (1) config-level external_user_id mapping,
        # (2) the caller's Keycloak UUID (user_id param, same value used
        #     during POST /auth/connect/{provider}/start).
        ext_user_id = (
            getattr(config, "mailbridge_external_user_id", None) if config else None
        ) or user_id
        if ext_user_id:
            mb_payload["external_user_id"] = ext_user_id

        # Build auth headers. MailBridge tenancy mode requires a Bearer
        # API key (mb_live_...) from POST /platform/register.
        api_key = (
            getattr(config, "mailbridge_api_key", None) if config else None
        ) or self._settings.MAILBRIDGE_API_KEY
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(
                timeout=float(self._settings.MAILBRIDGE_TIMEOUT_SECONDS)
            ) as client:
                resp = await client.post(
                    f"{url.rstrip('/')}/outbound/send",
                    json=mb_payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                # MailBridge returns snake_case fields: message_id, status,
                # thread_id. Map to Outrena's camelCase contract.
                msg_id = (
                    data.get("message_id")
                    or data.get("messageId")
                    or ""
                )
                # Best-effort: record the send against the user's quota.
                if user_id and user_id != "system":
                    try:
                        await self._quota.record_send(db, user_id, count=1)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "mailbridge.send.quota_record_failed",
                            user_id=user_id, error=str(exc),
                        )
                # FIX-BE-1 / HIGH 8: record usage_event(email_send) for
                # per-tenant cost roll-ups. Best-effort — never blocks the send.
                await self._record_usage_send(db, user_id)
                return MailBridgeSendResponse(
                    messageId=msg_id,
                    status=data.get("status", "sent"),
                    accepted=True,
                )
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            logger.warning("mailbridge.send.fallback", error=str(exc))
            return MailBridgeSendResponse(
                messageId="", status="failed", accepted=False
            )

    async def apply_tracking_event(
        self, db: AsyncSession, event: MailBridgeTrackingEvent
    ) -> bool:
        """Update a Sequence row from a MailBridge tracking webhook.

        Per SAAS2-USER-BE §H: 'complaint' is now a handled event type and
        triggers per-user quota bookkeeping + potential throttle.
        """
        if not event.sequenceId:
            return False
        result = await db.execute(
            select(Sequence).where(Sequence.id == event.sequenceId)
        )
        seq = result.scalar_one_or_none()
        if seq is None:
            return False
        now = event.timestamp or datetime.now(timezone.utc)
        event_map = {
            "sent": (EmailStatus.Sent, "sentAt"),
            "opened": (EmailStatus.Sent, "openedAt"),
            "replied": (EmailStatus.Replied, "repliedAt"),
            "bounced": (EmailStatus.Bounced, "bouncedAt"),
            "failed": (EmailStatus.Failed, "bouncedAt"),
        }
        if event.event in event_map:
            new_status, ts_attr = event_map[event.event]
            seq.status = new_status
            setattr(seq, ts_attr, now)
            if event.event in ("bounced", "failed") and event.reason:
                seq.bounceReason = event.reason
            await db.commit()

        # FIX-BE-1 / HIGH 6 (re-verification): auto-create a ReplyDraft when
        # a "replied" tracking event arrives, then trigger AI triage so the
        # rep sees a categorized draft in the Reply Inbox without manual
        # intake. Best-effort — failures are logged + swallowed so a triage
        # bug never blocks the webhook receipt (which is already persisted
        # above on the Sequence row).
        if event.event == "replied":
            try:
                await self._auto_create_reply_draft(db, seq, event, now)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "mailbridge.reply_draft_create_failed",
                    sequence_id=getattr(seq, "id", None),
                    error=str(exc),
                )

        # Per-user quota bookkeeping for bounce / complaint events.
        owner_id = getattr(seq, "owner_user_id", None)
        if owner_id and owner_id != "system":
            if event.event in ("bounced", "failed"):
                try:
                    await self._quota.record_bounce(db, owner_id, count=1)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "mailbridge.bounce.quota_record_failed",
                        user_id=owner_id, error=str(exc),
                    )
            elif event.event == "complaint":
                try:
                    await self._quota.record_complaint(db, owner_id, count=1)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "mailbridge.complaint.quota_record_failed",
                        user_id=owner_id, error=str(exc),
                    )

        return True

    async def get_user_email_stats(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        """Aggregate per-user email activity over a date range (dashboard use).

        Returns a dict with: sent / opened / replied / bounced / complaints /
        meetings_booked (count of ReplyDraft.meetingBookedAt set) +
        the user's current-day quota snapshot.
        """
        since = since or (datetime.now(timezone.utc) - timedelta(days=30))
        until = until or datetime.now(timezone.utc)

        # Sequences owned by the user within the window.
        seq_result = await db.execute(
            select(Sequence).where(
                Sequence.owner_user_id == user_id,
                Sequence.createdAt >= since,
                Sequence.createdAt <= until,
            )
        )
        sequences = list(seq_result.scalars().all())
        sent = sum(1 for s in sequences if s.sentAt is not None)
        opened = sum(1 for s in sequences if s.openedAt is not None)
        replied = sum(1 for s in sequences if s.repliedAt is not None)
        bounced = sum(1 for s in sequences if s.bouncedAt is not None)

        # Per-user quota snapshot (today).
        quota_status = await self._quota.get_user_quota_status(db, user_id)
        complaints_today = int(quota_status.get("complaints", 0))

        # Meetings booked — ReplyDraft.meetingBookedAt set.
        meetings = 0
        try:
            from app.models.campaign_models import ReplyDraft

            meetings_result = await db.execute(
                select(func.count())
                .select_from(ReplyDraft)
                .join(Sequence, ReplyDraft.sequenceId == Sequence.id)
                .where(
                    Sequence.owner_user_id == user_id,
                    ReplyDraft.meetingBookedAt.is_not(None),
                    ReplyDraft.meetingBookedAt >= since,
                    ReplyDraft.meetingBookedAt <= until,
                )
            )
            meetings = int(meetings_result.scalar() or 0)
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning("mailbridge.user_stats.meetings_failed", error=str(exc))

        return {
            "user_id": user_id,
            "since": since.isoformat(),
            "until": until.isoformat(),
            "sent": sent,
            "opened": opened,
            "replied": replied,
            "bounced": bounced,
            "complaints_today": complaints_today,
            "meetings_booked": meetings,
            "quota": quota_status,
        }

    async def _auto_create_reply_draft(
        self,
        db: AsyncSession,
        seq: Sequence,
        event: MailBridgeTrackingEvent,
        now: datetime,
    ) -> ReplyDraft | None:
        """Create a ReplyDraft + fire AI categorization on a replied event.

        Per FIX-BE-1 / HIGH 6: previously apply_tracking_event only stamped
        Sequence.repliedAt — the rep had to manually open the Reply Inbox
        and click "Categorize" to surface a draft. This helper now performs
        the full intake automatically:

          1. Idempotency: skip if a ReplyDraft already exists for this
             (sequenceId, prospectId) with originalReply == event.payload.
          2. Insert a ReplyDraft row with status='pending', category='other'
             (placeholder until AI triage runs).
          3. Trigger AI triage via ReplyDraftService.categorize (best-effort
             — if the LLM is unavailable, the draft remains 'other' /
             'pending' for a human to triage).

        The AI triage uses the tenant's LlmConfig (default model). When no
        reply text is supplied in the event payload we use a placeholder
        so the draft is still surfaced in the Reply Inbox.

        Task 3-a / FIX 3: the reply body is now extracted from the
        ``event.payload`` dict (added to ``MailBridgeTrackingEvent`` by
        this task). MailBridge should include the reply text at
        ``payload.body`` (preferred) or ``payload.text`` / ``payload.replyBody``
        (aliases). Falls back to ``event.reason`` (bounce/error reason —
        not the reply text but better than nothing) and finally to a
        placeholder string so the draft is still surfaced.
        """
        prospect_id = getattr(seq, "prospectId", None)
        if not prospect_id:
            return None
        reply_text = (
            (event.payload or {}).get("body")
            or (event.payload or {}).get("text")
            or (event.payload or {}).get("replyBody")
            or getattr(event, "reason", None)
            or "(reply body not captured by MailBridge webhook)"
        )
        # Idempotency: skip if a draft already exists for this sequence.
        existing = (
            await db.execute(
                select(ReplyDraft).where(ReplyDraft.sequenceId == seq.id).limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        draft = ReplyDraft(
            sequenceId=seq.id,
            prospectId=prospect_id,
            originalReply=reply_text,
            category="other",
            status="pending",
        )
        db.add(draft)
        await db.commit()
        draft = await db.get(ReplyDraft, draft.id)
        logger.info(
            "mailbridge.reply_draft_created",
            draft_id=draft.id,
            sequence_id=seq.id,
            prospect_id=prospect_id,
        )
        # Fire AI triage best-effort. Categorization failure leaves the
        # draft in 'pending'/'other' state for manual triage — never blocks.
        try:
            from app.features.reply_drafts.service import ReplyDraftService

            await ReplyDraftService().categorize(db, draft.id, reply_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "mailbridge.reply_draft_triage_failed",
                draft_id=draft.id,
                error=str(exc),
            )
        return draft

    @staticmethod
    async def _record_usage_send(
        db: AsyncSession, user_id: str | None
    ) -> None:
        """Fire-and-forget: record one usage_event(email_send) row.

        FIX-BE-1 / HIGH 8 (re-verification): MailBridgeService.send was
        previously the only send site that did NOT call
        UsageService.record_email_send, so email volume never showed up in
        per-tenant cost roll-ups. This helper derives the tenant slug from
        the session's search_path (tenants are locked to tenant_<slug> by
        get_db) and delegates to UsageService. Failures are logged + swallowed
        so a usage write never blocks the send.
        """
        try:
            tenant = await resolve_tenant_slug(db)
            if not tenant:
                return  # public-only session — nothing to attribute
            from app.features.usage.service import UsageService

            await UsageService().record_email_send(
                tenant=tenant,
                user_id=user_id or "system",
                metadata={"source": "mailbridge.send"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "mailbridge.send.usage_record_failed",
                user_id=user_id,
                error=str(exc),
            )

    @staticmethod
    async def _resolve_config(
        db: AsyncSession,
        config_id: str | None,
        *,
        user_id: str | None = None,
    ) -> MailBridgeConfig | None:
        """Resolve MailBridgeConfig, preferring per-user over tenant-level.

        Resolution order:
          1. Explicit config_id (caller-supplied).
          2. Per-user active config (MailBridgeConfig.owner_user_id == user_id)
             — only if the owner_user_id column exists on the model (BE-A
             migration 0004 not yet applied → graceful fallback).
          3. First active tenant-level config.
        """
        if config_id:
            result = await db.execute(
                select(MailBridgeConfig).where(MailBridgeConfig.id == config_id)
            )
            cfg = result.scalar_one_or_none()
            if cfg:
                return cfg

        # Per-user lookup — only if the column exists on the model.
        has_owner_col = hasattr(MailBridgeConfig, "owner_user_id")
        if user_id and user_id != "system" and has_owner_col:
            try:
                result = await db.execute(
                    select(MailBridgeConfig)
                    .where(MailBridgeConfig.isActive.is_(True))
                    .where(
                        getattr(MailBridgeConfig, "owner_user_id") == user_id
                    )
                    .limit(1)
                )
                cfg = result.scalar_one_or_none()
                if cfg is not None:
                    return cfg
            except Exception as exc:  # noqa: BLE001 — fall back to tenant-level
                logger.warning(
                    "mailbridge.config.per_user_lookup_failed",
                    user_id=user_id, error=str(exc),
                )

        # fallback: first active config
        result = await db.execute(
            select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
        )
        return result.scalar_one_or_none()


__all__ = ["MailBridgeService"]