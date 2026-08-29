# # """
# # app/features/mailbridge/reply_poller.py
# # ========================================
# # Background scheduler task: poll MailBridge for replies to sent sequences
# # and surface them in Outrena's Reply Inbox.
 
# # DESIGN (final):
# #   The Sequence table is the authoritative source of truth. Every sent
# #   sequence has:
# #     - owner_user_id: Keycloak UUID of who sent it (= external_user_id in MailBridge)
# #     - prospectId:    who the email was sent to
# #     - sentAt:        when it was sent (used as `since` filter)
 
# #   For each sent-but-unreplied sequence, the poller calls:
# #     GET /auth/connect/replies
# #       ?external_user_id=<seq.owner_user_id>
# #       &sender=<prospect.email>
# #       &since=<seq.sentAt>
 
# #   If MailBridge returns replies, the earliest one is recorded via
# #   apply_tracking_event(), which stamps Sequence.repliedAt, creates a
# #   ReplyDraft, and fires AI categorization.
 
# #   No guessing about which users are connected. No querying MailBridgeConfig
# #   or UserSenderIdentity. The sequence row tells us exactly who sent the
# #   email and who to ask MailBridge about.
 
# #   Edge case — owner_user_id is "system" (auto-generated sequences before
# #   the campaigns/service.py fix): we skip these sequences since "system"
# #   is not a real MailBridge external_user_id.
# # """
# # from __future__ import annotations
 
# # from datetime import datetime, timezone
# # from typing import Any
 
# # import structlog
# # from sqlalchemy import select, text
 
# # from app.core.config import get_settings
# # from app.core.database import AsyncSessionLocal, engine
# # from app.models.campaign_models import Sequence
# # from app.models.enums import EmailStatus
# # from app.models.prospect_models import Prospect
# # from app.schemas.mailbridge import MailBridgeTrackingEvent
 
# # logger = structlog.get_logger(__name__)
 
 
# # async def run_reply_poll_all_tenants() -> dict[str, Any]:
# #     """Top-level entry point called by the APScheduler job."""
# #     summary: dict[str, Any] = {
# #         "tenants_polled": 0,
# #         "sequences_checked": 0,
# #         "replies_found": 0,
# #         "errors": 0,
# #     }
 
# #     schemas: list[str] = []
# #     try:
# #         async with engine.connect() as conn:
# #             result = await conn.execute(
# #                 text(
# #                     "SELECT schema_name FROM public.tenants "
# #                     "WHERE status='ACTIVE' AND deleted_at IS NULL"
# #                 )
# #             )
# #             schemas = [row[0] for row in result.fetchall()]
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning("reply_poller.no_tenants_table", error=str(exc))
# #         schemas = []
 
# #     for schema in schemas:
# #         try:
# #             result = await _poll_tenant(schema)
# #             summary["tenants_polled"] += 1
# #             summary["sequences_checked"] += result["sequences_checked"]
# #             summary["replies_found"] += result["replies_found"]
# #             summary["errors"] += result["errors"]
# #         except Exception as exc:  # noqa: BLE001
# #             summary["errors"] += 1
# #             logger.error(
# #                 "reply_poller.tenant_failed",
# #                 schema=schema,
# #                 error=str(exc),
# #                 exc_info=True,
# #             )
 
# #     logger.info("reply_poller.complete", **summary)
# #     return summary
 
 
# # async def _poll_tenant(schema: str) -> dict[str, Any]:
# #     """Poll one tenant schema for reply events.
 
# #     Loads all sent-but-unreplied sequences, then for each one asks
# #     MailBridge: did owner_user_id's mailbox receive a reply from
# #     prospect.email since sentAt?
# #     """
# #     result: dict[str, Any] = {
# #         "sequences_checked": 0,
# #         "replies_found": 0,
# #         "errors": 0,
# #     }
 
# #     # Load all sent-but-unreplied sequences.
# #     #
# #     # Poll identity resolution (migration 0018):
# #     #   sent_via_external_user_id — the exact external_user_id that was passed
# #     #     to MailBridge when the email was dispatched.  This is the identity
# #     #     whose inbox MailBridge recorded the reply against, so we MUST use it
# #     #     when calling GET /auth/connect/replies.  Present on all rows sent
# #     #     after migration 0018.
# #     #   owner_user_id — fallback for legacy rows sent before migration 0018,
# #     #     where sent_via_external_user_id is NULL.  This preserves the previous
# #     #     behaviour for old rows while new rows use the correct sender identity.
# #     sequences_to_check: list[dict[str, Any]] = []
# #     try:
# #         async with AsyncSessionLocal() as db:
# #             await db.execute(text(f'SET search_path TO "{schema}", public'))
# #             rows = (await db.execute(
# #                 select(Sequence)
# #                 .where(Sequence.status == 'Sent')  # FIX: string avoids schema-qualified enum cast error (CannotCoerceError) across tenants
# #                 .where(Sequence.repliedAt.is_(None))
# #                 .where(Sequence.sentAt.is_not(None))
# #                 # Include sequences that have either a sent_via_external_user_id
# #                 # (post-0018 rows) or a non-system owner_user_id (legacy rows).
# #                 # We exclude pure 'system' rows that have no usable identity at all.
# #                 .where(
# #                     (
# #                         Sequence.sent_via_external_user_id.is_not(None)
# #                     ) | (
# #                         (Sequence.owner_user_id.is_not(None)) &
# #                         (Sequence.owner_user_id != "system")
# #                     )
# #                 )
# #             )).scalars().all()
# #             for seq in rows:
# #                 # Prefer the stamp from send-time; fall back to creator identity.
# #                 poll_identity = (
# #                     getattr(seq, "sent_via_external_user_id", None)
# #                     or seq.owner_user_id
# #                 )
# #                 sequences_to_check.append({
# #                     "id": seq.id,
# #                     "poll_identity": poll_identity,
# #                     "sentAt": seq.sentAt,
# #                     "prospectId": seq.prospectId,
# #                 })
# #     except Exception as exc:  # noqa: BLE001
# #         logger.error("reply_poller.tenant_load_failed", schema=schema, error=str(exc))
# #         result["errors"] += 1
# #         return result
 
# #     result["sequences_checked"] = len(sequences_to_check)
# #     if not sequences_to_check:
# #         return result
 
# #     mb_client = await _get_mb_client_for_schema(schema)
# #     if mb_client is None:
# #         logger.debug("reply_poller.no_mailbridge_config", schema=schema)
# #         return result
 
# #     for seq_data in sequences_to_check:
# #         try:
# #             found = await _check_sequence(schema, seq_data, mb_client)
# #             if found:
# #                 result["replies_found"] += 1
# #         except Exception as exc:  # noqa: BLE001
# #             result["errors"] += 1
# #             logger.warning(
# #                 "reply_poller.sequence_check_failed",
# #                 schema=schema,
# #                 sequence_id=seq_data["id"],
# #                 error=str(exc),
# #             )
 
# #     return result
 
 
# # async def _check_sequence(
# #     schema: str,
# #     seq_data: dict[str, Any],
# #     mb_client: Any,
# # ) -> bool:
# #     """Check one sequence for a reply in MailBridge.
 
# #     Calls GET /auth/connect/replies with:
# #       external_user_id = seq_data["poll_identity"]
# #                          — sent_via_external_user_id when set (post-0018 rows,
# #                            i.e. the exact MailBridge identity used at send-time),
# #                            or owner_user_id for legacy rows.
# #       sender           = prospect.email  (who we expect a reply from)
# #       since            = seq.sentAt      (ignore pre-existing inbox mail)
 
# #     Using the actual send-time identity (not the campaign creator) ensures we
# #     poll the correct inbox in multi-user tenants where the person who clicked
# #     Send differs from the person who generated the sequences.
# #     """
# #     sequence_id: str = seq_data["id"]
# #     poll_identity: str = seq_data["poll_identity"]
# #     sent_at: datetime = seq_data["sentAt"]
# #     prospect_id: str = seq_data["prospectId"]
 
# #     prospect_email = await _resolve_prospect_email(schema, prospect_id)
# #     if not prospect_email:
# #         return False
 
# #     if sent_at.tzinfo is None:
# #         sent_at = sent_at.replace(tzinfo=timezone.utc)
 
# #     try:
# #         replies = await mb_client.get_connect_replies(
# #             external_user_id=poll_identity,
# #             sender=prospect_email,
# #             since=sent_at,
# #         )
# #     except RuntimeError as exc:
# #         logger.warning(
# #             "reply_poller.mailbridge_call_failed",
# #             schema=schema,
# #             sequence_id=sequence_id,
# #             poll_identity=poll_identity,
# #             error=str(exc),
# #         )
# #         return False
 
# #     if not replies:
# #         return False
 
# #     # Take the earliest reply.
# #     replies_sorted = sorted(replies, key=lambda r: r.get("received_at") or "")
# #     earliest = replies_sorted[0]
 
# #     await _record_reply(schema, sequence_id, earliest)
 
# #     logger.info(
# #         "reply_poller.reply_recorded",
# #         schema=schema,
# #         sequence_id=sequence_id,
# #         poll_identity=poll_identity,
# #         from_address=earliest.get("from_address"),
# #         subject=earliest.get("subject"),
# #         received_at=earliest.get("received_at"),
# #     )
# #     return True
 
 
# # async def _record_reply(
# #     schema: str,
# #     sequence_id: str,
# #     reply_event: dict[str, Any],
# # ) -> None:
# #     """Apply a 'replied' tracking event in an isolated tenant session."""
# #     from app.features.mailbridge.service import MailBridgeService
 
# #     received_at_str: str | None = reply_event.get("received_at")
# #     received_at: datetime | None = None
# #     if received_at_str:
# #         try:
# #             received_at = datetime.fromisoformat(received_at_str)
# #             if received_at.tzinfo is None:
# #                 received_at = received_at.replace(tzinfo=timezone.utc)
# #         except ValueError:
# #             pass
 
# #     subject = reply_event.get("subject") or "(no subject)"
# #     message_id = reply_event.get("message_id") or ""
# #     # Use the real email body returned by MailBridge (after the body_text fix).
# #     # Fall back to the subject line if body is empty (e.g. old reply_events
# #     # rows that were recorded before the body_text column was added).
# #     body = (
# #         reply_event.get("body")
# #         or reply_event.get("body_text")
# #         or f"[Reply received — subject: {subject}]"
# #     )
 
# #     event = MailBridgeTrackingEvent(
# #         event="replied",
# #         messageId=message_id,
# #         sequenceId=sequence_id,
# #         timestamp=received_at or datetime.now(timezone.utc),
# #         recipient=None,
# #         reason=None,
# #         payload={"body": body},
# #     )
 
# #     svc = MailBridgeService()
# #     async with AsyncSessionLocal() as db:
# #         await db.execute(text(f'SET search_path TO "{schema}", public'))
# #         await svc.apply_tracking_event(db, event)
 
 
# # async def _resolve_prospect_email(schema: str, prospect_id: str) -> str:
# #     """Decrypt and return the prospect's email address."""
# #     try:
# #         async with AsyncSessionLocal() as db:
# #             await db.execute(text(f'SET search_path TO "{schema}", public'))
# #             result = await db.execute(
# #                 select(Prospect).where(Prospect.id == prospect_id)
# #             )
# #             prospect = result.scalar_one_or_none()
# #             if prospect is None:
# #                 return ""
# #             raw_email: str = getattr(prospect, "email", None) or ""
# #             if not raw_email or getattr(prospect, "anonymized", False):
# #                 return ""
# #             try:
# #                 from app.services.pii_service import PiiService
# #                 return PiiService().decrypt_field(raw_email) or ""
# #             except Exception:  # noqa: BLE001
# #                 return raw_email
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning(
# #             "reply_poller.prospect_email_failed",
# #             schema=schema,
# #             prospect_id=prospect_id,
# #             error=str(exc),
# #         )
# #         return ""
 
 
# # async def _get_mb_client_for_schema(schema: str) -> Any | None:
# #     """Load the active MailBridgeConfig and build a client."""
# #     from app.features.mailbridge.mailbridge_client import MailBridgeClient
# #     from app.models.config_models import MailBridgeConfig
 
# #     try:
# #         async with AsyncSessionLocal() as db:
# #             await db.execute(text(f'SET search_path TO "{schema}", public'))
# #             result = await db.execute(
# #                 select(MailBridgeConfig)
# #                 .where(MailBridgeConfig.isActive.is_(True))
# #                 .limit(1)
# #             )
# #             config = result.scalar_one_or_none()
# #             if config is None:
# #                 return None
# #             base_url: str = config.baseUrl or ""
# #             api_key: str = getattr(config, "mailbridge_api_key", "") or ""
# #             if not base_url:
# #                 return None
# #             return MailBridgeClient(base_url=base_url, api_key=api_key)
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning(
# #             "reply_poller.config_load_failed",
# #             schema=schema,
# #             error=str(exc),
# #         )
# #         return None
 
 
# # async def _reply_poll_wrapper() -> None:
# #     """APScheduler entry point."""
# #     try:
# #         await run_reply_poll_all_tenants()
# #     except Exception as exc:  # noqa: BLE001
# #         logger.error("reply_poller.unhandled_error", error=str(exc), exc_info=True)
 
 
# # def register_reply_poll_job(scheduler: Any) -> None:
# #     """Register the reply-poll job on an existing AsyncIOScheduler instance."""
# #     settings = get_settings()
 
# #     poll_enabled: bool = getattr(settings, "MAILBRIDGE_REPLY_POLL_ENABLED", True)
# #     if not poll_enabled:
# #         logger.info("reply_poller.disabled", reason="MAILBRIDGE_REPLY_POLL_ENABLED=false")
# #         return
 
# #     if not settings.MAILBRIDGE_DEFAULT_URL:
# #         logger.info(
# #             "reply_poller.skipped",
# #             reason="MAILBRIDGE_DEFAULT_URL not set — configure MailBridge to enable reply polling",
# #         )
# #         return
 
# #     poll_seconds: int = getattr(settings, "MAILBRIDGE_REPLY_POLL_SECONDS", 120)
 
# #     scheduler.add_job(
# #         _reply_poll_wrapper,
# #         "interval",
# #         seconds=poll_seconds,
# #         id="outrena_reply_poll",
# #         max_instances=1,
# #         coalesce=True,
# #         replace_existing=True,
# #     )
# #     logger.info(
# #         "reply_poller.registered",
# #         poll_seconds=poll_seconds,
# #         job_id="outrena_reply_poll",
# #     )
 
 
# # __all__ = [
# #     "run_reply_poll_all_tenants",
# #     "register_reply_poll_job",
# # ]

# """
# app/features/mailbridge/reply_poller.py
# ========================================
# Background scheduler task: poll MailBridge for replies AND bounces on
# sent sequences, and surface them in Outrena's tracking system.

# ARCHITECTURE
# ============

# MailBridge is the only source of inbound email data. It stores every
# inbound email in {tenant_schema}.reply_events regardless of what kind
# of email it is — real replies from prospects AND NDR bounce notifications
# from mailer-daemon are both rows in reply_events.

# The key insight: reply_events.from_address tells us whether the inbound
# email is a real reply or a bounce notification:
#   - Real reply:  from_address = the prospect's email address
#   - NDR bounce:  from_address contains "mailer-daemon" or "postmaster"

# So this poller runs TWO scans per tenant per tick:

# SCAN 1 — REPLIES
#   For each Sequence with status=Sent, repliedAt=NULL:
#     Call GET /auth/connect/replies?sender=<prospect.email>&since=<sentAt>
#     If results found → stamp repliedAt, create ReplyDraft, AI-categorize.

# SCAN 2 — BOUNCES
#   For each Sequence with status=Sent, bouncedAt=NULL:
#     Call GET /auth/connect/replies?sender=mailer-daemon@googlemail.com&since=<sentAt>
#     Parse body to extract the failed recipient email.
#     If failed recipient matches this sequence's prospect email → stamp
#     bouncedAt + bounceReason, flip status to Bounced.

#     We also try postmaster@gmail.com and mailer-daemon (LIKE pattern)
#     as MailBridge normalises the from_address via LOWER LIKE matching.

# DB WRITE SAFETY
# ===============
# apply_tracking_event() uses raw SQL UPDATE (not ORM attribute mutation)
# to avoid the search_path loss pattern: after db.commit(), asyncpg
# returns the connection to the pool and strips the tenant search_path.
# ORM attribute mutation after commit causes PendingRollbackError.

# ENUM CAST SAFETY
# ================
# All WHERE clauses on Sequence.status use string literals ('Sent',
# 'Bounced') not EmailStatus enum values. SQLAlchemy's SAEnum column type
# adds ::email_status to bind params even for string values, which causes
# "cannot cast type tenant_X.email_status to email_status" cross-schema
# errors in asyncpg. String literals bypass the cast entirely.
# """
# from __future__ import annotations

# import re
# from datetime import datetime, timezone
# from typing import Any

# import structlog
# from sqlalchemy import select, text

# from app.core.config import get_settings
# from app.core.database import AsyncSessionLocal, engine
# from app.models.campaign_models import Sequence
# from app.models.prospect_models import Prospect

# logger = structlog.get_logger(__name__)

# # NDR sender patterns — all patterns MailBridge stores from Gmail/Outlook NDRs.
# # MailBridge normalises from_address to lowercase when storing, so we match lower.
# _NDR_SENDERS = [
#     "mailer-daemon@googlemail.com",
#     "mailer-daemon@gmail.com",
#     "postmaster@gmail.com",
#     "mailer-daemon",
# ]

# # Regex patterns to extract the failed recipient from an NDR body.
# # Gmail NDRs are multipart/report. MailBridge captures only the text/plain part.
# # The machine-readable message/delivery-status part (with Final-Recipient header)
# # is NOT stored — so we parse the human-readable plain text instead.
# _FAILED_RECIPIENT_PATTERNS = [
#     # machine-readable DSN (if body_text ever includes delivery-status content)
#     re.compile(r"final-recipient\s*:\s*rfc822\s*;\s*([^\s,\r\n]+)", re.IGNORECASE),
#     re.compile(r"original-recipient\s*:\s*rfc822\s*;\s*([^\s,\r\n]+)", re.IGNORECASE),
#     re.compile(r"x-failed-recipients?\s*:\s*([^\s,\r\n]+)", re.IGNORECASE),
#     # human-readable Gmail NDR text/plain patterns (most common)
#     re.compile(r"your message wasn.t delivered to\s+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", re.IGNORECASE),
#     re.compile(r"delivering your message to\s+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", re.IGNORECASE),
#     re.compile(r"your message to\s+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\s+couldn", re.IGNORECASE),
#     re.compile(r"<([^>]+@[^>]+)>\s+(?:does not exist|not found|address not found|couldn)", re.IGNORECASE),
#     # broad fallback: email near delivery-failure keywords
#     re.compile(r"(?:deliver|undeliver|bounce|failed|returned).*?([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", re.IGNORECASE),
# ]


# def _extract_failed_recipient(body: str) -> str | None:
#     """Extract the bounced email address from an NDR body.

#     Parses the human-readable text/plain portion of Gmail NDRs.
#     The machine-readable delivery-status part is not stored by MailBridge.
#     """
#     if not body:
#         return None
#     for pattern in _FAILED_RECIPIENT_PATTERNS:
#         match = pattern.search(body)
#         if match:
#             candidate = match.group(1).strip().lower().rstrip(".,><;)")
#             if "@" in candidate and "." in candidate.split("@")[-1] and len(candidate) > 5:
#                 if "mailer-daemon" in candidate or "postmaster" in candidate:
#                     continue
#                 return candidate
#     return None


# def _extract_bounce_reason(body: str, subject: str) -> str:
#     """Extract a human-readable bounce reason from the NDR body."""
#     # Look for SMTP status codes like "550 5.1.1 user not found"
#     smtp_match = re.search(r"\b(5\d{2})\s+[\d.]+\s+([^\r\n]{5,80})", body, re.IGNORECASE)
#     if smtp_match:
#         return f"{smtp_match.group(1)} {smtp_match.group(2).strip()}"

#     # Common Gmail NDR phrases
#     reason_patterns = [
#         re.compile(r"address not found", re.IGNORECASE),
#         re.compile(r"user.*not found", re.IGNORECASE),
#         re.compile(r"no such user", re.IGNORECASE),
#         re.compile(r"recipient address rejected", re.IGNORECASE),
#         re.compile(r"mailbox.*full", re.IGNORECASE),
#         re.compile(r"over.*quota", re.IGNORECASE),
#         re.compile(r"account.*does not exist", re.IGNORECASE),
#         re.compile(r"delivery.*failed", re.IGNORECASE),
#     ]
#     for p in reason_patterns:
#         if p.search(body):
#             return p.pattern.replace(".*", " ").replace(r"\.", ".").strip()

#     # Fall back to subject line (e.g. "Delivery Status Notification (Failure)")
#     if subject:
#         return subject[:120]
#     return "Delivery failure"


# def _extract_reply_text(full_body: str, subject: str) -> str:
#     """Extract only the prospect's new reply text from a full Gmail/Outlook thread body.

#     Gmail and Outlook include the original sent email as a quoted block at the
#     bottom of every reply. Without stripping this, every ReplyDraft shows the
#     same content (the original email template) instead of what the prospect wrote.

#     Stripping patterns (in order of priority):
#       1. Gmail:   "On <date>, <name> <email> wrote:" followed by "> " quoted lines
#       2. Gmail:   "---------- Forwarded message ----------"
#       3. Outlook: "From: ... Sent: ... To: ... Subject: ..."
#       4. Generic: Lines starting with ">" (quoted reply lines)
#       5. Fallback: Return full body if no quote markers found
#     """
#     import re as _re

#     if not full_body:
#         return f"[Reply received — subject: {subject}]"

#     lines = full_body.split('\n')
#     quote_start_idx: int | None = None

#     # Pattern 1: Gmail "On <date>, <name> wrote:" — single line
#     gmail_quote_re = _re.compile(
#         r'^On .{5,100} wrote:$',
#         _re.IGNORECASE
#     )
#     # Pattern 2: Gmail "On <date>\n<name> <email>\nwrote:" — multi-line (2-3 lines)
#     gmail_quote_multiline_re = _re.compile(
#         r'^On \w{3},',
#         _re.IGNORECASE
#     )
#     # Pattern 3: Forwarded message divider
#     forward_re = _re.compile(
#         r'^-{5,}\s*(Forwarded|Original)\s*(message|email)',
#         _re.IGNORECASE
#     )
#     # Pattern 4: Outlook header block
#     outlook_re = _re.compile(
#         r'^From:\s*.+',
#         _re.IGNORECASE
#     )

#     for i, line in enumerate(lines):
#         stripped = line.strip()
#         if gmail_quote_re.match(stripped):
#             quote_start_idx = i
#             break
#         if gmail_quote_multiline_re.match(stripped):
#             # Check if this multi-line pattern completes within next 3 lines
#             context = ' '.join(lines[i:i+3])
#             if 'wrote:' in context.lower():
#                 quote_start_idx = i
#                 break
#         if forward_re.match(stripped):
#             quote_start_idx = i
#             break
#         if outlook_re.match(stripped) and i > 2:
#             # Outlook header only valid if not at very top (avoid matching real From: headers)
#             quote_start_idx = i
#             break

#     if quote_start_idx is not None:
#         reply_lines = lines[:quote_start_idx]
#     else:
#         # Fallback: strip lines starting with ">" (quoted lines)
#         reply_lines = [l for l in lines if not l.strip().startswith('>')]

#     reply_text = '\n'.join(reply_lines).strip()

#     # If stripping left us with nothing, return the full body
#     if not reply_text or len(reply_text) < 5:
#         return full_body.strip() or f"[Reply received — subject: {subject}]"

#     return reply_text





# # ── Main entry points ──────────────────────────────────────────────────────────

# async def run_reply_poll_all_tenants() -> dict[str, Any]:
#     """Top-level entry point called by APScheduler every MAILBRIDGE_REPLY_POLL_SECONDS."""
#     summary: dict[str, Any] = {
#         "tenants_polled": 0,
#         "sequences_checked": 0,
#         "replies_found": 0,
#         "bounces_found": 0,
#         "errors": 0,
#     }

#     schemas: list[str] = []
#     try:
#         async with engine.connect() as conn:
#             result = await conn.execute(
#                 text(
#                     "SELECT schema_name FROM public.tenants "
#                     "WHERE status='ACTIVE' AND deleted_at IS NULL"
#                 )
#             )
#             schemas = [row[0] for row in result.fetchall()]
#     except Exception as exc:  # noqa: BLE001
#         logger.warning("reply_poller.no_tenants_table", error=str(exc))
#         schemas = []

#     for schema in schemas:
#         try:
#             result = await _poll_tenant(schema)
#             summary["tenants_polled"] += 1
#             summary["sequences_checked"] += result["sequences_checked"]
#             summary["replies_found"] += result["replies_found"]
#             summary["bounces_found"] += result["bounces_found"]
#             summary["errors"] += result["errors"]
#         except Exception as exc:  # noqa: BLE001
#             summary["errors"] += 1
#             logger.error(
#                 "reply_poller.tenant_failed",
#                 schema=schema,
#                 error=str(exc),
#                 exc_info=True,
#             )

#     logger.info("reply_poller.complete", **summary)
#     return summary


# async def _poll_tenant(schema: str) -> dict[str, Any]:
#     """Poll one tenant schema for reply + bounce events."""
#     result: dict[str, Any] = {
#         "sequences_checked": 0,
#         "replies_found": 0,
#         "bounces_found": 0,
#         "errors": 0,
#     }

#     mb_client = await _get_mb_client_for_schema(schema)
#     if mb_client is None:
#         logger.debug("reply_poller.no_mailbridge_config", schema=schema)
#         return result

#     # Load all Sent sequences that still need checking.
#     # We load both unreplied AND unbounced in a single query to minimise DB round-trips.
#     sequences_to_check: list[dict[str, Any]] = []
#     try:
#         async with AsyncSessionLocal() as db:
#             await db.execute(text(f'SET search_path TO "{schema}", public'))
#             # String literal 'Sent' avoids the ::email_status cross-schema cast error
#             rows = (await db.execute(
#                 select(Sequence)
#                 .where(Sequence.status == 'Sent')
#                 .where(Sequence.sentAt.is_not(None))
#                 # Only include sequences with a usable poll identity
#                 .where(
#                     (Sequence.sent_via_external_user_id.is_not(None))
#                     | (
#                         (Sequence.owner_user_id.is_not(None))
#                         & (Sequence.owner_user_id != "system")
#                     )
#                 )
#             )).scalars().all()

#             for seq in rows:
#                 poll_identity = (
#                     getattr(seq, "sent_via_external_user_id", None)
#                     or seq.owner_user_id
#                 )
#                 sequences_to_check.append({
#                     "id": seq.id,
#                     "poll_identity": poll_identity,
#                     "sentAt": seq.sentAt,
#                     "prospectId": seq.prospectId,
#                     "repliedAt": seq.repliedAt,
#                     "bouncedAt": seq.bouncedAt,
#                 })
#     except Exception as exc:  # noqa: BLE001
#         logger.error("reply_poller.tenant_load_failed", schema=schema, error=str(exc))
#         result["errors"] += 1
#         return result

#     result["sequences_checked"] = len(sequences_to_check)
#     if not sequences_to_check:
#         return result

#     # Pre-resolve all prospect emails in one pass to avoid N+1 queries
#     prospect_ids = list({s["prospectId"] for s in sequences_to_check})
#     prospect_email_map = await _resolve_prospect_emails(schema, prospect_ids)

#     # ── SCAN 1: Replies ──────────────────────────────────────────────────────
#     for seq_data in sequences_to_check:
#         if seq_data["repliedAt"] is not None:
#             continue  # already replied — skip
#         try:
#             found = await _check_for_reply(schema, seq_data, mb_client, prospect_email_map)
#             if found:
#                 result["replies_found"] += 1
#         except Exception as exc:  # noqa: BLE001
#             result["errors"] += 1
#             logger.warning(
#                 "reply_poller.reply_check_failed",
#                 schema=schema,
#                 sequence_id=seq_data["id"],
#                 error=str(exc),
#             )

#     # ── SCAN 2: Bounces ──────────────────────────────────────────────────────
#     for seq_data in sequences_to_check:
#         if seq_data["bouncedAt"] is not None:
#             continue  # already bounced — skip
#         if seq_data["repliedAt"] is not None:
#             continue  # if they replied they didn't bounce
#         try:
#             found = await _check_for_bounce(schema, seq_data, mb_client, prospect_email_map)
#             if found:
#                 result["bounces_found"] += 1
#         except Exception as exc:  # noqa: BLE001
#             result["errors"] += 1
#             logger.warning(
#                 "reply_poller.bounce_check_failed",
#                 schema=schema,
#                 sequence_id=seq_data["id"],
#                 error=str(exc),
#             )

#     return result


# # ── SCAN 1: Reply detection ────────────────────────────────────────────────────

# async def _check_for_reply(
#     schema: str,
#     seq_data: dict[str, Any],
#     mb_client: Any,
#     prospect_email_map: dict[str, str],
# ) -> bool:
#     """Check one sequence for a reply from the prospect."""
#     sequence_id: str = seq_data["id"]
#     poll_identity: str = seq_data["poll_identity"]
#     sent_at: datetime = seq_data["sentAt"]
#     prospect_id: str = seq_data["prospectId"]

#     prospect_email = prospect_email_map.get(prospect_id, "")
#     if not prospect_email:
#         return False

#     if sent_at.tzinfo is None:
#         sent_at = sent_at.replace(tzinfo=timezone.utc)

#     try:
#         replies = await mb_client.get_connect_replies(
#             external_user_id=poll_identity,
#             sender=prospect_email,
#             since=sent_at,
#         )
#     except RuntimeError as exc:
#         logger.warning(
#             "reply_poller.mailbridge_call_failed",
#             schema=schema,
#             sequence_id=sequence_id,
#             poll_identity=poll_identity,
#             error=str(exc),
#         )
#         return False

#     if not replies:
#         return False

#     # Filter out any NDRs that MailBridge may have stored with a matching sender
#     # (shouldn't happen with the prospect email filter, but be safe)
#     real_replies = [
#         r for r in replies
#         if not _is_ndr_sender(r.get("from_address", ""))
#     ]
#     if not real_replies:
#         return False

#     # Take the earliest real reply
#     replies_sorted = sorted(real_replies, key=lambda r: r.get("received_at") or "")
#     earliest = replies_sorted[0]

#     await _stamp_reply(schema, sequence_id, earliest)

#     logger.info(
#         "reply_poller.reply_recorded",
#         schema=schema,
#         sequence_id=sequence_id,
#         poll_identity=poll_identity,
#         from_address=earliest.get("from_address"),
#         received_at=earliest.get("received_at"),
#     )
#     return True


# # ── SCAN 2: Bounce detection ───────────────────────────────────────────────────

# async def _check_for_bounce(
#     schema: str,
#     seq_data: dict[str, Any],
#     mb_client: Any,
#     prospect_email_map: dict[str, str],
# ) -> bool:
#     """Check one sequence for a bounce NDR.

#     Strategy: poll MailBridge for NDR emails received after the sequence
#     was sent. MailBridge stores NDRs in reply_events just like real replies
#     (from_address = "Mail Delivery Subsystem <mailer-daemon@googlemail.com>").

#     We call GET /auth/connect/replies once per NDR sender variant. When we
#     get NDRs, we parse the body to extract the failed recipient address and
#     match it against this sequence's prospect email.
#     """
#     sequence_id: str = seq_data["id"]
#     poll_identity: str = seq_data["poll_identity"]
#     sent_at: datetime = seq_data["sentAt"]
#     prospect_id: str = seq_data["prospectId"]

#     prospect_email = prospect_email_map.get(prospect_id, "")
#     if not prospect_email:
#         return False

#     if sent_at.tzinfo is None:
#         sent_at = sent_at.replace(tzinfo=timezone.utc)

#     # Try each NDR sender variant
#     all_ndrs: list[dict[str, Any]] = []
#     for ndr_sender in _NDR_SENDERS:
#         try:
#             ndrs = await mb_client.get_connect_replies(
#                 external_user_id=poll_identity,
#                 sender=ndr_sender,
#                 since=sent_at,
#             )
#             if ndrs:
#                 all_ndrs.extend(ndrs)
#         except RuntimeError:
#             # Ignore per-sender failures — try next variant
#             pass

#     if not all_ndrs:
#         return False

#     # Deduplicate by message_id
#     seen_ids: set[str] = set()
#     unique_ndrs: list[dict[str, Any]] = []
#     for ndr in all_ndrs:
#         mid = ndr.get("message_id", "")
#         if mid not in seen_ids:
#             seen_ids.add(mid)
#             unique_ndrs.append(ndr)

#     # For each NDR, check if the failed recipient matches this sequence's prospect
#     for ndr in unique_ndrs:
#         body = ndr.get("body") or ndr.get("body_text") or ""
#         subject = ndr.get("subject") or ""

#         failed_recipient = _extract_failed_recipient(body)
#         if not failed_recipient:
#             # Cannot extract recipient from body. Try matching prospect email
#             # directly in the subject line (uncommon fallback).
#             if prospect_email.lower() in subject.lower():
#                 failed_recipient = prospect_email.lower()
#             else:
#                 logger.warning(
#                     "reply_poller.ndr_no_recipient",
#                     schema=schema,
#                     sequence_id=sequence_id,
#                     ndr_message_id=ndr.get("message_id"),
#                     body_empty=not bool(body),
#                     body_preview=body[:120] if body else "(empty)",
#                 )
#                 continue

#         if failed_recipient.lower() != prospect_email.lower():
#             # This NDR is for a different prospect — skip
#             continue

#         # This NDR matches our prospect. Stamp the bounce.
#         bounce_reason = _extract_bounce_reason(body, subject)
#         received_at_str = ndr.get("received_at")
#         received_at = _parse_iso(received_at_str) or datetime.now(timezone.utc)

#         await _stamp_bounce(schema, sequence_id, bounce_reason, received_at)

#         logger.info(
#             "reply_poller.bounce_recorded",
#             schema=schema,
#             sequence_id=sequence_id,
#             poll_identity=poll_identity,
#             failed_recipient=failed_recipient,
#             bounce_reason=bounce_reason,
#             received_at=received_at.isoformat(),
#         )
#         return True

#     return False


# def _is_ndr_sender(from_address: str) -> bool:
#     """Return True if this from_address looks like a bounce/NDR sender."""
#     addr = from_address.lower()
#     return any(
#         ndr in addr
#         for ndr in ["mailer-daemon", "postmaster", "mail delivery", "delivery subsystem"]
#     )


# # ── Write helpers ──────────────────────────────────────────────────────────────

# async def _stamp_reply(
#     schema: str,
#     sequence_id: str,
#     reply_event: dict[str, Any],
# ) -> None:
#     """Stamp repliedAt on the Sequence and create a ReplyDraft.

#     Uses raw SQL UPDATE for status + repliedAt to avoid the ORM
#     search_path loss pattern (asyncpg strips SET search_path on pool
#     checkout after commit; ORM attribute access after commit causes
#     PendingRollbackError on the next operation).
#     """
#     received_at = _parse_iso(reply_event.get("received_at")) or datetime.now(timezone.utc)
#     subject = reply_event.get("subject") or "(no subject)"
#     raw_body = (
#         reply_event.get("body")
#         or reply_event.get("body_text")
#         or ""
#     )
#     body = _extract_reply_text(raw_body, subject)
#     message_id = reply_event.get("message_id") or ""

#     async with AsyncSessionLocal() as db:
#         await db.execute(text(f'SET search_path TO "{schema}", public'))

#         # Raw SQL UPDATE — avoids enum cast + ORM-after-commit issues
#         await db.execute(
#             text(
#                 'UPDATE "Sequence" '
#                 "SET status = 'Replied', \"repliedAt\" = :replied_at "
#                 "WHERE id = :seq_id AND \"repliedAt\" IS NULL"
#             ),
#             {"replied_at": received_at, "seq_id": sequence_id},
#         )
#         await db.commit()

#     # Create ReplyDraft in a separate session — completely isolated
#     try:
#         from app.features.mailbridge.service import MailBridgeService
#         from app.schemas.mailbridge import MailBridgeTrackingEvent

#         event = MailBridgeTrackingEvent(
#             event="replied",
#             messageId=message_id,
#             sequenceId=sequence_id,
#             timestamp=received_at,
#             recipient=None,
#             reason=None,
#             payload={"body": body},
#         )
#         svc = MailBridgeService()
#         async with AsyncSessionLocal() as db2:
#             await db2.execute(text(f'SET search_path TO "{schema}", public'))
#             await svc._auto_create_reply_draft(db2, await _load_sequence(db2, sequence_id), event, received_at)
#             await db2.commit()
#     except Exception as exc:  # noqa: BLE001 — best-effort, never blocks stamp
#         logger.warning(
#             "reply_poller.reply_draft_create_failed",
#             schema=schema,
#             sequence_id=sequence_id,
#             error=str(exc),
#         )


# async def _stamp_bounce(
#     schema: str,
#     sequence_id: str,
#     bounce_reason: str,
#     bounced_at: datetime,
# ) -> None:
#     """Stamp bouncedAt + bounceReason on the Sequence using raw SQL.

#     Raw SQL avoids:
#     1. The SAEnum ::email_status cross-schema cast error
#     2. ORM attribute mutation after search_path loss
#     """
#     async with AsyncSessionLocal() as db:
#         await db.execute(text(f'SET search_path TO "{schema}", public'))
#         await db.execute(
#             text(
#                 'UPDATE "Sequence" '
#                 "SET status = 'Bounced', "
#                 '    "bouncedAt" = :bounced_at, '
#                 '    "bounceReason" = :bounce_reason '
#                 "WHERE id = :seq_id AND \"bouncedAt\" IS NULL"
#             ),
#             {
#                 "bounced_at": bounced_at,
#                 "bounce_reason": bounce_reason[:500],  # guard against very long reasons
#                 "seq_id": sequence_id,
#             },
#         )
#         await db.commit()

#         # Also record quota — best-effort
#         try:
#             from app.features.user_email_quota.service import UserEmailQuotaService
#             # Reload seq to get owner_user_id — fresh query after commit
#             await db.execute(text(f'SET search_path TO "{schema}", public'))
#             seq = await _load_sequence(db, sequence_id)
#             owner_id = getattr(seq, "owner_user_id", None) if seq else None
#             if owner_id and owner_id != "system":
#                 quota_svc = UserEmailQuotaService()
#                 await quota_svc.record_bounce(db, owner_id, count=1)
#                 await db.commit()
#         except Exception as exc:  # noqa: BLE001
#             logger.debug(
#                 "reply_poller.bounce_quota_record_failed",
#                 schema=schema,
#                 sequence_id=sequence_id,
#                 error=str(exc),
#             )


# async def _load_sequence(db: Any, sequence_id: str) -> Sequence | None:
#     """Load a Sequence row in the current session's search_path."""
#     result = await db.execute(
#         select(Sequence).where(Sequence.id == sequence_id)
#     )
#     return result.scalar_one_or_none()


# # ── Lookup helpers ─────────────────────────────────────────────────────────────

# async def _resolve_prospect_emails(schema: str, prospect_ids: list[str]) -> dict[str, str]:
#     """Return {prospect_id: decrypted_email} for a batch of IDs."""
#     if not prospect_ids:
#         return {}
#     result_map: dict[str, str] = {}
#     try:
#         async with AsyncSessionLocal() as db:
#             await db.execute(text(f'SET search_path TO "{schema}", public'))
#             rows = (await db.execute(
#                 select(Prospect).where(Prospect.id.in_(prospect_ids))
#             )).scalars().all()

#         for prospect in rows:
#             if getattr(prospect, "anonymized", False):
#                 continue
#             raw_email: str = getattr(prospect, "email", None) or ""
#             if not raw_email:
#                 continue
#             try:
#                 from app.services.pii_service import PiiService
#                 decrypted = PiiService().decrypt_field(raw_email) or raw_email
#             except Exception:  # noqa: BLE001
#                 decrypted = raw_email
#             if decrypted:
#                 result_map[prospect.id] = decrypted.strip().lower()
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "reply_poller.prospect_email_batch_failed",
#             schema=schema,
#             error=str(exc),
#         )
#     return result_map


# async def _get_mb_client_for_schema(schema: str) -> Any | None:
#     """Load the active MailBridgeConfig for a schema and build a client."""
#     from app.features.mailbridge.mailbridge_client import MailBridgeClient
#     from app.models.config_models import MailBridgeConfig

#     try:
#         async with AsyncSessionLocal() as db:
#             await db.execute(text(f'SET search_path TO "{schema}", public'))
#             result = await db.execute(
#                 select(MailBridgeConfig)
#                 .where(MailBridgeConfig.isActive.is_(True))
#                 .limit(1)
#             )
#             config = result.scalar_one_or_none()
#             if config is None:
#                 return None
#             base_url: str = config.baseUrl or ""
#             api_key: str = getattr(config, "mailbridge_api_key", "") or ""
#             if not base_url:
#                 return None
#             return MailBridgeClient(base_url=base_url, api_key=api_key)
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "reply_poller.config_load_failed",
#             schema=schema,
#             error=str(exc),
#         )
#         return None


# def _parse_iso(value: str | None) -> datetime | None:
#     """Parse an ISO-8601 string into a timezone-aware datetime, or None."""
#     if not value:
#         return None
#     try:
#         dt = datetime.fromisoformat(value)
#         if dt.tzinfo is None:
#             dt = dt.replace(tzinfo=timezone.utc)
#         return dt
#     except ValueError:
#         return None


# # ── Scheduler wiring ───────────────────────────────────────────────────────────

# async def _reply_poll_wrapper() -> None:
#     """APScheduler entry point — catches all errors so the job never dies."""
#     try:
#         await run_reply_poll_all_tenants()
#     except Exception as exc:  # noqa: BLE001
#         logger.error("reply_poller.unhandled_error", error=str(exc), exc_info=True)


# def register_reply_poll_job(scheduler: Any) -> None:
#     """Register the reply+bounce poll job on an existing AsyncIOScheduler."""
#     settings = get_settings()

#     poll_enabled: bool = getattr(settings, "MAILBRIDGE_REPLY_POLL_ENABLED", True)
#     if not poll_enabled:
#         logger.info("reply_poller.disabled", reason="MAILBRIDGE_REPLY_POLL_ENABLED=false")
#         return

#     if not settings.MAILBRIDGE_DEFAULT_URL:
#         logger.info(
#             "reply_poller.skipped",
#             reason="MAILBRIDGE_DEFAULT_URL not set",
#         )
#         return

#     poll_seconds: int = getattr(settings, "MAILBRIDGE_REPLY_POLL_SECONDS", 120)

#     scheduler.add_job(
#         _reply_poll_wrapper,
#         "interval",
#         seconds=poll_seconds,
#         id="outrena_reply_poll",
#         max_instances=1,
#         coalesce=True,
#         replace_existing=True,
#     )
#     logger.info(
#         "reply_poller.registered",
#         poll_seconds=poll_seconds,
#         job_id="outrena_reply_poll",
#     )


# __all__ = [
#     "run_reply_poll_all_tenants",
#     "register_reply_poll_job",
# ]

"""
app/features/mailbridge/reply_poller.py
========================================
Background scheduler task: poll MailBridge for replies AND bounces on
sent sequences, and surface them in Outrena's tracking system.

ARCHITECTURE
============

MailBridge is the only source of inbound email data. It stores every
inbound email in {tenant_schema}.reply_events regardless of what kind
of email it is — real replies from prospects AND NDR bounce notifications
from mailer-daemon are both rows in reply_events.

The key insight: reply_events.from_address tells us whether the inbound
email is a real reply or a bounce notification:
  - Real reply:  from_address = the prospect's email address
  - NDR bounce:  from_address contains "mailer-daemon" or "postmaster"

So this poller runs TWO scans per tenant per tick:

SCAN 1 — REPLIES
  For each Sequence with status=Sent, repliedAt=NULL:
    Call GET /auth/connect/replies?sender=<prospect.email>&since=<sentAt>
    If results found → stamp repliedAt, create ReplyDraft, AI-categorize.

SCAN 2 — BOUNCES
  For each Sequence with status=Sent, bouncedAt=NULL:
    Call GET /auth/connect/replies?sender=mailer-daemon@googlemail.com&since=<sentAt>
    Parse body to extract the failed recipient email.
    If failed recipient matches this sequence's prospect email → stamp
    bouncedAt + bounceReason, flip status to Bounced.

    We also try postmaster@gmail.com and mailer-daemon (LIKE pattern)
    as MailBridge normalises the from_address via LOWER LIKE matching.

DB WRITE SAFETY
===============
apply_tracking_event() uses raw SQL UPDATE (not ORM attribute mutation)
to avoid the search_path loss pattern: after db.commit(), asyncpg
returns the connection to the pool and strips the tenant search_path.
ORM attribute mutation after commit causes PendingRollbackError.

ENUM CAST SAFETY
================
All WHERE clauses on Sequence.status use string literals ('Sent',
'Bounced') not EmailStatus enum values. SQLAlchemy's SAEnum column type
adds ::email_status to bind params even for string values, which causes
"cannot cast type tenant_X.email_status to email_status" cross-schema
errors in asyncpg. String literals bypass the cast entirely.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.models.campaign_models import Sequence
from app.models.prospect_models import Prospect

logger = structlog.get_logger(__name__)

# NDR sender patterns — all patterns MailBridge stores from Gmail/Outlook NDRs.
# MailBridge normalises from_address to lowercase when storing, so we match lower.
_NDR_SENDERS = [
    "mailer-daemon@googlemail.com",
    "mailer-daemon@gmail.com",
    "postmaster@gmail.com",
    "mailer-daemon",
]

# Regex patterns to extract the failed recipient from an NDR body.
# Gmail NDRs are multipart/report. MailBridge captures only the text/plain part.
# The machine-readable message/delivery-status part (with Final-Recipient header)
# is NOT stored — so we parse the human-readable plain text instead.
_FAILED_RECIPIENT_PATTERNS = [
    # machine-readable DSN (if body_text ever includes delivery-status content)
    re.compile(r"final-recipient\s*:\s*rfc822\s*;\s*([^\s,\r\n]+)", re.IGNORECASE),
    re.compile(r"original-recipient\s*:\s*rfc822\s*;\s*([^\s,\r\n]+)", re.IGNORECASE),
    re.compile(r"x-failed-recipients?\s*:\s*([^\s,\r\n]+)", re.IGNORECASE),
    # human-readable Gmail NDR text/plain patterns (most common)
    re.compile(r"your message wasn.t delivered to\s+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", re.IGNORECASE),
    re.compile(r"delivering your message to\s+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", re.IGNORECASE),
    re.compile(r"your message to\s+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\s+couldn", re.IGNORECASE),
    re.compile(r"<([^>]+@[^>]+)>\s+(?:does not exist|not found|address not found|couldn)", re.IGNORECASE),
    # broad fallback: email near delivery-failure keywords
    re.compile(r"(?:deliver|undeliver|bounce|failed|returned).*?([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", re.IGNORECASE),
]


def _extract_failed_recipient(body: str) -> str | None:
    """Extract the bounced email address from an NDR body.

    Parses the human-readable text/plain portion of Gmail NDRs.
    The machine-readable delivery-status part is not stored by MailBridge.
    """
    if not body:
        return None
    for pattern in _FAILED_RECIPIENT_PATTERNS:
        match = pattern.search(body)
        if match:
            candidate = match.group(1).strip().lower().rstrip(".,><;)")
            if "@" in candidate and "." in candidate.split("@")[-1] and len(candidate) > 5:
                if "mailer-daemon" in candidate or "postmaster" in candidate:
                    continue
                return candidate
    return None


def _extract_bounce_reason(body: str, subject: str) -> str:
    """Extract a human-readable bounce reason from the NDR body."""
    # Look for SMTP status codes like "550 5.1.1 user not found"
    smtp_match = re.search(r"\b(5\d{2})\s+[\d.]+\s+([^\r\n]{5,80})", body, re.IGNORECASE)
    if smtp_match:
        return f"{smtp_match.group(1)} {smtp_match.group(2).strip()}"

    # Common Gmail NDR phrases
    reason_patterns = [
        re.compile(r"address not found", re.IGNORECASE),
        re.compile(r"user.*not found", re.IGNORECASE),
        re.compile(r"no such user", re.IGNORECASE),
        re.compile(r"recipient address rejected", re.IGNORECASE),
        re.compile(r"mailbox.*full", re.IGNORECASE),
        re.compile(r"over.*quota", re.IGNORECASE),
        re.compile(r"account.*does not exist", re.IGNORECASE),
        re.compile(r"delivery.*failed", re.IGNORECASE),
    ]
    for p in reason_patterns:
        if p.search(body):
            return p.pattern.replace(".*", " ").replace(r"\.", ".").strip()

    # Fall back to subject line (e.g. "Delivery Status Notification (Failure)")
    if subject:
        return subject[:120]
    return "Delivery failure"


def _extract_reply_text(full_body: str, subject: str) -> str:
    """Extract only the prospect's new reply text from a full Gmail/Outlook thread body.

    Gmail and Outlook include the original sent email as a quoted block at the
    bottom of every reply. Without stripping this, every ReplyDraft shows the
    same content (the original email template) instead of what the prospect wrote.

    Stripping patterns (in order of priority):
      1. Gmail:   "On <date>, <name> <email> wrote:" followed by "> " quoted lines
      2. Gmail:   "---------- Forwarded message ----------"
      3. Outlook: "From: ... Sent: ... To: ... Subject: ..."
      4. Generic: Lines starting with ">" (quoted reply lines)
      5. Fallback: Return full body if no quote markers found
    """
    import re as _re

    if not full_body:
        return f"[Reply received — subject: {subject}]"

    lines = full_body.split('\n')
    quote_start_idx: int | None = None

    # Pattern 1: Gmail "On <date>, <name> wrote:" — single line
    gmail_quote_re = _re.compile(
        r'^On .{5,100} wrote:$',
        _re.IGNORECASE
    )
    # Pattern 2: Gmail "On <date>\n<name> <email>\nwrote:" — multi-line (2-3 lines)
    gmail_quote_multiline_re = _re.compile(
        r'^On \w{3},',
        _re.IGNORECASE
    )
    # Pattern 3: Forwarded message divider
    forward_re = _re.compile(
        r'^-{5,}\s*(Forwarded|Original)\s*(message|email)',
        _re.IGNORECASE
    )
    # Pattern 4: Outlook header block
    outlook_re = _re.compile(
        r'^From:\s*.+',
        _re.IGNORECASE
    )

    for i, line in enumerate(lines):
        stripped = line.strip()
        if gmail_quote_re.match(stripped):
            quote_start_idx = i
            break
        if gmail_quote_multiline_re.match(stripped):
            # Check if this multi-line pattern completes within next 3 lines
            context = ' '.join(lines[i:i+3])
            if 'wrote:' in context.lower():
                quote_start_idx = i
                break
        if forward_re.match(stripped):
            quote_start_idx = i
            break
        if outlook_re.match(stripped) and i > 2:
            # Outlook header only valid if not at very top (avoid matching real From: headers)
            quote_start_idx = i
            break

    if quote_start_idx is not None:
        reply_lines = lines[:quote_start_idx]
    else:
        # Fallback: strip lines starting with ">" (quoted lines)
        reply_lines = [l for l in lines if not l.strip().startswith('>')]

    reply_text = '\n'.join(reply_lines).strip()

    # If stripping left us with nothing, return the full body
    if not reply_text or len(reply_text) < 5:
        return full_body.strip() or f"[Reply received — subject: {subject}]"

    return reply_text





# ── Main entry points ──────────────────────────────────────────────────────────

async def run_reply_poll_all_tenants() -> dict[str, Any]:
    """Top-level entry point called by APScheduler every MAILBRIDGE_REPLY_POLL_SECONDS."""
    summary: dict[str, Any] = {
        "tenants_polled": 0,
        "sequences_checked": 0,
        "replies_found": 0,
        "bounces_found": 0,
        "errors": 0,
    }

    schemas: list[str] = []
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT schema_name FROM public.tenants "
                    "WHERE status='ACTIVE' AND deleted_at IS NULL"
                )
            )
            schemas = [row[0] for row in result.fetchall()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("reply_poller.no_tenants_table", error=str(exc))
        schemas = []

    for schema in schemas:
        try:
            result = await _poll_tenant(schema)
            summary["tenants_polled"] += 1
            summary["sequences_checked"] += result["sequences_checked"]
            summary["replies_found"] += result["replies_found"]
            summary["bounces_found"] += result["bounces_found"]
            summary["errors"] += result["errors"]
        except Exception as exc:  # noqa: BLE001
            summary["errors"] += 1
            logger.error(
                "reply_poller.tenant_failed",
                schema=schema,
                error=str(exc),
                exc_info=True,
            )

    logger.info("reply_poller.complete", **summary)
    return summary


async def _poll_tenant(schema: str) -> dict[str, Any]:
    """Poll one tenant schema for reply + bounce events."""
    result: dict[str, Any] = {
        "sequences_checked": 0,
        "replies_found": 0,
        "bounces_found": 0,
        "errors": 0,
    }

    mb_client = await _get_mb_client_for_schema(schema)
    if mb_client is None:
        logger.debug("reply_poller.no_mailbridge_config", schema=schema)
        return result

    # Load all Sent sequences that still need checking.
    # We load both unreplied AND unbounced in a single query to minimise DB round-trips.
    sequences_to_check: list[dict[str, Any]] = []
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text(f'SET search_path TO "{schema}", public'))
            # String literals avoid the ::email_status cross-schema cast error.
            # Also include status='Bounced' with bouncedAt=NULL — these were flipped
            # to Bounced by earlier code paths that didn't stamp the timestamp,
            # causing a mismatch between the stats card (counts bouncedAt IS NOT NULL)
            # and the Bounced tab (counts status='Bounced'). The bounce scan will
            # backfill bouncedAt for them automatically.
            from sqlalchemy import or_ as _or_
            rows = (await db.execute(
                select(Sequence)
                .where(
                    _or_(
                        Sequence.status == 'Sent',
                        (Sequence.status == 'Bounced') & Sequence.bouncedAt.is_(None),
                    )
                )
                .where(Sequence.sentAt.is_not(None))
                # Only include sequences with a usable poll identity
                .where(
                    (Sequence.sent_via_external_user_id.is_not(None))
                    | (
                        (Sequence.owner_user_id.is_not(None))
                        & (Sequence.owner_user_id != "system")
                    )
                )
            )).scalars().all()

            for seq in rows:
                poll_identity = (
                    getattr(seq, "sent_via_external_user_id", None)
                    or seq.owner_user_id
                )
                sequences_to_check.append({
                    "id": seq.id,
                    "poll_identity": poll_identity,
                    "sentAt": seq.sentAt,
                    "prospectId": seq.prospectId,
                    "repliedAt": seq.repliedAt,
                    "bouncedAt": seq.bouncedAt,
                })
    except Exception as exc:  # noqa: BLE001
        logger.error("reply_poller.tenant_load_failed", schema=schema, error=str(exc))
        result["errors"] += 1
        return result

    result["sequences_checked"] = len(sequences_to_check)
    if not sequences_to_check:
        return result

    # Pre-resolve all prospect emails in one pass to avoid N+1 queries
    prospect_ids = list({s["prospectId"] for s in sequences_to_check})
    prospect_email_map = await _resolve_prospect_emails(schema, prospect_ids)

    # ── SCAN 1: Replies ──────────────────────────────────────────────────────
    for seq_data in sequences_to_check:
        if seq_data["repliedAt"] is not None:
            continue  # already replied — skip
        try:
            found = await _check_for_reply(schema, seq_data, mb_client, prospect_email_map)
            if found:
                result["replies_found"] += 1
        except Exception as exc:  # noqa: BLE001
            result["errors"] += 1
            logger.warning(
                "reply_poller.reply_check_failed",
                schema=schema,
                sequence_id=seq_data["id"],
                error=str(exc),
            )

    # ── SCAN 2: Bounces grouped by poll_identity ─────────────────────────────
    # Group sequences by poll_identity (sender's Keycloak UUID).
    # Each unique sender has their own connected mailbox in MailBridge —
    # NDRs land in the SENDER's inbox, not a shared inbox.
    # Grouping means one MailBridge API call per sender, not one per sequence,
    # and correctly polls each user's own mailbox for their NDRs.
    from collections import defaultdict as _dd
    bounce_groups: dict = _dd(list)
    for seq_data in sequences_to_check:
        if seq_data["bouncedAt"] is not None:
            continue
        if seq_data["repliedAt"] is not None:
            continue
        bounce_groups[seq_data["poll_identity"]].append(seq_data)

    for poll_identity, group_seqs in bounce_groups.items():
        try:
            found_count = await _check_bounces_for_identity(
                schema, poll_identity, group_seqs, mb_client, prospect_email_map
            )
            result["bounces_found"] += found_count
        except Exception as exc:  # noqa: BLE001
            result["errors"] += 1
            logger.warning(
                "reply_poller.bounce_scan_failed",
                schema=schema,
                poll_identity=poll_identity,
                error=str(exc),
            )

    return result


# ── SCAN 1: Reply detection ────────────────────────────────────────────────────

async def _check_for_reply(
    schema: str,
    seq_data: dict[str, Any],
    mb_client: Any,
    prospect_email_map: dict[str, str],
) -> bool:
    """Check one sequence for a reply from the prospect."""
    sequence_id: str = seq_data["id"]
    poll_identity: str = seq_data["poll_identity"]
    sent_at: datetime = seq_data["sentAt"]
    prospect_id: str = seq_data["prospectId"]

    prospect_email = prospect_email_map.get(prospect_id, "")
    if not prospect_email:
        return False

    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    try:
        replies = await mb_client.get_connect_replies(
            external_user_id=poll_identity,
            sender=prospect_email,
            since=sent_at,
        )
    except RuntimeError as exc:
        logger.warning(
            "reply_poller.mailbridge_call_failed",
            schema=schema,
            sequence_id=sequence_id,
            poll_identity=poll_identity,
            error=str(exc),
        )
        return False

    if not replies:
        return False

    # Filter out any NDRs that MailBridge may have stored with a matching sender
    # (shouldn't happen with the prospect email filter, but be safe)
    real_replies = [
        r for r in replies
        if not _is_ndr_sender(r.get("from_address", ""))
    ]
    if not real_replies:
        return False

    # Take the earliest real reply
    replies_sorted = sorted(real_replies, key=lambda r: r.get("received_at") or "")
    earliest = replies_sorted[0]

    await _stamp_reply(schema, sequence_id, earliest)

    logger.info(
        "reply_poller.reply_recorded",
        schema=schema,
        sequence_id=sequence_id,
        poll_identity=poll_identity,
        from_address=earliest.get("from_address"),
        received_at=earliest.get("received_at"),
    )
    return True


# ── SCAN 2: Bounce detection (grouped by sender identity) ─────────────────────

async def _check_bounces_for_identity(
    schema: str,
    poll_identity: str,
    identity_sequences: list[dict[str, Any]],
    mb_client: Any,
    prospect_email_map: dict[str, str],
) -> int:
    """Check all sequences sent by one sender identity for NDR bounces.

    Groups the bounce scan by poll_identity so we make ONE MailBridge call
    per unique sender account instead of one per sequence.

    Multi-user tenant fix: NDRs from emails sent by pantrangamsudheer@gmail.com
    land in THAT account's IMAP inbox (linked to the manager's external_user_id
    in MailBridge). We must poll using that specific external_user_id, not the
    tenant admin's UUID. By grouping per poll_identity we naturally poll the
    right mailbox for each sender.

    Returns the number of bounces recorded.
    """
    if not identity_sequences:
        return 0

    # Use the earliest sentAt across all sequences for this identity.
    # One API call covers NDRs for all sequences sent by this user.
    earliest_sent_at = min(
        (s["sentAt"] for s in identity_sequences if s["sentAt"]),
        default=None,
    )
    if earliest_sent_at is None:
        return 0
    if earliest_sent_at.tzinfo is None:
        earliest_sent_at = earliest_sent_at.replace(tzinfo=timezone.utc)

    # Fetch all NDRs for this sender since the earliest send
    all_ndrs: list[dict[str, Any]] = []
    for ndr_sender in _NDR_SENDERS:
        try:
            ndrs = await mb_client.get_connect_replies(
                external_user_id=poll_identity,
                sender=ndr_sender,
                since=earliest_sent_at,
            )
            if ndrs:
                all_ndrs.extend(ndrs)
        except RuntimeError:
            pass

    if not all_ndrs:
        return 0

    # Deduplicate by message_id
    seen_ids: set[str] = set()
    unique_ndrs: list[dict[str, Any]] = []
    for ndr in all_ndrs:
        mid = ndr.get("message_id", "")
        if mid not in seen_ids:
            seen_ids.add(mid)
            unique_ndrs.append(ndr)

    # Parse each NDR once — extract failed_recipient and bounce_reason
    parsed_ndrs: list[dict[str, Any]] = []
    for ndr in unique_ndrs:
        body = ndr.get("body") or ndr.get("body_text") or ""
        subject = ndr.get("subject") or ""
        failed_recipient = _extract_failed_recipient(body)
        if not failed_recipient:
            logger.warning(
                "reply_poller.ndr_no_recipient",
                schema=schema,
                poll_identity=poll_identity,
                ndr_message_id=ndr.get("message_id"),
                body_empty=not bool(body),
                body_preview=body[:120] if body else "(empty)",
            )
            continue
        parsed_ndrs.append({
            "failed_recipient": failed_recipient.lower(),
            "bounce_reason": _extract_bounce_reason(body, subject),
            "received_at": _parse_iso(ndr.get("received_at")) or datetime.now(timezone.utc),
        })

    if not parsed_ndrs:
        return 0

    # Build lookup: {prospect_email_lower: [parsed_ndr, ...]}
    ndr_by_email: dict[str, list[dict]] = {}
    for pndr in parsed_ndrs:
        ndr_by_email.setdefault(pndr["failed_recipient"], []).append(pndr)

    bounces_recorded = 0
    for seq_data in identity_sequences:
        sequence_id = seq_data["id"]
        sent_at = seq_data["sentAt"]
        if sent_at and sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)

        prospect_email = prospect_email_map.get(seq_data["prospectId"], "")
        if not prospect_email:
            continue

        matching = ndr_by_email.get(prospect_email.lower(), [])
        if not matching:
            continue

        # Match NDR received AFTER this sequence was sent
        matched = next(
            (n for n in matching if sent_at is None or n["received_at"] >= sent_at),
            None,
        )
        if not matched:
            continue

        await _stamp_bounce(schema, sequence_id, matched["bounce_reason"], matched["received_at"])
        bounces_recorded += 1
        logger.info(
            "reply_poller.bounce_recorded",
            schema=schema,
            sequence_id=sequence_id,
            poll_identity=poll_identity,
            failed_recipient=prospect_email,
            bounce_reason=matched["bounce_reason"],
            received_at=matched["received_at"].isoformat(),
        )

    return bounces_recorded

def _is_ndr_sender(from_address: str) -> bool:
    """Return True if this from_address looks like a bounce/NDR sender."""
    addr = from_address.lower()
    return any(
        ndr in addr
        for ndr in ["mailer-daemon", "postmaster", "mail delivery", "delivery subsystem"]
    )


# ── Write helpers ──────────────────────────────────────────────────────────────

async def _stamp_reply(
    schema: str,
    sequence_id: str,
    reply_event: dict[str, Any],
) -> None:
    """Stamp repliedAt on the Sequence and create a ReplyDraft.

    Uses raw SQL UPDATE for status + repliedAt to avoid the ORM
    search_path loss pattern (asyncpg strips SET search_path on pool
    checkout after commit; ORM attribute access after commit causes
    PendingRollbackError on the next operation).
    """
    received_at = _parse_iso(reply_event.get("received_at")) or datetime.now(timezone.utc)
    subject = reply_event.get("subject") or "(no subject)"
    raw_body = (
        reply_event.get("body")
        or reply_event.get("body_text")
        or ""
    )
    body = _extract_reply_text(raw_body, subject)
    message_id = reply_event.get("message_id") or ""

    async with AsyncSessionLocal() as db:
        await db.execute(text(f'SET search_path TO "{schema}", public'))

        # Raw SQL UPDATE — avoids enum cast + ORM-after-commit issues
        await db.execute(
            text(
                'UPDATE "Sequence" '
                "SET status = 'Replied', \"repliedAt\" = :replied_at "
                "WHERE id = :seq_id AND \"repliedAt\" IS NULL"
            ),
            {"replied_at": received_at, "seq_id": sequence_id},
        )
        await db.commit()

    # Create ReplyDraft in a separate session — completely isolated
    try:
        from app.features.mailbridge.service import MailBridgeService
        from app.schemas.mailbridge import MailBridgeTrackingEvent

        event = MailBridgeTrackingEvent(
            event="replied",
            messageId=message_id,
            sequenceId=sequence_id,
            timestamp=received_at,
            recipient=None,
            reason=None,
            payload={"body": body},
        )
        svc = MailBridgeService()
        async with AsyncSessionLocal() as db2:
            await db2.execute(text(f'SET search_path TO "{schema}", public'))
            await svc._auto_create_reply_draft(db2, await _load_sequence(db2, sequence_id), event, received_at)
            await db2.commit()
    except Exception as exc:  # noqa: BLE001 — best-effort, never blocks stamp
        logger.warning(
            "reply_poller.reply_draft_create_failed",
            schema=schema,
            sequence_id=sequence_id,
            error=str(exc),
        )


async def _stamp_bounce(
    schema: str,
    sequence_id: str,
    bounce_reason: str,
    bounced_at: datetime,
) -> None:
    """Stamp bouncedAt + bounceReason on the Sequence using raw SQL.

    Raw SQL avoids:
    1. The SAEnum ::email_status cross-schema cast error
    2. ORM attribute mutation after search_path loss
    """
    async with AsyncSessionLocal() as db:
        await db.execute(text(f'SET search_path TO "{schema}", public'))
        await db.execute(
            text(
                'UPDATE "Sequence" '
                "SET status = 'Bounced', "
                '    "bouncedAt" = :bounced_at, '
                '    "bounceReason" = :bounce_reason '
                "WHERE id = :seq_id AND \"bouncedAt\" IS NULL"
            ),
            {
                "bounced_at": bounced_at,
                "bounce_reason": bounce_reason[:500],  # guard against very long reasons
                "seq_id": sequence_id,
            },
        )
        await db.commit()

        # Also record quota — best-effort
        try:
            from app.features.user_email_quota.service import UserEmailQuotaService
            # Reload seq to get owner_user_id — fresh query after commit
            await db.execute(text(f'SET search_path TO "{schema}", public'))
            seq = await _load_sequence(db, sequence_id)
            owner_id = getattr(seq, "owner_user_id", None) if seq else None
            if owner_id and owner_id != "system":
                quota_svc = UserEmailQuotaService()
                await quota_svc.record_bounce(db, owner_id, count=1)
                await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "reply_poller.bounce_quota_record_failed",
                schema=schema,
                sequence_id=sequence_id,
                error=str(exc),
            )


async def _load_sequence(db: Any, sequence_id: str) -> Sequence | None:
    """Load a Sequence row in the current session's search_path."""
    result = await db.execute(
        select(Sequence).where(Sequence.id == sequence_id)
    )
    return result.scalar_one_or_none()


# ── Lookup helpers ─────────────────────────────────────────────────────────────

async def _resolve_prospect_emails(schema: str, prospect_ids: list[str]) -> dict[str, str]:
    """Return {prospect_id: decrypted_email} for a batch of IDs."""
    if not prospect_ids:
        return {}
    result_map: dict[str, str] = {}
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text(f'SET search_path TO "{schema}", public'))
            rows = (await db.execute(
                select(Prospect).where(Prospect.id.in_(prospect_ids))
            )).scalars().all()

        for prospect in rows:
            if getattr(prospect, "anonymized", False):
                continue
            raw_email: str = getattr(prospect, "email", None) or ""
            if not raw_email:
                continue
            try:
                from app.services.pii_service import PiiService
                decrypted = PiiService().decrypt_field(raw_email) or raw_email
            except Exception:  # noqa: BLE001
                decrypted = raw_email
            if decrypted:
                result_map[prospect.id] = decrypted.strip().lower()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "reply_poller.prospect_email_batch_failed",
            schema=schema,
            error=str(exc),
        )
    return result_map


async def _get_mb_client_for_schema(schema: str) -> Any | None:
    """Load the active MailBridgeConfig for a schema and build a client."""
    from app.features.mailbridge.mailbridge_client import MailBridgeClient
    from app.models.config_models import MailBridgeConfig

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text(f'SET search_path TO "{schema}", public'))
            result = await db.execute(
                select(MailBridgeConfig)
                .where(MailBridgeConfig.isActive.is_(True))
                .limit(1)
            )
            config = result.scalar_one_or_none()
            if config is None:
                return None
            base_url: str = config.baseUrl or ""
            api_key: str = getattr(config, "mailbridge_api_key", "") or ""
            if not base_url:
                return None
            return MailBridgeClient(base_url=base_url, api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "reply_poller.config_load_failed",
            schema=schema,
            error=str(exc),
        )
        return None


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string into a timezone-aware datetime, or None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


# ── Scheduler wiring ───────────────────────────────────────────────────────────

async def _reply_poll_wrapper() -> None:
    """APScheduler entry point — catches all errors so the job never dies."""
    try:
        await run_reply_poll_all_tenants()
    except Exception as exc:  # noqa: BLE001
        logger.error("reply_poller.unhandled_error", error=str(exc), exc_info=True)


def register_reply_poll_job(scheduler: Any) -> None:
    """Register the reply+bounce poll job on an existing AsyncIOScheduler."""
    settings = get_settings()

    poll_enabled: bool = getattr(settings, "MAILBRIDGE_REPLY_POLL_ENABLED", True)
    if not poll_enabled:
        logger.info("reply_poller.disabled", reason="MAILBRIDGE_REPLY_POLL_ENABLED=false")
        return

    if not settings.MAILBRIDGE_DEFAULT_URL:
        logger.info(
            "reply_poller.skipped",
            reason="MAILBRIDGE_DEFAULT_URL not set",
        )
        return

    poll_seconds: int = getattr(settings, "MAILBRIDGE_REPLY_POLL_SECONDS", 120)

    scheduler.add_job(
        _reply_poll_wrapper,
        "interval",
        seconds=poll_seconds,
        id="outrena_reply_poll",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info(
        "reply_poller.registered",
        poll_seconds=poll_seconds,
        job_id="outrena_reply_poll",
    )


__all__ = [
    "run_reply_poll_all_tenants",
    "register_reply_poll_job",
]