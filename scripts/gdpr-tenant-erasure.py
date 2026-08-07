#!/usr/bin/env python3
"""
gdpr-tenant-erasure.py — CLI to fully erase a tenant (right-to-erasure at
tenant level — used for tenant offboarding).

Usage:
    python scripts/gdpr-tenant-erasure.py --tenant-slug acme --confirm

What this script does (in order):
  1. Anonymises ALL prospects in the tenant schema (PII → "[anonymized]",
     deleted_at=now, anonymized=true).
  2. Hard-deletes all consent_logs + consents for the tenant.
  3. Hard-deletes all support_messages + support_tickets.
  4. Hard-deletes all sequences, deals, reply_drafts, meeting_preps,
     meetings, call_logs, job_change_alerts, competitors, campaigns.
  5. Drops the tenant schema (DROP SCHEMA tenant_{slug} CASCADE).
  6. Soft-deletes the tenant row in public.tenants (deleted_at=now,
     status='PROVISIONING').
  7. Logs a single platform_audit_log entry recording the erasure
     (actor=script, action='TENANT_ERASE', target_type='tenant',
     target_id=slug).

This is DESTRUCTIVE and IRREVERSIBLE. The --confirm flag is required.
Backups (RDS PITR, 35 days) are the only rollback — and only for 35
days.

Used for:
  - Tenant offboarding (customer cancels + requests full data deletion).
  - Tenant right-to-erasure at the controller level (customer is the
    controller for their tenant's prospect data and requests erasure of
    ALL prospect data on exit).
  - Compliance audits (regulator requests deletion of a specific
    tenant's data).

Exit codes:
  0  erasure succeeded
  1  erasure failed (DB error, tenant not found)
  2  usage error (missing required args, --confirm not set)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the backend app to the import path.
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "outrena-backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


def _validate_slug(slug: str) -> str:
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid tenant slug '{slug}' — must be 3-63 chars, "
            "lowercase alphanumeric + hyphens."
        )
    return slug


def _schema_name_for(slug: str) -> str:
    """Derive the tenant schema name: hyphens become underscores."""
    return f"tenant_{slug.replace('-', '_')}"


async def run_erasure(tenant_slug: str) -> dict:
    """Run the full tenant erasure. Returns a summary dict."""
    from app.core.database import AsyncSessionLocal, engine

    schema = _schema_name_for(tenant_slug)
    summary: dict = {"tenant_slug": tenant_slug, "schema": schema, "steps": []}

    # Step 0 — verify the tenant exists.
    async with AsyncSessionLocal() as session:
        await session.execute(text('SET search_path TO "public"'))
        row = (
            await session.execute(
                text(
                    "SELECT tenant_id, slug, schema_name, status "
                    "FROM public.tenants WHERE slug = :slug AND deleted_at IS NULL"
                ),
                {"slug": tenant_slug},
            )
        ).fetchone()
        if row is None:
            raise ValueError(f"Tenant '{tenant_slug}' not found or already deleted.")
        summary["tenant_id"] = row.tenant_id

    # Steps 1-4 — tenant-schema data wipe + anonymise.
    async with AsyncSessionLocal() as session:
        await session.execute(text(f'SET search_path TO "{schema}", public'))

        # 1. Anonymise all prospects (retain row for FK integrity until step 5
        # CASCADE drops everything).
        result = await session.execute(
            text(
                'UPDATE "Prospect" SET '
                '  "firstName" = \'[anonymized]\', '
                '  "lastName" = \'[anonymized]\', '
                '  "email" = \'[anonymized]\', '
                '  "linkedinUrl" = NULL, '
                '  "notes" = NULL, '
                '  "deleted_at" = now(), '
                '  "anonymized" = true, '
                '  "consent_status" = \'withdrawn\' '
                'WHERE COALESCE("anonymized", false) = false'
            )
        )
        summary["steps"].append(
            {"step": "1_anonymise_prospects", "rows_affected": result.rowcount or 0}
        )

        # 2. Delete consent_logs + consents.
        for tbl in ("consent_logs", "consents"):
            result = await session.execute(text(f"DELETE FROM {tbl}"))
            summary["steps"].append(
                {"step": f"2_delete_{tbl}", "rows_affected": result.rowcount or 0}
            )

        # 3. Delete support_messages + support_tickets.
        for tbl in ("support_messages", "support_tickets"):
            result = await session.execute(text(f"DELETE FROM {tbl}"))
            summary["steps"].append(
                {"step": f"3_delete_{tbl}", "rows_affected": result.rowcount or 0}
            )

        # 4. Delete remaining tenant data (FK order matters — children first).
        for tbl in (
            "FlowWebhookDelivery", "FlowWebhook", "FlowAbTest", "FlowRunStep",
            "FlowRun", "AutopilotQueue", "RateLimitLog", "RateLimit",
            "ProspectingFlow",
            "AbTestAssignment", "EmailAbTest", "AbTest",
            "ReplyDraft", "SubjectLine", "Sequence",
            "CampaignCollateralLink", "CampaignProspect", "CampaignResult",
            "CampaignMetric", "Campaign",
            "Deal", "MeetingPrep", "Meeting", "CallLog", "JobChangeAlert",
            "Competitor", "Collateral",
            "LinkedInInboxMessage", "LinkedInEngagement", "LinkedInConfig",
            "OptimizationAction", "OptimizationRule", "ContentIdea",
            "WeeklyDigest", "EmailTemplate", "ProspectSource", "SourceConfig",
            "SignalMonitor", "Signal", "DomainEnrichment", "SchedulerStatus",
            "MailBridgeConfig", "Domain",
            "PromptTemplate", "SystemParameter", "ProspectingIntegration",
            "ExclusionRule", "LlmConfig",
            "IcpProfile",
            "Prospect",  # last — children reference it
        ):
            try:
                result = await session.execute(text(f'DELETE FROM "{tbl}"'))
                summary["steps"].append(
                    {"step": f"4_delete_{tbl}", "rows_affected": result.rowcount or 0}
                )
            except Exception as exc:  # noqa: BLE001 — table may not exist in this tenant
                summary["steps"].append(
                    {"step": f"4_delete_{tbl}", "skipped": True, "reason": str(exc)}
                )

        await session.commit()

    # Step 5 — DROP SCHEMA CASCADE (autocommit — DDL).
    async with engine.connect() as conn:
        autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await autocommit.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    summary["steps"].append({"step": "5_drop_schema", "schema": schema})

    # Step 6 — soft-delete the tenant row.
    async with AsyncSessionLocal() as session:
        await session.execute(text('SET search_path TO "public"'))
        await session.execute(
            text(
                "UPDATE public.tenants "
                "SET status = 'PROVISIONING', deleted_at = now() "
                "WHERE slug = :slug"
            ),
            {"slug": tenant_slug},
        )
        # Step 7 — log to platform_audit_log.
        await session.execute(
            text(
                "INSERT INTO public.platform_audit_log "
                "(actor_sub, actor_email, actor_role, tenant_slug, action, "
                " target, target_id, metadata, request_id, ip_address) "
                "VALUES (:sub, :email, :role, :slug, :action, "
                "        :target, :target_id, CAST(:meta AS jsonb), :req_id, :ip)"
            ),
            {
                "sub": "script:gdpr-tenant-erasure",
                "email": None,
                "role": "SUPER_ADMIN",
                "slug": tenant_slug,
                "action": "TENANT_ERASE",
                "target": f"tenant:{tenant_slug}",
                "target_id": tenant_slug,
                "meta": '{"script": "gdpr-tenant-erasure.py", '
                '"timestamp": "' + datetime.now(timezone.utc).isoformat() + '"}',
                "req_id": None,
                "ip": None,
            },
        )
        await session.commit()
    summary["steps"].append({"step": "6_soft_delete_tenant_row"})
    summary["steps"].append({"step": "7_audit_log_entry"})

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "FULLY ERASE a tenant (anonymise PII, drop schema, soft-delete "
            "tenant row). DESTRUCTIVE — requires --confirm."
        )
    )
    parser.add_argument(
        "--tenant-slug",
        required=True,
        help="The tenant slug to erase (e.g. 'acme').",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required flag — without it the script is a dry-run.",
    )
    args = parser.parse_args()

    try:
        slug = _validate_slug(args.tenant_slug)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not args.confirm:
        print(
            f"DRY RUN — tenant '{slug}' would be fully erased.\n"
            f"  Schema: {_schema_name_for(slug)}\n"
            f"  Steps:\n"
            f"    1. Anonymise all prospects (PII → [anonymized])\n"
            f"    2. Delete consent_logs + consents\n"
            f"    3. Delete support_messages + support_tickets\n"
            f"    4. Delete sequences, deals, reply_drafts, meeting_preps, "
            f"meetings, call_logs, job_change_alerts, competitors, campaigns, ...\n"
            f"    5. DROP SCHEMA {_schema_name_for(slug)} CASCADE\n"
            f"    6. Soft-delete tenant row (status=PROVISIONING, deleted_at=now)\n"
            f"    7. Log to platform_audit_log (action=TENANT_ERASE)\n"
            f"\n"
            f"To actually run the erasure, re-run with --confirm.",
            file=sys.stderr,
        )
        return 0

    print(f"ERASING tenant '{slug}' (schema {_schema_name_for(slug)})...")
    try:
        summary = asyncio.run(run_erasure(slug))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: erasure failed: {exc}", file=sys.stderr)
        return 1

    print("\nErasure summary:")
    print(f"  Tenant: {summary['tenant_slug']} (id={summary['tenant_id']})")
    print(f"  Schema: {summary['schema']}")
    for step in summary["steps"]:
        if "rows_affected" in step:
            print(f"  Step {step['step']}: {step['rows_affected']} row(s)")
        elif "skipped" in step:
            print(f"  Step {step['step']}: SKIPPED — {step.get('reason', '?')}")
        else:
            print(f"  Step {step['step']}: OK")
    return 0


if __name__ == "__main__":
    # Ensure DATABASE_URL is set.
    if not os.environ.get("DATABASE_URL"):
        print(
            "ERROR: DATABASE_URL env var is not set.\n"
            "Example: DATABASE_URL='postgresql+asyncpg://user:pass@localhost:5432/outrena' "
            f"python {sys.argv[0]} ...",
            file=sys.stderr,
        )
        sys.exit(2)
    sys.exit(main())
