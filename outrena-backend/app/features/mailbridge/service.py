

# # """
# # mailbridge_service.py — SMTP relay client + tracking-event ingestion.

# # FIX (search_path crash on send):
# #   UserEmailQuotaService.check_can_send() and record_send() both call
# #   db.commit() on the shared request-scoped session. After each commit,
# #   asyncpg re-pools the connection and clears search_path. When
# #   SequenceService.send_email() then tries to commit its own Sequence
# #   UPDATE on that same session, PostgreSQL cannot find the "Sequence"
# #   table because search_path is gone → UndefinedTableError.

# #   Fix: all quota and usage bookkeeping inside send() now opens a
# #   short-lived AsyncSessionLocal() with its own search_path — exactly
# #   the pattern UsageService.record_event() already uses. The request-
# #   scoped db passed into send() is NEVER committed inside this method;
# #   it is used only for read-only lookups (resolve_config).

# # FIX (wrong sender mailbox):
# #   ext_user_id was resolved as:
# #     getattr(config, "mailbridge_external_user_id", None) or user_id
# #   For a tenant-level config (owner_user_id=NULL), mailbridge_external_user_id
# #   holds the first user who ever connected — so every subsequent user's
# #   send went through that first mailbox. Fix: only use the config's
# #   mailbridge_external_user_id when the config is explicitly owned by
# #   this user (owner_user_id == user_id). Otherwise always use user_id
# #   directly, which is the Keycloak UUID MailBridge registered during
# #   POST /connect/{provider}/start.
# # """
# # from __future__ import annotations

# # from datetime import datetime, timedelta, timezone
# # from typing import Any

# # import httpx
# # import structlog
# # from sqlalchemy import func, select, text
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.core.config import get_settings
# # from app.core.database import AsyncSessionLocal
# # from app.models.campaign_models import Campaign, ReplyDraft, Sequence
# # from app.models.config_models import MailBridgeConfig
# # from app.models.enums import EmailStatus
# # from app.schemas.mailbridge import (
# #     MailBridgeSendRequest,
# #     MailBridgeSendResponse,
# #     MailBridgeTrackingEvent,
# # )
# # from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
# # from app.utils.tenant_context import resolve_tenant_slug

# # logger = structlog.get_logger(__name__)


# # # ── Internal helpers for isolated-session bookkeeping ─────────────────────────

# # async def _quota_check_isolated(
# #     tenant_schema: str, user_id: str
# # ) -> tuple[bool, str]:
# #     """Run check_can_send in a fresh session so it never touches the caller's db.

# #     Opens AsyncSessionLocal, sets search_path to the tenant schema, runs the
# #     pre-send quota gate, closes the session. The caller's request-scoped db
# #     is never modified.
# #     """
# #     try:
# #         async with AsyncSessionLocal() as session:
# #             await session.execute(
# #                 text(f'SET search_path TO "{tenant_schema}", public')
# #             )
# #             svc = UserEmailQuotaService()
# #             can_send, reason = await svc.check_can_send(session, user_id, count=1)
# #             return can_send, reason
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning(
# #             "mailbridge.quota_check_isolated.failed",
# #             user_id=user_id,
# #             error=str(exc),
# #         )
# #         # On error, allow the send rather than blocking it — quota is best-effort.
# #         return True, "quota_check_error"


# # async def _record_quota_and_usage_isolated(
# #     tenant_schema: str,
# #     tenant_slug: str,
# #     user_id: str,
# #     *,
# #     send_succeeded: bool,
# # ) -> None:
# #     """Record quota increment + usage event in a fresh session.

# #     Opens AsyncSessionLocal, sets search_path, records send (quota) and
# #     usage_event. Failures are logged and swallowed — never blocks the caller.
# #     """
# #     if not send_succeeded:
# #         return
# #     try:
# #         async with AsyncSessionLocal() as session:
# #             await session.execute(
# #                 text(f'SET search_path TO "{tenant_schema}", public')
# #             )
# #             svc = UserEmailQuotaService()
# #             await svc.record_send(session, user_id, count=1)
# #             # session.commit() is called inside record_send — safe because
# #             # this is an isolated session, not the request-scoped one.
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning(
# #             "mailbridge.record_quota_isolated.failed",
# #             user_id=user_id,
# #             error=str(exc),
# #         )
# #     # Usage event goes through its own AsyncSessionLocal inside record_event.
# #     try:
# #         from app.features.usage.service import UsageService
# #         await UsageService().record_email_send(
# #             tenant=tenant_slug,
# #             user_id=user_id,
# #             metadata={"source": "mailbridge.send"},
# #         )
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning(
# #             "mailbridge.record_usage_isolated.failed",
# #             user_id=user_id,
# #             error=str(exc),
# #         )


# # class MailBridgeService:
# #     """Async SMTP-relay client + tracking event applier."""

# #     def __init__(self, settings: Any | None = None) -> None:
# #         self._settings = settings or get_settings()
# #         self._quota = UserEmailQuotaService()

# #     async def send(
# #         self,
# #         *,
# #         db: AsyncSession,
# #         to: str,
# #         subject: str,
# #         body: str,
# #         sequence_id: str | None = None,
# #         config_id: str | None = None,
# #         user_id: str | None = None,
# #     ) -> MailBridgeSendResponse:
# #         """Send an email via the configured MailBridge instance (stub-safe).

# #         CRITICAL: This method never calls db.commit(). All side-effect work
# #         (quota check, quota record, usage record) runs in isolated sessions
# #         via AsyncSessionLocal so the caller's request-scoped db is left clean
# #         for the caller to commit its own Sequence UPDATE.
# #         """
# #         # Resolve config using the read-only request db — no commit needed.
# #         config = await self._resolve_config(db, config_id, user_id=user_id)
# #         url = (config.baseUrl if config else "") or self._settings.MAILBRIDGE_DEFAULT_URL

# #         # Derive tenant info once from the request db before any isolated sessions.
# #         tenant_slug = ""
# #         tenant_schema = ""
# #         try:
# #             tenant_slug = await resolve_tenant_slug(db)
# #             if tenant_slug:
# #                 tenant_schema = f"tenant_{tenant_slug}"
# #         except Exception as exc:  # noqa: BLE001
# #             logger.warning("mailbridge.send.tenant_resolve_failed", error=str(exc))

# #         # Pre-send quota check — isolated session, never touches request db.
# #         if user_id and user_id != "system" and tenant_schema:
# #             can_send, reason = await _quota_check_isolated(tenant_schema, user_id)
# #             if not can_send:
# #                 logger.info(
# #                     "mailbridge.send.quota_exceeded",
# #                     user_id=user_id,
# #                     sequence_id=sequence_id,
# #                     reason=reason,
# #                 )
# #                 return MailBridgeSendResponse(
# #                     messageId="", status="quota_exceeded", accepted=False
# #                 )

# #         if not url:
# #             # Dev/CI stub — no MailBridge configured.
# #             msg_id = f"stub-{sequence_id or 'adhoc'}@outrena.local"
# #             if user_id and user_id != "system" and tenant_schema:
# #                 await _record_quota_and_usage_isolated(
# #                     tenant_schema, tenant_slug, user_id, send_succeeded=True
# #                 )
# #             return MailBridgeSendResponse(
# #                 messageId=msg_id, status="queued", accepted=True
# #             )

# #         # ── Resolve the prospect's unsubscribe token and replace the placeholder ──
# #         # {{unsubscribe_url}} is written into bodyCopy at generation time.
# #         # We resolve the real URL here, at send time, using the prospect's
# #         # unsubscribeToken stored in the DB. This avoids storing live URLs in
# #         # the Sequence row, which would break if the domain changes.
# #         body_for_send = body
# #         if "{{unsubscribe_url}}" in body_for_send:
# #             try:
# #                 from app.models.campaign_models import Sequence as _SendSeq
# #                 from app.models.prospect_models import Prospect as _SendProspect
# #                 _unsubscribe_token: str | None = None
# #                 if sequence_id:
# #                     _seq_lookup = await db.execute(
# #                         select(_SendSeq).where(_SendSeq.id == sequence_id)
# #                     )
# #                     _seq_row = _seq_lookup.scalar_one_or_none()
# #                     if _seq_row:
# #                         _p_lookup = await db.execute(
# #                             select(_SendProspect).where(
# #                                 _SendProspect.id == _seq_row.prospectId
# #                             )
# #                         )
# #                         _prospect_row = _p_lookup.scalar_one_or_none()
# #                         if _prospect_row:
# #                             _unsubscribe_token = getattr(
# #                                 _prospect_row, "unsubscribeToken", None
# #                             )

# #                 if _unsubscribe_token:
# #                     _scheme = "https" if self._settings.ENVIRONMENT != "development" else "https"
# #                     _real_unsubscribe_url = (
# #                         f"{_scheme}://{self._settings.BASE_DOMAIN}"
# #                         f"/p/unsubscribe?token={_unsubscribe_token}"
# #                     )
# #                 else:
# #                     # Fallback: link to the public unsubscribe page without token
# #                     # (user will need to enter their email manually).
# #                     _scheme = "https" if self._settings.ENVIRONMENT != "development" else "http"
# #                     _real_unsubscribe_url = (
# #                         f"{_scheme}://{self._settings.BASE_DOMAIN}/p/unsubscribe"
# #                     )

# #                 body_for_send = body_for_send.replace(
# #                     "{{unsubscribe_url}}", _real_unsubscribe_url
# #                 )
# #             except Exception as _unsub_exc:  # noqa: BLE001 — never block send
# #                 logger.warning(
# #                     "mailbridge.send.unsubscribe_token_resolve_failed",
# #                     sequence_id=sequence_id,
# #                     error=str(_unsub_exc),
# #                 )
# #                 # Leave the token in the text as a visible fallback — better
# #                 # than silently dropping the footer.

# #         # ── Build HTML body from plain text ──────────────────────────────────
# #         # bodyCopy is stored as plain text with \n line breaks. Email clients
# #         # that render body_html (Gmail, Outlook) collapse whitespace and ignore
# #         # \n unless it is converted to HTML. We do a minimal conversion:
# #         #   - Split on blank lines → <p> paragraphs
# #         #   - Convert single \n within a paragraph → <br>
# #         #   - Escape HTML special characters to prevent injection
# #         import html as _html_mod

# #         def _plain_to_html(text: str) -> str:
# #             """Convert plain text email body to minimal HTML."""
# #             # Escape HTML entities
# #             escaped = _html_mod.escape(text)
# #             # Split into paragraphs on blank lines (one or more empty lines)
# #             import re as _re
# #             paragraphs = _re.split(r"\n\s*\n", escaped)
# #             html_parts: list[str] = []
# #             for para in paragraphs:
# #                 stripped = para.strip()
# #                 if not stripped:
# #                     continue
# #                 # Convert single newlines within a paragraph to <br>
# #                 inner = stripped.replace("\n", "<br>\n")
# #                 html_parts.append(f"<p>{inner}</p>")
# #             body_html = "\n".join(html_parts)
# #             return (
# #                 "<!DOCTYPE html>"
# #                 "<html><head>"
# #                 '<meta charset="UTF-8">'
# #                 '<meta name="viewport" content="width=device-width,initial-scale=1">'
# #                 "<style>"
# #                 "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;"
# #                 "font-size:14px;line-height:1.6;color:#1a1a1a;max-width:600px;margin:0 auto;padding:20px}"
# #                 "p{margin:0 0 12px}"
# #                 "a{color:#2563eb}"
# #                 "hr{border:none;border-top:1px solid #e5e7eb;margin:20px 0}"
# #                 ".footer{font-size:11px;color:#6b7280;margin-top:24px}"
# #                 "</style>"
# #                 f"</head><body>{body_html}</body></html>"
# #             )

# #         body_html = _plain_to_html(body_for_send)

# #         # Build the MailBridge-compatible payload.
# #         mb_payload: dict[str, Any] = {
# #             "to": [to],
# #             "subject": subject,
# #             "body_html": body_html,
# #             "body_text": body_for_send,  # plain text fallback for non-HTML clients
# #         }

# #         # FIX — per-user mailbox routing via external_user_id:
# #         # Use the config's mailbridge_external_user_id ONLY when this config
# #         # is explicitly owned by this user (owner_user_id == user_id).
# #         # For a tenant-level config (owner_user_id=NULL), always use user_id
# #         # directly — it is the Keycloak UUID MailBridge recorded during
# #         # POST /connect/{provider}/start, so MailBridge will route through
# #         # that user's connected mailbox.
# #         config_owner = getattr(config, "owner_user_id", None) if config else None
# #         config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
# #         ext_user_id = (
# #             config_ext_id
# #             if (config_owner and config_owner == user_id and config_ext_id)
# #             else user_id
# #         )
# #         if ext_user_id:
# #             mb_payload["external_user_id"] = ext_user_id

# #         # Stamp sender identity on the Sequence row so the reply-poller can
# #         # poll the correct MailBridge inbox regardless of who created the
# #         # campaign.  Done before the HTTP call so a partial failure (the call
# #         # succeeds but the DB write later fails) at least has the right values
# #         # committed on retry.  Both columns were added in migration 0018.
# #         if sequence_id:
# #             try:
# #                 from app.models.campaign_models import Sequence as _Seq
# #                 _seq_result = await db.execute(
# #                     select(_Seq).where(_Seq.id == sequence_id)
# #                 )
# #                 _seq = _seq_result.scalar_one_or_none()
# #                 if _seq is not None:
# #                     if user_id:
# #                         _seq.sent_by_user_id = user_id
# #                     if ext_user_id:
# #                         _seq.sent_via_external_user_id = ext_user_id
# #             except Exception as _stamp_exc:  # noqa: BLE001 — best-effort; never block send
# #                 logger.warning(
# #                     "mailbridge.send.stamp_sender_failed",
# #                     sequence_id=sequence_id,
# #                     error=str(_stamp_exc),
# #                 )

# #         # Build auth headers.
# #         api_key = (
# #             getattr(config, "mailbridge_api_key", None) if config else None
# #         ) or self._settings.MAILBRIDGE_API_KEY
# #         headers: dict[str, str] = {"Content-Type": "application/json"}
# #         if api_key:
# #             headers["Authorization"] = f"Bearer {api_key}"

# #         try:
# #             async with httpx.AsyncClient(
# #                 timeout=float(self._settings.MAILBRIDGE_TIMEOUT_SECONDS)
# #             ) as client:
# #                 resp = await client.post(
# #                     f"{url.rstrip('/')}/outbound/send",
# #                     json=mb_payload,
# #                     headers=headers,
# #                 )
# #                 resp.raise_for_status()
# #                 data = resp.json()
# #                 msg_id = (
# #                     data.get("message_id")
# #                     or data.get("messageId")
# #                     or ""
# #                 )
# #                 # Post-send bookkeeping in isolated session — never touches db.
# #                 if user_id and user_id != "system" and tenant_schema:
# #                     await _record_quota_and_usage_isolated(
# #                         tenant_schema, tenant_slug, user_id, send_succeeded=True
# #                     )
# #                 return MailBridgeSendResponse(
# #                     messageId=msg_id,
# #                     status=data.get("status", "sent"),
# #                     accepted=True,
# #                 )
# #         except Exception as exc:  # noqa: BLE001 — graceful degradation
# #             logger.warning("mailbridge.send.fallback", error=str(exc))
# #             return MailBridgeSendResponse(
# #                 messageId="", status="failed", accepted=False
# #             )

# #     async def apply_tracking_event(
# #         self, db: AsyncSession, event: MailBridgeTrackingEvent
# #     ) -> bool:
# #         """Update a Sequence row from a MailBridge tracking webhook.

# #         Per SAAS2-USER-BE §H: 'complaint' is now a handled event type and
# #         triggers per-user quota bookkeeping + potential throttle.

# #         FIX: bounce/complaint quota recording now uses isolated sessions so
# #         the shared db session is never committed inside this method before
# #         the caller can do its own work.
# #         """
# #         if not event.sequenceId:
# #             return False
# #         result = await db.execute(
# #             select(Sequence).where(Sequence.id == event.sequenceId)
# #         )
# #         seq = result.scalar_one_or_none()
# #         if seq is None:
# #             return False
# #         now = event.timestamp or datetime.now(timezone.utc)
# #         event_map = {
# #             "sent": (EmailStatus.Sent, "sentAt"),
# #             "opened": (EmailStatus.Sent, "openedAt"),
# #             "replied": (EmailStatus.Replied, "repliedAt"),
# #             "bounced": (EmailStatus.Bounced, "bouncedAt"),
# #             "failed": (EmailStatus.Failed, "bouncedAt"),
# #         }
# #         if event.event in event_map:
# #             new_status, ts_attr = event_map[event.event]
# #             seq.status = new_status
# #             setattr(seq, ts_attr, now)
# #             if event.event in ("bounced", "failed") and event.reason:
# #                 seq.bounceReason = event.reason
# #             await db.commit()

# #         if event.event == "replied":
# #             try:
# #                 await self._auto_create_reply_draft(db, seq, event, now)
# #             except Exception as exc:  # noqa: BLE001
# #                 logger.warning(
# #                     "mailbridge.reply_draft_create_failed",
# #                     sequence_id=getattr(seq, "id", None),
# #                     error=str(exc),
# #                 )

# #         # Bounce/complaint quota bookkeeping in isolated sessions.
# #         owner_id = getattr(seq, "owner_user_id", None)
# #         if owner_id and owner_id != "system":
# #             tenant_slug = ""
# #             tenant_schema = ""
# #             try:
# #                 tenant_slug = await resolve_tenant_slug(db)
# #                 if tenant_slug:
# #                     tenant_schema = f"tenant_{tenant_slug}"
# #             except Exception:  # noqa: BLE001
# #                 pass

# #             if tenant_schema:
# #                 if event.event in ("bounced", "failed"):
# #                     try:
# #                         async with AsyncSessionLocal() as sess:
# #                             await sess.execute(
# #                                 text(f'SET search_path TO "{tenant_schema}", public')
# #                             )
# #                             await self._quota.record_bounce(sess, owner_id, count=1)
# #                     except Exception as exc:  # noqa: BLE001
# #                         logger.warning(
# #                             "mailbridge.bounce.quota_record_failed",
# #                             user_id=owner_id,
# #                             error=str(exc),
# #                         )
# #                 elif event.event == "complaint":
# #                     try:
# #                         async with AsyncSessionLocal() as sess:
# #                             await sess.execute(
# #                                 text(f'SET search_path TO "{tenant_schema}", public')
# #                             )
# #                             await self._quota.record_complaint(sess, owner_id, count=1)
# #                     except Exception as exc:  # noqa: BLE001
# #                         logger.warning(
# #                             "mailbridge.complaint.quota_record_failed",
# #                             user_id=owner_id,
# #                             error=str(exc),
# #                         )

# #         return True

# #     async def get_user_email_stats(
# #         self,
# #         db: AsyncSession,
# #         user_id: str,
# #         *,
# #         since: datetime | None = None,
# #         until: datetime | None = None,
# #     ) -> dict[str, Any]:
# #         """Aggregate per-user email activity over a date range (dashboard use)."""
# #         since = since or (datetime.now(timezone.utc) - timedelta(days=30))
# #         until = until or datetime.now(timezone.utc)

# #         seq_result = await db.execute(
# #             select(Sequence).where(
# #                 Sequence.owner_user_id == user_id,
# #                 Sequence.createdAt >= since,
# #                 Sequence.createdAt <= until,
# #             )
# #         )
# #         sequences = list(seq_result.scalars().all())
# #         sent = sum(1 for s in sequences if s.sentAt is not None)
# #         opened = sum(1 for s in sequences if s.openedAt is not None)
# #         replied = sum(1 for s in sequences if s.repliedAt is not None)
# #         bounced = sum(1 for s in sequences if s.bouncedAt is not None)

# #         quota_status = await self._quota.get_user_quota_status(db, user_id)
# #         complaints_today = int(quota_status.get("complaints", 0))

# #         meetings = 0
# #         try:
# #             from app.models.campaign_models import ReplyDraft

# #             meetings_result = await db.execute(
# #                 select(func.count())
# #                 .select_from(ReplyDraft)
# #                 .join(Sequence, ReplyDraft.sequenceId == Sequence.id)
# #                 .where(
# #                     Sequence.owner_user_id == user_id,
# #                     ReplyDraft.meetingBookedAt.is_not(None),
# #                     ReplyDraft.meetingBookedAt >= since,
# #                     ReplyDraft.meetingBookedAt <= until,
# #                 )
# #             )
# #             meetings = int(meetings_result.scalar() or 0)
# #         except Exception as exc:  # noqa: BLE001
# #             logger.warning("mailbridge.user_stats.meetings_failed", error=str(exc))

# #         return {
# #             "user_id": user_id,
# #             "since": since.isoformat(),
# #             "until": until.isoformat(),
# #             "sent": sent,
# #             "opened": opened,
# #             "replied": replied,
# #             "bounced": bounced,
# #             "complaints_today": complaints_today,
# #             "meetings_booked": meetings,
# #             "quota": quota_status,
# #         }

# #     async def _auto_create_reply_draft(
# #         self,
# #         db: AsyncSession,
# #         seq: Sequence,
# #         event: MailBridgeTrackingEvent,
# #         now: datetime,
# #     ) -> ReplyDraft | None:
# #         """Create a ReplyDraft + fire AI categorization on a replied event.

# #         FIX: Removed post-commit db.get(ReplyDraft, draft.id). The in-memory
# #         draft object has id populated via RETURNING (eager_defaults=True on
# #         Base). Reading draft.id after commit on this session is safe because
# #         we only need the id — we don't re-SELECT it.
# #         """
# #         prospect_id = getattr(seq, "prospectId", None)
# #         if not prospect_id:
# #             return None
# #         reply_text = (
# #             (event.payload or {}).get("body")
# #             or (event.payload or {}).get("text")
# #             or (event.payload or {}).get("replyBody")
# #             or getattr(event, "reason", None)
# #             or "(reply body not captured by MailBridge webhook)"
# #         )
# #         existing = (
# #             await db.execute(
# #                 select(ReplyDraft).where(ReplyDraft.sequenceId == seq.id).limit(1)
# #             )
# #         ).scalar_one_or_none()
# #         if existing is not None:
# #             return existing
# #         draft = ReplyDraft(
# #             sequenceId=seq.id,
# #             prospectId=prospect_id,
# #             originalReply=reply_text,
# #             category="other",
# #             status="pending",
# #         )
# #         db.add(draft)
# #         await db.commit()
# #         # FIX: do NOT call db.get(ReplyDraft, draft.id) after commit —
# #         # the connection loses search_path. draft.id is already populated
# #         # via RETURNING (eager_defaults=True). Read it from the in-memory object.
# #         draft_id = draft.id
# #         logger.info(
# #             "mailbridge.reply_draft_created",
# #             draft_id=draft_id,
# #             sequence_id=seq.id,
# #             prospect_id=prospect_id,
# #         )
# #         try:
# #             from app.features.reply_drafts.service import ReplyDraftService
# #             await ReplyDraftService().categorize(db, draft_id, reply_text)
# #         except Exception as exc:  # noqa: BLE001
# #             logger.warning(
# #                 "mailbridge.reply_draft_triage_failed",
# #                 draft_id=draft_id,
# #                 error=str(exc),
# #             )
# #         return draft

# #     @staticmethod
# #     async def _resolve_config(
# #         db: AsyncSession,
# #         config_id: str | None,
# #         *,
# #         user_id: str | None = None,
# #     ) -> MailBridgeConfig | None:
# #         """Resolve MailBridgeConfig — read-only, never commits.

# #         Resolution order:
# #           1. Explicit config_id (caller-supplied).
# #           2. Per-user active config (MailBridgeConfig.owner_user_id == user_id).
# #           3. First active tenant-level config (fallback).
# #         """
# #         if config_id:
# #             result = await db.execute(
# #                 select(MailBridgeConfig).where(MailBridgeConfig.id == config_id)
# #             )
# #             cfg = result.scalar_one_or_none()
# #             if cfg:
# #                 return cfg

# #         has_owner_col = hasattr(MailBridgeConfig, "owner_user_id")
# #         if user_id and user_id != "system" and has_owner_col:
# #             try:
# #                 result = await db.execute(
# #                     select(MailBridgeConfig)
# #                     .where(MailBridgeConfig.isActive.is_(True))
# #                     .where(
# #                         getattr(MailBridgeConfig, "owner_user_id") == user_id
# #                     )
# #                     .limit(1)
# #                 )
# #                 cfg = result.scalar_one_or_none()
# #                 if cfg is not None:
# #                     return cfg
# #             except Exception as exc:  # noqa: BLE001
# #                 logger.warning(
# #                     "mailbridge.config.per_user_lookup_failed",
# #                     user_id=user_id,
# #                     error=str(exc),
# #                 )

# #         result = await db.execute(
# #             select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
# #         )
# #         return result.scalar_one_or_none()


# # __all__ = ["MailBridgeService"]

# """
# mailbridge_service.py — SMTP relay client + tracking-event ingestion.

# FIX (search_path crash on send):
#   UserEmailQuotaService.check_can_send() and record_send() both call
#   db.commit() on the shared request-scoped session. After each commit,
#   asyncpg re-pools the connection and clears search_path. When
#   SequenceService.send_email() then tries to commit its own Sequence
#   UPDATE on that same session, PostgreSQL cannot find the "Sequence"
#   table because search_path is gone → UndefinedTableError.

#   Fix: all quota and usage bookkeeping inside send() now opens a
#   short-lived AsyncSessionLocal() with its own search_path — exactly
#   the pattern UsageService.record_event() already uses. The request-
#   scoped db passed into send() is NEVER committed inside this method;
#   it is used only for read-only lookups (resolve_config).

# FIX (wrong sender mailbox):
#   ext_user_id was resolved as:
#     getattr(config, "mailbridge_external_user_id", None) or user_id
#   For a tenant-level config (owner_user_id=NULL), mailbridge_external_user_id
#   holds the first user who ever connected — so every subsequent user's
#   send went through that first mailbox. Fix: only use the config's
#   mailbridge_external_user_id when the config is explicitly owned by
#   this user (owner_user_id == user_id). Otherwise always use user_id
#   directly, which is the Keycloak UUID MailBridge registered during
#   POST /connect/{provider}/start.
# """
# from __future__ import annotations

# from datetime import datetime, timedelta, timezone
# from typing import Any

# import httpx
# import structlog
# from sqlalchemy import func, select, text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.config import get_settings
# from app.core.database import AsyncSessionLocal
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


# # ── Internal helpers for isolated-session bookkeeping ─────────────────────────

# async def _quota_check_isolated(
#     tenant_schema: str, user_id: str
# ) -> tuple[bool, str]:
#     """Run check_can_send in a fresh session so it never touches the caller's db.

#     Opens AsyncSessionLocal, sets search_path to the tenant schema, runs the
#     pre-send quota gate, closes the session. The caller's request-scoped db
#     is never modified.
#     """
#     try:
#         async with AsyncSessionLocal() as session:
#             await session.execute(
#                 text(f'SET search_path TO "{tenant_schema}", public')
#             )
#             svc = UserEmailQuotaService()
#             can_send, reason = await svc.check_can_send(session, user_id, count=1)
#             return can_send, reason
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "mailbridge.quota_check_isolated.failed",
#             user_id=user_id,
#             error=str(exc),
#         )
#         # On error, allow the send rather than blocking it — quota is best-effort.
#         return True, "quota_check_error"


# async def _record_quota_and_usage_isolated(
#     tenant_schema: str,
#     tenant_slug: str,
#     user_id: str,
#     *,
#     send_succeeded: bool,
# ) -> None:
#     """Record quota increment + usage event in a fresh session.

#     Opens AsyncSessionLocal, sets search_path, records send (quota) and
#     usage_event. Failures are logged and swallowed — never blocks the caller.
#     """
#     if not send_succeeded:
#         return
#     try:
#         async with AsyncSessionLocal() as session:
#             await session.execute(
#                 text(f'SET search_path TO "{tenant_schema}", public')
#             )
#             svc = UserEmailQuotaService()
#             await svc.record_send(session, user_id, count=1)
#             # session.commit() is called inside record_send — safe because
#             # this is an isolated session, not the request-scoped one.
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "mailbridge.record_quota_isolated.failed",
#             user_id=user_id,
#             error=str(exc),
#         )
#     # Usage event goes through its own AsyncSessionLocal inside record_event.
#     try:
#         from app.features.usage.service import UsageService
#         await UsageService().record_email_send(
#             tenant=tenant_slug,
#             user_id=user_id,
#             metadata={"source": "mailbridge.send"},
#         )
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "mailbridge.record_usage_isolated.failed",
#             user_id=user_id,
#             error=str(exc),
#         )


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

#         CRITICAL: This method never calls db.commit(). All side-effect work
#         (quota check, quota record, usage record) runs in isolated sessions
#         via AsyncSessionLocal so the caller's request-scoped db is left clean
#         for the caller to commit its own Sequence UPDATE.
#         """
#         # Resolve config using the read-only request db — no commit needed.
#         config = await self._resolve_config(db, config_id, user_id=user_id)
#         url = (config.baseUrl if config else "") or self._settings.MAILBRIDGE_DEFAULT_URL

#         # Derive tenant info once from the request db before any isolated sessions.
#         tenant_slug = ""
#         tenant_schema = ""
#         try:
#             tenant_slug = await resolve_tenant_slug(db)
#             if tenant_slug:
#                 tenant_schema = f"tenant_{tenant_slug}"
#         except Exception as exc:  # noqa: BLE001
#             logger.warning("mailbridge.send.tenant_resolve_failed", error=str(exc))

#         # Pre-send quota check — isolated session, never touches request db.
#         if user_id and user_id != "system" and tenant_schema:
#             can_send, reason = await _quota_check_isolated(tenant_schema, user_id)
#             if not can_send:
#                 logger.info(
#                     "mailbridge.send.quota_exceeded",
#                     user_id=user_id,
#                     sequence_id=sequence_id,
#                     reason=reason,
#                 )
#                 return MailBridgeSendResponse(
#                     messageId="", status="quota_exceeded", accepted=False
#                 )

#         if not url:
#             # Dev/CI stub — no MailBridge configured.
#             msg_id = f"stub-{sequence_id or 'adhoc'}@outrena.local"
#             if user_id and user_id != "system" and tenant_schema:
#                 await _record_quota_and_usage_isolated(
#                     tenant_schema, tenant_slug, user_id, send_succeeded=True
#                 )
#             return MailBridgeSendResponse(
#                 messageId=msg_id, status="queued", accepted=True
#             )

#         # ── Resolve the prospect's unsubscribe token and replace the placeholder ──
#         # {{unsubscribe_url}} is written into bodyCopy at generation time.
#         # We resolve the real URL here, at send time, using the prospect's
#         # unsubscribeToken stored in the DB. This avoids storing live URLs in
#         # the Sequence row, which would break if the domain changes.
#         body_for_send = body
#         if "{{unsubscribe_url}}" in body_for_send:
#             try:
#                 from app.models.campaign_models import Sequence as _SendSeq
#                 from app.models.prospect_models import Prospect as _SendProspect
#                 _unsubscribe_token: str | None = None
#                 if sequence_id:
#                     _seq_lookup = await db.execute(
#                         select(_SendSeq).where(_SendSeq.id == sequence_id)
#                     )
#                     _seq_row = _seq_lookup.scalar_one_or_none()
#                     if _seq_row:
#                         _p_lookup = await db.execute(
#                             select(_SendProspect).where(
#                                 _SendProspect.id == _seq_row.prospectId
#                             )
#                         )
#                         _prospect_row = _p_lookup.scalar_one_or_none()
#                         if _prospect_row:
#                             _unsubscribe_token = getattr(
#                                 _prospect_row, "unsubscribeToken", None
#                             )

#                 if _unsubscribe_token:
#                     _scheme = "https" if self._settings.ENVIRONMENT != "development" else "https"
#                     _real_unsubscribe_url = (
#                         f"{_scheme}://{self._settings.BASE_DOMAIN}"
#                         f"/p/unsubscribe?token={_unsubscribe_token}"
#                         f"&tenant_slug={tenant_slug}"
#                     )
#                 else:
#                     # Fallback: link to the public unsubscribe page without token
#                     # (user will need to enter their email manually).
#                     _scheme = "https" if self._settings.ENVIRONMENT != "development" else "http"
#                     _real_unsubscribe_url = (
#                         f"{_scheme}://{self._settings.BASE_DOMAIN}/p/unsubscribe"
#                     )

#                 body_for_send = body_for_send.replace(
#                     "{{unsubscribe_url}}", _real_unsubscribe_url
#                 )
#             except Exception as _unsub_exc:  # noqa: BLE001 — never block send
#                 logger.warning(
#                     "mailbridge.send.unsubscribe_token_resolve_failed",
#                     sequence_id=sequence_id,
#                     error=str(_unsub_exc),
#                 )
#                 # Leave the token in the text as a visible fallback — better
#                 # than silently dropping the footer.

#         # ── Build HTML body from plain text ──────────────────────────────────
#         # bodyCopy is stored as plain text with \n line breaks. Email clients
#         # that render body_html (Gmail, Outlook) collapse whitespace and ignore
#         # \n unless it is converted to HTML. We do a minimal conversion:
#         #   - Split on blank lines → <p> paragraphs
#         #   - Convert single \n within a paragraph → <br>
#         #   - Escape HTML special characters to prevent injection
#         import html as _html_mod

#         def _plain_to_html(text: str) -> str:
#             """Convert plain text email body to minimal HTML."""
#             # Escape HTML entities
#             escaped = _html_mod.escape(text)
#             # Split into paragraphs on blank lines (one or more empty lines)
#             import re as _re
#             paragraphs = _re.split(r"\n\s*\n", escaped)
#             html_parts: list[str] = []
#             for para in paragraphs:
#                 stripped = para.strip()
#                 if not stripped:
#                     continue
#                 # Convert single newlines within a paragraph to <br>
#                 inner = stripped.replace("\n", "<br>\n")
#                 html_parts.append(f"<p>{inner}</p>")
#             body_html = "\n".join(html_parts)
#             return (
#                 "<!DOCTYPE html>"
#                 "<html><head>"
#                 '<meta charset="UTF-8">'
#                 '<meta name="viewport" content="width=device-width,initial-scale=1">'
#                 "<style>"
#                 "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;"
#                 "font-size:14px;line-height:1.6;color:#1a1a1a;max-width:600px;margin:0 auto;padding:20px}"
#                 "p{margin:0 0 12px}"
#                 "a{color:#2563eb}"
#                 "hr{border:none;border-top:1px solid #e5e7eb;margin:20px 0}"
#                 ".footer{font-size:11px;color:#6b7280;margin-top:24px}"
#                 "</style>"
#                 f"</head><body>{body_html}</body></html>"
#             )

#         # body_html = _plain_to_html(body_for_send)

#         # # Build the MailBridge-compatible payload.
#         # mb_payload: dict[str, Any] = {
#         #     "to": [to],
#         #     "subject": subject,
#         #     "body_html": body_html,
#         #     "body_text": body_for_send,  # plain text fallback for non-HTML clients
#         # }
#         # ── HTML body detection ───────────────────────────────────────────────
#         # When the body was authored in the Tiptap RTE it already contains valid
#         # HTML (starts with a tag, contains closing tags). In that case:
#         #   - body_html: use the HTML as-is (do NOT call _plain_to_html, which
#         #     would html.escape() the tags and break the rendering)
#         #   - body_text: strip tags to generate a plain-text fallback
#         # For legacy plain-text bodies, keep the existing _plain_to_html path.
#         import re as _re_strip

#         def _is_rte_html(text: str) -> bool:
#             """True when body was produced by the Tiptap RTE (already HTML)."""
#             s = text.lstrip()
#             return bool(s) and s[0] == "<" and any(
#                 marker in text
#                 for marker in (
#                     "</p>", "</h", "<br", "</ul>", "</ol>",
#                     "</li>", "</strong>", "</em>",
#                 )
#             )

#         if _is_rte_html(body_for_send):
#             # Body is HTML from the RTE — use directly, strip for plain-text fallback.
#             body_html = body_for_send
#             body_text_plain = _re_strip.sub(r"<[^>]+>", " ", body_for_send)
#             body_text_plain = _re_strip.sub(r"\s+", " ", body_text_plain).strip()
#         else:
#             # Legacy plain-text body — convert to HTML for rich clients.
#             body_html = _plain_to_html(body_for_send)
#             body_text_plain = body_for_send

#         # Build the MailBridge-compatible payload.
#         mb_payload: dict[str, Any] = {
#             "to": [to],
#             "subject": subject,
#             "body_html": body_html,
#             "body_text": body_text_plain,  # plain text fallback for non-HTML clients
#         }

#         # FIX — per-user mailbox routing via external_user_id:
#         # Use the config's mailbridge_external_user_id ONLY when this config
#         # is explicitly owned by this user (owner_user_id == user_id).
#         # For a tenant-level config (owner_user_id=NULL), always use user_id
#         # directly — it is the Keycloak UUID MailBridge recorded during
#         # POST /connect/{provider}/start, so MailBridge will route through
#         # that user's connected mailbox.
#         config_owner = getattr(config, "owner_user_id", None) if config else None
#         config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
#         ext_user_id = (
#             config_ext_id
#             if (config_owner and config_owner == user_id and config_ext_id)
#             else user_id
#         )
#         if ext_user_id:
#             mb_payload["external_user_id"] = ext_user_id

#         # Stamp sender identity on the Sequence row so the reply-poller can
#         # poll the correct MailBridge inbox regardless of who created the
#         # campaign.  Done before the HTTP call so a partial failure (the call
#         # succeeds but the DB write later fails) at least has the right values
#         # committed on retry.  Both columns were added in migration 0018.
#         if sequence_id:
#             try:
#                 from app.models.campaign_models import Sequence as _Seq
#                 _seq_result = await db.execute(
#                     select(_Seq).where(_Seq.id == sequence_id)
#                 )
#                 _seq = _seq_result.scalar_one_or_none()
#                 if _seq is not None:
#                     if user_id:
#                         _seq.sent_by_user_id = user_id
#                     if ext_user_id:
#                         _seq.sent_via_external_user_id = ext_user_id
#             except Exception as _stamp_exc:  # noqa: BLE001 — best-effort; never block send
#                 logger.warning(
#                     "mailbridge.send.stamp_sender_failed",
#                     sequence_id=sequence_id,
#                     error=str(_stamp_exc),
#                 )

#         # Build auth headers.
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
#                 msg_id = (
#                     data.get("message_id")
#                     or data.get("messageId")
#                     or ""
#                 )
#                 # Post-send bookkeeping in isolated session — never touches db.
#                 if user_id and user_id != "system" and tenant_schema:
#                     await _record_quota_and_usage_isolated(
#                         tenant_schema, tenant_slug, user_id, send_succeeded=True
#                     )
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

#         FIX: bounce/complaint quota recording now uses isolated sessions so
#         the shared db session is never committed inside this method before
#         the caller can do its own work.
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

#         if event.event == "replied":
#             try:
#                 await self._auto_create_reply_draft(db, seq, event, now)
#             except Exception as exc:  # noqa: BLE001
#                 logger.warning(
#                     "mailbridge.reply_draft_create_failed",
#                     sequence_id=getattr(seq, "id", None),
#                     error=str(exc),
#                 )

#         # Bounce/complaint quota bookkeeping in isolated sessions.
#         owner_id = getattr(seq, "owner_user_id", None)
#         if owner_id and owner_id != "system":
#             tenant_slug = ""
#             tenant_schema = ""
#             try:
#                 tenant_slug = await resolve_tenant_slug(db)
#                 if tenant_slug:
#                     tenant_schema = f"tenant_{tenant_slug}"
#             except Exception:  # noqa: BLE001
#                 pass

#             if tenant_schema:
#                 if event.event in ("bounced", "failed"):
#                     try:
#                         async with AsyncSessionLocal() as sess:
#                             await sess.execute(
#                                 text(f'SET search_path TO "{tenant_schema}", public')
#                             )
#                             await self._quota.record_bounce(sess, owner_id, count=1)
#                     except Exception as exc:  # noqa: BLE001
#                         logger.warning(
#                             "mailbridge.bounce.quota_record_failed",
#                             user_id=owner_id,
#                             error=str(exc),
#                         )
#                 elif event.event == "complaint":
#                     try:
#                         async with AsyncSessionLocal() as sess:
#                             await sess.execute(
#                                 text(f'SET search_path TO "{tenant_schema}", public')
#                             )
#                             await self._quota.record_complaint(sess, owner_id, count=1)
#                     except Exception as exc:  # noqa: BLE001
#                         logger.warning(
#                             "mailbridge.complaint.quota_record_failed",
#                             user_id=owner_id,
#                             error=str(exc),
#                         )

#         return True

#     async def get_user_email_stats(
#         self,
#         db: AsyncSession,
#         user_id: str,
#         *,
#         since: datetime | None = None,
#         until: datetime | None = None,
#     ) -> dict[str, Any]:
#         """Aggregate per-user email activity over a date range (dashboard use)."""
#         since = since or (datetime.now(timezone.utc) - timedelta(days=30))
#         until = until or datetime.now(timezone.utc)

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

#         quota_status = await self._quota.get_user_quota_status(db, user_id)
#         complaints_today = int(quota_status.get("complaints", 0))

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
#         except Exception as exc:  # noqa: BLE001
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

#         FIX: Removed post-commit db.get(ReplyDraft, draft.id). The in-memory
#         draft object has id populated via RETURNING (eager_defaults=True on
#         Base). Reading draft.id after commit on this session is safe because
#         we only need the id — we don't re-SELECT it.
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
#         # FIX: do NOT call db.get(ReplyDraft, draft.id) after commit —
#         # the connection loses search_path. draft.id is already populated
#         # via RETURNING (eager_defaults=True). Read it from the in-memory object.
#         draft_id = draft.id
#         logger.info(
#             "mailbridge.reply_draft_created",
#             draft_id=draft_id,
#             sequence_id=seq.id,
#             prospect_id=prospect_id,
#         )
#         try:
#             from app.features.reply_drafts.service import ReplyDraftService
#             await ReplyDraftService().categorize(db, draft_id, reply_text)
#         except Exception as exc:  # noqa: BLE001
#             logger.warning(
#                 "mailbridge.reply_draft_triage_failed",
#                 draft_id=draft_id,
#                 error=str(exc),
#             )
#         return draft

#     @staticmethod
#     async def _resolve_config(
#         db: AsyncSession,
#         config_id: str | None,
#         *,
#         user_id: str | None = None,
#     ) -> MailBridgeConfig | None:
#         """Resolve MailBridgeConfig — read-only, never commits.

#         Resolution order:
#           1. Explicit config_id (caller-supplied).
#           2. Per-user active config (MailBridgeConfig.owner_user_id == user_id).
#           3. First active tenant-level config (fallback).
#         """
#         if config_id:
#             result = await db.execute(
#                 select(MailBridgeConfig).where(MailBridgeConfig.id == config_id)
#             )
#             cfg = result.scalar_one_or_none()
#             if cfg:
#                 return cfg

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
#             except Exception as exc:  # noqa: BLE001
#                 logger.warning(
#                     "mailbridge.config.per_user_lookup_failed",
#                     user_id=user_id,
#                     error=str(exc),
#                 )

#         result = await db.execute(
#             select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
#         )
#         return result.scalar_one_or_none()


# __all__ = ["MailBridgeService"]

# """
# mailbridge_service.py — SMTP relay client + tracking-event ingestion.

# FIX (search_path crash on send):
#   UserEmailQuotaService.check_can_send() and record_send() both call
#   db.commit() on the shared request-scoped session. After each commit,
#   asyncpg re-pools the connection and clears search_path. When
#   SequenceService.send_email() then tries to commit its own Sequence
#   UPDATE on that same session, PostgreSQL cannot find the "Sequence"
#   table because search_path is gone → UndefinedTableError.

#   Fix: all quota and usage bookkeeping inside send() now opens a
#   short-lived AsyncSessionLocal() with its own search_path — exactly
#   the pattern UsageService.record_event() already uses. The request-
#   scoped db passed into send() is NEVER committed inside this method;
#   it is used only for read-only lookups (resolve_config).

# FIX (wrong sender mailbox):
#   ext_user_id was resolved as:
#     getattr(config, "mailbridge_external_user_id", None) or user_id
#   For a tenant-level config (owner_user_id=NULL), mailbridge_external_user_id
#   holds the first user who ever connected — so every subsequent user's
#   send went through that first mailbox. Fix: only use the config's
#   mailbridge_external_user_id when the config is explicitly owned by
#   this user (owner_user_id == user_id). Otherwise always use user_id
#   directly, which is the Keycloak UUID MailBridge registered during
#   POST /connect/{provider}/start.
# """
# from __future__ import annotations

# from datetime import datetime, timedelta, timezone
# from typing import Any

# import httpx
# import structlog
# from sqlalchemy import func, select, text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.config import get_settings
# from app.core.database import AsyncSessionLocal
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


# # ── Internal helpers for isolated-session bookkeeping ─────────────────────────

# async def _quota_check_isolated(
#     tenant_schema: str, user_id: str
# ) -> tuple[bool, str]:
#     """Run check_can_send in a fresh session so it never touches the caller's db.

#     Opens AsyncSessionLocal, sets search_path to the tenant schema, runs the
#     pre-send quota gate, closes the session. The caller's request-scoped db
#     is never modified.
#     """
#     try:
#         async with AsyncSessionLocal() as session:
#             await session.execute(
#                 text(f'SET search_path TO "{tenant_schema}", public')
#             )
#             svc = UserEmailQuotaService()
#             can_send, reason = await svc.check_can_send(session, user_id, count=1)
#             return can_send, reason
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "mailbridge.quota_check_isolated.failed",
#             user_id=user_id,
#             error=str(exc),
#         )
#         # On error, allow the send rather than blocking it — quota is best-effort.
#         return True, "quota_check_error"


# async def _record_quota_and_usage_isolated(
#     tenant_schema: str,
#     tenant_slug: str,
#     user_id: str,
#     *,
#     send_succeeded: bool,
# ) -> None:
#     """Record quota increment + usage event in a fresh session.

#     Opens AsyncSessionLocal, sets search_path, records send (quota) and
#     usage_event. Failures are logged and swallowed — never blocks the caller.
#     """
#     if not send_succeeded:
#         return
#     try:
#         async with AsyncSessionLocal() as session:
#             await session.execute(
#                 text(f'SET search_path TO "{tenant_schema}", public')
#             )
#             svc = UserEmailQuotaService()
#             await svc.record_send(session, user_id, count=1)
#             # session.commit() is called inside record_send — safe because
#             # this is an isolated session, not the request-scoped one.
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "mailbridge.record_quota_isolated.failed",
#             user_id=user_id,
#             error=str(exc),
#         )
#     # Usage event goes through its own AsyncSessionLocal inside record_event.
#     try:
#         from app.features.usage.service import UsageService
#         await UsageService().record_email_send(
#             tenant=tenant_slug,
#             user_id=user_id,
#             metadata={"source": "mailbridge.send"},
#         )
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "mailbridge.record_usage_isolated.failed",
#             user_id=user_id,
#             error=str(exc),
#         )


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

#         CRITICAL: This method never calls db.commit(). All side-effect work
#         (quota check, quota record, usage record) runs in isolated sessions
#         via AsyncSessionLocal so the caller's request-scoped db is left clean
#         for the caller to commit its own Sequence UPDATE.
#         """
#         # Resolve config using the read-only request db — no commit needed.
#         config = await self._resolve_config(db, config_id, user_id=user_id)
#         url = (config.baseUrl if config else "") or self._settings.MAILBRIDGE_DEFAULT_URL

#         # Derive tenant info once from the request db before any isolated sessions.
#         tenant_slug = ""
#         tenant_schema = ""
#         try:
#             tenant_slug = await resolve_tenant_slug(db)
#             if tenant_slug:
#                 tenant_schema = f"tenant_{tenant_slug}"
#         except Exception as exc:  # noqa: BLE001
#             logger.warning("mailbridge.send.tenant_resolve_failed", error=str(exc))

#         # Pre-send quota check — isolated session, never touches request db.
#         if user_id and user_id != "system" and tenant_schema:
#             can_send, reason = await _quota_check_isolated(tenant_schema, user_id)
#             if not can_send:
#                 logger.info(
#                     "mailbridge.send.quota_exceeded",
#                     user_id=user_id,
#                     sequence_id=sequence_id,
#                     reason=reason,
#                 )
#                 return MailBridgeSendResponse(
#                     messageId="", status="quota_exceeded", accepted=False
#                 )

#         if not url:
#             # Dev/CI stub — no MailBridge configured.
#             msg_id = f"stub-{sequence_id or 'adhoc'}@outrena.local"
#             if user_id and user_id != "system" and tenant_schema:
#                 await _record_quota_and_usage_isolated(
#                     tenant_schema, tenant_slug, user_id, send_succeeded=True
#                 )
#             return MailBridgeSendResponse(
#                 messageId=msg_id, status="queued", accepted=True
#             )

#         # ── Resolve the prospect's unsubscribe token and replace the placeholder ──
#         # {{unsubscribe_url}} is written into bodyCopy at generation time.
#         # We resolve the real URL here, at send time, using the prospect's
#         # unsubscribeToken stored in the DB. This avoids storing live URLs in
#         # the Sequence row, which would break if the domain changes.
#         body_for_send = body
#         if "{{unsubscribe_url}}" in body_for_send:
#             try:
#                 from app.models.campaign_models import Sequence as _SendSeq
#                 from app.models.prospect_models import Prospect as _SendProspect
#                 _unsubscribe_token: str | None = None
#                 if sequence_id:
#                     _seq_lookup = await db.execute(
#                         select(_SendSeq).where(_SendSeq.id == sequence_id)
#                     )
#                     _seq_row = _seq_lookup.scalar_one_or_none()
#                     if _seq_row:
#                         _p_lookup = await db.execute(
#                             select(_SendProspect).where(
#                                 _SendProspect.id == _seq_row.prospectId
#                             )
#                         )
#                         _prospect_row = _p_lookup.scalar_one_or_none()
#                         if _prospect_row:
#                             _unsubscribe_token = getattr(
#                                 _prospect_row, "unsubscribeToken", None
#                             )

#                 if _unsubscribe_token:
#                     _scheme = "https" if self._settings.ENVIRONMENT != "development" else "https"
#                     _real_unsubscribe_url = (
#                         f"{_scheme}://{self._settings.BASE_DOMAIN}"
#                         f"/p/unsubscribe?token={_unsubscribe_token}"
#                     )
#                 else:
#                     # Fallback: link to the public unsubscribe page without token
#                     # (user will need to enter their email manually).
#                     _scheme = "https" if self._settings.ENVIRONMENT != "development" else "http"
#                     _real_unsubscribe_url = (
#                         f"{_scheme}://{self._settings.BASE_DOMAIN}/p/unsubscribe"
#                     )

#                 body_for_send = body_for_send.replace(
#                     "{{unsubscribe_url}}", _real_unsubscribe_url
#                 )
#             except Exception as _unsub_exc:  # noqa: BLE001 — never block send
#                 logger.warning(
#                     "mailbridge.send.unsubscribe_token_resolve_failed",
#                     sequence_id=sequence_id,
#                     error=str(_unsub_exc),
#                 )
#                 # Leave the token in the text as a visible fallback — better
#                 # than silently dropping the footer.

#         # ── Build HTML body from plain text ──────────────────────────────────
#         # bodyCopy is stored as plain text with \n line breaks. Email clients
#         # that render body_html (Gmail, Outlook) collapse whitespace and ignore
#         # \n unless it is converted to HTML. We do a minimal conversion:
#         #   - Split on blank lines → <p> paragraphs
#         #   - Convert single \n within a paragraph → <br>
#         #   - Escape HTML special characters to prevent injection
#         import html as _html_mod

#         def _plain_to_html(text: str) -> str:
#             """Convert plain text email body to minimal HTML."""
#             # Escape HTML entities
#             escaped = _html_mod.escape(text)
#             # Split into paragraphs on blank lines (one or more empty lines)
#             import re as _re
#             paragraphs = _re.split(r"\n\s*\n", escaped)
#             html_parts: list[str] = []
#             for para in paragraphs:
#                 stripped = para.strip()
#                 if not stripped:
#                     continue
#                 # Convert single newlines within a paragraph to <br>
#                 inner = stripped.replace("\n", "<br>\n")
#                 html_parts.append(f"<p>{inner}</p>")
#             body_html = "\n".join(html_parts)
#             return (
#                 "<!DOCTYPE html>"
#                 "<html><head>"
#                 '<meta charset="UTF-8">'
#                 '<meta name="viewport" content="width=device-width,initial-scale=1">'
#                 "<style>"
#                 "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;"
#                 "font-size:14px;line-height:1.6;color:#1a1a1a;max-width:600px;margin:0 auto;padding:20px}"
#                 "p{margin:0 0 12px}"
#                 "a{color:#2563eb}"
#                 "hr{border:none;border-top:1px solid #e5e7eb;margin:20px 0}"
#                 ".footer{font-size:11px;color:#6b7280;margin-top:24px}"
#                 "</style>"
#                 f"</head><body>{body_html}</body></html>"
#             )

#         body_html = _plain_to_html(body_for_send)

#         # Build the MailBridge-compatible payload.
#         mb_payload: dict[str, Any] = {
#             "to": [to],
#             "subject": subject,
#             "body_html": body_html,
#             "body_text": body_for_send,  # plain text fallback for non-HTML clients
#         }

#         # FIX — per-user mailbox routing via external_user_id:
#         # Use the config's mailbridge_external_user_id ONLY when this config
#         # is explicitly owned by this user (owner_user_id == user_id).
#         # For a tenant-level config (owner_user_id=NULL), always use user_id
#         # directly — it is the Keycloak UUID MailBridge recorded during
#         # POST /connect/{provider}/start, so MailBridge will route through
#         # that user's connected mailbox.
#         config_owner = getattr(config, "owner_user_id", None) if config else None
#         config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
#         ext_user_id = (
#             config_ext_id
#             if (config_owner and config_owner == user_id and config_ext_id)
#             else user_id
#         )
#         if ext_user_id:
#             mb_payload["external_user_id"] = ext_user_id

#         # Stamp sender identity on the Sequence row so the reply-poller can
#         # poll the correct MailBridge inbox regardless of who created the
#         # campaign.  Done before the HTTP call so a partial failure (the call
#         # succeeds but the DB write later fails) at least has the right values
#         # committed on retry.  Both columns were added in migration 0018.
#         if sequence_id:
#             try:
#                 from app.models.campaign_models import Sequence as _Seq
#                 _seq_result = await db.execute(
#                     select(_Seq).where(_Seq.id == sequence_id)
#                 )
#                 _seq = _seq_result.scalar_one_or_none()
#                 if _seq is not None:
#                     if user_id:
#                         _seq.sent_by_user_id = user_id
#                     if ext_user_id:
#                         _seq.sent_via_external_user_id = ext_user_id
#             except Exception as _stamp_exc:  # noqa: BLE001 — best-effort; never block send
#                 logger.warning(
#                     "mailbridge.send.stamp_sender_failed",
#                     sequence_id=sequence_id,
#                     error=str(_stamp_exc),
#                 )

#         # Build auth headers.
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
#                 msg_id = (
#                     data.get("message_id")
#                     or data.get("messageId")
#                     or ""
#                 )
#                 # Post-send bookkeeping in isolated session — never touches db.
#                 if user_id and user_id != "system" and tenant_schema:
#                     await _record_quota_and_usage_isolated(
#                         tenant_schema, tenant_slug, user_id, send_succeeded=True
#                     )
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

#         FIX: bounce/complaint quota recording now uses isolated sessions so
#         the shared db session is never committed inside this method before
#         the caller can do its own work.
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

#         if event.event == "replied":
#             try:
#                 await self._auto_create_reply_draft(db, seq, event, now)
#             except Exception as exc:  # noqa: BLE001
#                 logger.warning(
#                     "mailbridge.reply_draft_create_failed",
#                     sequence_id=getattr(seq, "id", None),
#                     error=str(exc),
#                 )

#         # Bounce/complaint quota bookkeeping in isolated sessions.
#         owner_id = getattr(seq, "owner_user_id", None)
#         if owner_id and owner_id != "system":
#             tenant_slug = ""
#             tenant_schema = ""
#             try:
#                 tenant_slug = await resolve_tenant_slug(db)
#                 if tenant_slug:
#                     tenant_schema = f"tenant_{tenant_slug}"
#             except Exception:  # noqa: BLE001
#                 pass

#             if tenant_schema:
#                 if event.event in ("bounced", "failed"):
#                     try:
#                         async with AsyncSessionLocal() as sess:
#                             await sess.execute(
#                                 text(f'SET search_path TO "{tenant_schema}", public')
#                             )
#                             await self._quota.record_bounce(sess, owner_id, count=1)
#                     except Exception as exc:  # noqa: BLE001
#                         logger.warning(
#                             "mailbridge.bounce.quota_record_failed",
#                             user_id=owner_id,
#                             error=str(exc),
#                         )
#                 elif event.event == "complaint":
#                     try:
#                         async with AsyncSessionLocal() as sess:
#                             await sess.execute(
#                                 text(f'SET search_path TO "{tenant_schema}", public')
#                             )
#                             await self._quota.record_complaint(sess, owner_id, count=1)
#                     except Exception as exc:  # noqa: BLE001
#                         logger.warning(
#                             "mailbridge.complaint.quota_record_failed",
#                             user_id=owner_id,
#                             error=str(exc),
#                         )

#         return True

#     async def get_user_email_stats(
#         self,
#         db: AsyncSession,
#         user_id: str,
#         *,
#         since: datetime | None = None,
#         until: datetime | None = None,
#     ) -> dict[str, Any]:
#         """Aggregate per-user email activity over a date range (dashboard use)."""
#         since = since or (datetime.now(timezone.utc) - timedelta(days=30))
#         until = until or datetime.now(timezone.utc)

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

#         quota_status = await self._quota.get_user_quota_status(db, user_id)
#         complaints_today = int(quota_status.get("complaints", 0))

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
#         except Exception as exc:  # noqa: BLE001
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

#         FIX: Removed post-commit db.get(ReplyDraft, draft.id). The in-memory
#         draft object has id populated via RETURNING (eager_defaults=True on
#         Base). Reading draft.id after commit on this session is safe because
#         we only need the id — we don't re-SELECT it.
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
#         # FIX: do NOT call db.get(ReplyDraft, draft.id) after commit —
#         # the connection loses search_path. draft.id is already populated
#         # via RETURNING (eager_defaults=True). Read it from the in-memory object.
#         draft_id = draft.id
#         logger.info(
#             "mailbridge.reply_draft_created",
#             draft_id=draft_id,
#             sequence_id=seq.id,
#             prospect_id=prospect_id,
#         )
#         try:
#             from app.features.reply_drafts.service import ReplyDraftService
#             await ReplyDraftService().categorize(db, draft_id, reply_text)
#         except Exception as exc:  # noqa: BLE001
#             logger.warning(
#                 "mailbridge.reply_draft_triage_failed",
#                 draft_id=draft_id,
#                 error=str(exc),
#             )
#         return draft

#     @staticmethod
#     async def _resolve_config(
#         db: AsyncSession,
#         config_id: str | None,
#         *,
#         user_id: str | None = None,
#     ) -> MailBridgeConfig | None:
#         """Resolve MailBridgeConfig — read-only, never commits.

#         Resolution order:
#           1. Explicit config_id (caller-supplied).
#           2. Per-user active config (MailBridgeConfig.owner_user_id == user_id).
#           3. First active tenant-level config (fallback).
#         """
#         if config_id:
#             result = await db.execute(
#                 select(MailBridgeConfig).where(MailBridgeConfig.id == config_id)
#             )
#             cfg = result.scalar_one_or_none()
#             if cfg:
#                 return cfg

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
#             except Exception as exc:  # noqa: BLE001
#                 logger.warning(
#                     "mailbridge.config.per_user_lookup_failed",
#                     user_id=user_id,
#                     error=str(exc),
#                 )

#         result = await db.execute(
#             select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
#         )
#         return result.scalar_one_or_none()


# __all__ = ["MailBridgeService"]

"""
mailbridge_service.py — SMTP relay client + tracking-event ingestion.

FIX (search_path crash on send):
  UserEmailQuotaService.check_can_send() and record_send() both call
  db.commit() on the shared request-scoped session. After each commit,
  asyncpg re-pools the connection and clears search_path. When
  SequenceService.send_email() then tries to commit its own Sequence
  UPDATE on that same session, PostgreSQL cannot find the "Sequence"
  table because search_path is gone → UndefinedTableError.

  Fix: all quota and usage bookkeeping inside send() now opens a
  short-lived AsyncSessionLocal() with its own search_path — exactly
  the pattern UsageService.record_event() already uses. The request-
  scoped db passed into send() is NEVER committed inside this method;
  it is used only for read-only lookups (resolve_config).

FIX (wrong sender mailbox):
  ext_user_id was resolved as:
    getattr(config, "mailbridge_external_user_id", None) or user_id
  For a tenant-level config (owner_user_id=NULL), mailbridge_external_user_id
  holds the first user who ever connected — so every subsequent user's
  send went through that first mailbox. Fix: only use the config's
  mailbridge_external_user_id when the config is explicitly owned by
  this user (owner_user_id == user_id). Otherwise always use user_id
  directly, which is the Keycloak UUID MailBridge registered during
  POST /connect/{provider}/start.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
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


# ── Internal helpers for isolated-session bookkeeping ─────────────────────────

async def _quota_check_isolated(
    tenant_schema: str, user_id: str
) -> tuple[bool, str]:
    """Run check_can_send in a fresh session so it never touches the caller's db.

    Opens AsyncSessionLocal, sets search_path to the tenant schema, runs the
    pre-send quota gate, closes the session. The caller's request-scoped db
    is never modified.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(f'SET search_path TO "{tenant_schema}", public')
            )
            svc = UserEmailQuotaService()
            can_send, reason = await svc.check_can_send(session, user_id, count=1)
            return can_send, reason
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "mailbridge.quota_check_isolated.failed",
            user_id=user_id,
            error=str(exc),
        )
        # On error, allow the send rather than blocking it — quota is best-effort.
        return True, "quota_check_error"


async def _record_quota_and_usage_isolated(
    tenant_schema: str,
    tenant_slug: str,
    user_id: str,
    *,
    send_succeeded: bool,
) -> None:
    """Record quota increment + usage event in a fresh session.

    Opens AsyncSessionLocal, sets search_path, records send (quota) and
    usage_event. Failures are logged and swallowed — never blocks the caller.
    """
    if not send_succeeded:
        return
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(f'SET search_path TO "{tenant_schema}", public')
            )
            svc = UserEmailQuotaService()
            await svc.record_send(session, user_id, count=1)
            # session.commit() is called inside record_send — safe because
            # this is an isolated session, not the request-scoped one.
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "mailbridge.record_quota_isolated.failed",
            user_id=user_id,
            error=str(exc),
        )
    # Usage event goes through its own AsyncSessionLocal inside record_event.
    try:
        from app.features.usage.service import UsageService
        await UsageService().record_email_send(
            tenant=tenant_slug,
            user_id=user_id,
            metadata={"source": "mailbridge.send"},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "mailbridge.record_usage_isolated.failed",
            user_id=user_id,
            error=str(exc),
        )


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

        CRITICAL: This method never calls db.commit(). All side-effect work
        (quota check, quota record, usage record) runs in isolated sessions
        via AsyncSessionLocal so the caller's request-scoped db is left clean
        for the caller to commit its own Sequence UPDATE.
        """
        # Resolve config using the read-only request db — no commit needed.
        config = await self._resolve_config(db, config_id, user_id=user_id)
        url = (config.baseUrl if config else "") or self._settings.MAILBRIDGE_DEFAULT_URL

        # Derive tenant info once from the request db before any isolated sessions.
        tenant_slug = ""
        tenant_schema = ""
        try:
            tenant_slug = await resolve_tenant_slug(db)
            if tenant_slug:
                tenant_schema = f"tenant_{tenant_slug}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("mailbridge.send.tenant_resolve_failed", error=str(exc))

        # Pre-send quota check — isolated session, never touches request db.
        if user_id and user_id != "system" and tenant_schema:
            can_send, reason = await _quota_check_isolated(tenant_schema, user_id)
            if not can_send:
                logger.info(
                    "mailbridge.send.quota_exceeded",
                    user_id=user_id,
                    sequence_id=sequence_id,
                    reason=reason,
                )
                return MailBridgeSendResponse(
                    messageId="", status="quota_exceeded", accepted=False
                )

        if not url:
            # Dev/CI stub — no MailBridge configured.
            msg_id = f"stub-{sequence_id or 'adhoc'}@outrena.local"
            if user_id and user_id != "system" and tenant_schema:
                await _record_quota_and_usage_isolated(
                    tenant_schema, tenant_slug, user_id, send_succeeded=True
                )
            return MailBridgeSendResponse(
                messageId=msg_id, status="queued", accepted=True
            )

        # ── Resolve the prospect's unsubscribe token and replace the placeholder ──
        # {{unsubscribe_url}} is written into bodyCopy at generation time.
        # We resolve the real URL here, at send time, using the prospect's
        # unsubscribeToken stored in the DB. This avoids storing live URLs in
        # the Sequence row, which would break if the domain changes.
        body_for_send = body
        if "{{unsubscribe_url}}" in body_for_send:
            try:
                from app.models.campaign_models import Sequence as _SendSeq
                from app.models.prospect_models import Prospect as _SendProspect
                _unsubscribe_token: str | None = None
                if sequence_id:
                    _seq_lookup = await db.execute(
                        select(_SendSeq).where(_SendSeq.id == sequence_id)
                    )
                    _seq_row = _seq_lookup.scalar_one_or_none()
                    if _seq_row:
                        _p_lookup = await db.execute(
                            select(_SendProspect).where(
                                _SendProspect.id == _seq_row.prospectId
                            )
                        )
                        _prospect_row = _p_lookup.scalar_one_or_none()
                        if _prospect_row:
                            _unsubscribe_token = getattr(
                                _prospect_row, "unsubscribeToken", None
                            )

                if _unsubscribe_token:
                    _scheme = "https" if self._settings.ENVIRONMENT != "development" else "https"
                    _real_unsubscribe_url = (
                        f"{_scheme}://{self._settings.BASE_DOMAIN}"
                        f"/p/unsubscribe?token={_unsubscribe_token}"
                        f"&tenant_slug={tenant_slug}"
                    )
                else:
                    # Fallback: link to the public unsubscribe page without token
                    # (user will need to enter their email manually).
                    _scheme = "https" if self._settings.ENVIRONMENT != "development" else "http"
                    _real_unsubscribe_url = (
                        f"{_scheme}://{self._settings.BASE_DOMAIN}/p/unsubscribe"
                    )

                body_for_send = body_for_send.replace(
                    "{{unsubscribe_url}}", _real_unsubscribe_url
                )
            except Exception as _unsub_exc:  # noqa: BLE001 — never block send
                logger.warning(
                    "mailbridge.send.unsubscribe_token_resolve_failed",
                    sequence_id=sequence_id,
                    error=str(_unsub_exc),
                )
                # Leave the token in the text as a visible fallback — better
                # than silently dropping the footer.

        # ── Build HTML body from plain text ──────────────────────────────────
        # bodyCopy is stored as plain text with \n line breaks. Email clients
        # that render body_html (Gmail, Outlook) collapse whitespace and ignore
        # \n unless it is converted to HTML. We do a minimal conversion:
        #   - Split on blank lines → <p> paragraphs
        #   - Convert single \n within a paragraph → <br>
        #   - Escape HTML special characters to prevent injection
        import html as _html_mod

        def _plain_to_html(text: str) -> str:
            """Convert plain text email body to minimal HTML."""
            # Escape HTML entities
            escaped = _html_mod.escape(text)
            # Split into paragraphs on blank lines (one or more empty lines)
            import re as _re
            paragraphs = _re.split(r"\n\s*\n", escaped)
            html_parts: list[str] = []
            for para in paragraphs:
                stripped = para.strip()
                if not stripped:
                    continue
                # Convert single newlines within a paragraph to <br>
                inner = stripped.replace("\n", "<br>\n")
                html_parts.append(f"<p>{inner}</p>")
            body_html = "\n".join(html_parts)
            return (
                "<!DOCTYPE html>"
                "<html><head>"
                '<meta charset="UTF-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                "<style>"
                "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;"
                "font-size:14px;line-height:1.6;color:#1a1a1a;max-width:600px;margin:0 auto;padding:20px}"
                "p{margin:0 0 12px}"
                "a{color:#2563eb}"
                "hr{border:none;border-top:1px solid #e5e7eb;margin:20px 0}"
                ".footer{font-size:11px;color:#6b7280;margin-top:24px}"
                "</style>"
                f"</head><body>{body_html}</body></html>"
            )

        # body_html = _plain_to_html(body_for_send)

        # # Build the MailBridge-compatible payload.
        # mb_payload: dict[str, Any] = {
        #     "to": [to],
        #     "subject": subject,
        #     "body_html": body_html,
        #     "body_text": body_for_send,  # plain text fallback for non-HTML clients
        # }
        # ── HTML body detection ───────────────────────────────────────────────
        # When the body was authored in the Tiptap RTE it already contains valid
        # HTML (starts with a tag, contains closing tags). In that case:
        #   - body_html: use the HTML as-is (do NOT call _plain_to_html, which
        #     would html.escape() the tags and break the rendering)
        #   - body_text: strip tags to generate a plain-text fallback
        # For legacy plain-text bodies, keep the existing _plain_to_html path.
        import re as _re_strip

        def _is_rte_html(text: str) -> bool:
            """True when body was produced by the Tiptap RTE (already HTML)."""
            s = text.lstrip()
            return bool(s) and s[0] == "<" and any(
                marker in text
                for marker in (
                    "</p>", "</h", "<br", "</ul>", "</ol>",
                    "</li>", "</strong>", "</em>",
                )
            )

        if _is_rte_html(body_for_send):
            # Body is HTML from the RTE — use directly, strip for plain-text fallback.
            body_html = body_for_send
            body_text_plain = _re_strip.sub(r"<[^>]+>", " ", body_for_send)
            body_text_plain = _re_strip.sub(r"\s+", " ", body_text_plain).strip()
        else:
            # Legacy plain-text body — convert to HTML for rich clients.
            body_html = _plain_to_html(body_for_send)
            body_text_plain = body_for_send

        # Build the MailBridge-compatible payload.
        mb_payload: dict[str, Any] = {
            "to": [to],
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text_plain,  # plain text fallback for non-HTML clients
        }

        # FIX — per-user mailbox routing via external_user_id:
        # Use the config's mailbridge_external_user_id ONLY when this config
        # is explicitly owned by this user (owner_user_id == user_id).
        # For a tenant-level config (owner_user_id=NULL), always use user_id
        # directly — it is the Keycloak UUID MailBridge recorded during
        # POST /connect/{provider}/start, so MailBridge will route through
        # that user's connected mailbox.
        config_owner = getattr(config, "owner_user_id", None) if config else None
        config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
        ext_user_id = (
            config_ext_id
            if (config_owner and config_owner == user_id and config_ext_id)
            else user_id
        )
        if ext_user_id:
            mb_payload["external_user_id"] = ext_user_id

        # Stamp sender identity on the Sequence row so the reply-poller can
        # poll the correct MailBridge inbox regardless of who created the
        # campaign.  Done before the HTTP call so a partial failure (the call
        # succeeds but the DB write later fails) at least has the right values
        # committed on retry.  Both columns were added in migration 0018.
        if sequence_id:
            try:
                from app.models.campaign_models import Sequence as _Seq
                _seq_result = await db.execute(
                    select(_Seq).where(_Seq.id == sequence_id)
                )
                _seq = _seq_result.scalar_one_or_none()
                if _seq is not None:
                    if user_id:
                        _seq.sent_by_user_id = user_id
                    if ext_user_id:
                        _seq.sent_via_external_user_id = ext_user_id
            except Exception as _stamp_exc:  # noqa: BLE001 — best-effort; never block send
                logger.warning(
                    "mailbridge.send.stamp_sender_failed",
                    sequence_id=sequence_id,
                    error=str(_stamp_exc),
                )

        # Build auth headers.
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
                msg_id = (
                    data.get("message_id")
                    or data.get("messageId")
                    or ""
                )
                # Post-send bookkeeping in isolated session — never touches db.
                if user_id and user_id != "system" and tenant_schema:
                    await _record_quota_and_usage_isolated(
                        tenant_schema, tenant_slug, user_id, send_succeeded=True
                    )
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

        FIX: bounce/complaint quota recording now uses isolated sessions so
        the shared db session is never committed inside this method before
        the caller can do its own work.
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
            # Raw SQL UPDATE — avoids two failure modes:
            # 1. SAEnum adds ::email_status cast that fails across tenant schemas
            #    (asyncpg CannotCoerceError: cannot cast tenant_X.email_status to email_status).
            # 2. ORM attribute mutation after db.commit() loses search_path:
            #    asyncpg returns the connection to pool and strips SET search_path,
            #    so any ORM access after commit hits the wrong (public) schema.
            status_value = new_status.value if hasattr(new_status, "value") else str(new_status)
            set_clauses = f"status = :status, \"{ts_attr}\" = :ts_value"
            params: dict = {
                "status": status_value,
                "ts_value": now,
                "seq_id": seq.id,
            }
            if event.event in ("bounced", "failed") and event.reason:
                set_clauses += ', "bounceReason" = :bounce_reason'
                params["bounce_reason"] = event.reason
            await db.execute(
                text(f'UPDATE "Sequence" SET {set_clauses} WHERE id = :seq_id'),
                params,
            )
            await db.commit()

        if event.event == "replied":
            try:
                await self._auto_create_reply_draft(db, seq, event, now)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "mailbridge.reply_draft_create_failed",
                    sequence_id=getattr(seq, "id", None),
                    error=str(exc),
                )

        # Bounce/complaint quota bookkeeping in isolated sessions.
        owner_id = getattr(seq, "owner_user_id", None)
        if owner_id and owner_id != "system":
            tenant_slug = ""
            tenant_schema = ""
            try:
                tenant_slug = await resolve_tenant_slug(db)
                if tenant_slug:
                    tenant_schema = f"tenant_{tenant_slug}"
            except Exception:  # noqa: BLE001
                pass

            if tenant_schema:
                if event.event in ("bounced", "failed"):
                    try:
                        async with AsyncSessionLocal() as sess:
                            await sess.execute(
                                text(f'SET search_path TO "{tenant_schema}", public')
                            )
                            await self._quota.record_bounce(sess, owner_id, count=1)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "mailbridge.bounce.quota_record_failed",
                            user_id=owner_id,
                            error=str(exc),
                        )
                elif event.event == "complaint":
                    try:
                        async with AsyncSessionLocal() as sess:
                            await sess.execute(
                                text(f'SET search_path TO "{tenant_schema}", public')
                            )
                            await self._quota.record_complaint(sess, owner_id, count=1)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "mailbridge.complaint.quota_record_failed",
                            user_id=owner_id,
                            error=str(exc),
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
        """Aggregate per-user email activity over a date range (dashboard use)."""
        since = since or (datetime.now(timezone.utc) - timedelta(days=30))
        until = until or datetime.now(timezone.utc)

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

        quota_status = await self._quota.get_user_quota_status(db, user_id)
        complaints_today = int(quota_status.get("complaints", 0))

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
        except Exception as exc:  # noqa: BLE001
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

        FIX: Removed post-commit db.get(ReplyDraft, draft.id). The in-memory
        draft object has id populated via RETURNING (eager_defaults=True on
        Base). Reading draft.id after commit on this session is safe because
        we only need the id — we don't re-SELECT it.
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
        # FIX: do NOT call db.get(ReplyDraft, draft.id) after commit —
        # the connection loses search_path. draft.id is already populated
        # via RETURNING (eager_defaults=True). Read it from the in-memory object.
        draft_id = draft.id
        logger.info(
            "mailbridge.reply_draft_created",
            draft_id=draft_id,
            sequence_id=seq.id,
            prospect_id=prospect_id,
        )
        try:
            from app.features.reply_drafts.service import ReplyDraftService
            await ReplyDraftService().categorize(db, draft_id, reply_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "mailbridge.reply_draft_triage_failed",
                draft_id=draft_id,
                error=str(exc),
            )
        return draft

    @staticmethod
    async def _resolve_config(
        db: AsyncSession,
        config_id: str | None,
        *,
        user_id: str | None = None,
    ) -> MailBridgeConfig | None:
        """Resolve MailBridgeConfig — read-only, never commits.

        Resolution order:
          1. Explicit config_id (caller-supplied).
          2. Per-user active config (MailBridgeConfig.owner_user_id == user_id).
          3. First active tenant-level config (fallback).
        """
        if config_id:
            result = await db.execute(
                select(MailBridgeConfig).where(MailBridgeConfig.id == config_id)
            )
            cfg = result.scalar_one_or_none()
            if cfg:
                return cfg

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
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "mailbridge.config.per_user_lookup_failed",
                    user_id=user_id,
                    error=str(exc),
                )

        result = await db.execute(
            select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
        )
        return result.scalar_one_or_none()


__all__ = ["MailBridgeService"]