"""
retention_service.py — Enforce data-retention policies per data type.

GDPR Article 5(1)(e) requires personal data be kept "in a form which
permits identification of data subjects for no longer than is necessary".
This service enforces the per-data-type retention schedule declared in
``RETENTION_POLICIES`` (below) — either anonymising PII (Article 17(3)(e)
carve-out for stats) or hard-deleting the row when the retention window
elapses.

The persisted policy catalog lives in ``public.retention_policies``
(migration 0007) — operators can override days / action via the
``/api/v1/retention`` router (SUPER_ADMIN). The in-memory dict below is
the boot-strapped default that the migration seeds.

Enforcement model:
  - Tenant-scoped policies (prospects_inactive, consent_logs,
    email_events, support_tickets_resolved) run inside a session locked
    to the tenant schema via ``SET search_path TO "<schema>", public``.
  - Public-schema policies (audit_logs) run inside a public-only session.

All queries are idempotent — re-running enforcement on the same day
produces the same result. Counts returned by ``get_policy_status`` are
the rows that WOULD be affected (dry-run view); enforcement actually
mutates them.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.utils.slug import schema_name_for

logger = structlog.get_logger(__name__)


class RetentionService:
    """Enforce per-data-type retention policies for a tenant."""

    # In-memory default policy catalog. The migration 0007 seeds these
    # rows into public.retention_policies; operators can override via the
    # /api/v1/retention router (SUPER_ADMIN).
    RETENTION_POLICIES: dict[str, dict[str, Any]] = {
        # 2 years of prospect inactivity, then anonymise (keep for stats).
        "prospects_inactive": {
            "days": 730,
            "action": "anonymize",
            "description": (
                "Prospects with no activity (no email reply, no meeting, "
                "no deal update) in the last 2 years are anonymised. The "
                "row is retained for aggregate stats; PII is purged."
            ),
            "scope": "tenant",
        },
        # Consent logs are immutable audit evidence — keep 3y then hard-delete.
        "consent_logs": {
            "days": 1095,
            "action": "delete",
            "description": "Consent log entries older than 3 years are hard-deleted.",
            "scope": "tenant",
        },
        # URD §6.2: tracking events — 30 days then purge. Tracking data lives
        # denormalised on Sequence (openedAt / bouncedAt timestamps + reasons);
        # this class clears the granular tracking columns on old sent rows
        # while keeping the Sequence row and its status for funnel stats.
        "tracking_events": {
            "days": 30,
            "action": "delete",
            "description": (
                "Per-email tracking detail (open/bounce timestamps, bounce "
                "reasons) older than 30 days is cleared from Sequence rows. "
                "Aggregate status is retained (URD §6.2)."
            ),
            "scope": "tenant",
        },
        # URD §6.2: reply bodies — 90 days then anonymise body, keep metadata.
        "reply_bodies": {
            "days": 90,
            "action": "anonymize",
            "description": (
                "ReplyDraft originalReply / draftBody older than 90 days are "
                "anonymised; category, status, and timestamps are retained "
                "(URD §6.2)."
            ),
            "scope": "tenant",
        },
        # URD §6.2: deal history — purge closed-lost deals after 365 days.
        "deals_closed_lost": {
            "days": 365,
            "action": "delete",
            "description": (
                "Deals in closed_lost older than 365 days are purged "
                "(URD §6.2)."
            ),
            "scope": "tenant",
        },
        # Email engagement events (opens, clicks, bounces) — 1y then delete.
        "email_events": {
            "days": 365,
            "action": "delete",
            "description": "Per-recipient email engagement events older than 1 year are deleted.",
            "scope": "tenant",
        },
        # Audit log retention aligned with SOC2 (7-year financial-controls
        # evidence window). public.platform_audit_log.
        "audit_logs": {
            "days": 2555,
            "action": "delete",
            "description": (
                "Platform audit log rows older than 7 years are hard-deleted "
                "(SOC2 retention floor)."
            ),
            "scope": "public",
        },
        # Resolved support tickets — anonymise after 1 year (keep for trend stats).
        "support_tickets_resolved": {
            "days": 365,
            "action": "anonymize",
            "description": (
                "Resolved support tickets older than 1 year are anonymised "
                "(author_user_id blanked; body replaced with [anonymized])."
            ),
            "scope": "tenant",
        },
    }

    # ── Enforcement ─────────────────────────────────────────────────────────

    async def enforce_all_policies(self, tenant_slug: str) -> dict[str, int]:
        """Run every tenant-scoped policy + the public audit-log policy.

        Returns ``{policy_name: rows_affected}``. Idempotent — re-running
        on the same day yields the same result (the rows that exceeded the
        window yesterday are already gone today).
        """
        results: dict[str, int] = {}
        schema = schema_name_for(tenant_slug)

        # Tenant-scoped policies — locked to the tenant schema.
        async with AsyncSessionLocal() as session:
            await session.execute(text(f'SET search_path TO "{schema}", public'))
            for name, cfg in self.RETENTION_POLICIES.items():
                if cfg.get("scope") != "tenant":
                    continue
                try:
                    affected = await self._enforce_tenant_policy(
                        session, name, cfg
                    )
                    results[name] = affected
                except Exception as exc:  # noqa: BLE001 — one failed policy must not abort the rest
                    logger.error(
                        "retention.policy_failed",
                        tenant=tenant_slug,
                        policy=name,
                        error=str(exc),
                    )
                    results[name] = 0
            await session.commit()

        # Public-schema policies (audit_logs).
        async with AsyncSessionLocal() as session:
            await session.execute(text('SET search_path TO "public"'))
            for name, cfg in self.RETENTION_POLICIES.items():
                if cfg.get("scope") != "public":
                    continue
                try:
                    affected = await self._enforce_public_policy(
                        session, name, cfg
                    )
                    results[name] = affected
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "retention.policy_failed",
                        tenant=tenant_slug,
                        policy=name,
                        error=str(exc),
                    )
                    results[name] = 0
            await session.commit()

        logger.info(
            "retention.enforced",
            tenant=tenant_slug,
            results=results,
        )
        return results

    # ── Status (dry-run — counts only, no mutation) ─────────────────────────

    async def get_policy_status(self, tenant_slug: str) -> dict[str, dict[str, Any]]:
        """Return ``{policy_name: {days, action, scope, affected_count}}``.

        ``affected_count`` is the number of rows that WOULD be affected if
        enforcement ran now. Used by the retention status dashboard.
        """
        status: dict[str, dict[str, Any]] = {}
        schema = schema_name_for(tenant_slug)

        async with AsyncSessionLocal() as session:
            await session.execute(text(f'SET search_path TO "{schema}", public'))
            for name, cfg in self.RETENTION_POLICIES.items():
                if cfg.get("scope") != "tenant":
                    continue
                count = await self._count_tenant_affected(session, name, cfg)
                status[name] = {
                    "days": cfg["days"],
                    "action": cfg["action"],
                    "scope": cfg["scope"],
                    "affected_count": count,
                }

        async with AsyncSessionLocal() as session:
            await session.execute(text('SET search_path TO "public"'))
            for name, cfg in self.RETENTION_POLICIES.items():
                if cfg.get("scope") != "public":
                    continue
                count = await self._count_public_affected(session, name, cfg)
                status[name] = {
                    "days": cfg["days"],
                    "action": cfg["action"],
                    "scope": cfg["scope"],
                    "affected_count": count,
                }

        return status

    # ── Tenant-scoped policy enforcement ────────────────────────────────────

    async def _enforce_tenant_policy(
        self, session: AsyncSession, name: str, cfg: dict[str, Any]
    ) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["days"])
        action = cfg["action"]

        if name == "prospects_inactive":
            # Anonymise prospects whose updatedAt is older than cutoff AND
            # not already anonymised. We rely on updatedAt as the "last
            # activity" proxy (any touch bumps updatedAt).
            if action == "anonymize":
                result = await session.execute(
                    text(
                        'UPDATE "Prospect" SET '
                        '  "firstName" = \'[anonymized]\', '
                        '  "lastName" = \'[anonymized]\', '
                        '  "email" = \'[anonymized]\', '
                        '  "linkedinUrl" = NULL, '
                        '  "deleted_at" = now(), '
                        '  "anonymized" = true '
                        'WHERE "updatedAt" < :cutoff '
                        '  AND COALESCE("anonymized", false) = false'
                    ),
                    {"cutoff": cutoff},
                )
                return result.rowcount or 0
            # Future: hard-delete option.
            result = await session.execute(
                text(
                    'DELETE FROM "Prospect" '
                    'WHERE "updatedAt" < :cutoff '
                    '  AND COALESCE("anonymized", false) = false'
                ),
                {"cutoff": cutoff},
            )
            return result.rowcount or 0

        if name == "consent_logs":
            # Hard-delete old consent log entries.
            result = await session.execute(
                text("DELETE FROM consent_logs WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            )
            return result.rowcount or 0

        if name == "email_events":
            # Email event table — guarded by table-exists check (some
            # tenants may not have the table if the feature is disabled).
            if not await self._table_exists(session, "email_events"):
                return 0
            result = await session.execute(
                text("DELETE FROM email_events WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            )
            return result.rowcount or 0

        if name == "support_tickets_resolved":
            if action == "anonymize":
                # Anonymise the AUTHOR of resolved tickets older than cutoff
                # (subject retained for trend stats; bodies blanked).
                result = await session.execute(
                    text(
                        "UPDATE support_messages SET "
                        "  body = '[anonymized]', "
                        "  author_user_id = '[anonymized]' "
                        "WHERE ticket_id IN ("
                        "  SELECT id FROM support_tickets "
                        "  WHERE status IN ('RESOLVED', 'CLOSED') "
                        "    AND COALESCE(resolved_at, updated_at) < :cutoff"
                        ")"
                    ),
                    {"cutoff": cutoff},
                )
                return result.rowcount or 0
            result = await session.execute(
                text(
                    "DELETE FROM support_tickets "
                    "WHERE status IN ('RESOLVED', 'CLOSED') "
                    "  AND COALESCE(resolved_at, updated_at) < :cutoff"
                ),
                {"cutoff": cutoff},
            )
            return result.rowcount or 0

        if name == "tracking_events":
            # Clear granular tracking detail on old sent sequences (URD 30d).
            result = await session.execute(
                text(
                    'UPDATE "Sequence" SET '
                    '  "openedAt" = NULL, '
                    '  "bouncedAt" = NULL, '
                    '  "bounceReason" = NULL '
                    'WHERE "sentAt" IS NOT NULL AND "sentAt" < :cutoff '
                    '  AND ("openedAt" IS NOT NULL OR "bouncedAt" IS NOT NULL '
                    '       OR "bounceReason" IS NOT NULL)'
                ),
                {"cutoff": cutoff},
            )
            return result.rowcount or 0

        if name == "reply_bodies":
            # Anonymise reply bodies past 90d; keep classification metadata.
            result = await session.execute(
                text(
                    'UPDATE "ReplyDraft" SET '
                    "  \"originalReply\" = '[anonymized]', "
                    "  \"draftBody\" = NULL, "
                    "  summary = NULL "
                    'WHERE "createdAt" < :cutoff '
                    "  AND \"originalReply\" != '[anonymized]'"
                ),
                {"cutoff": cutoff},
            )
            return result.rowcount or 0

        if name == "deals_closed_lost":
            result = await session.execute(
                text(
                    'DELETE FROM "Deal" '
                    "WHERE stage = 'closed_lost' "
                    '  AND COALESCE("closedAt", "updatedAt") < :cutoff'
                ),
                {"cutoff": cutoff},
            )
            return result.rowcount or 0

        logger.warning("retention.unknown_tenant_policy", policy=name)
        return 0

    # ── Public-schema policy enforcement ────────────────────────────────────

    async def _enforce_public_policy(
        self, session: AsyncSession, name: str, cfg: dict[str, Any]
    ) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["days"])

        if name == "audit_logs":
            result = await session.execute(
                text(
                    "DELETE FROM public.platform_audit_log "
                    "WHERE created_at < :cutoff"
                ),
                {"cutoff": cutoff},
            )
            return result.rowcount or 0

        logger.warning("retention.unknown_public_policy", policy=name)
        return 0

    # ── Dry-run counters ────────────────────────────────────────────────────

    async def _count_tenant_affected(
        self, session: AsyncSession, name: str, cfg: dict[str, Any]
    ) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["days"])

        if name == "prospects_inactive":
            row = await session.execute(
                text(
                    'SELECT COUNT(*) FROM "Prospect" '
                    'WHERE "updatedAt" < :cutoff '
                    '  AND COALESCE("anonymized", false) = false'
                ),
                {"cutoff": cutoff},
            )
            return int(row.scalar() or 0)

        if name == "consent_logs":
            row = await session.execute(
                text("SELECT COUNT(*) FROM consent_logs WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            )
            return int(row.scalar() or 0)

        if name == "tracking_events":
            row = await session.execute(
                text(
                    'SELECT COUNT(*) FROM "Sequence" '
                    'WHERE "sentAt" IS NOT NULL AND "sentAt" < :cutoff '
                    '  AND ("openedAt" IS NOT NULL OR "bouncedAt" IS NOT NULL '
                    '       OR "bounceReason" IS NOT NULL)'
                ),
                {"cutoff": cutoff},
            )
            return int(row.scalar() or 0)

        if name == "reply_bodies":
            row = await session.execute(
                text(
                    'SELECT COUNT(*) FROM "ReplyDraft" '
                    'WHERE "createdAt" < :cutoff '
                    "  AND \"originalReply\" != '[anonymized]'"
                ),
                {"cutoff": cutoff},
            )
            return int(row.scalar() or 0)

        if name == "deals_closed_lost":
            row = await session.execute(
                text(
                    'SELECT COUNT(*) FROM "Deal" '
                    "WHERE stage = 'closed_lost' "
                    '  AND COALESCE("closedAt", "updatedAt") < :cutoff'
                ),
                {"cutoff": cutoff},
            )
            return int(row.scalar() or 0)

        if name == "email_events":
            if not await self._table_exists(session, "email_events"):
                return 0
            row = await session.execute(
                text("SELECT COUNT(*) FROM email_events WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            )
            return int(row.scalar() or 0)

        if name == "support_tickets_resolved":
            row = await session.execute(
                text(
                    "SELECT COUNT(*) FROM support_messages sm "
                    "JOIN support_tickets st ON st.id = sm.ticket_id "
                    "WHERE st.status IN ('RESOLVED', 'CLOSED') "
                    "  AND COALESCE(st.resolved_at, st.updated_at) < :cutoff"
                ),
                {"cutoff": cutoff},
            )
            return int(row.scalar() or 0)

        return 0

    async def _count_public_affected(
        self, session: AsyncSession, name: str, cfg: dict[str, Any]
    ) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["days"])

        if name == "audit_logs":
            row = await session.execute(
                text(
                    "SELECT COUNT(*) FROM public.platform_audit_log "
                    "WHERE created_at < :cutoff"
                ),
                {"cutoff": cutoff},
            )
            return int(row.scalar() or 0)

        return 0

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    async def _table_exists(session: AsyncSession, table_name: str) -> bool:
        """Check if a table exists in the current search_path."""
        # current_schema() returns the first schema on the search_path.
        row = await session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = :name "
                "  AND table_schema IN ("
                "    SELECT unnest(string_to_array(current_setting('search_path'), ', '))"
                "  )"
            ),
            {"name": table_name},
        )
        return row.fetchone() is not None


__all__ = ["RetentionService"]
