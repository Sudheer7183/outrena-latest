


# # from __future__ import annotations
 
# # import asyncio
# # import hashlib
# # import zoneinfo
# # from datetime import datetime, time, timedelta, timezone
# # from typing import Any
 
# # import httpx
# # import structlog
# # from apscheduler.schedulers.asyncio import AsyncIOScheduler
# # from sqlalchemy import select, text
# # from sqlalchemy.ext.asyncio import AsyncSession
 
# # from app.core.config import get_settings
# # from app.core.database import AsyncSessionLocal, engine
# # from app.models.campaign_models import Sequence
# # from app.models.config_models import MailBridgeConfig
# # from app.models.enums import EmailStatus, EnrichmentTier
# # from app.models.phase3_models import SchedulerRun, SchedulerStatus
# # from app.models.prospect_models import Prospect
# # from app.schemas.scheduler import ManualTickResponse
# # from app.features.mailbridge.service import MailBridgeService
# # from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
# # from app.features.mailbridge.reply_poller import register_reply_poll_job
# # from app.features.scheduler.query_service import write_skip_log, upsert_daily_sent
# # logger = structlog.get_logger(__name__)
 
# # # ── Module-global singleton scheduler ──────────────────────────────────────
# # _scheduler: AsyncIOScheduler | None = None
# # # register_reply_poll_job(_scheduler)
 
# # # def get_scheduler() -> AsyncIOScheduler:
# # #     """Return the AsyncIOScheduler singleton (migration §9.1 L1266-1278).
 
# # #     The scheduler is created lazily on first access and configured with
# # #     max_instances=1 + coalesce=True so missed ticks never pile up. The
# # #     interval job is registered here; start()/shutdown() are called from
# # #     the FastAPI lifespan in app.main.create_app().
# # #     """
# # #     global _scheduler
# # #     if _scheduler is None:
# # #         settings = get_settings()
# # #         _scheduler = AsyncIOScheduler()
# # #         _scheduler.add_job(
# # #             _async_tick_wrapper,
# # #             "interval",
# # #             seconds=settings.SCHEDULER_TICK_SECONDS,
# # #             id="outrena_tick",
# # #             max_instances=1,
# # #             coalesce=True,
# # #             replace_existing=True,
# # #         )
# # #         # Nightly cost-summary rollup — runs at 02:00 UTC every day.
# # #         # Materialises per-user × event_type × provider cost_summaries rows
# # #         # for the current month so the Usage dashboard reads from a fast
# # #         # rollup table rather than scanning raw usage_events.
# # #         _scheduler.add_job(
# # #             _async_cost_rollup_wrapper,
# # #             "cron",
# # #             hour=2,
# # #             minute=0,
# # #             id="outrena_cost_rollup",
# # #             max_instances=1,
# # #             coalesce=True,
# # #             replace_existing=True,
# # #         )
# # #                 # Reply-inbox poller — polls MailBridge for inbound replies.
# # #         # Only registers when MAILBRIDGE_DEFAULT_URL is configured.
# # #         from app.features.mailbridge.reply_poller import register_reply_poll_job
# # #         register_reply_poll_job(_scheduler)
# # #         logger.info(
# # #             "scheduler.registered",
# # #             tick_seconds=settings.SCHEDULER_TICK_SECONDS,
# # #             job_id="outrena_tick",
# # #         )
# # #     return _scheduler
 
# # def get_scheduler(
# #     *,
# #     email_tick_enabled: bool = True,
# #     reply_poller_enabled: bool = True,
# # ) -> AsyncIOScheduler:
# #     """Return the APScheduler singleton — email tick and reply poller
# #     are registered independently based on their respective flags."""
# #     global _scheduler
# #     if _scheduler is None:
# #         settings = get_settings()
# #         _scheduler = AsyncIOScheduler()

# #         if email_tick_enabled:
# #             _scheduler.add_job(
# #                 _async_tick_wrapper,
# #                 "interval",
# #                 seconds=settings.SCHEDULER_TICK_SECONDS,
# #                 id="outrena_tick",
# #                 max_instances=1,
# #                 coalesce=True,
# #                 replace_existing=True,
# #             )
# #             logger.info("scheduler.email_tick.registered",
# #                         tick_seconds=settings.SCHEDULER_TICK_SECONDS)
# #         else:
# #             logger.info("scheduler.email_tick.disabled")

# #         _scheduler.add_job(
# #             _async_cost_rollup_wrapper,
# #             "cron",
# #             hour=2,
# #             minute=0,
# #             id="outrena_cost_rollup",
# #             max_instances=1,
# #             coalesce=True,
# #             replace_existing=True,
# #         )

# #         if reply_poller_enabled:
# #             from app.features.mailbridge.reply_poller import register_reply_poll_job
# #             register_reply_poll_job(_scheduler)
# #             logger.info("scheduler.reply_poller.registered",
# #                         poll_seconds=settings.MAILBRIDGE_REPLY_POLL_SECONDS)
# #         else:
# #             logger.info("scheduler.reply_poller.disabled")

# #     return _scheduler
 
# # async def _async_tick_wrapper() -> None:
# #     """Top-level tick wrapper — catches + logs every exception so a single
# #     tenant's failure (or even a DB outage) never kills the scheduler."""
# #     try:
# #         summary = await run_tick_all_tenants()
# #         logger.info("scheduler.tick.complete", **summary)
# #     except Exception as exc:  # noqa: BLE001 — scheduler must never die
# #         logger.error("scheduler.tick.fatal", error=str(exc), exc_info=True)
 
 
# # async def _async_cost_rollup_wrapper() -> None:
# #     """Nightly job — materialise CostSummary rows for all active tenants.
 
# #     Iterates all ACTIVE tenants in public.tenants and calls
# #     UsageService().rebuild_cost_summaries() for the current month.
# #     Failures per-tenant are logged and swallowed so one bad schema
# #     never blocks all others.
# #     """
# #     from app.core.database import AsyncSessionLocal
# #     from app.features.usage.service import UsageService
# #     from datetime import date as _date
 
# #     period = _date.today().strftime("%Y-%m")  # e.g. "2026-07"
# #     total = 0
# #     errors = 0
# #     try:
# #         async with AsyncSessionLocal() as db:
# #             from sqlalchemy import text as _text
# #             try:
# #                 result = await db.execute(
# #                     _text("SELECT slug FROM public.tenants WHERE status = 'ACTIVE' AND deleted_at IS NULL")
# #                 )
# #                 slugs = [row[0] for row in result.all()]
# #             except Exception as exc:  # noqa: BLE001
# #                 if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
# #                     raise
# #                 logger.warning("scheduler.cost_rollup.no_tenants_table", error=str(exc))
# #                 slugs = []
# #         for slug in slugs:
# #             try:
# #                 svc = UsageService()
# #                 written = await svc.rebuild_cost_summaries(slug, period)
# #                 total += written
# #             except Exception as exc:  # noqa: BLE001
# #                 errors += 1
# #                 logger.warning(
# #                     "scheduler.cost_rollup.tenant_failed",
# #                     tenant=slug,
# #                     error=str(exc),
# #                 )
# #         logger.info(
# #             "scheduler.cost_rollup.complete",
# #             period=period,
# #             tenants=len(slugs),
# #             rows_written=total,
# #             errors=errors,
# #         )
 
# #         # ── FR-038: nightly warm-up week advancement per tenant ────────────
# #         advanced_total = 0
# #         for slug in slugs:
# #             try:
# #                 async with AsyncSessionLocal() as db:
# #                     from sqlalchemy import text as _text
 
# #                     await db.execute(
# #                         _text(f'SET search_path TO "tenant_{slug}", public')
# #                     )
# #                     advanced_total += await advance_domain_warmup(db)
# #                     await db.commit()
# #             except Exception as exc:  # noqa: BLE001
# #                 logger.warning(
# #                     "scheduler.warmup_advance.tenant_failed",
# #                     tenant=slug,
# #                     error=str(exc),
# #                 )
# #         if advanced_total:
# #             logger.info(
# #                 "scheduler.warmup_advance.complete", domains=advanced_total
# #             )
# #     except Exception as exc:  # noqa: BLE001
# #         logger.error("scheduler.cost_rollup.fatal", error=str(exc), exc_info=True)
 
 
# # # ── §9.2 Business-hours filter ─────────────────────────────────────────────
 
 
# # # 7-week ramp per Help Guide §Domains (Warming Schedule)
# # # Week 1=10, 2=30, 3=50, 4=100, 5=200, 6=350, 7=500
# # _WARMUP_RAMP: dict[int, int] = {1: 10, 2: 30, 3: 50, 4: 100, 5: 200, 6: 350, 7: 500}
# # WARMING_SCHEDULE = [10, 30, 50, 100, 200, 350, 500]  # exported for UI display
 
 
# # def _warmup_effective_cap(dom) -> int:
# #     """FR-038: effective daily cap for a (possibly warming) domain."""
# #     week = int(getattr(dom, "warmingWeek", 0) or 0)
# #     base = int(getattr(dom, "dailySendLimit", 0) or 0) or 10_000
# #     if 1 <= week <= 7:
# #         return min(base, _WARMUP_RAMP[week])
# #     return base
 
 
# # async def advance_domain_warmup(db) -> int:
# #     """FR-038: advance warmingWeek for domains warmed >= 7 days per week.
 
# #     Called by the nightly maintenance job. A domain whose updatedAt is more
# #     than 7 days old and whose warmingWeek is 1-4 moves to the next week;
# #     week 5 means warm-up complete (full dailySendLimit applies).
# #     Returns the number of domains advanced."""
# #     result = await db.execute(
# #         text(
# #             'UPDATE "Domain" SET '
# #             '  "warmingWeek" = "warmingWeek" + 1, '
# #             '  "updatedAt" = now() '
# #             'WHERE "warmingWeek" BETWEEN 1 AND 7 '
# #             "  AND \"updatedAt\" < now() - interval '7 days'"
# #         )
# #     )
# #     return result.rowcount or 0
 
 
# # def _is_business_hours(now: datetime, tz_name: str | None) -> bool:
# #     """Return True iff `now` falls inside recipient-local 9am-5pm, Mon-Fri.
 
# #     If tz_name is None, defaults to America/New_York (US Eastern) — the most
# #     common timezone for B2B cold outreach targets. If tz_name is unparseable,
# #     falls back to UTC. local is always assigned before use (no UnboundLocalError).
# #     """
# #     local = now  # always assigned — fallback if zoneinfo fails
# #     effective_tz = tz_name or "America/New_York"
# #     try:
# #         tz = zoneinfo.ZoneInfo(effective_tz)
# #         local = now.astimezone(tz)
# #     except Exception:  # noqa: BLE001 — unknown tz string, keep UTC fallback
# #         local = now
# #     if local.weekday() >= 5:  # Sat=5, Sun=6
# #         return False
# #     start, end = time(9, 0), time(17, 0)
# #     return start <= local.time() <= end
 
 
# # # ── §9.3 PARTIAL throttle (deterministic hash) ─────────────────────────────
 
 
# # def _partial_throttle_passes(prospect_id: str, tick_bucket: int) -> bool:
# #     """Return True iff this PARTIAL-enrichment prospect should be sent this tick.
 
# #     Per migration §9.3 L1309-1316: hash(prospect_id + tick_bucket) % 100 must
# #     be < SCHEDULER_PARTIAL_PER_TICK_CAP (default 5). The hash is deterministic
# #     so retries within the same tick window select the same prospects.
# #     """
# #     settings = get_settings()
# #     cap = settings.SCHEDULER_PARTIAL_PER_TICK_CAP
# #     hash_input = f"{prospect_id}:{tick_bucket}"
# #     bucket = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16) % 100
# #     return bucket < cap
 
 
# # # ── §9.5 MailBridge dispatch ───────────────────────────────────────────────
 
 
# # async def _resolve_mailbridge_config(
# #     db: AsyncSession, user_id: str | None
# # ) -> MailBridgeConfig | None:
# #     """Resolve the MailBridgeConfig to use for a given user.
 
# #     Per SAAS2-USER-BE §G:
# #       1. If user_id is provided, look for an active MailBridgeConfig owned by
# #          that user (MailBridgeConfig.owner_user_id == user_id). This requires
# #          BE-A to have added the owner_user_id column to MailBridgeConfig.
# #       2. Fall back to a tenant-level config (owner_user_id IS NULL or column
# #          does not exist yet) — preserves the pre-user-behaviour.
# #       3. Return None if no active config exists.
 
# #     The lookup is defensive: if MailBridgeConfig does not yet expose
# #     owner_user_id (BE-A migration 0004 not yet applied), the per-user filter
# #     is skipped and the tenant-level fallback is used.
# #     """
# #     # Per-user lookup — only if the column exists on the model.
# #     has_owner_col = hasattr(MailBridgeConfig, "owner_user_id")
# #     if user_id and has_owner_col:
# #         try:
# #             result = await db.execute(
# #                 select(MailBridgeConfig)
# #                 .where(MailBridgeConfig.isActive.is_(True))
# #                 .where(getattr(MailBridgeConfig, "owner_user_id") == user_id)
# #                 .limit(1)
# #             )
# #             cfg = result.scalar_one_or_none()
# #             if cfg is not None:
# #                 return cfg
# #         except Exception as exc:  # noqa: BLE001 — fall back to tenant-level
# #             logger.warning(
# #                 "scheduler.mailbridge.per_user_lookup_failed",
# #                 user_id=user_id, error=str(exc),
# #             )
 
# #     # Tenant-level fallback.
# #     result = await db.execute(
# #         select(MailBridgeConfig)
# #         .where(MailBridgeConfig.isActive.is_(True))
# #         .limit(1)
# #     )
# #     return result.scalar_one_or_none()

# # def _is_html_body(body: str | None) -> bool:
# #     """True when body was authored in the Tiptap RTE (already HTML).

# #     The RTE always opens content with a block-level HTML tag. We also require
# #     at least one closing tag to avoid false-positives on plain text that
# #     happens to start with '<'.
# #     """
# #     if not body:
# #         return False
# #     s = body.lstrip()
# #     return s.startswith("<") and any(
# #         marker in body
# #         for marker in (
# #             "</p>", "</h", "<br", "</ul>", "</ol>",
# #             "</li>", "</strong>", "</em>",
# #         )
# #     )


# # def _strip_html_text(html: str) -> str:
# #     """Strip HTML tags and collapse whitespace → plain-text fallback."""
# #     import re as _re
# #     text = _re.sub(r"<[^>]+>", " ", html)
# #     return _re.sub(r"\s+", " ", text).strip() 
 
# # async def _send_via_mailbridge(
# #     db: AsyncSession,
# #     config: MailBridgeConfig | None,
# #     sequence: Sequence,
# #     user_id: str | None = None,
# # ) -> str:
# #     """Send one sequence via MailBridge and return the messageId.
 
# #     Per migration §9.5 L1339-1353. Uses httpx.AsyncClient with a 30s timeout.
# #     The prospect is loaded from the same session to resolve the recipient
# #     email + timezone. On HTTP 4xx/5xx or any network error, raises
# #     RuntimeError so the caller can mark the sequence as skipped.
 
# #     Stub-safe: if no `config` is supplied (dev/CI), returns a deterministic
# #     stub messageId so tests can run without a MailBridge instance.
# #     """
# #     # Resolve prospect + recipient email
# #     prospect_result = await db.execute(
# #         select(Prospect).where(Prospect.id == sequence.prospectId)
# #     )
# #     prospect = prospect_result.scalar_one_or_none()
# #     if prospect is None or not prospect.email:
# #         raise RuntimeError(
# #             f"Prospect {sequence.prospectId} missing or has no email"
# #         )
 
# #     # Wiring audit (Task 2-e): the Prospect.email column is encrypted at rest
# #     # when ENCRYPTION_KEY is set (production). Previously this helper passed
# #     # the raw encrypted blob to MailBridge — which then attempted to deliver
# #     # to a Fernet-token-looking address and bounced every send. Decrypt via
# #     # PiiService before building the payload (mirrors SequenceService.send_email
# #     # + ReplyDraftService.auto_reply). Best-effort: fall back to the stored
# #     # value when decryption fails (legacy plaintext / dev mode without key).
# #     raw_email = prospect.email
# #     if not getattr(prospect, "anonymized", False):
# #         try:
# #             from app.services.pii_service import PiiService
 
# #             recipient_email = PiiService().decrypt_field(raw_email) or raw_email
# #         except Exception:  # noqa: BLE001 — best-effort
# #             recipient_email = raw_email
# #     else:
# #         recipient_email = raw_email
# #     if not recipient_email:
# #         raise RuntimeError(
# #             f"Prospect {sequence.prospectId} email is empty after decrypt"
# #         )
 
# #     settings = get_settings()
 
# #     # ── FR-039: DNS verification gate ────────────────────────────────────
# #     # If the sending config is bound to a Domain whose SPF/DKIM/DMARC
# #     # verification is failing, refuse the send and name the failing record.
# #     # Domains that have never been checked (lastChecked IS NULL) are allowed
# #     # through — blocking on "not yet verified" would deadlock fresh tenants.
# #     if config is not None and getattr(config, "domainId", None):
# #         from app.models.config_models import Domain as _Domain
 
# #         dom = (
# #             await db.execute(select(_Domain).where(_Domain.id == config.domainId))
# #         ).scalar_one_or_none()
# #         if dom is not None and dom.lastChecked is not None:
# #             failing = [
# #                 name
# #                 for name, ok in (
# #                     ("SPF", dom.spfStatus),
# #                     ("DKIM", dom.dkimStatus),
# #                     ("DMARC", dom.dmarcStatus),
# #                 )
# #                 if not ok
# #             ]
# #             if failing:
# #                 raise RuntimeError(
# #                     f"DNS verification failing for domain '{dom.domainName}': "
# #                     f"{', '.join(failing)}. Fix the DNS records and re-verify "
# #                     "before sending (FR-039)."
# #                 )
 
# #         # ── Pre-flight warmup gate (Help Guide §Domains) ─────────────────
# #         # The domain must have completed at least 2 weeks of warmup before
# #         # any sequence email is dispatched. This mirrors the Sequences
# #         # Pre-Flight Activation Gate documented in the guide.
# #         if dom is not None:
# #             week = int(getattr(dom, "warmingWeek", 0) or 0)
# #             if 1 <= week < 2:
# #                 raise RuntimeError(
# #                     f"Domain '{dom.domainName}' has only completed "
# #                     f"{week} week(s) of warm-up. At least 2 weeks are "
# #                     "required before sending. Use the Auto-Warm button on "
# #                     "the Domains page to advance the schedule, or wait for "
# #                     "the nightly auto-advance."
# #                 )
 
# #         # ── FR-038: warm-up escalating daily cap ────────────────────────
# #         # While a domain is warming (warmingWeek 1-4), the effective daily
# #         # send cap ramps: week1=10, week2=25, week3=50, week4=100, then the
# #         # domain's own dailySendLimit applies. Week advancement is automated
# #         # by the nightly maintenance job (advance_domain_warmup below).
# #         if dom is not None:
# #             effective_cap = _warmup_effective_cap(dom)
# #             sent_today = (
# #                 await db.execute(
# #                     text(
# #                         'SELECT COUNT(*) FROM "Sequence" s '
# #                         'JOIN "Campaign" c ON c.id = s."campaignId" '
# #                         "WHERE c.\"domainId\" = :dom_id "
# #                         "  AND s.\"sentAt\" >= date_trunc('day', now())"
# #                     ),
# #                     {"dom_id": dom.id},
# #                 )
# #             ).scalar() or 0
# #             if int(sent_today) >= effective_cap:
# #                 raise RuntimeError(
# #                     f"Warm-up daily cap reached for domain "
# #                     f"'{dom.domainName}' ({sent_today}/{effective_cap}, "
# #                     f"week {dom.warmingWeek}). Deferring to tomorrow "
# #                     "(FR-038)."
# #                 )
 
# #     # Dev/CI stub: no config + no default URL → deterministic fake id.
# #     if config is None and not settings.MAILBRIDGE_DEFAULT_URL:
# #         msg_id = f"stub-{sequence.id}@outrena.local"
# #         # Best-effort: record usage_event(email_send) so even dev-mode stub
# #         # sends show up in per-tenant cost roll-ups (mirrors MailBridgeService.send).
# #         await _record_usage_send_safe(db, sequence)
# #         return msg_id
 
# #     base_url = (config.baseUrl if config else "") or settings.MAILBRIDGE_DEFAULT_URL
 
# #     # Build MailBridge-compatible body with CAN-SPAM footer.
# #     # RTE UPGRADE: body may be HTML from Tiptap; detect and route accordingly.
# #     body_text = sequence.bodyCopy or ""
# #     is_html = _is_html_body(body_text)

# #     # ── CAN-SPAM / NFR-19: footer enforcement ─────────────────────────────
# #     # Every commercial email must contain: physical address + unsubscribe URL.
# #     # If the sequence body lacks them, we append a minimal compliant footer.
# #     # HTML bodies get an HTML footer; plain-text bodies get the existing footer.
# #     # Best-effort: silently skip if we can't compute tenant slug.
# #     needs_footer = (
# #         "unsubscribe" not in body_text.lower()
# #         or "physical" not in body_text.lower()
# #         and "address" not in body_text.lower()
# #     )
# #     if needs_footer:
# #         try:
# #             from app.utils.tenant_context import resolve_tenant_slug as _rts
# #             from app.core.config import get_settings as _gs
# #             _tenant_slug = await _rts(db)
# #             _prospect_token = getattr(prospect, "unsubscribeToken", None) or ""
# #             _base = _gs().BASE_DOMAIN
# #             _unsub_url = (
# #                 f"https://{_base}/api/v1/public/unsubscribe"
# #                 f"?token={_prospect_token}&tenant_slug={_tenant_slug}"
# #                 if _prospect_token and _tenant_slug
# #                 else ""
# #             )

# #             if is_html:
# #                 # HTML footer — inline styles for maximum email-client compat.
# #                 _unsub_link = (
# #                     f' <a href="{_unsub_url}" '
# #                     'style="color:#6b7280;text-decoration:underline">Unsubscribe</a>'
# #                     if _unsub_url
# #                     else ""
# #                 )
# #                 _html_footer = (
# #                     '<hr style="border:0;border-top:1px solid #e5e7eb;margin:24px 0">'
# #                     '<p style="color:#6b7280;font-size:11px;line-height:1.5;margin:0">'
# #                     f"This email was sent by an authorised OUTRENA user.{_unsub_link}"
# #                     "</p>"
# #                 )
# #                 body_text = body_text + _html_footer
# #             else:
# #                 # Plain-text footer (unchanged from original behaviour).
# #                 _footer_lines = [
# #                     "",
# #                     "---",
# #                     "This email was sent by an authorised OUTRENA user.",
# #                 ]
# #                 if _unsub_url:
# #                     _footer_lines.append(f"Unsubscribe: {_unsub_url}")
# #                 body_text = body_text + "\n".join(_footer_lines)

# #         except Exception:  # noqa: BLE001 — footer is best-effort, never block send
# #             pass

# #     # Build MailBridge-compatible payload (Phase 3+ /outbound/send).
# #     # body_html: rich HTML for Gmail / Outlook / Apple Mail.
# #     # body_text: plain-text fallback for non-HTML email clients.
# #     if is_html:
# #         body_html_final = body_text           # already HTML with HTML footer
# #         body_text_final = _strip_html_text(body_text)   # stripped for fallback
# #     else:
# #         body_html_final = body_text           # MailBridge/Gmail handles plain text display
# #         body_text_final = body_text           # same plain text for fallback

# #     payload = {
# #         "to": [recipient_email],
# #         "subject": sequence.subjectLine or "",
# #         "body_html": body_html_final,
# #         "body_text": body_text_final,
# #     }
# #     # Identity propagation: tell MailBridge which connected mailbox to send from.
# #     #
# #     # Priority (mirrors MailBridgeService.send fix):
# #     #   1. config.mailbridge_external_user_id — ONLY when the config is explicitly
# #     #      owned by the sending user (config.owner_user_id == user_id), i.e. this
# #     #      is the user's own per-user config with a static identity override.
# #     #   2. user_id — the Keycloak UUID of the person who clicked Send.  This is
# #     #      the exact value MailBridge recorded during POST /connect/{provider}/start,
# #     #      so it routes through *that* user's connected mailbox — not the campaign
# #     #      creator's.
# #     #
# #     # We record the resolved value as `sent_via_external_user_id` on the Sequence
# #     # row so the reply-poller knows exactly which MailBridge identity to poll.
# #     config_owner = getattr(config, "owner_user_id", None) if config else None
# #     config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
# #     ext_user_id = (
# #         config_ext_id
# #         if (config_owner and config_owner == user_id and config_ext_id)
# #         else user_id
# #     )
# #     if ext_user_id:
# #         payload["external_user_id"] = ext_user_id
 
# #     # Build auth headers. MailBridge tenancy mode requires a Bearer
# #     # API key (mb_live_...) from POST /platform/register.
# #     api_key = (
# #         getattr(config, "mailbridge_api_key", None) if config else None
# #     ) or settings.MAILBRIDGE_API_KEY
# #     headers: dict[str, str] = {"Content-Type": "application/json"}
# #     if api_key:
# #         headers["Authorization"] = f"Bearer {api_key}"
 
# #     timeout_s = float(settings.MAILBRIDGE_TIMEOUT_SECONDS)
# #     async with httpx.AsyncClient(timeout=timeout_s) as client:
# #         resp = await client.post(
# #             f"{base_url.rstrip('/')}/outbound/send",
# #             json=payload,
# #             headers=headers,
# #         )
# #         if resp.status_code >= 400:
# #             raise RuntimeError(
# #                 f"MailBridge returned HTTP {resp.status_code}: {resp.text[:200]}"
# #             )
# #         data = resp.json()
# #         # MailBridge returns snake_case "message_id"; fall back to camelCase
# #         # for backward compatibility with older/stub MailBridge instances.
# #         msg_id = data.get("message_id") or data.get("messageId", "")
# #         if not msg_id:
# #             raise RuntimeError("MailBridge response missing message_id")
 
# #     # Stamp who actually sent this and which MailBridge identity was used.
# #     # These are the values the reply-poller relies on — see reply_poller.py.
# #     if user_id:
# #         sequence.sent_by_user_id = user_id
# #     if ext_user_id:
# #         sequence.sent_via_external_user_id = ext_user_id
 
# #     # Best-effort: record usage_event(email_send) for per-tenant cost roll-ups.
# #     # (Mirrors MailBridgeService.send._record_usage_send so the scheduler-tick
# #     # path doesn't silently bypass cost tracking.)
# #     await _record_usage_send_safe(db, sequence)
# #     return msg_id
 
 
# # async def _record_usage_send_safe(db: AsyncSession, sequence: Sequence) -> None:
# #     """Fire-and-forget: record one usage_event(email_send) row.
 
# #     Wiring audit (Task 2-e): scheduler_service._send_via_mailbridge
# #     previously bypassed MailBridgeService.send (it makes its own httpx call
# #     per migration §9.5), so the per-tenant cost roll-up never saw
# #     scheduler-tick sends. This helper delegates to the same
# #     UsageService.record_email_send path used by MailBridgeService.send,
# #     deriving the tenant slug from the session's search_path. Best-effort —
# #     failures are logged + swallowed so a usage write never blocks the send.
# #     """
# #     try:
# #         from app.utils.tenant_context import resolve_tenant_slug
# #         tenant = await resolve_tenant_slug(db)
# #         if not tenant:
# #             return
# #         from app.features.usage.service import UsageService
# #         await UsageService().record_email_send(
# #             tenant=tenant,
# #             user_id=getattr(sequence, "owner_user_id", None) or "system",
# #             metadata={"source": "scheduler.run_tick", "sequence_id": sequence.id},
# #         )
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning(
# #             "scheduler.send.usage_record_failed",
# #             sequence_id=getattr(sequence, "id", None),
# #             error=str(exc),
# #         )
 
 
# # # ── §9.6 Single-tenant + multi-tenant ticks ────────────────────────────────
 
 
# # async def run_tick(schema_name: str) -> dict[str, Any]:
# #     """Run a single scheduler tick against one tenant schema.
 
# #     Per migration §9.4-9.6 + §10 Phase 5 L1502-1523. Steps:
# #       1. SET search_path TO "{schema}", public
# #       2. SELECT Sequences WHERE status=Scheduled AND touchNumber<=6
# #       3. For each candidate:
# #          a. Load prospect; skip if suppressed or no email.
# #          b. Business-hours filter (§9.2) — skip if outside 9am-5pm local.
# #          c. PARTIAL throttle (§9.3) — skip if hash falls outside this tick's cap.
# #          d. Resolve MailBridgeConfig (first active row).
# #          e. Call _send_via_mailbridge → on success, set status=Sent + sentAt
# #             + mailBridgeMessageId. On failure, log + count as skipped.
# #       4. Update SchedulerStatus row (id=1) with new counters + nextTickAt.
# #       5. Commit + return summary dict.
# #     """
# #     settings = get_settings()
# #     started = datetime.now(timezone.utc)
# #     tick_bucket = int(started.timestamp()) // settings.SCHEDULER_TICK_SECONDS
 
# #     summary: dict[str, Any] = {
# #         "schema": schema_name,
# #         "candidates": 0,
# #         "sent": 0,
# #         "skipped": 0,
# #         "started_at": started.isoformat(),
# #     }
 
# #     async with AsyncSessionLocal() as session:
# #         await session.execute(text(f'SET search_path TO "{schema_name}", public'))
 
# #         # ── Step 1: load SchedulerStatus row (create if absent) ──────────
# #         # FIX: wrap in try/except — SchedulerStatus table may not exist in
# #         # partially-provisioned tenant schemas (migration 0002 not yet run).
# #         # In that case skip the status tracking but still attempt sends.
# #         status_row = None
# #         try:
# #             status_result = await session.execute(
# #                 select(SchedulerStatus).where(SchedulerStatus.id == 1)
# #             )
# #             status_row = status_result.scalar_one_or_none()
# #             if status_row is None:
# #                 status_row = SchedulerStatus(id=1, isRunning=False)
# #                 session.add(status_row)
# #                 await session.flush()
# #             status_row.isRunning = True
# #             await session.commit()
# #         except Exception as _ss_exc:
# #             err_str = str(_ss_exc)
# #             if "does not exist" in err_str or "UndefinedTable" in err_str:
# #                 await session.rollback()
# #                 logger.warning(
# #                     "scheduler.tick.scheduler_status_missing",
# #                     schema=schema_name,
# #                     hint="Run alembic upgrade head to create SchedulerStatus table",
# #                 )
# #             else:
# #                 raise
 
# #         sent = 0
# #         skipped = 0
# #         try:
# #             # ── Step 2: load Scheduled sequences with touchNumber<=6 ─────
# #             # Guard against UndefinedTableError on a fresh tenant schema
# #             # (tables may not exist yet) or InFailedSQLTransactionError
# #             # if a prior query in this session aborted the transaction.
# #             # Roll back and skip cleanly rather than poisoning the session.
# #             try:
# #                 seq_result = await session.execute(
# #                     select(Sequence)
# #                     .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
# #                     .where(Sequence.touchNumber <= 6)
# #                     .order_by(Sequence.createdAt.asc())
# #                     .limit(500)
# #                 )
# #                 sequences = list(seq_result.scalars().all())
# #             except Exception as table_exc:
# #                 err_str = str(table_exc)
# #                 if "UndefinedTableError" in err_str or "InFailedSQLTransaction" in err_str or "does not exist" in err_str:
# #                     import structlog as _sl
# #                     _sl.get_logger(__name__).warning(
# #                         "scheduler.tick.schema_not_ready",
# #                         schema=schema_name,
# #                         error=err_str[:200],
# #                     )
# #                     await session.rollback()
# #                     summary["skipped"] = 0
# #                     summary["sent"] = 0
# #                     return summary
# #                 raise
# #             sequences = list(sequences) if not isinstance(sequences, list) else sequences
# #             summary["candidates"] = len(sequences)
 
# #             # Pre-load first active MailBridgeConfig for this schema (kept as
# #             # a tenant-level fallback for sequences without an owner_user_id).
# #             cfg_result = await session.execute(
# #                 select(MailBridgeConfig)
# #                 .where(MailBridgeConfig.isActive.is_(True))
# #                 .limit(1)
# #             )
# #             tenant_default_config = cfg_result.scalar_one_or_none()
 
# #             quota_service = UserEmailQuotaService()
 
# #             for seq in sequences:
# #                 try:
# #                     # ── Load prospect once per sequence (cheap with session cache) ──
# #                     prospect_result = await session.execute(
# #                         select(Prospect).where(Prospect.id == seq.prospectId)
# #                     )
# #                     prospect = prospect_result.scalar_one_or_none()
 
# #                     # Skip suppressed / no-email prospects
# #                     # Layer 1: Prospect-level suppression flag
# #                     if prospect is None or not prospect.email:
# #                         skipped += 1
# #                         await write_skip_log(
# #                             session,
# #                             run_id=None,
# #                             sequence_id=seq.id,
# #                             campaign_id=getattr(seq, "campaignId", None),
# #                             prospect_id=seq.prospectId,
# #                             skip_reason="no_email",
# #                             detail="Prospect not found or has no email address",
# #                         )
# #                         continue
# #                     if prospect.suppressed:
# #                         skipped += 1
# #                         await write_skip_log(
# #                             session,
# #                             run_id=None,
# #                             sequence_id=seq.id,
# #                             campaign_id=getattr(seq, "campaignId", None),
# #                             prospect_id=seq.prospectId,
# #                             skip_reason="suppressed",
# #                             detail="Prospect suppression flag is set",
# #                         )
# #                         continue

# #                     # Layer 2: Email-level suppression — catches duplicate Prospect
# #                     # rows and future imports of the same address.
# #                     _sched_email_lower = (prospect.email or "").strip().lower()
# #                     if _sched_email_lower:
# #                         try:
# #                             from sqlalchemy import text as _sched_t
# #                             _sched_es = await session.execute(
# #                                 _sched_t(
# #                                     'SELECT 1 FROM "EmailSuppression" '
# #                                     'WHERE email = :email LIMIT 1'
# #                                 ),
# #                                 {"email": _sched_email_lower},
# #                             )
# #                             if _sched_es.fetchone() is not None:
# #                                 skipped += 1
# #                                 await write_skip_log(
# #                                     session,
# #                                     run_id=None,
# #                                     sequence_id=seq.id,
# #                                     campaign_id=getattr(seq, "campaignId", None),
# #                                     prospect_id=seq.prospectId,
# #                                     skip_reason="suppressed",
# #                                     detail=f"Email {_sched_email_lower} is on suppression list",
# #                                 )
# #                                 continue
# #                         except Exception:  # noqa: BLE001
# #                             # EmailSuppression table may not exist yet — fail open.
# #                             pass

# #                     # ── Step 3a: business-hours filter (§9.2) ─────────────
# #                     if not _is_business_hours(started, prospect.timezone):
# #                         skipped += 1
# #                         await write_skip_log(
# #                             session,
# #                             run_id=None,
# #                             sequence_id=seq.id,
# #                             campaign_id=getattr(seq, "campaignId", None),
# #                             prospect_id=seq.prospectId,
# #                             skip_reason="business_hours",
# #                             detail=f"Outside 9am-5pm in timezone {prospect.timezone or 'UTC'}",
# #                         )
# #                         continue

# #                     # ── Step 3b: PARTIAL throttle (§9.3) ──────────────────
# #                     if (
# #                         prospect.enrichmentTier == EnrichmentTier.PARTIAL
# #                         and not _partial_throttle_passes(prospect.id, tick_bucket)
# #                     ):
# #                         skipped += 1
# #                         await write_skip_log(
# #                             session,
# #                             run_id=None,
# #                             sequence_id=seq.id,
# #                             campaign_id=getattr(seq, "campaignId", None),
# #                             prospect_id=seq.prospectId,
# #                             skip_reason="warmup_cap",
# #                             detail="PARTIAL throttle hash did not pass for this tick bucket",
# #                         )
# #                         continue

# #                     # ── Step 3b': per-user quota enforcement (SAAS2-USER-BE §G) ──
# #                     # For the background scheduler, the "sender" is the sequence
# #                     # owner — the person whose MailBridge account will be used.
# #                     # sent_by_user_id is stamped inside _send_via_mailbridge on
# #                     # success (same value as seq_owner for scheduler-driven sends).
# #                     seq_owner = getattr(seq, "owner_user_id", None) or "system"
# #                     if seq_owner and seq_owner != "system":
# #                         try:
# #                             can_send, reason = await quota_service.check_can_send(
# #                                 session, seq_owner, count=1
# #                             )
# #                         except Exception as exc:  # noqa: BLE001 — never abort the tick
# #                             can_send, reason = False, f"quota_check_error: {exc}"
# #                         if not can_send:
# #                             skipped += 1
# #                             logger.info(
# #                                 "scheduler.sequence.quota_exceeded",
# #                                 schema=schema_name,
# #                                 sequence_id=seq.id,
# #                                 user_id=seq_owner,
# #                                 reason=reason,
# #                             )
# #                             await write_skip_log(
# #                                 session,
# #                                 run_id=None,
# #                                 sequence_id=seq.id,
# #                                 campaign_id=getattr(seq, "campaignId", None),
# #                                 prospect_id=seq.prospectId,
# #                                 skip_reason="quota_exceeded",
# #                                 detail=str(reason),
# #                             )
# #                             continue
# #                     else:
# #                         reason = "ok"
 
# #                     # ── Step 3c: per-user MailBridge resolution (SAAS2-USER-BE §G) ──
# #                     # Use the sequence owner's MailBridge config (their connected
# #                     # mailbox); fall back to the tenant-level default only when the
# #                     # owner has no personal config registered.
# #                     if seq_owner and seq_owner != "system":
# #                         config = await _resolve_mailbridge_config(session, seq_owner)
# #                     else:
# #                         config = tenant_default_config
# #                     if config is None:
# #                         config = tenant_default_config
 
# #                     # ── Step 3d: MailBridge dispatch (§9.5) ───────────────
# #                     # _send_via_mailbridge stamps seq.sent_by_user_id and
# #                     # seq.sent_via_external_user_id on the sequence row so the
# #                     # reply-poller can poll the correct MailBridge inbox.
# #                     msg_id = await _send_via_mailbridge(session, config, seq, user_id=seq_owner)
# #                     # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError across schemas)
# #                     await session.execute(
# #                         text(
# #                             "UPDATE \"Sequence\" SET status = 'Sent', "
# #                             "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
# #                             "WHERE id = :seq_id"
# #                         ),
# #                         {
# #                             "sent_at": datetime.now(timezone.utc),
# #                             "msg_id": msg_id,
# #                             "seq_id": seq.id,
# #                         },
# #                     )
# #                     sent += 1

# #                     # ── Step 3e: record daily sent aggregation ────────────
# #                     camp_id_for_log = getattr(seq, "campaignId", None)
# #                     if camp_id_for_log:
# #                         await upsert_daily_sent(
# #                             session,
# #                             campaign_id=camp_id_for_log,
# #                             sent_date=started.date(),
# #                             increment=1,
# #                         )

# #                     # ── Step 3f: record send against per-user quota ───────
# #                     if seq_owner and seq_owner != "system":
# #                         try:
# #                             await quota_service.record_send(session, seq_owner, count=1)
# #                         except Exception as exc:  # noqa: BLE001 — best-effort
# #                             logger.warning(
# #                                 "scheduler.sequence.quota_record_failed",
# #                                 schema=schema_name,
# #                                 sequence_id=seq.id,
# #                                 user_id=seq_owner,
# #                                 error=str(exc),
# #                             )
# #                 except Exception as exc:  # noqa: BLE001 — per-seq isolation
# #                     skipped += 1
# #                     logger.warning(
# #                         "scheduler.sequence.send_failed",
# #                         schema=schema_name,
# #                         sequence_id=seq.id,
# #                         error=str(exc),
# #                     )
# #                     await write_skip_log(
# #                         session,
# #                         run_id=None,
# #                         sequence_id=seq.id,
# #                         campaign_id=getattr(seq, "campaignId", None),
# #                         prospect_id=getattr(seq, "prospectId", None),
# #                         skip_reason="send_error",
# #                         detail=str(exc)[:500],
# #                     )
 
# #             await session.commit()
# #         finally:
# #             # ── Step 4: update SchedulerStatus counters + nextTickAt ─────
# #             ended = datetime.now(timezone.utc)
# #             if status_row is not None:
# #                 status_row.isRunning = False
# #                 status_row.lastTickAt = started
# #                 status_row.sentSinceLastTick = sent
# #                 status_row.skippedSinceLastTick = skipped
# #                 status_row.nextTickAt = started + timedelta(
# #                     seconds=settings.SCHEDULER_TICK_SECONDS
# #                 )
# #                 try:
# #                     await session.commit()
# #                 except Exception:  # noqa: BLE001
# #                     await session.rollback()
 
# #         summary["sent"] = sent
# #         summary["skipped"] = skipped
# #         summary["ended_at"] = ended.isoformat()
# #         summary["duration_ms"] = int((ended - started).total_seconds() * 1000)
# #         return summary
 
 
# # async def _get_tenant_scheduler_config(schema_name: str) -> dict:
# #     """Read scheduler.enabled and scheduler.tick_interval_minutes from
# #     the tenant's SystemParameter table.

# #     Returns a dict with:
# #       enabled: bool   — True if scheduler should run for this tenant
# #       tick_minutes: int — how often to send (in minutes, default 5)

# #     Falls back to safe defaults if the table doesn't exist or the keys
# #     are missing (fail-open: enabled=True, tick_minutes=5).
# #     """
# #     defaults = {"enabled": True, "tick_minutes": 5}
# #     try:
# #         async with AsyncSessionLocal() as session:
# #             await session.execute(
# #                 text(f'SET search_path TO "{schema_name}", public')
# #             )

# #             # Read scheduler.enabled
# #             enabled_row = await session.execute(
# #                 text(
# #                     'SELECT value FROM "SystemParameter" '
# #                     "WHERE key = 'scheduler.enabled' LIMIT 1"
# #                 )
# #             )
# #             enabled_val = enabled_row.scalar()
# #             if enabled_val is not None:
# #                 defaults["enabled"] = enabled_val.lower().strip() not in (
# #                     "false", "0", "no", "off", "disabled"
# #                 )

# #             # Read scheduler.tick_interval_minutes
# #             interval_row = await session.execute(
# #                 text(
# #                     'SELECT value FROM "SystemParameter" '
# #                     "WHERE key = 'scheduler.tick_interval_minutes' LIMIT 1"
# #                 )
# #             )
# #             interval_val = interval_row.scalar()
# #             if interval_val is not None:
# #                 try:
# #                     defaults["tick_minutes"] = max(1, int(float(interval_val)))
# #                 except (ValueError, TypeError):
# #                     pass

# #     except Exception as exc:  # noqa: BLE001 — never block the tick
# #         err = str(exc)
# #         if "does not exist" not in err and "UndefinedTable" not in err:
# #             logger.warning(
# #                 "scheduler.tenant_config.read_failed",
# #                 schema=schema_name,
# #                 error=err[:200],
# #             )
# #     return defaults


# # # Per-tenant last-tick timestamps — used to enforce per-tenant tick intervals
# # # without needing a separate DB table. Resets on process restart (fine —
# # # worst case all tenants tick once on restart regardless of interval).
# # _tenant_last_tick: dict[str, datetime] = {}


# # async def run_tick_all_tenants() -> dict[str, Any]:
# #     """Run a tick across every ACTIVE tenant schema.

# #     Per-tenant control:
# #       scheduler.enabled = false  → tenant is completely skipped this tick
# #       scheduler.tick_interval_minutes = N → tenant only ticks if at least
# #         N minutes have passed since its last successful tick.

# #     Per migration §9.6 L1362-1378: SELECT schema_name FROM public.tenants
# #     WHERE status='ACTIVE' AND deleted_at IS NULL. Per-tenant failure is
# #     logged + skipped — it never aborts the entire tick.
# #     """
# #     summary: dict[str, Any] = {
# #         "tenants": 0,
# #         "sent": 0,
# #         "skipped": 0,
# #         "failed_tenants": 0,
# #         "tenants_disabled": 0,
# #         "tenants_interval_skipped": 0,
# #     }

# #     # Query public.tenants directly via a raw connection (not the ORM)
# #     # so we don't pollute the tenant-schema-bound session cache.
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
# #         if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
# #             raise
# #         logger.warning("scheduler.tick.no_tenants_table", error=str(exc))
# #         schemas = []

# #     summary["tenant_count"] = len(schemas)
# #     now = datetime.now(timezone.utc)

# #     for schema in schemas:
# #         try:
# #             # ── Read per-tenant scheduler config from SystemParameter ──────
# #             tenant_cfg = await _get_tenant_scheduler_config(schema)

# #             # Gate 1: tenant has disabled their scheduler
# #             if not tenant_cfg["enabled"]:
# #                 summary["tenants_disabled"] += 1
# #                 logger.debug(
# #                     "scheduler.tenant.disabled",
# #                     schema=schema,
# #                 )
# #                 continue

# #             # Gate 2: tick interval not yet elapsed for this tenant
# #             tick_interval_minutes = tenant_cfg["tick_minutes"]
# #             last_tick = _tenant_last_tick.get(schema)
# #             if last_tick is not None:
# #                 elapsed_minutes = (now - last_tick).total_seconds() / 60
# #                 if elapsed_minutes < tick_interval_minutes:
# #                     summary["tenants_interval_skipped"] += 1
# #                     logger.debug(
# #                         "scheduler.tenant.interval_not_elapsed",
# #                         schema=schema,
# #                         elapsed_minutes=round(elapsed_minutes, 1),
# #                         required_minutes=tick_interval_minutes,
# #                     )
# #                     continue

# #             # ── Run tick for this tenant ───────────────────────────────────
# #             tick_result = await run_tick(schema)
# #             _tenant_last_tick[schema] = now  # record successful tick time
# #             summary["tenants"] += 1
# #             summary["sent"] += tick_result.get("sent", 0)
# #             summary["skipped"] += tick_result.get("skipped", 0)

# #         except Exception as exc:  # noqa: BLE001 — per-tenant isolation
# #             summary["failed_tenants"] += 1
# #             logger.error(
# #                 "scheduler.tenant_failed",
# #                 schema=schema,
# #                 error=str(exc),
# #                 exc_info=True,
# #             )

# #     return summary
 
 
# # # ── Phase 3 SchedulerService (preserved) ────────────────────────────────────
 
 
# # class SchedulerService:
# #     """Backwards-compatible wrapper exposing the Phase 3 status +
# #     manual-tick endpoints. Phase 5 callers should use run_tick() /
# #     run_tick_all_tenants() / get_scheduler() directly."""
 
# #     def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
# #         self._mailbridge = mailbridge or MailBridgeService()
 
# #     async def get_status(self, db: AsyncSession) -> SchedulerStatus:
# #         """Return the singleton status row, creating it if absent."""
# #         result = await db.execute(
# #             select(SchedulerStatus).where(SchedulerStatus.id == 1)
# #         )
# #         status = result.scalar_one_or_none()
# #         if status is None:
# #             status = SchedulerStatus(id=1, isRunning=False)
# #             db.add(status)
# #             await db.commit()
# #             status = await db.get(SchedulerStatus, status.id)
# #         return status
 
# #     async def manual_tick(
# #         self,
# #         db: AsyncSession,
# #         *,
# #         tenant_scoped: bool = True,
# #         max_send: int = 50,
# #     ) -> ManualTickResponse:
# #         """Send up to max_send Scheduled sequences in one synchronous tick.
 
# #         Phase 3 contract — preserved verbatim. Does NOT apply the §9.2/§9.3
# #         business-hours + PARTIAL throttle filters (callers that want the
# #         Phase 5 behavior should invoke run_tick() instead).
# #         """
# #         started = datetime.now(timezone.utc)
# #         status = await self.get_status(db)
# #         status.isRunning = True
# #         await db.commit()
 
# #         sent = 0
# #         skipped = 0
# #         try:
# #             result = await db.execute(
# #                 select(Sequence)
# #                 .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
# #                 .limit(max_send)
# #             )
# #             sequences = list(result.scalars().all())
# #             for seq in sequences:
# #                 # Phase 5 will add business-hours + throttle filters here.
# #                 try:
# #                     # Wiring audit (Task 2-e): previously this method passed
# #                     # ``to=""`` to MailBridgeService.send with a comment saying
# #                     # "caller resolves prospect.email" — but no caller actually
# #                     # did so, resulting in empty-envelope stub-accepts. Resolve
# #                     # the prospect email (with PII decrypt) here so the manual
# #                     # tick actually delivers. Mirrors SequenceService.send_email.
# #                     to_email = ""
# #                     if seq.prospectId:
# #                         p_result = await db.execute(
# #                             select(Prospect).where(Prospect.id == seq.prospectId)
# #                         )
# #                         p = p_result.scalar_one_or_none()
# #                         if p is not None:
# #                             raw_email = getattr(p, "email", None) or ""
# #                             if raw_email and not getattr(p, "anonymized", False):
# #                                 try:
# #                                     from app.services.pii_service import PiiService
 
# #                                     to_email = (
# #                                         PiiService().decrypt_field(raw_email)
# #                                         or raw_email
# #                                     )
# #                                 except Exception:  # noqa: BLE001 — best-effort
# #                                     to_email = raw_email
# #                             elif raw_email:
# #                                 to_email = raw_email
# #                     if not to_email:
# #                         skipped += 1
# #                         continue
# #                     send_result = await self._mailbridge.send(
# #                         db=db,
# #                         to=to_email,
# #                         subject=seq.subjectLine or "",
# #                         body=seq.bodyCopy or "",
# #                         sequence_id=seq.id,
# #                         user_id=getattr(seq, "owner_user_id", None),
# #                     )
# #                     if send_result.accepted:
# #                         # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError)
# #                         # seq.status = EmailStatus.Sent would generate $1::email_status
# #                         # which fails across tenant schemas due to asyncpg plan cache.
# #                         await db.execute(
# #                             text(
# #                                 "UPDATE \"Sequence\" SET status = 'Sent', "
# #                                 "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
# #                                 "WHERE id = :seq_id"
# #                             ),
# #                             {
# #                                 "sent_at": datetime.now(timezone.utc),
# #                                 "msg_id": send_result.messageId,
# #                                 "seq_id": seq.id,
# #                             },
# #                         )
# #                         sent += 1
# #                     else:
# #                         skipped += 1
# #                 except Exception:  # noqa: BLE001
# #                     skipped += 1
# #             try:
# #                 await db.commit()
# #             except Exception:  # noqa: BLE001 — swallow if already aborted
# #                 await db.rollback()
# #         finally:
# #             duration_ms = int(
# #                 (datetime.now(timezone.utc) - started).total_seconds() * 1000
# #             )
# #             # FIX: rollback any aborted transaction before updating SchedulerStatus
# #             # so the finally block never runs inside an aborted transaction.
# #             try:
# #                 await db.rollback()
# #             except Exception:  # noqa: BLE001
# #                 pass
# #             try:
# #                 await db.execute(
# #                     text(
# #                         'UPDATE "SchedulerStatus" SET "isRunning" = false, '
# #                         '"lastTickAt" = :last, "nextTickAt" = :next, '
# #                         '"sentSinceLastTick" = :sent, "skippedSinceLastTick" = :skipped, '
# #                         '"updatedAt" = now() WHERE id = 1'
# #                     ),
# #                     {
# #                         "last": started,
# #                         "next": started + timedelta(seconds=get_settings().SCHEDULER_TICK_SECONDS),
# #                         "sent": sent,
# #                         "skipped": skipped,
# #                     },
# #                 )
# #                 await db.commit()
# #             except Exception as _fin_exc:  # noqa: BLE001
# #                 logger.warning(
# #                     "scheduler.manual_tick.status_update_failed",
# #                     error=str(_fin_exc)[:200],
# #                 )
# #         return ManualTickResponse(
# #             sent=sent,
# #             skipped=skipped,
# #             durationMs=duration_ms,
# #             tickedAt=started,
# #         )
 
# #     async def trigger(self, db: AsyncSession) -> "TriggerResponse":
# #         """Trigger an immediate scheduler tick via Celery or direct invocation.
 
# #         If Celery is available and the broker is reachable, enqueues
# #         ``autopilot.run_pipeline`` and returns immediately with the task ID
# #         as ``runId``. Otherwise falls back to a synchronous tick and logs
# #         a ``SchedulerRun`` row.
 
# #         Returns a ``TriggerResponse`` with ``triggered=True`` on success.
# #         """
# #         from app.schemas.scheduler import TriggerResponse
 
# #         # FIX: SchedulerRun table may not exist yet (migration 0019 creates it).
# #         # If insert fails, continue without logging - the tick still runs.
# #         run = None
# #         try:
# #             _run_obj = SchedulerRun(status="running")
# #             db.add(_run_obj)
# #             await db.commit()
# #             run = await db.get(SchedulerRun, _run_obj.id)
# #         except Exception as _exc:  # noqa: BLE001
# #             await db.rollback()
# #             logger.warning(
# #                 "scheduler.trigger.run_log_skipped",
# #                 hint="Run migration 0019 to create SchedulerRun table",
# #                 error=str(_exc)[:200],
# #             )
 
# #         # Attempt Celery enqueue
# #         try:
# #             from app.worker.celery_app import celery_app
 
# #             if celery_app is not None:
# #                 result = celery_app.send_task(
# #                     "autopilot.run_pipeline",
# #                     kwargs={"schema_name": "current"},
# #                 )
# #                 if run is not None:
# #                     run.status = "completed"
# #                     run.completedAt = datetime.now(timezone.utc)
# #                     await db.commit()
# #                 return TriggerResponse(
# #                     triggered=True,
# #                     message="Scheduler triggered via Celery.",
# #                     runId=result.id,
# #                 )
# #         except Exception as exc:  # noqa: BLE001
# #             logger.warning("scheduler.trigger.celery_failed", error=str(exc))
 
# #         # Fallback: synchronous tick
# #         started = datetime.now(timezone.utc)
# #         try:
# #             tick_result = await self.manual_tick(
# #                 db, tenant_scoped=True, max_send=50
# #             )
# #             if run is not None:
# #                 run.status = "completed"
# #                 run.sent = tick_result.sent
# #                 run.skipped = tick_result.skipped
# #                 run.durationMs = tick_result.durationMs
# #                 run.completedAt = datetime.now(timezone.utc)
# #                 await db.commit()
# #             return TriggerResponse(
# #                 triggered=True,
# #                 message="Scheduler tick completed synchronously.",
# #                 runId=run.id if run else None,
# #             )
# #         except Exception as exc:  # noqa: BLE001
# #             if run is not None:
# #                 run.status = "failed"
# #                 run.error = str(exc)
# #                 run.completedAt = datetime.now(timezone.utc)
# #                 await db.commit()
# #             return TriggerResponse(
# #                 triggered=False,
# #                 message=f"Scheduler tick failed: {exc}",
# #                 runId=run.id if run else None,
# #             )
 
# #     async def list_runs(
# #         self,
# #         db: AsyncSession,
# #         *,
# #         limit: int = 20,
# #         offset: int = 0,
# #     ) -> "SchedulerRunsListResponse":
# #         """Return recent scheduler run log entries, newest first.
 
# #         FIX: SchedulerRun table was never in any migration — wraps queries in
# #         try/except so the Scheduler Status page loads cleanly even on tenants
# #         that have not run migration 0019 yet. Returns empty list in that case.
# #         """
# #         from app.schemas.scheduler import (
# #             SchedulerRunResponse,
# #             SchedulerRunsListResponse,
# #         )
# #         from sqlalchemy import func as sa_func
 
# #         try:
# #             count_result = await db.execute(
# #                 select(sa_func.count()).select_from(SchedulerRun)
# #             )
# #             total = count_result.scalar() or 0
 
# #             result = await db.execute(
# #                 select(SchedulerRun)
# #                 .order_by(SchedulerRun.startedAt.desc())
# #                 .limit(limit)
# #                 .offset(offset)
# #             )
# #             rows = list(result.scalars().all())
# #             items = [SchedulerRunResponse.model_validate(r) for r in rows]
# #             return SchedulerRunsListResponse(items=items, total=total)
# #         except Exception as exc:  # noqa: BLE001
# #             # Table does not exist yet - return empty list instead of crashing.
# #             # Resolved permanently by running migration 0019.
# #             err_str = str(exc)
# #             if "UndefinedTableError" in err_str or "does not exist" in err_str or "undefined_table" in err_str.lower():
# #                 await db.rollback()
# #                 logger.warning(
# #                     "scheduler.list_runs.table_missing",
# #                     hint="Run migration 0019 to create SchedulerRun table",
# #                     error=err_str[:200],
# #                 )
# #                 return SchedulerRunsListResponse(items=[], total=0)
# #             raise
 
 
# # __all__ = [
# #     "SchedulerService",
# #     "get_scheduler",
# #     "run_tick",
# #     "run_tick_all_tenants",
# #     "_is_business_hours",
# #     "_partial_throttle_passes",
# #     "_resolve_mailbridge_config",
# #     "_send_via_mailbridge",
# #     "_async_tick_wrapper",
# # ]

# # # # """
# # # # scheduler/service.py — Outrena email scheduler (auto + manual tick).

# # # # ────────────────────────────────────────────────────────────────────────────
# # # # QUOTA LOGIC (identical for auto and manual tick)
# # # # ────────────────────────────────────────────────────────────────────────────

# # # # The daily send cap is resolved in this priority order for every sequence:

# # # #   1. Campaign has a domain linked (Campaign.domainId set)?
# # # #         AND that domain has been DNS-verified (lastChecked IS NOT NULL)?
# # # #         AND all three DNS records pass (SPF + DKIM + DMARC)?
# # # #      → USE WARMUP WEEK CAP:
# # # #           week 1 =  10/day
# # # #           week 2 =  30/day
# # # #           week 3 =  50/day
# # # #           week 4 = 100/day
# # # #           week 5 = 200/day
# # # #           week 6 = 350/day
# # # #           week 7 = 500/day
# # # #           week 8+ = Domain.dailySendLimit (or 10 000 if not explicitly set >10)

# # # #   2. Otherwise (no domain, domain unverified, or DNS failing)
# # # #      → USE ENV DEFAULT: settings.DEFAULT_USER_DAILY_EMAIL_QUOTA (default 100)

# # # # ────────────────────────────────────────────────────────────────────────────
# # # # GATES: AUTO TICK vs MANUAL TICK
# # # # ────────────────────────────────────────────────────────────────────────────

# # # #   Gate                    Auto tick    Manual tick
# # # #   ──────────────────────  ─────────    ───────────
# # # #   No email / suppressed   ✅ checked   ✅ checked   (always wrong to send)
# # # #   Email suppression list  ✅ checked   ✅ checked   (legal compliance)
# # # #   Business hours          ✅ checked   ✗ skipped   (manual = send now)
# # # #   PARTIAL throttle        ✅ checked   ✗ skipped   (not relevant)
# # # #   Domain quota (above)    ✅ checked   ✅ checked   (warmup cap is sacred)
# # # #   DNS verification        ✅ checked   ✗ skipped   (operator override)

# # # # ────────────────────────────────────────────────────────────────────────────
# # # # BUSINESS HOURS LOGIC
# # # # ────────────────────────────────────────────────────────────────────────────

# # # #   prospect.timezone IS SET  → enforce 9am–5pm Mon–Fri in that timezone
# # # #   prospect.timezone IS NULL → SEND ANYWAY (unknown location = no restriction)
# # # #                                Do NOT default to America/New_York — that
# # # #                                assumption is wrong for non-US prospects.

# # # # ────────────────────────────────────────────────────────────────────────────
# # # # """
# # # # from __future__ import annotations

# # # # import asyncio
# # # # import hashlib
# # # # import zoneinfo
# # # # from datetime import date, datetime, time, timedelta, timezone
# # # # from typing import Any

# # # # import httpx
# # # # import structlog
# # # # from apscheduler.schedulers.asyncio import AsyncIOScheduler
# # # # from sqlalchemy import select, text
# # # # from sqlalchemy.ext.asyncio import AsyncSession

# # # # from app.core.config import get_settings
# # # # from app.core.database import AsyncSessionLocal, engine
# # # # from app.models.campaign_models import Campaign, Sequence
# # # # from app.models.config_models import Domain, MailBridgeConfig
# # # # from app.models.enums import EmailStatus, EnrichmentTier
# # # # from app.models.phase3_models import SchedulerRun, SchedulerStatus
# # # # from app.models.prospect_models import Prospect
# # # # from app.schemas.scheduler import ManualTickResponse
# # # # from app.features.mailbridge.service import MailBridgeService
# # # # from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
# # # # from app.features.mailbridge.reply_poller import register_reply_poll_job
# # # # from app.features.scheduler.query_service import write_skip_log, upsert_daily_sent
# # # # from app.models.base import _generate_cuid

# # # # logger = structlog.get_logger(__name__)

# # # # # ── Module-global singleton scheduler ──────────────────────────────────────
# # # # _scheduler: AsyncIOScheduler | None = None

# # # # # ── Warmup ramp table ──────────────────────────────────────────────────────
# # # # # Week 1=10, 2=30, 3=50, 4=100, 5=200, 6=350, 7=500
# # # # _WARMUP_RAMP: dict[int, int] = {1: 10, 2: 30, 3: 50, 4: 100, 5: 200, 6: 350, 7: 500}
# # # # WARMING_SCHEDULE = [10, 30, 50, 100, 200, 350, 500]  # exported for UI display


# # # # # ═══════════════════════════════════════════════════════════════════════════
# # # # # SCHEDULER SINGLETON
# # # # # ═══════════════════════════════════════════════════════════════════════════

# # # # def get_scheduler() -> AsyncIOScheduler:
# # # #     """Return the AsyncIOScheduler singleton."""
# # # #     global _scheduler
# # # #     if _scheduler is None:
# # # #         settings = get_settings()
# # # #         _scheduler = AsyncIOScheduler()
# # # #         _scheduler.add_job(
# # # #             _async_tick_wrapper,
# # # #             "interval",
# # # #             seconds=settings.SCHEDULER_TICK_SECONDS,
# # # #             id="outrena_tick",
# # # #             max_instances=1,
# # # #             coalesce=True,
# # # #             replace_existing=True,
# # # #         )
# # # #         _scheduler.add_job(
# # # #             _async_cost_rollup_wrapper,
# # # #             "cron",
# # # #             hour=2,
# # # #             minute=0,
# # # #             id="outrena_cost_rollup",
# # # #             max_instances=1,
# # # #             coalesce=True,
# # # #             replace_existing=True,
# # # #         )
# # # #         from app.features.mailbridge.reply_poller import register_reply_poll_job
# # # #         register_reply_poll_job(_scheduler)
# # # #         logger.info(
# # # #             "scheduler.registered",
# # # #             tick_seconds=settings.SCHEDULER_TICK_SECONDS,
# # # #             job_id="outrena_tick",
# # # #         )
# # # #     return _scheduler


# # # # async def _async_tick_wrapper() -> None:
# # # #     """Top-level tick wrapper — catches every exception so a single
# # # #     tenant failure never kills the scheduler."""
# # # #     try:
# # # #         summary = await run_tick_all_tenants()
# # # #         logger.info("scheduler.tick.complete", **summary)
# # # #     except Exception as exc:  # noqa: BLE001
# # # #         logger.error("scheduler.tick.fatal", error=str(exc), exc_info=True)


# # # # async def _async_cost_rollup_wrapper() -> None:
# # # #     """Nightly job — materialise CostSummary rows for all active tenants."""
# # # #     from app.core.database import AsyncSessionLocal
# # # #     from app.features.usage.service import UsageService
# # # #     from datetime import date as _date

# # # #     period = _date.today().strftime("%Y-%m")
# # # #     total = 0
# # # #     errors = 0
# # # #     try:
# # # #         async with AsyncSessionLocal() as db:
# # # #             from sqlalchemy import text as _text
# # # #             try:
# # # #                 result = await db.execute(
# # # #                     _text("SELECT slug FROM public.tenants WHERE status = 'ACTIVE' AND deleted_at IS NULL")
# # # #                 )
# # # #                 slugs = [row[0] for row in result.all()]
# # # #             except Exception as exc:  # noqa: BLE001
# # # #                 if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
# # # #                     raise
# # # #                 logger.warning("scheduler.cost_rollup.no_tenants_table", error=str(exc))
# # # #                 slugs = []

# # # #         for slug in slugs:
# # # #             try:
# # # #                 svc = UsageService()
# # # #                 written = await svc.rebuild_cost_summaries(slug, period)
# # # #                 total += written
# # # #             except Exception as exc:  # noqa: BLE001
# # # #                 errors += 1
# # # #                 logger.warning("scheduler.cost_rollup.tenant_failed", tenant=slug, error=str(exc))

# # # #         logger.info(
# # # #             "scheduler.cost_rollup.complete",
# # # #             period=period,
# # # #             tenants=len(slugs),
# # # #             rows_written=total,
# # # #             errors=errors,
# # # #         )

# # # #         # FR-038: nightly warm-up week advancement
# # # #         advanced_total = 0
# # # #         for slug in slugs:
# # # #             try:
# # # #                 async with AsyncSessionLocal() as db:
# # # #                     from sqlalchemy import text as _text
# # # #                     await db.execute(_text(f'SET search_path TO "tenant_{slug}", public'))
# # # #                     advanced_total += await advance_domain_warmup(db)
# # # #                     await db.commit()
# # # #             except Exception as exc:  # noqa: BLE001
# # # #                 logger.warning("scheduler.warmup_advance.tenant_failed", tenant=slug, error=str(exc))
# # # #         if advanced_total:
# # # #             logger.info("scheduler.warmup_advance.complete", domains=advanced_total)

# # # #     except Exception as exc:  # noqa: BLE001
# # # #         logger.error("scheduler.cost_rollup.fatal", error=str(exc), exc_info=True)


# # # # # ═══════════════════════════════════════════════════════════════════════════
# # # # # DOMAIN WARMUP HELPERS
# # # # # ═══════════════════════════════════════════════════════════════════════════

# # # # def _warmup_effective_cap(dom: Domain) -> int:
# # # #     """Return the effective daily send cap for a domain.

# # # #     - warmingWeek 1–7  → ramp cap from _WARMUP_RAMP
# # # #     - warmingWeek 8+   → Domain.dailySendLimit (treat ≤10 as not configured → 10 000)
# # # #     - warmingWeek 0    → not started → use dailySendLimit (or 10 000)
# # # #     """
# # # #     week = int(getattr(dom, "warmingWeek", 0) or 0)
# # # #     raw_limit = int(getattr(dom, "dailySendLimit", 0) or 0)
# # # #     # dailySendLimit defaults to 10 in the model — treat ≤10 as "not explicitly set"
# # # #     base = raw_limit if raw_limit > 10 else 10_000
# # # #     if 1 <= week <= 7:
# # # #         return min(base, _WARMUP_RAMP[week])
# # # #     return base


# # # # async def advance_domain_warmup(db: AsyncSession) -> int:
# # # #     """Advance warmingWeek for domains warmed ≥7 days. Called nightly."""
# # # #     result = await db.execute(
# # # #         text(
# # # #             'UPDATE "Domain" SET '
# # # #             '  "warmingWeek" = "warmingWeek" + 1, '
# # # #             '  "updatedAt" = now() '
# # # #             'WHERE "warmingWeek" BETWEEN 1 AND 7 '
# # # #             "  AND \"updatedAt\" < now() - interval '7 days'"
# # # #         )
# # # #     )
# # # #     return result.rowcount or 0


# # # # # ═══════════════════════════════════════════════════════════════════════════
# # # # # QUOTA RESOLUTION  (shared by auto-tick and manual-tick)
# # # # # ═══════════════════════════════════════════════════════════════════════════

# # # # async def _resolve_daily_cap(
# # # #     db: AsyncSession,
# # # #     campaign_id: str | None,
# # # # ) -> tuple[int, str]:
# # # #     """Return (effective_daily_cap, source_label).

# # # #     source_label is one of:
# # # #       "warmup_week_{N}"  — domain warmup ramp cap
# # # #       "domain_limit"     — post-warmup domain dailySendLimit
# # # #       "env_default"      — settings.DEFAULT_USER_DAILY_EMAIL_QUOTA

# # # #     Logic:
# # # #       Campaign has domainId AND domain has been DNS-verified
# # # #       AND all DNS records pass → warmup cap governs.
# # # #       Otherwise → env default.
# # # #     """
# # # #     settings = get_settings()
# # # #     env_cap = settings.DEFAULT_USER_DAILY_EMAIL_QUOTA

# # # #     if not campaign_id:
# # # #         return env_cap, "env_default"

# # # #     try:
# # # #         camp = (
# # # #             await db.execute(select(Campaign).where(Campaign.id == campaign_id))
# # # #         ).scalar_one_or_none()

# # # #         if camp is None or not getattr(camp, "domainId", None):
# # # #             return env_cap, "env_default"

# # # #         dom = (
# # # #             await db.execute(select(Domain).where(Domain.id == camp.domainId))
# # # #         ).scalar_one_or_none()

# # # #         if dom is None:
# # # #             return env_cap, "env_default"

# # # #         # Domain must have been verified at least once
# # # #         if dom.lastChecked is None:
# # # #             return env_cap, "env_default"

# # # #         # All three DNS records must pass
# # # #         if not (dom.spfStatus and dom.dkimStatus and dom.dmarcStatus):
# # # #             return env_cap, "env_default"

# # # #         # Domain is verified — warmup cap governs
# # # #         week = int(getattr(dom, "warmingWeek", 0) or 0)
# # # #         cap = _warmup_effective_cap(dom)
# # # #         source = f"warmup_week_{week}" if 1 <= week <= 7 else "domain_limit"
# # # #         return cap, source

# # # #     except Exception as exc:  # noqa: BLE001 — fail open to env default
# # # #         logger.warning("scheduler.quota_resolve.failed", error=str(exc)[:200])
# # # #         return env_cap, "env_default"


# # # # async def _count_sent_today(db: AsyncSession, campaign_id: str | None) -> int:
# # # #     """Count emails sent today for this campaign from SchedulerDailySent,
# # # #     falling back to Sequence.sentAt aggregate if table doesn't exist."""
# # # #     if not campaign_id:
# # # #         return 0
# # # #     try:
# # # #         result = await db.execute(
# # # #             text(
# # # #                 'SELECT "sentCount" FROM "SchedulerDailySent" '
# # # #                 'WHERE "campaignId" = :cid AND "sentDate" = CURRENT_DATE'
# # # #             ),
# # # #             {"cid": campaign_id},
# # # #         )
# # # #         row = result.fetchone()
# # # #         return int(row[0]) if row else 0
# # # #     except Exception:  # noqa: BLE001 — table may not exist
# # # #         pass
# # # #     # Fallback: count directly from Sequence
# # # #     try:
# # # #         result = await db.execute(
# # # #             text(
# # # #                 'SELECT COUNT(*) FROM "Sequence" '
# # # #                 'WHERE "campaignId" = :cid '
# # # #                 "AND \"sentAt\" >= date_trunc('day', now() AT TIME ZONE 'UTC')"
# # # #             ),
# # # #             {"cid": campaign_id},
# # # #         )
# # # #         return int(result.scalar() or 0)
# # # #     except Exception:  # noqa: BLE001
# # # #         return 0


# # # # # ═══════════════════════════════════════════════════════════════════════════
# # # # # BUSINESS HOURS  (auto-tick only)
# # # # # ═══════════════════════════════════════════════════════════════════════════

# # # # def _is_business_hours(now: datetime, tz_name: str | None) -> bool:
# # # #     """Return True iff sending is permitted for this prospect right now.

# # # #     Rules:
# # # #       - prospect.timezone is NULL  → return True (unknown location = no gate)
# # # #       - prospect.timezone is set   → enforce 9am–5pm Mon–Fri in that tz
# # # #       - timezone string invalid    → return True (fail open, don't block)

# # # #     We deliberately do NOT default NULL to America/New_York because that
# # # #     assumption is wrong for non-US prospects (e.g. India, UK, APAC).
# # # #     """
# # # #     if tz_name is None:
# # # #         # Timezone unknown — send immediately, don't guess
# # # #         return True

# # # #     try:
# # # #         tz = zoneinfo.ZoneInfo(tz_name)
# # # #         local = now.astimezone(tz)
# # # #     except Exception:  # noqa: BLE001 — invalid tz string, fail open
# # # #         return True

# # # #     if local.weekday() >= 5:  # Sat=5, Sun=6
# # # #         return False
# # # #     return time(9, 0) <= local.time() <= time(17, 0)


# # # # # ═══════════════════════════════════════════════════════════════════════════
# # # # # PARTIAL THROTTLE  (auto-tick only)
# # # # # ═══════════════════════════════════════════════════════════════════════════

# # # # def _partial_throttle_passes(prospect_id: str, tick_bucket: int) -> bool:
# # # #     """Deterministic hash throttle for PARTIAL-enrichment prospects."""
# # # #     settings = get_settings()
# # # #     cap = settings.SCHEDULER_PARTIAL_PER_TICK_CAP
# # # #     hash_input = f"{prospect_id}:{tick_bucket}"
# # # #     bucket = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16) % 100
# # # #     return bucket < cap


# # # # # ═══════════════════════════════════════════════════════════════════════════
# # # # # MAILBRIDGE CONFIG RESOLUTION
# # # # # ═══════════════════════════════════════════════════════════════════════════

# # # # async def _resolve_mailbridge_config(
# # # #     db: AsyncSession, user_id: str | None
# # # # ) -> MailBridgeConfig | None:
# # # #     """Resolve MailBridgeConfig: per-user first, then tenant fallback."""
# # # #     has_owner_col = hasattr(MailBridgeConfig, "owner_user_id")
# # # #     if user_id and has_owner_col:
# # # #         try:
# # # #             result = await db.execute(
# # # #                 select(MailBridgeConfig)
# # # #                 .where(MailBridgeConfig.isActive.is_(True))
# # # #                 .where(getattr(MailBridgeConfig, "owner_user_id") == user_id)
# # # #                 .limit(1)
# # # #             )
# # # #             cfg = result.scalar_one_or_none()
# # # #             if cfg is not None:
# # # #                 return cfg
# # # #         except Exception as exc:  # noqa: BLE001
# # # #             logger.warning("scheduler.mailbridge.per_user_lookup_failed", user_id=user_id, error=str(exc))

# # # #     result = await db.execute(
# # # #         select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
# # # #     )
# # # #     return result.scalar_one_or_none()


# # # # # ═══════════════════════════════════════════════════════════════════════════
# # # # # HTML HELPERS
# # # # # ═══════════════════════════════════════════════════════════════════════════

# # # # def _is_html_body(body: str | None) -> bool:
# # # #     if not body:
# # # #         return False
# # # #     s = body.lstrip()
# # # #     return s.startswith("<") and any(
# # # #         marker in body
# # # #         for marker in ("</p>", "</h", "<br", "</ul>", "</ol>", "</li>", "</strong>", "</em>")
# # # #     )


# # # # def _strip_html_text(html: str) -> str:
# # # #     import re as _re
# # # #     text_content = _re.sub(r"<[^>]+>", " ", html)
# # # #     return _re.sub(r"\s+", " ", text_content).strip()


# # # # # ═══════════════════════════════════════════════════════════════════════════
# # # # # MAILBRIDGE DISPATCH
# # # # # ═══════════════════════════════════════════════════════════════════════════

# # # # async def _send_via_mailbridge(
# # # #     db: AsyncSession,
# # # #     config: MailBridgeConfig | None,
# # # #     sequence: Sequence,
# # # #     user_id: str | None = None,
# # # # ) -> str:
# # # #     """Send one sequence via MailBridge and return the messageId.

# # # #     NOTE: DNS verification and warmup cap are NOT checked here in the
# # # #     send function — they are checked by the caller (run_tick / manual_tick)
# # # #     BEFORE calling this function. This keeps the send function clean and
# # # #     allows manual_tick to skip DNS verification while auto-tick enforces it.
# # # #     """
# # # #     # Resolve prospect + recipient email
# # # #     prospect_result = await db.execute(
# # # #         select(Prospect).where(Prospect.id == sequence.prospectId)
# # # #     )
# # # #     prospect = prospect_result.scalar_one_or_none()
# # # #     if prospect is None or not prospect.email:
# # # #         raise RuntimeError(f"Prospect {sequence.prospectId} missing or has no email")

# # # #     raw_email = prospect.email
# # # #     if not getattr(prospect, "anonymized", False):
# # # #         try:
# # # #             from app.services.pii_service import PiiService
# # # #             recipient_email = PiiService().decrypt_field(raw_email) or raw_email
# # # #         except Exception:  # noqa: BLE001
# # # #             recipient_email = raw_email
# # # #     else:
# # # #         recipient_email = raw_email

# # # #     if not recipient_email:
# # # #         raise RuntimeError(f"Prospect {sequence.prospectId} email is empty after decrypt")

# # # #     settings = get_settings()

# # # #     # Dev/CI stub: no config + no default URL → deterministic fake id
# # # #     if config is None and not settings.MAILBRIDGE_DEFAULT_URL:
# # # #         msg_id = f"stub-{sequence.id}@outrena.local"
# # # #         await _record_usage_send_safe(db, sequence)
# # # #         return msg_id

# # # #     base_url = (config.baseUrl if config else "") or settings.MAILBRIDGE_DEFAULT_URL

# # # #     # Build body with CAN-SPAM footer
# # # #     body_text = sequence.bodyCopy or ""
# # # #     is_html = _is_html_body(body_text)

# # # #     needs_footer = (
# # # #         "unsubscribe" not in body_text.lower()
# # # #         or "physical" not in body_text.lower()
# # # #         and "address" not in body_text.lower()
# # # #     )
# # # #     if needs_footer:
# # # #         try:
# # # #             from app.utils.tenant_context import resolve_tenant_slug as _rts
# # # #             from app.core.config import get_settings as _gs
# # # #             _tenant_slug = await _rts(db)
# # # #             _prospect_token = getattr(prospect, "unsubscribeToken", None) or ""
# # # #             _base = _gs().BASE_DOMAIN
# # # #             _unsub_url = (
# # # #                 f"https://{_base}/api/v1/public/unsubscribe"
# # # #                 f"?token={_prospect_token}&tenant_slug={_tenant_slug}"
# # # #                 if _prospect_token and _tenant_slug
# # # #                 else ""
# # # #             )
# # # #             if is_html:
# # # #                 _unsub_link = (
# # # #                     f' <a href="{_unsub_url}" style="color:#6b7280;text-decoration:underline">Unsubscribe</a>'
# # # #                     if _unsub_url else ""
# # # #                 )
# # # #                 _html_footer = (
# # # #                     '<hr style="border:0;border-top:1px solid #e5e7eb;margin:24px 0">'
# # # #                     '<p style="color:#6b7280;font-size:11px;line-height:1.5;margin:0">'
# # # #                     f"This email was sent by an authorised OUTRENA user.{_unsub_link}</p>"
# # # #                 )
# # # #                 body_text = body_text + _html_footer
# # # #             else:
# # # #                 _footer_lines = ["", "---", "This email was sent by an authorised OUTRENA user."]
# # # #                 if _unsub_url:
# # # #                     _footer_lines.append(f"Unsubscribe: {_unsub_url}")
# # # #                 body_text = body_text + "\n".join(_footer_lines)
# # # #         except Exception:  # noqa: BLE001
# # # #             pass

# # # #     if is_html:
# # # #         body_html_final = body_text
# # # #         body_text_final = _strip_html_text(body_text)
# # # #     else:
# # # #         body_html_final = body_text
# # # #         body_text_final = body_text

# # # #     payload = {
# # # #         "to": [recipient_email],
# # # #         "subject": sequence.subjectLine or "",
# # # #         "body_html": body_html_final,
# # # #         "body_text": body_text_final,
# # # #     }

# # # #     config_owner = getattr(config, "owner_user_id", None) if config else None
# # # #     config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
# # # #     ext_user_id = (
# # # #         config_ext_id
# # # #         if (config_owner and config_owner == user_id and config_ext_id)
# # # #         else user_id
# # # #     )
# # # #     if ext_user_id:
# # # #         payload["external_user_id"] = ext_user_id

# # # #     api_key = (getattr(config, "mailbridge_api_key", None) if config else None) or settings.MAILBRIDGE_API_KEY
# # # #     headers: dict[str, str] = {"Content-Type": "application/json"}
# # # #     if api_key:
# # # #         headers["Authorization"] = f"Bearer {api_key}"

# # # #     timeout_s = float(settings.MAILBRIDGE_TIMEOUT_SECONDS)
# # # #     async with httpx.AsyncClient(timeout=timeout_s) as client:
# # # #         resp = await client.post(
# # # #             f"{base_url.rstrip('/')}/outbound/send",
# # # #             json=payload,
# # # #             headers=headers,
# # # #         )
# # # #         if resp.status_code >= 400:
# # # #             raise RuntimeError(f"MailBridge returned HTTP {resp.status_code}: {resp.text[:200]}")
# # # #         data = resp.json()
# # # #         msg_id = data.get("message_id") or data.get("messageId", "")
# # # #         if not msg_id:
# # # #             raise RuntimeError("MailBridge response missing message_id")

# # # #     if user_id:
# # # #         sequence.sent_by_user_id = user_id
# # # #     if ext_user_id:
# # # #         sequence.sent_via_external_user_id = ext_user_id

# # # #     await _record_usage_send_safe(db, sequence)
# # # #     return msg_id


# # # # async def _record_usage_send_safe(db: AsyncSession, sequence: Sequence) -> None:
# # # #     """Best-effort: record one usage_event(email_send) row."""
# # # #     try:
# # # #         from app.utils.tenant_context import resolve_tenant_slug
# # # #         tenant = await resolve_tenant_slug(db)
# # # #         if not tenant:
# # # #             return
# # # #         from app.features.usage.service import UsageService
# # # #         await UsageService().record_email_send(
# # # #             tenant=tenant,
# # # #             user_id=getattr(sequence, "owner_user_id", None) or "system",
# # # #             metadata={"source": "scheduler.run_tick", "sequence_id": sequence.id},
# # # #         )
# # # #     except Exception as exc:  # noqa: BLE001
# # # #         logger.warning("scheduler.send.usage_record_failed", sequence_id=getattr(sequence, "id", None), error=str(exc))


# # # # # ═══════════════════════════════════════════════════════════════════════════
# # # # # AUTO TICK — runs every SCHEDULER_TICK_SECONDS for all tenants
# # # # # ═══════════════════════════════════════════════════════════════════════════

# # # # async def run_tick(schema_name: str) -> dict[str, Any]:
# # # #     """Run a single auto-scheduler tick against one tenant schema.

# # # #     Gates (in order):
# # # #       1. status IN ('Scheduled','QaPassed') AND touchNumber <= 7
# # # #       2. prospect exists AND has email            → else skip (no_email)
# # # #       3. prospect.suppressed = False              → else skip (suppressed)
# # # #       4. email not in EmailSuppression table      → else skip (suppressed)
# # # #       5. business hours in prospect.timezone      → else skip (business_hours)
# # # #          (NULL timezone = skip gate, send anyway)
# # # #       6. PARTIAL enrichment throttle              → else skip (warmup_cap)
# # # #       7. DNS verification on domain               → else skip (send_error)
# # # #       8. daily cap check (warmup week OR env)     → else skip (quota_exceeded)
# # # #       9. _send_via_mailbridge
# # # #     """
# # # #     settings = get_settings()
# # # #     started = datetime.now(timezone.utc)
# # # #     tick_bucket = int(started.timestamp()) // settings.SCHEDULER_TICK_SECONDS

# # # #     summary: dict[str, Any] = {
# # # #         "schema": schema_name,
# # # #         "candidates": 0,
# # # #         "sent": 0,
# # # #         "skipped": 0,
# # # #         "started_at": started.isoformat(),
# # # #     }

# # # #     async with AsyncSessionLocal() as session:
# # # #         await session.execute(text(f'SET search_path TO "{schema_name}", public'))

# # # #         # ── SchedulerStatus row ───────────────────────────────────────────
# # # #         status_row = None
# # # #         try:
# # # #             status_result = await session.execute(
# # # #                 select(SchedulerStatus).where(SchedulerStatus.id == 1)
# # # #             )
# # # #             status_row = status_result.scalar_one_or_none()
# # # #             if status_row is None:
# # # #                 status_row = SchedulerStatus(id=1, isRunning=False)
# # # #                 session.add(status_row)
# # # #                 await session.flush()
# # # #             status_row.isRunning = True
# # # #             await session.commit()
# # # #         except Exception as _ss_exc:
# # # #             err_str = str(_ss_exc)
# # # #             if "does not exist" in err_str or "UndefinedTable" in err_str:
# # # #                 await session.rollback()
# # # #                 logger.warning("scheduler.tick.scheduler_status_missing", schema=schema_name)
# # # #             else:
# # # #                 raise

# # # #         sent = 0
# # # #         skipped = 0
# # # #         ended = started  # will be updated in finally

# # # #         try:
# # # #             # ── Step 1: fetch candidates via raw SQL (avoids asyncpg enum cast bug) ──
# # # #             # touchNumber <= 7 to include all 7 touches of the cadence.
# # # #             try:
# # # #                 await session.execute(text(f'SET search_path TO "{schema_name}", public'))
# # # #                 seq_id_result = await session.execute(
# # # #                     text(
# # # #                         'SELECT id FROM "Sequence" '
# # # #                         "WHERE status IN ('Scheduled', 'QaPassed') "
# # # #                         'AND "touchNumber" <= 7 '
# # # #                         'ORDER BY "createdAt" ASC '
# # # #                         'LIMIT 500'
# # # #                     )
# # # #                 )
# # # #                 seq_ids = [row[0] for row in seq_id_result.fetchall()]
# # # #             except Exception as table_exc:
# # # #                 err_str = str(table_exc)
# # # #                 if "does not exist" in err_str or "UndefinedTable" in err_str or "InFailedSQLTransaction" in err_str:
# # # #                     await session.rollback()
# # # #                     logger.warning("scheduler.tick.schema_not_ready", schema=schema_name, error=err_str[:200])
# # # #                     summary["skipped"] = 0
# # # #                     summary["sent"] = 0
# # # #                     return summary
# # # #                 raise

# # # #             if not seq_ids:
# # # #                 summary["candidates"] = 0
# # # #                 summary["sent"] = 0
# # # #                 summary["skipped"] = 0
# # # #                 return summary

# # # #             # Re-fetch as ORM objects for attribute access
# # # #             await session.execute(text(f'SET search_path TO "{schema_name}", public'))
# # # #             orm_result = await session.execute(
# # # #                 select(Sequence).where(Sequence.id.in_(seq_ids)).order_by(Sequence.createdAt.asc())
# # # #             )
# # # #             sequences = list(orm_result.scalars().all())
# # # #             summary["candidates"] = len(sequences)

# # # #             # Pre-load tenant-level MailBridge config fallback
# # # #             cfg_result = await session.execute(
# # # #                 select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
# # # #             )
# # # #             tenant_default_config = cfg_result.scalar_one_or_none()

# # # #             # Track per-campaign sent count within this tick to avoid over-sending
# # # #             campaign_sent_this_tick: dict[str, int] = {}

# # # #             for seq in sequences:
# # # #                 await session.execute(text(f'SET search_path TO "{schema_name}", public'))
# # # #                 try:
# # # #                     campaign_id = getattr(seq, "campaignId", None)
# # # #                     seq_owner = getattr(seq, "owner_user_id", None) or "system"

# # # #                     # ── Gate 2: prospect exists + has email ───────────────
# # # #                     prospect_result = await session.execute(
# # # #                         select(Prospect).where(Prospect.id == seq.prospectId)
# # # #                     )
# # # #                     prospect = prospect_result.scalar_one_or_none()

# # # #                     if prospect is None or not prospect.email:
# # # #                         skipped += 1
# # # #                         await write_skip_log(
# # # #                             session, run_id=None, sequence_id=seq.id,
# # # #                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                             skip_reason="no_email",
# # # #                             detail="Prospect not found or has no email address",
# # # #                         )
# # # #                         continue

# # # #                     # ── Gate 3: prospect suppression flag ─────────────────
# # # #                     if prospect.suppressed:
# # # #                         skipped += 1
# # # #                         await write_skip_log(
# # # #                             session, run_id=None, sequence_id=seq.id,
# # # #                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                             skip_reason="suppressed",
# # # #                             detail="Prospect suppression flag is set",
# # # #                         )
# # # #                         continue

# # # #                     # ── Gate 4: email suppression list ────────────────────
# # # #                     _email_lower = (prospect.email or "").strip().lower()
# # # #                     if _email_lower:
# # # #                         try:
# # # #                             _es = await session.execute(
# # # #                                 text('SELECT 1 FROM "EmailSuppression" WHERE email = :email LIMIT 1'),
# # # #                                 {"email": _email_lower},
# # # #                             )
# # # #                             if _es.fetchone() is not None:
# # # #                                 skipped += 1
# # # #                                 await write_skip_log(
# # # #                                     session, run_id=None, sequence_id=seq.id,
# # # #                                     campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                                     skip_reason="suppressed",
# # # #                                     detail=f"Email {_email_lower} is on suppression list",
# # # #                                 )
# # # #                                 continue
# # # #                         except Exception:  # noqa: BLE001 — table may not exist, fail open
# # # #                             pass

# # # #                     # ── Gate 5: business hours (NULL timezone = send anyway) ──
# # # #                     if prospect.timezone is not None and not _is_business_hours(started, prospect.timezone):
# # # #                         skipped += 1
# # # #                         await write_skip_log(
# # # #                             session, run_id=None, sequence_id=seq.id,
# # # #                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                             skip_reason="business_hours",
# # # #                             detail=f"Outside 9am-5pm in timezone {prospect.timezone}",
# # # #                         )
# # # #                         continue

# # # #                     # ── Gate 6: PARTIAL throttle ──────────────────────────
# # # #                     if (
# # # #                         prospect.enrichmentTier == EnrichmentTier.PARTIAL
# # # #                         and not _partial_throttle_passes(prospect.id, tick_bucket)
# # # #                     ):
# # # #                         skipped += 1
# # # #                         await write_skip_log(
# # # #                             session, run_id=None, sequence_id=seq.id,
# # # #                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                             skip_reason="warmup_cap",
# # # #                             detail="PARTIAL throttle hash did not pass for this tick bucket",
# # # #                         )
# # # #                         continue

# # # #                     # ── Gate 7: DNS verification (auto-tick only) ─────────
# # # #                     if campaign_id:
# # # #                         try:
# # # #                             _camp = (
# # # #                                 await session.execute(select(Campaign).where(Campaign.id == campaign_id))
# # # #                             ).scalar_one_or_none()
# # # #                             if _camp and getattr(_camp, "domainId", None):
# # # #                                 _dom = (
# # # #                                     await session.execute(select(Domain).where(Domain.id == _camp.domainId))
# # # #                                 ).scalar_one_or_none()
# # # #                                 if _dom is not None and _dom.lastChecked is not None:
# # # #                                     failing_dns = [
# # # #                                         name for name, ok in (
# # # #                                             ("SPF", _dom.spfStatus),
# # # #                                             ("DKIM", _dom.dkimStatus),
# # # #                                             ("DMARC", _dom.dmarcStatus),
# # # #                                         ) if not ok
# # # #                                     ]
# # # #                                     if failing_dns:
# # # #                                         skipped += 1
# # # #                                         await write_skip_log(
# # # #                                             session, run_id=None, sequence_id=seq.id,
# # # #                                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                                             skip_reason="send_error",
# # # #                                             detail=f"DNS failing: {', '.join(failing_dns)} for domain '{_dom.domainName}'",
# # # #                                         )
# # # #                                         continue
# # # #                         except Exception:  # noqa: BLE001 — fail open
# # # #                             pass

# # # #                     # ── Gate 8: daily cap check (warmup week OR env default) ──
# # # #                     effective_cap, cap_source = await _resolve_daily_cap(session, campaign_id)
# # # #                     already_sent = await _count_sent_today(session, campaign_id)
# # # #                     within_tick = campaign_sent_this_tick.get(campaign_id or "__none__", 0)

# # # #                     if (already_sent + within_tick) >= effective_cap:
# # # #                         skipped += 1
# # # #                         logger.info(
# # # #                             "scheduler.sequence.quota_exceeded",
# # # #                             schema=schema_name, sequence_id=seq.id,
# # # #                             cap=effective_cap, source=cap_source,
# # # #                             sent_today=already_sent + within_tick,
# # # #                         )
# # # #                         await write_skip_log(
# # # #                             session, run_id=None, sequence_id=seq.id,
# # # #                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                             skip_reason="quota_exceeded",
# # # #                             detail=f"Daily cap {effective_cap} reached ({already_sent + within_tick} sent, source={cap_source})",
# # # #                         )
# # # #                         continue

# # # #                     # ── Resolve MailBridge config ─────────────────────────
# # # #                     config = await _resolve_mailbridge_config(session, seq_owner if seq_owner != "system" else None)
# # # #                     if config is None:
# # # #                         config = tenant_default_config

# # # #                     # ── Send ─────────────────────────────────────────────
# # # #                     msg_id = await _send_via_mailbridge(session, config, seq, user_id=seq_owner)

# # # #                     await session.execute(
# # # #                         text(
# # # #                             'UPDATE "Sequence" SET status = \'Sent\', '
# # # #                             '"sentAt" = :sent_at, "mailBridgeMessageId" = :msg_id '
# # # #                             "WHERE id = :seq_id"
# # # #                         ),
# # # #                         {"sent_at": datetime.now(timezone.utc), "msg_id": msg_id, "seq_id": seq.id},
# # # #                     )
# # # #                     sent += 1

# # # #                     # Track within-tick count
# # # #                     key = campaign_id or "__none__"
# # # #                     campaign_sent_this_tick[key] = campaign_sent_this_tick.get(key, 0) + 1

# # # #                     # Daily sent log
# # # #                     if campaign_id:
# # # #                         await upsert_daily_sent(
# # # #                             session, campaign_id=campaign_id, sent_date=started.date(), increment=1
# # # #                         )

# # # #                 except Exception as exc:  # noqa: BLE001 — per-sequence isolation
# # # #                     skipped += 1
# # # #                     logger.warning("scheduler.sequence.send_failed", schema=schema_name, sequence_id=seq.id, error=str(exc))
# # # #                     await write_skip_log(
# # # #                         session, run_id=None, sequence_id=seq.id,
# # # #                         campaign_id=getattr(seq, "campaignId", None),
# # # #                         prospect_id=getattr(seq, "prospectId", None),
# # # #                         skip_reason="send_error", detail=str(exc)[:500],
# # # #                     )

# # # #             await session.commit()

# # # #         finally:
# # # #             ended = datetime.now(timezone.utc)
# # # #             if status_row is not None:
# # # #                 try:
# # # #                     await session.execute(text(f'SET search_path TO "{schema_name}", public'))
# # # #                     status_row.isRunning = False
# # # #                     status_row.lastTickAt = started
# # # #                     status_row.sentSinceLastTick = sent
# # # #                     status_row.skippedSinceLastTick = skipped
# # # #                     status_row.nextTickAt = started + timedelta(seconds=settings.SCHEDULER_TICK_SECONDS)
# # # #                     await session.commit()
# # # #                 except Exception:  # noqa: BLE001
# # # #                     await session.rollback()

# # # #     summary["sent"] = sent
# # # #     summary["skipped"] = skipped
# # # #     summary["ended_at"] = ended.isoformat()
# # # #     summary["duration_ms"] = int((ended - started).total_seconds() * 1000)
# # # #     return summary


# # # # async def run_tick_all_tenants() -> dict[str, Any]:
# # # #     """Run a tick across every ACTIVE tenant schema."""
# # # #     summary: dict[str, Any] = {"tenants": 0, "sent": 0, "skipped": 0, "failed_tenants": 0}

# # # #     schemas: list[str] = []
# # # #     try:
# # # #         async with engine.connect() as conn:
# # # #             result = await conn.execute(
# # # #                 text("SELECT schema_name FROM public.tenants WHERE status='ACTIVE' AND deleted_at IS NULL")
# # # #             )
# # # #             schemas = [row[0] for row in result.fetchall()]
# # # #     except Exception as exc:  # noqa: BLE001
# # # #         if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
# # # #             raise
# # # #         logger.warning("scheduler.tick.no_tenants_table", error=str(exc))

# # # #     summary["tenant_count"] = len(schemas)
# # # #     for schema in schemas:
# # # #         try:
# # # #             tick_result = await run_tick(schema)
# # # #             summary["tenants"] += 1
# # # #             summary["sent"] += tick_result.get("sent", 0)
# # # #             summary["skipped"] += tick_result.get("skipped", 0)
# # # #         except Exception as exc:  # noqa: BLE001
# # # #             summary["failed_tenants"] += 1
# # # #             logger.error("scheduler.tenant_failed", schema=schema, error=str(exc), exc_info=True)

# # # #     return summary


# # # # # ═══════════════════════════════════════════════════════════════════════════
# # # # # SCHEDULER SERVICE  (manual tick + trigger + status + runs)
# # # # # ═══════════════════════════════════════════════════════════════════════════

# # # # class SchedulerService:
# # # #     """Backwards-compatible wrapper for the Scheduler page endpoints."""

# # # #     def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
# # # #         self._mailbridge = mailbridge or MailBridgeService()

# # # #     async def get_status(self, db: AsyncSession) -> SchedulerStatus:
# # # #         """Return the singleton SchedulerStatus row, creating it if absent."""
# # # #         result = await db.execute(select(SchedulerStatus).where(SchedulerStatus.id == 1))
# # # #         status = result.scalar_one_or_none()
# # # #         if status is None:
# # # #             status = SchedulerStatus(id=1, isRunning=False)
# # # #             db.add(status)
# # # #             await db.commit()
# # # #             status = await db.get(SchedulerStatus, status.id)
# # # #         return status

# # # #     async def manual_tick(
# # # #         self,
# # # #         db: AsyncSession,
# # # #         *,
# # # #         tenant_scoped: bool = True,
# # # #         max_send: int = 50,
# # # #     ) -> ManualTickResponse:
# # # #         """Manual tick — sends immediately with minimal gates.

# # # #         Gates ENFORCED (always):
# # # #           ✅ prospect exists + has email     (legal / deliverability)
# # # #           ✅ email not suppressed             (legal compliance)
# # # #           ✅ daily cap (warmup week or env)   (warmup cap is sacred)

# # # #         Gates SKIPPED (by design for manual sends):
# # # #           ✗ business hours   (manual = operator wants to send NOW)
# # # #           ✗ PARTIAL throttle (not relevant for manual trigger)
# # # #           ✗ DNS verification (operator override — they know what they're doing)

# # # #         Quota logic (same as auto-tick):
# # # #           Campaign has verified domain with warmup configured
# # # #             → warmup week cap (week 1=10 ... week 7=500)
# # # #           Otherwise
# # # #             → settings.DEFAULT_USER_DAILY_EMAIL_QUOTA (from .env)
# # # #         """
# # # #         started = datetime.now(timezone.utc)
# # # #         settings = get_settings()
# # # #         sent = 0
# # # #         skipped = 0

# # # #         # Resolve tenant schema from session search_path
# # # #         schema_name = "public"
# # # #         try:
# # # #             _sr = await db.execute(text("SELECT current_schema()"))
# # # #             _sc = _sr.scalar()
# # # #             if _sc and _sc != "public":
# # # #                 schema_name = _sc
# # # #             else:
# # # #                 _sr2 = await db.execute(text("SHOW search_path"))
# # # #                 _sp = (_sr2.scalar() or "").replace('"', '')
# # # #                 for part in _sp.split(","):
# # # #                     part = part.strip()
# # # #                     if part and part not in ("public", "$user"):
# # # #                         schema_name = part
# # # #                         break
# # # #         except Exception:  # noqa: BLE001
# # # #             pass

# # # #         # Mark running
# # # #         try:
# # # #             await db.execute(
# # # #                 text('UPDATE "SchedulerStatus" SET "isRunning" = true, "updatedAt" = now() WHERE id = 1')
# # # #             )
# # # #             await db.commit()
# # # #         except Exception:  # noqa: BLE001
# # # #             await db.rollback()

# # # #         # Tenant-level MailBridge config fallback
# # # #         try:
# # # #             _cfg_r = await db.execute(
# # # #                 select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
# # # #             )
# # # #             tenant_default_config = _cfg_r.scalar_one_or_none()
# # # #         except Exception:  # noqa: BLE001
# # # #             tenant_default_config = None

# # # #         # Fetch candidates — raw SQL to avoid asyncpg enum cast bug
# # # #         try:
# # # #             await db.execute(text(f'SET search_path TO "{schema_name}", public'))
# # # #             seq_id_result = await db.execute(
# # # #                 text(
# # # #                     'SELECT id FROM "Sequence" '
# # # #                     "WHERE status IN ('Scheduled', 'QaPassed') "
# # # #                     'AND "touchNumber" <= 7 '
# # # #                     'ORDER BY "createdAt" ASC '
# # # #                     'LIMIT :limit'
# # # #                 ),
# # # #                 {"limit": max_send},
# # # #             )
# # # #             seq_ids = [row[0] for row in seq_id_result.fetchall()]
# # # #         except Exception as exc:  # noqa: BLE001
# # # #             logger.warning("scheduler.manual_tick.fetch_failed", error=str(exc)[:200])
# # # #             seq_ids = []

# # # #         if seq_ids:
# # # #             await db.execute(text(f'SET search_path TO "{schema_name}", public'))
# # # #             orm_result = await db.execute(
# # # #                 select(Sequence).where(Sequence.id.in_(seq_ids)).order_by(Sequence.createdAt.asc())
# # # #             )
# # # #             sequences = list(orm_result.scalars().all())
# # # #         else:
# # # #             sequences = []

# # # #         # Track per-campaign sent count within this tick
# # # #         campaign_sent_this_tick: dict[str, int] = {}

# # # #         for seq in sequences:
# # # #             campaign_id = getattr(seq, "campaignId", None)
# # # #             seq_owner = getattr(seq, "owner_user_id", None) or "system"

# # # #             try:
# # # #                 await db.execute(text(f'SET search_path TO "{schema_name}", public'))

# # # #                 # ── Gate: prospect exists + has email ─────────────────────
# # # #                 prospect_result = await db.execute(
# # # #                     select(Prospect).where(Prospect.id == seq.prospectId)
# # # #                 )
# # # #                 prospect = prospect_result.scalar_one_or_none()

# # # #                 if prospect is None or not prospect.email:
# # # #                     skipped += 1
# # # #                     await write_skip_log(
# # # #                         db, run_id=None, sequence_id=seq.id,
# # # #                         campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                         skip_reason="no_email",
# # # #                         detail="Prospect not found or has no email address",
# # # #                     )
# # # #                     continue

# # # #                 # ── Gate: suppression ─────────────────────────────────────
# # # #                 if prospect.suppressed:
# # # #                     skipped += 1
# # # #                     await write_skip_log(
# # # #                         db, run_id=None, sequence_id=seq.id,
# # # #                         campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                         skip_reason="suppressed",
# # # #                         detail="Prospect suppression flag is set",
# # # #                     )
# # # #                     continue

# # # #                 _email_lower = (prospect.email or "").strip().lower()
# # # #                 if _email_lower:
# # # #                     try:
# # # #                         _es = await db.execute(
# # # #                             text('SELECT 1 FROM "EmailSuppression" WHERE email = :email LIMIT 1'),
# # # #                             {"email": _email_lower},
# # # #                         )
# # # #                         if _es.fetchone() is not None:
# # # #                             skipped += 1
# # # #                             await write_skip_log(
# # # #                                 db, run_id=None, sequence_id=seq.id,
# # # #                                 campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                                 skip_reason="suppressed",
# # # #                                 detail=f"Email {_email_lower} is on suppression list",
# # # #                             )
# # # #                             continue
# # # #                     except Exception:  # noqa: BLE001 — fail open
# # # #                         pass

# # # #                 # ── Gate: daily cap (warmup week OR env default) ──────────
# # # #                 effective_cap, cap_source = await _resolve_daily_cap(db, campaign_id)
# # # #                 already_sent = await _count_sent_today(db, campaign_id)
# # # #                 within_tick = campaign_sent_this_tick.get(campaign_id or "__none__", 0)

# # # #                 if (already_sent + within_tick) >= effective_cap:
# # # #                     skipped += 1
# # # #                     logger.info(
# # # #                         "scheduler.manual_tick.daily_cap_reached",
# # # #                         campaign_id=campaign_id, cap=effective_cap,
# # # #                         source=cap_source, sent_today=already_sent + within_tick,
# # # #                     )
# # # #                     await write_skip_log(
# # # #                         db, run_id=None, sequence_id=seq.id,
# # # #                         campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                         skip_reason="quota_exceeded",
# # # #                         detail=f"Daily cap {effective_cap} reached ({already_sent + within_tick} sent, source={cap_source})",
# # # #                     )
# # # #                     continue

# # # #                 # ── Resolve MailBridge config ─────────────────────────────
# # # #                 config = await _resolve_mailbridge_config(db, seq_owner if seq_owner != "system" else None)
# # # #                 if config is None:
# # # #                     config = tenant_default_config

# # # #                 # ── Send ─────────────────────────────────────────────────
# # # #                 msg_id = await _send_via_mailbridge(db, config, seq, user_id=seq_owner)

# # # #                 await db.execute(
# # # #                     text(
# # # #                         'UPDATE "Sequence" SET status = \'Sent\', '
# # # #                         '"sentAt" = :sent_at, "mailBridgeMessageId" = :msg_id '
# # # #                         "WHERE id = :seq_id"
# # # #                     ),
# # # #                     {"sent_at": datetime.now(timezone.utc), "msg_id": msg_id, "seq_id": seq.id},
# # # #                 )
# # # #                 await db.commit()
# # # #                 sent += 1

# # # #                 key = campaign_id or "__none__"
# # # #                 campaign_sent_this_tick[key] = campaign_sent_this_tick.get(key, 0) + 1

# # # #                 if campaign_id:
# # # #                     await upsert_daily_sent(
# # # #                         db, campaign_id=campaign_id, sent_date=started.date(), increment=1
# # # #                     )

# # # #             except Exception as exc:  # noqa: BLE001 — per-sequence isolation
# # # #                 skipped += 1
# # # #                 logger.warning("scheduler.manual_tick.seq_failed", sequence_id=seq.id, error=str(exc)[:300])
# # # #                 await write_skip_log(
# # # #                     db, run_id=None, sequence_id=seq.id,
# # # #                     campaign_id=campaign_id, prospect_id=seq.prospectId,
# # # #                     skip_reason="send_error", detail=str(exc)[:500],
# # # #                 )
# # # #                 try:
# # # #                     await db.rollback()
# # # #                 except Exception:  # noqa: BLE001
# # # #                     pass

# # # #         # Update SchedulerStatus
# # # #         try:
# # # #             await db.execute(text(f'SET search_path TO "{schema_name}", public'))
# # # #             await db.execute(
# # # #                 text(
# # # #                     'UPDATE "SchedulerStatus" SET '
# # # #                     '"isRunning" = false, "lastTickAt" = :last, "nextTickAt" = :next, '
# # # #                     '"sentSinceLastTick" = :sent, "skippedSinceLastTick" = :skipped, '
# # # #                     '"updatedAt" = now() WHERE id = 1'
# # # #                 ),
# # # #                 {
# # # #                     "last": started,
# # # #                     "next": started + timedelta(seconds=settings.SCHEDULER_TICK_SECONDS),
# # # #                     "sent": sent,
# # # #                     "skipped": skipped,
# # # #                 },
# # # #             )
# # # #             await db.commit()
# # # #         except Exception as exc:  # noqa: BLE001
# # # #             logger.warning("scheduler.manual_tick.status_update_failed", error=str(exc)[:200])

# # # #         duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
# # # #         logger.info("scheduler.manual_tick.complete", sent=sent, skipped=skipped, duration_ms=duration_ms)
# # # #         return ManualTickResponse(sent=sent, skipped=skipped, durationMs=duration_ms, tickedAt=started)

# # # #     async def trigger(self, db: AsyncSession) -> "TriggerResponse":
# # # #         """Trigger an immediate scheduler tick via Celery or synchronous fallback."""
# # # #         from app.schemas.scheduler import TriggerResponse

# # # #         run = None
# # # #         try:
# # # #             _run_obj = SchedulerRun(status="running")
# # # #             db.add(_run_obj)
# # # #             await db.commit()
# # # #             run = await db.get(SchedulerRun, _run_obj.id)
# # # #         except Exception as _exc:  # noqa: BLE001
# # # #             await db.rollback()
# # # #             logger.warning("scheduler.trigger.run_log_skipped", error=str(_exc)[:200])

# # # #         try:
# # # #             from app.worker.celery_app import celery_app
# # # #             if celery_app is not None:
# # # #                 result = celery_app.send_task("autopilot.run_pipeline", kwargs={"schema_name": "current"})
# # # #                 if run is not None:
# # # #                     run.status = "completed"
# # # #                     run.completedAt = datetime.now(timezone.utc)
# # # #                     await db.commit()
# # # #                 return TriggerResponse(triggered=True, message="Scheduler triggered via Celery.", runId=result.id)
# # # #         except Exception as exc:  # noqa: BLE001
# # # #             logger.warning("scheduler.trigger.celery_failed", error=str(exc))

# # # #         try:
# # # #             tick_result = await self.manual_tick(db, tenant_scoped=True, max_send=50)
# # # #             if run is not None:
# # # #                 run.status = "completed"
# # # #                 run.sent = tick_result.sent
# # # #                 run.skipped = tick_result.skipped
# # # #                 run.durationMs = tick_result.durationMs
# # # #                 run.completedAt = datetime.now(timezone.utc)
# # # #                 await db.commit()
# # # #             return TriggerResponse(
# # # #                 triggered=True,
# # # #                 message="Scheduler tick completed synchronously.",
# # # #                 runId=run.id if run else None,
# # # #             )
# # # #         except Exception as exc:  # noqa: BLE001
# # # #             if run is not None:
# # # #                 run.status = "failed"
# # # #                 run.error = str(exc)
# # # #                 run.completedAt = datetime.now(timezone.utc)
# # # #                 await db.commit()
# # # #             return TriggerResponse(triggered=False, message=f"Scheduler tick failed: {exc}", runId=run.id if run else None)

# # # #     async def list_runs(self, db: AsyncSession, *, limit: int = 20, offset: int = 0) -> "SchedulerRunsListResponse":
# # # #         """Return recent scheduler run log entries, newest first."""
# # # #         from app.schemas.scheduler import SchedulerRunResponse, SchedulerRunsListResponse
# # # #         from sqlalchemy import func as sa_func

# # # #         try:
# # # #             count_result = await db.execute(select(sa_func.count()).select_from(SchedulerRun))
# # # #             total = count_result.scalar() or 0
# # # #             result = await db.execute(
# # # #                 select(SchedulerRun).order_by(SchedulerRun.startedAt.desc()).limit(limit).offset(offset)
# # # #             )
# # # #             rows = list(result.scalars().all())
# # # #             items = [SchedulerRunResponse.model_validate(r) for r in rows]
# # # #             return SchedulerRunsListResponse(items=items, total=total)
# # # #         except Exception as exc:  # noqa: BLE001
# # # #             err_str = str(exc)
# # # #             if "UndefinedTableError" in err_str or "does not exist" in err_str or "undefined_table" in err_str.lower():
# # # #                 await db.rollback()
# # # #                 logger.warning("scheduler.list_runs.table_missing", error=err_str[:200])
# # # #                 from app.schemas.scheduler import SchedulerRunsListResponse
# # # #                 return SchedulerRunsListResponse(items=[], total=0)
# # # #             raise


# # # # __all__ = [
# # # #     "SchedulerService",
# # # #     "get_scheduler",
# # # #     "run_tick",
# # # #     "run_tick_all_tenants",
# # # #     "_is_business_hours",
# # # #     "_partial_throttle_passes",
# # # #     "_resolve_mailbridge_config",
# # # #     "_send_via_mailbridge",
# # # #     "_async_tick_wrapper",
# # # #     "_resolve_daily_cap",
# # # #     "advance_domain_warmup",
# # # # ]

# # # """
# # # scheduler/service.py — Outrena email scheduler (auto + manual tick).

# # # ────────────────────────────────────────────────────────────────────────────
# # # QUOTA LOGIC (identical for auto and manual tick)
# # # ────────────────────────────────────────────────────────────────────────────

# # # The daily send cap is resolved in this priority order for every sequence:

# # #   1. Campaign has a domain linked (Campaign.domainId set)?
# # #         AND that domain has been DNS-verified (lastChecked IS NOT NULL)?
# # #         AND all three DNS records pass (SPF + DKIM + DMARC)?
# # #      → USE WARMUP WEEK CAP:
# # #           week 1 =  10/day
# # #           week 2 =  30/day
# # #           week 3 =  50/day
# # #           week 4 = 100/day
# # #           week 5 = 200/day
# # #           week 6 = 350/day
# # #           week 7 = 500/day
# # #           week 8+ = Domain.dailySendLimit (or 10 000 if not explicitly set >10)

# # #   2. Otherwise (no domain, domain unverified, or DNS failing)
# # #      → USE ENV DEFAULT: settings.DEFAULT_USER_DAILY_EMAIL_QUOTA (default 100)

# # # ────────────────────────────────────────────────────────────────────────────
# # # GATES: AUTO TICK vs MANUAL TICK
# # # ────────────────────────────────────────────────────────────────────────────

# # #   Gate                    Auto tick    Manual tick
# # #   ──────────────────────  ─────────    ───────────
# # #   No email / suppressed   ✅ checked   ✅ checked   (always wrong to send)
# # #   Email suppression list  ✅ checked   ✅ checked   (legal compliance)
# # #   Business hours          ✅ checked   ✗ skipped   (manual = send now)
# # #   PARTIAL throttle        ✅ checked   ✗ skipped   (not relevant)
# # #   Domain quota (above)    ✅ checked   ✅ checked   (warmup cap is sacred)
# # #   DNS verification        ✅ checked   ✗ skipped   (operator override)

# # # ────────────────────────────────────────────────────────────────────────────
# # # BUSINESS HOURS LOGIC
# # # ────────────────────────────────────────────────────────────────────────────

# # #   prospect.timezone IS SET  → enforce 9am–5pm Mon–Fri in that timezone
# # #   prospect.timezone IS NULL → SEND ANYWAY (unknown location = no restriction)
# # #                                Do NOT default to America/New_York — that
# # #                                assumption is wrong for non-US prospects.

# # # ────────────────────────────────────────────────────────────────────────────
# # # """
# # # from __future__ import annotations

# # # import asyncio
# # # import hashlib
# # # import zoneinfo
# # # from datetime import date, datetime, time, timedelta, timezone
# # # from typing import Any

# # # import httpx
# # # import structlog
# # # from apscheduler.schedulers.asyncio import AsyncIOScheduler
# # # from sqlalchemy import select, text
# # # from sqlalchemy.ext.asyncio import AsyncSession

# # # from app.core.config import get_settings
# # # from app.core.database import AsyncSessionLocal, engine
# # # from app.models.campaign_models import Campaign, Sequence
# # # from app.models.config_models import Domain, MailBridgeConfig
# # # from app.models.enums import EmailStatus, EnrichmentTier
# # # from app.models.phase3_models import SchedulerRun, SchedulerStatus
# # # from app.models.prospect_models import Prospect
# # # from app.schemas.scheduler import ManualTickResponse
# # # from app.features.mailbridge.service import MailBridgeService
# # # from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
# # # from app.features.mailbridge.reply_poller import register_reply_poll_job
# # # from app.features.scheduler.query_service import write_skip_log, upsert_daily_sent
# # # from app.models.base import _generate_cuid

# # # logger = structlog.get_logger(__name__)

# # # # ── Module-global singleton scheduler ──────────────────────────────────────
# # # _scheduler: AsyncIOScheduler | None = None

# # # # ── Warmup ramp table ──────────────────────────────────────────────────────
# # # # Week 1=10, 2=30, 3=50, 4=100, 5=200, 6=350, 7=500
# # # _WARMUP_RAMP: dict[int, int] = {1: 10, 2: 30, 3: 50, 4: 100, 5: 200, 6: 350, 7: 500}
# # # WARMING_SCHEDULE = [10, 30, 50, 100, 200, 350, 500]  # exported for UI display


# # # # ═══════════════════════════════════════════════════════════════════════════
# # # # SCHEDULER SINGLETON
# # # # ═══════════════════════════════════════════════════════════════════════════

# # # def get_scheduler() -> AsyncIOScheduler:
# # #     """Return the AsyncIOScheduler singleton."""
# # #     global _scheduler
# # #     if _scheduler is None:
# # #         settings = get_settings()
# # #         _scheduler = AsyncIOScheduler()
# # #         _scheduler.add_job(
# # #             _async_tick_wrapper,
# # #             "interval",
# # #             seconds=settings.SCHEDULER_TICK_SECONDS,
# # #             id="outrena_tick",
# # #             max_instances=1,
# # #             coalesce=True,
# # #             replace_existing=True,
# # #         )
# # #         _scheduler.add_job(
# # #             _async_cost_rollup_wrapper,
# # #             "cron",
# # #             hour=2,
# # #             minute=0,
# # #             id="outrena_cost_rollup",
# # #             max_instances=1,
# # #             coalesce=True,
# # #             replace_existing=True,
# # #         )
# # #         from app.features.mailbridge.reply_poller import register_reply_poll_job
# # #         register_reply_poll_job(_scheduler)
# # #         logger.info(
# # #             "scheduler.registered",
# # #             tick_seconds=settings.SCHEDULER_TICK_SECONDS,
# # #             job_id="outrena_tick",
# # #         )
# # #     return _scheduler


# # # async def _async_tick_wrapper() -> None:
# # #     """Top-level tick wrapper — catches every exception so a single
# # #     tenant failure never kills the scheduler."""
# # #     try:
# # #         summary = await run_tick_all_tenants()
# # #         logger.info("scheduler.tick.complete", **summary)
# # #     except Exception as exc:  # noqa: BLE001
# # #         logger.error("scheduler.tick.fatal", error=str(exc), exc_info=True)


# # # async def _async_cost_rollup_wrapper() -> None:
# # #     """Nightly job — materialise CostSummary rows for all active tenants."""
# # #     from app.core.database import AsyncSessionLocal
# # #     from app.features.usage.service import UsageService
# # #     from datetime import date as _date

# # #     period = _date.today().strftime("%Y-%m")
# # #     total = 0
# # #     errors = 0
# # #     try:
# # #         async with AsyncSessionLocal() as db:
# # #             from sqlalchemy import text as _text
# # #             try:
# # #                 result = await db.execute(
# # #                     _text("SELECT slug FROM public.tenants WHERE status = 'ACTIVE' AND deleted_at IS NULL")
# # #                 )
# # #                 slugs = [row[0] for row in result.all()]
# # #             except Exception as exc:  # noqa: BLE001
# # #                 if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
# # #                     raise
# # #                 logger.warning("scheduler.cost_rollup.no_tenants_table", error=str(exc))
# # #                 slugs = []

# # #         for slug in slugs:
# # #             try:
# # #                 svc = UsageService()
# # #                 written = await svc.rebuild_cost_summaries(slug, period)
# # #                 total += written
# # #             except Exception as exc:  # noqa: BLE001
# # #                 errors += 1
# # #                 logger.warning("scheduler.cost_rollup.tenant_failed", tenant=slug, error=str(exc))

# # #         logger.info(
# # #             "scheduler.cost_rollup.complete",
# # #             period=period,
# # #             tenants=len(slugs),
# # #             rows_written=total,
# # #             errors=errors,
# # #         )

# # #         # FR-038: nightly warm-up week advancement
# # #         advanced_total = 0
# # #         for slug in slugs:
# # #             try:
# # #                 async with AsyncSessionLocal() as db:
# # #                     from sqlalchemy import text as _text
# # #                     await db.execute(_text(f'SET search_path TO "tenant_{slug}", public'))
# # #                     advanced_total += await advance_domain_warmup(db)
# # #                     await db.commit()
# # #             except Exception as exc:  # noqa: BLE001
# # #                 logger.warning("scheduler.warmup_advance.tenant_failed", tenant=slug, error=str(exc))
# # #         if advanced_total:
# # #             logger.info("scheduler.warmup_advance.complete", domains=advanced_total)

# # #     except Exception as exc:  # noqa: BLE001
# # #         logger.error("scheduler.cost_rollup.fatal", error=str(exc), exc_info=True)


# # # # ═══════════════════════════════════════════════════════════════════════════
# # # # DOMAIN WARMUP HELPERS
# # # # ═══════════════════════════════════════════════════════════════════════════

# # # def _warmup_effective_cap(dom: Domain) -> int:
# # #     """Return the effective daily send cap for a domain.

# # #     - warmingWeek 1–7  → ramp cap from _WARMUP_RAMP
# # #     - warmingWeek 8+   → Domain.dailySendLimit (treat ≤10 as not configured → 10 000)
# # #     - warmingWeek 0    → not started → use dailySendLimit (or 10 000)
# # #     """
# # #     week = int(getattr(dom, "warmingWeek", 0) or 0)
# # #     raw_limit = int(getattr(dom, "dailySendLimit", 0) or 0)
# # #     # dailySendLimit defaults to 10 in the model — treat ≤10 as "not explicitly set"
# # #     base = raw_limit if raw_limit > 10 else 10_000
# # #     if 1 <= week <= 7:
# # #         return min(base, _WARMUP_RAMP[week])
# # #     return base


# # # async def advance_domain_warmup(db: AsyncSession) -> int:
# # #     """Advance warmingWeek for domains warmed ≥7 days. Called nightly."""
# # #     result = await db.execute(
# # #         text(
# # #             'UPDATE "Domain" SET '
# # #             '  "warmingWeek" = "warmingWeek" + 1, '
# # #             '  "updatedAt" = now() '
# # #             'WHERE "warmingWeek" BETWEEN 1 AND 7 '
# # #             "  AND \"updatedAt\" < now() - interval '7 days'"
# # #         )
# # #     )
# # #     return result.rowcount or 0


# # # # ═══════════════════════════════════════════════════════════════════════════
# # # # QUOTA RESOLUTION  (shared by auto-tick and manual-tick)
# # # # ═══════════════════════════════════════════════════════════════════════════

# # # async def _resolve_daily_cap(
# # #     db: AsyncSession,
# # #     campaign_id: str | None,
# # # ) -> tuple[int, str]:
# # #     """Return (effective_daily_cap, source_label).

# # #     source_label is one of:
# # #       "warmup_week_{N}"  — domain warmup ramp cap
# # #       "domain_limit"     — post-warmup domain dailySendLimit
# # #       "env_default"      — settings.DEFAULT_USER_DAILY_EMAIL_QUOTA

# # #     Logic:
# # #       Campaign has domainId AND domain has been DNS-verified
# # #       AND all DNS records pass → warmup cap governs.
# # #       Otherwise → env default.
# # #     """
# # #     settings = get_settings()
# # #     env_cap = settings.DEFAULT_USER_DAILY_EMAIL_QUOTA

# # #     if not campaign_id:
# # #         return env_cap, "env_default"

# # #     try:
# # #         camp = (
# # #             await db.execute(select(Campaign).where(Campaign.id == campaign_id))
# # #         ).scalar_one_or_none()

# # #         if camp is None or not getattr(camp, "domainId", None):
# # #             return env_cap, "env_default"

# # #         dom = (
# # #             await db.execute(select(Domain).where(Domain.id == camp.domainId))
# # #         ).scalar_one_or_none()

# # #         if dom is None:
# # #             return env_cap, "env_default"

# # #         # Domain must have been verified at least once
# # #         if dom.lastChecked is None:
# # #             return env_cap, "env_default"

# # #         # All three DNS records must pass
# # #         if not (dom.spfStatus and dom.dkimStatus and dom.dmarcStatus):
# # #             return env_cap, "env_default"

# # #         # Domain is verified — warmup cap governs
# # #         week = int(getattr(dom, "warmingWeek", 0) or 0)
# # #         cap = _warmup_effective_cap(dom)
# # #         source = f"warmup_week_{week}" if 1 <= week <= 7 else "domain_limit"
# # #         return cap, source

# # #     except Exception as exc:  # noqa: BLE001 — fail open to env default
# # #         logger.warning("scheduler.quota_resolve.failed", error=str(exc)[:200])
# # #         return env_cap, "env_default"


# # # async def _count_sent_today(db: AsyncSession, campaign_id: str | None) -> int:
# # #     """Count emails sent today for this campaign from SchedulerDailySent,
# # #     falling back to Sequence.sentAt aggregate if table doesn't exist."""
# # #     if not campaign_id:
# # #         return 0
# # #     try:
# # #         result = await db.execute(
# # #             text(
# # #                 'SELECT "sentCount" FROM "SchedulerDailySent" '
# # #                 'WHERE "campaignId" = :cid AND "sentDate" = CURRENT_DATE'
# # #             ),
# # #             {"cid": campaign_id},
# # #         )
# # #         row = result.fetchone()
# # #         return int(row[0]) if row else 0
# # #     except Exception:  # noqa: BLE001 — table may not exist
# # #         pass
# # #     # Fallback: count directly from Sequence
# # #     try:
# # #         result = await db.execute(
# # #             text(
# # #                 'SELECT COUNT(*) FROM "Sequence" '
# # #                 'WHERE "campaignId" = :cid '
# # #                 "AND \"sentAt\" >= date_trunc('day', now() AT TIME ZONE 'UTC')"
# # #             ),
# # #             {"cid": campaign_id},
# # #         )
# # #         return int(result.scalar() or 0)
# # #     except Exception:  # noqa: BLE001
# # #         return 0


# # # # ═══════════════════════════════════════════════════════════════════════════
# # # # BUSINESS HOURS  (auto-tick only)
# # # # ═══════════════════════════════════════════════════════════════════════════

# # # def _is_business_hours(now: datetime, tz_name: str | None) -> bool:
# # #     """Return True iff sending is permitted for this prospect right now.

# # #     Rules:
# # #       - prospect.timezone is NULL  → return True (unknown location = no gate)
# # #       - prospect.timezone is set   → enforce 9am–5pm Mon–Fri in that tz
# # #       - timezone string invalid    → return True (fail open, don't block)

# # #     We deliberately do NOT default NULL to America/New_York because that
# # #     assumption is wrong for non-US prospects (e.g. India, UK, APAC).
# # #     """
# # #     if tz_name is None:
# # #         # Timezone unknown — send immediately, don't guess
# # #         return True

# # #     try:
# # #         tz = zoneinfo.ZoneInfo(tz_name)
# # #         local = now.astimezone(tz)
# # #     except Exception:  # noqa: BLE001 — invalid tz string, fail open
# # #         return True

# # #     if local.weekday() >= 5:  # Sat=5, Sun=6
# # #         return False
# # #     return time(9, 0) <= local.time() <= time(17, 0)


# # # # ═══════════════════════════════════════════════════════════════════════════
# # # # PARTIAL THROTTLE  (auto-tick only)
# # # # ═══════════════════════════════════════════════════════════════════════════

# # # def _partial_throttle_passes(prospect_id: str, tick_bucket: int) -> bool:
# # #     """Deterministic hash throttle for PARTIAL-enrichment prospects."""
# # #     settings = get_settings()
# # #     cap = settings.SCHEDULER_PARTIAL_PER_TICK_CAP
# # #     hash_input = f"{prospect_id}:{tick_bucket}"
# # #     bucket = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16) % 100
# # #     return bucket < cap


# # # # ═══════════════════════════════════════════════════════════════════════════
# # # # MAILBRIDGE CONFIG RESOLUTION
# # # # ═══════════════════════════════════════════════════════════════════════════

# # # async def _resolve_mailbridge_config(
# # #     db: AsyncSession, user_id: str | None
# # # ) -> MailBridgeConfig | None:
# # #     """Resolve MailBridgeConfig: per-user first, then tenant fallback."""
# # #     has_owner_col = hasattr(MailBridgeConfig, "owner_user_id")
# # #     if user_id and has_owner_col:
# # #         try:
# # #             result = await db.execute(
# # #                 select(MailBridgeConfig)
# # #                 .where(MailBridgeConfig.isActive.is_(True))
# # #                 .where(getattr(MailBridgeConfig, "owner_user_id") == user_id)
# # #                 .limit(1)
# # #             )
# # #             cfg = result.scalar_one_or_none()
# # #             if cfg is not None:
# # #                 return cfg
# # #         except Exception as exc:  # noqa: BLE001
# # #             logger.warning("scheduler.mailbridge.per_user_lookup_failed", user_id=user_id, error=str(exc))

# # #     result = await db.execute(
# # #         select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
# # #     )
# # #     return result.scalar_one_or_none()


# # # # ═══════════════════════════════════════════════════════════════════════════
# # # # HTML HELPERS
# # # # ═══════════════════════════════════════════════════════════════════════════

# # # def _is_html_body(body: str | None) -> bool:
# # #     if not body:
# # #         return False
# # #     s = body.lstrip()
# # #     return s.startswith("<") and any(
# # #         marker in body
# # #         for marker in ("</p>", "</h", "<br", "</ul>", "</ol>", "</li>", "</strong>", "</em>")
# # #     )


# # # def _strip_html_text(html: str) -> str:
# # #     import re as _re
# # #     text_content = _re.sub(r"<[^>]+>", " ", html)
# # #     return _re.sub(r"\s+", " ", text_content).strip()


# # # # ═══════════════════════════════════════════════════════════════════════════
# # # # MAILBRIDGE DISPATCH
# # # # ═══════════════════════════════════════════════════════════════════════════

# # # async def _send_via_mailbridge(
# # #     db: AsyncSession,
# # #     config: MailBridgeConfig | None,
# # #     sequence: Sequence,
# # #     user_id: str | None = None,
# # # ) -> str:
# # #     """Send one sequence via MailBridge and return the messageId.

# # #     NOTE: DNS verification and warmup cap are NOT checked here in the
# # #     send function — they are checked by the caller (run_tick / manual_tick)
# # #     BEFORE calling this function. This keeps the send function clean and
# # #     allows manual_tick to skip DNS verification while auto-tick enforces it.
# # #     """
# # #     # Resolve prospect + recipient email
# # #     prospect_result = await db.execute(
# # #         select(Prospect).where(Prospect.id == sequence.prospectId)
# # #     )
# # #     prospect = prospect_result.scalar_one_or_none()
# # #     if prospect is None or not prospect.email:
# # #         raise RuntimeError(f"Prospect {sequence.prospectId} missing or has no email")

# # #     raw_email = prospect.email
# # #     if not getattr(prospect, "anonymized", False):
# # #         try:
# # #             from app.services.pii_service import PiiService
# # #             recipient_email = PiiService().decrypt_field(raw_email) or raw_email
# # #         except Exception:  # noqa: BLE001
# # #             recipient_email = raw_email
# # #     else:
# # #         recipient_email = raw_email

# # #     if not recipient_email:
# # #         raise RuntimeError(f"Prospect {sequence.prospectId} email is empty after decrypt")

# # #     settings = get_settings()

# # #     # Dev/CI stub: no config + no default URL → deterministic fake id
# # #     if config is None and not settings.MAILBRIDGE_DEFAULT_URL:
# # #         msg_id = f"stub-{sequence.id}@outrena.local"
# # #         await _record_usage_send_safe(db, sequence)
# # #         return msg_id

# # #     base_url = (config.baseUrl if config else "") or settings.MAILBRIDGE_DEFAULT_URL

# # #     # Build body with CAN-SPAM footer
# # #     body_text = sequence.bodyCopy or ""
# # #     is_html = _is_html_body(body_text)

# # #     needs_footer = (
# # #         "unsubscribe" not in body_text.lower()
# # #         or "physical" not in body_text.lower()
# # #         and "address" not in body_text.lower()
# # #     )
# # #     if needs_footer:
# # #         try:
# # #             from app.utils.tenant_context import resolve_tenant_slug as _rts
# # #             from app.core.config import get_settings as _gs
# # #             _tenant_slug = await _rts(db)
# # #             _prospect_token = getattr(prospect, "unsubscribeToken", None) or ""
# # #             _base = _gs().BASE_DOMAIN
# # #             _unsub_url = (
# # #                 f"https://{_base}/api/v1/public/unsubscribe"
# # #                 f"?token={_prospect_token}&tenant_slug={_tenant_slug}"
# # #                 if _prospect_token and _tenant_slug
# # #                 else ""
# # #             )
# # #             if is_html:
# # #                 _unsub_link = (
# # #                     f' <a href="{_unsub_url}" style="color:#6b7280;text-decoration:underline">Unsubscribe</a>'
# # #                     if _unsub_url else ""
# # #                 )
# # #                 _html_footer = (
# # #                     '<hr style="border:0;border-top:1px solid #e5e7eb;margin:24px 0">'
# # #                     '<p style="color:#6b7280;font-size:11px;line-height:1.5;margin:0">'
# # #                     f"This email was sent by an authorised OUTRENA user.{_unsub_link}</p>"
# # #                 )
# # #                 body_text = body_text + _html_footer
# # #             else:
# # #                 _footer_lines = ["", "---", "This email was sent by an authorised OUTRENA user."]
# # #                 if _unsub_url:
# # #                     _footer_lines.append(f"Unsubscribe: {_unsub_url}")
# # #                 body_text = body_text + "\n".join(_footer_lines)
# # #         except Exception:  # noqa: BLE001
# # #             pass

# # #     if is_html:
# # #         body_html_final = body_text
# # #         body_text_final = _strip_html_text(body_text)
# # #     else:
# # #         body_html_final = body_text
# # #         body_text_final = body_text

# # #     payload = {
# # #         "to": [recipient_email],
# # #         "subject": sequence.subjectLine or "",
# # #         "body_html": body_html_final,
# # #         "body_text": body_text_final,
# # #     }

# # #     config_owner = getattr(config, "owner_user_id", None) if config else None
# # #     config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
# # #     ext_user_id = (
# # #         config_ext_id
# # #         if (config_owner and config_owner == user_id and config_ext_id)
# # #         else user_id
# # #     )
# # #     if ext_user_id:
# # #         payload["external_user_id"] = ext_user_id

# # #     api_key = (getattr(config, "mailbridge_api_key", None) if config else None) or settings.MAILBRIDGE_API_KEY
# # #     headers: dict[str, str] = {"Content-Type": "application/json"}
# # #     if api_key:
# # #         headers["Authorization"] = f"Bearer {api_key}"

# # #     timeout_s = float(settings.MAILBRIDGE_TIMEOUT_SECONDS)
# # #     async with httpx.AsyncClient(timeout=timeout_s) as client:
# # #         resp = await client.post(
# # #             f"{base_url.rstrip('/')}/outbound/send",
# # #             json=payload,
# # #             headers=headers,
# # #         )
# # #         if resp.status_code >= 400:
# # #             raise RuntimeError(f"MailBridge returned HTTP {resp.status_code}: {resp.text[:200]}")
# # #         data = resp.json()
# # #         msg_id = data.get("message_id") or data.get("messageId", "")
# # #         if not msg_id:
# # #             raise RuntimeError("MailBridge response missing message_id")

# # #     if user_id:
# # #         sequence.sent_by_user_id = user_id
# # #     if ext_user_id:
# # #         sequence.sent_via_external_user_id = ext_user_id

# # #     await _record_usage_send_safe(db, sequence)
# # #     return msg_id


# # # async def _record_usage_send_safe(db: AsyncSession, sequence: Sequence) -> None:
# # #     """Best-effort: record one usage_event(email_send) row."""
# # #     try:
# # #         from app.utils.tenant_context import resolve_tenant_slug
# # #         tenant = await resolve_tenant_slug(db)
# # #         if not tenant:
# # #             return
# # #         from app.features.usage.service import UsageService
# # #         await UsageService().record_email_send(
# # #             tenant=tenant,
# # #             user_id=getattr(sequence, "owner_user_id", None) or "system",
# # #             metadata={"source": "scheduler.run_tick", "sequence_id": sequence.id},
# # #         )
# # #     except Exception as exc:  # noqa: BLE001
# # #         logger.warning("scheduler.send.usage_record_failed", sequence_id=getattr(sequence, "id", None), error=str(exc))


# # # # ═══════════════════════════════════════════════════════════════════════════
# # # # AUTO TICK — runs every SCHEDULER_TICK_SECONDS for all tenants
# # # # ═══════════════════════════════════════════════════════════════════════════

# # # async def run_tick(schema_name: str) -> dict[str, Any]:
# # #     """Run a single auto-scheduler tick against one tenant schema.

# # #     Gates (in order):
# # #       1. status = 'Scheduled' AND touchNumber <= 7
# # #       2. prospect exists AND has email            → else skip (no_email)
# # #       3. prospect.suppressed = False              → else skip (suppressed)
# # #       4. email not in EmailSuppression table      → else skip (suppressed)
# # #       5. business hours in prospect.timezone      → else skip (business_hours)
# # #          (NULL timezone = skip gate, send anyway)
# # #       6. PARTIAL enrichment throttle              → else skip (warmup_cap)
# # #       7. DNS verification on domain               → else skip (send_error)
# # #       8. daily cap check (warmup week OR env)     → else skip (quota_exceeded)
# # #       9. _send_via_mailbridge
# # #     """
# # #     settings = get_settings()
# # #     started = datetime.now(timezone.utc)
# # #     tick_bucket = int(started.timestamp()) // settings.SCHEDULER_TICK_SECONDS

# # #     summary: dict[str, Any] = {
# # #         "schema": schema_name,
# # #         "candidates": 0,
# # #         "sent": 0,
# # #         "skipped": 0,
# # #         "started_at": started.isoformat(),
# # #     }

# # #     async with AsyncSessionLocal() as session:
# # #         await session.execute(text(f'SET search_path TO "{schema_name}", public'))

# # #         # ── SchedulerStatus row ───────────────────────────────────────────
# # #         status_row = None
# # #         try:
# # #             status_result = await session.execute(
# # #                 select(SchedulerStatus).where(SchedulerStatus.id == 1)
# # #             )
# # #             status_row = status_result.scalar_one_or_none()
# # #             if status_row is None:
# # #                 status_row = SchedulerStatus(id=1, isRunning=False)
# # #                 session.add(status_row)
# # #                 await session.flush()
# # #             status_row.isRunning = True
# # #             await session.commit()
# # #         except Exception as _ss_exc:
# # #             err_str = str(_ss_exc)
# # #             if "does not exist" in err_str or "UndefinedTable" in err_str:
# # #                 await session.rollback()
# # #                 logger.warning("scheduler.tick.scheduler_status_missing", schema=schema_name)
# # #             else:
# # #                 raise

# # #         sent = 0
# # #         skipped = 0
# # #         ended = started  # will be updated in finally

# # #         try:
# # #             # ── Step 1: fetch candidates via raw SQL (avoids asyncpg enum cast bug) ──
# # #             # touchNumber <= 7 to include all 7 touches of the cadence.
# # #             try:
# # #                 await session.execute(text(f'SET search_path TO "{schema_name}", public'))
# # #                 seq_id_result = await session.execute(
# # #                     text(
# # #                         'SELECT id FROM "Sequence" '
# # #                         "WHERE status = 'Scheduled' "
# # #                         'AND "touchNumber" <= 7 '
# # #                         'ORDER BY "createdAt" ASC '
# # #                         'LIMIT 500'
# # #                     )
# # #                 )
# # #                 seq_ids = [row[0] for row in seq_id_result.fetchall()]
# # #             except Exception as table_exc:
# # #                 err_str = str(table_exc)
# # #                 if "does not exist" in err_str or "UndefinedTable" in err_str or "InFailedSQLTransaction" in err_str:
# # #                     await session.rollback()
# # #                     logger.warning("scheduler.tick.schema_not_ready", schema=schema_name, error=err_str[:200])
# # #                     summary["skipped"] = 0
# # #                     summary["sent"] = 0
# # #                     return summary
# # #                 raise

# # #             if not seq_ids:
# # #                 summary["candidates"] = 0
# # #                 summary["sent"] = 0
# # #                 summary["skipped"] = 0
# # #                 return summary

# # #             # Re-fetch as ORM objects for attribute access
# # #             await session.execute(text(f'SET search_path TO "{schema_name}", public'))
# # #             orm_result = await session.execute(
# # #                 select(Sequence).where(Sequence.id.in_(seq_ids)).order_by(Sequence.createdAt.asc())
# # #             )
# # #             sequences = list(orm_result.scalars().all())
# # #             summary["candidates"] = len(sequences)

# # #             # Pre-load tenant-level MailBridge config fallback
# # #             cfg_result = await session.execute(
# # #                 select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
# # #             )
# # #             tenant_default_config = cfg_result.scalar_one_or_none()

# # #             # Track per-campaign sent count within this tick to avoid over-sending
# # #             campaign_sent_this_tick: dict[str, int] = {}

# # #             for seq in sequences:
# # #                 await session.execute(text(f'SET search_path TO "{schema_name}", public'))
# # #                 try:
# # #                     campaign_id = getattr(seq, "campaignId", None)
# # #                     seq_owner = getattr(seq, "owner_user_id", None) or "system"

# # #                     # ── Gate 2: prospect exists + has email ───────────────
# # #                     prospect_result = await session.execute(
# # #                         select(Prospect).where(Prospect.id == seq.prospectId)
# # #                     )
# # #                     prospect = prospect_result.scalar_one_or_none()

# # #                     if prospect is None or not prospect.email:
# # #                         skipped += 1
# # #                         await write_skip_log(
# # #                             session, run_id=None, sequence_id=seq.id,
# # #                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                             skip_reason="no_email",
# # #                             detail="Prospect not found or has no email address",
# # #                         )
# # #                         continue

# # #                     # ── Gate 3: prospect suppression flag ─────────────────
# # #                     if prospect.suppressed:
# # #                         skipped += 1
# # #                         await write_skip_log(
# # #                             session, run_id=None, sequence_id=seq.id,
# # #                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                             skip_reason="suppressed",
# # #                             detail="Prospect suppression flag is set",
# # #                         )
# # #                         continue

# # #                     # ── Gate 4: email suppression list ────────────────────
# # #                     _email_lower = (prospect.email or "").strip().lower()
# # #                     if _email_lower:
# # #                         try:
# # #                             _es = await session.execute(
# # #                                 text('SELECT 1 FROM "EmailSuppression" WHERE email = :email LIMIT 1'),
# # #                                 {"email": _email_lower},
# # #                             )
# # #                             if _es.fetchone() is not None:
# # #                                 skipped += 1
# # #                                 await write_skip_log(
# # #                                     session, run_id=None, sequence_id=seq.id,
# # #                                     campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                                     skip_reason="suppressed",
# # #                                     detail=f"Email {_email_lower} is on suppression list",
# # #                                 )
# # #                                 continue
# # #                         except Exception:  # noqa: BLE001 — table may not exist, fail open
# # #                             pass

# # #                     # ── Gate 5: business hours (NULL timezone = send anyway) ──
# # #                     if prospect.timezone is not None and not _is_business_hours(started, prospect.timezone):
# # #                         skipped += 1
# # #                         await write_skip_log(
# # #                             session, run_id=None, sequence_id=seq.id,
# # #                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                             skip_reason="business_hours",
# # #                             detail=f"Outside 9am-5pm in timezone {prospect.timezone}",
# # #                         )
# # #                         continue

# # #                     # ── Gate 6: PARTIAL throttle ──────────────────────────
# # #                     if (
# # #                         prospect.enrichmentTier == EnrichmentTier.PARTIAL
# # #                         and not _partial_throttle_passes(prospect.id, tick_bucket)
# # #                     ):
# # #                         skipped += 1
# # #                         await write_skip_log(
# # #                             session, run_id=None, sequence_id=seq.id,
# # #                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                             skip_reason="warmup_cap",
# # #                             detail="PARTIAL throttle hash did not pass for this tick bucket",
# # #                         )
# # #                         continue

# # #                     # ── Gate 7: DNS verification (auto-tick only) ─────────
# # #                     if campaign_id:
# # #                         try:
# # #                             _camp = (
# # #                                 await session.execute(select(Campaign).where(Campaign.id == campaign_id))
# # #                             ).scalar_one_or_none()
# # #                             if _camp and getattr(_camp, "domainId", None):
# # #                                 _dom = (
# # #                                     await session.execute(select(Domain).where(Domain.id == _camp.domainId))
# # #                                 ).scalar_one_or_none()
# # #                                 if _dom is not None and _dom.lastChecked is not None:
# # #                                     failing_dns = [
# # #                                         name for name, ok in (
# # #                                             ("SPF", _dom.spfStatus),
# # #                                             ("DKIM", _dom.dkimStatus),
# # #                                             ("DMARC", _dom.dmarcStatus),
# # #                                         ) if not ok
# # #                                     ]
# # #                                     if failing_dns:
# # #                                         skipped += 1
# # #                                         await write_skip_log(
# # #                                             session, run_id=None, sequence_id=seq.id,
# # #                                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                                             skip_reason="send_error",
# # #                                             detail=f"DNS failing: {', '.join(failing_dns)} for domain '{_dom.domainName}'",
# # #                                         )
# # #                                         continue
# # #                         except Exception:  # noqa: BLE001 — fail open
# # #                             pass

# # #                     # ── Gate 8: daily cap check (warmup week OR env default) ──
# # #                     effective_cap, cap_source = await _resolve_daily_cap(session, campaign_id)
# # #                     already_sent = await _count_sent_today(session, campaign_id)
# # #                     within_tick = campaign_sent_this_tick.get(campaign_id or "__none__", 0)

# # #                     if (already_sent + within_tick) >= effective_cap:
# # #                         skipped += 1
# # #                         logger.info(
# # #                             "scheduler.sequence.quota_exceeded",
# # #                             schema=schema_name, sequence_id=seq.id,
# # #                             cap=effective_cap, source=cap_source,
# # #                             sent_today=already_sent + within_tick,
# # #                         )
# # #                         await write_skip_log(
# # #                             session, run_id=None, sequence_id=seq.id,
# # #                             campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                             skip_reason="quota_exceeded",
# # #                             detail=f"Daily cap {effective_cap} reached ({already_sent + within_tick} sent, source={cap_source})",
# # #                         )
# # #                         continue

# # #                     # ── Resolve MailBridge config ─────────────────────────
# # #                     config = await _resolve_mailbridge_config(session, seq_owner if seq_owner != "system" else None)
# # #                     if config is None:
# # #                         config = tenant_default_config

# # #                     # ── Send ─────────────────────────────────────────────
# # #                     msg_id = await _send_via_mailbridge(session, config, seq, user_id=seq_owner)

# # #                     await session.execute(
# # #                         text(
# # #                             'UPDATE "Sequence" SET status = \'Sent\', '
# # #                             '"sentAt" = :sent_at, "mailBridgeMessageId" = :msg_id '
# # #                             "WHERE id = :seq_id"
# # #                         ),
# # #                         {"sent_at": datetime.now(timezone.utc), "msg_id": msg_id, "seq_id": seq.id},
# # #                     )
# # #                     sent += 1

# # #                     # Track within-tick count
# # #                     key = campaign_id or "__none__"
# # #                     campaign_sent_this_tick[key] = campaign_sent_this_tick.get(key, 0) + 1

# # #                     # Daily sent log
# # #                     if campaign_id:
# # #                         await upsert_daily_sent(
# # #                             session, campaign_id=campaign_id, sent_date=started.date(), increment=1
# # #                         )

# # #                 except Exception as exc:  # noqa: BLE001 — per-sequence isolation
# # #                     skipped += 1
# # #                     logger.warning("scheduler.sequence.send_failed", schema=schema_name, sequence_id=seq.id, error=str(exc))
# # #                     await write_skip_log(
# # #                         session, run_id=None, sequence_id=seq.id,
# # #                         campaign_id=getattr(seq, "campaignId", None),
# # #                         prospect_id=getattr(seq, "prospectId", None),
# # #                         skip_reason="send_error", detail=str(exc)[:500],
# # #                     )

# # #             await session.commit()

# # #         finally:
# # #             ended = datetime.now(timezone.utc)
# # #             if status_row is not None:
# # #                 try:
# # #                     await session.execute(text(f'SET search_path TO "{schema_name}", public'))
# # #                     status_row.isRunning = False
# # #                     status_row.lastTickAt = started
# # #                     status_row.sentSinceLastTick = sent
# # #                     status_row.skippedSinceLastTick = skipped
# # #                     status_row.nextTickAt = started + timedelta(seconds=settings.SCHEDULER_TICK_SECONDS)
# # #                     await session.commit()
# # #                 except Exception:  # noqa: BLE001
# # #                     await session.rollback()

# # #     summary["sent"] = sent
# # #     summary["skipped"] = skipped
# # #     summary["ended_at"] = ended.isoformat()
# # #     summary["duration_ms"] = int((ended - started).total_seconds() * 1000)
# # #     return summary


# # # async def run_tick_all_tenants() -> dict[str, Any]:
# # #     """Run a tick across every ACTIVE tenant schema."""
# # #     summary: dict[str, Any] = {"tenants": 0, "sent": 0, "skipped": 0, "failed_tenants": 0}

# # #     schemas: list[str] = []
# # #     try:
# # #         async with engine.connect() as conn:
# # #             result = await conn.execute(
# # #                 text("SELECT schema_name FROM public.tenants WHERE status='ACTIVE' AND deleted_at IS NULL")
# # #             )
# # #             schemas = [row[0] for row in result.fetchall()]
# # #     except Exception as exc:  # noqa: BLE001
# # #         if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
# # #             raise
# # #         logger.warning("scheduler.tick.no_tenants_table", error=str(exc))

# # #     summary["tenant_count"] = len(schemas)
# # #     for schema in schemas:
# # #         try:
# # #             tick_result = await run_tick(schema)
# # #             summary["tenants"] += 1
# # #             summary["sent"] += tick_result.get("sent", 0)
# # #             summary["skipped"] += tick_result.get("skipped", 0)
# # #         except Exception as exc:  # noqa: BLE001
# # #             summary["failed_tenants"] += 1
# # #             logger.error("scheduler.tenant_failed", schema=schema, error=str(exc), exc_info=True)

# # #     return summary


# # # # ═══════════════════════════════════════════════════════════════════════════
# # # # SCHEDULER SERVICE  (manual tick + trigger + status + runs)
# # # # ═══════════════════════════════════════════════════════════════════════════

# # # class SchedulerService:
# # #     """Backwards-compatible wrapper for the Scheduler page endpoints."""

# # #     def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
# # #         self._mailbridge = mailbridge or MailBridgeService()

# # #     async def get_status(self, db: AsyncSession) -> SchedulerStatus:
# # #         """Return the singleton SchedulerStatus row, creating it if absent."""
# # #         result = await db.execute(select(SchedulerStatus).where(SchedulerStatus.id == 1))
# # #         status = result.scalar_one_or_none()
# # #         if status is None:
# # #             status = SchedulerStatus(id=1, isRunning=False)
# # #             db.add(status)
# # #             await db.commit()
# # #             status = await db.get(SchedulerStatus, status.id)
# # #         return status

# # #     async def manual_tick(
# # #         self,
# # #         db: AsyncSession,
# # #         *,
# # #         tenant_scoped: bool = True,
# # #         max_send: int = 50,
# # #     ) -> ManualTickResponse:
# # #         """Manual tick — sends immediately with minimal gates.

# # #         Gates ENFORCED (always):
# # #           ✅ prospect exists + has email     (legal / deliverability)
# # #           ✅ email not suppressed             (legal compliance)
# # #           ✅ daily cap (warmup week or env)   (warmup cap is sacred)

# # #         Gates SKIPPED (by design for manual sends):
# # #           ✗ business hours   (manual = operator wants to send NOW)
# # #           ✗ PARTIAL throttle (not relevant for manual trigger)
# # #           ✗ DNS verification (operator override — they know what they're doing)

# # #         Quota logic (same as auto-tick):
# # #           Campaign has verified domain with warmup configured
# # #             → warmup week cap (week 1=10 ... week 7=500)
# # #           Otherwise
# # #             → settings.DEFAULT_USER_DAILY_EMAIL_QUOTA (from .env)
# # #         """
# # #         started = datetime.now(timezone.utc)
# # #         settings = get_settings()
# # #         sent = 0
# # #         skipped = 0

# # #         # Resolve tenant schema from session search_path
# # #         schema_name = "public"
# # #         try:
# # #             _sr = await db.execute(text("SELECT current_schema()"))
# # #             _sc = _sr.scalar()
# # #             if _sc and _sc != "public":
# # #                 schema_name = _sc
# # #             else:
# # #                 _sr2 = await db.execute(text("SHOW search_path"))
# # #                 _sp = (_sr2.scalar() or "").replace('"', '')
# # #                 for part in _sp.split(","):
# # #                     part = part.strip()
# # #                     if part and part not in ("public", "$user"):
# # #                         schema_name = part
# # #                         break
# # #         except Exception:  # noqa: BLE001
# # #             pass

# # #         # Mark running
# # #         try:
# # #             await db.execute(
# # #                 text('UPDATE "SchedulerStatus" SET "isRunning" = true, "updatedAt" = now() WHERE id = 1')
# # #             )
# # #             await db.commit()
# # #         except Exception:  # noqa: BLE001
# # #             await db.rollback()

# # #         # Tenant-level MailBridge config fallback
# # #         try:
# # #             _cfg_r = await db.execute(
# # #                 select(MailBridgeConfig).where(MailBridgeConfig.isActive.is_(True)).limit(1)
# # #             )
# # #             tenant_default_config = _cfg_r.scalar_one_or_none()
# # #         except Exception:  # noqa: BLE001
# # #             tenant_default_config = None

# # #         # Fetch candidates — raw SQL to avoid asyncpg enum cast bug
# # #         try:
# # #             await db.execute(text(f'SET search_path TO "{schema_name}", public'))
# # #             seq_id_result = await db.execute(
# # #                 text(
# # #                     'SELECT id FROM "Sequence" '
# # #                     "WHERE status = 'Scheduled' "
# # #                     'AND "touchNumber" <= 7 '
# # #                     'ORDER BY "createdAt" ASC '
# # #                     'LIMIT :limit'
# # #                 ),
# # #                 {"limit": max_send},
# # #             )
# # #             seq_ids = [row[0] for row in seq_id_result.fetchall()]
# # #         except Exception as exc:  # noqa: BLE001
# # #             logger.warning("scheduler.manual_tick.fetch_failed", error=str(exc)[:200])
# # #             seq_ids = []

# # #         if seq_ids:
# # #             await db.execute(text(f'SET search_path TO "{schema_name}", public'))
# # #             orm_result = await db.execute(
# # #                 select(Sequence).where(Sequence.id.in_(seq_ids)).order_by(Sequence.createdAt.asc())
# # #             )
# # #             sequences = list(orm_result.scalars().all())
# # #         else:
# # #             sequences = []

# # #         # Track per-campaign sent count within this tick
# # #         campaign_sent_this_tick: dict[str, int] = {}

# # #         for seq in sequences:
# # #             campaign_id = getattr(seq, "campaignId", None)
# # #             seq_owner = getattr(seq, "owner_user_id", None) or "system"

# # #             try:
# # #                 await db.execute(text(f'SET search_path TO "{schema_name}", public'))

# # #                 # ── Gate: prospect exists + has email ─────────────────────
# # #                 prospect_result = await db.execute(
# # #                     select(Prospect).where(Prospect.id == seq.prospectId)
# # #                 )
# # #                 prospect = prospect_result.scalar_one_or_none()

# # #                 if prospect is None or not prospect.email:
# # #                     skipped += 1
# # #                     await write_skip_log(
# # #                         db, run_id=None, sequence_id=seq.id,
# # #                         campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                         skip_reason="no_email",
# # #                         detail="Prospect not found or has no email address",
# # #                     )
# # #                     continue

# # #                 # ── Gate: suppression ─────────────────────────────────────
# # #                 if prospect.suppressed:
# # #                     skipped += 1
# # #                     await write_skip_log(
# # #                         db, run_id=None, sequence_id=seq.id,
# # #                         campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                         skip_reason="suppressed",
# # #                         detail="Prospect suppression flag is set",
# # #                     )
# # #                     continue

# # #                 _email_lower = (prospect.email or "").strip().lower()
# # #                 if _email_lower:
# # #                     try:
# # #                         _es = await db.execute(
# # #                             text('SELECT 1 FROM "EmailSuppression" WHERE email = :email LIMIT 1'),
# # #                             {"email": _email_lower},
# # #                         )
# # #                         if _es.fetchone() is not None:
# # #                             skipped += 1
# # #                             await write_skip_log(
# # #                                 db, run_id=None, sequence_id=seq.id,
# # #                                 campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                                 skip_reason="suppressed",
# # #                                 detail=f"Email {_email_lower} is on suppression list",
# # #                             )
# # #                             continue
# # #                     except Exception:  # noqa: BLE001 — fail open
# # #                         pass

# # #                 # ── Gate: daily cap (warmup week OR env default) ──────────
# # #                 effective_cap, cap_source = await _resolve_daily_cap(db, campaign_id)
# # #                 already_sent = await _count_sent_today(db, campaign_id)
# # #                 within_tick = campaign_sent_this_tick.get(campaign_id or "__none__", 0)

# # #                 if (already_sent + within_tick) >= effective_cap:
# # #                     skipped += 1
# # #                     logger.info(
# # #                         "scheduler.manual_tick.daily_cap_reached",
# # #                         campaign_id=campaign_id, cap=effective_cap,
# # #                         source=cap_source, sent_today=already_sent + within_tick,
# # #                     )
# # #                     await write_skip_log(
# # #                         db, run_id=None, sequence_id=seq.id,
# # #                         campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                         skip_reason="quota_exceeded",
# # #                         detail=f"Daily cap {effective_cap} reached ({already_sent + within_tick} sent, source={cap_source})",
# # #                     )
# # #                     continue

# # #                 # ── Resolve MailBridge config ─────────────────────────────
# # #                 config = await _resolve_mailbridge_config(db, seq_owner if seq_owner != "system" else None)
# # #                 if config is None:
# # #                     config = tenant_default_config

# # #                 # ── Send ─────────────────────────────────────────────────
# # #                 msg_id = await _send_via_mailbridge(db, config, seq, user_id=seq_owner)

# # #                 await db.execute(
# # #                     text(
# # #                         'UPDATE "Sequence" SET status = \'Sent\', '
# # #                         '"sentAt" = :sent_at, "mailBridgeMessageId" = :msg_id '
# # #                         "WHERE id = :seq_id"
# # #                     ),
# # #                     {"sent_at": datetime.now(timezone.utc), "msg_id": msg_id, "seq_id": seq.id},
# # #                 )
# # #                 await db.commit()
# # #                 sent += 1

# # #                 key = campaign_id or "__none__"
# # #                 campaign_sent_this_tick[key] = campaign_sent_this_tick.get(key, 0) + 1

# # #                 if campaign_id:
# # #                     await upsert_daily_sent(
# # #                         db, campaign_id=campaign_id, sent_date=started.date(), increment=1
# # #                     )

# # #             except Exception as exc:  # noqa: BLE001 — per-sequence isolation
# # #                 skipped += 1
# # #                 logger.warning("scheduler.manual_tick.seq_failed", sequence_id=seq.id, error=str(exc)[:300])
# # #                 await write_skip_log(
# # #                     db, run_id=None, sequence_id=seq.id,
# # #                     campaign_id=campaign_id, prospect_id=seq.prospectId,
# # #                     skip_reason="send_error", detail=str(exc)[:500],
# # #                 )
# # #                 try:
# # #                     await db.rollback()
# # #                 except Exception:  # noqa: BLE001
# # #                     pass

# # #         # Update SchedulerStatus
# # #         try:
# # #             await db.execute(text(f'SET search_path TO "{schema_name}", public'))
# # #             await db.execute(
# # #                 text(
# # #                     'UPDATE "SchedulerStatus" SET '
# # #                     '"isRunning" = false, "lastTickAt" = :last, "nextTickAt" = :next, '
# # #                     '"sentSinceLastTick" = :sent, "skippedSinceLastTick" = :skipped, '
# # #                     '"updatedAt" = now() WHERE id = 1'
# # #                 ),
# # #                 {
# # #                     "last": started,
# # #                     "next": started + timedelta(seconds=settings.SCHEDULER_TICK_SECONDS),
# # #                     "sent": sent,
# # #                     "skipped": skipped,
# # #                 },
# # #             )
# # #             await db.commit()
# # #         except Exception as exc:  # noqa: BLE001
# # #             logger.warning("scheduler.manual_tick.status_update_failed", error=str(exc)[:200])

# # #         duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
# # #         logger.info("scheduler.manual_tick.complete", sent=sent, skipped=skipped, duration_ms=duration_ms)
# # #         return ManualTickResponse(sent=sent, skipped=skipped, durationMs=duration_ms, tickedAt=started)

# # #     async def trigger(self, db: AsyncSession) -> "TriggerResponse":
# # #         """Trigger an immediate scheduler tick via Celery or synchronous fallback."""
# # #         from app.schemas.scheduler import TriggerResponse

# # #         run = None
# # #         try:
# # #             _run_obj = SchedulerRun(status="running")
# # #             db.add(_run_obj)
# # #             await db.commit()
# # #             run = await db.get(SchedulerRun, _run_obj.id)
# # #         except Exception as _exc:  # noqa: BLE001
# # #             await db.rollback()
# # #             logger.warning("scheduler.trigger.run_log_skipped", error=str(_exc)[:200])

# # #         try:
# # #             from app.worker.celery_app import celery_app
# # #             if celery_app is not None:
# # #                 result = celery_app.send_task("autopilot.run_pipeline", kwargs={"schema_name": "current"})
# # #                 if run is not None:
# # #                     run.status = "completed"
# # #                     run.completedAt = datetime.now(timezone.utc)
# # #                     await db.commit()
# # #                 return TriggerResponse(triggered=True, message="Scheduler triggered via Celery.", runId=result.id)
# # #         except Exception as exc:  # noqa: BLE001
# # #             logger.warning("scheduler.trigger.celery_failed", error=str(exc))

# # #         try:
# # #             tick_result = await self.manual_tick(db, tenant_scoped=True, max_send=50)
# # #             if run is not None:
# # #                 run.status = "completed"
# # #                 run.sent = tick_result.sent
# # #                 run.skipped = tick_result.skipped
# # #                 run.durationMs = tick_result.durationMs
# # #                 run.completedAt = datetime.now(timezone.utc)
# # #                 await db.commit()
# # #             return TriggerResponse(
# # #                 triggered=True,
# # #                 message="Scheduler tick completed synchronously.",
# # #                 runId=run.id if run else None,
# # #             )
# # #         except Exception as exc:  # noqa: BLE001
# # #             if run is not None:
# # #                 run.status = "failed"
# # #                 run.error = str(exc)
# # #                 run.completedAt = datetime.now(timezone.utc)
# # #                 await db.commit()
# # #             return TriggerResponse(triggered=False, message=f"Scheduler tick failed: {exc}", runId=run.id if run else None)

# # #     async def list_runs(self, db: AsyncSession, *, limit: int = 20, offset: int = 0) -> "SchedulerRunsListResponse":
# # #         """Return recent scheduler run log entries, newest first."""
# # #         from app.schemas.scheduler import SchedulerRunResponse, SchedulerRunsListResponse
# # #         from sqlalchemy import func as sa_func

# # #         try:
# # #             count_result = await db.execute(select(sa_func.count()).select_from(SchedulerRun))
# # #             total = count_result.scalar() or 0
# # #             result = await db.execute(
# # #                 select(SchedulerRun).order_by(SchedulerRun.startedAt.desc()).limit(limit).offset(offset)
# # #             )
# # #             rows = list(result.scalars().all())
# # #             items = [SchedulerRunResponse.model_validate(r) for r in rows]
# # #             return SchedulerRunsListResponse(items=items, total=total)
# # #         except Exception as exc:  # noqa: BLE001
# # #             err_str = str(exc)
# # #             if "UndefinedTableError" in err_str or "does not exist" in err_str or "undefined_table" in err_str.lower():
# # #                 await db.rollback()
# # #                 logger.warning("scheduler.list_runs.table_missing", error=err_str[:200])
# # #                 from app.schemas.scheduler import SchedulerRunsListResponse
# # #                 return SchedulerRunsListResponse(items=[], total=0)
# # #             raise


# # # __all__ = [
# # #     "SchedulerService",
# # #     "get_scheduler",
# # #     "run_tick",
# # #     "run_tick_all_tenants",
# # #     "_is_business_hours",
# # #     "_partial_throttle_passes",
# # #     "_resolve_mailbridge_config",
# # #     "_send_via_mailbridge",
# # #     "_async_tick_wrapper",
# # #     "_resolve_daily_cap",
# # #     "advance_domain_warmup",
# # # ]


# # from __future__ import annotations
 
# # import asyncio
# # import hashlib
# # import zoneinfo
# # from datetime import datetime, time, timedelta, timezone
# # from typing import Any
 
# # import httpx
# # import structlog
# # from apscheduler.schedulers.asyncio import AsyncIOScheduler
# # from sqlalchemy import select, text
# # from sqlalchemy.ext.asyncio import AsyncSession
 
# # from app.core.config import get_settings
# # from app.core.database import AsyncSessionLocal, engine
# # from app.models.campaign_models import Sequence
# # from app.models.config_models import MailBridgeConfig
# # from app.models.enums import EmailStatus, EnrichmentTier
# # from app.models.phase3_models import SchedulerRun, SchedulerStatus
# # from app.models.prospect_models import Prospect
# # from app.schemas.scheduler import ManualTickResponse
# # from app.features.mailbridge.service import MailBridgeService
# # from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
# # from app.features.mailbridge.reply_poller import register_reply_poll_job
# # from app.features.scheduler.query_service import write_skip_log, upsert_daily_sent
# # logger = structlog.get_logger(__name__)
 
# # # ── Module-global singleton scheduler ──────────────────────────────────────
# # _scheduler: AsyncIOScheduler | None = None
# # # register_reply_poll_job(_scheduler)
 
# # def get_scheduler(
# #     *,
# #     email_tick_enabled: bool = True,
# #     reply_poller_enabled: bool = True,
# # ) -> AsyncIOScheduler:
# #     """Return the APScheduler singleton with two independently controlled jobs.

# #     email_tick_enabled=True   → registers the email-sending tick job
# #                                 (fires every SCHEDULER_TICK_SECONDS)
# #     reply_poller_enabled=True → registers the MailBridge reply+bounce
# #                                 polling job (fires every
# #                                 MAILBRIDGE_REPLY_POLL_SECONDS)

# #     The nightly cost-rollup cron job is always registered regardless of
# #     both flags — it is lightweight and has no impact on sending.

# #     Called from FastAPI lifespan in main.py. start()/shutdown() are called
# #     by the caller — this function only builds and returns the scheduler.
# #     """
# #     global _scheduler
# #     if _scheduler is None:
# #         settings = get_settings()
# #         _scheduler = AsyncIOScheduler()

# #         # ── Email sending tick (optional) ─────────────────────────────────
# #         if email_tick_enabled:
# #             _scheduler.add_job(
# #                 _async_tick_wrapper,
# #                 "interval",
# #                 seconds=settings.SCHEDULER_TICK_SECONDS,
# #                 id="outrena_tick",
# #                 max_instances=1,
# #                 coalesce=True,
# #                 replace_existing=True,
# #             )
# #             logger.info(
# #                 "scheduler.email_tick.registered",
# #                 tick_seconds=settings.SCHEDULER_TICK_SECONDS,
# #             )
# #         else:
# #             logger.info("scheduler.email_tick.disabled")

# #         # ── Nightly cost-rollup (always on) ───────────────────────────────
# #         _scheduler.add_job(
# #             _async_cost_rollup_wrapper,
# #             "cron",
# #             hour=2,
# #             minute=0,
# #             id="outrena_cost_rollup",
# #             max_instances=1,
# #             coalesce=True,
# #             replace_existing=True,
# #         )

# #         # ── Reply + bounce poller (optional, recommended always True) ──────
# #         if reply_poller_enabled:
# #             from app.features.mailbridge.reply_poller import register_reply_poll_job
# #             register_reply_poll_job(_scheduler)
# #             logger.info(
# #                 "scheduler.reply_poller.registered",
# #                 poll_seconds=settings.MAILBRIDGE_REPLY_POLL_SECONDS,
# #             )
# #         else:
# #             logger.info("scheduler.reply_poller.disabled")

# #     return _scheduler
 
 
# # async def _async_tick_wrapper() -> None:
# #     """Top-level tick wrapper — catches + logs every exception so a single
# #     tenant's failure (or even a DB outage) never kills the scheduler."""
# #     try:
# #         summary = await run_tick_all_tenants()
# #         logger.info("scheduler.tick.complete", **summary)
# #     except Exception as exc:  # noqa: BLE001 — scheduler must never die
# #         logger.error("scheduler.tick.fatal", error=str(exc), exc_info=True)
 
 
# # async def _async_cost_rollup_wrapper() -> None:
# #     """Nightly job — materialise CostSummary rows for all active tenants.
 
# #     Iterates all ACTIVE tenants in public.tenants and calls
# #     UsageService().rebuild_cost_summaries() for the current month.
# #     Failures per-tenant are logged and swallowed so one bad schema
# #     never blocks all others.
# #     """
# #     from app.core.database import AsyncSessionLocal
# #     from app.features.usage.service import UsageService
# #     from datetime import date as _date
 
# #     period = _date.today().strftime("%Y-%m")  # e.g. "2026-07"
# #     total = 0
# #     errors = 0
# #     try:
# #         async with AsyncSessionLocal() as db:
# #             from sqlalchemy import text as _text
# #             try:
# #                 result = await db.execute(
# #                     _text("SELECT slug FROM public.tenants WHERE status = 'ACTIVE' AND deleted_at IS NULL")
# #                 )
# #                 slugs = [row[0] for row in result.all()]
# #             except Exception as exc:  # noqa: BLE001
# #                 if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
# #                     raise
# #                 logger.warning("scheduler.cost_rollup.no_tenants_table", error=str(exc))
# #                 slugs = []
# #         for slug in slugs:
# #             try:
# #                 svc = UsageService()
# #                 written = await svc.rebuild_cost_summaries(slug, period)
# #                 total += written
# #             except Exception as exc:  # noqa: BLE001
# #                 errors += 1
# #                 logger.warning(
# #                     "scheduler.cost_rollup.tenant_failed",
# #                     tenant=slug,
# #                     error=str(exc),
# #                 )
# #         logger.info(
# #             "scheduler.cost_rollup.complete",
# #             period=period,
# #             tenants=len(slugs),
# #             rows_written=total,
# #             errors=errors,
# #         )
 
# #         # ── FR-038: nightly warm-up week advancement per tenant ────────────
# #         advanced_total = 0
# #         for slug in slugs:
# #             try:
# #                 async with AsyncSessionLocal() as db:
# #                     from sqlalchemy import text as _text
 
# #                     await db.execute(
# #                         _text(f'SET search_path TO "tenant_{slug}", public')
# #                     )
# #                     advanced_total += await advance_domain_warmup(db)
# #                     await db.commit()
# #             except Exception as exc:  # noqa: BLE001
# #                 logger.warning(
# #                     "scheduler.warmup_advance.tenant_failed",
# #                     tenant=slug,
# #                     error=str(exc),
# #                 )
# #         if advanced_total:
# #             logger.info(
# #                 "scheduler.warmup_advance.complete", domains=advanced_total
# #             )
# #     except Exception as exc:  # noqa: BLE001
# #         logger.error("scheduler.cost_rollup.fatal", error=str(exc), exc_info=True)
 
 
# # # ── §9.2 Business-hours filter ─────────────────────────────────────────────
 
 
# # # 7-week ramp per Help Guide §Domains (Warming Schedule)
# # # Week 1=10, 2=30, 3=50, 4=100, 5=200, 6=350, 7=500
# # _WARMUP_RAMP: dict[int, int] = {1: 10, 2: 30, 3: 50, 4: 100, 5: 200, 6: 350, 7: 500}
# # WARMING_SCHEDULE = [10, 30, 50, 100, 200, 350, 500]  # exported for UI display
 
 
# # def _warmup_effective_cap(dom) -> int:
# #     """FR-038: effective daily cap for a (possibly warming) domain."""
# #     week = int(getattr(dom, "warmingWeek", 0) or 0)
# #     base = int(getattr(dom, "dailySendLimit", 0) or 0) or 10_000
# #     if 1 <= week <= 7:
# #         return min(base, _WARMUP_RAMP[week])
# #     return base
 
 
# # async def advance_domain_warmup(db) -> int:
# #     """FR-038: advance warmingWeek for domains warmed >= 7 days per week.
 
# #     Called by the nightly maintenance job. A domain whose updatedAt is more
# #     than 7 days old and whose warmingWeek is 1-4 moves to the next week;
# #     week 5 means warm-up complete (full dailySendLimit applies).
# #     Returns the number of domains advanced."""
# #     result = await db.execute(
# #         text(
# #             'UPDATE "Domain" SET '
# #             '  "warmingWeek" = "warmingWeek" + 1, '
# #             '  "updatedAt" = now() '
# #             'WHERE "warmingWeek" BETWEEN 1 AND 7 '
# #             "  AND \"updatedAt\" < now() - interval '7 days'"
# #         )
# #     )
# #     return result.rowcount or 0
 
 
# # def _is_business_hours(now: datetime, tz_name: str | None) -> bool:
# #     """Return True iff `now` falls inside recipient-local 9am-5pm, Mon-Fri.
 
# #     If tz_name is None, defaults to America/New_York (US Eastern) — the most
# #     common timezone for B2B cold outreach targets. If tz_name is unparseable,
# #     falls back to UTC. local is always assigned before use (no UnboundLocalError).
# #     """
# #     local = now  # always assigned — fallback if zoneinfo fails
# #     effective_tz = tz_name or "America/New_York"
# #     try:
# #         tz = zoneinfo.ZoneInfo(effective_tz)
# #         local = now.astimezone(tz)
# #     except Exception:  # noqa: BLE001 — unknown tz string, keep UTC fallback
# #         local = now
# #     if local.weekday() >= 5:  # Sat=5, Sun=6
# #         return False
# #     start, end = time(9, 0), time(17, 0)
# #     return start <= local.time() <= end
 
 
# # # ── §9.3 PARTIAL throttle (deterministic hash) ─────────────────────────────
 
 
# # def _partial_throttle_passes(prospect_id: str, tick_bucket: int) -> bool:
# #     """Return True iff this PARTIAL-enrichment prospect should be sent this tick.
 
# #     Per migration §9.3 L1309-1316: hash(prospect_id + tick_bucket) % 100 must
# #     be < SCHEDULER_PARTIAL_PER_TICK_CAP (default 5). The hash is deterministic
# #     so retries within the same tick window select the same prospects.
# #     """
# #     settings = get_settings()
# #     cap = settings.SCHEDULER_PARTIAL_PER_TICK_CAP
# #     hash_input = f"{prospect_id}:{tick_bucket}"
# #     bucket = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16) % 100
# #     return bucket < cap
 
 
# # # ── §9.5 MailBridge dispatch ───────────────────────────────────────────────
 
 
# # async def _resolve_mailbridge_config(
# #     db: AsyncSession, user_id: str | None
# # ) -> MailBridgeConfig | None:
# #     """Resolve the MailBridgeConfig to use for a given user.
 
# #     Per SAAS2-USER-BE §G:
# #       1. If user_id is provided, look for an active MailBridgeConfig owned by
# #          that user (MailBridgeConfig.owner_user_id == user_id). This requires
# #          BE-A to have added the owner_user_id column to MailBridgeConfig.
# #       2. Fall back to a tenant-level config (owner_user_id IS NULL or column
# #          does not exist yet) — preserves the pre-user-behaviour.
# #       3. Return None if no active config exists.
 
# #     The lookup is defensive: if MailBridgeConfig does not yet expose
# #     owner_user_id (BE-A migration 0004 not yet applied), the per-user filter
# #     is skipped and the tenant-level fallback is used.
# #     """
# #     # Per-user lookup — only if the column exists on the model.
# #     has_owner_col = hasattr(MailBridgeConfig, "owner_user_id")
# #     if user_id and has_owner_col:
# #         try:
# #             result = await db.execute(
# #                 select(MailBridgeConfig)
# #                 .where(MailBridgeConfig.isActive.is_(True))
# #                 .where(getattr(MailBridgeConfig, "owner_user_id") == user_id)
# #                 .limit(1)
# #             )
# #             cfg = result.scalar_one_or_none()
# #             if cfg is not None:
# #                 return cfg
# #         except Exception as exc:  # noqa: BLE001 — fall back to tenant-level
# #             logger.warning(
# #                 "scheduler.mailbridge.per_user_lookup_failed",
# #                 user_id=user_id, error=str(exc),
# #             )
 
# #     # Tenant-level fallback.
# #     result = await db.execute(
# #         select(MailBridgeConfig)
# #         .where(MailBridgeConfig.isActive.is_(True))
# #         .limit(1)
# #     )
# #     return result.scalar_one_or_none()

# # def _is_html_body(body: str | None) -> bool:
# #     """True when body was authored in the Tiptap RTE (already HTML).

# #     The RTE always opens content with a block-level HTML tag. We also require
# #     at least one closing tag to avoid false-positives on plain text that
# #     happens to start with '<'.
# #     """
# #     if not body:
# #         return False
# #     s = body.lstrip()
# #     return s.startswith("<") and any(
# #         marker in body
# #         for marker in (
# #             "</p>", "</h", "<br", "</ul>", "</ol>",
# #             "</li>", "</strong>", "</em>",
# #         )
# #     )


# # def _strip_html_text(html: str) -> str:
# #     """Strip HTML tags and collapse whitespace → plain-text fallback."""
# #     import re as _re
# #     text = _re.sub(r"<[^>]+>", " ", html)
# #     return _re.sub(r"\s+", " ", text).strip() 
 
# # async def _send_via_mailbridge(
# #     db: AsyncSession,
# #     config: MailBridgeConfig | None,
# #     sequence: Sequence,
# #     user_id: str | None = None,
# # ) -> str:
# #     """Send one sequence via MailBridge and return the messageId.
 
# #     Per migration §9.5 L1339-1353. Uses httpx.AsyncClient with a 30s timeout.
# #     The prospect is loaded from the same session to resolve the recipient
# #     email + timezone. On HTTP 4xx/5xx or any network error, raises
# #     RuntimeError so the caller can mark the sequence as skipped.
 
# #     Stub-safe: if no `config` is supplied (dev/CI), returns a deterministic
# #     stub messageId so tests can run without a MailBridge instance.
# #     """
# #     # Resolve prospect + recipient email
# #     prospect_result = await db.execute(
# #         select(Prospect).where(Prospect.id == sequence.prospectId)
# #     )
# #     prospect = prospect_result.scalar_one_or_none()
# #     if prospect is None or not prospect.email:
# #         raise RuntimeError(
# #             f"Prospect {sequence.prospectId} missing or has no email"
# #         )
 
# #     # Wiring audit (Task 2-e): the Prospect.email column is encrypted at rest
# #     # when ENCRYPTION_KEY is set (production). Previously this helper passed
# #     # the raw encrypted blob to MailBridge — which then attempted to deliver
# #     # to a Fernet-token-looking address and bounced every send. Decrypt via
# #     # PiiService before building the payload (mirrors SequenceService.send_email
# #     # + ReplyDraftService.auto_reply). Best-effort: fall back to the stored
# #     # value when decryption fails (legacy plaintext / dev mode without key).
# #     raw_email = prospect.email
# #     if not getattr(prospect, "anonymized", False):
# #         try:
# #             from app.services.pii_service import PiiService
 
# #             recipient_email = PiiService().decrypt_field(raw_email) or raw_email
# #         except Exception:  # noqa: BLE001 — best-effort
# #             recipient_email = raw_email
# #     else:
# #         recipient_email = raw_email
# #     if not recipient_email:
# #         raise RuntimeError(
# #             f"Prospect {sequence.prospectId} email is empty after decrypt"
# #         )
 
# #     settings = get_settings()
 
# #     # ── FR-039: DNS verification gate ────────────────────────────────────
# #     # If the sending config is bound to a Domain whose SPF/DKIM/DMARC
# #     # verification is failing, refuse the send and name the failing record.
# #     # Domains that have never been checked (lastChecked IS NULL) are allowed
# #     # through — blocking on "not yet verified" would deadlock fresh tenants.
# #     if config is not None and getattr(config, "domainId", None):
# #         from app.models.config_models import Domain as _Domain
 
# #         dom = (
# #             await db.execute(select(_Domain).where(_Domain.id == config.domainId))
# #         ).scalar_one_or_none()
# #         if dom is not None and dom.lastChecked is not None:
# #             failing = [
# #                 name
# #                 for name, ok in (
# #                     ("SPF", dom.spfStatus),
# #                     ("DKIM", dom.dkimStatus),
# #                     ("DMARC", dom.dmarcStatus),
# #                 )
# #                 if not ok
# #             ]
# #             if failing:
# #                 raise RuntimeError(
# #                     f"DNS verification failing for domain '{dom.domainName}': "
# #                     f"{', '.join(failing)}. Fix the DNS records and re-verify "
# #                     "before sending (FR-039)."
# #                 )
 
# #         # ── Pre-flight warmup gate (Help Guide §Domains) ─────────────────
# #         # The domain must have completed at least 2 weeks of warmup before
# #         # any sequence email is dispatched. This mirrors the Sequences
# #         # Pre-Flight Activation Gate documented in the guide.
# #         if dom is not None:
# #             week = int(getattr(dom, "warmingWeek", 0) or 0)
# #             if 1 <= week < 2:
# #                 raise RuntimeError(
# #                     f"Domain '{dom.domainName}' has only completed "
# #                     f"{week} week(s) of warm-up. At least 2 weeks are "
# #                     "required before sending. Use the Auto-Warm button on "
# #                     "the Domains page to advance the schedule, or wait for "
# #                     "the nightly auto-advance."
# #                 )
 
# #         # ── FR-038: warm-up escalating daily cap ────────────────────────
# #         # While a domain is warming (warmingWeek 1-4), the effective daily
# #         # send cap ramps: week1=10, week2=25, week3=50, week4=100, then the
# #         # domain's own dailySendLimit applies. Week advancement is automated
# #         # by the nightly maintenance job (advance_domain_warmup below).
# #         if dom is not None:
# #             effective_cap = _warmup_effective_cap(dom)
# #             sent_today = (
# #                 await db.execute(
# #                     text(
# #                         'SELECT COUNT(*) FROM "Sequence" s '
# #                         'JOIN "Campaign" c ON c.id = s."campaignId" '
# #                         "WHERE c.\"domainId\" = :dom_id "
# #                         "  AND s.\"sentAt\" >= date_trunc('day', now())"
# #                     ),
# #                     {"dom_id": dom.id},
# #                 )
# #             ).scalar() or 0
# #             if int(sent_today) >= effective_cap:
# #                 raise RuntimeError(
# #                     f"Warm-up daily cap reached for domain "
# #                     f"'{dom.domainName}' ({sent_today}/{effective_cap}, "
# #                     f"week {dom.warmingWeek}). Deferring to tomorrow "
# #                     "(FR-038)."
# #                 )
 
# #     # Dev/CI stub: no config + no default URL → deterministic fake id.
# #     if config is None and not settings.MAILBRIDGE_DEFAULT_URL:
# #         msg_id = f"stub-{sequence.id}@outrena.local"
# #         # Best-effort: record usage_event(email_send) so even dev-mode stub
# #         # sends show up in per-tenant cost roll-ups (mirrors MailBridgeService.send).
# #         await _record_usage_send_safe(db, sequence)
# #         return msg_id
 
# #     base_url = (config.baseUrl if config else "") or settings.MAILBRIDGE_DEFAULT_URL
 
# #     # Build MailBridge-compatible body with CAN-SPAM footer.
# #     # RTE UPGRADE: body may be HTML from Tiptap; detect and route accordingly.
# #     body_text = sequence.bodyCopy or ""
# #     is_html = _is_html_body(body_text)

# #     # ── CAN-SPAM / NFR-19: footer enforcement ─────────────────────────────
# #     # Every commercial email must contain: physical address + unsubscribe URL.
# #     # If the sequence body lacks them, we append a minimal compliant footer.
# #     # HTML bodies get an HTML footer; plain-text bodies get the existing footer.
# #     # Best-effort: silently skip if we can't compute tenant slug.
# #     needs_footer = (
# #         "unsubscribe" not in body_text.lower()
# #         or "physical" not in body_text.lower()
# #         and "address" not in body_text.lower()
# #     )
# #     if needs_footer:
# #         try:
# #             from app.utils.tenant_context import resolve_tenant_slug as _rts
# #             from app.core.config import get_settings as _gs
# #             _tenant_slug = await _rts(db)
# #             _prospect_token = getattr(prospect, "unsubscribeToken", None) or ""
# #             _base = _gs().BASE_DOMAIN
# #             _unsub_url = (
# #                 f"https://{_base}/api/v1/public/unsubscribe"
# #                 f"?token={_prospect_token}&tenant_slug={_tenant_slug}"
# #                 if _prospect_token and _tenant_slug
# #                 else ""
# #             )

# #             if is_html:
# #                 # HTML footer — inline styles for maximum email-client compat.
# #                 _unsub_link = (
# #                     f' <a href="{_unsub_url}" '
# #                     'style="color:#6b7280;text-decoration:underline">Unsubscribe</a>'
# #                     if _unsub_url
# #                     else ""
# #                 )
# #                 _html_footer = (
# #                     '<hr style="border:0;border-top:1px solid #e5e7eb;margin:24px 0">'
# #                     '<p style="color:#6b7280;font-size:11px;line-height:1.5;margin:0">'
# #                     f"This email was sent by an authorised OUTRENA user.{_unsub_link}"
# #                     "</p>"
# #                 )
# #                 body_text = body_text + _html_footer
# #             else:
# #                 # Plain-text footer (unchanged from original behaviour).
# #                 _footer_lines = [
# #                     "",
# #                     "---",
# #                     "This email was sent by an authorised OUTRENA user.",
# #                 ]
# #                 if _unsub_url:
# #                     _footer_lines.append(f"Unsubscribe: {_unsub_url}")
# #                 body_text = body_text + "\n".join(_footer_lines)

# #         except Exception:  # noqa: BLE001 — footer is best-effort, never block send
# #             pass

# #     # Build MailBridge-compatible payload (Phase 3+ /outbound/send).
# #     # body_html: rich HTML for Gmail / Outlook / Apple Mail.
# #     # body_text: plain-text fallback for non-HTML email clients.
# #     if is_html:
# #         body_html_final = body_text           # already HTML with HTML footer
# #         body_text_final = _strip_html_text(body_text)   # stripped for fallback
# #     else:
# #         body_html_final = body_text           # MailBridge/Gmail handles plain text display
# #         body_text_final = body_text           # same plain text for fallback

# #     payload = {
# #         "to": [recipient_email],
# #         "subject": sequence.subjectLine or "",
# #         "body_html": body_html_final,
# #         "body_text": body_text_final,
# #     }
# #     # Identity propagation: tell MailBridge which connected mailbox to send from.
# #     #
# #     # Priority (mirrors MailBridgeService.send fix):
# #     #   1. config.mailbridge_external_user_id — ONLY when the config is explicitly
# #     #      owned by the sending user (config.owner_user_id == user_id), i.e. this
# #     #      is the user's own per-user config with a static identity override.
# #     #   2. user_id — the Keycloak UUID of the person who clicked Send.  This is
# #     #      the exact value MailBridge recorded during POST /connect/{provider}/start,
# #     #      so it routes through *that* user's connected mailbox — not the campaign
# #     #      creator's.
# #     #
# #     # We record the resolved value as `sent_via_external_user_id` on the Sequence
# #     # row so the reply-poller knows exactly which MailBridge identity to poll.
# #     config_owner = getattr(config, "owner_user_id", None) if config else None
# #     config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
# #     ext_user_id = (
# #         config_ext_id
# #         if (config_owner and config_owner == user_id and config_ext_id)
# #         else user_id
# #     )
# #     if ext_user_id:
# #         payload["external_user_id"] = ext_user_id
 
# #     # Build auth headers. MailBridge tenancy mode requires a Bearer
# #     # API key (mb_live_...) from POST /platform/register.
# #     api_key = (
# #         getattr(config, "mailbridge_api_key", None) if config else None
# #     ) or settings.MAILBRIDGE_API_KEY
# #     headers: dict[str, str] = {"Content-Type": "application/json"}
# #     if api_key:
# #         headers["Authorization"] = f"Bearer {api_key}"
 
# #     timeout_s = float(settings.MAILBRIDGE_TIMEOUT_SECONDS)
# #     async with httpx.AsyncClient(timeout=timeout_s) as client:
# #         resp = await client.post(
# #             f"{base_url.rstrip('/')}/outbound/send",
# #             json=payload,
# #             headers=headers,
# #         )
# #         if resp.status_code >= 400:
# #             raise RuntimeError(
# #                 f"MailBridge returned HTTP {resp.status_code}: {resp.text[:200]}"
# #             )
# #         data = resp.json()
# #         # MailBridge returns snake_case "message_id"; fall back to camelCase
# #         # for backward compatibility with older/stub MailBridge instances.
# #         msg_id = data.get("message_id") or data.get("messageId", "")
# #         if not msg_id:
# #             raise RuntimeError("MailBridge response missing message_id")
 
# #     # Stamp who actually sent this and which MailBridge identity was used.
# #     # These are the values the reply-poller relies on — see reply_poller.py.
# #     if user_id:
# #         sequence.sent_by_user_id = user_id
# #     if ext_user_id:
# #         sequence.sent_via_external_user_id = ext_user_id
 
# #     # Best-effort: record usage_event(email_send) for per-tenant cost roll-ups.
# #     # (Mirrors MailBridgeService.send._record_usage_send so the scheduler-tick
# #     # path doesn't silently bypass cost tracking.)
# #     await _record_usage_send_safe(db, sequence)
# #     return msg_id
 
 
# # async def _record_usage_send_safe(db: AsyncSession, sequence: Sequence) -> None:
# #     """Fire-and-forget: record one usage_event(email_send) row.
 
# #     Wiring audit (Task 2-e): scheduler_service._send_via_mailbridge
# #     previously bypassed MailBridgeService.send (it makes its own httpx call
# #     per migration §9.5), so the per-tenant cost roll-up never saw
# #     scheduler-tick sends. This helper delegates to the same
# #     UsageService.record_email_send path used by MailBridgeService.send,
# #     deriving the tenant slug from the session's search_path. Best-effort —
# #     failures are logged + swallowed so a usage write never blocks the send.
# #     """
# #     try:
# #         from app.utils.tenant_context import resolve_tenant_slug
# #         tenant = await resolve_tenant_slug(db)
# #         if not tenant:
# #             return
# #         from app.features.usage.service import UsageService
# #         await UsageService().record_email_send(
# #             tenant=tenant,
# #             user_id=getattr(sequence, "owner_user_id", None) or "system",
# #             metadata={"source": "scheduler.run_tick", "sequence_id": sequence.id},
# #         )
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning(
# #             "scheduler.send.usage_record_failed",
# #             sequence_id=getattr(sequence, "id", None),
# #             error=str(exc),
# #         )
 
 
# # # ── §9.6 Single-tenant + multi-tenant ticks ────────────────────────────────
 
 
# # async def run_tick(schema_name: str) -> dict[str, Any]:
# #     """Run a single scheduler tick against one tenant schema.
 
# #     Per migration §9.4-9.6 + §10 Phase 5 L1502-1523. Steps:
# #       1. SET search_path TO "{schema}", public
# #       2. SELECT Sequences WHERE status=Scheduled AND touchNumber<=6
# #       3. For each candidate:
# #          a. Load prospect; skip if suppressed or no email.
# #          b. Business-hours filter (§9.2) — skip if outside 9am-5pm local.
# #          c. PARTIAL throttle (§9.3) — skip if hash falls outside this tick's cap.
# #          d. Resolve MailBridgeConfig (first active row).
# #          e. Call _send_via_mailbridge → on success, set status=Sent + sentAt
# #             + mailBridgeMessageId. On failure, log + count as skipped.
# #       4. Update SchedulerStatus row (id=1) with new counters + nextTickAt.
# #       5. Commit + return summary dict.
# #     """
# #     settings = get_settings()
# #     started = datetime.now(timezone.utc)
# #     tick_bucket = int(started.timestamp()) // settings.SCHEDULER_TICK_SECONDS
 
# #     summary: dict[str, Any] = {
# #         "schema": schema_name,
# #         "candidates": 0,
# #         "sent": 0,
# #         "skipped": 0,
# #         "started_at": started.isoformat(),
# #     }
 
# #     async with AsyncSessionLocal() as session:
# #         await session.execute(text(f'SET search_path TO "{schema_name}", public'))
 
# #         # ── Step 1: load SchedulerStatus row (create if absent) ──────────
# #         # FIX: wrap in try/except — SchedulerStatus table may not exist in
# #         # partially-provisioned tenant schemas (migration 0002 not yet run).
# #         # In that case skip the status tracking but still attempt sends.
# #         status_row = None
# #         try:
# #             status_result = await session.execute(
# #                 select(SchedulerStatus).where(SchedulerStatus.id == 1)
# #             )
# #             status_row = status_result.scalar_one_or_none()
# #             if status_row is None:
# #                 status_row = SchedulerStatus(id=1, isRunning=False)
# #                 session.add(status_row)
# #                 await session.flush()
# #             status_row.isRunning = True
# #             await session.commit()
# #         except Exception as _ss_exc:
# #             err_str = str(_ss_exc)
# #             if "does not exist" in err_str or "UndefinedTable" in err_str:
# #                 await session.rollback()
# #                 logger.warning(
# #                     "scheduler.tick.scheduler_status_missing",
# #                     schema=schema_name,
# #                     hint="Run alembic upgrade head to create SchedulerStatus table",
# #                 )
# #             else:
# #                 raise
 
# #         sent = 0
# #         skipped = 0
# #         try:
# #             # ── Step 2: load Scheduled sequences with touchNumber<=6 ─────
# #             # Guard against UndefinedTableError on a fresh tenant schema
# #             # (tables may not exist yet) or InFailedSQLTransactionError
# #             # if a prior query in this session aborted the transaction.
# #             # Roll back and skip cleanly rather than poisoning the session.
# #             try:
# #                 seq_result = await session.execute(
# #                     select(Sequence)
# #                     .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
# #                     .where(Sequence.touchNumber <= 6)
# #                     .order_by(Sequence.createdAt.asc())
# #                     .limit(500)
# #                 )
# #                 sequences = list(seq_result.scalars().all())
# #             except Exception as table_exc:
# #                 err_str = str(table_exc)
# #                 if "UndefinedTableError" in err_str or "InFailedSQLTransaction" in err_str or "does not exist" in err_str:
# #                     import structlog as _sl
# #                     _sl.get_logger(__name__).warning(
# #                         "scheduler.tick.schema_not_ready",
# #                         schema=schema_name,
# #                         error=err_str[:200],
# #                     )
# #                     await session.rollback()
# #                     summary["skipped"] = 0
# #                     summary["sent"] = 0
# #                     return summary
# #                 raise
# #             sequences = list(sequences) if not isinstance(sequences, list) else sequences
# #             summary["candidates"] = len(sequences)
 
# #             # Pre-load first active MailBridgeConfig for this schema (kept as
# #             # a tenant-level fallback for sequences without an owner_user_id).
# #             cfg_result = await session.execute(
# #                 select(MailBridgeConfig)
# #                 .where(MailBridgeConfig.isActive.is_(True))
# #                 .limit(1)
# #             )
# #             tenant_default_config = cfg_result.scalar_one_or_none()
 
# #             quota_service = UserEmailQuotaService()
 
# #             for seq in sequences:
# #                 try:
# #                     # ── Load prospect once per sequence (cheap with session cache) ──
# #                     prospect_result = await session.execute(
# #                         select(Prospect).where(Prospect.id == seq.prospectId)
# #                     )
# #                     prospect = prospect_result.scalar_one_or_none()
 
# #                     # Skip suppressed / no-email prospects
# #                     # Layer 1: Prospect-level suppression flag
# #                     if prospect is None or not prospect.email:
# #                         skipped += 1
# #                         await write_skip_log(
# #                             session,
# #                             run_id=None,
# #                             sequence_id=seq.id,
# #                             campaign_id=getattr(seq, "campaignId", None),
# #                             prospect_id=seq.prospectId,
# #                             skip_reason="no_email",
# #                             detail="Prospect not found or has no email address",
# #                         )
# #                         continue
# #                     if prospect.suppressed:
# #                         skipped += 1
# #                         await write_skip_log(
# #                             session,
# #                             run_id=None,
# #                             sequence_id=seq.id,
# #                             campaign_id=getattr(seq, "campaignId", None),
# #                             prospect_id=seq.prospectId,
# #                             skip_reason="suppressed",
# #                             detail="Prospect suppression flag is set",
# #                         )
# #                         continue

# #                     # Layer 2: Email-level suppression — catches duplicate Prospect
# #                     # rows and future imports of the same address.
# #                     _sched_email_lower = (prospect.email or "").strip().lower()
# #                     if _sched_email_lower:
# #                         try:
# #                             from sqlalchemy import text as _sched_t
# #                             _sched_es = await session.execute(
# #                                 _sched_t(
# #                                     'SELECT 1 FROM "EmailSuppression" '
# #                                     'WHERE email = :email LIMIT 1'
# #                                 ),
# #                                 {"email": _sched_email_lower},
# #                             )
# #                             if _sched_es.fetchone() is not None:
# #                                 skipped += 1
# #                                 await write_skip_log(
# #                                     session,
# #                                     run_id=None,
# #                                     sequence_id=seq.id,
# #                                     campaign_id=getattr(seq, "campaignId", None),
# #                                     prospect_id=seq.prospectId,
# #                                     skip_reason="suppressed",
# #                                     detail=f"Email {_sched_email_lower} is on suppression list",
# #                                 )
# #                                 continue
# #                         except Exception:  # noqa: BLE001
# #                             # EmailSuppression table may not exist yet — fail open.
# #                             pass

# #                     # ── Step 3a: business-hours filter (§9.2) ─────────────
# #                     if not _is_business_hours(started, prospect.timezone):
# #                         skipped += 1
# #                         await write_skip_log(
# #                             session,
# #                             run_id=None,
# #                             sequence_id=seq.id,
# #                             campaign_id=getattr(seq, "campaignId", None),
# #                             prospect_id=seq.prospectId,
# #                             skip_reason="business_hours",
# #                             detail=f"Outside 9am-5pm in timezone {prospect.timezone or 'UTC'}",
# #                         )
# #                         continue

# #                     # ── Step 3b: PARTIAL throttle (§9.3) ──────────────────
# #                     if (
# #                         prospect.enrichmentTier == EnrichmentTier.PARTIAL
# #                         and not _partial_throttle_passes(prospect.id, tick_bucket)
# #                     ):
# #                         skipped += 1
# #                         await write_skip_log(
# #                             session,
# #                             run_id=None,
# #                             sequence_id=seq.id,
# #                             campaign_id=getattr(seq, "campaignId", None),
# #                             prospect_id=seq.prospectId,
# #                             skip_reason="warmup_cap",
# #                             detail="PARTIAL throttle hash did not pass for this tick bucket",
# #                         )
# #                         continue

# #                     # ── Step 3b': per-user quota enforcement (SAAS2-USER-BE §G) ──
# #                     # For the background scheduler, the "sender" is the sequence
# #                     # owner — the person whose MailBridge account will be used.
# #                     # sent_by_user_id is stamped inside _send_via_mailbridge on
# #                     # success (same value as seq_owner for scheduler-driven sends).
# #                     seq_owner = getattr(seq, "owner_user_id", None) or "system"
# #                     if seq_owner and seq_owner != "system":
# #                         try:
# #                             can_send, reason = await quota_service.check_can_send(
# #                                 session, seq_owner, count=1
# #                             )
# #                         except Exception as exc:  # noqa: BLE001 — never abort the tick
# #                             can_send, reason = False, f"quota_check_error: {exc}"
# #                         if not can_send:
# #                             skipped += 1
# #                             logger.info(
# #                                 "scheduler.sequence.quota_exceeded",
# #                                 schema=schema_name,
# #                                 sequence_id=seq.id,
# #                                 user_id=seq_owner,
# #                                 reason=reason,
# #                             )
# #                             await write_skip_log(
# #                                 session,
# #                                 run_id=None,
# #                                 sequence_id=seq.id,
# #                                 campaign_id=getattr(seq, "campaignId", None),
# #                                 prospect_id=seq.prospectId,
# #                                 skip_reason="quota_exceeded",
# #                                 detail=str(reason),
# #                             )
# #                             continue
# #                     else:
# #                         reason = "ok"
 
# #                     # ── Step 3c: per-user MailBridge resolution (SAAS2-USER-BE §G) ──
# #                     # Use the sequence owner's MailBridge config (their connected
# #                     # mailbox); fall back to the tenant-level default only when the
# #                     # owner has no personal config registered.
# #                     if seq_owner and seq_owner != "system":
# #                         config = await _resolve_mailbridge_config(session, seq_owner)
# #                     else:
# #                         config = tenant_default_config
# #                     if config is None:
# #                         config = tenant_default_config
 
# #                     # ── Step 3d: MailBridge dispatch (§9.5) ───────────────
# #                     # _send_via_mailbridge stamps seq.sent_by_user_id and
# #                     # seq.sent_via_external_user_id on the sequence row so the
# #                     # reply-poller can poll the correct MailBridge inbox.
# #                     msg_id = await _send_via_mailbridge(session, config, seq, user_id=seq_owner)
# #                     # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError across schemas)
# #                     await session.execute(
# #                         text(
# #                             "UPDATE \"Sequence\" SET status = 'Sent', "
# #                             "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
# #                             "WHERE id = :seq_id"
# #                         ),
# #                         {
# #                             "sent_at": datetime.now(timezone.utc),
# #                             "msg_id": msg_id,
# #                             "seq_id": seq.id,
# #                         },
# #                     )
# #                     sent += 1

# #                     # ── Step 3e: record daily sent aggregation ────────────
# #                     camp_id_for_log = getattr(seq, "campaignId", None)
# #                     if camp_id_for_log:
# #                         await upsert_daily_sent(
# #                             session,
# #                             campaign_id=camp_id_for_log,
# #                             sent_date=started.date(),
# #                             increment=1,
# #                         )

# #                     # ── Step 3f: record send against per-user quota ───────
# #                     if seq_owner and seq_owner != "system":
# #                         try:
# #                             await quota_service.record_send(session, seq_owner, count=1)
# #                         except Exception as exc:  # noqa: BLE001 — best-effort
# #                             logger.warning(
# #                                 "scheduler.sequence.quota_record_failed",
# #                                 schema=schema_name,
# #                                 sequence_id=seq.id,
# #                                 user_id=seq_owner,
# #                                 error=str(exc),
# #                             )
# #                 except Exception as exc:  # noqa: BLE001 — per-seq isolation
# #                     skipped += 1
# #                     logger.warning(
# #                         "scheduler.sequence.send_failed",
# #                         schema=schema_name,
# #                         sequence_id=seq.id,
# #                         error=str(exc),
# #                     )
# #                     await write_skip_log(
# #                         session,
# #                         run_id=None,
# #                         sequence_id=seq.id,
# #                         campaign_id=getattr(seq, "campaignId", None),
# #                         prospect_id=getattr(seq, "prospectId", None),
# #                         skip_reason="send_error",
# #                         detail=str(exc)[:500],
# #                     )
 
# #             await session.commit()
# #         finally:
# #             # ── Step 4: update SchedulerStatus counters + nextTickAt ─────
# #             ended = datetime.now(timezone.utc)
# #             if status_row is not None:
# #                 status_row.isRunning = False
# #                 status_row.lastTickAt = started
# #                 status_row.sentSinceLastTick = sent
# #                 status_row.skippedSinceLastTick = skipped
# #                 status_row.nextTickAt = started + timedelta(
# #                     seconds=settings.SCHEDULER_TICK_SECONDS
# #                 )
# #                 try:
# #                     await session.commit()
# #                 except Exception:  # noqa: BLE001
# #                     await session.rollback()
 
# #         summary["sent"] = sent
# #         summary["skipped"] = skipped
# #         summary["ended_at"] = ended.isoformat()
# #         summary["duration_ms"] = int((ended - started).total_seconds() * 1000)
# #         return summary
 
 
# # async def run_tick_all_tenants() -> dict[str, Any]:
# #     """Run a tick across every ACTIVE tenant schema.
 
# #     Per migration §9.6 L1362-1378: SELECT schema_name FROM public.tenants
# #     WHERE status='ACTIVE' AND deleted_at IS NULL. Per-tenant failure is
# #     logged + skipped — it never aborts the entire tick.
# #     """
# #     summary: dict[str, Any] = {
# #         "tenants": 0,
# #         "sent": 0,
# #         "skipped": 0,
# #         "failed_tenants": 0,
# #     }
 
# #     # Query public.tenants directly via a raw connection (not the ORM)
# #     # so we don't pollute the tenant-schema-bound session cache.
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
# #         # UndefinedTableError on a fresh DB (no tenants provisioned yet) or
# #         # a stale asyncpg per-connection statement plan — either way, there
# #         # are no active tenant schemas to tick. Log and continue with [].
# #         if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
# #             raise
# #         logger.warning("scheduler.tick.no_tenants_table", error=str(exc))
# #         schemas = []
 
# #     summary["tenant_count"] = len(schemas)
# #     for schema in schemas:
# #         try:
# #             tick_result = await run_tick(schema)
# #             summary["tenants"] += 1
# #             summary["sent"] += tick_result.get("sent", 0)
# #             summary["skipped"] += tick_result.get("skipped", 0)
# #         except Exception as exc:  # noqa: BLE001 — per-tenant isolation
# #             summary["failed_tenants"] += 1
# #             logger.error(
# #                 "scheduler.tenant_failed",
# #                 schema=schema,
# #                 error=str(exc),
# #                 exc_info=True,
# #             )
 
# #     return summary
 
 
# # # ── Phase 3 SchedulerService (preserved) ────────────────────────────────────
 
 
# # class SchedulerService:
# #     """Backwards-compatible wrapper exposing the Phase 3 status +
# #     manual-tick endpoints. Phase 5 callers should use run_tick() /
# #     run_tick_all_tenants() / get_scheduler() directly."""
 
# #     def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
# #         self._mailbridge = mailbridge or MailBridgeService()
 
# #     async def get_status(self, db: AsyncSession) -> SchedulerStatus:
# #         """Return the singleton status row, creating it if absent."""
# #         result = await db.execute(
# #             select(SchedulerStatus).where(SchedulerStatus.id == 1)
# #         )
# #         status = result.scalar_one_or_none()
# #         if status is None:
# #             status = SchedulerStatus(id=1, isRunning=False)
# #             db.add(status)
# #             await db.commit()
# #             status = await db.get(SchedulerStatus, status.id)
# #         return status
 
# #     async def manual_tick(
# #         self,
# #         db: AsyncSession,
# #         *,
# #         tenant_scoped: bool = True,
# #         max_send: int = 50,
# #     ) -> ManualTickResponse:
# #         """Send up to max_send Scheduled sequences in one synchronous tick.
 
# #         Phase 3 contract — preserved verbatim. Does NOT apply the §9.2/§9.3
# #         business-hours + PARTIAL throttle filters (callers that want the
# #         Phase 5 behavior should invoke run_tick() instead).
# #         """
# #         started = datetime.now(timezone.utc)
# #         status = await self.get_status(db)
# #         status.isRunning = True
# #         await db.commit()
 
# #         sent = 0
# #         skipped = 0
# #         try:
# #             result = await db.execute(
# #                 select(Sequence)
# #                 .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
# #                 .limit(max_send)
# #             )
# #             sequences = list(result.scalars().all())
# #             for seq in sequences:
# #                 # Phase 5 will add business-hours + throttle filters here.
# #                 try:
# #                     # Wiring audit (Task 2-e): previously this method passed
# #                     # ``to=""`` to MailBridgeService.send with a comment saying
# #                     # "caller resolves prospect.email" — but no caller actually
# #                     # did so, resulting in empty-envelope stub-accepts. Resolve
# #                     # the prospect email (with PII decrypt) here so the manual
# #                     # tick actually delivers. Mirrors SequenceService.send_email.
# #                     to_email = ""
# #                     if seq.prospectId:
# #                         p_result = await db.execute(
# #                             select(Prospect).where(Prospect.id == seq.prospectId)
# #                         )
# #                         p = p_result.scalar_one_or_none()
# #                         if p is not None:
# #                             raw_email = getattr(p, "email", None) or ""
# #                             if raw_email and not getattr(p, "anonymized", False):
# #                                 try:
# #                                     from app.services.pii_service import PiiService
 
# #                                     to_email = (
# #                                         PiiService().decrypt_field(raw_email)
# #                                         or raw_email
# #                                     )
# #                                 except Exception:  # noqa: BLE001 — best-effort
# #                                     to_email = raw_email
# #                             elif raw_email:
# #                                 to_email = raw_email
# #                     if not to_email:
# #                         skipped += 1
# #                         continue
# #                     send_result = await self._mailbridge.send(
# #                         db=db,
# #                         to=to_email,
# #                         subject=seq.subjectLine or "",
# #                         body=seq.bodyCopy or "",
# #                         sequence_id=seq.id,
# #                         user_id=getattr(seq, "owner_user_id", None),
# #                     )
# #                     if send_result.accepted:
# #                         # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError)
# #                         # seq.status = EmailStatus.Sent would generate $1::email_status
# #                         # which fails across tenant schemas due to asyncpg plan cache.
# #                         await db.execute(
# #                             text(
# #                                 "UPDATE \"Sequence\" SET status = 'Sent', "
# #                                 "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
# #                                 "WHERE id = :seq_id"
# #                             ),
# #                             {
# #                                 "sent_at": datetime.now(timezone.utc),
# #                                 "msg_id": send_result.messageId,
# #                                 "seq_id": seq.id,
# #                             },
# #                         )
# #                         sent += 1
# #                     else:
# #                         skipped += 1
# #                 except Exception:  # noqa: BLE001
# #                     skipped += 1
# #             try:
# #                 await db.commit()
# #             except Exception:  # noqa: BLE001 — swallow if already aborted
# #                 await db.rollback()
# #         finally:
# #             duration_ms = int(
# #                 (datetime.now(timezone.utc) - started).total_seconds() * 1000
# #             )
# #             # FIX: rollback any aborted transaction before updating SchedulerStatus
# #             # so the finally block never runs inside an aborted transaction.
# #             try:
# #                 await db.rollback()
# #             except Exception:  # noqa: BLE001
# #                 pass
# #             try:
# #                 await db.execute(
# #                     text(
# #                         'UPDATE "SchedulerStatus" SET "isRunning" = false, '
# #                         '"lastTickAt" = :last, "nextTickAt" = :next, '
# #                         '"sentSinceLastTick" = :sent, "skippedSinceLastTick" = :skipped, '
# #                         '"updatedAt" = now() WHERE id = 1'
# #                     ),
# #                     {
# #                         "last": started,
# #                         "next": started + timedelta(seconds=get_settings().SCHEDULER_TICK_SECONDS),
# #                         "sent": sent,
# #                         "skipped": skipped,
# #                     },
# #                 )
# #                 await db.commit()
# #             except Exception as _fin_exc:  # noqa: BLE001
# #                 logger.warning(
# #                     "scheduler.manual_tick.status_update_failed",
# #                     error=str(_fin_exc)[:200],
# #                 )
# #         return ManualTickResponse(
# #             sent=sent,
# #             skipped=skipped,
# #             durationMs=duration_ms,
# #             tickedAt=started,
# #         )
 
# #     async def trigger(self, db: AsyncSession) -> "TriggerResponse":
# #         """Trigger an immediate scheduler tick via Celery or direct invocation.
 
# #         If Celery is available and the broker is reachable, enqueues
# #         ``autopilot.run_pipeline`` and returns immediately with the task ID
# #         as ``runId``. Otherwise falls back to a synchronous tick and logs
# #         a ``SchedulerRun`` row.
 
# #         Returns a ``TriggerResponse`` with ``triggered=True`` on success.
# #         """
# #         from app.schemas.scheduler import TriggerResponse
 
# #         # FIX: SchedulerRun table may not exist yet (migration 0019 creates it).
# #         # If insert fails, continue without logging - the tick still runs.
# #         run = None
# #         try:
# #             _run_obj = SchedulerRun(status="running")
# #             db.add(_run_obj)
# #             await db.commit()
# #             run = await db.get(SchedulerRun, _run_obj.id)
# #         except Exception as _exc:  # noqa: BLE001
# #             await db.rollback()
# #             logger.warning(
# #                 "scheduler.trigger.run_log_skipped",
# #                 hint="Run migration 0019 to create SchedulerRun table",
# #                 error=str(_exc)[:200],
# #             )
 
# #         # Attempt Celery enqueue
# #         try:
# #             from app.worker.celery_app import celery_app
 
# #             if celery_app is not None:
# #                 result = celery_app.send_task(
# #                     "autopilot.run_pipeline",
# #                     kwargs={"schema_name": "current"},
# #                 )
# #                 if run is not None:
# #                     run.status = "completed"
# #                     run.completedAt = datetime.now(timezone.utc)
# #                     await db.commit()
# #                 return TriggerResponse(
# #                     triggered=True,
# #                     message="Scheduler triggered via Celery.",
# #                     runId=result.id,
# #                 )
# #         except Exception as exc:  # noqa: BLE001
# #             logger.warning("scheduler.trigger.celery_failed", error=str(exc))
 
# #         # Fallback: synchronous tick
# #         started = datetime.now(timezone.utc)
# #         try:
# #             tick_result = await self.manual_tick(
# #                 db, tenant_scoped=True, max_send=50
# #             )
# #             if run is not None:
# #                 run.status = "completed"
# #                 run.sent = tick_result.sent
# #                 run.skipped = tick_result.skipped
# #                 run.durationMs = tick_result.durationMs
# #                 run.completedAt = datetime.now(timezone.utc)
# #                 await db.commit()
# #             return TriggerResponse(
# #                 triggered=True,
# #                 message="Scheduler tick completed synchronously.",
# #                 runId=run.id if run else None,
# #             )
# #         except Exception as exc:  # noqa: BLE001
# #             if run is not None:
# #                 run.status = "failed"
# #                 run.error = str(exc)
# #                 run.completedAt = datetime.now(timezone.utc)
# #                 await db.commit()
# #             return TriggerResponse(
# #                 triggered=False,
# #                 message=f"Scheduler tick failed: {exc}",
# #                 runId=run.id if run else None,
# #             )
 
# #     async def list_runs(
# #         self,
# #         db: AsyncSession,
# #         *,
# #         limit: int = 20,
# #         offset: int = 0,
# #     ) -> "SchedulerRunsListResponse":
# #         """Return recent scheduler run log entries, newest first.
 
# #         FIX: SchedulerRun table was never in any migration — wraps queries in
# #         try/except so the Scheduler Status page loads cleanly even on tenants
# #         that have not run migration 0019 yet. Returns empty list in that case.
# #         """
# #         from app.schemas.scheduler import (
# #             SchedulerRunResponse,
# #             SchedulerRunsListResponse,
# #         )
# #         from sqlalchemy import func as sa_func
 
# #         try:
# #             count_result = await db.execute(
# #                 select(sa_func.count()).select_from(SchedulerRun)
# #             )
# #             total = count_result.scalar() or 0
 
# #             result = await db.execute(
# #                 select(SchedulerRun)
# #                 .order_by(SchedulerRun.startedAt.desc())
# #                 .limit(limit)
# #                 .offset(offset)
# #             )
# #             rows = list(result.scalars().all())
# #             items = [SchedulerRunResponse.model_validate(r) for r in rows]
# #             return SchedulerRunsListResponse(items=items, total=total)
# #         except Exception as exc:  # noqa: BLE001
# #             # Table does not exist yet - return empty list instead of crashing.
# #             # Resolved permanently by running migration 0019.
# #             err_str = str(exc)
# #             if "UndefinedTableError" in err_str or "does not exist" in err_str or "undefined_table" in err_str.lower():
# #                 await db.rollback()
# #                 logger.warning(
# #                     "scheduler.list_runs.table_missing",
# #                     hint="Run migration 0019 to create SchedulerRun table",
# #                     error=err_str[:200],
# #                 )
# #                 return SchedulerRunsListResponse(items=[], total=0)
# #             raise
 
 
# # __all__ = [
# #     "SchedulerService",
# #     "get_scheduler",
# #     "run_tick",
# #     "run_tick_all_tenants",
# #     "_is_business_hours",
# #     "_partial_throttle_passes",
# #     "_resolve_mailbridge_config",
# #     "_send_via_mailbridge",
# #     "_async_tick_wrapper",
# # ]


# from __future__ import annotations
 
# import asyncio
# import hashlib
# import zoneinfo
# from datetime import datetime, time, timedelta, timezone
# from typing import Any
 
# import httpx
# import structlog
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from sqlalchemy import select, text
# from sqlalchemy.ext.asyncio import AsyncSession
 
# from app.core.config import get_settings
# from app.core.database import AsyncSessionLocal, engine
# from app.models.campaign_models import Sequence
# from app.models.config_models import MailBridgeConfig
# from app.models.enums import EmailStatus, EnrichmentTier
# from app.models.phase3_models import SchedulerRun, SchedulerStatus
# from app.models.prospect_models import Prospect
# from app.schemas.scheduler import ManualTickResponse
# from app.features.mailbridge.service import MailBridgeService
# from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
# from app.features.mailbridge.reply_poller import register_reply_poll_job
# from app.features.scheduler.query_service import write_skip_log, upsert_daily_sent
# logger = structlog.get_logger(__name__)
 
# # ── Module-global singleton scheduler ──────────────────────────────────────
# _scheduler: AsyncIOScheduler | None = None
# # register_reply_poll_job(_scheduler)
 
# # def get_scheduler() -> AsyncIOScheduler:
# #     """Return the AsyncIOScheduler singleton (migration §9.1 L1266-1278).
 
# #     The scheduler is created lazily on first access and configured with
# #     max_instances=1 + coalesce=True so missed ticks never pile up. The
# #     interval job is registered here; start()/shutdown() are called from
# #     the FastAPI lifespan in app.main.create_app().
# #     """
# #     global _scheduler
# #     if _scheduler is None:
# #         settings = get_settings()
# #         _scheduler = AsyncIOScheduler()
# #         _scheduler.add_job(
# #             _async_tick_wrapper,
# #             "interval",
# #             seconds=settings.SCHEDULER_TICK_SECONDS,
# #             id="outrena_tick",
# #             max_instances=1,
# #             coalesce=True,
# #             replace_existing=True,
# #         )
# #         # Nightly cost-summary rollup — runs at 02:00 UTC every day.
# #         # Materialises per-user × event_type × provider cost_summaries rows
# #         # for the current month so the Usage dashboard reads from a fast
# #         # rollup table rather than scanning raw usage_events.
# #         _scheduler.add_job(
# #             _async_cost_rollup_wrapper,
# #             "cron",
# #             hour=2,
# #             minute=0,
# #             id="outrena_cost_rollup",
# #             max_instances=1,
# #             coalesce=True,
# #             replace_existing=True,
# #         )
# #                 # Reply-inbox poller — polls MailBridge for inbound replies.
# #         # Only registers when MAILBRIDGE_DEFAULT_URL is configured.
# #         from app.features.mailbridge.reply_poller import register_reply_poll_job
# #         register_reply_poll_job(_scheduler)
# #         logger.info(
# #             "scheduler.registered",
# #             tick_seconds=settings.SCHEDULER_TICK_SECONDS,
# #             job_id="outrena_tick",
# #         )
# #     return _scheduler
 
# def get_scheduler(
#     *,
#     email_tick_enabled: bool = True,
#     reply_poller_enabled: bool = True,
# ) -> AsyncIOScheduler:
#     """Return the APScheduler singleton — email tick and reply poller
#     are registered independently based on their respective flags."""
#     global _scheduler
#     if _scheduler is None:
#         settings = get_settings()
#         _scheduler = AsyncIOScheduler()

#         if email_tick_enabled:
#             _scheduler.add_job(
#                 _async_tick_wrapper,
#                 "interval",
#                 seconds=settings.SCHEDULER_TICK_SECONDS,
#                 id="outrena_tick",
#                 max_instances=1,
#                 coalesce=True,
#                 replace_existing=True,
#             )
#             logger.info("scheduler.email_tick.registered",
#                         tick_seconds=settings.SCHEDULER_TICK_SECONDS)
#         else:
#             logger.info("scheduler.email_tick.disabled")

#         _scheduler.add_job(
#             _async_cost_rollup_wrapper,
#             "cron",
#             hour=2,
#             minute=0,
#             id="outrena_cost_rollup",
#             max_instances=1,
#             coalesce=True,
#             replace_existing=True,
#         )

#         if reply_poller_enabled:
#             from app.features.mailbridge.reply_poller import register_reply_poll_job
#             register_reply_poll_job(_scheduler)
#             logger.info("scheduler.reply_poller.registered",
#                         poll_seconds=settings.MAILBRIDGE_REPLY_POLL_SECONDS)
#         else:
#             logger.info("scheduler.reply_poller.disabled")

#     return _scheduler
 
# async def _async_tick_wrapper() -> None:
#     """Top-level tick wrapper — catches + logs every exception so a single
#     tenant's failure (or even a DB outage) never kills the scheduler."""
#     try:
#         summary = await run_tick_all_tenants()
#         logger.info("scheduler.tick.complete", **summary)
#     except Exception as exc:  # noqa: BLE001 — scheduler must never die
#         logger.error("scheduler.tick.fatal", error=str(exc), exc_info=True)
 
 
# async def _async_cost_rollup_wrapper() -> None:
#     """Nightly job — materialise CostSummary rows for all active tenants.
 
#     Iterates all ACTIVE tenants in public.tenants and calls
#     UsageService().rebuild_cost_summaries() for the current month.
#     Failures per-tenant are logged and swallowed so one bad schema
#     never blocks all others.
#     """
#     from app.core.database import AsyncSessionLocal
#     from app.features.usage.service import UsageService
#     from datetime import date as _date
 
#     period = _date.today().strftime("%Y-%m")  # e.g. "2026-07"
#     total = 0
#     errors = 0
#     try:
#         async with AsyncSessionLocal() as db:
#             from sqlalchemy import text as _text
#             try:
#                 result = await db.execute(
#                     _text("SELECT slug FROM public.tenants WHERE status = 'ACTIVE' AND deleted_at IS NULL")
#                 )
#                 slugs = [row[0] for row in result.all()]
#             except Exception as exc:  # noqa: BLE001
#                 if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
#                     raise
#                 logger.warning("scheduler.cost_rollup.no_tenants_table", error=str(exc))
#                 slugs = []
#         for slug in slugs:
#             try:
#                 svc = UsageService()
#                 written = await svc.rebuild_cost_summaries(slug, period)
#                 total += written
#             except Exception as exc:  # noqa: BLE001
#                 errors += 1
#                 logger.warning(
#                     "scheduler.cost_rollup.tenant_failed",
#                     tenant=slug,
#                     error=str(exc),
#                 )
#         logger.info(
#             "scheduler.cost_rollup.complete",
#             period=period,
#             tenants=len(slugs),
#             rows_written=total,
#             errors=errors,
#         )
 
#         # ── FR-038: nightly warm-up week advancement per tenant ────────────
#         advanced_total = 0
#         for slug in slugs:
#             try:
#                 async with AsyncSessionLocal() as db:
#                     from sqlalchemy import text as _text
 
#                     await db.execute(
#                         _text(f'SET search_path TO "tenant_{slug}", public')
#                     )
#                     advanced_total += await advance_domain_warmup(db)
#                     await db.commit()
#             except Exception as exc:  # noqa: BLE001
#                 logger.warning(
#                     "scheduler.warmup_advance.tenant_failed",
#                     tenant=slug,
#                     error=str(exc),
#                 )
#         if advanced_total:
#             logger.info(
#                 "scheduler.warmup_advance.complete", domains=advanced_total
#             )
#     except Exception as exc:  # noqa: BLE001
#         logger.error("scheduler.cost_rollup.fatal", error=str(exc), exc_info=True)
 
 
# # ── §9.2 Business-hours filter ─────────────────────────────────────────────
 
 
# # 7-week ramp per Help Guide §Domains (Warming Schedule)
# # Week 1=10, 2=30, 3=50, 4=100, 5=200, 6=350, 7=500
# _WARMUP_RAMP: dict[int, int] = {1: 10, 2: 30, 3: 50, 4: 100, 5: 200, 6: 350, 7: 500}
# WARMING_SCHEDULE = [10, 30, 50, 100, 200, 350, 500]  # exported for UI display
 
 
# def _warmup_effective_cap(dom) -> int:
#     """FR-038: effective daily cap for a (possibly warming) domain."""
#     week = int(getattr(dom, "warmingWeek", 0) or 0)
#     base = int(getattr(dom, "dailySendLimit", 0) or 0) or 10_000
#     if 1 <= week <= 7:
#         return min(base, _WARMUP_RAMP[week])
#     return base
 
 
# async def advance_domain_warmup(db) -> int:
#     """FR-038: advance warmingWeek for domains warmed >= 7 days per week.
 
#     Called by the nightly maintenance job. A domain whose updatedAt is more
#     than 7 days old and whose warmingWeek is 1-4 moves to the next week;
#     week 5 means warm-up complete (full dailySendLimit applies).
#     Returns the number of domains advanced."""
#     result = await db.execute(
#         text(
#             'UPDATE "Domain" SET '
#             '  "warmingWeek" = "warmingWeek" + 1, '
#             '  "updatedAt" = now() '
#             'WHERE "warmingWeek" BETWEEN 1 AND 7 '
#             "  AND \"updatedAt\" < now() - interval '7 days'"
#         )
#     )
#     return result.rowcount or 0
 
 
# def _is_business_hours(now: datetime, tz_name: str | None) -> bool:
#     """Return True iff `now` falls inside recipient-local 9am-5pm, Mon-Fri.
 
#     If tz_name is None, defaults to America/New_York (US Eastern) — the most
#     common timezone for B2B cold outreach targets. If tz_name is unparseable,
#     falls back to UTC. local is always assigned before use (no UnboundLocalError).
#     """
#     local = now  # always assigned — fallback if zoneinfo fails
#     effective_tz = tz_name or "America/New_York"
#     try:
#         tz = zoneinfo.ZoneInfo(effective_tz)
#         local = now.astimezone(tz)
#     except Exception:  # noqa: BLE001 — unknown tz string, keep UTC fallback
#         local = now
#     if local.weekday() >= 5:  # Sat=5, Sun=6
#         return False
#     start, end = time(9, 0), time(17, 0)
#     return start <= local.time() <= end
 
 
# # ── §9.3 PARTIAL throttle (deterministic hash) ─────────────────────────────
 
 
# def _partial_throttle_passes(prospect_id: str, tick_bucket: int) -> bool:
#     """Return True iff this PARTIAL-enrichment prospect should be sent this tick.
 
#     Per migration §9.3 L1309-1316: hash(prospect_id + tick_bucket) % 100 must
#     be < SCHEDULER_PARTIAL_PER_TICK_CAP (default 5). The hash is deterministic
#     so retries within the same tick window select the same prospects.
#     """
#     settings = get_settings()
#     cap = settings.SCHEDULER_PARTIAL_PER_TICK_CAP
#     hash_input = f"{prospect_id}:{tick_bucket}"
#     bucket = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16) % 100
#     return bucket < cap


# def _is_batch_send_enabled() -> bool:
#     """True if BatchSend should be used — single global switch
#     (settings.BATCH_SEND_ENABLED). Shared by run_tick() (automatic tick)
#     and SchedulerService.manual_tick() (the UI's "Run Tick"/"Trigger Now"
#     buttons) so both paths always agree on whether BatchSend is on.
#     """
#     return get_settings().BATCH_SEND_ENABLED


# # ── §9.5 MailBridge dispatch ───────────────────────────────────────────────
 
 
# async def _resolve_mailbridge_config(
#     db: AsyncSession, user_id: str | None
# ) -> MailBridgeConfig | None:
#     """Resolve the MailBridgeConfig to use for a given user.
 
#     Per SAAS2-USER-BE §G:
#       1. If user_id is provided, look for an active MailBridgeConfig owned by
#          that user (MailBridgeConfig.owner_user_id == user_id). This requires
#          BE-A to have added the owner_user_id column to MailBridgeConfig.
#       2. Fall back to a tenant-level config (owner_user_id IS NULL or column
#          does not exist yet) — preserves the pre-user-behaviour.
#       3. Return None if no active config exists.
 
#     The lookup is defensive: if MailBridgeConfig does not yet expose
#     owner_user_id (BE-A migration 0004 not yet applied), the per-user filter
#     is skipped and the tenant-level fallback is used.
#     """
#     # Per-user lookup — only if the column exists on the model.
#     has_owner_col = hasattr(MailBridgeConfig, "owner_user_id")
#     if user_id and has_owner_col:
#         try:
#             result = await db.execute(
#                 select(MailBridgeConfig)
#                 .where(MailBridgeConfig.isActive.is_(True))
#                 .where(getattr(MailBridgeConfig, "owner_user_id") == user_id)
#                 .limit(1)
#             )
#             cfg = result.scalar_one_or_none()
#             if cfg is not None:
#                 return cfg
#         except Exception as exc:  # noqa: BLE001 — fall back to tenant-level
#             logger.warning(
#                 "scheduler.mailbridge.per_user_lookup_failed",
#                 user_id=user_id, error=str(exc),
#             )
 
#     # Tenant-level fallback.
#     result = await db.execute(
#         select(MailBridgeConfig)
#         .where(MailBridgeConfig.isActive.is_(True))
#         .limit(1)
#     )
#     return result.scalar_one_or_none()

# def _is_html_body(body: str | None) -> bool:
#     """True when body was authored in the Tiptap RTE (already HTML).

#     The RTE always opens content with a block-level HTML tag. We also require
#     at least one closing tag to avoid false-positives on plain text that
#     happens to start with '<'.
#     """
#     if not body:
#         return False
#     s = body.lstrip()
#     return s.startswith("<") and any(
#         marker in body
#         for marker in (
#             "</p>", "</h", "<br", "</ul>", "</ol>",
#             "</li>", "</strong>", "</em>",
#         )
#     )


# def _strip_html_text(html: str) -> str:
#     """Strip HTML tags and collapse whitespace → plain-text fallback."""
#     import re as _re
#     text = _re.sub(r"<[^>]+>", " ", html)
#     return _re.sub(r"\s+", " ", text).strip() 
 
# async def _resolve_recipient_email(db: AsyncSession, sequence: Sequence) -> tuple[Any, str]:
#     """Resolve + decrypt the recipient email for a sequence's prospect.

#     Extracted verbatim from the original _send_via_mailbridge body (no
#     behaviour change) so both the single-send path and the BatchSend
#     message-builder below share one implementation. Returns (prospect,
#     recipient_email); raises RuntimeError on missing prospect/email, same
#     as before.
#     """
#     prospect_result = await db.execute(
#         select(Prospect).where(Prospect.id == sequence.prospectId)
#     )
#     prospect = prospect_result.scalar_one_or_none()
#     if prospect is None or not prospect.email:
#         raise RuntimeError(
#             f"Prospect {sequence.prospectId} missing or has no email"
#         )

#     # Wiring audit (Task 2-e): the Prospect.email column is encrypted at rest
#     # when ENCRYPTION_KEY is set (production). Decrypt via PiiService before
#     # building the payload (mirrors SequenceService.send_email +
#     # ReplyDraftService.auto_reply). Best-effort: fall back to the stored
#     # value when decryption fails (legacy plaintext / dev mode without key).
#     raw_email = prospect.email
#     if not getattr(prospect, "anonymized", False):
#         try:
#             from app.services.pii_service import PiiService

#             recipient_email = PiiService().decrypt_field(raw_email) or raw_email
#         except Exception:  # noqa: BLE001 — best-effort
#             recipient_email = raw_email
#     else:
#         recipient_email = raw_email
#     if not recipient_email:
#         raise RuntimeError(
#             f"Prospect {sequence.prospectId} email is empty after decrypt"
#         )
#     return prospect, recipient_email


# async def _domain_preflight_gate(db: AsyncSession, config: MailBridgeConfig | None) -> None:
#     """Run the FR-039 DNS gate + FR-038 warm-up gate for `config`'s bound
#     Domain. Extracted verbatim from the original _send_via_mailbridge body
#     — same exceptions, same conditions, no behaviour change. Shared by the
#     single-send path and the BatchSend grouping path for run_tick (NOT
#     used by manual_tick's batch path — manual_tick intentionally only
#     checks quota, see its docstring)."""
#     if config is None or not getattr(config, "domainId", None):
#         return
#     from app.models.config_models import Domain as _Domain

#     dom = (
#         await db.execute(select(_Domain).where(_Domain.id == config.domainId))
#     ).scalar_one_or_none()
#     if dom is not None and dom.lastChecked is not None:
#         failing = [
#             name
#             for name, ok in (
#                 ("SPF", dom.spfStatus),
#                 ("DKIM", dom.dkimStatus),
#                 ("DMARC", dom.dmarcStatus),
#             )
#             if not ok
#         ]
#         if failing:
#             raise RuntimeError(
#                 f"DNS verification failing for domain '{dom.domainName}': "
#                 f"{', '.join(failing)}. Fix the DNS records and re-verify "
#                 "before sending (FR-039)."
#             )

#     if dom is not None:
#         week = int(getattr(dom, "warmingWeek", 0) or 0)
#         if 1 <= week < 2:
#             raise RuntimeError(
#                 f"Domain '{dom.domainName}' has only completed "
#                 f"{week} week(s) of warm-up. At least 2 weeks are "
#                 "required before sending. Use the Auto-Warm button on "
#                 "the Domains page to advance the schedule, or wait for "
#                 "the nightly auto-advance."
#             )

#     if dom is not None:
#         effective_cap = _warmup_effective_cap(dom)
#         sent_today = (
#             await db.execute(
#                 text(
#                     'SELECT COUNT(*) FROM "Sequence" s '
#                     'JOIN "Campaign" c ON c.id = s."campaignId" '
#                     "WHERE c.\"domainId\" = :dom_id "
#                     "  AND s.\"sentAt\" >= date_trunc('day', now())"
#                 ),
#                 {"dom_id": dom.id},
#             )
#         ).scalar() or 0
#         if int(sent_today) >= effective_cap:
#             raise RuntimeError(
#                 f"Warm-up daily cap reached for domain "
#                 f"'{dom.domainName}' ({sent_today}/{effective_cap}, "
#                 f"week {dom.warmingWeek}). Deferring to tomorrow "
#                 "(FR-038)."
#             )


# async def _build_email_body(
#     db: AsyncSession, sequence: Sequence, prospect: Prospect
# ) -> tuple[str, str]:
#     """Build (body_html_final, body_text_final) with the CAN-SPAM footer.

#     Extracted verbatim from the original _send_via_mailbridge body (no
#     behaviour change) — shared by the single-send path and the BatchSend
#     message-builder. NOT used by manual_tick's batch path, which uses
#     MailBridgeService._prepare_body_for_send() instead, to stay identical
#     to a per-row manual send.
#     """
#     body_text = sequence.bodyCopy or ""
#     is_html = _is_html_body(body_text)

#     needs_footer = (
#         "unsubscribe" not in body_text.lower()
#         or "physical" not in body_text.lower()
#         and "address" not in body_text.lower()
#     )
#     if needs_footer:
#         try:
#             from app.utils.tenant_context import resolve_tenant_slug as _rts
#             from app.core.config import get_settings as _gs
#             _tenant_slug = await _rts(db)
#             _prospect_token = getattr(prospect, "unsubscribeToken", None) or ""
#             _base = _gs().BASE_DOMAIN
#             _unsub_url = (
#                 f"https://{_base}/api/v1/public/unsubscribe"
#                 f"?token={_prospect_token}&tenant_slug={_tenant_slug}"
#                 if _prospect_token and _tenant_slug
#                 else ""
#             )

#             if is_html:
#                 _unsub_link = (
#                     f' <a href="{_unsub_url}" '
#                     'style="color:#6b7280;text-decoration:underline">Unsubscribe</a>'
#                     if _unsub_url
#                     else ""
#                 )
#                 _html_footer = (
#                     '<hr style="border:0;border-top:1px solid #e5e7eb;margin:24px 0">'
#                     '<p style="color:#6b7280;font-size:11px;line-height:1.5;margin:0">'
#                     f"This email was sent by an authorised OUTRENA user.{_unsub_link}"
#                     "</p>"
#                 )
#                 body_text = body_text + _html_footer
#             else:
#                 _footer_lines = [
#                     "",
#                     "---",
#                     "This email was sent by an authorised OUTRENA user.",
#                 ]
#                 if _unsub_url:
#                     _footer_lines.append(f"Unsubscribe: {_unsub_url}")
#                 body_text = body_text + "\n".join(_footer_lines)

#         except Exception:  # noqa: BLE001 — footer is best-effort, never block send
#             pass

#     if is_html:
#         body_html_final = body_text
#         body_text_final = _strip_html_text(body_text)
#     else:
#         body_html_final = body_text
#         body_text_final = body_text

#     return body_html_final, body_text_final


# def _resolve_ext_user_id(config: MailBridgeConfig | None, user_id: str | None) -> str | None:
#     """Identity propagation resolution — extracted verbatim, shared by both
#     the single-send path and the BatchSend message-builder. Priority:
#       1. config.mailbridge_external_user_id — ONLY when the config is
#          explicitly owned by the sending user.
#       2. user_id — the Keycloak UUID of the sequence owner.
#     """
#     config_owner = getattr(config, "owner_user_id", None) if config else None
#     config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
#     return (
#         config_ext_id
#         if (config_owner and config_owner == user_id and config_ext_id)
#         else user_id
#     )


# async def _send_via_mailbridge(
#     db: AsyncSession,
#     config: MailBridgeConfig | None,
#     sequence: Sequence,
#     user_id: str | None = None,
# ) -> str:
#     """Send one sequence via MailBridge and return the messageId.
 
#     Per migration §9.5 L1339-1353. Uses httpx.AsyncClient with a 30s timeout.
#     The prospect is loaded from the same session to resolve the recipient
#     email + timezone. On HTTP 4xx/5xx or any network error, raises
#     RuntimeError so the caller can mark the sequence as skipped.
 
#     Stub-safe: if no `config` is supplied (dev/CI), returns a deterministic
#     stub messageId so tests can run without a MailBridge instance.

#     UNCHANGED BEHAVIOUR: this function's externally-visible logic (order of
#     checks, exceptions raised, payload shape, sentinel returns) is identical
#     to before BatchSend — it now calls out to the shared helpers above
#     (_resolve_recipient_email / _domain_preflight_gate / _build_email_body /
#     _resolve_ext_user_id) instead of inlining that logic, purely so the
#     BatchSend grouping path (below, in run_tick) can reuse the exact same
#     business logic rather than reimplementing it. This is the code path
#     used when BatchSend is off (default), and remains the fallback path
#     per-group when BatchSend's send_batch() returns None.
#     """
#     prospect, recipient_email = await _resolve_recipient_email(db, sequence)
#     settings = get_settings()

#     await _domain_preflight_gate(db, config)

#     # Dev/CI stub: no config + no default URL → deterministic fake id.
#     if config is None and not settings.MAILBRIDGE_DEFAULT_URL:
#         msg_id = f"stub-{sequence.id}@outrena.local"
#         await _record_usage_send_safe(db, sequence)
#         return msg_id

#     base_url = (config.baseUrl if config else "") or settings.MAILBRIDGE_DEFAULT_URL
#     body_html_final, body_text_final = await _build_email_body(db, sequence, prospect)

#     payload = {
#         "to": [recipient_email],
#         "subject": sequence.subjectLine or "",
#         "body_html": body_html_final,
#         "body_text": body_text_final,
#     }
#     ext_user_id = _resolve_ext_user_id(config, user_id)
#     if ext_user_id:
#         payload["external_user_id"] = ext_user_id
 
#     # Build auth headers. MailBridge tenancy mode requires a Bearer
#     # API key (mb_live_...) from POST /platform/register.
#     api_key = (
#         getattr(config, "mailbridge_api_key", None) if config else None
#     ) or settings.MAILBRIDGE_API_KEY
#     headers: dict[str, str] = {"Content-Type": "application/json"}
#     if api_key:
#         headers["Authorization"] = f"Bearer {api_key}"
 
#     timeout_s = float(settings.MAILBRIDGE_TIMEOUT_SECONDS)
#     async with httpx.AsyncClient(timeout=timeout_s) as client:
#         resp = await client.post(
#             f"{base_url.rstrip('/')}/outbound/send",
#             json=payload,
#             headers=headers,
#         )
#         if resp.status_code >= 400:
#             raise RuntimeError(
#                 f"MailBridge returned HTTP {resp.status_code}: {resp.text[:200]}"
#             )
#         data = resp.json()
#         # MailBridge returns snake_case "message_id"; fall back to camelCase
#         # for backward compatibility with older/stub MailBridge instances.
#         msg_id = data.get("message_id") or data.get("messageId", "")
#         if not msg_id:
#             raise RuntimeError("MailBridge response missing message_id")
 
#     # Stamp who actually sent this and which MailBridge identity was used.
#     # These are the values the reply-poller relies on — see reply_poller.py.
#     if user_id:
#         sequence.sent_by_user_id = user_id
#     if ext_user_id:
#         sequence.sent_via_external_user_id = ext_user_id
 
#     # Best-effort: record usage_event(email_send) for per-tenant cost roll-ups.
#     # (Mirrors MailBridgeService.send._record_usage_send so the scheduler-tick
#     # path doesn't silently bypass cost tracking.)
#     await _record_usage_send_safe(db, sequence)
#     return msg_id


# async def _build_batch_send_message(
#     db: AsyncSession, sequence: Sequence, config: MailBridgeConfig | None, user_id: str | None
# ):
#     """Build one BatchSendMessage for `sequence`, reusing the exact same
#     recipient-resolution / domain-preflight / footer / identity-propagation
#     logic as the single-send path. Returns raises if the sequence should be
#     skipped rather than batched — caller treats that the same as any other
#     pre-flight skip.
#     """
#     from app.schemas.mailbridge import BatchSendMessage

#     prospect, recipient_email = await _resolve_recipient_email(db, sequence)
#     await _domain_preflight_gate(db, config)
#     body_html_final, body_text_final = await _build_email_body(db, sequence, prospect)
#     ext_user_id = _resolve_ext_user_id(config, user_id)

#     return BatchSendMessage(
#         sequenceId=sequence.id,
#         to=recipient_email,
#         subject=sequence.subjectLine or "",
#         body_html=body_html_final,
#         body_text=body_text_final,
#         external_user_id=ext_user_id,
#     )


# def _build_batch_callback_url(tenant_slug: str | None) -> str:
#     """Per-tenant callback URL MailBridge should POST batch results to.

#     Outrena resolves tenant identity by subdomain (TenantMiddleware —
#     app/middleware/tenant_middleware.py::_extract_slug), same as the
#     existing /mailbridge/webhook endpoint. Falls back to
#     settings.OUTRENA_BATCH_CALLBACK_URL only when a tenant slug genuinely
#     can't be resolved.
#     """
#     settings = get_settings()
#     if not tenant_slug:
#         return settings.OUTRENA_BATCH_CALLBACK_URL
#     return f"https://{tenant_slug}.{settings.BASE_DOMAIN}/api/v1/mailbridge/batch-complete"


# async def _dispatch_batch_groups(
#     session: AsyncSession,
#     schema_name: str,
#     batch_groups: dict[tuple, dict[str, Any]],
#     quota_service: UserEmailQuotaService,
#     started: datetime,
# ) -> tuple[int, int]:
#     """Dispatch every (owner_user_id, config_id) group as one BatchSend
#     call. Returns (sent, skipped) counts to fold into run_tick's summary.

#     Per group:
#       1. Build a BatchSendMessage per sequence (same business logic as a
#          single send). A sequence that fails to build (e.g. missing
#          prospect email, DNS gate) is skipped + skip-logged individually,
#          same as the legacy per-row path.
#       2. Call MailBridgeService().send_batch() for the survivors.
#       3. On success: mark every dispatched sequence BatchPending (NOT
#          Sent — Sent is set later by the completion webhook handler).
#       4. On failure (None): fall back to the original per-row send loop
#          for exactly this group's sequences.
#     """
#     from app.features.mailbridge.service import MailBridgeService

#     settings = get_settings()
#     send_service = MailBridgeService()

#     tenant_slug = ""
#     try:
#         from app.utils.tenant_context import resolve_tenant_slug
#         tenant_slug = await resolve_tenant_slug(session)
#     except Exception as exc:  # noqa: BLE001
#         logger.warning("scheduler.batch_dispatch.tenant_resolve_failed", error=str(exc))
#     callback_url = _build_batch_callback_url(tenant_slug)

#     sent = 0
#     skipped = 0

#     for (seq_owner, _config_id), group in batch_groups.items():
#         config = group["config"]
#         group_sequences: list[Sequence] = group["sequences"]

#         messages = []
#         buildable_sequences = []
#         for seq in group_sequences:
#             try:
#                 msg = await _build_batch_send_message(session, seq, config, seq_owner)
#                 messages.append(msg)
#                 buildable_sequences.append(seq)
#             except Exception as exc:  # noqa: BLE001 — per-seq isolation, same as legacy path
#                 skipped += 1
#                 logger.warning(
#                     "scheduler.batch_dispatch.message_build_failed",
#                     schema=schema_name,
#                     sequence_id=seq.id,
#                     error=str(exc),
#                 )
#                 await write_skip_log(
#                     session,
#                     run_id=None,
#                     sequence_id=seq.id,
#                     campaign_id=getattr(seq, "campaignId", None),
#                     prospect_id=getattr(seq, "prospectId", None),
#                     skip_reason="send_error",
#                     detail=str(exc)[:500],
#                 )

#         if not messages:
#             continue

#         ack = await send_service.send_batch(
#             db=session,
#             messages=messages,
#             callback_url=callback_url,
#             user_id=(seq_owner if seq_owner != "system" else None),
#         )

#         if ack is not None:
#             # Dispatched — mark BatchPending, NOT Sent. sentAt/Sent is set
#             # by the completion webhook handler once MailBridge confirms
#             # delivery.
#             seq_ids = [s.id for s in buildable_sequences]
#             await session.execute(
#                 text(
#                     'UPDATE "Sequence" SET status = \'BatchPending\', '
#                     '"mailBridgeBatchId" = :batch_id '
#                     'WHERE id = ANY(:seq_ids)'
#                 ),
#                 {"batch_id": ack.batchId, "seq_ids": seq_ids},
#             )
#             sent += len(buildable_sequences)
#             logger.info(
#                 "scheduler.batch_dispatch.accepted",
#                 schema=schema_name,
#                 batch_id=ack.batchId,
#                 owner=seq_owner,
#                 count=len(buildable_sequences),
#             )
#             continue

#         # send_batch returned None — fall back to the proven per-row path
#         # for exactly this group, exactly as run_tick's legacy loop does.
#         logger.warning(
#             "scheduler.batch_dispatch.fallback_to_per_row",
#             schema=schema_name,
#             owner=seq_owner,
#             count=len(buildable_sequences),
#         )
#         for seq in buildable_sequences:
#             try:
#                 msg_id = await _send_via_mailbridge(session, config, seq, user_id=seq_owner)
#                 await session.execute(
#                     text(
#                         "UPDATE \"Sequence\" SET status = 'Sent', "
#                         "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
#                         "WHERE id = :seq_id"
#                     ),
#                     {
#                         "sent_at": datetime.now(timezone.utc),
#                         "msg_id": msg_id,
#                         "seq_id": seq.id,
#                     },
#                 )
#                 sent += 1
#                 camp_id_for_log = getattr(seq, "campaignId", None)
#                 if camp_id_for_log:
#                     await upsert_daily_sent(
#                         session,
#                         campaign_id=camp_id_for_log,
#                         sent_date=started.date(),
#                         increment=1,
#                     )
#                 if seq_owner and seq_owner != "system":
#                     try:
#                         await quota_service.record_send(session, seq_owner, count=1)
#                     except Exception as exc:  # noqa: BLE001 — best-effort
#                         logger.warning(
#                             "scheduler.sequence.quota_record_failed",
#                             schema=schema_name,
#                             sequence_id=seq.id,
#                             user_id=seq_owner,
#                             error=str(exc),
#                         )
#             except Exception as exc:  # noqa: BLE001 — per-seq isolation
#                 skipped += 1
#                 logger.warning(
#                     "scheduler.sequence.send_failed",
#                     schema=schema_name,
#                     sequence_id=seq.id,
#                     error=str(exc),
#                 )
#                 await write_skip_log(
#                     session,
#                     run_id=None,
#                     sequence_id=seq.id,
#                     campaign_id=getattr(seq, "campaignId", None),
#                     prospect_id=getattr(seq, "prospectId", None),
#                     skip_reason="send_error",
#                     detail=str(exc)[:500],
#                 )

#     return sent, skipped
 
 
# async def _record_usage_send_safe(db: AsyncSession, sequence: Sequence) -> None:
#     """Fire-and-forget: record one usage_event(email_send) row.
 
#     Wiring audit (Task 2-e): scheduler_service._send_via_mailbridge
#     previously bypassed MailBridgeService.send (it makes its own httpx call
#     per migration §9.5), so the per-tenant cost roll-up never saw
#     scheduler-tick sends. This helper delegates to the same
#     UsageService.record_email_send path used by MailBridgeService.send,
#     deriving the tenant slug from the session's search_path. Best-effort —
#     failures are logged + swallowed so a usage write never blocks the send.
#     """
#     try:
#         from app.utils.tenant_context import resolve_tenant_slug
#         tenant = await resolve_tenant_slug(db)
#         if not tenant:
#             return
#         from app.features.usage.service import UsageService
#         await UsageService().record_email_send(
#             tenant=tenant,
#             user_id=getattr(sequence, "owner_user_id", None) or "system",
#             metadata={"source": "scheduler.run_tick", "sequence_id": sequence.id},
#         )
#     except Exception as exc:  # noqa: BLE001
#         logger.warning(
#             "scheduler.send.usage_record_failed",
#             sequence_id=getattr(sequence, "id", None),
#             error=str(exc),
#         )
 
 
# # ── §9.6 Single-tenant + multi-tenant ticks ────────────────────────────────
 
 
# async def run_tick(schema_name: str) -> dict[str, Any]:
#     """Run a single scheduler tick against one tenant schema.
 
#     Per migration §9.4-9.6 + §10 Phase 5 L1502-1523. Steps:
#       1. SET search_path TO "{schema}", public
#       2. SELECT Sequences WHERE status=Scheduled AND touchNumber<=6
#       3. For each candidate:
#          a. Load prospect; skip if suppressed or no email.
#          b. Business-hours filter (§9.2) — skip if outside 9am-5pm local.
#          c. PARTIAL throttle (§9.3) — skip if hash falls outside this tick's cap.
#          d. Resolve MailBridgeConfig (first active row).
#          e. Call _send_via_mailbridge → on success, set status=Sent + sentAt
#             + mailBridgeMessageId. On failure, log + count as skipped.
#       4. Update SchedulerStatus row (id=1) with new counters + nextTickAt.
#       5. Commit + return summary dict.
#     """
#     settings = get_settings()
#     started = datetime.now(timezone.utc)
#     tick_bucket = int(started.timestamp()) // settings.SCHEDULER_TICK_SECONDS
 
#     summary: dict[str, Any] = {
#         "schema": schema_name,
#         "candidates": 0,
#         "sent": 0,
#         "skipped": 0,
#         "started_at": started.isoformat(),
#     }
 
#     async with AsyncSessionLocal() as session:
#         await session.execute(text(f'SET search_path TO "{schema_name}", public'))
 
#         # ── Step 1: load SchedulerStatus row (create if absent) ──────────
#         # FIX: wrap in try/except — SchedulerStatus table may not exist in
#         # partially-provisioned tenant schemas (migration 0002 not yet run).
#         # In that case skip the status tracking but still attempt sends.
#         status_row = None
#         try:
#             status_result = await session.execute(
#                 select(SchedulerStatus).where(SchedulerStatus.id == 1)
#             )
#             status_row = status_result.scalar_one_or_none()
#             if status_row is None:
#                 status_row = SchedulerStatus(id=1, isRunning=False)
#                 session.add(status_row)
#                 await session.flush()
#             status_row.isRunning = True
#             await session.commit()
#         except Exception as _ss_exc:
#             err_str = str(_ss_exc)
#             if "does not exist" in err_str or "UndefinedTable" in err_str:
#                 await session.rollback()
#                 logger.warning(
#                     "scheduler.tick.scheduler_status_missing",
#                     schema=schema_name,
#                     hint="Run alembic upgrade head to create SchedulerStatus table",
#                 )
#             else:
#                 raise
 
#         sent = 0
#         skipped = 0
#         try:
#             # ── Step 2: load Scheduled sequences with touchNumber<=6 ─────
#             # Guard against UndefinedTableError on a fresh tenant schema
#             # (tables may not exist yet) or InFailedSQLTransactionError
#             # if a prior query in this session aborted the transaction.
#             # Roll back and skip cleanly rather than poisoning the session.
#             try:
#                 seq_result = await session.execute(
#                     select(Sequence)
#                     .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
#                     .where(Sequence.touchNumber <= 6)
#                     .order_by(Sequence.createdAt.asc())
#                     .limit(500)
#                 )
#                 sequences = list(seq_result.scalars().all())
#             except Exception as table_exc:
#                 err_str = str(table_exc)
#                 if "UndefinedTableError" in err_str or "InFailedSQLTransaction" in err_str or "does not exist" in err_str:
#                     import structlog as _sl
#                     _sl.get_logger(__name__).warning(
#                         "scheduler.tick.schema_not_ready",
#                         schema=schema_name,
#                         error=err_str[:200],
#                     )
#                     await session.rollback()
#                     summary["skipped"] = 0
#                     summary["sent"] = 0
#                     return summary
#                 raise
#             sequences = list(sequences) if not isinstance(sequences, list) else sequences
#             summary["candidates"] = len(sequences)
 
#             # Pre-load first active MailBridgeConfig for this schema (kept as
#             # a tenant-level fallback for sequences without an owner_user_id).
#             cfg_result = await session.execute(
#                 select(MailBridgeConfig)
#                 .where(MailBridgeConfig.isActive.is_(True))
#                 .limit(1)
#             )
#             tenant_default_config = cfg_result.scalar_one_or_none()
 
#             quota_service = UserEmailQuotaService()
#             batch_send_enabled = _is_batch_send_enabled()

#             # BatchSend: sequences that pass all pre-flight checks are
#             # collected here (keyed by (owner_user_id, config_id)) instead
#             # of being dispatched immediately, when batch_send_enabled is
#             # True. Left empty and unused when the flag is False — zero
#             # behaviour change for the default configuration.
#             batch_groups: dict[tuple, dict[str, Any]] = {}

#             for seq in sequences:
#                 try:
#                     # ── Load prospect once per sequence (cheap with session cache) ──
#                     prospect_result = await session.execute(
#                         select(Prospect).where(Prospect.id == seq.prospectId)
#                     )
#                     prospect = prospect_result.scalar_one_or_none()
 
#                     # Skip suppressed / no-email prospects
#                     # Layer 1: Prospect-level suppression flag
#                     if prospect is None or not prospect.email:
#                         skipped += 1
#                         await write_skip_log(
#                             session,
#                             run_id=None,
#                             sequence_id=seq.id,
#                             campaign_id=getattr(seq, "campaignId", None),
#                             prospect_id=seq.prospectId,
#                             skip_reason="no_email",
#                             detail="Prospect not found or has no email address",
#                         )
#                         continue
#                     if prospect.suppressed:
#                         skipped += 1
#                         await write_skip_log(
#                             session,
#                             run_id=None,
#                             sequence_id=seq.id,
#                             campaign_id=getattr(seq, "campaignId", None),
#                             prospect_id=seq.prospectId,
#                             skip_reason="suppressed",
#                             detail="Prospect suppression flag is set",
#                         )
#                         continue

#                     # Layer 2: Email-level suppression — catches duplicate Prospect
#                     # rows and future imports of the same address.
#                     _sched_email_lower = (prospect.email or "").strip().lower()
#                     if _sched_email_lower:
#                         try:
#                             from sqlalchemy import text as _sched_t
#                             _sched_es = await session.execute(
#                                 _sched_t(
#                                     'SELECT 1 FROM "EmailSuppression" '
#                                     'WHERE email = :email LIMIT 1'
#                                 ),
#                                 {"email": _sched_email_lower},
#                             )
#                             if _sched_es.fetchone() is not None:
#                                 skipped += 1
#                                 await write_skip_log(
#                                     session,
#                                     run_id=None,
#                                     sequence_id=seq.id,
#                                     campaign_id=getattr(seq, "campaignId", None),
#                                     prospect_id=seq.prospectId,
#                                     skip_reason="suppressed",
#                                     detail=f"Email {_sched_email_lower} is on suppression list",
#                                 )
#                                 continue
#                         except Exception:  # noqa: BLE001
#                             # EmailSuppression table may not exist yet — fail open.
#                             pass

#                     # ── Step 3a: business-hours filter (§9.2) ─────────────
#                     if not _is_business_hours(started, prospect.timezone):
#                         skipped += 1
#                         await write_skip_log(
#                             session,
#                             run_id=None,
#                             sequence_id=seq.id,
#                             campaign_id=getattr(seq, "campaignId", None),
#                             prospect_id=seq.prospectId,
#                             skip_reason="business_hours",
#                             detail=f"Outside 9am-5pm in timezone {prospect.timezone or 'UTC'}",
#                         )
#                         continue

#                     # ── Step 3b: PARTIAL throttle (§9.3) ──────────────────
#                     if (
#                         prospect.enrichmentTier == EnrichmentTier.PARTIAL
#                         and not _partial_throttle_passes(prospect.id, tick_bucket)
#                     ):
#                         skipped += 1
#                         await write_skip_log(
#                             session,
#                             run_id=None,
#                             sequence_id=seq.id,
#                             campaign_id=getattr(seq, "campaignId", None),
#                             prospect_id=seq.prospectId,
#                             skip_reason="warmup_cap",
#                             detail="PARTIAL throttle hash did not pass for this tick bucket",
#                         )
#                         continue

#                     # ── Step 3b': per-user quota enforcement (SAAS2-USER-BE §G) ──
#                     # For the background scheduler, the "sender" is the sequence
#                     # owner — the person whose MailBridge account will be used.
#                     # sent_by_user_id is stamped inside _send_via_mailbridge on
#                     # success (same value as seq_owner for scheduler-driven sends).
#                     seq_owner = getattr(seq, "owner_user_id", None) or "system"
#                     if seq_owner and seq_owner != "system":
#                         try:
#                             can_send, reason = await quota_service.check_can_send(
#                                 session, seq_owner, count=1
#                             )
#                         except Exception as exc:  # noqa: BLE001 — never abort the tick
#                             can_send, reason = False, f"quota_check_error: {exc}"
#                         if not can_send:
#                             skipped += 1
#                             logger.info(
#                                 "scheduler.sequence.quota_exceeded",
#                                 schema=schema_name,
#                                 sequence_id=seq.id,
#                                 user_id=seq_owner,
#                                 reason=reason,
#                             )
#                             await write_skip_log(
#                                 session,
#                                 run_id=None,
#                                 sequence_id=seq.id,
#                                 campaign_id=getattr(seq, "campaignId", None),
#                                 prospect_id=seq.prospectId,
#                                 skip_reason="quota_exceeded",
#                                 detail=str(reason),
#                             )
#                             continue
#                     else:
#                         reason = "ok"
 
#                     # ── Step 3c: per-user MailBridge resolution (SAAS2-USER-BE §G) ──
#                     # Use the sequence owner's MailBridge config (their connected
#                     # mailbox); fall back to the tenant-level default only when the
#                     # owner has no personal config registered.
#                     if seq_owner and seq_owner != "system":
#                         config = await _resolve_mailbridge_config(session, seq_owner)
#                     else:
#                         config = tenant_default_config
#                     if config is None:
#                         config = tenant_default_config
 
#                     # ── Step 3d: MailBridge dispatch (§9.5) ───────────────
#                     if batch_send_enabled:
#                         # BatchSend path: collect into a group keyed by
#                         # (owner_user_id, config_id) — different sequence
#                         # owners can have different connected mailboxes.
#                         # All the per-row gates above (suppression,
#                         # business hours, PARTIAL throttle, quota
#                         # pre-check) have already run for this sequence —
#                         # batching only changes HOW the dispatch HTTP call
#                         # is made.
#                         group_key = (seq_owner, getattr(config, "id", None) if config else None)
#                         batch_groups.setdefault(group_key, {"config": config, "sequences": []})
#                         batch_groups[group_key]["sequences"].append(seq)
#                         continue

#                     # ── Legacy per-row dispatch (BatchSend off, the
#                     # default) — completely unchanged from before
#                     # BatchSend existed. ─────────────────────────────────
#                     # _send_via_mailbridge stamps seq.sent_by_user_id and
#                     # seq.sent_via_external_user_id on the sequence row so the
#                     # reply-poller can poll the correct MailBridge inbox.
#                     msg_id = await _send_via_mailbridge(session, config, seq, user_id=seq_owner)
#                     # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError across schemas)
#                     await session.execute(
#                         text(
#                             "UPDATE \"Sequence\" SET status = 'Sent', "
#                             "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
#                             "WHERE id = :seq_id"
#                         ),
#                         {
#                             "sent_at": datetime.now(timezone.utc),
#                             "msg_id": msg_id,
#                             "seq_id": seq.id,
#                         },
#                     )
#                     sent += 1

#                     # ── Step 3e: record daily sent aggregation ────────────
#                     camp_id_for_log = getattr(seq, "campaignId", None)
#                     if camp_id_for_log:
#                         await upsert_daily_sent(
#                             session,
#                             campaign_id=camp_id_for_log,
#                             sent_date=started.date(),
#                             increment=1,
#                         )

#                     # ── Step 3f: record send against per-user quota ───────
#                     if seq_owner and seq_owner != "system":
#                         try:
#                             await quota_service.record_send(session, seq_owner, count=1)
#                         except Exception as exc:  # noqa: BLE001 — best-effort
#                             logger.warning(
#                                 "scheduler.sequence.quota_record_failed",
#                                 schema=schema_name,
#                                 sequence_id=seq.id,
#                                 user_id=seq_owner,
#                                 error=str(exc),
#                             )
#                 except Exception as exc:  # noqa: BLE001 — per-seq isolation
#                     skipped += 1
#                     logger.warning(
#                         "scheduler.sequence.send_failed",
#                         schema=schema_name,
#                         sequence_id=seq.id,
#                         error=str(exc),
#                     )
#                     await write_skip_log(
#                         session,
#                         run_id=None,
#                         sequence_id=seq.id,
#                         campaign_id=getattr(seq, "campaignId", None),
#                         prospect_id=getattr(seq, "prospectId", None),
#                         skip_reason="send_error",
#                         detail=str(exc)[:500],
#                     )

#             # ── Step 3d(batch): dispatch every group collected above ─────
#             # Only reached when BatchSend is enabled and at least one
#             # sequence passed all pre-flight checks. Each group becomes one
#             # POST /outbound/batch-send call; a group that fails to dispatch
#             # falls back to the original per-row loop for exactly that
#             # group — never for the whole tick.
#             if batch_send_enabled and batch_groups:
#                 batch_sent, batch_skipped = await _dispatch_batch_groups(
#                     session, schema_name, batch_groups, quota_service, started
#                 )
#                 sent += batch_sent
#                 skipped += batch_skipped

#             await session.commit()
#         finally:
#             # ── Step 4: update SchedulerStatus counters + nextTickAt ─────
#             ended = datetime.now(timezone.utc)
#             if status_row is not None:
#                 status_row.isRunning = False
#                 status_row.lastTickAt = started
#                 status_row.sentSinceLastTick = sent
#                 status_row.skippedSinceLastTick = skipped
#                 status_row.nextTickAt = started + timedelta(
#                     seconds=settings.SCHEDULER_TICK_SECONDS
#                 )
#                 try:
#                     await session.commit()
#                 except Exception:  # noqa: BLE001
#                     await session.rollback()
 
#         summary["sent"] = sent
#         summary["skipped"] = skipped
#         summary["ended_at"] = ended.isoformat()
#         summary["duration_ms"] = int((ended - started).total_seconds() * 1000)
#         return summary
 
 
# async def _get_tenant_scheduler_config(schema_name: str) -> dict:
#     """Read scheduler.enabled and scheduler.tick_interval_minutes from
#     the tenant's SystemParameter table.

#     Returns a dict with:
#       enabled: bool   — True if scheduler should run for this tenant
#       tick_minutes: int — how often to send (in minutes, default 5)

#     Falls back to safe defaults if the table doesn't exist or the keys
#     are missing (fail-open: enabled=True, tick_minutes=5).
#     """
#     defaults = {"enabled": True, "tick_minutes": 5}
#     try:
#         async with AsyncSessionLocal() as session:
#             await session.execute(
#                 text(f'SET search_path TO "{schema_name}", public')
#             )

#             # Read scheduler.enabled
#             enabled_row = await session.execute(
#                 text(
#                     'SELECT value FROM "SystemParameter" '
#                     "WHERE key = 'scheduler.enabled' LIMIT 1"
#                 )
#             )
#             enabled_val = enabled_row.scalar()
#             if enabled_val is not None:
#                 defaults["enabled"] = enabled_val.lower().strip() not in (
#                     "false", "0", "no", "off", "disabled"
#                 )

#             # Read scheduler.tick_interval_minutes
#             interval_row = await session.execute(
#                 text(
#                     'SELECT value FROM "SystemParameter" '
#                     "WHERE key = 'scheduler.tick_interval_minutes' LIMIT 1"
#                 )
#             )
#             interval_val = interval_row.scalar()
#             if interval_val is not None:
#                 try:
#                     defaults["tick_minutes"] = max(1, int(float(interval_val)))
#                 except (ValueError, TypeError):
#                     pass

#     except Exception as exc:  # noqa: BLE001 — never block the tick
#         err = str(exc)
#         if "does not exist" not in err and "UndefinedTable" not in err:
#             logger.warning(
#                 "scheduler.tenant_config.read_failed",
#                 schema=schema_name,
#                 error=err[:200],
#             )
#     return defaults


# # Per-tenant last-tick timestamps — used to enforce per-tenant tick intervals
# # without needing a separate DB table. Resets on process restart (fine —
# # worst case all tenants tick once on restart regardless of interval).
# _tenant_last_tick: dict[str, datetime] = {}


# async def run_tick_all_tenants() -> dict[str, Any]:
#     """Run a tick across every ACTIVE tenant schema.

#     Per-tenant control:
#       scheduler.enabled = false  → tenant is completely skipped this tick
#       scheduler.tick_interval_minutes = N → tenant only ticks if at least
#         N minutes have passed since its last successful tick.

#     Per migration §9.6 L1362-1378: SELECT schema_name FROM public.tenants
#     WHERE status='ACTIVE' AND deleted_at IS NULL. Per-tenant failure is
#     logged + skipped — it never aborts the entire tick.
#     """
#     summary: dict[str, Any] = {
#         "tenants": 0,
#         "sent": 0,
#         "skipped": 0,
#         "failed_tenants": 0,
#         "tenants_disabled": 0,
#         "tenants_interval_skipped": 0,
#     }

#     # Query public.tenants directly via a raw connection (not the ORM)
#     # so we don't pollute the tenant-schema-bound session cache.
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
#         if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
#             raise
#         logger.warning("scheduler.tick.no_tenants_table", error=str(exc))
#         schemas = []

#     summary["tenant_count"] = len(schemas)
#     now = datetime.now(timezone.utc)

#     for schema in schemas:
#         try:
#             # ── Read per-tenant scheduler config from SystemParameter ──────
#             tenant_cfg = await _get_tenant_scheduler_config(schema)

#             # Gate 1: tenant has disabled their scheduler
#             if not tenant_cfg["enabled"]:
#                 summary["tenants_disabled"] += 1
#                 logger.debug(
#                     "scheduler.tenant.disabled",
#                     schema=schema,
#                 )
#                 continue

#             # Gate 2: tick interval not yet elapsed for this tenant
#             tick_interval_minutes = tenant_cfg["tick_minutes"]
#             last_tick = _tenant_last_tick.get(schema)
#             if last_tick is not None:
#                 elapsed_minutes = (now - last_tick).total_seconds() / 60
#                 if elapsed_minutes < tick_interval_minutes:
#                     summary["tenants_interval_skipped"] += 1
#                     logger.debug(
#                         "scheduler.tenant.interval_not_elapsed",
#                         schema=schema,
#                         elapsed_minutes=round(elapsed_minutes, 1),
#                         required_minutes=tick_interval_minutes,
#                     )
#                     continue

#             # ── Run tick for this tenant ───────────────────────────────────
#             tick_result = await run_tick(schema)
#             _tenant_last_tick[schema] = now  # record successful tick time
#             summary["tenants"] += 1
#             summary["sent"] += tick_result.get("sent", 0)
#             summary["skipped"] += tick_result.get("skipped", 0)

#         except Exception as exc:  # noqa: BLE001 — per-tenant isolation
#             summary["failed_tenants"] += 1
#             logger.error(
#                 "scheduler.tenant_failed",
#                 schema=schema,
#                 error=str(exc),
#                 exc_info=True,
#             )

#     return summary


# async def _resolve_manual_recipient_email(db: AsyncSession, seq: Sequence) -> str:
#     """Resolve + decrypt the recipient email for manual_tick's per-row loop.

#     Extracted verbatim from the original manual_tick body (no behaviour
#     change) so the BatchSend batch-message-builder below
#     (_build_manual_batch_message) produces the exact same recipient
#     resolution as the per-row fallback path.
#     """
#     to_email = ""
#     if seq.prospectId:
#         p_result = await db.execute(
#             select(Prospect).where(Prospect.id == seq.prospectId)
#         )
#         p = p_result.scalar_one_or_none()
#         if p is not None:
#             raw_email = getattr(p, "email", None) or ""
#             if raw_email and not getattr(p, "anonymized", False):
#                 try:
#                     from app.services.pii_service import PiiService

#                     to_email = (
#                         PiiService().decrypt_field(raw_email)
#                         or raw_email
#                     )
#                 except Exception:  # noqa: BLE001 — best-effort
#                     to_email = raw_email
#             elif raw_email:
#                 to_email = raw_email
#     return to_email


# async def _build_manual_batch_message(
#     db: AsyncSession,
#     seq: Sequence,
#     user_id: str | None,
#     mailbridge_service: MailBridgeService,
#     tenant_slug: str,
# ):
#     """Build one BatchSendMessage for manual_tick's BatchSend path.

#     Deliberately lighter-weight than run_tick's _build_batch_send_message:
#     no business-hours check, no PARTIAL throttle, no DNS/warmup gate — the
#     manual tick has never applied those, and batching must not silently
#     add gates that weren't there before. Only the daily quota gate
#     applies, same as before BatchSend existed.

#     Body is prepared via MailBridgeService._prepare_body_for_send() — the
#     exact same {{unsubscribe_url}} substitution + plain-text/RTE-HTML
#     conversion that MailBridgeService.send() uses — so a batched manual
#     send produces byte-for-byte the same email a per-row manual send would
#     have produced for this row. Quota is NOT checked here: send_batch()
#     does its own pre-flight check_can_send(count=len(group)) for the whole
#     group, which is manual_tick's one required gate.

#     Raises RuntimeError (caller skips the row) if the recipient email can't
#     be resolved — same failure mode as the per-row path's `if not to_email`.
#     """
#     from app.schemas.mailbridge import BatchSendMessage

#     to_email = await _resolve_manual_recipient_email(db, seq)
#     if not to_email:
#         raise RuntimeError(f"Sequence {seq.id}: no resolvable recipient email")

#     body_html, body_text = await mailbridge_service._prepare_body_for_send(
#         db, seq.bodyCopy or "", seq.id, tenant_slug
#     )

#     return BatchSendMessage(
#         sequenceId=seq.id,
#         to=to_email,
#         subject=seq.subjectLine or "",
#         body_html=body_html,
#         body_text=body_text,
#         external_user_id=user_id,
#     )


# async def _dispatch_manual_batch_groups(
#     db: AsyncSession,
#     schema_name: str,
#     batch_groups: dict[str, list[Sequence]],
#     mailbridge_service: MailBridgeService,
# ) -> tuple[int, int]:
#     """Dispatch every owner_user_id group as one BatchSend call, for
#     manual_tick(). Returns (sent, skipped).

#     Mirrors _dispatch_batch_groups' shape but tailored to manual_tick's
#     parity requirements: message-building uses _build_manual_batch_message
#     (no business-hours/DNS/warmup gates), and the fallback-on-failure path
#     calls MailBridgeService.send() per row — the exact same call the
#     original manual_tick loop made — instead of _send_via_mailbridge.
#     """
#     tenant_slug = ""
#     try:
#         from app.utils.tenant_context import resolve_tenant_slug
#         tenant_slug = await resolve_tenant_slug(db)
#     except Exception as exc:  # noqa: BLE001
#         logger.warning("scheduler.manual_tick.tenant_resolve_failed", error=str(exc))
#     callback_url = _build_batch_callback_url(tenant_slug)

#     sent = 0
#     skipped = 0

#     for seq_owner, group_sequences in batch_groups.items():
#         messages = []
#         buildable_sequences = []
#         for seq in group_sequences:
#             try:
#                 msg = await _build_manual_batch_message(
#                     db, seq, seq_owner if seq_owner != "system" else None,
#                     mailbridge_service, tenant_slug,
#                 )
#                 messages.append(msg)
#                 buildable_sequences.append(seq)
#             except Exception as exc:  # noqa: BLE001 — per-seq isolation
#                 skipped += 1
#                 logger.warning(
#                     "scheduler.manual_tick.batch_message_build_failed",
#                     schema=schema_name,
#                     sequence_id=seq.id,
#                     error=str(exc),
#                 )

#         if not messages:
#             continue

#         ack = await mailbridge_service.send_batch(
#             db=db,
#             messages=messages,
#             callback_url=callback_url,
#             user_id=(seq_owner if seq_owner != "system" else None),
#         )

#         if ack is not None:
#             seq_ids = [s.id for s in buildable_sequences]
#             await db.execute(
#                 text(
#                     'UPDATE "Sequence" SET status = \'BatchPending\', '
#                     '"mailBridgeBatchId" = :batch_id '
#                     'WHERE id = ANY(:seq_ids)'
#                 ),
#                 {"batch_id": ack.batchId, "seq_ids": seq_ids},
#             )
#             sent += len(buildable_sequences)
#             logger.info(
#                 "scheduler.manual_tick.batch_dispatch_accepted",
#                 schema=schema_name,
#                 batch_id=ack.batchId,
#                 owner=seq_owner,
#                 count=len(buildable_sequences),
#             )
#             continue

#         # send_batch() returned None — fall back to the ORIGINAL per-row
#         # manual send (MailBridgeService.send()), exactly as before
#         # BatchSend existed for this group.
#         logger.warning(
#             "scheduler.manual_tick.batch_fallback_to_per_row",
#             schema=schema_name,
#             owner=seq_owner,
#             count=len(buildable_sequences),
#         )
#         for seq in buildable_sequences:
#             try:
#                 to_email = await _resolve_manual_recipient_email(db, seq)
#                 if not to_email:
#                     skipped += 1
#                     continue
#                 send_result = await mailbridge_service.send(
#                     db=db,
#                     to=to_email,
#                     subject=seq.subjectLine or "",
#                     body=seq.bodyCopy or "",
#                     sequence_id=seq.id,
#                     user_id=getattr(seq, "owner_user_id", None),
#                 )
#                 if send_result.accepted:
#                     await db.execute(
#                         text(
#                             "UPDATE \"Sequence\" SET status = 'Sent', "
#                             "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
#                             "WHERE id = :seq_id"
#                         ),
#                         {
#                             "sent_at": datetime.now(timezone.utc),
#                             "msg_id": send_result.messageId,
#                             "seq_id": seq.id,
#                         },
#                     )
#                     sent += 1
#                 else:
#                     skipped += 1
#             except Exception:  # noqa: BLE001
#                 skipped += 1

#     return sent, skipped


# # ── Phase 3 SchedulerService (preserved) ────────────────────────────────────


# class SchedulerService:
#     """Backwards-compatible wrapper exposing the Phase 3 status +
#     manual-tick endpoints. Phase 5 callers should use run_tick() /
#     run_tick_all_tenants() / get_scheduler() directly."""

#     def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
#         self._mailbridge = mailbridge or MailBridgeService()

#     async def get_status(self, db: AsyncSession) -> SchedulerStatus:
#         """Return the singleton status row, creating it if absent."""
#         result = await db.execute(
#             select(SchedulerStatus).where(SchedulerStatus.id == 1)
#         )
#         status = result.scalar_one_or_none()
#         if status is None:
#             status = SchedulerStatus(id=1, isRunning=False)
#             db.add(status)
#             await db.commit()
#             status = await db.get(SchedulerStatus, status.id)
#         return status

#     async def manual_tick(
#         self,
#         db: AsyncSession,
#         *,
#         tenant_scoped: bool = True,
#         max_send: int = 50,
#     ) -> ManualTickResponse:
#         """Send up to max_send Scheduled sequences in one synchronous tick.

#         Phase 3 contract — preserved verbatim. Does NOT apply the §9.2/§9.3
#         business-hours + PARTIAL throttle filters (callers that want that
#         behavior should invoke run_tick() instead — this is intentional,
#         not a gap: the manual tick is an operator-triggered "send now"
#         action, not the automatic scheduler, and only the daily quota gate
#         applies here, same as before BatchSend existed).

#         BatchSend: when settings.BATCH_SEND_ENABLED is on, sequences are
#         grouped by owner_user_id and dispatched via
#         MailBridgeService.send_batch() instead of one-by-one — see
#         _dispatch_manual_batch_groups. When it's off (the default), this
#         method's behaviour is BYTE-FOR-BYTE IDENTICAL to before BatchSend
#         existed: same per-row MailBridgeService.send() loop, same
#         quota-only gating, nothing else changed.
#         """
#         started = datetime.now(timezone.utc)
#         status = await self.get_status(db)
#         status.isRunning = True
#         await db.commit()

#         batch_send_enabled = _is_batch_send_enabled()

#         sent = 0
#         skipped = 0
#         try:
#             result = await db.execute(
#                 select(Sequence)
#                 .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
#                 .limit(max_send)
#             )
#             sequences = list(result.scalars().all())

#             if batch_send_enabled and sequences:
#                 # ── BatchSend path ────────────────────────────────────────
#                 # Group by owner_user_id only — manual_tick has never done
#                 # per-user MailBridgeConfig resolution like run_tick's Step
#                 # 3c; send_batch()/MailBridgeService resolve the config
#                 # themselves via user_id, same as the per-row path already did.
#                 batch_groups: dict[str, list[Sequence]] = {}
#                 for seq in sequences:
#                     owner = getattr(seq, "owner_user_id", None) or "system"
#                     batch_groups.setdefault(owner, []).append(seq)

#                 schema_name = "public"
#                 try:
#                     sc_result = await db.execute(text("SELECT current_schema()"))
#                     current = sc_result.scalar()
#                     if current:
#                         schema_name = current
#                 except Exception:  # noqa: BLE001 — logging context only
#                     pass

#                 batch_sent, batch_skipped = await _dispatch_manual_batch_groups(
#                     db, schema_name, batch_groups, self._mailbridge
#                 )
#                 sent += batch_sent
#                 skipped += batch_skipped
#             else:
#                 # ── Original per-row path — UNCHANGED ─────────────────────
#                 for seq in sequences:
#                     # Phase 5 will add business-hours + throttle filters here.
#                     try:
#                         # Wiring audit (Task 2-e): previously this method passed
#                         # ``to=""`` to MailBridgeService.send with a comment saying
#                         # "caller resolves prospect.email" — but no caller actually
#                         # did so, resulting in empty-envelope stub-accepts. Resolve
#                         # the prospect email (with PII decrypt) here so the manual
#                         # tick actually delivers. Mirrors SequenceService.send_email.
#                         to_email = await _resolve_manual_recipient_email(db, seq)
#                         if not to_email:
#                             skipped += 1
#                             continue
#                         send_result = await self._mailbridge.send(
#                             db=db,
#                             to=to_email,
#                             subject=seq.subjectLine or "",
#                             body=seq.bodyCopy or "",
#                             sequence_id=seq.id,
#                             user_id=getattr(seq, "owner_user_id", None),
#                         )
#                         if send_result.accepted:
#                             # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError)
#                             # seq.status = EmailStatus.Sent would generate $1::email_status
#                             # which fails across tenant schemas due to asyncpg plan cache.
#                             await db.execute(
#                                 text(
#                                     "UPDATE \"Sequence\" SET status = 'Sent', "
#                                     "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
#                                     "WHERE id = :seq_id"
#                                 ),
#                                 {
#                                     "sent_at": datetime.now(timezone.utc),
#                                     "msg_id": send_result.messageId,
#                                     "seq_id": seq.id,
#                                 },
#                             )
#                             sent += 1
#                         else:
#                             skipped += 1
#                     except Exception:  # noqa: BLE001
#                         skipped += 1
#             try:
#                 await db.commit()
#             except Exception:  # noqa: BLE001 — swallow if already aborted
#                 await db.rollback()
#         finally:
#             duration_ms = int(
#                 (datetime.now(timezone.utc) - started).total_seconds() * 1000
#             )
#             # FIX: rollback any aborted transaction before updating SchedulerStatus
#             # so the finally block never runs inside an aborted transaction.
#             try:
#                 await db.rollback()
#             except Exception:  # noqa: BLE001
#                 pass
#             try:
#                 await db.execute(
#                     text(
#                         'UPDATE "SchedulerStatus" SET "isRunning" = false, '
#                         '"lastTickAt" = :last, "nextTickAt" = :next, '
#                         '"sentSinceLastTick" = :sent, "skippedSinceLastTick" = :skipped, '
#                         '"updatedAt" = now() WHERE id = 1'
#                     ),
#                     {
#                         "last": started,
#                         "next": started + timedelta(seconds=get_settings().SCHEDULER_TICK_SECONDS),
#                         "sent": sent,
#                         "skipped": skipped,
#                     },
#                 )
#                 await db.commit()
#             except Exception as _fin_exc:  # noqa: BLE001
#                 logger.warning(
#                     "scheduler.manual_tick.status_update_failed",
#                     error=str(_fin_exc)[:200],
#                 )
#         return ManualTickResponse(
#             sent=sent,
#             skipped=skipped,
#             durationMs=duration_ms,
#             tickedAt=started,
#         )

#     async def trigger(self, db: AsyncSession) -> "TriggerResponse":
#         """Trigger an immediate scheduler tick via Celery or direct invocation.
 
#         If Celery is available and the broker is reachable, enqueues
#         ``autopilot.run_pipeline`` and returns immediately with the task ID
#         as ``runId``. Otherwise falls back to a synchronous tick and logs
#         a ``SchedulerRun`` row.
 
#         Returns a ``TriggerResponse`` with ``triggered=True`` on success.
#         """
#         from app.schemas.scheduler import TriggerResponse
 
#         # FIX: SchedulerRun table may not exist yet (migration 0019 creates it).
#         # If insert fails, continue without logging - the tick still runs.
#         run = None
#         try:
#             _run_obj = SchedulerRun(status="running")
#             db.add(_run_obj)
#             await db.commit()
#             run = await db.get(SchedulerRun, _run_obj.id)
#         except Exception as _exc:  # noqa: BLE001
#             await db.rollback()
#             logger.warning(
#                 "scheduler.trigger.run_log_skipped",
#                 hint="Run migration 0019 to create SchedulerRun table",
#                 error=str(_exc)[:200],
#             )
 
#         # Attempt Celery enqueue
#         try:
#             from app.worker.celery_app import celery_app
 
#             if celery_app is not None:
#                 result = celery_app.send_task(
#                     "autopilot.run_pipeline",
#                     kwargs={"schema_name": "current"},
#                 )
#                 if run is not None:
#                     run.status = "completed"
#                     run.completedAt = datetime.now(timezone.utc)
#                     await db.commit()
#                 return TriggerResponse(
#                     triggered=True,
#                     message="Scheduler triggered via Celery.",
#                     runId=result.id,
#                 )
#         except Exception as exc:  # noqa: BLE001
#             logger.warning("scheduler.trigger.celery_failed", error=str(exc))
 
#         # Fallback: synchronous tick
#         started = datetime.now(timezone.utc)
#         try:
#             tick_result = await self.manual_tick(
#                 db, tenant_scoped=True, max_send=50
#             )
#             if run is not None:
#                 run.status = "completed"
#                 run.sent = tick_result.sent
#                 run.skipped = tick_result.skipped
#                 run.durationMs = tick_result.durationMs
#                 run.completedAt = datetime.now(timezone.utc)
#                 await db.commit()
#             return TriggerResponse(
#                 triggered=True,
#                 message="Scheduler tick completed synchronously.",
#                 runId=run.id if run else None,
#             )
#         except Exception as exc:  # noqa: BLE001
#             if run is not None:
#                 run.status = "failed"
#                 run.error = str(exc)
#                 run.completedAt = datetime.now(timezone.utc)
#                 await db.commit()
#             return TriggerResponse(
#                 triggered=False,
#                 message=f"Scheduler tick failed: {exc}",
#                 runId=run.id if run else None,
#             )
 
#     async def list_runs(
#         self,
#         db: AsyncSession,
#         *,
#         limit: int = 20,
#         offset: int = 0,
#     ) -> "SchedulerRunsListResponse":
#         """Return recent scheduler run log entries, newest first.
 
#         FIX: SchedulerRun table was never in any migration — wraps queries in
#         try/except so the Scheduler Status page loads cleanly even on tenants
#         that have not run migration 0019 yet. Returns empty list in that case.
#         """
#         from app.schemas.scheduler import (
#             SchedulerRunResponse,
#             SchedulerRunsListResponse,
#         )
#         from sqlalchemy import func as sa_func
 
#         try:
#             count_result = await db.execute(
#                 select(sa_func.count()).select_from(SchedulerRun)
#             )
#             total = count_result.scalar() or 0
 
#             result = await db.execute(
#                 select(SchedulerRun)
#                 .order_by(SchedulerRun.startedAt.desc())
#                 .limit(limit)
#                 .offset(offset)
#             )
#             rows = list(result.scalars().all())
#             items = [SchedulerRunResponse.model_validate(r) for r in rows]
#             return SchedulerRunsListResponse(items=items, total=total)
#         except Exception as exc:  # noqa: BLE001
#             # Table does not exist yet - return empty list instead of crashing.
#             # Resolved permanently by running migration 0019.
#             err_str = str(exc)
#             if "UndefinedTableError" in err_str or "does not exist" in err_str or "undefined_table" in err_str.lower():
#                 await db.rollback()
#                 logger.warning(
#                     "scheduler.list_runs.table_missing",
#                     hint="Run migration 0019 to create SchedulerRun table",
#                     error=err_str[:200],
#                 )
#                 return SchedulerRunsListResponse(items=[], total=0)
#             raise
 
 
# __all__ = [
#     "SchedulerService",
#     "get_scheduler",
#     "run_tick",
#     "run_tick_all_tenants",
#     "_is_business_hours",
#     "_partial_throttle_passes",
#     "_resolve_mailbridge_config",
#     "_send_via_mailbridge",
#     "_async_tick_wrapper",
# ]

from __future__ import annotations
 
import asyncio
import hashlib
import zoneinfo
from datetime import datetime, time, timedelta, timezone
from typing import Any
 
import httpx
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.models.campaign_models import Sequence
from app.models.config_models import MailBridgeConfig
from app.models.enums import EmailStatus, EnrichmentTier
from app.models.phase3_models import SchedulerRun, SchedulerStatus
from app.models.prospect_models import Prospect
from app.schemas.scheduler import ManualTickResponse
from app.features.mailbridge.service import MailBridgeService
from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
from app.features.mailbridge.reply_poller import register_reply_poll_job
from app.features.scheduler.query_service import write_skip_log, upsert_daily_sent
logger = structlog.get_logger(__name__)
 
# ── Module-global singleton scheduler ──────────────────────────────────────
_scheduler: AsyncIOScheduler | None = None
# register_reply_poll_job(_scheduler)
 
# def get_scheduler() -> AsyncIOScheduler:
#     """Return the AsyncIOScheduler singleton (migration §9.1 L1266-1278).
 
#     The scheduler is created lazily on first access and configured with
#     max_instances=1 + coalesce=True so missed ticks never pile up. The
#     interval job is registered here; start()/shutdown() are called from
#     the FastAPI lifespan in app.main.create_app().
#     """
#     global _scheduler
#     if _scheduler is None:
#         settings = get_settings()
#         _scheduler = AsyncIOScheduler()
#         _scheduler.add_job(
#             _async_tick_wrapper,
#             "interval",
#             seconds=settings.SCHEDULER_TICK_SECONDS,
#             id="outrena_tick",
#             max_instances=1,
#             coalesce=True,
#             replace_existing=True,
#         )
#         # Nightly cost-summary rollup — runs at 02:00 UTC every day.
#         # Materialises per-user × event_type × provider cost_summaries rows
#         # for the current month so the Usage dashboard reads from a fast
#         # rollup table rather than scanning raw usage_events.
#         _scheduler.add_job(
#             _async_cost_rollup_wrapper,
#             "cron",
#             hour=2,
#             minute=0,
#             id="outrena_cost_rollup",
#             max_instances=1,
#             coalesce=True,
#             replace_existing=True,
#         )
#                 # Reply-inbox poller — polls MailBridge for inbound replies.
#         # Only registers when MAILBRIDGE_DEFAULT_URL is configured.
#         from app.features.mailbridge.reply_poller import register_reply_poll_job
#         register_reply_poll_job(_scheduler)
#         logger.info(
#             "scheduler.registered",
#             tick_seconds=settings.SCHEDULER_TICK_SECONDS,
#             job_id="outrena_tick",
#         )
#     return _scheduler
 
def get_scheduler(
    *,
    email_tick_enabled: bool = True,
    reply_poller_enabled: bool = True,
) -> AsyncIOScheduler:
    """Return the APScheduler singleton — email tick and reply poller
    are registered independently based on their respective flags."""
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = AsyncIOScheduler()

        if email_tick_enabled:
            _scheduler.add_job(
                _async_tick_wrapper,
                "interval",
                seconds=settings.SCHEDULER_TICK_SECONDS,
                id="outrena_tick",
                max_instances=1,
                coalesce=True,
                replace_existing=True,
            )
            logger.info("scheduler.email_tick.registered",
                        tick_seconds=settings.SCHEDULER_TICK_SECONDS)
        else:
            logger.info("scheduler.email_tick.disabled")

        _scheduler.add_job(
            _async_cost_rollup_wrapper,
            "cron",
            hour=2,
            minute=0,
            id="outrena_cost_rollup",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

        if reply_poller_enabled:
            from app.features.mailbridge.reply_poller import register_reply_poll_job
            register_reply_poll_job(_scheduler)
            logger.info("scheduler.reply_poller.registered",
                        poll_seconds=settings.MAILBRIDGE_REPLY_POLL_SECONDS)
        else:
            logger.info("scheduler.reply_poller.disabled")

    return _scheduler
 
async def _async_tick_wrapper() -> None:
    """Top-level tick wrapper — catches + logs every exception so a single
    tenant's failure (or even a DB outage) never kills the scheduler."""
    try:
        summary = await run_tick_all_tenants()
        logger.info("scheduler.tick.complete", **summary)
    except Exception as exc:  # noqa: BLE001 — scheduler must never die
        logger.error("scheduler.tick.fatal", error=str(exc), exc_info=True)
 
 
async def _async_cost_rollup_wrapper() -> None:
    """Nightly job — materialise CostSummary rows for all active tenants.
 
    Iterates all ACTIVE tenants in public.tenants and calls
    UsageService().rebuild_cost_summaries() for the current month.
    Failures per-tenant are logged and swallowed so one bad schema
    never blocks all others.
    """
    from app.core.database import AsyncSessionLocal
    from app.features.usage.service import UsageService
    from datetime import date as _date
 
    period = _date.today().strftime("%Y-%m")  # e.g. "2026-07"
    total = 0
    errors = 0
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text as _text
            try:
                result = await db.execute(
                    _text("SELECT slug FROM public.tenants WHERE status = 'ACTIVE' AND deleted_at IS NULL")
                )
                slugs = [row[0] for row in result.all()]
            except Exception as exc:  # noqa: BLE001
                if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
                    raise
                logger.warning("scheduler.cost_rollup.no_tenants_table", error=str(exc))
                slugs = []
        for slug in slugs:
            try:
                svc = UsageService()
                written = await svc.rebuild_cost_summaries(slug, period)
                total += written
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "scheduler.cost_rollup.tenant_failed",
                    tenant=slug,
                    error=str(exc),
                )
        logger.info(
            "scheduler.cost_rollup.complete",
            period=period,
            tenants=len(slugs),
            rows_written=total,
            errors=errors,
        )
 
        # ── FR-038: nightly warm-up week advancement per tenant ────────────
        advanced_total = 0
        for slug in slugs:
            try:
                async with AsyncSessionLocal() as db:
                    from sqlalchemy import text as _text
 
                    await db.execute(
                        _text(f'SET search_path TO "tenant_{slug}", public')
                    )
                    advanced_total += await advance_domain_warmup(db)
                    await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "scheduler.warmup_advance.tenant_failed",
                    tenant=slug,
                    error=str(exc),
                )
        if advanced_total:
            logger.info(
                "scheduler.warmup_advance.complete", domains=advanced_total
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("scheduler.cost_rollup.fatal", error=str(exc), exc_info=True)
 
 
# ── §9.2 Business-hours filter ─────────────────────────────────────────────
 
 
# 7-week ramp per Help Guide §Domains (Warming Schedule)
# Week 1=10, 2=30, 3=50, 4=100, 5=200, 6=350, 7=500
_WARMUP_RAMP: dict[int, int] = {1: 10, 2: 30, 3: 50, 4: 100, 5: 200, 6: 350, 7: 500}
WARMING_SCHEDULE = [10, 30, 50, 100, 200, 350, 500]  # exported for UI display
 
 
def _warmup_effective_cap(dom) -> int:
    """FR-038: effective daily cap for a (possibly warming) domain."""
    week = int(getattr(dom, "warmingWeek", 0) or 0)
    base = int(getattr(dom, "dailySendLimit", 0) or 0) or 10_000
    if 1 <= week <= 7:
        return min(base, _WARMUP_RAMP[week])
    return base
 
 
async def advance_domain_warmup(db) -> int:
    """FR-038: advance warmingWeek for domains warmed >= 7 days per week.
 
    Called by the nightly maintenance job. A domain whose updatedAt is more
    than 7 days old and whose warmingWeek is 1-4 moves to the next week;
    week 5 means warm-up complete (full dailySendLimit applies).
    Returns the number of domains advanced."""
    result = await db.execute(
        text(
            'UPDATE "Domain" SET '
            '  "warmingWeek" = "warmingWeek" + 1, '
            '  "updatedAt" = now() '
            'WHERE "warmingWeek" BETWEEN 1 AND 7 '
            "  AND \"updatedAt\" < now() - interval '7 days'"
        )
    )
    return result.rowcount or 0
 
 
def _is_business_hours(now: datetime, tz_name: str | None) -> bool:
    """Return True iff `now` falls inside recipient-local 9am-5pm, Mon-Fri.
 
    If tz_name is None, defaults to America/New_York (US Eastern) — the most
    common timezone for B2B cold outreach targets. If tz_name is unparseable,
    falls back to UTC. local is always assigned before use (no UnboundLocalError).
    """
    local = now  # always assigned — fallback if zoneinfo fails
    effective_tz = tz_name or "America/New_York"
    try:
        tz = zoneinfo.ZoneInfo(effective_tz)
        local = now.astimezone(tz)
    except Exception:  # noqa: BLE001 — unknown tz string, keep UTC fallback
        local = now
    if local.weekday() >= 5:  # Sat=5, Sun=6
        return False
    start, end = time(9, 0), time(17, 0)
    return start <= local.time() <= end
 
 
# ── §9.3 PARTIAL throttle (deterministic hash) ─────────────────────────────
 
 
def _partial_throttle_passes(prospect_id: str, tick_bucket: int) -> bool:
    """Return True iff this PARTIAL-enrichment prospect should be sent this tick.
 
    Per migration §9.3 L1309-1316: hash(prospect_id + tick_bucket) % 100 must
    be < SCHEDULER_PARTIAL_PER_TICK_CAP (default 5). The hash is deterministic
    so retries within the same tick window select the same prospects.
    """
    settings = get_settings()
    cap = settings.SCHEDULER_PARTIAL_PER_TICK_CAP
    hash_input = f"{prospect_id}:{tick_bucket}"
    bucket = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16) % 100
    return bucket < cap


def _is_batch_send_enabled() -> bool:
    """True if BatchSend should be used — single global switch
    (settings.BATCH_SEND_ENABLED). Shared by run_tick() (automatic tick)
    and SchedulerService.manual_tick() (the UI's "Run Tick"/"Trigger Now"
    buttons) so both paths always agree on whether BatchSend is on.
    """
    return get_settings().BATCH_SEND_ENABLED


# ── §9.5 MailBridge dispatch ───────────────────────────────────────────────
 
 
async def _resolve_mailbridge_config(
    db: AsyncSession, user_id: str | None
) -> MailBridgeConfig | None:
    """Resolve the MailBridgeConfig to use for a given user.
 
    Per SAAS2-USER-BE §G:
      1. If user_id is provided, look for an active MailBridgeConfig owned by
         that user (MailBridgeConfig.owner_user_id == user_id). This requires
         BE-A to have added the owner_user_id column to MailBridgeConfig.
      2. Fall back to a tenant-level config (owner_user_id IS NULL or column
         does not exist yet) — preserves the pre-user-behaviour.
      3. Return None if no active config exists.
 
    The lookup is defensive: if MailBridgeConfig does not yet expose
    owner_user_id (BE-A migration 0004 not yet applied), the per-user filter
    is skipped and the tenant-level fallback is used.
    """
    # Per-user lookup — only if the column exists on the model.
    has_owner_col = hasattr(MailBridgeConfig, "owner_user_id")
    if user_id and has_owner_col:
        try:
            result = await db.execute(
                select(MailBridgeConfig)
                .where(MailBridgeConfig.isActive.is_(True))
                .where(getattr(MailBridgeConfig, "owner_user_id") == user_id)
                .limit(1)
            )
            cfg = result.scalar_one_or_none()
            if cfg is not None:
                return cfg
        except Exception as exc:  # noqa: BLE001 — fall back to tenant-level
            logger.warning(
                "scheduler.mailbridge.per_user_lookup_failed",
                user_id=user_id, error=str(exc),
            )
 
    # Tenant-level fallback.
    result = await db.execute(
        select(MailBridgeConfig)
        .where(MailBridgeConfig.isActive.is_(True))
        .limit(1)
    )
    return result.scalar_one_or_none()

def _is_html_body(body: str | None) -> bool:
    """True when body was authored in the Tiptap RTE (already HTML).

    The RTE always opens content with a block-level HTML tag. We also require
    at least one closing tag to avoid false-positives on plain text that
    happens to start with '<'.
    """
    if not body:
        return False
    s = body.lstrip()
    return s.startswith("<") and any(
        marker in body
        for marker in (
            "</p>", "</h", "<br", "</ul>", "</ol>",
            "</li>", "</strong>", "</em>",
        )
    )


def _strip_html_text(html: str) -> str:
    """Strip HTML tags and collapse whitespace → plain-text fallback."""
    import re as _re
    text = _re.sub(r"<[^>]+>", " ", html)
    return _re.sub(r"\s+", " ", text).strip() 
 
async def _resolve_recipient_email(db: AsyncSession, sequence: Sequence) -> tuple[Any, str]:
    """Resolve + decrypt the recipient email for a sequence's prospect.

    Extracted verbatim from the original _send_via_mailbridge body (no
    behaviour change) so both the single-send path and the BatchSend
    message-builder below share one implementation. Returns (prospect,
    recipient_email); raises RuntimeError on missing prospect/email, same
    as before.
    """
    prospect_result = await db.execute(
        select(Prospect).where(Prospect.id == sequence.prospectId)
    )
    prospect = prospect_result.scalar_one_or_none()
    if prospect is None or not prospect.email:
        raise RuntimeError(
            f"Prospect {sequence.prospectId} missing or has no email"
        )

    # Wiring audit (Task 2-e): the Prospect.email column is encrypted at rest
    # when ENCRYPTION_KEY is set (production). Decrypt via PiiService before
    # building the payload (mirrors SequenceService.send_email +
    # ReplyDraftService.auto_reply). Best-effort: fall back to the stored
    # value when decryption fails (legacy plaintext / dev mode without key).
    raw_email = prospect.email
    if not getattr(prospect, "anonymized", False):
        try:
            from app.services.pii_service import PiiService

            recipient_email = PiiService().decrypt_field(raw_email) or raw_email
        except Exception:  # noqa: BLE001 — best-effort
            recipient_email = raw_email
    else:
        recipient_email = raw_email
    if not recipient_email:
        raise RuntimeError(
            f"Prospect {sequence.prospectId} email is empty after decrypt"
        )
    return prospect, recipient_email


async def _domain_preflight_gate(db: AsyncSession, config: MailBridgeConfig | None) -> None:
    """Run the FR-039 DNS gate + FR-038 warm-up gate for `config`'s bound
    Domain. Extracted verbatim from the original _send_via_mailbridge body
    — same exceptions, same conditions, no behaviour change. Shared by the
    single-send path and the BatchSend grouping path for run_tick (NOT
    used by manual_tick's batch path — manual_tick intentionally only
    checks quota, see its docstring)."""
    if config is None or not getattr(config, "domainId", None):
        return
    from app.models.config_models import Domain as _Domain

    dom = (
        await db.execute(select(_Domain).where(_Domain.id == config.domainId))
    ).scalar_one_or_none()
    if dom is not None and dom.lastChecked is not None:
        failing = [
            name
            for name, ok in (
                ("SPF", dom.spfStatus),
                ("DKIM", dom.dkimStatus),
                ("DMARC", dom.dmarcStatus),
            )
            if not ok
        ]
        if failing:
            raise RuntimeError(
                f"DNS verification failing for domain '{dom.domainName}': "
                f"{', '.join(failing)}. Fix the DNS records and re-verify "
                "before sending (FR-039)."
            )

    if dom is not None:
        week = int(getattr(dom, "warmingWeek", 0) or 0)
        if 1 <= week < 2:
            raise RuntimeError(
                f"Domain '{dom.domainName}' has only completed "
                f"{week} week(s) of warm-up. At least 2 weeks are "
                "required before sending. Use the Auto-Warm button on "
                "the Domains page to advance the schedule, or wait for "
                "the nightly auto-advance."
            )

    if dom is not None:
        effective_cap = _warmup_effective_cap(dom)
        sent_today = (
            await db.execute(
                text(
                    'SELECT COUNT(*) FROM "Sequence" s '
                    'JOIN "Campaign" c ON c.id = s."campaignId" '
                    "WHERE c.\"domainId\" = :dom_id "
                    "  AND s.\"sentAt\" >= date_trunc('day', now())"
                ),
                {"dom_id": dom.id},
            )
        ).scalar() or 0
        if int(sent_today) >= effective_cap:
            raise RuntimeError(
                f"Warm-up daily cap reached for domain "
                f"'{dom.domainName}' ({sent_today}/{effective_cap}, "
                f"week {dom.warmingWeek}). Deferring to tomorrow "
                "(FR-038)."
            )


async def _build_email_body(
    db: AsyncSession, sequence: Sequence, prospect: Prospect
) -> tuple[str, str]:
    """Build (body_html_final, body_text_final) with the CAN-SPAM footer.

    Extracted verbatim from the original _send_via_mailbridge body (no
    behaviour change) — shared by the single-send path and the BatchSend
    message-builder. NOT used by manual_tick's batch path, which uses
    MailBridgeService._prepare_body_for_send() instead, to stay identical
    to a per-row manual send.
    """
    body_text = sequence.bodyCopy or ""
    is_html = _is_html_body(body_text)

    needs_footer = (
        "unsubscribe" not in body_text.lower()
        or "physical" not in body_text.lower()
        and "address" not in body_text.lower()
    )
    if needs_footer:
        try:
            from app.utils.tenant_context import resolve_tenant_slug as _rts
            from app.core.config import get_settings as _gs
            _tenant_slug = await _rts(db)
            _prospect_token = getattr(prospect, "unsubscribeToken", None) or ""
            _base = _gs().BASE_DOMAIN
            _unsub_url = (
                f"https://{_base}/api/v1/public/unsubscribe"
                f"?token={_prospect_token}&tenant_slug={_tenant_slug}"
                if _prospect_token and _tenant_slug
                else ""
            )

            if is_html:
                _unsub_link = (
                    f' <a href="{_unsub_url}" '
                    'style="color:#6b7280;text-decoration:underline">Unsubscribe</a>'
                    if _unsub_url
                    else ""
                )
                _html_footer = (
                    '<hr style="border:0;border-top:1px solid #e5e7eb;margin:24px 0">'
                    '<p style="color:#6b7280;font-size:11px;line-height:1.5;margin:0">'
                    f"This email was sent by an authorised OUTRENA user.{_unsub_link}"
                    "</p>"
                )
                body_text = body_text + _html_footer
            else:
                _footer_lines = [
                    "",
                    "---",
                    "This email was sent by an authorised OUTRENA user.",
                ]
                if _unsub_url:
                    _footer_lines.append(f"Unsubscribe: {_unsub_url}")
                body_text = body_text + "\n".join(_footer_lines)

        except Exception:  # noqa: BLE001 — footer is best-effort, never block send
            pass

    if is_html:
        body_html_final = body_text
        body_text_final = _strip_html_text(body_text)
    else:
        body_html_final = body_text
        body_text_final = body_text

    return body_html_final, body_text_final


def _resolve_ext_user_id(config: MailBridgeConfig | None, user_id: str | None) -> str | None:
    """Identity propagation resolution — extracted verbatim, shared by both
    the single-send path and the BatchSend message-builder. Priority:
      1. config.mailbridge_external_user_id — ONLY when the config is
         explicitly owned by the sending user.
      2. user_id — the Keycloak UUID of the sequence owner.
    """
    config_owner = getattr(config, "owner_user_id", None) if config else None
    config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
    return (
        config_ext_id
        if (config_owner and config_owner == user_id and config_ext_id)
        else user_id
    )


async def _send_via_mailbridge(
    db: AsyncSession,
    config: MailBridgeConfig | None,
    sequence: Sequence,
    user_id: str | None = None,
) -> str:
    """Send one sequence via MailBridge and return the messageId.
 
    Per migration §9.5 L1339-1353. Uses httpx.AsyncClient with a 30s timeout.
    The prospect is loaded from the same session to resolve the recipient
    email + timezone. On HTTP 4xx/5xx or any network error, raises
    RuntimeError so the caller can mark the sequence as skipped.
 
    Stub-safe: if no `config` is supplied (dev/CI), returns a deterministic
    stub messageId so tests can run without a MailBridge instance.

    UNCHANGED BEHAVIOUR: this function's externally-visible logic (order of
    checks, exceptions raised, payload shape, sentinel returns) is identical
    to before BatchSend — it now calls out to the shared helpers above
    (_resolve_recipient_email / _domain_preflight_gate / _build_email_body /
    _resolve_ext_user_id) instead of inlining that logic, purely so the
    BatchSend grouping path (below, in run_tick) can reuse the exact same
    business logic rather than reimplementing it. This is the code path
    used when BatchSend is off (default), and remains the fallback path
    per-group when BatchSend's send_batch() returns None.
    """
    prospect, recipient_email = await _resolve_recipient_email(db, sequence)
    settings = get_settings()

    await _domain_preflight_gate(db, config)

    # Dev/CI stub: no config + no default URL → deterministic fake id.
    if config is None and not settings.MAILBRIDGE_DEFAULT_URL:
        msg_id = f"stub-{sequence.id}@outrena.local"
        await _record_usage_send_safe(db, sequence)
        return msg_id

    base_url = (config.baseUrl if config else "") or settings.MAILBRIDGE_DEFAULT_URL
    body_html_final, body_text_final = await _build_email_body(db, sequence, prospect)

    payload = {
        "to": [recipient_email],
        "subject": sequence.subjectLine or "",
        "body_html": body_html_final,
        "body_text": body_text_final,
    }
    ext_user_id = _resolve_ext_user_id(config, user_id)
    if ext_user_id:
        payload["external_user_id"] = ext_user_id
 
    # Build auth headers. MailBridge tenancy mode requires a Bearer
    # API key (mb_live_...) from POST /platform/register.
    api_key = (
        getattr(config, "mailbridge_api_key", None) if config else None
    ) or settings.MAILBRIDGE_API_KEY
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
 
    timeout_s = float(settings.MAILBRIDGE_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/outbound/send",
            json=payload,
            headers=headers,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"MailBridge returned HTTP {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json()
        # MailBridge returns snake_case "message_id"; fall back to camelCase
        # for backward compatibility with older/stub MailBridge instances.
        msg_id = data.get("message_id") or data.get("messageId", "")
        if not msg_id:
            raise RuntimeError("MailBridge response missing message_id")
 
    # Stamp who actually sent this and which MailBridge identity was used.
    # These are the values the reply-poller relies on — see reply_poller.py.
    if user_id:
        sequence.sent_by_user_id = user_id
    if ext_user_id:
        sequence.sent_via_external_user_id = ext_user_id
 
    # Best-effort: record usage_event(email_send) for per-tenant cost roll-ups.
    # (Mirrors MailBridgeService.send._record_usage_send so the scheduler-tick
    # path doesn't silently bypass cost tracking.)
    await _record_usage_send_safe(db, sequence)
    return msg_id


async def _build_batch_send_message(
    db: AsyncSession, sequence: Sequence, config: MailBridgeConfig | None, user_id: str | None
):
    """Build one BatchSendMessage for `sequence`, reusing the exact same
    recipient-resolution / domain-preflight / footer / identity-propagation
    logic as the single-send path. Returns raises if the sequence should be
    skipped rather than batched — caller treats that the same as any other
    pre-flight skip.
    """
    from app.schemas.mailbridge import BatchSendMessage

    prospect, recipient_email = await _resolve_recipient_email(db, sequence)
    await _domain_preflight_gate(db, config)
    body_html_final, body_text_final = await _build_email_body(db, sequence, prospect)
    ext_user_id = _resolve_ext_user_id(config, user_id)

    return BatchSendMessage(
        sequenceId=sequence.id,
        to=recipient_email,
        subject=sequence.subjectLine or "",
        body_html=body_html_final,
        body_text=body_text_final,
        external_user_id=ext_user_id,
    )


def _build_batch_callback_url(tenant_slug: str | None) -> str:
    """Callback URL MailBridge should POST batch results to.

    Uses a flat, single-domain URL with tenant_slug as a query parameter —
    NOT a per-tenant subdomain. Subdomain-based tenant resolution
    (TenantMiddleware) is how the authenticated app identifies tenants for
    logged-in users, but it isn't the only mechanism this codebase uses:
    /api/v1/public/unsubscribe (clicked from email clients, which can't be
    expected to hit the right subdomain either) already resolves tenant via
    a `tenant_slug` query param instead, precisely to avoid requiring
    wildcard DNS + a wildcard TLS cert covering every tenant subdomain.
    MailBridge — a separate service, possibly without any path to resolve
    or trust arbitrary tenant subdomains — has the same requirement, so the
    batch-complete webhook follows the same pattern. See
    app/middleware/tenant_middleware.py's EXEMPT_PREFIXES entry for
    /api/v1/mailbridge/batch-complete, and the route itself in
    app/features/mailbridge/router.py::batch_complete.

    Falls back to settings.OUTRENA_BATCH_CALLBACK_URL (unchanged) only
    when a tenant slug genuinely can't be resolved.
    """
    settings = get_settings()
    if not tenant_slug:
        return settings.OUTRENA_BATCH_CALLBACK_URL
    return (
        f"https://{settings.BASE_DOMAIN}/api/v1/mailbridge/batch-complete"
        f"?tenant_slug={tenant_slug}"
    )


async def _dispatch_batch_groups(
    session: AsyncSession,
    schema_name: str,
    batch_groups: dict[tuple, dict[str, Any]],
    quota_service: UserEmailQuotaService,
    started: datetime,
) -> tuple[int, int]:
    """Dispatch every (owner_user_id, config_id) group as one BatchSend
    call. Returns (sent, skipped) counts to fold into run_tick's summary.

    Per group:
      1. Build a BatchSendMessage per sequence (same business logic as a
         single send). A sequence that fails to build (e.g. missing
         prospect email, DNS gate) is skipped + skip-logged individually,
         same as the legacy per-row path.
      2. Call MailBridgeService().send_batch() for the survivors.
      3. On success: mark every dispatched sequence BatchPending (NOT
         Sent — Sent is set later by the completion webhook handler).
      4. On failure (None): fall back to the original per-row send loop
         for exactly this group's sequences.
    """
    from app.features.mailbridge.service import MailBridgeService

    settings = get_settings()
    send_service = MailBridgeService()

    tenant_slug = ""
    try:
        from app.utils.tenant_context import resolve_tenant_slug
        tenant_slug = await resolve_tenant_slug(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("scheduler.batch_dispatch.tenant_resolve_failed", error=str(exc))
    callback_url = _build_batch_callback_url(tenant_slug)

    sent = 0
    skipped = 0

    for (seq_owner, _config_id), group in batch_groups.items():
        config = group["config"]
        group_sequences: list[Sequence] = group["sequences"]

        messages = []
        buildable_sequences = []
        for seq in group_sequences:
            try:
                msg = await _build_batch_send_message(session, seq, config, seq_owner)
                messages.append(msg)
                buildable_sequences.append(seq)
            except Exception as exc:  # noqa: BLE001 — per-seq isolation, same as legacy path
                skipped += 1
                logger.warning(
                    "scheduler.batch_dispatch.message_build_failed",
                    schema=schema_name,
                    sequence_id=seq.id,
                    error=str(exc),
                )
                await write_skip_log(
                    session,
                    run_id=None,
                    sequence_id=seq.id,
                    campaign_id=getattr(seq, "campaignId", None),
                    prospect_id=getattr(seq, "prospectId", None),
                    skip_reason="send_error",
                    detail=str(exc)[:500],
                )

        if not messages:
            continue

        ack = await send_service.send_batch(
            db=session,
            messages=messages,
            callback_url=callback_url,
            user_id=(seq_owner if seq_owner != "system" else None),
        )

        if ack is not None:
            # Dispatched — mark BatchPending, NOT Sent. sentAt/Sent is set
            # by the completion webhook handler once MailBridge confirms
            # delivery.
            seq_ids = [s.id for s in buildable_sequences]
            await session.execute(
                text(
                    'UPDATE "Sequence" SET status = \'BatchPending\', '
                    '"mailBridgeBatchId" = :batch_id '
                    'WHERE id = ANY(:seq_ids)'
                ),
                {"batch_id": ack.batchId, "seq_ids": seq_ids},
            )
            sent += len(buildable_sequences)
            logger.info(
                "scheduler.batch_dispatch.accepted",
                schema=schema_name,
                batch_id=ack.batchId,
                owner=seq_owner,
                count=len(buildable_sequences),
            )
            continue

        # send_batch returned None — fall back to the proven per-row path
        # for exactly this group, exactly as run_tick's legacy loop does.
        logger.warning(
            "scheduler.batch_dispatch.fallback_to_per_row",
            schema=schema_name,
            owner=seq_owner,
            count=len(buildable_sequences),
        )
        for seq in buildable_sequences:
            try:
                msg_id = await _send_via_mailbridge(session, config, seq, user_id=seq_owner)
                await session.execute(
                    text(
                        "UPDATE \"Sequence\" SET status = 'Sent', "
                        "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
                        "WHERE id = :seq_id"
                    ),
                    {
                        "sent_at": datetime.now(timezone.utc),
                        "msg_id": msg_id,
                        "seq_id": seq.id,
                    },
                )
                sent += 1
                camp_id_for_log = getattr(seq, "campaignId", None)
                if camp_id_for_log:
                    await upsert_daily_sent(
                        session,
                        campaign_id=camp_id_for_log,
                        sent_date=started.date(),
                        increment=1,
                    )
                if seq_owner and seq_owner != "system":
                    try:
                        await quota_service.record_send(session, seq_owner, count=1)
                    except Exception as exc:  # noqa: BLE001 — best-effort
                        logger.warning(
                            "scheduler.sequence.quota_record_failed",
                            schema=schema_name,
                            sequence_id=seq.id,
                            user_id=seq_owner,
                            error=str(exc),
                        )
            except Exception as exc:  # noqa: BLE001 — per-seq isolation
                skipped += 1
                logger.warning(
                    "scheduler.sequence.send_failed",
                    schema=schema_name,
                    sequence_id=seq.id,
                    error=str(exc),
                )
                await write_skip_log(
                    session,
                    run_id=None,
                    sequence_id=seq.id,
                    campaign_id=getattr(seq, "campaignId", None),
                    prospect_id=getattr(seq, "prospectId", None),
                    skip_reason="send_error",
                    detail=str(exc)[:500],
                )

    return sent, skipped
 
 
async def _record_usage_send_safe(db: AsyncSession, sequence: Sequence) -> None:
    """Fire-and-forget: record one usage_event(email_send) row.
 
    Wiring audit (Task 2-e): scheduler_service._send_via_mailbridge
    previously bypassed MailBridgeService.send (it makes its own httpx call
    per migration §9.5), so the per-tenant cost roll-up never saw
    scheduler-tick sends. This helper delegates to the same
    UsageService.record_email_send path used by MailBridgeService.send,
    deriving the tenant slug from the session's search_path. Best-effort —
    failures are logged + swallowed so a usage write never blocks the send.
    """
    try:
        from app.utils.tenant_context import resolve_tenant_slug
        tenant = await resolve_tenant_slug(db)
        if not tenant:
            return
        from app.features.usage.service import UsageService
        await UsageService().record_email_send(
            tenant=tenant,
            user_id=getattr(sequence, "owner_user_id", None) or "system",
            metadata={"source": "scheduler.run_tick", "sequence_id": sequence.id},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "scheduler.send.usage_record_failed",
            sequence_id=getattr(sequence, "id", None),
            error=str(exc),
        )
 
 
# ── §9.6 Single-tenant + multi-tenant ticks ────────────────────────────────
 
 
async def run_tick(schema_name: str) -> dict[str, Any]:
    """Run a single scheduler tick against one tenant schema.
 
    Per migration §9.4-9.6 + §10 Phase 5 L1502-1523. Steps:
      1. SET search_path TO "{schema}", public
      2. SELECT Sequences WHERE status=Scheduled AND touchNumber<=6
      3. For each candidate:
         a. Load prospect; skip if suppressed or no email.
         b. Business-hours filter (§9.2) — skip if outside 9am-5pm local.
         c. PARTIAL throttle (§9.3) — skip if hash falls outside this tick's cap.
         d. Resolve MailBridgeConfig (first active row).
         e. Call _send_via_mailbridge → on success, set status=Sent + sentAt
            + mailBridgeMessageId. On failure, log + count as skipped.
      4. Update SchedulerStatus row (id=1) with new counters + nextTickAt.
      5. Commit + return summary dict.
    """
    settings = get_settings()
    started = datetime.now(timezone.utc)
    tick_bucket = int(started.timestamp()) // settings.SCHEDULER_TICK_SECONDS
 
    summary: dict[str, Any] = {
        "schema": schema_name,
        "candidates": 0,
        "sent": 0,
        "skipped": 0,
        "started_at": started.isoformat(),
    }
 
    async with AsyncSessionLocal() as session:
        await session.execute(text(f'SET search_path TO "{schema_name}", public'))
 
        # ── Step 1: load SchedulerStatus row (create if absent) ──────────
        # FIX: wrap in try/except — SchedulerStatus table may not exist in
        # partially-provisioned tenant schemas (migration 0002 not yet run).
        # In that case skip the status tracking but still attempt sends.
        status_row = None
        try:
            status_result = await session.execute(
                select(SchedulerStatus).where(SchedulerStatus.id == 1)
            )
            status_row = status_result.scalar_one_or_none()
            if status_row is None:
                status_row = SchedulerStatus(id=1, isRunning=False)
                session.add(status_row)
                await session.flush()
            status_row.isRunning = True
            await session.commit()
        except Exception as _ss_exc:
            err_str = str(_ss_exc)
            if "does not exist" in err_str or "UndefinedTable" in err_str:
                await session.rollback()
                logger.warning(
                    "scheduler.tick.scheduler_status_missing",
                    schema=schema_name,
                    hint="Run alembic upgrade head to create SchedulerStatus table",
                )
            else:
                raise
 
        sent = 0
        skipped = 0
        try:
            # ── Step 2: load Scheduled sequences with touchNumber<=6 ─────
            # Guard against UndefinedTableError on a fresh tenant schema
            # (tables may not exist yet) or InFailedSQLTransactionError
            # if a prior query in this session aborted the transaction.
            # Roll back and skip cleanly rather than poisoning the session.
            try:
                seq_result = await session.execute(
                    select(Sequence)
                    .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
                    .where(Sequence.touchNumber <= 6)
                    .order_by(Sequence.createdAt.asc())
                    .limit(500)
                )
                sequences = list(seq_result.scalars().all())
            except Exception as table_exc:
                err_str = str(table_exc)
                if "UndefinedTableError" in err_str or "InFailedSQLTransaction" in err_str or "does not exist" in err_str:
                    import structlog as _sl
                    _sl.get_logger(__name__).warning(
                        "scheduler.tick.schema_not_ready",
                        schema=schema_name,
                        error=err_str[:200],
                    )
                    await session.rollback()
                    summary["skipped"] = 0
                    summary["sent"] = 0
                    return summary
                raise
            sequences = list(sequences) if not isinstance(sequences, list) else sequences
            summary["candidates"] = len(sequences)
 
            # Pre-load first active MailBridgeConfig for this schema (kept as
            # a tenant-level fallback for sequences without an owner_user_id).
            cfg_result = await session.execute(
                select(MailBridgeConfig)
                .where(MailBridgeConfig.isActive.is_(True))
                .limit(1)
            )
            tenant_default_config = cfg_result.scalar_one_or_none()
 
            quota_service = UserEmailQuotaService()
            batch_send_enabled = _is_batch_send_enabled()

            # BatchSend: sequences that pass all pre-flight checks are
            # collected here (keyed by (owner_user_id, config_id)) instead
            # of being dispatched immediately, when batch_send_enabled is
            # True. Left empty and unused when the flag is False — zero
            # behaviour change for the default configuration.
            batch_groups: dict[tuple, dict[str, Any]] = {}

            for seq in sequences:
                try:
                    # ── Load prospect once per sequence (cheap with session cache) ──
                    prospect_result = await session.execute(
                        select(Prospect).where(Prospect.id == seq.prospectId)
                    )
                    prospect = prospect_result.scalar_one_or_none()
 
                    # Skip suppressed / no-email prospects
                    # Layer 1: Prospect-level suppression flag
                    if prospect is None or not prospect.email:
                        skipped += 1
                        await write_skip_log(
                            session,
                            run_id=None,
                            sequence_id=seq.id,
                            campaign_id=getattr(seq, "campaignId", None),
                            prospect_id=seq.prospectId,
                            skip_reason="no_email",
                            detail="Prospect not found or has no email address",
                        )
                        continue
                    if prospect.suppressed:
                        skipped += 1
                        await write_skip_log(
                            session,
                            run_id=None,
                            sequence_id=seq.id,
                            campaign_id=getattr(seq, "campaignId", None),
                            prospect_id=seq.prospectId,
                            skip_reason="suppressed",
                            detail="Prospect suppression flag is set",
                        )
                        continue

                    # Layer 2: Email-level suppression — catches duplicate Prospect
                    # rows and future imports of the same address.
                    _sched_email_lower = (prospect.email or "").strip().lower()
                    if _sched_email_lower:
                        try:
                            from sqlalchemy import text as _sched_t
                            _sched_es = await session.execute(
                                _sched_t(
                                    'SELECT 1 FROM "EmailSuppression" '
                                    'WHERE email = :email LIMIT 1'
                                ),
                                {"email": _sched_email_lower},
                            )
                            if _sched_es.fetchone() is not None:
                                skipped += 1
                                await write_skip_log(
                                    session,
                                    run_id=None,
                                    sequence_id=seq.id,
                                    campaign_id=getattr(seq, "campaignId", None),
                                    prospect_id=seq.prospectId,
                                    skip_reason="suppressed",
                                    detail=f"Email {_sched_email_lower} is on suppression list",
                                )
                                continue
                        except Exception:  # noqa: BLE001
                            # EmailSuppression table may not exist yet — fail open.
                            pass

                    # ── Step 3a: business-hours filter (§9.2) ─────────────
                    if not _is_business_hours(started, prospect.timezone):
                        skipped += 1
                        await write_skip_log(
                            session,
                            run_id=None,
                            sequence_id=seq.id,
                            campaign_id=getattr(seq, "campaignId", None),
                            prospect_id=seq.prospectId,
                            skip_reason="business_hours",
                            detail=f"Outside 9am-5pm in timezone {prospect.timezone or 'UTC'}",
                        )
                        continue

                    # ── Step 3b: PARTIAL throttle (§9.3) ──────────────────
                    if (
                        prospect.enrichmentTier == EnrichmentTier.PARTIAL
                        and not _partial_throttle_passes(prospect.id, tick_bucket)
                    ):
                        skipped += 1
                        await write_skip_log(
                            session,
                            run_id=None,
                            sequence_id=seq.id,
                            campaign_id=getattr(seq, "campaignId", None),
                            prospect_id=seq.prospectId,
                            skip_reason="warmup_cap",
                            detail="PARTIAL throttle hash did not pass for this tick bucket",
                        )
                        continue

                    # ── Step 3b': per-user quota enforcement (SAAS2-USER-BE §G) ──
                    # For the background scheduler, the "sender" is the sequence
                    # owner — the person whose MailBridge account will be used.
                    # sent_by_user_id is stamped inside _send_via_mailbridge on
                    # success (same value as seq_owner for scheduler-driven sends).
                    seq_owner = getattr(seq, "owner_user_id", None) or "system"
                    if seq_owner and seq_owner != "system":
                        try:
                            can_send, reason = await quota_service.check_can_send(
                                session, seq_owner, count=1
                            )
                        except Exception as exc:  # noqa: BLE001 — never abort the tick
                            can_send, reason = False, f"quota_check_error: {exc}"
                        if not can_send:
                            skipped += 1
                            logger.info(
                                "scheduler.sequence.quota_exceeded",
                                schema=schema_name,
                                sequence_id=seq.id,
                                user_id=seq_owner,
                                reason=reason,
                            )
                            await write_skip_log(
                                session,
                                run_id=None,
                                sequence_id=seq.id,
                                campaign_id=getattr(seq, "campaignId", None),
                                prospect_id=seq.prospectId,
                                skip_reason="quota_exceeded",
                                detail=str(reason),
                            )
                            continue
                    else:
                        reason = "ok"
 
                    # ── Step 3c: per-user MailBridge resolution (SAAS2-USER-BE §G) ──
                    # Use the sequence owner's MailBridge config (their connected
                    # mailbox); fall back to the tenant-level default only when the
                    # owner has no personal config registered.
                    if seq_owner and seq_owner != "system":
                        config = await _resolve_mailbridge_config(session, seq_owner)
                    else:
                        config = tenant_default_config
                    if config is None:
                        config = tenant_default_config
 
                    # ── Step 3d: MailBridge dispatch (§9.5) ───────────────
                    if batch_send_enabled:
                        # BatchSend path: collect into a group keyed by
                        # (owner_user_id, config_id) — different sequence
                        # owners can have different connected mailboxes.
                        # All the per-row gates above (suppression,
                        # business hours, PARTIAL throttle, quota
                        # pre-check) have already run for this sequence —
                        # batching only changes HOW the dispatch HTTP call
                        # is made.
                        group_key = (seq_owner, getattr(config, "id", None) if config else None)
                        batch_groups.setdefault(group_key, {"config": config, "sequences": []})
                        batch_groups[group_key]["sequences"].append(seq)
                        continue

                    # ── Legacy per-row dispatch (BatchSend off, the
                    # default) — completely unchanged from before
                    # BatchSend existed. ─────────────────────────────────
                    # _send_via_mailbridge stamps seq.sent_by_user_id and
                    # seq.sent_via_external_user_id on the sequence row so the
                    # reply-poller can poll the correct MailBridge inbox.
                    msg_id = await _send_via_mailbridge(session, config, seq, user_id=seq_owner)
                    # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError across schemas)
                    await session.execute(
                        text(
                            "UPDATE \"Sequence\" SET status = 'Sent', "
                            "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
                            "WHERE id = :seq_id"
                        ),
                        {
                            "sent_at": datetime.now(timezone.utc),
                            "msg_id": msg_id,
                            "seq_id": seq.id,
                        },
                    )
                    sent += 1

                    # ── Step 3e: record daily sent aggregation ────────────
                    camp_id_for_log = getattr(seq, "campaignId", None)
                    if camp_id_for_log:
                        await upsert_daily_sent(
                            session,
                            campaign_id=camp_id_for_log,
                            sent_date=started.date(),
                            increment=1,
                        )

                    # ── Step 3f: record send against per-user quota ───────
                    if seq_owner and seq_owner != "system":
                        try:
                            await quota_service.record_send(session, seq_owner, count=1)
                        except Exception as exc:  # noqa: BLE001 — best-effort
                            logger.warning(
                                "scheduler.sequence.quota_record_failed",
                                schema=schema_name,
                                sequence_id=seq.id,
                                user_id=seq_owner,
                                error=str(exc),
                            )
                except Exception as exc:  # noqa: BLE001 — per-seq isolation
                    skipped += 1
                    logger.warning(
                        "scheduler.sequence.send_failed",
                        schema=schema_name,
                        sequence_id=seq.id,
                        error=str(exc),
                    )
                    await write_skip_log(
                        session,
                        run_id=None,
                        sequence_id=seq.id,
                        campaign_id=getattr(seq, "campaignId", None),
                        prospect_id=getattr(seq, "prospectId", None),
                        skip_reason="send_error",
                        detail=str(exc)[:500],
                    )

            # ── Step 3d(batch): dispatch every group collected above ─────
            # Only reached when BatchSend is enabled and at least one
            # sequence passed all pre-flight checks. Each group becomes one
            # POST /outbound/batch-send call; a group that fails to dispatch
            # falls back to the original per-row loop for exactly that
            # group — never for the whole tick.
            if batch_send_enabled and batch_groups:
                batch_sent, batch_skipped = await _dispatch_batch_groups(
                    session, schema_name, batch_groups, quota_service, started
                )
                sent += batch_sent
                skipped += batch_skipped

            await session.commit()
        finally:
            # ── Step 4: update SchedulerStatus counters + nextTickAt ─────
            ended = datetime.now(timezone.utc)
            if status_row is not None:
                status_row.isRunning = False
                status_row.lastTickAt = started
                status_row.sentSinceLastTick = sent
                status_row.skippedSinceLastTick = skipped
                status_row.nextTickAt = started + timedelta(
                    seconds=settings.SCHEDULER_TICK_SECONDS
                )
                try:
                    await session.commit()
                except Exception:  # noqa: BLE001
                    await session.rollback()
 
        summary["sent"] = sent
        summary["skipped"] = skipped
        summary["ended_at"] = ended.isoformat()
        summary["duration_ms"] = int((ended - started).total_seconds() * 1000)
        return summary
 
 
async def _get_tenant_scheduler_config(schema_name: str) -> dict:
    """Read scheduler.enabled and scheduler.tick_interval_minutes from
    the tenant's SystemParameter table.

    Returns a dict with:
      enabled: bool   — True if scheduler should run for this tenant
      tick_minutes: int — how often to send (in minutes, default 5)

    Falls back to safe defaults if the table doesn't exist or the keys
    are missing (fail-open: enabled=True, tick_minutes=5).
    """
    defaults = {"enabled": True, "tick_minutes": 5}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(f'SET search_path TO "{schema_name}", public')
            )

            # Read scheduler.enabled
            enabled_row = await session.execute(
                text(
                    'SELECT value FROM "SystemParameter" '
                    "WHERE key = 'scheduler.enabled' LIMIT 1"
                )
            )
            enabled_val = enabled_row.scalar()
            if enabled_val is not None:
                defaults["enabled"] = enabled_val.lower().strip() not in (
                    "false", "0", "no", "off", "disabled"
                )

            # Read scheduler.tick_interval_minutes
            interval_row = await session.execute(
                text(
                    'SELECT value FROM "SystemParameter" '
                    "WHERE key = 'scheduler.tick_interval_minutes' LIMIT 1"
                )
            )
            interval_val = interval_row.scalar()
            if interval_val is not None:
                try:
                    defaults["tick_minutes"] = max(1, int(float(interval_val)))
                except (ValueError, TypeError):
                    pass

    except Exception as exc:  # noqa: BLE001 — never block the tick
        err = str(exc)
        if "does not exist" not in err and "UndefinedTable" not in err:
            logger.warning(
                "scheduler.tenant_config.read_failed",
                schema=schema_name,
                error=err[:200],
            )
    return defaults


# Per-tenant last-tick timestamps — used to enforce per-tenant tick intervals
# without needing a separate DB table. Resets on process restart (fine —
# worst case all tenants tick once on restart regardless of interval).
_tenant_last_tick: dict[str, datetime] = {}


async def run_tick_all_tenants() -> dict[str, Any]:
    """Run a tick across every ACTIVE tenant schema.

    Per-tenant control:
      scheduler.enabled = false  → tenant is completely skipped this tick
      scheduler.tick_interval_minutes = N → tenant only ticks if at least
        N minutes have passed since its last successful tick.

    Per migration §9.6 L1362-1378: SELECT schema_name FROM public.tenants
    WHERE status='ACTIVE' AND deleted_at IS NULL. Per-tenant failure is
    logged + skipped — it never aborts the entire tick.
    """
    summary: dict[str, Any] = {
        "tenants": 0,
        "sent": 0,
        "skipped": 0,
        "failed_tenants": 0,
        "tenants_disabled": 0,
        "tenants_interval_skipped": 0,
    }

    # Query public.tenants directly via a raw connection (not the ORM)
    # so we don't pollute the tenant-schema-bound session cache.
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
        if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
            raise
        logger.warning("scheduler.tick.no_tenants_table", error=str(exc))
        schemas = []

    summary["tenant_count"] = len(schemas)
    now = datetime.now(timezone.utc)

    for schema in schemas:
        try:
            # ── Read per-tenant scheduler config from SystemParameter ──────
            tenant_cfg = await _get_tenant_scheduler_config(schema)

            # Gate 1: tenant has disabled their scheduler
            if not tenant_cfg["enabled"]:
                summary["tenants_disabled"] += 1
                logger.debug(
                    "scheduler.tenant.disabled",
                    schema=schema,
                )
                continue

            # Gate 2: tick interval not yet elapsed for this tenant
            tick_interval_minutes = tenant_cfg["tick_minutes"]
            last_tick = _tenant_last_tick.get(schema)
            if last_tick is not None:
                elapsed_minutes = (now - last_tick).total_seconds() / 60
                if elapsed_minutes < tick_interval_minutes:
                    summary["tenants_interval_skipped"] += 1
                    logger.debug(
                        "scheduler.tenant.interval_not_elapsed",
                        schema=schema,
                        elapsed_minutes=round(elapsed_minutes, 1),
                        required_minutes=tick_interval_minutes,
                    )
                    continue

            # ── Run tick for this tenant ───────────────────────────────────
            tick_result = await run_tick(schema)
            _tenant_last_tick[schema] = now  # record successful tick time
            summary["tenants"] += 1
            summary["sent"] += tick_result.get("sent", 0)
            summary["skipped"] += tick_result.get("skipped", 0)

        except Exception as exc:  # noqa: BLE001 — per-tenant isolation
            summary["failed_tenants"] += 1
            logger.error(
                "scheduler.tenant_failed",
                schema=schema,
                error=str(exc),
                exc_info=True,
            )

    return summary


async def _resolve_manual_recipient_email(db: AsyncSession, seq: Sequence) -> str:
    """Resolve + decrypt the recipient email for manual_tick's per-row loop.

    Extracted verbatim from the original manual_tick body (no behaviour
    change) so the BatchSend batch-message-builder below
    (_build_manual_batch_message) produces the exact same recipient
    resolution as the per-row fallback path.
    """
    to_email = ""
    if seq.prospectId:
        p_result = await db.execute(
            select(Prospect).where(Prospect.id == seq.prospectId)
        )
        p = p_result.scalar_one_or_none()
        if p is not None:
            raw_email = getattr(p, "email", None) or ""
            if raw_email and not getattr(p, "anonymized", False):
                try:
                    from app.services.pii_service import PiiService

                    to_email = (
                        PiiService().decrypt_field(raw_email)
                        or raw_email
                    )
                except Exception:  # noqa: BLE001 — best-effort
                    to_email = raw_email
            elif raw_email:
                to_email = raw_email
    return to_email


async def _build_manual_batch_message(
    db: AsyncSession,
    seq: Sequence,
    user_id: str | None,
    mailbridge_service: MailBridgeService,
    tenant_slug: str,
):
    """Build one BatchSendMessage for manual_tick's BatchSend path.

    Deliberately lighter-weight than run_tick's _build_batch_send_message:
    no business-hours check, no PARTIAL throttle, no DNS/warmup gate — the
    manual tick has never applied those, and batching must not silently
    add gates that weren't there before. Only the daily quota gate
    applies, same as before BatchSend existed.

    Body is prepared via MailBridgeService._prepare_body_for_send() — the
    exact same {{unsubscribe_url}} substitution + plain-text/RTE-HTML
    conversion that MailBridgeService.send() uses — so a batched manual
    send produces byte-for-byte the same email a per-row manual send would
    have produced for this row. Quota is NOT checked here: send_batch()
    does its own pre-flight check_can_send(count=len(group)) for the whole
    group, which is manual_tick's one required gate.

    Raises RuntimeError (caller skips the row) if the recipient email can't
    be resolved — same failure mode as the per-row path's `if not to_email`.
    """
    from app.schemas.mailbridge import BatchSendMessage

    to_email = await _resolve_manual_recipient_email(db, seq)
    if not to_email:
        raise RuntimeError(f"Sequence {seq.id}: no resolvable recipient email")

    body_html, body_text = await mailbridge_service._prepare_body_for_send(
        db, seq.bodyCopy or "", seq.id, tenant_slug
    )

    return BatchSendMessage(
        sequenceId=seq.id,
        to=to_email,
        subject=seq.subjectLine or "",
        body_html=body_html,
        body_text=body_text,
        external_user_id=user_id,
    )


async def _dispatch_manual_batch_groups(
    db: AsyncSession,
    schema_name: str,
    batch_groups: dict[str, list[Sequence]],
    mailbridge_service: MailBridgeService,
) -> tuple[int, int]:
    """Dispatch every owner_user_id group as one BatchSend call, for
    manual_tick(). Returns (sent, skipped).

    Mirrors _dispatch_batch_groups' shape but tailored to manual_tick's
    parity requirements: message-building uses _build_manual_batch_message
    (no business-hours/DNS/warmup gates), and the fallback-on-failure path
    calls MailBridgeService.send() per row — the exact same call the
    original manual_tick loop made — instead of _send_via_mailbridge.
    """
    tenant_slug = ""
    try:
        from app.utils.tenant_context import resolve_tenant_slug
        tenant_slug = await resolve_tenant_slug(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("scheduler.manual_tick.tenant_resolve_failed", error=str(exc))
    callback_url = _build_batch_callback_url(tenant_slug)

    sent = 0
    skipped = 0

    for seq_owner, group_sequences in batch_groups.items():
        messages = []
        buildable_sequences = []
        for seq in group_sequences:
            try:
                # external_user_id must be the raw owner_user_id — even the
                # literal string "system" — matching MailBridgeService.send()'s
                # behaviour exactly (ext_user_id = user_id there too). MailBridge
                # requires SOME external_user_id/account_id on every message
                # when authenticated via a tenant API key; nulling this out for
                # "system"-owned rows caused a real send failure ("API key
                # requests must specify 'external_user_id' ... or 'account_id'").
                # The "system" → None substitution below is ONLY for the
                # send_batch() quota check/reservation call further down —
                # system-owned sequences shouldn't consume a real user's daily
                # quota — it must never be reused for the message payload itself.
                msg = await _build_manual_batch_message(
                    db, seq, seq_owner,
                    mailbridge_service, tenant_slug,
                )
                messages.append(msg)
                buildable_sequences.append(seq)
            except Exception as exc:  # noqa: BLE001 — per-seq isolation
                skipped += 1
                logger.warning(
                    "scheduler.manual_tick.batch_message_build_failed",
                    schema=schema_name,
                    sequence_id=seq.id,
                    error=str(exc),
                )

        if not messages:
            continue

        ack = await mailbridge_service.send_batch(
            db=db,
            messages=messages,
            callback_url=callback_url,
            user_id=(seq_owner if seq_owner != "system" else None),
        )

        if ack is not None:
            seq_ids = [s.id for s in buildable_sequences]
            await db.execute(
                text(
                    'UPDATE "Sequence" SET status = \'BatchPending\', '
                    '"mailBridgeBatchId" = :batch_id '
                    'WHERE id = ANY(:seq_ids)'
                ),
                {"batch_id": ack.batchId, "seq_ids": seq_ids},
            )
            sent += len(buildable_sequences)
            logger.info(
                "scheduler.manual_tick.batch_dispatch_accepted",
                schema=schema_name,
                batch_id=ack.batchId,
                owner=seq_owner,
                count=len(buildable_sequences),
            )
            continue

        # send_batch() returned None — fall back to the ORIGINAL per-row
        # manual send (MailBridgeService.send()), exactly as before
        # BatchSend existed for this group.
        logger.warning(
            "scheduler.manual_tick.batch_fallback_to_per_row",
            schema=schema_name,
            owner=seq_owner,
            count=len(buildable_sequences),
        )
        for seq in buildable_sequences:
            try:
                to_email = await _resolve_manual_recipient_email(db, seq)
                if not to_email:
                    skipped += 1
                    continue
                send_result = await mailbridge_service.send(
                    db=db,
                    to=to_email,
                    subject=seq.subjectLine or "",
                    body=seq.bodyCopy or "",
                    sequence_id=seq.id,
                    user_id=getattr(seq, "owner_user_id", None),
                )
                if send_result.accepted:
                    await db.execute(
                        text(
                            "UPDATE \"Sequence\" SET status = 'Sent', "
                            "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
                            "WHERE id = :seq_id"
                        ),
                        {
                            "sent_at": datetime.now(timezone.utc),
                            "msg_id": send_result.messageId,
                            "seq_id": seq.id,
                        },
                    )
                    sent += 1
                else:
                    skipped += 1
            except Exception:  # noqa: BLE001
                skipped += 1

    return sent, skipped


# ── Phase 3 SchedulerService (preserved) ────────────────────────────────────


class SchedulerService:
    """Backwards-compatible wrapper exposing the Phase 3 status +
    manual-tick endpoints. Phase 5 callers should use run_tick() /
    run_tick_all_tenants() / get_scheduler() directly."""

    def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
        self._mailbridge = mailbridge or MailBridgeService()

    async def get_status(self, db: AsyncSession) -> SchedulerStatus:
        """Return the singleton status row, creating it if absent."""
        result = await db.execute(
            select(SchedulerStatus).where(SchedulerStatus.id == 1)
        )
        status = result.scalar_one_or_none()
        if status is None:
            status = SchedulerStatus(id=1, isRunning=False)
            db.add(status)
            await db.commit()
            status = await db.get(SchedulerStatus, status.id)
        return status

    async def manual_tick(
        self,
        db: AsyncSession,
        *,
        tenant_scoped: bool = True,
        max_send: int = 50,
    ) -> ManualTickResponse:
        """Send up to max_send Scheduled sequences in one synchronous tick.

        Phase 3 contract — preserved verbatim. Does NOT apply the §9.2/§9.3
        business-hours + PARTIAL throttle filters (callers that want that
        behavior should invoke run_tick() instead — this is intentional,
        not a gap: the manual tick is an operator-triggered "send now"
        action, not the automatic scheduler, and only the daily quota gate
        applies here, same as before BatchSend existed).

        BatchSend: when settings.BATCH_SEND_ENABLED is on, sequences are
        grouped by owner_user_id and dispatched via
        MailBridgeService.send_batch() instead of one-by-one — see
        _dispatch_manual_batch_groups. When it's off (the default), this
        method's behaviour is BYTE-FOR-BYTE IDENTICAL to before BatchSend
        existed: same per-row MailBridgeService.send() loop, same
        quota-only gating, nothing else changed.
        """
        started = datetime.now(timezone.utc)
        status = await self.get_status(db)
        status.isRunning = True
        await db.commit()

        batch_send_enabled = _is_batch_send_enabled()

        sent = 0
        skipped = 0
        try:
            result = await db.execute(
                select(Sequence)
                .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
                .limit(max_send)
            )
            sequences = list(result.scalars().all())

            if batch_send_enabled and sequences:
                # ── BatchSend path ────────────────────────────────────────
                # Group by owner_user_id only — manual_tick has never done
                # per-user MailBridgeConfig resolution like run_tick's Step
                # 3c; send_batch()/MailBridgeService resolve the config
                # themselves via user_id, same as the per-row path already did.
                batch_groups: dict[str, list[Sequence]] = {}
                for seq in sequences:
                    owner = getattr(seq, "owner_user_id", None) or "system"
                    batch_groups.setdefault(owner, []).append(seq)

                schema_name = "public"
                try:
                    sc_result = await db.execute(text("SELECT current_schema()"))
                    current = sc_result.scalar()
                    if current:
                        schema_name = current
                except Exception:  # noqa: BLE001 — logging context only
                    pass

                batch_sent, batch_skipped = await _dispatch_manual_batch_groups(
                    db, schema_name, batch_groups, self._mailbridge
                )
                sent += batch_sent
                skipped += batch_skipped
            else:
                # ── Original per-row path — UNCHANGED ─────────────────────
                for seq in sequences:
                    # Phase 5 will add business-hours + throttle filters here.
                    try:
                        # Wiring audit (Task 2-e): previously this method passed
                        # ``to=""`` to MailBridgeService.send with a comment saying
                        # "caller resolves prospect.email" — but no caller actually
                        # did so, resulting in empty-envelope stub-accepts. Resolve
                        # the prospect email (with PII decrypt) here so the manual
                        # tick actually delivers. Mirrors SequenceService.send_email.
                        to_email = await _resolve_manual_recipient_email(db, seq)
                        if not to_email:
                            skipped += 1
                            continue
                        send_result = await self._mailbridge.send(
                            db=db,
                            to=to_email,
                            subject=seq.subjectLine or "",
                            body=seq.bodyCopy or "",
                            sequence_id=seq.id,
                            user_id=getattr(seq, "owner_user_id", None),
                        )
                        if send_result.accepted:
                            # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError)
                            # seq.status = EmailStatus.Sent would generate $1::email_status
                            # which fails across tenant schemas due to asyncpg plan cache.
                            await db.execute(
                                text(
                                    "UPDATE \"Sequence\" SET status = 'Sent', "
                                    "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
                                    "WHERE id = :seq_id"
                                ),
                                {
                                    "sent_at": datetime.now(timezone.utc),
                                    "msg_id": send_result.messageId,
                                    "seq_id": seq.id,
                                },
                            )
                            sent += 1
                        else:
                            skipped += 1
                    except Exception:  # noqa: BLE001
                        skipped += 1
            try:
                await db.commit()
            except Exception:  # noqa: BLE001 — swallow if already aborted
                await db.rollback()
        finally:
            duration_ms = int(
                (datetime.now(timezone.utc) - started).total_seconds() * 1000
            )
            # FIX: rollback any aborted transaction before updating SchedulerStatus
            # so the finally block never runs inside an aborted transaction.
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass
            try:
                await db.execute(
                    text(
                        'UPDATE "SchedulerStatus" SET "isRunning" = false, '
                        '"lastTickAt" = :last, "nextTickAt" = :next, '
                        '"sentSinceLastTick" = :sent, "skippedSinceLastTick" = :skipped, '
                        '"updatedAt" = now() WHERE id = 1'
                    ),
                    {
                        "last": started,
                        "next": started + timedelta(seconds=get_settings().SCHEDULER_TICK_SECONDS),
                        "sent": sent,
                        "skipped": skipped,
                    },
                )
                await db.commit()
            except Exception as _fin_exc:  # noqa: BLE001
                logger.warning(
                    "scheduler.manual_tick.status_update_failed",
                    error=str(_fin_exc)[:200],
                )
        return ManualTickResponse(
            sent=sent,
            skipped=skipped,
            durationMs=duration_ms,
            tickedAt=started,
        )

    async def trigger(self, db: AsyncSession) -> "TriggerResponse":
        """Trigger an immediate scheduler tick via Celery or direct invocation.
 
        If Celery is available and the broker is reachable, enqueues
        ``autopilot.run_pipeline`` and returns immediately with the task ID
        as ``runId``. Otherwise falls back to a synchronous tick and logs
        a ``SchedulerRun`` row.
 
        Returns a ``TriggerResponse`` with ``triggered=True`` on success.
        """
        from app.schemas.scheduler import TriggerResponse
 
        # FIX: SchedulerRun table may not exist yet (migration 0019 creates it).
        # If insert fails, continue without logging - the tick still runs.
        run = None
        try:
            _run_obj = SchedulerRun(status="running")
            db.add(_run_obj)
            await db.commit()
            run = await db.get(SchedulerRun, _run_obj.id)
        except Exception as _exc:  # noqa: BLE001
            await db.rollback()
            logger.warning(
                "scheduler.trigger.run_log_skipped",
                hint="Run migration 0019 to create SchedulerRun table",
                error=str(_exc)[:200],
            )
 
        # Attempt Celery enqueue
        try:
            from app.worker.celery_app import celery_app
 
            if celery_app is not None:
                result = celery_app.send_task(
                    "autopilot.run_pipeline",
                    kwargs={"schema_name": "current"},
                )
                if run is not None:
                    run.status = "completed"
                    run.completedAt = datetime.now(timezone.utc)
                    await db.commit()
                return TriggerResponse(
                    triggered=True,
                    message="Scheduler triggered via Celery.",
                    runId=result.id,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheduler.trigger.celery_failed", error=str(exc))
 
        # Fallback: synchronous tick
        started = datetime.now(timezone.utc)
        try:
            tick_result = await self.manual_tick(
                db, tenant_scoped=True, max_send=50
            )
            if run is not None:
                run.status = "completed"
                run.sent = tick_result.sent
                run.skipped = tick_result.skipped
                run.durationMs = tick_result.durationMs
                run.completedAt = datetime.now(timezone.utc)
                await db.commit()
            return TriggerResponse(
                triggered=True,
                message="Scheduler tick completed synchronously.",
                runId=run.id if run else None,
            )
        except Exception as exc:  # noqa: BLE001
            if run is not None:
                run.status = "failed"
                run.error = str(exc)
                run.completedAt = datetime.now(timezone.utc)
                await db.commit()
            return TriggerResponse(
                triggered=False,
                message=f"Scheduler tick failed: {exc}",
                runId=run.id if run else None,
            )
 
    async def list_runs(
        self,
        db: AsyncSession,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> "SchedulerRunsListResponse":
        """Return recent scheduler run log entries, newest first.
 
        FIX: SchedulerRun table was never in any migration — wraps queries in
        try/except so the Scheduler Status page loads cleanly even on tenants
        that have not run migration 0019 yet. Returns empty list in that case.
        """
        from app.schemas.scheduler import (
            SchedulerRunResponse,
            SchedulerRunsListResponse,
        )
        from sqlalchemy import func as sa_func
 
        try:
            count_result = await db.execute(
                select(sa_func.count()).select_from(SchedulerRun)
            )
            total = count_result.scalar() or 0
 
            result = await db.execute(
                select(SchedulerRun)
                .order_by(SchedulerRun.startedAt.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = list(result.scalars().all())
            items = [SchedulerRunResponse.model_validate(r) for r in rows]
            return SchedulerRunsListResponse(items=items, total=total)
        except Exception as exc:  # noqa: BLE001
            # Table does not exist yet - return empty list instead of crashing.
            # Resolved permanently by running migration 0019.
            err_str = str(exc)
            if "UndefinedTableError" in err_str or "does not exist" in err_str or "undefined_table" in err_str.lower():
                await db.rollback()
                logger.warning(
                    "scheduler.list_runs.table_missing",
                    hint="Run migration 0019 to create SchedulerRun table",
                    error=err_str[:200],
                )
                return SchedulerRunsListResponse(items=[], total=0)
            raise
 
 
__all__ = [
    "SchedulerService",
    "get_scheduler",
    "run_tick",
    "run_tick_all_tenants",
    "_is_business_hours",
    "_partial_throttle_passes",
    "_resolve_mailbridge_config",
    "_send_via_mailbridge",
    "_async_tick_wrapper",
]