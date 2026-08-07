"""
usage_service.py — Per-user + per-tenant usage / cost tracking.

Writes raw ``usage_events`` rows fire-and-forget (a failed write must
NEVER break the LLM call / email send / enrichment it is logging). Reads
power the /api/v1/usage/* endpoints:

  - get_user_usage      — REP, current user's own usage
  - get_user_cost       — convenience: total cents for a user / period
  - get_tenant_usage    — MANAGER+, all users in the tenant
  - get_tenant_cost     — convenience: total cents for a tenant / period
  - get_manager_usage   — MANAGER+, per-user breakdown for the manager dashboard
  - get_platform_usage  — SUPER_ADMIN only, cross-tenant aggregation
  - rebuild_cost_summaries — daily Celery task materializes cost_summaries

All writes open a SHORT-LIVED session (NOT the caller's session) so a
failed commit does not roll back the caller's transaction. Reads accept
the caller's session (already locked to the right search_path) so they
participate in the request transaction.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.usage import EVENT_TYPES, UsageEvent
from app.features.usage.cost_service import CostService

logger = structlog.get_logger(__name__)


def _json_dumps(value: Any) -> str:
    """Serialize for the CAST(:meta AS jsonb) bind param."""
    import json

    return json.dumps(value, default=str)


def _period_bounds(period: str) -> tuple[datetime, datetime]:
    """Convert a "YYYY-MM" or "YYYY-MM-DD" period string to (start, end).

    ``start`` is inclusive (00:00:00 UTC of the first day); ``end`` is
    exclusive (00:00:00 UTC of the day AFTER the last day).
    """
    if not period:
        # Default to current month if empty
        now = datetime.now(timezone.utc)
        period = now.strftime("%Y-%m")
    parts = period.split("-")
    if len(parts) == 2:
        year, month = int(parts[0]), int(parts[1])
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    elif len(parts) == 3:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        start = datetime(year, month, day, tzinfo=timezone.utc)
        end = datetime(year, month, day, tzinfo=timezone.utc)
        # Add one day
        import calendar

        days_in_month = calendar.monthrange(year, month)[1]
        if day < days_in_month:
            end = datetime(year, month, day + 1, tzinfo=timezone.utc)
        elif month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    else:
        raise ValueError(f"Invalid period: {period!r} (expected YYYY-MM or YYYY-MM-DD)")

    return start, end


class UsageService:
    """Per-user + per-tenant usage recording + aggregation."""

    def __init__(self, cost_service: CostService | None = None) -> None:
        self._cost = cost_service or CostService()

    # ── Recording (write path) ───────────────────────────────────────────
    # ── FR-114: per-tenant monthly usage caps ───────────────────────────────
    # The cap is stored in public.tenant_config.features JSONB under
    # "monthly_cost_cap_cents" (0 / absent = no cap). Approaching the cap
    # (>= 80%) notifies the TENANT_ADMIN once per period via a support-style
    # log + PostHog event; at/over the cap, non-critical LLM calls raise
    # UsageCapExceeded so the caller can throttle gracefully.

    CAP_WARN_RATIO: float = 0.8

    async def get_monthly_cap_cents(
        self, db: AsyncSession, tenant_id: int | None
    ) -> int:
        """Return the tenant's monthly cost cap in cents (0 = uncapped)."""
        if tenant_id is None:
            return 0
        try:
            row = await db.execute(
                text(
                    "SELECT features FROM public.tenant_config "
                    "WHERE tenant_id = :tid"
                ),
                {"tid": tenant_id},
            )
            features = row.scalar() or {}
            if isinstance(features, str):
                import json as _json

                features = _json.loads(features or "{}")
            return int(features.get("monthly_cost_cap_cents") or 0)
        except Exception:  # noqa: BLE001 — cap lookup must never break usage
            return 0

    async def get_month_spend_cents(self, db: AsyncSession) -> int:
        """Current calendar-month spend for the active tenant schema."""
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        try:
            row = await db.execute(
                text(
                    "SELECT COALESCE(SUM(cost_cents), 0) FROM usage_events "
                    "WHERE to_char(occurred_at, 'YYYY-MM') = :period"
                ),
                {"period": period},
            )
            return int(row.scalar() or 0)
        except Exception:  # noqa: BLE001
            return 0

    async def check_llm_cap(
        self, db: AsyncSession, tenant_id: int | None
    ) -> tuple[bool, str | None]:
        """
        FR-114 gate for non-critical LLM calls.

        Returns (allowed, reason). At >= CAP_WARN_RATIO of the cap a warning
        is logged (surfaced to TENANT_ADMIN via the usage dashboard banner +
        PostHog event); at/over the cap the call is disallowed.
        """
        cap = await self.get_monthly_cap_cents(db, tenant_id)
        if cap <= 0:
            return True, None
        spend = await self.get_month_spend_cents(db)
        if spend >= cap:
            logger.warning(
                "usage.cap.exceeded", cap_cents=cap, spend_cents=spend
            )
            return False, (
                f"Monthly usage cap reached (${spend / 100:.2f} of "
                f"${cap / 100:.2f}). Non-critical AI features are paused "
                "until the period resets or the cap is raised."
            )
        if spend >= cap * self.CAP_WARN_RATIO:
            logger.warning(
                "usage.cap.approaching", cap_cents=cap, spend_cents=spend
            )
        return True, None

    async def record_event(
        self,
        tenant: str,
        user_id: str,
        event_type: str,
        provider: str | None = None,
        resource: str | None = None,
        quantity: int = 1,
        unit: str = "count",
        metadata: dict[str, Any] | None = None,
        cost_cents: int = 0,
    ) -> None:
        """Insert one ``usage_events`` row. Fire-and-forget — never raises.

        Opens a SHORT-LIVED session so a failed commit does not roll back
        the caller's transaction. The session's search_path is locked to
        the tenant schema (``tenant_{slug}``).
        """
        if event_type not in EVENT_TYPES:
            logger.warning(
                "usage_service.unknown_event_type",
                event_type=event_type,
                tenant=tenant,
            )
            event_type = "api_call"
        schema = _schema_for_tenant(tenant)
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text(f'SET search_path TO "{schema}", public'))
                await session.execute(
                    text(
                        "INSERT INTO usage_events "
                        "(user_id, event_type, provider, resource, quantity, unit, "
                        " metadata, cost_cents, occurred_at, created_at) "
                        "VALUES (:u, :et, :p, :r, :q, :un, "
                        "        CAST(:m AS jsonb), :c, NOW(), NOW())"
                    ),
                    {
                        "u": user_id,
                        "et": event_type,
                        "p": provider,
                        "r": resource,
                        "q": int(quantity or 0),
                        "un": unit,
                        "m": _json_dumps(metadata or {}),
                        "c": int(cost_cents or 0),
                    },
                )
                await session.commit()
        except Exception as exc:  # noqa: BLE001 — usage write must never break the caller
            logger.warning(
                "usage_service.record_event_failed",
                tenant=tenant,
                user_id=user_id,
                event_type=event_type,
                error=str(exc),
            )

    async def record_llm_call(
        self,
        tenant: str,
        user_id: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Compute cost via CostService then record an ``llm_call`` event.

        Cost lookup is best-effort: if it fails, the event is still
        recorded with cost_cents=0.
        """
        cost_cents = 0
        try:
            cost_cents = await self._cost.compute_llm_cost(
                provider, model, prompt_tokens, completion_tokens
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "usage_service.llm_cost_failed",
                provider=provider,
                model=model,
                error=str(exc),
            )
        # Bump Prometheus counters in the background (best-effort, never
        # blocks the caller). The metrics are also exposed at /metrics.
        try:
            from app.core.metrics import LLM_CALLS, LLM_TOKENS, LLM_COST_CENTS

            LLM_CALLS.labels(provider=provider, model=model, tenant=tenant).inc()
            LLM_TOKENS.labels(
                provider=provider, model=model, type="input", tenant=tenant
            ).inc(prompt_tokens)
            LLM_TOKENS.labels(
                provider=provider, model=model, type="output", tenant=tenant
            ).inc(completion_tokens)
            if cost_cents > 0:
                LLM_COST_CENTS.labels(provider=provider, tenant=tenant).inc(cost_cents)
        except Exception:  # noqa: BLE001
            pass

        meta = dict(metadata or {})
        meta.setdefault("prompt_tokens", prompt_tokens)
        meta.setdefault("completion_tokens", completion_tokens)
        await self.record_event(
            tenant=tenant,
            user_id=user_id,
            event_type="llm_call",
            provider=provider,
            resource=model,
            quantity=prompt_tokens + completion_tokens,
            unit="tokens",
            metadata=meta,
            cost_cents=cost_cents,
        )

    async def record_email_send(
        self,
        tenant: str,
        user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Email sends are infrastructure cost (not passed through to tenant)."""
        try:
            from app.core.metrics import EMAILS_SENT

            EMAILS_SENT.labels(tenant=tenant, user_id=user_id).inc()
        except Exception:  # noqa: BLE001
            pass
        await self.record_event(
            tenant=tenant,
            user_id=user_id,
            event_type="email_send",
            provider="smtp",
            resource=None,
            quantity=1,
            unit="emails",
            metadata=metadata,
            cost_cents=0,
        )

    async def record_prospect_enrich(
        self,
        tenant: str,
        user_id: str,
        provider: str,
        count: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Compute cost via CostService then record a ``prospect_enrich`` event."""
        cost_cents = 0
        try:
            cost_cents = await self._cost.compute_enrichment_cost(provider, count)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "usage_service.enrich_cost_failed",
                provider=provider,
                error=str(exc),
            )
        await self.record_event(
            tenant=tenant,
            user_id=user_id,
            event_type="prospect_enrich",
            provider=provider,
            resource=None,
            quantity=count,
            unit="calls",
            metadata=metadata,
            cost_cents=cost_cents,
        )

    async def record_linkedin_action(
        self,
        tenant: str,
        user_id: str,
        action_count: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record one or more LinkedIn API actions."""
        cost_cents = 0
        try:
            cost_cents = await self._cost.compute_linkedin_cost(action_count)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "usage_service.linkedin_cost_failed",
                error=str(exc),
            )
        await self.record_event(
            tenant=tenant,
            user_id=user_id,
            event_type="linkedin_action",
            provider="linkedin",
            resource=None,
            quantity=action_count,
            unit="actions",
            metadata=metadata,
            cost_cents=cost_cents,
        )

    # ── Aggregations (read path) ─────────────────────────────────────────
    async def get_user_usage(
        self,
        db: AsyncSession,
        user_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        """Aggregate the user's usage by event_type × provider."""
        rows = (
            await db.execute(
                text(
                    "SELECT event_type, provider, "
                    "       COALESCE(SUM(quantity), 0) AS total_quantity, "
                    "       COALESCE(SUM(cost_cents), 0) AS total_cost_cents, "
                    "       COUNT(*) AS event_count "
                    "FROM usage_events "
                    "WHERE user_id = :u AND occurred_at >= :s AND occurred_at < :e "
                    "GROUP BY event_type, provider "
                    "ORDER BY event_type, provider"
                ),
                {"u": user_id, "s": period_start, "e": period_end},
            )
        ).fetchall()
        breakdown = [
            {
                "event_type": r.event_type,
                "provider": r.provider,
                "total_quantity": int(r.total_quantity or 0),
                "total_cost_cents": int(r.total_cost_cents or 0),
                "event_count": int(r.event_count or 0),
            }
            for r in rows
        ]
        return {
            "user_id": user_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "breakdown": breakdown,
            "total_cost_cents": sum(b["total_cost_cents"] for b in breakdown),
        }

    async def get_tenant_usage(
        self,
        db: AsyncSession,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        """Aggregate the whole tenant's usage by event_type × provider."""
        rows = (
            await db.execute(
                text(
                    "SELECT event_type, provider, "
                    "       COALESCE(SUM(quantity), 0) AS total_quantity, "
                    "       COALESCE(SUM(cost_cents), 0) AS total_cost_cents, "
                    "       COUNT(*) AS event_count "
                    "FROM usage_events "
                    "WHERE occurred_at >= :s AND occurred_at < :e "
                    "GROUP BY event_type, provider "
                    "ORDER BY event_type, provider"
                ),
                {"s": period_start, "e": period_end},
            )
        ).fetchall()
        breakdown = [
            {
                "event_type": r.event_type,
                "provider": r.provider,
                "total_quantity": int(r.total_quantity or 0),
                "total_cost_cents": int(r.total_cost_cents or 0),
                "event_count": int(r.event_count or 0),
            }
            for r in rows
        ]
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "breakdown": breakdown,
            "total_cost_cents": sum(b["total_cost_cents"] for b in breakdown),
        }

    async def get_manager_usage(
        self,
        db: AsyncSession,
        period_start: datetime,
        period_end: datetime,
    ) -> list[dict[str, Any]]:
        """Per-user breakdown for the manager dashboard."""
        rows = (
            await db.execute(
                text(
                    "SELECT user_id, "
                    "       COALESCE(SUM(quantity), 0) AS total_quantity, "
                    "       COALESCE(SUM(cost_cents), 0) AS total_cost_cents, "
                    "       COUNT(*) AS event_count, "
                    "       COUNT(DISTINCT event_type) AS event_types "
                    "FROM usage_events "
                    "WHERE occurred_at >= :s AND occurred_at < :e "
                    "GROUP BY user_id "
                    "ORDER BY total_cost_cents DESC"
                ),
                {"s": period_start, "e": period_end},
            )
        ).fetchall()
        return [
            {
                "user_id": r.user_id,
                "total_quantity": int(r.total_quantity or 0),
                "total_cost_cents": int(r.total_cost_cents or 0),
                "event_count": int(r.event_count or 0),
                "event_types": int(r.event_types or 0),
            }
            for r in rows
        ]

    async def get_platform_usage(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        """Cross-tenant aggregation (SUPER_ADMIN only).

        Iterates every active tenant schema and sums cost / quantity /
        event_count. Uses a fresh connection per tenant so search_path
        changes don't bleed across tenants.
        """
        tenant_slugs = await _list_active_tenant_slugs()
        per_tenant: list[dict[str, Any]] = []
        total_cost_cents = 0
        total_event_count = 0
        for slug, schema in tenant_slugs:
            try:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        text(f'SET search_path TO "{schema}", public')
                    )
                    row = (
                        await session.execute(
                            text(
                                "SELECT COALESCE(SUM(cost_cents), 0) AS c, "
                                "       COUNT(*) AS n "
                                "FROM usage_events "
                                "WHERE occurred_at >= :s AND occurred_at < :e"
                            ),
                            {"s": period_start, "e": period_end},
                        )
                    ).fetchone()
                    cost = int(row.c or 0) if row else 0
                    count = int(row.n or 0) if row else 0
                    per_tenant.append({
                        "tenant_slug": slug,
                        "total_cost_cents": cost,
                        "event_count": count,
                    })
                    total_cost_cents += cost
                    total_event_count += count
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "usage_service.platform_usage_tenant_failed",
                    tenant=slug,
                    error=str(exc),
                )
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "total_cost_cents": total_cost_cents,
            "total_event_count": total_event_count,
            "per_tenant": sorted(
                per_tenant, key=lambda t: t["total_cost_cents"], reverse=True
            ),
        }

    async def get_user_cost(
        self,
        db: AsyncSession,
        user_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Return total cost (cents) for one user / period."""
        row = (
            await db.execute(
                text(
                    "SELECT COALESCE(SUM(cost_cents), 0) AS c FROM usage_events "
                    "WHERE user_id = :u AND occurred_at >= :s AND occurred_at < :e"
                ),
                {"u": user_id, "s": period_start, "e": period_end},
            )
        ).fetchone()
        return int(row.c or 0) if row else 0

    async def get_tenant_cost(
        self,
        db: AsyncSession,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Return total cost (cents) for the whole tenant / period."""
        row = (
            await db.execute(
                text(
                    "SELECT COALESCE(SUM(cost_cents), 0) AS c FROM usage_events "
                    "WHERE occurred_at >= :s AND occurred_at < :e"
                ),
                {"s": period_start, "e": period_end},
            )
        ).fetchone()
        return int(row.c or 0) if row else 0

    # ── Cost-summary materialization ─────────────────────────────────────
    async def rebuild_cost_summaries(
        self,
        tenant: str,
        period: str,
        period_type: str = "monthly",
    ) -> int:
        """Materialize ``cost_summaries`` rows for one tenant / period.

        Called by the daily Celery task (one invocation per tenant). Idempotent:
        existing rows for the period are DELETEd before re-insert.

        Returns the number of summary rows written.
        """
        schema = _schema_for_tenant(tenant)
        period_start, period_end = _period_bounds(period)

        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text(f'SET search_path TO "{schema}", public'))
                # Delete existing summaries for this period
                await session.execute(
                    text(
                        "DELETE FROM cost_summaries "
                        "WHERE period = :p AND period_type = :pt"
                    ),
                    {"p": period, "pt": period_type},
                )
                # Per-user × event_type × provider roll-up
                await session.execute(
                    text(
                        "INSERT INTO cost_summaries "
                        "(user_id, period, period_type, event_type, provider, "
                        " total_quantity, total_cost_cents, event_count, updated_at) "
                        "SELECT user_id, :p, :pt, event_type, provider, "
                        "       COALESCE(SUM(quantity), 0), "
                        "       COALESCE(SUM(cost_cents), 0), "
                        "       COUNT(*), NOW() "
                        "FROM usage_events "
                        "WHERE occurred_at >= :s AND occurred_at < :e "
                        "GROUP BY user_id, event_type, provider"
                    ),
                    {"p": period, "pt": period_type, "s": period_start, "e": period_end},
                )
                # Tenant-level roll-up (user_id = NULL)
                await session.execute(
                    text(
                        "INSERT INTO cost_summaries "
                        "(user_id, period, period_type, event_type, provider, "
                        " total_quantity, total_cost_cents, event_count, updated_at) "
                        "SELECT NULL, :p, :pt, event_type, provider, "
                        "       COALESCE(SUM(quantity), 0), "
                        "       COALESCE(SUM(cost_cents), 0), "
                        "       COUNT(*), NOW() "
                        "FROM usage_events "
                        "WHERE occurred_at >= :s AND occurred_at < :e "
                        "GROUP BY event_type, provider"
                    ),
                    {"p": period, "pt": period_type, "s": period_start, "e": period_end},
                )
                await session.commit()
                # Count what we wrote (best-effort — even if this fails the
                # materialization itself succeeded).
                row = (
                    await session.execute(
                        text(
                            "SELECT COUNT(*) AS n FROM cost_summaries "
                            "WHERE period = :p AND period_type = :pt"
                        ),
                        {"p": period, "pt": period_type},
                    )
                ).fetchone()
                return int(row.n or 0) if row else 0
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "usage_service.rebuild_failed",
                tenant=tenant,
                period=period,
                error=str(exc),
            )
            return 0

    # ── Convenience: rebuild all active tenants in parallel ──────────────
    async def rebuild_all_tenants(self, period: str, period_type: str = "monthly") -> dict[str, int]:
        """Rebuild cost_summaries for every active tenant.

        Returns ``{tenant_slug: row_count}``. Called by the daily Celery
        task ``rebuild_cost_summaries_all`` (defined in app/worker/).
        """
        tenants = await _list_active_tenant_slugs()
        results: dict[str, int] = {}
        # Parallel rebuild — each tenant runs in its own task; failures
        # are isolated (one tenant failing does not block the others).
        async def _one(slug: str) -> tuple[str, int]:
            try:
                n = await self.rebuild_cost_summaries(slug, period, period_type)
            except Exception as exc:  # noqa: BLE001
                logger.warning("usage_service.rebuild_all_failed", tenant=slug, error=str(exc))
                n = -1
            return slug, n

        gathered = await asyncio.gather(*[_one(s) for s, _ in tenants])
        for slug, n in gathered:
            results[slug] = n
        return results


# ── Helpers ─────────────────────────────────────────────────────────────────


def _schema_for_tenant(tenant: str) -> str:
    """Return the schema name for a tenant slug.

    OUTRENA's convention (migration 0001 + tenant_provisioning_service) is
    ``tenant_{slug}`` — slug is lowercased and stripped of any path-unsafe
    characters at provisioning time, so the slug we receive here is
    already safe to interpolate. We still defensively guard against
    empty / None.
    """
    if not tenant:
        return "public"
    slug = tenant.lower()
    # Defensive: strip any character that could break out of the identifier.
    safe = "".join(c for c in slug if c.isalnum() or c in ("_", "-"))
    return f"tenant_{safe}"


async def _list_active_tenant_slugs() -> list[tuple[str, str]]:
    """Return ``[(slug, schema_name), ...]`` for every active tenant."""
    async with AsyncSessionLocal() as session:
        await session.execute(text('SET search_path TO "public"'))
        rows = (
            await session.execute(
                text(
                    "SELECT slug, schema_name FROM public.tenants "
                    "WHERE deleted_at IS NULL AND status IN ('ACTIVE', 'PROVISIONING') "
                    "ORDER BY slug"
                )
            )
        ).fetchall()
    return [(r.slug, r.schema_name) for r in rows]


__all__ = ["UsageService"]
