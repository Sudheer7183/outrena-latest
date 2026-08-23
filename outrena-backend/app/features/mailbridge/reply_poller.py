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

# #     # Load all sent-but-unreplied sequences that have a real sender.
# #     # owner_user_id IS the MailBridge external_user_id — it's the Keycloak
# #     # UUID passed to POST /connect/{provider}/start during the connect flow.
# #     sequences_to_check: list[dict[str, Any]] = []
# #     try:
# #         async with AsyncSessionLocal() as db:
# #             await db.execute(text(f'SET search_path TO "{schema}", public'))
# #             rows = (await db.execute(
# #                 select(Sequence)
# #                 .where(Sequence.status == EmailStatus.Sent)
# #                 .where(Sequence.repliedAt.is_(None))
# #                 .where(Sequence.sentAt.is_not(None))
# #                 .where(Sequence.owner_user_id.is_not(None))
# #                 .where(Sequence.owner_user_id != "system")
# #             )).scalars().all()
# #             for seq in rows:
# #                 sequences_to_check.append({
# #                     "id": seq.id,
# #                     "owner_user_id": seq.owner_user_id,
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
# #       external_user_id = seq.owner_user_id  (who sent the sequence)
# #       sender           = prospect.email     (who we expect a reply from)
# #       since            = seq.sentAt         (ignore pre-existing inbox mail)
# #     """
# #     sequence_id: str = seq_data["id"]
# #     owner_user_id: str = seq_data["owner_user_id"]
# #     sent_at: datetime = seq_data["sentAt"]
# #     prospect_id: str = seq_data["prospectId"]

# #     prospect_email = await _resolve_prospect_email(schema, prospect_id)
# #     if not prospect_email:
# #         return False

# #     if sent_at.tzinfo is None:
# #         sent_at = sent_at.replace(tzinfo=timezone.utc)

# #     try:
# #         replies = await mb_client.get_connect_replies(
# #             external_user_id=owner_user_id,
# #             sender=prospect_email,
# #             since=sent_at,
# #         )
# #     except RuntimeError as exc:
# #         logger.warning(
# #             "reply_poller.mailbridge_call_failed",
# #             schema=schema,
# #             sequence_id=sequence_id,
# #             owner_user_id=owner_user_id,
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
# #         owner_user_id=owner_user_id,
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

# #     event = MailBridgeTrackingEvent(
# #         event="replied",
# #         messageId=message_id,
# #         sequenceId=sequence_id,
# #         timestamp=received_at or datetime.now(timezone.utc),
# #         recipient=None,
# #         reason=None,
# #         payload={"body": f"[Reply received — subject: {subject}]"},
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
# Background scheduler task: poll MailBridge for replies to sent sequences
# and surface them in Outrena's Reply Inbox.

# DESIGN (final):
#   The Sequence table is the authoritative source of truth. Every sent
#   sequence has:
#     - owner_user_id: Keycloak UUID of who sent it (= external_user_id in MailBridge)
#     - prospectId:    who the email was sent to
#     - sentAt:        when it was sent (used as `since` filter)

#   For each sent-but-unreplied sequence, the poller calls:
#     GET /auth/connect/replies
#       ?external_user_id=<seq.owner_user_id>
#       &sender=<prospect.email>
#       &since=<seq.sentAt>

#   If MailBridge returns replies, the earliest one is recorded via
#   apply_tracking_event(), which stamps Sequence.repliedAt, creates a
#   ReplyDraft, and fires AI categorization.

#   No guessing about which users are connected. No querying MailBridgeConfig
#   or UserSenderIdentity. The sequence row tells us exactly who sent the
#   email and who to ask MailBridge about.

#   Edge case — owner_user_id is "system" (auto-generated sequences before
#   the campaigns/service.py fix): we skip these sequences since "system"
#   is not a real MailBridge external_user_id.
# """
# from __future__ import annotations

# from datetime import datetime, timezone
# from typing import Any

# import structlog
# from sqlalchemy import select, text

# from app.core.config import get_settings
# from app.core.database import AsyncSessionLocal, engine
# from app.models.campaign_models import Sequence
# from app.models.enums import EmailStatus
# from app.models.prospect_models import Prospect
# from app.schemas.mailbridge import MailBridgeTrackingEvent

# logger = structlog.get_logger(__name__)


# async def run_reply_poll_all_tenants() -> dict[str, Any]:
#     """Top-level entry point called by the APScheduler job."""
#     summary: dict[str, Any] = {
#         "tenants_polled": 0,
#         "sequences_checked": 0,
#         "replies_found": 0,
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
#     """Poll one tenant schema for reply events.

#     Loads all sent-but-unreplied sequences, then for each one asks
#     MailBridge: did owner_user_id's mailbox receive a reply from
#     prospect.email since sentAt?
#     """
#     result: dict[str, Any] = {
#         "sequences_checked": 0,
#         "replies_found": 0,
#         "errors": 0,
#     }

#     # Load all sent-but-unreplied sequences that have a real sender.
#     # owner_user_id IS the MailBridge external_user_id — it's the Keycloak
#     # UUID passed to POST /connect/{provider}/start during the connect flow.
#     sequences_to_check: list[dict[str, Any]] = []
#     try:
#         async with AsyncSessionLocal() as db:
#             await db.execute(text(f'SET search_path TO "{schema}", public'))
#             rows = (await db.execute(
#                 select(Sequence)
#                 .where(Sequence.status == EmailStatus.Sent)
#                 .where(Sequence.repliedAt.is_(None))
#                 .where(Sequence.sentAt.is_not(None))
#                 .where(Sequence.owner_user_id.is_not(None))
#                 .where(Sequence.owner_user_id != "system")
#             )).scalars().all()
#             for seq in rows:
#                 sequences_to_check.append({
#                     "id": seq.id,
#                     "owner_user_id": seq.owner_user_id,
#                     "sentAt": seq.sentAt,
#                     "prospectId": seq.prospectId,
#                 })
#     except Exception as exc:  # noqa: BLE001
#         logger.error("reply_poller.tenant_load_failed", schema=schema, error=str(exc))
#         result["errors"] += 1
#         return result

#     result["sequences_checked"] = len(sequences_to_check)
#     if not sequences_to_check:
#         return result

#     mb_client = await _get_mb_client_for_schema(schema)
#     if mb_client is None:
#         logger.debug("reply_poller.no_mailbridge_config", schema=schema)
#         return result

#     for seq_data in sequences_to_check:
#         try:
#             found = await _check_sequence(schema, seq_data, mb_client)
#             if found:
#                 result["replies_found"] += 1
#         except Exception as exc:  # noqa: BLE001
#             result["errors"] += 1
#             logger.warning(
#                 "reply_poller.sequence_check_failed",
#                 schema=schema,
#                 sequence_id=seq_data["id"],
#                 error=str(exc),
#             )

#     return result


# async def _check_sequence(
#     schema: str,
#     seq_data: dict[str, Any],
#     mb_client: Any,
# ) -> bool:
#     """Check one sequence for a reply in MailBridge.

#     Calls GET /auth/connect/replies with:
#       external_user_id = seq.owner_user_id  (who sent the sequence)
#       sender           = prospect.email     (who we expect a reply from)
#       since            = seq.sentAt         (ignore pre-existing inbox mail)
#     """
#     sequence_id: str = seq_data["id"]
#     owner_user_id: str = seq_data["owner_user_id"]
#     sent_at: datetime = seq_data["sentAt"]
#     prospect_id: str = seq_data["prospectId"]

#     prospect_email = await _resolve_prospect_email(schema, prospect_id)
#     if not prospect_email:
#         return False

#     if sent_at.tzinfo is None:
#         sent_at = sent_at.replace(tzinfo=timezone.utc)

#     try:
#         replies = await mb_client.get_connect_replies(
#             external_user_id=owner_user_id,
#             sender=prospect_email,
#             since=sent_at,
#         )
#     except RuntimeError as exc:
#         logger.warning(
#             "reply_poller.mailbridge_call_failed",
#             schema=schema,
#             sequence_id=sequence_id,
#             owner_user_id=owner_user_id,
#             error=str(exc),
#         )
#         return False

#     if not replies:
#         return False

#     # Take the earliest reply.
#     replies_sorted = sorted(replies, key=lambda r: r.get("received_at") or "")
#     earliest = replies_sorted[0]

#     await _record_reply(schema, sequence_id, earliest)

#     logger.info(
#         "reply_poller.reply_recorded",
#         schema=schema,
#         sequence_id=sequence_id,
#         owner_user_id=owner_user_id,
#         from_address=earliest.get("from_address"),
#         subject=earliest.get("subject"),
#         received_at=earliest.get("received_at"),
#     )
#     return True


# async def _record_reply(
#     schema: str,
#     sequence_id: str,
#     reply_event: dict[str, Any],
# ) -> None:
#     """Apply a 'replied' tracking event in an isolated tenant session."""
#     from app.features.mailbridge.service import MailBridgeService

#     received_at_str: str | None = reply_event.get("received_at")
#     received_at: datetime | None = None
#     if received_at_str:
#         try:
#             received_at = datetime.fromisoformat(received_at_str)
#             if received_at.tzinfo is None:
#                 received_at = received_at.replace(tzinfo=timezone.utc)
#         except ValueError:
#             pass

#     subject = reply_event.get("subject") or "(no subject)"
#     message_id = reply_event.get("message_id") or ""
#     # Use the real email body returned by MailBridge (after the body_text fix).
#     # Fall back to the subject line if body is empty (e.g. old reply_events
#     # rows that were recorded before the body_text column was added).
#     body = (
#         reply_event.get("body")
#         or reply_event.get("body_text")
#         or f"[Reply received — subject: {subject}]"
#     )

#     event = MailBridgeTrackingEvent(
#         event="replied",
#         messageId=message_id,
#         sequenceId=sequence_id,
#         timestamp=received_at or datetime.now(timezone.utc),
#         recipient=None,
#         reason=None,
#         payload={"body": body},
#     )

#     svc = MailBridgeService()
#     async with AsyncSessionLocal() as db:
#         await db.execute(text(f'SET search_path TO "{schema}", public'))
#         await svc.apply_tracking_event(db, event)


# async def _resolve_prospect_email(schema: str, prospect_id: str) -> str:
#     """Decrypt and return the prospect's email address."""
#     try:
#         async with AsyncSessionLocal() as db:
#             await db.execute(text(f'SET search_path TO "{schema}", public'))
#             result = await db.execute(
#                 select(Prospect).where(Prospect.id == prospect_id)
#             )
#             prospect = result.scalar_one_or_none()
#             if prospect is None:
#                 return ""
#             raw_email: str = getattr(prospect, "email", None) or ""
#             if not raw_email or getattr(prospect, "anonymized", False):
#                 return ""
#             try:
#                 from app.services.pii_service import PiiService
#                 return PiiService().decrypt_field(raw_email) or ""
#             except Exception:  # noqa: BLE001
#                 return raw_email
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "reply_poller.prospect_email_failed",
#             schema=schema,
#             prospect_id=prospect_id,
#             error=str(exc),
#         )
#         return ""


# async def _get_mb_client_for_schema(schema: str) -> Any | None:
#     """Load the active MailBridgeConfig and build a client."""
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


# async def _reply_poll_wrapper() -> None:
#     """APScheduler entry point."""
#     try:
#         await run_reply_poll_all_tenants()
#     except Exception as exc:  # noqa: BLE001
#         logger.error("reply_poller.unhandled_error", error=str(exc), exc_info=True)


# def register_reply_poll_job(scheduler: Any) -> None:
#     """Register the reply-poll job on an existing AsyncIOScheduler instance."""
#     settings = get_settings()

#     poll_enabled: bool = getattr(settings, "MAILBRIDGE_REPLY_POLL_ENABLED", True)
#     if not poll_enabled:
#         logger.info("reply_poller.disabled", reason="MAILBRIDGE_REPLY_POLL_ENABLED=false")
#         return

#     if not settings.MAILBRIDGE_DEFAULT_URL:
#         logger.info(
#             "reply_poller.skipped",
#             reason="MAILBRIDGE_DEFAULT_URL not set — configure MailBridge to enable reply polling",
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

# """
# app/features/mailbridge/reply_poller.py
# ========================================
# Background scheduler task: poll MailBridge for replies to sent sequences
# and surface them in Outrena's Reply Inbox.

# DESIGN (final):
#   The Sequence table is the authoritative source of truth. Every sent
#   sequence has:
#     - owner_user_id: Keycloak UUID of who sent it (= external_user_id in MailBridge)
#     - prospectId:    who the email was sent to
#     - sentAt:        when it was sent (used as `since` filter)

#   For each sent-but-unreplied sequence, the poller calls:
#     GET /auth/connect/replies
#       ?external_user_id=<seq.owner_user_id>
#       &sender=<prospect.email>
#       &since=<seq.sentAt>

#   If MailBridge returns replies, the earliest one is recorded via
#   apply_tracking_event(), which stamps Sequence.repliedAt, creates a
#   ReplyDraft, and fires AI categorization.

#   No guessing about which users are connected. No querying MailBridgeConfig
#   or UserSenderIdentity. The sequence row tells us exactly who sent the
#   email and who to ask MailBridge about.

#   Edge case — owner_user_id is "system" (auto-generated sequences before
#   the campaigns/service.py fix): we skip these sequences since "system"
#   is not a real MailBridge external_user_id.
# """
# from __future__ import annotations

# from datetime import datetime, timezone
# from typing import Any

# import structlog
# from sqlalchemy import select, text

# from app.core.config import get_settings
# from app.core.database import AsyncSessionLocal, engine
# from app.models.campaign_models import Sequence
# from app.models.enums import EmailStatus
# from app.models.prospect_models import Prospect
# from app.schemas.mailbridge import MailBridgeTrackingEvent

# logger = structlog.get_logger(__name__)


# async def run_reply_poll_all_tenants() -> dict[str, Any]:
#     """Top-level entry point called by the APScheduler job."""
#     summary: dict[str, Any] = {
#         "tenants_polled": 0,
#         "sequences_checked": 0,
#         "replies_found": 0,
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
#     """Poll one tenant schema for reply events.

#     Loads all sent-but-unreplied sequences, then for each one asks
#     MailBridge: did owner_user_id's mailbox receive a reply from
#     prospect.email since sentAt?
#     """
#     result: dict[str, Any] = {
#         "sequences_checked": 0,
#         "replies_found": 0,
#         "errors": 0,
#     }

#     # Load all sent-but-unreplied sequences that have a real sender.
#     # owner_user_id IS the MailBridge external_user_id — it's the Keycloak
#     # UUID passed to POST /connect/{provider}/start during the connect flow.
#     sequences_to_check: list[dict[str, Any]] = []
#     try:
#         async with AsyncSessionLocal() as db:
#             await db.execute(text(f'SET search_path TO "{schema}", public'))
#             rows = (await db.execute(
#                 select(Sequence)
#                 .where(Sequence.status == EmailStatus.Sent)
#                 .where(Sequence.repliedAt.is_(None))
#                 .where(Sequence.sentAt.is_not(None))
#                 .where(Sequence.owner_user_id.is_not(None))
#                 .where(Sequence.owner_user_id != "system")
#             )).scalars().all()
#             for seq in rows:
#                 sequences_to_check.append({
#                     "id": seq.id,
#                     "owner_user_id": seq.owner_user_id,
#                     "sentAt": seq.sentAt,
#                     "prospectId": seq.prospectId,
#                 })
#     except Exception as exc:  # noqa: BLE001
#         logger.error("reply_poller.tenant_load_failed", schema=schema, error=str(exc))
#         result["errors"] += 1
#         return result

#     result["sequences_checked"] = len(sequences_to_check)
#     if not sequences_to_check:
#         return result

#     mb_client = await _get_mb_client_for_schema(schema)
#     if mb_client is None:
#         logger.debug("reply_poller.no_mailbridge_config", schema=schema)
#         return result

#     for seq_data in sequences_to_check:
#         try:
#             found = await _check_sequence(schema, seq_data, mb_client)
#             if found:
#                 result["replies_found"] += 1
#         except Exception as exc:  # noqa: BLE001
#             result["errors"] += 1
#             logger.warning(
#                 "reply_poller.sequence_check_failed",
#                 schema=schema,
#                 sequence_id=seq_data["id"],
#                 error=str(exc),
#             )

#     return result


# async def _check_sequence(
#     schema: str,
#     seq_data: dict[str, Any],
#     mb_client: Any,
# ) -> bool:
#     """Check one sequence for a reply in MailBridge.

#     Calls GET /auth/connect/replies with:
#       external_user_id = seq.owner_user_id  (who sent the sequence)
#       sender           = prospect.email     (who we expect a reply from)
#       since            = seq.sentAt         (ignore pre-existing inbox mail)
#     """
#     sequence_id: str = seq_data["id"]
#     owner_user_id: str = seq_data["owner_user_id"]
#     sent_at: datetime = seq_data["sentAt"]
#     prospect_id: str = seq_data["prospectId"]

#     prospect_email = await _resolve_prospect_email(schema, prospect_id)
#     if not prospect_email:
#         return False

#     if sent_at.tzinfo is None:
#         sent_at = sent_at.replace(tzinfo=timezone.utc)

#     try:
#         replies = await mb_client.get_connect_replies(
#             external_user_id=owner_user_id,
#             sender=prospect_email,
#             since=sent_at,
#         )
#     except RuntimeError as exc:
#         logger.warning(
#             "reply_poller.mailbridge_call_failed",
#             schema=schema,
#             sequence_id=sequence_id,
#             owner_user_id=owner_user_id,
#             error=str(exc),
#         )
#         return False

#     if not replies:
#         return False

#     # Take the earliest reply.
#     replies_sorted = sorted(replies, key=lambda r: r.get("received_at") or "")
#     earliest = replies_sorted[0]

#     await _record_reply(schema, sequence_id, earliest)

#     logger.info(
#         "reply_poller.reply_recorded",
#         schema=schema,
#         sequence_id=sequence_id,
#         owner_user_id=owner_user_id,
#         from_address=earliest.get("from_address"),
#         subject=earliest.get("subject"),
#         received_at=earliest.get("received_at"),
#     )
#     return True


# async def _record_reply(
#     schema: str,
#     sequence_id: str,
#     reply_event: dict[str, Any],
# ) -> None:
#     """Apply a 'replied' tracking event in an isolated tenant session."""
#     from app.features.mailbridge.service import MailBridgeService

#     received_at_str: str | None = reply_event.get("received_at")
#     received_at: datetime | None = None
#     if received_at_str:
#         try:
#             received_at = datetime.fromisoformat(received_at_str)
#             if received_at.tzinfo is None:
#                 received_at = received_at.replace(tzinfo=timezone.utc)
#         except ValueError:
#             pass

#     subject = reply_event.get("subject") or "(no subject)"
#     message_id = reply_event.get("message_id") or ""

#     event = MailBridgeTrackingEvent(
#         event="replied",
#         messageId=message_id,
#         sequenceId=sequence_id,
#         timestamp=received_at or datetime.now(timezone.utc),
#         recipient=None,
#         reason=None,
#         payload={"body": f"[Reply received — subject: {subject}]"},
#     )

#     svc = MailBridgeService()
#     async with AsyncSessionLocal() as db:
#         await db.execute(text(f'SET search_path TO "{schema}", public'))
#         await svc.apply_tracking_event(db, event)


# async def _resolve_prospect_email(schema: str, prospect_id: str) -> str:
#     """Decrypt and return the prospect's email address."""
#     try:
#         async with AsyncSessionLocal() as db:
#             await db.execute(text(f'SET search_path TO "{schema}", public'))
#             result = await db.execute(
#                 select(Prospect).where(Prospect.id == prospect_id)
#             )
#             prospect = result.scalar_one_or_none()
#             if prospect is None:
#                 return ""
#             raw_email: str = getattr(prospect, "email", None) or ""
#             if not raw_email or getattr(prospect, "anonymized", False):
#                 return ""
#             try:
#                 from app.services.pii_service import PiiService
#                 return PiiService().decrypt_field(raw_email) or ""
#             except Exception:  # noqa: BLE001
#                 return raw_email
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "reply_poller.prospect_email_failed",
#             schema=schema,
#             prospect_id=prospect_id,
#             error=str(exc),
#         )
#         return ""


# async def _get_mb_client_for_schema(schema: str) -> Any | None:
#     """Load the active MailBridgeConfig and build a client."""
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


# async def _reply_poll_wrapper() -> None:
#     """APScheduler entry point."""
#     try:
#         await run_reply_poll_all_tenants()
#     except Exception as exc:  # noqa: BLE001
#         logger.error("reply_poller.unhandled_error", error=str(exc), exc_info=True)


# def register_reply_poll_job(scheduler: Any) -> None:
#     """Register the reply-poll job on an existing AsyncIOScheduler instance."""
#     settings = get_settings()

#     poll_enabled: bool = getattr(settings, "MAILBRIDGE_REPLY_POLL_ENABLED", True)
#     if not poll_enabled:
#         logger.info("reply_poller.disabled", reason="MAILBRIDGE_REPLY_POLL_ENABLED=false")
#         return

#     if not settings.MAILBRIDGE_DEFAULT_URL:
#         logger.info(
#             "reply_poller.skipped",
#             reason="MAILBRIDGE_DEFAULT_URL not set — configure MailBridge to enable reply polling",
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
Background scheduler task: poll MailBridge for replies to sent sequences
and surface them in Outrena's Reply Inbox.

DESIGN (final):
  The Sequence table is the authoritative source of truth. Every sent
  sequence has:
    - owner_user_id: Keycloak UUID of who sent it (= external_user_id in MailBridge)
    - prospectId:    who the email was sent to
    - sentAt:        when it was sent (used as `since` filter)

  For each sent-but-unreplied sequence, the poller calls:
    GET /auth/connect/replies
      ?external_user_id=<seq.owner_user_id>
      &sender=<prospect.email>
      &since=<seq.sentAt>

  If MailBridge returns replies, the earliest one is recorded via
  apply_tracking_event(), which stamps Sequence.repliedAt, creates a
  ReplyDraft, and fires AI categorization.

  No guessing about which users are connected. No querying MailBridgeConfig
  or UserSenderIdentity. The sequence row tells us exactly who sent the
  email and who to ask MailBridge about.

  Edge case — owner_user_id is "system" (auto-generated sequences before
  the campaigns/service.py fix): we skip these sequences since "system"
  is not a real MailBridge external_user_id.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.models.campaign_models import Sequence
from app.models.enums import EmailStatus
from app.models.prospect_models import Prospect
from app.schemas.mailbridge import MailBridgeTrackingEvent

logger = structlog.get_logger(__name__)


async def run_reply_poll_all_tenants() -> dict[str, Any]:
    """Top-level entry point called by the APScheduler job."""
    summary: dict[str, Any] = {
        "tenants_polled": 0,
        "sequences_checked": 0,
        "replies_found": 0,
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
    """Poll one tenant schema for reply events.

    Loads all sent-but-unreplied sequences, then for each one asks
    MailBridge: did owner_user_id's mailbox receive a reply from
    prospect.email since sentAt?
    """
    result: dict[str, Any] = {
        "sequences_checked": 0,
        "replies_found": 0,
        "errors": 0,
    }

    # Load all sent-but-unreplied sequences.
    #
    # Poll identity resolution (migration 0018):
    #   sent_via_external_user_id — the exact external_user_id that was passed
    #     to MailBridge when the email was dispatched.  This is the identity
    #     whose inbox MailBridge recorded the reply against, so we MUST use it
    #     when calling GET /auth/connect/replies.  Present on all rows sent
    #     after migration 0018.
    #   owner_user_id — fallback for legacy rows sent before migration 0018,
    #     where sent_via_external_user_id is NULL.  This preserves the previous
    #     behaviour for old rows while new rows use the correct sender identity.
    sequences_to_check: list[dict[str, Any]] = []
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text(f'SET search_path TO "{schema}", public'))
            rows = (await db.execute(
                select(Sequence)
                .where(Sequence.status == EmailStatus.Sent)
                .where(Sequence.repliedAt.is_(None))
                .where(Sequence.sentAt.is_not(None))
                # Include sequences that have either a sent_via_external_user_id
                # (post-0018 rows) or a non-system owner_user_id (legacy rows).
                # We exclude pure 'system' rows that have no usable identity at all.
                .where(
                    (
                        Sequence.sent_via_external_user_id.is_not(None)
                    ) | (
                        (Sequence.owner_user_id.is_not(None)) &
                        (Sequence.owner_user_id != "system")
                    )
                )
            )).scalars().all()
            for seq in rows:
                # Prefer the stamp from send-time; fall back to creator identity.
                poll_identity = (
                    getattr(seq, "sent_via_external_user_id", None)
                    or seq.owner_user_id
                )
                sequences_to_check.append({
                    "id": seq.id,
                    "poll_identity": poll_identity,
                    "sentAt": seq.sentAt,
                    "prospectId": seq.prospectId,
                })
    except Exception as exc:  # noqa: BLE001
        logger.error("reply_poller.tenant_load_failed", schema=schema, error=str(exc))
        result["errors"] += 1
        return result

    result["sequences_checked"] = len(sequences_to_check)
    if not sequences_to_check:
        return result

    mb_client = await _get_mb_client_for_schema(schema)
    if mb_client is None:
        logger.debug("reply_poller.no_mailbridge_config", schema=schema)
        return result

    for seq_data in sequences_to_check:
        try:
            found = await _check_sequence(schema, seq_data, mb_client)
            if found:
                result["replies_found"] += 1
        except Exception as exc:  # noqa: BLE001
            result["errors"] += 1
            logger.warning(
                "reply_poller.sequence_check_failed",
                schema=schema,
                sequence_id=seq_data["id"],
                error=str(exc),
            )

    return result


async def _check_sequence(
    schema: str,
    seq_data: dict[str, Any],
    mb_client: Any,
) -> bool:
    """Check one sequence for a reply in MailBridge.

    Calls GET /auth/connect/replies with:
      external_user_id = seq_data["poll_identity"]
                         — sent_via_external_user_id when set (post-0018 rows,
                           i.e. the exact MailBridge identity used at send-time),
                           or owner_user_id for legacy rows.
      sender           = prospect.email  (who we expect a reply from)
      since            = seq.sentAt      (ignore pre-existing inbox mail)

    Using the actual send-time identity (not the campaign creator) ensures we
    poll the correct inbox in multi-user tenants where the person who clicked
    Send differs from the person who generated the sequences.
    """
    sequence_id: str = seq_data["id"]
    poll_identity: str = seq_data["poll_identity"]
    sent_at: datetime = seq_data["sentAt"]
    prospect_id: str = seq_data["prospectId"]

    prospect_email = await _resolve_prospect_email(schema, prospect_id)
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

    # Take the earliest reply.
    replies_sorted = sorted(replies, key=lambda r: r.get("received_at") or "")
    earliest = replies_sorted[0]

    await _record_reply(schema, sequence_id, earliest)

    logger.info(
        "reply_poller.reply_recorded",
        schema=schema,
        sequence_id=sequence_id,
        poll_identity=poll_identity,
        from_address=earliest.get("from_address"),
        subject=earliest.get("subject"),
        received_at=earliest.get("received_at"),
    )
    return True


async def _record_reply(
    schema: str,
    sequence_id: str,
    reply_event: dict[str, Any],
) -> None:
    """Apply a 'replied' tracking event in an isolated tenant session."""
    from app.features.mailbridge.service import MailBridgeService

    received_at_str: str | None = reply_event.get("received_at")
    received_at: datetime | None = None
    if received_at_str:
        try:
            received_at = datetime.fromisoformat(received_at_str)
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    subject = reply_event.get("subject") or "(no subject)"
    message_id = reply_event.get("message_id") or ""
    # Use the real email body returned by MailBridge (after the body_text fix).
    # Fall back to the subject line if body is empty (e.g. old reply_events
    # rows that were recorded before the body_text column was added).
    body = (
        reply_event.get("body")
        or reply_event.get("body_text")
        or f"[Reply received — subject: {subject}]"
    )

    event = MailBridgeTrackingEvent(
        event="replied",
        messageId=message_id,
        sequenceId=sequence_id,
        timestamp=received_at or datetime.now(timezone.utc),
        recipient=None,
        reason=None,
        payload={"body": body},
    )

    svc = MailBridgeService()
    async with AsyncSessionLocal() as db:
        await db.execute(text(f'SET search_path TO "{schema}", public'))
        await svc.apply_tracking_event(db, event)


async def _resolve_prospect_email(schema: str, prospect_id: str) -> str:
    """Decrypt and return the prospect's email address."""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text(f'SET search_path TO "{schema}", public'))
            result = await db.execute(
                select(Prospect).where(Prospect.id == prospect_id)
            )
            prospect = result.scalar_one_or_none()
            if prospect is None:
                return ""
            raw_email: str = getattr(prospect, "email", None) or ""
            if not raw_email or getattr(prospect, "anonymized", False):
                return ""
            try:
                from app.services.pii_service import PiiService
                return PiiService().decrypt_field(raw_email) or ""
            except Exception:  # noqa: BLE001
                return raw_email
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "reply_poller.prospect_email_failed",
            schema=schema,
            prospect_id=prospect_id,
            error=str(exc),
        )
        return ""


async def _get_mb_client_for_schema(schema: str) -> Any | None:
    """Load the active MailBridgeConfig and build a client."""
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


async def _reply_poll_wrapper() -> None:
    """APScheduler entry point."""
    try:
        await run_reply_poll_all_tenants()
    except Exception as exc:  # noqa: BLE001
        logger.error("reply_poller.unhandled_error", error=str(exc), exc_info=True)


def register_reply_poll_job(scheduler: Any) -> None:
    """Register the reply-poll job on an existing AsyncIOScheduler instance."""
    settings = get_settings()

    poll_enabled: bool = getattr(settings, "MAILBRIDGE_REPLY_POLL_ENABLED", True)
    if not poll_enabled:
        logger.info("reply_poller.disabled", reason="MAILBRIDGE_REPLY_POLL_ENABLED=false")
        return

    if not settings.MAILBRIDGE_DEFAULT_URL:
        logger.info(
            "reply_poller.skipped",
            reason="MAILBRIDGE_DEFAULT_URL not set — configure MailBridge to enable reply polling",
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