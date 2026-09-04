# """
# user_email_quota_service.py — Per-user email quota + spam/bounce enforcement.

# Responsibilities (per SAAS2-USER-BE task spec section C):
#   - get_or_create_quota — lazily provision today's UserEmailQuota row.
#   - check_can_send      — pre-send gate: daily cap + throttle + spam/bounce.
#   - record_send         — increment emails_sent by N (after a successful send).
#   - record_bounce       — increment emails_bounced; may trip the bounce throttle.
#   - record_complaint    — increment complaints; may trip the spam-complaint throttle.
#   - reset_daily_if_needed — auto-roll the quota row at midnight UTC or 24h after window_start.
#   - get_user_quota_status    — single-user status dict (for dashboard / quota endpoint).
#   - get_tenant_quota_summary — list of all tenant users' statuses (manager dashboard).

# Thresholds are env-tunable via Settings:
#   - DEFAULT_USER_DAILY_EMAIL_QUOTA (default 100) — quota for a new sender identity.
#   - SPAM_COMPLAINT_THRESHOLD      (default 0.001 = 0.1% = 1 per 1000) — beyond this, 24h throttle.
#   - BOUNCE_RATE_THRESHOLD         (default 0.05  = 5%) — beyond this, 1h throttle.
#   - SPAM_THROTTLE_HOURS           (default 24) — throttle duration after spam trip.
#   - BOUNCE_THROTTLE_HOURS         (default 1)  — throttle duration after bounce trip.

# All public methods are async and take a tenant-scoped AsyncSession (caller is
# responsible for SET search_path via app/api/deps.get_db or scheduler setup).
# """
# from __future__ import annotations

# from datetime import date, datetime, timedelta, timezone
# from typing import Any

# import structlog
# from sqlalchemy import func, select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.config import get_settings
# from app.models.user_email import UserEmailQuota, UserSenderIdentity

# logger = structlog.get_logger(__name__)


# class UserEmailQuotaService:
#     """Per-user email quota + spam/bounce enforcement."""

#     # ── Quota row lifecycle ────────────────────────────────────────────────

#     async def get_or_create_quota(
#         self, db: AsyncSession, user_id: str, *, today: date | None = None
#     ) -> UserEmailQuota:
#         """Return (creating if absent) today's UserEmailQuota row for the user.

#         Resets counters to zero if a row for a previous date exists — this is
#         the daily auto-roll. window_start is also bumped so the 24h rolling
#         window is consistent.
#         """
#         today = today or datetime.now(timezone.utc).date()
#         result = await db.execute(
#             select(UserEmailQuota).where(
#                 UserEmailQuota.user_id == user_id,
#                 UserEmailQuota.date == today,
#             )
#         )
#         quota = result.scalar_one_or_none()
#         if quota is not None:
#             return quota

#         # No row for today — create fresh. If a previous-day row exists, its
#         # counters are simply left alone (history); we do not migrate them.
#         now = datetime.now(timezone.utc)
#         quota = UserEmailQuota(
#             user_id=user_id,
#             date=today,
#             emails_sent=0,
#             emails_bounced=0,
#             complaints=0,
#             window_start=now,
#             last_reset_at=now,
#             is_throttled=False,
#             throttled_until=None,
#         )
#         db.add(quota)
#         await db.commit()
#         quota = await db.get(UserEmailQuota, quota.id)
#         return quota

#     async def reset_daily_if_needed(
#         self, db: AsyncSession, user_id: str
#     ) -> UserEmailQuota:
#         """Auto-roll the quota row when the day or 24h window has elapsed.

#         Returns the up-to-date quota row (new or existing).
#         """
#         now = datetime.now(timezone.utc)
#         today = now.date()
#         quota = await self.get_or_create_quota(db, user_id, today=today)

#         # If is_throttled + throttled_until has passed → clear the throttle.
#         if quota.is_throttled and quota.throttled_until is not None:
#             if now >= quota.throttled_until:
#                 quota.is_throttled = False
#                 quota.throttled_until = None
#                 await db.commit()
#                 quota = await db.get(UserEmailQuota, quota.id)

#         # If window_start is > 24h ago, the window has rolled — reset counters
#         # on the same row (date is already today thanks to get_or_create_quota).
#         if (now - quota.window_start) >= timedelta(hours=24):
#             quota.emails_sent = 0
#             quota.emails_bounced = 0
#             quota.complaints = 0
#             quota.window_start = now
#             quota.last_reset_at = now
#             await db.commit()
#             quota = await db.get(UserEmailQuota, quota.id)

#         return quota

#     # ── Pre-send gate ──────────────────────────────────────────────────────

#     async def check_can_send(
#         self, db: AsyncSession, user_id: str, *, count: int = 1
#     ) -> tuple[bool, str]:
#         """Return (can_send, reason).

#         Reasons:
#           * "ok"                     — send permitted.
#           * "throttled"              — is_throttled + throttled_until not yet passed.
#           * "daily_quota_exceeded"   — emails_sent + count > daily_send_quota.
#           * "spam_threshold_exceeded"— complaint rate crossed the threshold → throttled.
#           * "bounce_threshold_exceeded" — bounce rate crossed the threshold → throttled.
#         """
#         quota = await self.reset_daily_if_needed(db, user_id)

#         # 2 — throttle check
#         if quota.is_throttled:
#             until = quota.throttled_until
#             if until is None or datetime.now(timezone.utc) < until:
#                 return (
#                     False,
#                     f"throttled until {until.isoformat() if until else 'unknown'}",
#                 )
#             # Throttle window has elapsed — clear it.
#             quota.is_throttled = False
#             quota.throttled_until = None
#             await db.commit()
#             quota = await db.get(UserEmailQuota, quota.id)

#         # 1 — daily quota check (resolve per-user quota from sender identity)
#         daily_quota = await self._resolve_daily_quota(db, user_id)
#         if quota.emails_sent + count > daily_quota:
#             return (
#                 False,
#                 f"daily_quota_exceeded (sent={quota.emails_sent}, "
#                 f"quota={daily_quota}, requested={count})",
#             )

#         # 3 — spam-complaint rate threshold (complaints / emails_sent >= threshold)
#         settings = get_settings()
#         spam_threshold = float(getattr(settings, "SPAM_COMPLAINT_THRESHOLD", 0.001))
#         if quota.emails_sent >= 1000 and quota.complaints > 0:
#             rate = quota.complaints / max(quota.emails_sent, 1)
#             if rate >= spam_threshold:
#                 await self._apply_throttle(
#                     db, quota,
#                     hours=int(getattr(settings, "SPAM_THROTTLE_HOURS", 24)),
#                     reason="spam_threshold_exceeded",
#                 )
#                 return (False, "spam_threshold_exceeded")

#         # 4 — bounce rate threshold (bounces / emails_sent >= threshold)
#         bounce_threshold = float(getattr(settings, "BOUNCE_RATE_THRESHOLD", 0.05))
#         if quota.emails_sent >= 20 and quota.emails_bounced > 0:
#             rate = quota.emails_bounced / max(quota.emails_sent, 1)
#             if rate >= bounce_threshold:
#                 await self._apply_throttle(
#                     db, quota,
#                     hours=int(getattr(settings, "BOUNCE_THROTTLE_HOURS", 1)),
#                     reason="bounce_threshold_exceeded",
#                 )
#                 return (False, "bounce_threshold_exceeded")

#         return (True, "ok")

#     # ── Record events ──────────────────────────────────────────────────────

#     async def record_send(
#         self, db: AsyncSession, user_id: str, *, count: int = 1
#     ) -> UserEmailQuota:
#         """Increment emails_sent by `count` after a successful send."""
#         quota = await self.reset_daily_if_needed(db, user_id)
#         quota.emails_sent = (quota.emails_sent or 0) + count
#         await db.commit()
#         quota = await db.get(UserEmailQuota, quota.id)
#         return quota

#     async def record_bounce(
#         self, db: AsyncSession, user_id: str, *, count: int = 1
#     ) -> UserEmailQuota:
#         """Increment emails_bounced; auto-throttle if bounce-rate threshold crossed."""
#         quota = await self.reset_daily_if_needed(db, user_id)
#         quota.emails_bounced = (quota.emails_bounced or 0) + count
#         await db.commit()
#         quota = await db.get(UserEmailQuota, quota.id)

#         # Re-evaluate bounce threshold after recording.
#         settings = get_settings()
#         bounce_threshold = float(getattr(settings, "BOUNCE_RATE_THRESHOLD", 0.05))
#         if quota.emails_sent >= 20 and quota.emails_bounced > 0:
#             rate = quota.emails_bounced / max(quota.emails_sent, 1)
#             if rate >= bounce_threshold and not quota.is_throttled:
#                 await self._apply_throttle(
#                     db, quota,
#                     hours=int(getattr(settings, "BOUNCE_THROTTLE_HOURS", 1)),
#                     reason="bounce_threshold_exceeded",
#                 )
#         return quota

#     async def record_complaint(
#         self, db: AsyncSession, user_id: str, *, count: int = 1
#     ) -> UserEmailQuota:
#         """Increment complaints; auto-throttle if spam-complaint threshold crossed."""
#         quota = await self.reset_daily_if_needed(db, user_id)
#         quota.complaints = (quota.complaints or 0) + count
#         await db.commit()
#         quota = await db.get(UserEmailQuota, quota.id)

#         # Re-evaluate spam threshold after recording.
#         settings = get_settings()
#         spam_threshold = float(getattr(settings, "SPAM_COMPLAINT_THRESHOLD", 0.001))
#         if quota.emails_sent >= 1000 and quota.complaints > 0:
#             rate = quota.complaints / max(quota.emails_sent, 1)
#             if rate >= spam_threshold and not quota.is_throttled:
#                 await self._apply_throttle(
#                     db, quota,
#                     hours=int(getattr(settings, "SPAM_THROTTLE_HOURS", 24)),
#                     reason="spam_threshold_exceeded",
#                 )
#         return quota

#     # ── Read paths (for dashboard + endpoints) ─────────────────────────────

#     async def get_user_quota_status(
#         self, db: AsyncSession, user_id: str
#     ) -> dict[str, Any]:
#         """Return the user's current-day quota + throttle status as a dict."""
#         quota = await self.reset_daily_if_needed(db, user_id)
#         daily_quota = await self._resolve_daily_quota(db, user_id)
#         remaining = max(0, daily_quota - quota.emails_sent)
#         used_pct = round((quota.emails_sent / daily_quota * 100), 2) if daily_quota else 0.0
#         bounce_rate = (
#             round(quota.emails_bounced / quota.emails_sent, 4)
#             if quota.emails_sent
#             else 0.0
#         )
#         complaint_rate = (
#             round(quota.complaints / quota.emails_sent, 4)
#             if quota.emails_sent
#             else 0.0
#         )
#         return {
#             "user_id": user_id,
#             "date": quota.date.isoformat(),
#             "emails_sent": quota.emails_sent,
#             "emails_bounced": quota.emails_bounced,
#             "complaints": quota.complaints,
#             "daily_quota": daily_quota,
#             "remaining": remaining,
#             "used_pct": used_pct,
#             "bounce_rate": bounce_rate,
#             "complaint_rate": complaint_rate,
#             "is_throttled": quota.is_throttled,
#             "throttled_until": (
#                 quota.throttled_until.isoformat() if quota.throttled_until else None
#             ),
#             "window_start": quota.window_start.isoformat(),
#             "last_reset_at": quota.last_reset_at.isoformat(),
#         }

#     async def get_tenant_quota_summary(
#         self, db: AsyncSession
#     ) -> list[dict[str, Any]]:
#         """Return quota status for every user with activity today.

#         Used by the manager dashboard. Each entry is the same shape as
#         get_user_quota_status. Users with no row today are omitted (their
#         status is trivially "all zero").
#         """
#         today = datetime.now(timezone.utc).date()
#         result = await db.execute(
#             select(UserEmailQuota).where(UserEmailQuota.date == today)
#         )
#         rows = list(result.scalars().all())
#         statuses: list[dict[str, Any]] = []
#         for row in rows:
#             daily_quota = await self._resolve_daily_quota(db, row.user_id)
#             remaining = max(0, daily_quota - row.emails_sent)
#             used_pct = (
#                 round(row.emails_sent / daily_quota * 100, 2) if daily_quota else 0.0
#             )
#             bounce_rate = (
#                 round(row.emails_bounced / row.emails_sent, 4)
#                 if row.emails_sent
#                 else 0.0
#             )
#             complaint_rate = (
#                 round(row.complaints / row.emails_sent, 4)
#                 if row.emails_sent
#                 else 0.0
#             )
#             statuses.append(
#                 {
#                     "user_id": row.user_id,
#                     "date": row.date.isoformat(),
#                     "emails_sent": row.emails_sent,
#                     "emails_bounced": row.emails_bounced,
#                     "complaints": row.complaints,
#                     "daily_quota": daily_quota,
#                     "remaining": remaining,
#                     "used_pct": used_pct,
#                     "bounce_rate": bounce_rate,
#                     "complaint_rate": complaint_rate,
#                     "is_throttled": row.is_throttled,
#                     "throttled_until": (
#                         row.throttled_until.isoformat()
#                         if row.throttled_until
#                         else None
#                     ),
#                     "window_start": row.window_start.isoformat(),
#                     "last_reset_at": row.last_reset_at.isoformat(),
#                 }
#             )
#         return statuses

#     async def check_spam_threshold(
#         self, db: AsyncSession, user_id: str
#     ) -> tuple[bool, str]:
#         """Return (is_exceeded, reason). Side-effect-free check (no throttle write)."""
#         quota = await self.reset_daily_if_needed(db, user_id)
#         settings = get_settings()
#         spam_threshold = float(getattr(settings, "SPAM_COMPLAINT_THRESHOLD", 0.001))
#         bounce_threshold = float(getattr(settings, "BOUNCE_RATE_THRESHOLD", 0.05))
#         if quota.emails_sent >= 1000 and quota.complaints > 0:
#             rate = quota.complaints / quota.emails_sent
#             if rate >= spam_threshold:
#                 return (True, "spam_threshold_exceeded")
#         if quota.emails_sent >= 20 and quota.emails_bounced > 0:
#             rate = quota.emails_bounced / quota.emails_sent
#             if rate >= bounce_threshold:
#                 return (True, "bounce_threshold_exceeded")
#         return (False, "ok")

#     # ── Helpers ────────────────────────────────────────────────────────────

#     async def _resolve_daily_quota(
#         self, db: AsyncSession, user_id: str
#     ) -> int:
#         """Return the user's daily send quota.

#         Resolution order:
#           1. UserSenderIdentity.daily_send_quota on the user's default identity.
#           2. UserSenderIdentity.daily_send_quota on any of the user's identities.
#           3. Settings.DEFAULT_USER_DAILY_EMAIL_QUOTA fallback.
#         """
#         # Default identity first.
#         result = await db.execute(
#             select(UserSenderIdentity)
#             .where(
#                 UserSenderIdentity.user_id == user_id,
#                 UserSenderIdentity.is_default.is_(True),
#             )
#             .limit(1)
#         )
#         identity = result.scalar_one_or_none()
#         if identity is not None:
#             return int(identity.daily_send_quota)

#         # Fall back to any identity for the user.
#         result = await db.execute(
#             select(UserSenderIdentity)
#             .where(UserSenderIdentity.user_id == user_id)
#             .limit(1)
#         )
#         identity = result.scalar_one_or_none()
#         if identity is not None:
#             return int(identity.daily_send_quota)

#         return int(getattr(get_settings(), "DEFAULT_USER_DAILY_EMAIL_QUOTA", 100))

#     async def _apply_throttle(
#         self,
#         db: AsyncSession,
#         quota: UserEmailQuota,
#         *,
#         hours: int,
#         reason: str,
#     ) -> None:
#         """Flip is_throttled=True + set throttled_until = now + hours."""
#         quota.is_throttled = True
#         quota.throttled_until = datetime.now(timezone.utc) + timedelta(hours=hours)
#         await db.commit()
#         quota = await db.get(UserEmailQuota, quota.id)
#         logger.warning(
#             "user_email_quota.throttled",
#             user_id=quota.user_id,
#             reason=reason,
#             throttled_until=quota.throttled_until.isoformat(),
#         )


# __all__ = ["UserEmailQuotaService"]

"""
user_email_quota_service.py — Per-user email quota + spam/bounce enforcement.

Responsibilities (per SAAS2-USER-BE task spec section C):
  - get_or_create_quota — lazily provision today's UserEmailQuota row.
  - check_can_send      — pre-send gate: daily cap + throttle + spam/bounce.
  - record_send         — increment emails_sent by N (after a successful send).
  - record_bounce       — increment emails_bounced; may trip the bounce throttle.
  - record_complaint    — increment complaints; may trip the spam-complaint throttle.
  - reset_daily_if_needed — auto-roll the quota row at midnight UTC or 24h after window_start.
  - get_user_quota_status    — single-user status dict (for dashboard / quota endpoint).
  - get_tenant_quota_summary — list of all tenant users' statuses (manager dashboard).

Thresholds are env-tunable via Settings:
  - DEFAULT_USER_DAILY_EMAIL_QUOTA (default 100) — quota for a new sender identity.
  - SPAM_COMPLAINT_THRESHOLD      (default 0.001 = 0.1% = 1 per 1000) — beyond this, 24h throttle.
  - BOUNCE_RATE_THRESHOLD         (default 0.05  = 5%) — beyond this, 1h throttle.
  - SPAM_THROTTLE_HOURS           (default 24) — throttle duration after spam trip.
  - BOUNCE_THROTTLE_HOURS         (default 1)  — throttle duration after bounce trip.

All public methods are async and take a tenant-scoped AsyncSession (caller is
responsible for SET search_path via app/api/deps.get_db or scheduler setup).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user_email import UserEmailQuota, UserSenderIdentity

logger = structlog.get_logger(__name__)


class UserEmailQuotaService:
    """Per-user email quota + spam/bounce enforcement."""

    # ── Quota row lifecycle ────────────────────────────────────────────────

    async def get_or_create_quota(
        self, db: AsyncSession, user_id: str, *, today: date | None = None
    ) -> UserEmailQuota:
        """Return (creating if absent) today's UserEmailQuota row for the user.

        Resets counters to zero if a row for a previous date exists — this is
        the daily auto-roll. window_start is also bumped so the 24h rolling
        window is consistent.
        """
        today = today or datetime.now(timezone.utc).date()
        result = await db.execute(
            select(UserEmailQuota).where(
                UserEmailQuota.user_id == user_id,
                UserEmailQuota.date == today,
            )
        )
        quota = result.scalar_one_or_none()
        if quota is not None:
            return quota

        # No row for today — create fresh. If a previous-day row exists, its
        # counters are simply left alone (history); we do not migrate them.
        now = datetime.now(timezone.utc)
        quota = UserEmailQuota(
            user_id=user_id,
            date=today,
            emails_sent=0,
            emails_bounced=0,
            complaints=0,
            window_start=now,
            last_reset_at=now,
            is_throttled=False,
            throttled_until=None,
        )
        db.add(quota)
        await db.commit()
        quota = await db.get(UserEmailQuota, quota.id)
        return quota

    async def reset_daily_if_needed(
        self, db: AsyncSession, user_id: str
    ) -> UserEmailQuota:
        """Auto-roll the quota row when the day or 24h window has elapsed.

        Returns the up-to-date quota row (new or existing).
        """
        now = datetime.now(timezone.utc)
        today = now.date()
        quota = await self.get_or_create_quota(db, user_id, today=today)

        # If is_throttled + throttled_until has passed → clear the throttle.
        if quota.is_throttled and quota.throttled_until is not None:
            if now >= quota.throttled_until:
                quota.is_throttled = False
                quota.throttled_until = None
                await db.commit()
                quota = await db.get(UserEmailQuota, quota.id)

        # If window_start is > 24h ago, the window has rolled — reset counters
        # on the same row (date is already today thanks to get_or_create_quota).
        if (now - quota.window_start) >= timedelta(hours=24):
            quota.emails_sent = 0
            quota.emails_bounced = 0
            quota.complaints = 0
            quota.window_start = now
            quota.last_reset_at = now
            await db.commit()
            quota = await db.get(UserEmailQuota, quota.id)

        return quota

    # ── Pre-send gate ──────────────────────────────────────────────────────

    async def check_can_send(
        self, db: AsyncSession, user_id: str, *, count: int = 1
    ) -> tuple[bool, str]:
        """Return (can_send, reason).

        Reasons:
          * "ok"                     — send permitted.
          * "throttled"              — is_throttled + throttled_until not yet passed.
          * "daily_quota_exceeded"   — emails_sent + count > daily_send_quota.
          * "spam_threshold_exceeded"— complaint rate crossed the threshold → throttled.
          * "bounce_threshold_exceeded" — bounce rate crossed the threshold → throttled.
        """
        quota = await self.reset_daily_if_needed(db, user_id)

        # 2 — throttle check
        if quota.is_throttled:
            until = quota.throttled_until
            if until is None or datetime.now(timezone.utc) < until:
                return (
                    False,
                    f"throttled until {until.isoformat() if until else 'unknown'}",
                )
            # Throttle window has elapsed — clear it.
            quota.is_throttled = False
            quota.throttled_until = None
            await db.commit()
            quota = await db.get(UserEmailQuota, quota.id)

        # 1 — daily quota check (resolve per-user quota from sender identity)
        daily_quota = await self._resolve_daily_quota(db, user_id)
        if quota.emails_sent + count > daily_quota:
            return (
                False,
                f"daily_quota_exceeded (sent={quota.emails_sent}, "
                f"quota={daily_quota}, requested={count})",
            )

        # 3 — spam-complaint rate threshold (complaints / emails_sent >= threshold)
        settings = get_settings()
        spam_threshold = float(getattr(settings, "SPAM_COMPLAINT_THRESHOLD", 0.001))
        if quota.emails_sent >= 1000 and quota.complaints > 0:
            rate = quota.complaints / max(quota.emails_sent, 1)
            if rate >= spam_threshold:
                await self._apply_throttle(
                    db, quota,
                    hours=int(getattr(settings, "SPAM_THROTTLE_HOURS", 24)),
                    reason="spam_threshold_exceeded",
                )
                return (False, "spam_threshold_exceeded")

        # 4 — bounce rate threshold (bounces / emails_sent >= threshold)
        bounce_threshold = float(getattr(settings, "BOUNCE_RATE_THRESHOLD", 0.05))
        if quota.emails_sent >= 20 and quota.emails_bounced > 0:
            rate = quota.emails_bounced / max(quota.emails_sent, 1)
            if rate >= bounce_threshold:
                await self._apply_throttle(
                    db, quota,
                    hours=int(getattr(settings, "BOUNCE_THROTTLE_HOURS", 1)),
                    reason="bounce_threshold_exceeded",
                )
                return (False, "bounce_threshold_exceeded")

        return (True, "ok")

    # ── Record events ──────────────────────────────────────────────────────

    async def record_send(
        self, db: AsyncSession, user_id: str, *, count: int = 1
    ) -> UserEmailQuota:
        """Increment emails_sent by `count` after a successful send."""
        quota = await self.reset_daily_if_needed(db, user_id)
        quota.emails_sent = (quota.emails_sent or 0) + count
        await db.commit()
        quota = await db.get(UserEmailQuota, quota.id)
        return quota

    async def release_send(
        self, db: AsyncSession, user_id: str, *, count: int = 1
    ) -> UserEmailQuota:
        """Release a previously-reserved send count (BatchSend only).

        BatchSend reserves quota upfront — record_send(count=N) is called
        the moment a batch of N messages is POSTed to MailBridge, before
        any of them are actually confirmed sent — because recording only
        after the completion webhook leaves a window where a second
        scheduler tick sees "quota available" and sends the same user
        another full batch before the first batch's webhook has arrived.

        When the completion webhook comes back and some of those N
        messages actually failed, the reservation for the failed portion
        must be given back so a legitimate later send isn't blocked by
        quota that was never actually used. emails_sent is floored at 0.
        """
        quota = await self.reset_daily_if_needed(db, user_id)
        quota.emails_sent = max(0, (quota.emails_sent or 0) - count)
        await db.commit()
        quota = await db.get(UserEmailQuota, quota.id)
        return quota

    async def record_bounce(
        self, db: AsyncSession, user_id: str, *, count: int = 1
    ) -> UserEmailQuota:
        """Increment emails_bounced; auto-throttle if bounce-rate threshold crossed."""
        quota = await self.reset_daily_if_needed(db, user_id)
        quota.emails_bounced = (quota.emails_bounced or 0) + count
        await db.commit()
        quota = await db.get(UserEmailQuota, quota.id)

        # Re-evaluate bounce threshold after recording.
        settings = get_settings()
        bounce_threshold = float(getattr(settings, "BOUNCE_RATE_THRESHOLD", 0.05))
        if quota.emails_sent >= 20 and quota.emails_bounced > 0:
            rate = quota.emails_bounced / max(quota.emails_sent, 1)
            if rate >= bounce_threshold and not quota.is_throttled:
                await self._apply_throttle(
                    db, quota,
                    hours=int(getattr(settings, "BOUNCE_THROTTLE_HOURS", 1)),
                    reason="bounce_threshold_exceeded",
                )
        return quota

    async def record_complaint(
        self, db: AsyncSession, user_id: str, *, count: int = 1
    ) -> UserEmailQuota:
        """Increment complaints; auto-throttle if spam-complaint threshold crossed."""
        quota = await self.reset_daily_if_needed(db, user_id)
        quota.complaints = (quota.complaints or 0) + count
        await db.commit()
        quota = await db.get(UserEmailQuota, quota.id)

        # Re-evaluate spam threshold after recording.
        settings = get_settings()
        spam_threshold = float(getattr(settings, "SPAM_COMPLAINT_THRESHOLD", 0.001))
        if quota.emails_sent >= 1000 and quota.complaints > 0:
            rate = quota.complaints / max(quota.emails_sent, 1)
            if rate >= spam_threshold and not quota.is_throttled:
                await self._apply_throttle(
                    db, quota,
                    hours=int(getattr(settings, "SPAM_THROTTLE_HOURS", 24)),
                    reason="spam_threshold_exceeded",
                )
        return quota

    # ── Read paths (for dashboard + endpoints) ─────────────────────────────

    async def get_user_quota_status(
        self, db: AsyncSession, user_id: str
    ) -> dict[str, Any]:
        """Return the user's current-day quota + throttle status as a dict."""
        quota = await self.reset_daily_if_needed(db, user_id)
        daily_quota = await self._resolve_daily_quota(db, user_id)
        remaining = max(0, daily_quota - quota.emails_sent)
        used_pct = round((quota.emails_sent / daily_quota * 100), 2) if daily_quota else 0.0
        bounce_rate = (
            round(quota.emails_bounced / quota.emails_sent, 4)
            if quota.emails_sent
            else 0.0
        )
        complaint_rate = (
            round(quota.complaints / quota.emails_sent, 4)
            if quota.emails_sent
            else 0.0
        )
        return {
            "user_id": user_id,
            "date": quota.date.isoformat(),
            "emails_sent": quota.emails_sent,
            "emails_bounced": quota.emails_bounced,
            "complaints": quota.complaints,
            "daily_quota": daily_quota,
            "remaining": remaining,
            "used_pct": used_pct,
            "bounce_rate": bounce_rate,
            "complaint_rate": complaint_rate,
            "is_throttled": quota.is_throttled,
            "throttled_until": (
                quota.throttled_until.isoformat() if quota.throttled_until else None
            ),
            "window_start": quota.window_start.isoformat(),
            "last_reset_at": quota.last_reset_at.isoformat(),
        }

    async def get_tenant_quota_summary(
        self, db: AsyncSession
    ) -> list[dict[str, Any]]:
        """Return quota status for every user with activity today.

        Used by the manager dashboard. Each entry is the same shape as
        get_user_quota_status. Users with no row today are omitted (their
        status is trivially "all zero").
        """
        today = datetime.now(timezone.utc).date()
        result = await db.execute(
            select(UserEmailQuota).where(UserEmailQuota.date == today)
        )
        rows = list(result.scalars().all())
        statuses: list[dict[str, Any]] = []
        for row in rows:
            daily_quota = await self._resolve_daily_quota(db, row.user_id)
            remaining = max(0, daily_quota - row.emails_sent)
            used_pct = (
                round(row.emails_sent / daily_quota * 100, 2) if daily_quota else 0.0
            )
            bounce_rate = (
                round(row.emails_bounced / row.emails_sent, 4)
                if row.emails_sent
                else 0.0
            )
            complaint_rate = (
                round(row.complaints / row.emails_sent, 4)
                if row.emails_sent
                else 0.0
            )
            statuses.append(
                {
                    "user_id": row.user_id,
                    "date": row.date.isoformat(),
                    "emails_sent": row.emails_sent,
                    "emails_bounced": row.emails_bounced,
                    "complaints": row.complaints,
                    "daily_quota": daily_quota,
                    "remaining": remaining,
                    "used_pct": used_pct,
                    "bounce_rate": bounce_rate,
                    "complaint_rate": complaint_rate,
                    "is_throttled": row.is_throttled,
                    "throttled_until": (
                        row.throttled_until.isoformat()
                        if row.throttled_until
                        else None
                    ),
                    "window_start": row.window_start.isoformat(),
                    "last_reset_at": row.last_reset_at.isoformat(),
                }
            )
        return statuses

    async def check_spam_threshold(
        self, db: AsyncSession, user_id: str
    ) -> tuple[bool, str]:
        """Return (is_exceeded, reason). Side-effect-free check (no throttle write)."""
        quota = await self.reset_daily_if_needed(db, user_id)
        settings = get_settings()
        spam_threshold = float(getattr(settings, "SPAM_COMPLAINT_THRESHOLD", 0.001))
        bounce_threshold = float(getattr(settings, "BOUNCE_RATE_THRESHOLD", 0.05))
        if quota.emails_sent >= 1000 and quota.complaints > 0:
            rate = quota.complaints / quota.emails_sent
            if rate >= spam_threshold:
                return (True, "spam_threshold_exceeded")
        if quota.emails_sent >= 20 and quota.emails_bounced > 0:
            rate = quota.emails_bounced / quota.emails_sent
            if rate >= bounce_threshold:
                return (True, "bounce_threshold_exceeded")
        return (False, "ok")

    # ── Helpers ────────────────────────────────────────────────────────────

    async def _resolve_daily_quota(
        self, db: AsyncSession, user_id: str
    ) -> int:
        """Return the user's daily send quota.

        Resolution order:
          1. UserSenderIdentity.daily_send_quota on the user's default identity.
          2. UserSenderIdentity.daily_send_quota on any of the user's identities.
          3. Settings.DEFAULT_USER_DAILY_EMAIL_QUOTA fallback.
        """
        # Default identity first.
        result = await db.execute(
            select(UserSenderIdentity)
            .where(
                UserSenderIdentity.user_id == user_id,
                UserSenderIdentity.is_default.is_(True),
            )
            .limit(1)
        )
        identity = result.scalar_one_or_none()
        if identity is not None:
            return int(identity.daily_send_quota)

        # Fall back to any identity for the user.
        result = await db.execute(
            select(UserSenderIdentity)
            .where(UserSenderIdentity.user_id == user_id)
            .limit(1)
        )
        identity = result.scalar_one_or_none()
        if identity is not None:
            return int(identity.daily_send_quota)

        return int(getattr(get_settings(), "DEFAULT_USER_DAILY_EMAIL_QUOTA", 100))

    async def _apply_throttle(
        self,
        db: AsyncSession,
        quota: UserEmailQuota,
        *,
        hours: int,
        reason: str,
    ) -> None:
        """Flip is_throttled=True + set throttled_until = now + hours."""
        quota.is_throttled = True
        quota.throttled_until = datetime.now(timezone.utc) + timedelta(hours=hours)
        await db.commit()
        quota = await db.get(UserEmailQuota, quota.id)
        logger.warning(
            "user_email_quota.throttled",
            user_id=quota.user_id,
            reason=reason,
            throttled_until=quota.throttled_until.isoformat(),
        )


__all__ = ["UserEmailQuotaService"]