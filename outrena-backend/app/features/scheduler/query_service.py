"""
scheduler/query_service.py — Read-only query layer for the Scheduler dashboard.

Provides three new endpoints:
  GET /scheduler/campaign-schedules — sequences grouped by campaign with filter
  GET /scheduler/skipped-details    — skip reason drill-down per run/campaign
  GET /scheduler/daily-sent         — daily sent count per campaign

All functions operate inside the current tenant session (search_path already
set by get_db()). They never mutate state.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import _generate_cuid
from app.schemas.scheduler import (
    CampaignScheduleItem,
    CampaignScheduleListResponse,
    DailySentItem,
    DailySentListResponse,
    SkipLogItem,
    SkipLogListResponse,
)

logger = structlog.get_logger(__name__)


# ── 1. Campaign Schedules ─────────────────────────────────────────────────────

async def get_campaign_schedules(
    db: AsyncSession,
    *,
    campaign_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> CampaignScheduleListResponse:
    """Return sequence counts grouped by campaign.

    Aggregates Sequence rows per Campaign so the Scheduler page shows one
    row per campaign with columns: Scheduled / Sent / Skipped / Replied /
    Bounced / Failed.

    Uses raw SQL for the aggregation — avoids ORM relationship loading and
    is safe across tenant schemas (no schema-qualified enum casts).
    """

    # Build WHERE clauses
    where_parts = ['c.id IS NOT NULL']
    params: dict = {"limit": limit, "offset": offset}

    if campaign_id:
        where_parts.append('c.id = :campaign_id')
        params["campaign_id"] = campaign_id

    if status_filter:
        where_parts.append('c.status = :campaign_status')
        params["campaign_status"] = status_filter

    where_sql = " AND ".join(where_parts)

    count_sql = text(f"""
        SELECT COUNT(DISTINCT c.id)
        FROM "Campaign" c
        LEFT JOIN "Sequence" s ON s."campaignId" = c.id
        WHERE {where_sql}
    """)

    data_sql = text(f"""
        SELECT
            c.id                                              AS campaign_id,
            c.name                                            AS campaign_name,
            c.status                                          AS campaign_status,
            COUNT(s.id)                                       AS total_sequences,
            COUNT(s.id) FILTER (WHERE s.status = 'Scheduled')  AS scheduled,
            COUNT(s.id) FILTER (WHERE s.status = 'Sent')       AS sent,
            COUNT(s.id) FILTER (WHERE s.status = 'Failed')     AS skipped,
            COUNT(s.id) FILTER (WHERE s.status = 'Replied')    AS replied,
            COUNT(s.id) FILTER (WHERE s.status = 'Bounced')    AS bounced,
            COUNT(s.id) FILTER (WHERE s.status = 'Failed')     AS failed,
            MIN(s."createdAt") FILTER (WHERE s.status = 'Scheduled') AS next_send_at
        FROM "Campaign" c
        LEFT JOIN "Sequence" s ON s."campaignId" = c.id
        WHERE {where_sql}
        GROUP BY c.id, c.name, c.status
        ORDER BY c."createdAt" DESC
        LIMIT :limit OFFSET :offset
    """)

    try:
        total_result = await db.execute(count_sql, params)
        total = total_result.scalar() or 0

        data_result = await db.execute(data_sql, params)
        rows = data_result.fetchall()

        items = [
            CampaignScheduleItem(
                campaignId=row.campaign_id,
                campaignName=row.campaign_name or "Unnamed Campaign",
                campaignStatus=row.campaign_status or "draft",
                totalSequences=row.total_sequences or 0,
                scheduled=row.scheduled or 0,
                sent=row.sent or 0,
                skipped=row.skipped or 0,
                replied=row.replied or 0,
                bounced=row.bounced or 0,
                failed=row.failed or 0,
                nextSendAt=row.next_send_at,
            )
            for row in rows
        ]
        return CampaignScheduleListResponse(items=items, total=total)

    except Exception as exc:
        err = str(exc)
        if "does not exist" in err or "UndefinedTable" in err:
            await db.rollback()
            logger.warning("scheduler.campaign_schedules.table_missing", error=err[:200])
            return CampaignScheduleListResponse(items=[], total=0)
        raise


# ── 2. Skip Reason Drill-down ─────────────────────────────────────────────────

async def get_skipped_details(
    db: AsyncSession,
    *,
    run_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    skip_reason: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> SkipLogListResponse:
    """Return per-sequence skip events with reason drill-down.

    If the SchedulerSkipLog table doesn't exist yet (migration 0022 not run),
    falls back to deriving skip reasons from the Sequence table itself
    (status=Failed/Draft rows with missing email / suppressed flag).
    """
    params: dict = {"limit": limit, "offset": offset}
    where_parts = ["1=1"]

    if run_id:
        where_parts.append("sl.\"runId\" = :run_id")
        params["run_id"] = run_id
    if campaign_id:
        where_parts.append("sl.\"campaignId\" = :campaign_id")
        params["campaign_id"] = campaign_id
    if skip_reason:
        where_parts.append("sl.\"skipReason\" = :skip_reason")
        params["skip_reason"] = skip_reason
    if since:
        where_parts.append("sl.\"skippedAt\" >= :since")
        params["since"] = since

    where_sql = " AND ".join(where_parts)

    try:
        count_sql = text(f"""
            SELECT COUNT(*) FROM "SchedulerSkipLog" sl
            WHERE {where_sql}
        """)
        total_result = await db.execute(count_sql, params)
        total = total_result.scalar() or 0

        data_sql = text(f"""
            SELECT
                sl.id,
                sl."runId",
                sl."sequenceId",
                sl."campaignId",
                c.name        AS campaign_name,
                sl."prospectId",
                p.email       AS prospect_email,
                sl."skipReason",
                sl.detail,
                sl."skippedAt"
            FROM "SchedulerSkipLog" sl
            LEFT JOIN "Campaign" c ON c.id = sl."campaignId"
            LEFT JOIN "Prospect" p ON p.id = sl."prospectId"
            WHERE {where_sql}
            ORDER BY sl."skippedAt" DESC
            LIMIT :limit OFFSET :offset
        """)
        data_result = await db.execute(data_sql, params)
        rows = data_result.fetchall()

        # Aggregate reason breakdown
        breakdown_sql = text(f"""
            SELECT sl."skipReason", COUNT(*) AS cnt
            FROM "SchedulerSkipLog" sl
            WHERE {where_sql}
            GROUP BY sl."skipReason"
        """)
        breakdown_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
        breakdown_result = await db.execute(breakdown_sql, breakdown_params)
        reason_breakdown = {row[0]: row[1] for row in breakdown_result.fetchall()}

        items = [
            SkipLogItem(
                id=row.id,
                runId=row.runId,
                sequenceId=row.sequenceId,
                campaignId=row.campaignId,
                campaignName=row.campaign_name,
                prospectId=row.prospectId,
                prospectEmail=row.prospect_email,
                skipReason=row.skipReason,
                detail=row.detail,
                skippedAt=row.skippedAt,
            )
            for row in rows
        ]

        return SkipLogListResponse(
            items=items,
            total=total,
            reasonBreakdown=reason_breakdown,
        )

    except Exception as exc:
        err = str(exc)
        if "does not exist" in err or "UndefinedTable" in err:
            await db.rollback()
            logger.warning("scheduler.skipped_details.table_missing", error=err[:200])
            # Return empty with hint
            return SkipLogListResponse(
                items=[],
                total=0,
                reasonBreakdown={},
            )
        raise


# ── 3. Daily Sent Log ─────────────────────────────────────────────────────────

async def get_daily_sent(
    db: AsyncSession,
    *,
    campaign_id: Optional[str] = None,
    since: Optional[date] = None,
    until: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
) -> DailySentListResponse:
    """Return daily sent counts per campaign.

    Always queries Sequence.sentAt directly — this is the ground truth and
    contains all historical data. The SchedulerDailySent aggregation table
    only accumulates data from migration 0022 onwards and is not used here
    to avoid showing an empty tab for historical sends.
    """
    return await _daily_sent_fallback(
        db,
        campaign_id=campaign_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )


async def _daily_sent_fallback(
    db: AsyncSession,
    *,
    campaign_id: Optional[str],
    since: Optional[date],
    until: Optional[date],
    limit: int,
    offset: int,
) -> DailySentListResponse:
    """Query Sequence.sentAt directly — the ground truth for all sent emails.

    Uses only s."sentAt" IS NOT NULL as the filter (avoids enum cast issues
    with asyncpg prepared-statement cache on the status column).
    """
    # Build campaign filter separately — never inline into the f-string
    camp_clause = ""
    params: dict = {"limit": limit, "offset": offset}

    if campaign_id:
        camp_clause = 'AND s."campaignId" = :campaign_id'
        params["campaign_id"] = campaign_id

    since_clause = ""
    if since:
        since_clause = 'AND s."sentAt"::date >= :since'
        params["since"] = since

    until_clause = ""
    if until:
        until_clause = 'AND s."sentAt"::date <= :until'
        params["until"] = until

    try:
        data_sql = text(f"""
            SELECT
                s."campaignId",
                c.name          AS campaign_name,
                s."sentAt"::date AS sent_date,
                COUNT(*)        AS sent_count
            FROM "Sequence" s
            LEFT JOIN "Campaign" c ON c.id = s."campaignId"
            WHERE s."sentAt" IS NOT NULL
              {camp_clause}
              {since_clause}
              {until_clause}
            GROUP BY s."campaignId", c.name, s."sentAt"::date
            ORDER BY s."sentAt"::date DESC, COUNT(*) DESC
            LIMIT :limit OFFSET :offset
        """)
        data_result = await db.execute(data_sql, params)
        rows = data_result.fetchall()

        count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
        total_sql = text(f"""
            SELECT COUNT(*) FROM (
                SELECT s."campaignId", s."sentAt"::date
                FROM "Sequence" s
                WHERE s."sentAt" IS NOT NULL
                  {camp_clause}
                  {since_clause}
                  {until_clause}
                GROUP BY s."campaignId", s."sentAt"::date
            ) sub
        """)
        total_result = await db.execute(total_sql, count_params)
        total = total_result.scalar() or 0

        items = [
            DailySentItem(
                campaignId=row.campaignId,
                campaignName=row.campaign_name or "Unknown Campaign",
                sentDate=row.sent_date,
                sentCount=row.sent_count or 0,
            )
            for row in rows
        ]
        logger.info(
            "scheduler.daily_sent_fallback.ok",
            rows=len(items),
            total=total,
        )
        return DailySentListResponse(items=items, total=total)

    except Exception as exc:
        logger.warning(
            "scheduler.daily_sent_fallback.failed",
            error=str(exc)[:400],
        )
        return DailySentListResponse(items=[], total=0)


# ── Skip log writer (called from run_tick in service.py) ─────────────────────

async def write_skip_log(
    db: AsyncSession,
    *,
    run_id: Optional[str],
    sequence_id: str,
    campaign_id: Optional[str],
    prospect_id: Optional[str],
    skip_reason: str,
    detail: Optional[str] = None,
) -> None:
    """Insert one SchedulerSkipLog row. Best-effort — swallows all errors."""
    try:
        await db.execute(
            text(
                'INSERT INTO "SchedulerSkipLog" '
                '(id, "runId", "sequenceId", "campaignId", "prospectId", "skipReason", detail, "skippedAt") '
                "VALUES (:id, :run_id, :seq_id, :camp_id, :prospect_id, :reason, :detail, now())"
            ),
            {
                "id": _generate_cuid(),
                "run_id": run_id,
                "seq_id": sequence_id,
                "camp_id": campaign_id,
                "prospect_id": prospect_id,
                "reason": skip_reason,
                "detail": detail,
            },
        )
    except Exception as exc:  # noqa: BLE001
        # Table may not exist yet — best-effort, never block a tick
        err = str(exc)
        if "does not exist" not in err and "UndefinedTable" not in err:
            logger.warning("scheduler.skip_log.write_failed", error=err[:200])


async def upsert_daily_sent(
    db: AsyncSession,
    *,
    campaign_id: str,
    sent_date: date,
    increment: int = 1,
) -> None:
    """Upsert SchedulerDailySent row for (campaignId, sentDate). Best-effort."""
    try:
        await db.execute(
            text(
                'INSERT INTO "SchedulerDailySent" '
                '(id, "campaignId", "sentDate", "sentCount", "createdAt", "updatedAt") '
                "VALUES (:id, :campaign_id, :sent_date, :cnt, now(), now()) "
                'ON CONFLICT ("campaignId", "sentDate") DO UPDATE '
                'SET "sentCount" = "SchedulerDailySent"."sentCount" + :cnt, '
                '"updatedAt" = now()'
            ),
            {
                "id": _generate_cuid(),
                "campaign_id": campaign_id,
                "sent_date": sent_date,
                "cnt": increment,
            },
        )
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        if "does not exist" not in err and "UndefinedTable" not in err:
            logger.warning("scheduler.daily_sent.upsert_failed", error=err[:200])


__all__ = [
    "get_campaign_schedules",
    "get_skipped_details",
    "get_daily_sent",
    "write_skip_log",
    "upsert_daily_sent",
]
