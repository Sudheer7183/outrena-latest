
# # # from __future__ import annotations
 
# # # import asyncio
# # # import hashlib
# # # import zoneinfo
# # # from datetime import datetime, time, timedelta, timezone
# # # from typing import Any
 
# # # import httpx
# # # import structlog
# # # from apscheduler.schedulers.asyncio import AsyncIOScheduler
# # # from sqlalchemy import select, text
# # # from sqlalchemy.ext.asyncio import AsyncSession
 
# # # from app.core.config import get_settings
# # # from app.core.database import AsyncSessionLocal, engine
# # # from app.models.campaign_models import Sequence
# # # from app.models.config_models import MailBridgeConfig
# # # from app.models.enums import EmailStatus, EnrichmentTier
# # # from app.models.phase3_models import SchedulerRun, SchedulerStatus
# # # from app.models.prospect_models import Prospect
# # # from app.schemas.scheduler import ManualTickResponse
# # # from app.features.mailbridge.service import MailBridgeService
# # # from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService
# # # from app.features.mailbridge.reply_poller import register_reply_poll_job
# # # logger = structlog.get_logger(__name__)
 
# # # # ── Module-global singleton scheduler ──────────────────────────────────────
# # # _scheduler: AsyncIOScheduler | None = None
# # # # register_reply_poll_job(_scheduler)
 
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
 
 
# # # async def _async_tick_wrapper() -> None:
# # #     """Top-level tick wrapper — catches + logs every exception so a single
# # #     tenant's failure (or even a DB outage) never kills the scheduler."""
# # #     try:
# # #         summary = await run_tick_all_tenants()
# # #         logger.info("scheduler.tick.complete", **summary)
# # #     except Exception as exc:  # noqa: BLE001 — scheduler must never die
# # #         logger.error("scheduler.tick.fatal", error=str(exc), exc_info=True)
 
 
# # # async def _async_cost_rollup_wrapper() -> None:
# # #     """Nightly job — materialise CostSummary rows for all active tenants.
 
# # #     Iterates all ACTIVE tenants in public.tenants and calls
# # #     UsageService().rebuild_cost_summaries() for the current month.
# # #     Failures per-tenant are logged and swallowed so one bad schema
# # #     never blocks all others.
# # #     """
# # #     from app.core.database import AsyncSessionLocal
# # #     from app.features.usage.service import UsageService
# # #     from datetime import date as _date
 
# # #     period = _date.today().strftime("%Y-%m")  # e.g. "2026-07"
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
# # #                 logger.warning(
# # #                     "scheduler.cost_rollup.tenant_failed",
# # #                     tenant=slug,
# # #                     error=str(exc),
# # #                 )
# # #         logger.info(
# # #             "scheduler.cost_rollup.complete",
# # #             period=period,
# # #             tenants=len(slugs),
# # #             rows_written=total,
# # #             errors=errors,
# # #         )
 
# # #         # ── FR-038: nightly warm-up week advancement per tenant ────────────
# # #         advanced_total = 0
# # #         for slug in slugs:
# # #             try:
# # #                 async with AsyncSessionLocal() as db:
# # #                     from sqlalchemy import text as _text
 
# # #                     await db.execute(
# # #                         _text(f'SET search_path TO "tenant_{slug}", public')
# # #                     )
# # #                     advanced_total += await advance_domain_warmup(db)
# # #                     await db.commit()
# # #             except Exception as exc:  # noqa: BLE001
# # #                 logger.warning(
# # #                     "scheduler.warmup_advance.tenant_failed",
# # #                     tenant=slug,
# # #                     error=str(exc),
# # #                 )
# # #         if advanced_total:
# # #             logger.info(
# # #                 "scheduler.warmup_advance.complete", domains=advanced_total
# # #             )
# # #     except Exception as exc:  # noqa: BLE001
# # #         logger.error("scheduler.cost_rollup.fatal", error=str(exc), exc_info=True)
 
 
# # # # ── §9.2 Business-hours filter ─────────────────────────────────────────────
 
 
# # # # 7-week ramp per Help Guide §Domains (Warming Schedule)
# # # # Week 1=10, 2=30, 3=50, 4=100, 5=200, 6=350, 7=500
# # # _WARMUP_RAMP: dict[int, int] = {1: 10, 2: 30, 3: 50, 4: 100, 5: 200, 6: 350, 7: 500}
# # # WARMING_SCHEDULE = [10, 30, 50, 100, 200, 350, 500]  # exported for UI display
 
 
# # # def _warmup_effective_cap(dom) -> int:
# # #     """FR-038: effective daily cap for a (possibly warming) domain."""
# # #     week = int(getattr(dom, "warmingWeek", 0) or 0)
# # #     base = int(getattr(dom, "dailySendLimit", 0) or 0) or 10_000
# # #     if 1 <= week <= 7:
# # #         return min(base, _WARMUP_RAMP[week])
# # #     return base
 
 
# # # async def advance_domain_warmup(db) -> int:
# # #     """FR-038: advance warmingWeek for domains warmed >= 7 days per week.
 
# # #     Called by the nightly maintenance job. A domain whose updatedAt is more
# # #     than 7 days old and whose warmingWeek is 1-4 moves to the next week;
# # #     week 5 means warm-up complete (full dailySendLimit applies).
# # #     Returns the number of domains advanced."""
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
 
 
# # # def _is_business_hours(now: datetime, tz_name: str | None) -> bool:
# # #     """Return True iff `now` falls inside recipient-local 9am-5pm, Mon-Fri.
 
# # #     If tz_name is None, defaults to America/New_York (US Eastern) — the most
# # #     common timezone for B2B cold outreach targets. If tz_name is unparseable,
# # #     falls back to UTC. local is always assigned before use (no UnboundLocalError).
# # #     """
# # #     local = now  # always assigned — fallback if zoneinfo fails
# # #     effective_tz = tz_name or "America/New_York"
# # #     try:
# # #         tz = zoneinfo.ZoneInfo(effective_tz)
# # #         local = now.astimezone(tz)
# # #     except Exception:  # noqa: BLE001 — unknown tz string, keep UTC fallback
# # #         local = now
# # #     if local.weekday() >= 5:  # Sat=5, Sun=6
# # #         return False
# # #     start, end = time(9, 0), time(17, 0)
# # #     return start <= local.time() <= end
 
 
# # # # ── §9.3 PARTIAL throttle (deterministic hash) ─────────────────────────────
 
 
# # # def _partial_throttle_passes(prospect_id: str, tick_bucket: int) -> bool:
# # #     """Return True iff this PARTIAL-enrichment prospect should be sent this tick.
 
# # #     Per migration §9.3 L1309-1316: hash(prospect_id + tick_bucket) % 100 must
# # #     be < SCHEDULER_PARTIAL_PER_TICK_CAP (default 5). The hash is deterministic
# # #     so retries within the same tick window select the same prospects.
# # #     """
# # #     settings = get_settings()
# # #     cap = settings.SCHEDULER_PARTIAL_PER_TICK_CAP
# # #     hash_input = f"{prospect_id}:{tick_bucket}"
# # #     bucket = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16) % 100
# # #     return bucket < cap
 
 
# # # # ── §9.5 MailBridge dispatch ───────────────────────────────────────────────
 
 
# # # async def _resolve_mailbridge_config(
# # #     db: AsyncSession, user_id: str | None
# # # ) -> MailBridgeConfig | None:
# # #     """Resolve the MailBridgeConfig to use for a given user.
 
# # #     Per SAAS2-USER-BE §G:
# # #       1. If user_id is provided, look for an active MailBridgeConfig owned by
# # #          that user (MailBridgeConfig.owner_user_id == user_id). This requires
# # #          BE-A to have added the owner_user_id column to MailBridgeConfig.
# # #       2. Fall back to a tenant-level config (owner_user_id IS NULL or column
# # #          does not exist yet) — preserves the pre-user-behaviour.
# # #       3. Return None if no active config exists.
 
# # #     The lookup is defensive: if MailBridgeConfig does not yet expose
# # #     owner_user_id (BE-A migration 0004 not yet applied), the per-user filter
# # #     is skipped and the tenant-level fallback is used.
# # #     """
# # #     # Per-user lookup — only if the column exists on the model.
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
# # #         except Exception as exc:  # noqa: BLE001 — fall back to tenant-level
# # #             logger.warning(
# # #                 "scheduler.mailbridge.per_user_lookup_failed",
# # #                 user_id=user_id, error=str(exc),
# # #             )
 
# # #     # Tenant-level fallback.
# # #     result = await db.execute(
# # #         select(MailBridgeConfig)
# # #         .where(MailBridgeConfig.isActive.is_(True))
# # #         .limit(1)
# # #     )
# # #     return result.scalar_one_or_none()
 
 
# # # async def _send_via_mailbridge(
# # #     db: AsyncSession,
# # #     config: MailBridgeConfig | None,
# # #     sequence: Sequence,
# # #     user_id: str | None = None,
# # # ) -> str:
# # #     """Send one sequence via MailBridge and return the messageId.
 
# # #     Per migration §9.5 L1339-1353. Uses httpx.AsyncClient with a 30s timeout.
# # #     The prospect is loaded from the same session to resolve the recipient
# # #     email + timezone. On HTTP 4xx/5xx or any network error, raises
# # #     RuntimeError so the caller can mark the sequence as skipped.
 
# # #     Stub-safe: if no `config` is supplied (dev/CI), returns a deterministic
# # #     stub messageId so tests can run without a MailBridge instance.
# # #     """
# # #     # Resolve prospect + recipient email
# # #     prospect_result = await db.execute(
# # #         select(Prospect).where(Prospect.id == sequence.prospectId)
# # #     )
# # #     prospect = prospect_result.scalar_one_or_none()
# # #     if prospect is None or not prospect.email:
# # #         raise RuntimeError(
# # #             f"Prospect {sequence.prospectId} missing or has no email"
# # #         )
 
# # #     # Wiring audit (Task 2-e): the Prospect.email column is encrypted at rest
# # #     # when ENCRYPTION_KEY is set (production). Previously this helper passed
# # #     # the raw encrypted blob to MailBridge — which then attempted to deliver
# # #     # to a Fernet-token-looking address and bounced every send. Decrypt via
# # #     # PiiService before building the payload (mirrors SequenceService.send_email
# # #     # + ReplyDraftService.auto_reply). Best-effort: fall back to the stored
# # #     # value when decryption fails (legacy plaintext / dev mode without key).
# # #     raw_email = prospect.email
# # #     if not getattr(prospect, "anonymized", False):
# # #         try:
# # #             from app.services.pii_service import PiiService
 
# # #             recipient_email = PiiService().decrypt_field(raw_email) or raw_email
# # #         except Exception:  # noqa: BLE001 — best-effort
# # #             recipient_email = raw_email
# # #     else:
# # #         recipient_email = raw_email
# # #     if not recipient_email:
# # #         raise RuntimeError(
# # #             f"Prospect {sequence.prospectId} email is empty after decrypt"
# # #         )
 
# # #     settings = get_settings()
 
# # #     # ── FR-039: DNS verification gate ────────────────────────────────────
# # #     # If the sending config is bound to a Domain whose SPF/DKIM/DMARC
# # #     # verification is failing, refuse the send and name the failing record.
# # #     # Domains that have never been checked (lastChecked IS NULL) are allowed
# # #     # through — blocking on "not yet verified" would deadlock fresh tenants.
# # #     if config is not None and getattr(config, "domainId", None):
# # #         from app.models.config_models import Domain as _Domain
 
# # #         dom = (
# # #             await db.execute(select(_Domain).where(_Domain.id == config.domainId))
# # #         ).scalar_one_or_none()
# # #         if dom is not None and dom.lastChecked is not None:
# # #             failing = [
# # #                 name
# # #                 for name, ok in (
# # #                     ("SPF", dom.spfStatus),
# # #                     ("DKIM", dom.dkimStatus),
# # #                     ("DMARC", dom.dmarcStatus),
# # #                 )
# # #                 if not ok
# # #             ]
# # #             if failing:
# # #                 raise RuntimeError(
# # #                     f"DNS verification failing for domain '{dom.domainName}': "
# # #                     f"{', '.join(failing)}. Fix the DNS records and re-verify "
# # #                     "before sending (FR-039)."
# # #                 )
 
# # #         # ── Pre-flight warmup gate (Help Guide §Domains) ─────────────────
# # #         # The domain must have completed at least 2 weeks of warmup before
# # #         # any sequence email is dispatched. This mirrors the Sequences
# # #         # Pre-Flight Activation Gate documented in the guide.
# # #         if dom is not None:
# # #             week = int(getattr(dom, "warmingWeek", 0) or 0)
# # #             if 1 <= week < 2:
# # #                 raise RuntimeError(
# # #                     f"Domain '{dom.domainName}' has only completed "
# # #                     f"{week} week(s) of warm-up. At least 2 weeks are "
# # #                     "required before sending. Use the Auto-Warm button on "
# # #                     "the Domains page to advance the schedule, or wait for "
# # #                     "the nightly auto-advance."
# # #                 )
 
# # #         # ── FR-038: warm-up escalating daily cap ────────────────────────
# # #         # While a domain is warming (warmingWeek 1-4), the effective daily
# # #         # send cap ramps: week1=10, week2=25, week3=50, week4=100, then the
# # #         # domain's own dailySendLimit applies. Week advancement is automated
# # #         # by the nightly maintenance job (advance_domain_warmup below).
# # #         if dom is not None:
# # #             effective_cap = _warmup_effective_cap(dom)
# # #             sent_today = (
# # #                 await db.execute(
# # #                     text(
# # #                         'SELECT COUNT(*) FROM "Sequence" s '
# # #                         'JOIN "Campaign" c ON c.id = s."campaignId" '
# # #                         "WHERE c.\"domainId\" = :dom_id "
# # #                         "  AND s.\"sentAt\" >= date_trunc('day', now())"
# # #                     ),
# # #                     {"dom_id": dom.id},
# # #                 )
# # #             ).scalar() or 0
# # #             if int(sent_today) >= effective_cap:
# # #                 raise RuntimeError(
# # #                     f"Warm-up daily cap reached for domain "
# # #                     f"'{dom.domainName}' ({sent_today}/{effective_cap}, "
# # #                     f"week {dom.warmingWeek}). Deferring to tomorrow "
# # #                     "(FR-038)."
# # #                 )
 
# # #     # Dev/CI stub: no config + no default URL → deterministic fake id.
# # #     if config is None and not settings.MAILBRIDGE_DEFAULT_URL:
# # #         msg_id = f"stub-{sequence.id}@outrena.local"
# # #         # Best-effort: record usage_event(email_send) so even dev-mode stub
# # #         # sends show up in per-tenant cost roll-ups (mirrors MailBridgeService.send).
# # #         await _record_usage_send_safe(db, sequence)
# # #         return msg_id
 
# # #     base_url = (config.baseUrl if config else "") or settings.MAILBRIDGE_DEFAULT_URL
 
# # #     # Build MailBridge-compatible body text with CAN-SPAM footer.
# # #     body_text = sequence.bodyCopy or ""
 
# # #     # ── CAN-SPAM / NFR-19: footer enforcement ─────────────────────────────
# # #     # Every commercial email must contain: physical address + unsubscribe URL.
# # #     # If the sequence body lacks them, we append a minimal compliant footer
# # #     # rather than blocking the send (blocking would deadlock campaigns).
# # #     # Best-effort: silently skip if we can't compute tenant slug.

# # #     # ── Replace {{unsubscribe_url}} placeholder if present ────────────────────
# # #     # Template-send sequences store the literal placeholder in bodyCopy.
# # #     # Replace it with the real URL before sending.
# # #     if "{{unsubscribe_url}}" in body_text:
# # #         try:
# # #             from app.utils.tenant_context import resolve_tenant_slug as _rts
# # #             from app.core.config import get_settings as _gs
# # #             _t_slug = await _rts(db)
# # #             _p_token = getattr(prospect, "unsubscribeToken", None) or ""
# # #             _b = _gs().BASE_DOMAIN
# # #             if _p_token and _t_slug and _b:
# # #                 _real = (
# # #                     f"https://{_b}/p/unsubscribe"
# # #                     f"?token={_p_token}&tenant_slug={_t_slug}"
# # #                 )
# # #                 body_text = body_text.replace("{{unsubscribe_url}}", _real)
# # #         except Exception:  # noqa: BLE001
# # #             pass

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
# # #                 f"https://{_base}/p/unsubscribe"
# # #                 f"?token={_prospect_token}&tenant_slug={_tenant_slug}"
# # #                 if _prospect_token and _tenant_slug
# # #                 else ""
# # #             )
# # #             _footer_lines = [
# # #                 "",
# # #                 "---",
# # #                 "This email was sent by an authorised OUTRENA user.",
# # #             ]
# # #             if _unsub_url:
# # #                 _footer_lines.append(f"Unsubscribe: {_unsub_url}")
# # #             body_text = body_text + "\n".join(_footer_lines)
# # #         except Exception:  # noqa: BLE001 — footer is best-effort, never block send
# # #             pass
 
# # #     # Build MailBridge-compatible payload (Phase 3+ /outbound/send).
# # #     # MailBridge expects: to as a list, body_html/body_text (not "body"),
# # #     # and optional external_user_id for identity propagation.
# # #     payload = {
# # #         "to": [recipient_email],
# # #         "subject": sequence.subjectLine or "",
# # #         "body_html": body_text,
# # #         "body_text": body_text,
# # #     }
# # #     # Identity propagation: tell MailBridge which connected mailbox to send from.
# # #     #
# # #     # Priority (mirrors MailBridgeService.send fix):
# # #     #   1. config.mailbridge_external_user_id — ONLY when the config is explicitly
# # #     #      owned by the sending user (config.owner_user_id == user_id), i.e. this
# # #     #      is the user's own per-user config with a static identity override.
# # #     #   2. user_id — the Keycloak UUID of the person who clicked Send.  This is
# # #     #      the exact value MailBridge recorded during POST /connect/{provider}/start,
# # #     #      so it routes through *that* user's connected mailbox — not the campaign
# # #     #      creator's.
# # #     #
# # #     # We record the resolved value as `sent_via_external_user_id` on the Sequence
# # #     # row so the reply-poller knows exactly which MailBridge identity to poll.
# # #     config_owner = getattr(config, "owner_user_id", None) if config else None
# # #     config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
# # #     ext_user_id = (
# # #         config_ext_id
# # #         if (config_owner and config_owner == user_id and config_ext_id)
# # #         else user_id
# # #     )
# # #     if ext_user_id:
# # #         payload["external_user_id"] = ext_user_id
 
# # #     # Build auth headers. MailBridge tenancy mode requires a Bearer
# # #     # API key (mb_live_...) from POST /platform/register.
# # #     api_key = (
# # #         getattr(config, "mailbridge_api_key", None) if config else None
# # #     ) or settings.MAILBRIDGE_API_KEY
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
# # #             raise RuntimeError(
# # #                 f"MailBridge returned HTTP {resp.status_code}: {resp.text[:200]}"
# # #             )
# # #         data = resp.json()
# # #         # MailBridge returns snake_case "message_id"; fall back to camelCase
# # #         # for backward compatibility with older/stub MailBridge instances.
# # #         msg_id = data.get("message_id") or data.get("messageId", "")
# # #         if not msg_id:
# # #             raise RuntimeError("MailBridge response missing message_id")
 
# # #     # Stamp who actually sent this and which MailBridge identity was used.
# # #     # These are the values the reply-poller relies on — see reply_poller.py.
# # #     if user_id:
# # #         sequence.sent_by_user_id = user_id
# # #     if ext_user_id:
# # #         sequence.sent_via_external_user_id = ext_user_id
 
# # #     # Best-effort: record usage_event(email_send) for per-tenant cost roll-ups.
# # #     # (Mirrors MailBridgeService.send._record_usage_send so the scheduler-tick
# # #     # path doesn't silently bypass cost tracking.)
# # #     await _record_usage_send_safe(db, sequence)
# # #     return msg_id
 
 
# # # async def _record_usage_send_safe(db: AsyncSession, sequence: Sequence) -> None:
# # #     """Fire-and-forget: record one usage_event(email_send) row.
 
# # #     Wiring audit (Task 2-e): scheduler_service._send_via_mailbridge
# # #     previously bypassed MailBridgeService.send (it makes its own httpx call
# # #     per migration §9.5), so the per-tenant cost roll-up never saw
# # #     scheduler-tick sends. This helper delegates to the same
# # #     UsageService.record_email_send path used by MailBridgeService.send,
# # #     deriving the tenant slug from the session's search_path. Best-effort —
# # #     failures are logged + swallowed so a usage write never blocks the send.
# # #     """
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
# # #         logger.warning(
# # #             "scheduler.send.usage_record_failed",
# # #             sequence_id=getattr(sequence, "id", None),
# # #             error=str(exc),
# # #         )
 
 
# # # # ── §9.6 Single-tenant + multi-tenant ticks ────────────────────────────────
 
 
# # # async def run_tick(schema_name: str) -> dict[str, Any]:
# # #     """Run a single scheduler tick against one tenant schema.
 
# # #     Per migration §9.4-9.6 + §10 Phase 5 L1502-1523. Steps:
# # #       1. SET search_path TO "{schema}", public
# # #       2. SELECT Sequences WHERE status=Scheduled AND touchNumber<=6
# # #       3. For each candidate:
# # #          a. Load prospect; skip if suppressed or no email.
# # #          b. Business-hours filter (§9.2) — skip if outside 9am-5pm local.
# # #          c. PARTIAL throttle (§9.3) — skip if hash falls outside this tick's cap.
# # #          d. Resolve MailBridgeConfig (first active row).
# # #          e. Call _send_via_mailbridge → on success, set status=Sent + sentAt
# # #             + mailBridgeMessageId. On failure, log + count as skipped.
# # #       4. Update SchedulerStatus row (id=1) with new counters + nextTickAt.
# # #       5. Commit + return summary dict.
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
 
# # #         # ── Step 1: load SchedulerStatus row (create if absent) ──────────
# # #         # FIX: wrap in try/except — SchedulerStatus table may not exist in
# # #         # partially-provisioned tenant schemas (migration 0002 not yet run).
# # #         # In that case skip the status tracking but still attempt sends.
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
# # #                 logger.warning(
# # #                     "scheduler.tick.scheduler_status_missing",
# # #                     schema=schema_name,
# # #                     hint="Run alembic upgrade head to create SchedulerStatus table",
# # #                 )
# # #             else:
# # #                 raise
 
# # #         sent = 0
# # #         skipped = 0
# # #         try:
# # #             # ── Step 2: load Scheduled sequences with touchNumber<=6 ─────
# # #             # Guard against UndefinedTableError on a fresh tenant schema
# # #             # (tables may not exist yet) or InFailedSQLTransactionError
# # #             # if a prior query in this session aborted the transaction.
# # #             # Roll back and skip cleanly rather than poisoning the session.
# # #             try:
# # #                 seq_result = await session.execute(
# # #                     select(Sequence)
# # #                     .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
# # #                     .where(Sequence.touchNumber <= 6)
# # #                     .order_by(Sequence.createdAt.asc())
# # #                     .limit(500)
# # #                 )
# # #                 sequences = list(seq_result.scalars().all())
# # #             except Exception as table_exc:
# # #                 err_str = str(table_exc)
# # #                 if "UndefinedTableError" in err_str or "InFailedSQLTransaction" in err_str or "does not exist" in err_str:
# # #                     import structlog as _sl
# # #                     _sl.get_logger(__name__).warning(
# # #                         "scheduler.tick.schema_not_ready",
# # #                         schema=schema_name,
# # #                         error=err_str[:200],
# # #                     )
# # #                     await session.rollback()
# # #                     summary["skipped"] = 0
# # #                     summary["sent"] = 0
# # #                     return summary
# # #                 raise
# # #             sequences = list(sequences) if not isinstance(sequences, list) else sequences
# # #             summary["candidates"] = len(sequences)
 
# # #             # Pre-load first active MailBridgeConfig for this schema (kept as
# # #             # a tenant-level fallback for sequences without an owner_user_id).
# # #             cfg_result = await session.execute(
# # #                 select(MailBridgeConfig)
# # #                 .where(MailBridgeConfig.isActive.is_(True))
# # #                 .limit(1)
# # #             )
# # #             tenant_default_config = cfg_result.scalar_one_or_none()
 
# # #             quota_service = UserEmailQuotaService()
 
# # #             for seq in sequences:
# # #                 try:
# # #                     # ── Load prospect once per sequence (cheap with session cache) ──
# # #                     prospect_result = await session.execute(
# # #                         select(Prospect).where(Prospect.id == seq.prospectId)
# # #                     )
# # #                     prospect = prospect_result.scalar_one_or_none()
 
# # #                     # Skip suppressed / no-email prospects
# # #                     if prospect is None or prospect.suppressed or not prospect.email:
# # #                         skipped += 1
# # #                         continue
 
# # #                     # ── Step 3a: business-hours filter (§9.2) ─────────────
# # #                     if not _is_business_hours(started, prospect.timezone):
# # #                         skipped += 1
# # #                         continue
 
# # #                     # ── Step 3b: PARTIAL throttle (§9.3) ──────────────────
# # #                     if (
# # #                         prospect.enrichmentTier == EnrichmentTier.PARTIAL
# # #                         and not _partial_throttle_passes(prospect.id, tick_bucket)
# # #                     ):
# # #                         skipped += 1
# # #                         continue
 
# # #                     # ── Step 3b': per-user quota enforcement (SAAS2-USER-BE §G) ──
# # #                     # For the background scheduler, the "sender" is the sequence
# # #                     # owner — the person whose MailBridge account will be used.
# # #                     # sent_by_user_id is stamped inside _send_via_mailbridge on
# # #                     # success (same value as seq_owner for scheduler-driven sends).
# # #                     seq_owner = getattr(seq, "owner_user_id", None) or "system"
# # #                     if seq_owner and seq_owner != "system":
# # #                         try:
# # #                             can_send, reason = await quota_service.check_can_send(
# # #                                 session, seq_owner, count=1
# # #                             )
# # #                         except Exception as exc:  # noqa: BLE001 — never abort the tick
# # #                             can_send, reason = False, f"quota_check_error: {exc}"
# # #                         if not can_send:
# # #                             skipped += 1
# # #                             logger.info(
# # #                                 "scheduler.sequence.quota_exceeded",
# # #                                 schema=schema_name,
# # #                                 sequence_id=seq.id,
# # #                                 user_id=seq_owner,
# # #                                 reason=reason,
# # #                             )
# # #                             continue
# # #                     else:
# # #                         reason = "ok"
 
# # #                     # ── Step 3c: per-user MailBridge resolution (SAAS2-USER-BE §G) ──
# # #                     # Use the sequence owner's MailBridge config (their connected
# # #                     # mailbox); fall back to the tenant-level default only when the
# # #                     # owner has no personal config registered.
# # #                     if seq_owner and seq_owner != "system":
# # #                         config = await _resolve_mailbridge_config(session, seq_owner)
# # #                     else:
# # #                         config = tenant_default_config
# # #                     if config is None:
# # #                         config = tenant_default_config
 
# # #                     # ── Step 3d: MailBridge dispatch (§9.5) ───────────────
# # #                     # _send_via_mailbridge stamps seq.sent_by_user_id and
# # #                     # seq.sent_via_external_user_id on the sequence row so the
# # #                     # reply-poller can poll the correct MailBridge inbox.
# # #                     msg_id = await _send_via_mailbridge(session, config, seq, user_id=seq_owner)
# # #                     # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError across schemas)
# # #                     await session.execute(
# # #                         text(
# # #                             "UPDATE \"Sequence\" SET status = 'Sent', "
# # #                             "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
# # #                             "WHERE id = :seq_id"
# # #                         ),
# # #                         {
# # #                             "sent_at": datetime.now(timezone.utc),
# # #                             "msg_id": msg_id,
# # #                             "seq_id": seq.id,
# # #                         },
# # #                     )
# # #                     sent += 1
 
# # #                     # ── Step 3e: record send against per-user quota ───────
# # #                     if seq_owner and seq_owner != "system":
# # #                         try:
# # #                             await quota_service.record_send(session, seq_owner, count=1)
# # #                         except Exception as exc:  # noqa: BLE001 — best-effort
# # #                             logger.warning(
# # #                                 "scheduler.sequence.quota_record_failed",
# # #                                 schema=schema_name,
# # #                                 sequence_id=seq.id,
# # #                                 user_id=seq_owner,
# # #                                 error=str(exc),
# # #                             )
# # #                 except Exception as exc:  # noqa: BLE001 — per-seq isolation
# # #                     skipped += 1
# # #                     logger.warning(
# # #                         "scheduler.sequence.send_failed",
# # #                         schema=schema_name,
# # #                         sequence_id=seq.id,
# # #                         error=str(exc),
# # #                     )
 
# # #             await session.commit()
# # #         finally:
# # #             # ── Step 4: update SchedulerStatus counters + nextTickAt ─────
# # #             ended = datetime.now(timezone.utc)
# # #             if status_row is not None:
# # #                 status_row.isRunning = False
# # #                 status_row.lastTickAt = started
# # #                 status_row.sentSinceLastTick = sent
# # #                 status_row.skippedSinceLastTick = skipped
# # #                 status_row.nextTickAt = started + timedelta(
# # #                     seconds=settings.SCHEDULER_TICK_SECONDS
# # #                 )
# # #                 try:
# # #                     await session.commit()
# # #                 except Exception:  # noqa: BLE001
# # #                     await session.rollback()
 
# # #         summary["sent"] = sent
# # #         summary["skipped"] = skipped
# # #         summary["ended_at"] = ended.isoformat()
# # #         summary["duration_ms"] = int((ended - started).total_seconds() * 1000)
# # #         return summary
 
 
# # # async def run_tick_all_tenants() -> dict[str, Any]:
# # #     """Run a tick across every ACTIVE tenant schema.
 
# # #     Per migration §9.6 L1362-1378: SELECT schema_name FROM public.tenants
# # #     WHERE status='ACTIVE' AND deleted_at IS NULL. Per-tenant failure is
# # #     logged + skipped — it never aborts the entire tick.
# # #     """
# # #     summary: dict[str, Any] = {
# # #         "tenants": 0,
# # #         "sent": 0,
# # #         "skipped": 0,
# # #         "failed_tenants": 0,
# # #     }
 
# # #     # Query public.tenants directly via a raw connection (not the ORM)
# # #     # so we don't pollute the tenant-schema-bound session cache.
# # #     schemas: list[str] = []
# # #     try:
# # #         async with engine.connect() as conn:
# # #             result = await conn.execute(
# # #                 text(
# # #                     "SELECT schema_name FROM public.tenants "
# # #                     "WHERE status='ACTIVE' AND deleted_at IS NULL"
# # #                 )
# # #             )
# # #             schemas = [row[0] for row in result.fetchall()]
# # #     except Exception as exc:  # noqa: BLE001
# # #         # UndefinedTableError on a fresh DB (no tenants provisioned yet) or
# # #         # a stale asyncpg per-connection statement plan — either way, there
# # #         # are no active tenant schemas to tick. Log and continue with [].
# # #         if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
# # #             raise
# # #         logger.warning("scheduler.tick.no_tenants_table", error=str(exc))
# # #         schemas = []
 
# # #     summary["tenant_count"] = len(schemas)
# # #     for schema in schemas:
# # #         try:
# # #             tick_result = await run_tick(schema)
# # #             summary["tenants"] += 1
# # #             summary["sent"] += tick_result.get("sent", 0)
# # #             summary["skipped"] += tick_result.get("skipped", 0)
# # #         except Exception as exc:  # noqa: BLE001 — per-tenant isolation
# # #             summary["failed_tenants"] += 1
# # #             logger.error(
# # #                 "scheduler.tenant_failed",
# # #                 schema=schema,
# # #                 error=str(exc),
# # #                 exc_info=True,
# # #             )
 
# # #     return summary
 
 
# # # # ── Phase 3 SchedulerService (preserved) ────────────────────────────────────
 
 
# # # class SchedulerService:
# # #     """Backwards-compatible wrapper exposing the Phase 3 status +
# # #     manual-tick endpoints. Phase 5 callers should use run_tick() /
# # #     run_tick_all_tenants() / get_scheduler() directly."""
 
# # #     def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
# # #         self._mailbridge = mailbridge or MailBridgeService()
 
# # #     async def get_status(self, db: AsyncSession) -> SchedulerStatus:
# # #         """Return the singleton status row, creating it if absent."""
# # #         result = await db.execute(
# # #             select(SchedulerStatus).where(SchedulerStatus.id == 1)
# # #         )
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
# # #         """Send up to max_send Scheduled sequences in one synchronous tick.
 
# # #         Phase 3 contract — preserved verbatim. Does NOT apply the §9.2/§9.3
# # #         business-hours + PARTIAL throttle filters (callers that want the
# # #         Phase 5 behavior should invoke run_tick() instead).
# # #         """
# # #         started = datetime.now(timezone.utc)
# # #         status = await self.get_status(db)
# # #         status.isRunning = True
# # #         await db.commit()
 
# # #         sent = 0
# # #         skipped = 0
# # #         try:
# # #             result = await db.execute(
# # #                 select(Sequence)
# # #                 .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
# # #                 .limit(max_send)
# # #             )
# # #             sequences = list(result.scalars().all())
# # #             for seq in sequences:
# # #                 # Phase 5 will add business-hours + throttle filters here.
# # #                 try:
# # #                     # Wiring audit (Task 2-e): previously this method passed
# # #                     # ``to=""`` to MailBridgeService.send with a comment saying
# # #                     # "caller resolves prospect.email" — but no caller actually
# # #                     # did so, resulting in empty-envelope stub-accepts. Resolve
# # #                     # the prospect email (with PII decrypt) here so the manual
# # #                     # tick actually delivers. Mirrors SequenceService.send_email.
# # #                     to_email = ""
# # #                     if seq.prospectId:
# # #                         p_result = await db.execute(
# # #                             select(Prospect).where(Prospect.id == seq.prospectId)
# # #                         )
# # #                         p = p_result.scalar_one_or_none()
# # #                         if p is not None:
# # #                             raw_email = getattr(p, "email", None) or ""
# # #                             if raw_email and not getattr(p, "anonymized", False):
# # #                                 try:
# # #                                     from app.services.pii_service import PiiService
 
# # #                                     to_email = (
# # #                                         PiiService().decrypt_field(raw_email)
# # #                                         or raw_email
# # #                                     )
# # #                                 except Exception:  # noqa: BLE001 — best-effort
# # #                                     to_email = raw_email
# # #                             elif raw_email:
# # #                                 to_email = raw_email
# # #                     if not to_email:
# # #                         skipped += 1
# # #                         continue
# # #                     send_result = await self._mailbridge.send(
# # #                         db=db,
# # #                         to=to_email,
# # #                         subject=seq.subjectLine or "",
# # #                         body=seq.bodyCopy or "",
# # #                         sequence_id=seq.id,
# # #                         user_id=getattr(seq, "owner_user_id", None),
# # #                     )
# # #                     if send_result.accepted:
# # #                         # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError)
# # #                         # seq.status = EmailStatus.Sent would generate $1::email_status
# # #                         # which fails across tenant schemas due to asyncpg plan cache.
# # #                         await db.execute(
# # #                             text(
# # #                                 "UPDATE \"Sequence\" SET status = 'Sent', "
# # #                                 "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
# # #                                 "WHERE id = :seq_id"
# # #                             ),
# # #                             {
# # #                                 "sent_at": datetime.now(timezone.utc),
# # #                                 "msg_id": send_result.messageId,
# # #                                 "seq_id": seq.id,
# # #                             },
# # #                         )
# # #                         sent += 1
# # #                     else:
# # #                         skipped += 1
# # #                 except Exception:  # noqa: BLE001
# # #                     skipped += 1
# # #             try:
# # #                 await db.commit()
# # #             except Exception:  # noqa: BLE001 — swallow if already aborted
# # #                 await db.rollback()
# # #         finally:
# # #             duration_ms = int(
# # #                 (datetime.now(timezone.utc) - started).total_seconds() * 1000
# # #             )
# # #             # FIX: rollback any aborted transaction before updating SchedulerStatus
# # #             # so the finally block never runs inside an aborted transaction.
# # #             try:
# # #                 await db.rollback()
# # #             except Exception:  # noqa: BLE001
# # #                 pass
# # #             try:
# # #                 await db.execute(
# # #                     text(
# # #                         'UPDATE "SchedulerStatus" SET "isRunning" = false, '
# # #                         '"lastTickAt" = :last, "nextTickAt" = :next, '
# # #                         '"sentSinceLastTick" = :sent, "skippedSinceLastTick" = :skipped, '
# # #                         '"updatedAt" = now() WHERE id = 1'
# # #                     ),
# # #                     {
# # #                         "last": started,
# # #                         "next": started + timedelta(seconds=get_settings().SCHEDULER_TICK_SECONDS),
# # #                         "sent": sent,
# # #                         "skipped": skipped,
# # #                     },
# # #                 )
# # #                 await db.commit()
# # #             except Exception as _fin_exc:  # noqa: BLE001
# # #                 logger.warning(
# # #                     "scheduler.manual_tick.status_update_failed",
# # #                     error=str(_fin_exc)[:200],
# # #                 )
# # #         return ManualTickResponse(
# # #             sent=sent,
# # #             skipped=skipped,
# # #             durationMs=duration_ms,
# # #             tickedAt=started,
# # #         )
 
# # #     async def trigger(self, db: AsyncSession) -> "TriggerResponse":
# # #         """Trigger an immediate scheduler tick via Celery or direct invocation.
 
# # #         If Celery is available and the broker is reachable, enqueues
# # #         ``autopilot.run_pipeline`` and returns immediately with the task ID
# # #         as ``runId``. Otherwise falls back to a synchronous tick and logs
# # #         a ``SchedulerRun`` row.
 
# # #         Returns a ``TriggerResponse`` with ``triggered=True`` on success.
# # #         """
# # #         from app.schemas.scheduler import TriggerResponse
 
# # #         # FIX: SchedulerRun table may not exist yet (migration 0019 creates it).
# # #         # If insert fails, continue without logging - the tick still runs.
# # #         run = None
# # #         try:
# # #             _run_obj = SchedulerRun(status="running")
# # #             db.add(_run_obj)
# # #             await db.commit()
# # #             run = await db.get(SchedulerRun, _run_obj.id)
# # #         except Exception as _exc:  # noqa: BLE001
# # #             await db.rollback()
# # #             logger.warning(
# # #                 "scheduler.trigger.run_log_skipped",
# # #                 hint="Run migration 0019 to create SchedulerRun table",
# # #                 error=str(_exc)[:200],
# # #             )
 
# # #         # Attempt Celery enqueue
# # #         try:
# # #             from app.worker.celery_app import celery_app
 
# # #             if celery_app is not None:
# # #                 result = celery_app.send_task(
# # #                     "autopilot.run_pipeline",
# # #                     kwargs={"schema_name": "current"},
# # #                 )
# # #                 if run is not None:
# # #                     run.status = "completed"
# # #                     run.completedAt = datetime.now(timezone.utc)
# # #                     await db.commit()
# # #                 return TriggerResponse(
# # #                     triggered=True,
# # #                     message="Scheduler triggered via Celery.",
# # #                     runId=result.id,
# # #                 )
# # #         except Exception as exc:  # noqa: BLE001
# # #             logger.warning("scheduler.trigger.celery_failed", error=str(exc))
 
# # #         # Fallback: synchronous tick
# # #         started = datetime.now(timezone.utc)
# # #         try:
# # #             tick_result = await self.manual_tick(
# # #                 db, tenant_scoped=True, max_send=50
# # #             )
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
# # #             return TriggerResponse(
# # #                 triggered=False,
# # #                 message=f"Scheduler tick failed: {exc}",
# # #                 runId=run.id if run else None,
# # #             )
 
# # #     async def list_runs(
# # #         self,
# # #         db: AsyncSession,
# # #         *,
# # #         limit: int = 20,
# # #         offset: int = 0,
# # #     ) -> "SchedulerRunsListResponse":
# # #         """Return recent scheduler run log entries, newest first.
 
# # #         FIX: SchedulerRun table was never in any migration — wraps queries in
# # #         try/except so the Scheduler Status page loads cleanly even on tenants
# # #         that have not run migration 0019 yet. Returns empty list in that case.
# # #         """
# # #         from app.schemas.scheduler import (
# # #             SchedulerRunResponse,
# # #             SchedulerRunsListResponse,
# # #         )
# # #         from sqlalchemy import func as sa_func
 
# # #         try:
# # #             count_result = await db.execute(
# # #                 select(sa_func.count()).select_from(SchedulerRun)
# # #             )
# # #             total = count_result.scalar() or 0
 
# # #             result = await db.execute(
# # #                 select(SchedulerRun)
# # #                 .order_by(SchedulerRun.startedAt.desc())
# # #                 .limit(limit)
# # #                 .offset(offset)
# # #             )
# # #             rows = list(result.scalars().all())
# # #             items = [SchedulerRunResponse.model_validate(r) for r in rows]
# # #             return SchedulerRunsListResponse(items=items, total=total)
# # #         except Exception as exc:  # noqa: BLE001
# # #             # Table does not exist yet - return empty list instead of crashing.
# # #             # Resolved permanently by running migration 0019.
# # #             err_str = str(exc)
# # #             if "UndefinedTableError" in err_str or "does not exist" in err_str or "undefined_table" in err_str.lower():
# # #                 await db.rollback()
# # #                 logger.warning(
# # #                     "scheduler.list_runs.table_missing",
# # #                     hint="Run migration 0019 to create SchedulerRun table",
# # #                     error=err_str[:200],
# # #                 )
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
# # logger = structlog.get_logger(__name__)
 
# # # ── Module-global singleton scheduler ──────────────────────────────────────
# # _scheduler: AsyncIOScheduler | None = None
# # # register_reply_poll_job(_scheduler)
 
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
 
# #     # Build MailBridge-compatible body text with CAN-SPAM footer.
# #     body_text = sequence.bodyCopy or ""
 
# #     # ── CAN-SPAM / NFR-19: footer enforcement ─────────────────────────────
# #     # Every commercial email must contain: physical address + unsubscribe URL.
# #     # If the sequence body lacks them, we append a minimal compliant footer
# #     # rather than blocking the send (blocking would deadlock campaigns).
# #     # Best-effort: silently skip if we can't compute tenant slug.

# #     # ── Replace {{unsubscribe_url}} placeholder if present ────────────────────
# #     # Template-send sequences store the literal placeholder in bodyCopy.
# #     # Replace it with the real URL before sending.
# #     if "{{unsubscribe_url}}" in body_text:
# #         try:
# #             from app.utils.tenant_context import resolve_tenant_slug as _rts
# #             from app.core.config import get_settings as _gs
# #             _t_slug = await _rts(db)
# #             _p_token = getattr(prospect, "unsubscribeToken", None) or ""
# #             _b = _gs().BASE_DOMAIN
# #             if _p_token and _t_slug and _b:
# #                 _real = (
# #                     f"https://{_b}/p/unsubscribe"
# #                     f"?token={_p_token}&tenant_slug={_t_slug}"
# #                 )
# #                 body_text = body_text.replace("{{unsubscribe_url}}", _real)
# #         except Exception:  # noqa: BLE001
# #             pass

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
# #                 f"https://{_base}/p/unsubscribe"
# #                 f"?token={_prospect_token}&tenant_slug={_tenant_slug}"
# #                 if _prospect_token and _tenant_slug
# #                 else ""
# #             )
# #             _footer_lines = [
# #                 "",
# #                 "---",
# #                 "This email was sent by an authorised OUTRENA user.",
# #             ]
# #             if _unsub_url:
# #                 _footer_lines.append(f"Unsubscribe: {_unsub_url}")
# #             body_text = body_text + "\n".join(_footer_lines)
# #         except Exception:  # noqa: BLE001 — footer is best-effort, never block send
# #             pass
 
# #     # Build MailBridge-compatible payload (Phase 3+ /outbound/send).
# #     # MailBridge expects: to as a list, body_html/body_text (not "body"),
# #     # and optional external_user_id for identity propagation.
# #     payload = {
# #         "to": [recipient_email],
# #         "subject": sequence.subjectLine or "",
# #         "body_html": body_text,
# #         "body_text": body_text,
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
# #                     .join(Prospect, Sequence.prospectId == Prospect.id)
# #                     .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
# #                     .where(Sequence.touchNumber <= 6)
# #                     .where(Prospect.suppressed.is_(False))   # Skip suppressed prospects at query level
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
# #                     if prospect is None or prospect.suppressed or not prospect.email:
# #                         skipped += 1
# #                         continue
 
# #                     # ── Step 3a: business-hours filter (§9.2) ─────────────
# #                     if not _is_business_hours(started, prospect.timezone):
# #                         skipped += 1
# #                         continue
 
# #                     # ── Step 3b: PARTIAL throttle (§9.3) ──────────────────
# #                     if (
# #                         prospect.enrichmentTier == EnrichmentTier.PARTIAL
# #                         and not _partial_throttle_passes(prospect.id, tick_bucket)
# #                     ):
# #                         skipped += 1
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
 
# #                     # ── Step 3e: record send against per-user quota ───────
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
# logger = structlog.get_logger(__name__)
 
# # ── Module-global singleton scheduler ──────────────────────────────────────
# _scheduler: AsyncIOScheduler | None = None
# # register_reply_poll_job(_scheduler)
 
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
#     """
#     # Resolve prospect + recipient email
#     prospect_result = await db.execute(
#         select(Prospect).where(Prospect.id == sequence.prospectId)
#     )
#     prospect = prospect_result.scalar_one_or_none()
#     if prospect is None or not prospect.email:
#         raise RuntimeError(
#             f"Prospect {sequence.prospectId} missing or has no email"
#         )
 
#     # Wiring audit (Task 2-e): the Prospect.email column is encrypted at rest
#     # when ENCRYPTION_KEY is set (production). Previously this helper passed
#     # the raw encrypted blob to MailBridge — which then attempted to deliver
#     # to a Fernet-token-looking address and bounced every send. Decrypt via
#     # PiiService before building the payload (mirrors SequenceService.send_email
#     # + ReplyDraftService.auto_reply). Best-effort: fall back to the stored
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
 
#     settings = get_settings()
 
#     # ── FR-039: DNS verification gate ────────────────────────────────────
#     # If the sending config is bound to a Domain whose SPF/DKIM/DMARC
#     # verification is failing, refuse the send and name the failing record.
#     # Domains that have never been checked (lastChecked IS NULL) are allowed
#     # through — blocking on "not yet verified" would deadlock fresh tenants.
#     if config is not None and getattr(config, "domainId", None):
#         from app.models.config_models import Domain as _Domain
 
#         dom = (
#             await db.execute(select(_Domain).where(_Domain.id == config.domainId))
#         ).scalar_one_or_none()
#         if dom is not None and dom.lastChecked is not None:
#             failing = [
#                 name
#                 for name, ok in (
#                     ("SPF", dom.spfStatus),
#                     ("DKIM", dom.dkimStatus),
#                     ("DMARC", dom.dmarcStatus),
#                 )
#                 if not ok
#             ]
#             if failing:
#                 raise RuntimeError(
#                     f"DNS verification failing for domain '{dom.domainName}': "
#                     f"{', '.join(failing)}. Fix the DNS records and re-verify "
#                     "before sending (FR-039)."
#                 )
 
#         # ── Pre-flight warmup gate (Help Guide §Domains) ─────────────────
#         # The domain must have completed at least 2 weeks of warmup before
#         # any sequence email is dispatched. This mirrors the Sequences
#         # Pre-Flight Activation Gate documented in the guide.
#         if dom is not None:
#             week = int(getattr(dom, "warmingWeek", 0) or 0)
#             if 1 <= week < 2:
#                 raise RuntimeError(
#                     f"Domain '{dom.domainName}' has only completed "
#                     f"{week} week(s) of warm-up. At least 2 weeks are "
#                     "required before sending. Use the Auto-Warm button on "
#                     "the Domains page to advance the schedule, or wait for "
#                     "the nightly auto-advance."
#                 )
 
#         # ── FR-038: warm-up escalating daily cap ────────────────────────
#         # While a domain is warming (warmingWeek 1-4), the effective daily
#         # send cap ramps: week1=10, week2=25, week3=50, week4=100, then the
#         # domain's own dailySendLimit applies. Week advancement is automated
#         # by the nightly maintenance job (advance_domain_warmup below).
#         if dom is not None:
#             effective_cap = _warmup_effective_cap(dom)
#             sent_today = (
#                 await db.execute(
#                     text(
#                         'SELECT COUNT(*) FROM "Sequence" s '
#                         'JOIN "Campaign" c ON c.id = s."campaignId" '
#                         "WHERE c.\"domainId\" = :dom_id "
#                         "  AND s.\"sentAt\" >= date_trunc('day', now())"
#                     ),
#                     {"dom_id": dom.id},
#                 )
#             ).scalar() or 0
#             if int(sent_today) >= effective_cap:
#                 raise RuntimeError(
#                     f"Warm-up daily cap reached for domain "
#                     f"'{dom.domainName}' ({sent_today}/{effective_cap}, "
#                     f"week {dom.warmingWeek}). Deferring to tomorrow "
#                     "(FR-038)."
#                 )
 
#     # Dev/CI stub: no config + no default URL → deterministic fake id.
#     if config is None and not settings.MAILBRIDGE_DEFAULT_URL:
#         msg_id = f"stub-{sequence.id}@outrena.local"
#         # Best-effort: record usage_event(email_send) so even dev-mode stub
#         # sends show up in per-tenant cost roll-ups (mirrors MailBridgeService.send).
#         await _record_usage_send_safe(db, sequence)
#         return msg_id
 
#     base_url = (config.baseUrl if config else "") or settings.MAILBRIDGE_DEFAULT_URL
 
#     # Build MailBridge-compatible body text with CAN-SPAM footer.
#     body_text = sequence.bodyCopy or ""
 
#     # ── CAN-SPAM / NFR-19: footer enforcement ─────────────────────────────
#     # Every commercial email must contain: physical address + unsubscribe URL.
#     # If the sequence body lacks them, we append a minimal compliant footer
#     # rather than blocking the send (blocking would deadlock campaigns).
#     # Best-effort: silently skip if we can't compute tenant slug.

#     # ── Replace {{unsubscribe_url}} placeholder if present ────────────────────
#     # Template-send sequences store the literal placeholder in bodyCopy.
#     # Replace it with the real URL before sending.
#     if "{{unsubscribe_url}}" in body_text:
#         try:
#             from app.utils.tenant_context import resolve_tenant_slug as _rts
#             from app.core.config import get_settings as _gs
#             _t_slug = await _rts(db)
#             _p_token = getattr(prospect, "unsubscribeToken", None) or ""
#             _b = _gs().BASE_DOMAIN
#             if _p_token and _t_slug and _b:
#                 _real = (
#                     f"https://{_b}/p/unsubscribe"
#                     f"?token={_p_token}&tenant_slug={_t_slug}"
#                 )
#                 body_text = body_text.replace("{{unsubscribe_url}}", _real)
#         except Exception:  # noqa: BLE001
#             pass

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
#                 f"https://{_base}/p/unsubscribe"
#                 f"?token={_prospect_token}&tenant_slug={_tenant_slug}"
#                 if _prospect_token and _tenant_slug
#                 else ""
#             )
#             _footer_lines = [
#                 "",
#                 "---",
#                 "This email was sent by an authorised OUTRENA user.",
#             ]
#             if _unsub_url:
#                 _footer_lines.append(f"Unsubscribe: {_unsub_url}")
#             body_text = body_text + "\n".join(_footer_lines)
#         except Exception:  # noqa: BLE001 — footer is best-effort, never block send
#             pass
 
#     # Build MailBridge-compatible payload (Phase 3+ /outbound/send).
#     # MailBridge expects: to as a list, body_html/body_text (not "body"),
#     # and optional external_user_id for identity propagation.
#     payload = {
#         "to": [recipient_email],
#         "subject": sequence.subjectLine or "",
#         "body_html": body_text,
#         "body_text": body_text,
#     }
#     # Identity propagation: tell MailBridge which connected mailbox to send from.
#     #
#     # Priority (mirrors MailBridgeService.send fix):
#     #   1. config.mailbridge_external_user_id — ONLY when the config is explicitly
#     #      owned by the sending user (config.owner_user_id == user_id), i.e. this
#     #      is the user's own per-user config with a static identity override.
#     #   2. user_id — the Keycloak UUID of the person who clicked Send.  This is
#     #      the exact value MailBridge recorded during POST /connect/{provider}/start,
#     #      so it routes through *that* user's connected mailbox — not the campaign
#     #      creator's.
#     #
#     # We record the resolved value as `sent_via_external_user_id` on the Sequence
#     # row so the reply-poller knows exactly which MailBridge identity to poll.
#     config_owner = getattr(config, "owner_user_id", None) if config else None
#     config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
#     ext_user_id = (
#         config_ext_id
#         if (config_owner and config_owner == user_id and config_ext_id)
#         else user_id
#     )
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
#                     .where(
#                         # Exclude sequences whose prospect is suppressed/unsubscribed.
#                         # Using NOT EXISTS subquery — safer than JOIN for schema-per-tenant.
#                         ~Sequence.prospectId.in_(
#                             select(Prospect.id).where(Prospect.suppressed.is_(True))
#                         )
#                     )
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
 
#             for seq in sequences:
#                 try:
#                     # ── Load prospect once per sequence (cheap with session cache) ──
#                     prospect_result = await session.execute(
#                         select(Prospect).where(Prospect.id == seq.prospectId)
#                     )
#                     prospect = prospect_result.scalar_one_or_none()
 
#                     # Skip suppressed / no-email prospects
#                     if prospect is None or prospect.suppressed or not prospect.email:
#                         skipped += 1
#                         continue
 
#                     # ── Step 3a: business-hours filter (§9.2) ─────────────
#                     if not _is_business_hours(started, prospect.timezone):
#                         skipped += 1
#                         continue
 
#                     # ── Step 3b: PARTIAL throttle (§9.3) ──────────────────
#                     if (
#                         prospect.enrichmentTier == EnrichmentTier.PARTIAL
#                         and not _partial_throttle_passes(prospect.id, tick_bucket)
#                     ):
#                         skipped += 1
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
 
#                     # ── Step 3e: record send against per-user quota ───────
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
 
 
# async def run_tick_all_tenants() -> dict[str, Any]:
#     """Run a tick across every ACTIVE tenant schema.
 
#     Per migration §9.6 L1362-1378: SELECT schema_name FROM public.tenants
#     WHERE status='ACTIVE' AND deleted_at IS NULL. Per-tenant failure is
#     logged + skipped — it never aborts the entire tick.
#     """
#     summary: dict[str, Any] = {
#         "tenants": 0,
#         "sent": 0,
#         "skipped": 0,
#         "failed_tenants": 0,
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
#         # UndefinedTableError on a fresh DB (no tenants provisioned yet) or
#         # a stale asyncpg per-connection statement plan — either way, there
#         # are no active tenant schemas to tick. Log and continue with [].
#         if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
#             raise
#         logger.warning("scheduler.tick.no_tenants_table", error=str(exc))
#         schemas = []
 
#     summary["tenant_count"] = len(schemas)
#     for schema in schemas:
#         try:
#             tick_result = await run_tick(schema)
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
#         business-hours + PARTIAL throttle filters (callers that want the
#         Phase 5 behavior should invoke run_tick() instead).
#         """
#         started = datetime.now(timezone.utc)
#         status = await self.get_status(db)
#         status.isRunning = True
#         await db.commit()
 
#         sent = 0
#         skipped = 0
#         try:
#             result = await db.execute(
#                 select(Sequence)
#                 .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
#                 .limit(max_send)
#             )
#             sequences = list(result.scalars().all())
#             for seq in sequences:
#                 # Phase 5 will add business-hours + throttle filters here.
#                 try:
#                     # Wiring audit (Task 2-e): previously this method passed
#                     # ``to=""`` to MailBridgeService.send with a comment saying
#                     # "caller resolves prospect.email" — but no caller actually
#                     # did so, resulting in empty-envelope stub-accepts. Resolve
#                     # the prospect email (with PII decrypt) here so the manual
#                     # tick actually delivers. Mirrors SequenceService.send_email.
#                     to_email = ""
#                     if seq.prospectId:
#                         p_result = await db.execute(
#                             select(Prospect).where(Prospect.id == seq.prospectId)
#                         )
#                         p = p_result.scalar_one_or_none()
#                         if p is not None:
#                             raw_email = getattr(p, "email", None) or ""
#                             if raw_email and not getattr(p, "anonymized", False):
#                                 try:
#                                     from app.services.pii_service import PiiService
 
#                                     to_email = (
#                                         PiiService().decrypt_field(raw_email)
#                                         or raw_email
#                                     )
#                                 except Exception:  # noqa: BLE001 — best-effort
#                                     to_email = raw_email
#                             elif raw_email:
#                                 to_email = raw_email
#                     if not to_email:
#                         skipped += 1
#                         continue
#                     send_result = await self._mailbridge.send(
#                         db=db,
#                         to=to_email,
#                         subject=seq.subjectLine or "",
#                         body=seq.bodyCopy or "",
#                         sequence_id=seq.id,
#                         user_id=getattr(seq, "owner_user_id", None),
#                     )
#                     if send_result.accepted:
#                         # FIX: use raw SQL to avoid ORM enum cast (CannotCoerceError)
#                         # seq.status = EmailStatus.Sent would generate $1::email_status
#                         # which fails across tenant schemas due to asyncpg plan cache.
#                         await db.execute(
#                             text(
#                                 "UPDATE \"Sequence\" SET status = 'Sent', "
#                                 "\"sentAt\" = :sent_at, \"mailBridgeMessageId\" = :msg_id "
#                                 "WHERE id = :seq_id"
#                             ),
#                             {
#                                 "sent_at": datetime.now(timezone.utc),
#                                 "msg_id": send_result.messageId,
#                                 "seq_id": seq.id,
#                             },
#                         )
#                         sent += 1
#                     else:
#                         skipped += 1
#                 except Exception:  # noqa: BLE001
#                     skipped += 1
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
logger = structlog.get_logger(__name__)
 
# ── Module-global singleton scheduler ──────────────────────────────────────
_scheduler: AsyncIOScheduler | None = None
# register_reply_poll_job(_scheduler)
 
def get_scheduler() -> AsyncIOScheduler:
    """Return the AsyncIOScheduler singleton (migration §9.1 L1266-1278).
 
    The scheduler is created lazily on first access and configured with
    max_instances=1 + coalesce=True so missed ticks never pile up. The
    interval job is registered here; start()/shutdown() are called from
    the FastAPI lifespan in app.main.create_app().
    """
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            _async_tick_wrapper,
            "interval",
            seconds=settings.SCHEDULER_TICK_SECONDS,
            id="outrena_tick",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        # Nightly cost-summary rollup — runs at 02:00 UTC every day.
        # Materialises per-user × event_type × provider cost_summaries rows
        # for the current month so the Usage dashboard reads from a fast
        # rollup table rather than scanning raw usage_events.
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
                # Reply-inbox poller — polls MailBridge for inbound replies.
        # Only registers when MAILBRIDGE_DEFAULT_URL is configured.
        from app.features.mailbridge.reply_poller import register_reply_poll_job
        register_reply_poll_job(_scheduler)
        logger.info(
            "scheduler.registered",
            tick_seconds=settings.SCHEDULER_TICK_SECONDS,
            job_id="outrena_tick",
        )
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
    """
    # Resolve prospect + recipient email
    prospect_result = await db.execute(
        select(Prospect).where(Prospect.id == sequence.prospectId)
    )
    prospect = prospect_result.scalar_one_or_none()
    if prospect is None or not prospect.email:
        raise RuntimeError(
            f"Prospect {sequence.prospectId} missing or has no email"
        )
 
    # Wiring audit (Task 2-e): the Prospect.email column is encrypted at rest
    # when ENCRYPTION_KEY is set (production). Previously this helper passed
    # the raw encrypted blob to MailBridge — which then attempted to deliver
    # to a Fernet-token-looking address and bounced every send. Decrypt via
    # PiiService before building the payload (mirrors SequenceService.send_email
    # + ReplyDraftService.auto_reply). Best-effort: fall back to the stored
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
 
    settings = get_settings()
 
    # ── FR-039: DNS verification gate ────────────────────────────────────
    # If the sending config is bound to a Domain whose SPF/DKIM/DMARC
    # verification is failing, refuse the send and name the failing record.
    # Domains that have never been checked (lastChecked IS NULL) are allowed
    # through — blocking on "not yet verified" would deadlock fresh tenants.
    if config is not None and getattr(config, "domainId", None):
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
 
        # ── Pre-flight warmup gate (Help Guide §Domains) ─────────────────
        # The domain must have completed at least 2 weeks of warmup before
        # any sequence email is dispatched. This mirrors the Sequences
        # Pre-Flight Activation Gate documented in the guide.
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
 
        # ── FR-038: warm-up escalating daily cap ────────────────────────
        # While a domain is warming (warmingWeek 1-4), the effective daily
        # send cap ramps: week1=10, week2=25, week3=50, week4=100, then the
        # domain's own dailySendLimit applies. Week advancement is automated
        # by the nightly maintenance job (advance_domain_warmup below).
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
 
    # Dev/CI stub: no config + no default URL → deterministic fake id.
    if config is None and not settings.MAILBRIDGE_DEFAULT_URL:
        msg_id = f"stub-{sequence.id}@outrena.local"
        # Best-effort: record usage_event(email_send) so even dev-mode stub
        # sends show up in per-tenant cost roll-ups (mirrors MailBridgeService.send).
        await _record_usage_send_safe(db, sequence)
        return msg_id
 
    base_url = (config.baseUrl if config else "") or settings.MAILBRIDGE_DEFAULT_URL
 
    # Build MailBridge-compatible body text with CAN-SPAM footer.
    body_text = sequence.bodyCopy or ""
 
    # ── CAN-SPAM / NFR-19: footer enforcement ─────────────────────────────
    # Every commercial email must contain: physical address + unsubscribe URL.
    # If the sequence body lacks them, we append a minimal compliant footer
    # rather than blocking the send (blocking would deadlock campaigns).
    # Best-effort: silently skip if we can't compute tenant slug.
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
 
    # Build MailBridge-compatible payload (Phase 3+ /outbound/send).
    # MailBridge expects: to as a list, body_html/body_text (not "body"),
    # and optional external_user_id for identity propagation.
    payload = {
        "to": [recipient_email],
        "subject": sequence.subjectLine or "",
        "body_html": body_text,
        "body_text": body_text,
    }
    # Identity propagation: tell MailBridge which connected mailbox to send from.
    #
    # Priority (mirrors MailBridgeService.send fix):
    #   1. config.mailbridge_external_user_id — ONLY when the config is explicitly
    #      owned by the sending user (config.owner_user_id == user_id), i.e. this
    #      is the user's own per-user config with a static identity override.
    #   2. user_id — the Keycloak UUID of the person who clicked Send.  This is
    #      the exact value MailBridge recorded during POST /connect/{provider}/start,
    #      so it routes through *that* user's connected mailbox — not the campaign
    #      creator's.
    #
    # We record the resolved value as `sent_via_external_user_id` on the Sequence
    # row so the reply-poller knows exactly which MailBridge identity to poll.
    config_owner = getattr(config, "owner_user_id", None) if config else None
    config_ext_id = getattr(config, "mailbridge_external_user_id", None) if config else None
    ext_user_id = (
        config_ext_id
        if (config_owner and config_owner == user_id and config_ext_id)
        else user_id
    )
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
            # Re-apply search_path — commit returns connection to pool and strips it.
            await session.execute(text(f'SET search_path TO "{schema_name}", public'))
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

            for seq in sequences:
                try:
                    # ── Suppression check via raw SQL (bypasses identity-map cache) ──
                    # expire_on_commit=False means SQLAlchemy never invalidates cached
                    # ORM objects. Raw SQL hits the DB directly.
                    _chk = await session.execute(
                        text(
                            'SELECT suppressed, consent_status, email '
                            'FROM "Prospect" WHERE id = :pid'
                        ),
                        {"pid": seq.prospectId},
                    )
                    _chk_row = _chk.mappings().first()
                    if (
                        _chk_row is None
                        or not _chk_row.get("email")
                        or _chk_row.get("suppressed") is True
                        or _chk_row.get("consent_status") == "withdrawn"
                    ):
                        skipped += 1
                        continue

                    # Load full ORM object for downstream helpers
                    prospect_result = await session.execute(
                        select(Prospect).where(Prospect.id == seq.prospectId)
                    )
                    prospect = prospect_result.scalar_one_or_none()
                    if prospect is None or not prospect.email:
                        skipped += 1
                        continue
 
                    # ── Step 3a: business-hours filter (§9.2) ─────────────
                    if not _is_business_hours(started, prospect.timezone):
                        skipped += 1
                        continue
 
                    # ── Step 3b: PARTIAL throttle (§9.3) ──────────────────
                    if (
                        prospect.enrichmentTier == EnrichmentTier.PARTIAL
                        and not _partial_throttle_passes(prospect.id, tick_bucket)
                    ):
                        skipped += 1
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
 
                    # ── Step 3e: record send against per-user quota ───────
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
 
 
async def run_tick_all_tenants() -> dict[str, Any]:
    """Run a tick across every ACTIVE tenant schema.
 
    Per migration §9.6 L1362-1378: SELECT schema_name FROM public.tenants
    WHERE status='ACTIVE' AND deleted_at IS NULL. Per-tenant failure is
    logged + skipped — it never aborts the entire tick.
    """
    summary: dict[str, Any] = {
        "tenants": 0,
        "sent": 0,
        "skipped": 0,
        "failed_tenants": 0,
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
        # UndefinedTableError on a fresh DB (no tenants provisioned yet) or
        # a stale asyncpg per-connection statement plan — either way, there
        # are no active tenant schemas to tick. Log and continue with [].
        if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
            raise
        logger.warning("scheduler.tick.no_tenants_table", error=str(exc))
        schemas = []
 
    summary["tenant_count"] = len(schemas)
    for schema in schemas:
        try:
            tick_result = await run_tick(schema)
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
        business-hours + PARTIAL throttle filters (callers that want the
        Phase 5 behavior should invoke run_tick() instead).
        """
        started = datetime.now(timezone.utc)
        status = await self.get_status(db)
        status.isRunning = True
        await db.commit()
 
        sent = 0
        skipped = 0
        try:
            result = await db.execute(
                select(Sequence)
                .where(Sequence.status == 'Scheduled')  # FIX: string avoids schema-qualified enum cast error across tenants
                .limit(max_send)
            )
            sequences = list(result.scalars().all())
            for seq in sequences:
                # Phase 5 will add business-hours + throttle filters here.
                try:
                    # Wiring audit (Task 2-e): previously this method passed
                    # ``to=""`` to MailBridgeService.send with a comment saying
                    # "caller resolves prospect.email" — but no caller actually
                    # did so, resulting in empty-envelope stub-accepts. Resolve
                    # the prospect email (with PII decrypt) here so the manual
                    # tick actually delivers. Mirrors SequenceService.send_email.
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