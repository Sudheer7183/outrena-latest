---
title: OUTRENA Phase 6 Ops Runbooks — Index
last_updated: 2025-01-15
severity: N/A
owner: OUTRENA SRE
---

# OUTRENA Phase 6 Ops Runbooks — Index

This directory contains the operational runbooks for OUTRENA Phase 6 (multi-tenant
platform + blue/green cutover). Each runbook is a self-contained, actionable document
covering a specific operational domain. Runbooks are version-controlled alongside the
platform code in `migration/runbooks/`.

## How to Use These Runbooks

1. **During an incident**, start with `05-incident-response.md` to triage severity and
   assemble the response team. That runbook will reference the domain-specific runbooks
   (e.g. `06-keycloak-jwks-rotation.md`, `08-disaster-recovery.md`).
2. **During a planned operation** (tenant provisioning, schema migration, cutover),
   open the relevant runbook and follow the `## Procedure` section step-by-step. Do
   **not** skip the `## Prerequisites` section.
3. **Every runbook ends with an `## Escalation` section** — if you are blocked or the
   procedure fails in a way the runbook does not anticipate, escalate.
4. **Runbooks are source of truth.** If you discover a step is wrong or missing, file a
   GitHub Issue labeled `runbook-fix` and open a PR. Do not edit the runbook live during
   an incident unless the on-call lead authorizes it.
5. The `last_updated` date in each runbook's frontmatter must be bumped on every edit.
   Stale runbooks (older than 90 days) are flagged in the weekly SRE review.

## Runbook Index

| # | File | Domain | Typical Severity |
|---|------|--------|------------------|
| 00 | `00-README.md` | This index + severity classification + on-call + dashboards | N/A |
| 01 | `01-tenant-provisioning.md` | Provisioning a new tenant (6-step compensating flow) | SEV-3 |
| 02 | `02-schema-migration.md` | Alembic migrations across all tenant schemas | SEV-2 |
| 03 | `03-rollback.md` | Three-level rollback procedures + decision tree | SEV-1/SEV-2 |
| 04 | `04-blue-green-cutover.md` | 7-day weighted cutover (5%→25%→50%→100%) | SEV-1 |
| 05 | `05-incident-response.md` | SEV-1/2/3 incident response + common patterns | SEV-1/2/3 |
| 06 | `06-keycloak-jwks-rotation.md` | Keycloak JWKS key rotation + cache bust | SEV-1 |
| 07 | `07-scaling.md` | Manual + autoscaling (ECS/RDS/ElastiCache + Azure) | SEV-3 |
| 08 | `08-disaster-recovery.md` | Backup/restore + cross-region failover + DR drill | SEV-1 |
| 09 | `09-secrets-management.md` | Secrets rotation inventory + procedures + audit | SEV-2 |
| 10 | `10-cost-management.md` | Budgets + cost drivers + FinOps + per-tenant attribution | SEV-3 |
| 11 | `11-mailbridge-integration.md` | MailBridge inbound webhook operations | SEV-2 |

## Severity Classification

| Severity | Definition | Examples | Ack By | Mitigate By | Comms |
|----------|------------|----------|--------|-------------|-------|
| **SEV-1** | Production outage or data-loss risk. Customer-visible across multiple tenants. | Backend fully down; RDS unreachable; tenant isolation violation; all logins failing. | 5 min | 30 min | Page on-call + SRE lead + post in #incident + customer email within 1h |
| **SEV-2** | Production degraded. Single tenant or single subsystem affected, no data loss. | Single tenant 5xx spike; scheduler stalled; MailBridge retries exhausting; RDS CPU pinned. | 15 min | 4 hr | Slack #incident + customer email if customer-visible >30 min |
| **SEV-3** | Minor or operational. No customer impact, or cosmetic. | Cost alert; staging deploy broken; tenant provisioning for non-production tenant. | 1 business day | 1 business day | Slack #ops only |

### Severity Decision Heuristics

- **If customers cannot log in or send sequences → SEV-1.**
- **If one tenant is broken but others are fine → SEV-2** (unless that tenant is on a
  paid SLA, in which case → SEV-1).
- **If monitoring itself is broken → SEV-2 minimum** (you cannot confidently call
  anything healthy if you cannot observe it).
- **If a destructive migration has been applied → SEV-1** regardless of visible impact;
  data may already be lost.

## On-Call Rotation

- **Primary on-call:** 1 engineer from the OUTRENA SRE rotation, 7-day shifts,
  handoff Mondays 10:00 UTC. Rotation scheduled in PagerDuty schedule
  `OUTRENA-Primary`.
- **Secondary on-call:** 1 engineer for escalation if primary does not ack within 5 min.
  Rotation: `OUTRENA-Secondary`.
- **SRE lead (final escalation):** always contactable via PagerDuty escalation policy
  `OUTRENA-SRE-Lead` after secondary misses.
- **Product eng lead** is paged for SEV-1 incidents lasting >2 hr (auto-escalation).
- On-call schedule and current rotations: <https://outrena.pagerduty.com/schedules>
- On-call calendar export: `webcal://outrena.pagerduty.com/schedules/OUTRENA-Primary.ics>

> **⚠️ Warning:** If you are paged and the issue is **not** in this runbook set, page
> the SRE lead immediately. Improvised actions during a SEV-1 are a leading cause of
> secondary incidents. Document the new failure mode in `05-incident-response.md` once
> stable.

## Where to Find Dashboards

### Grafana (primary operational view)

- Base URL: <https://grafana.outrena.internal>
- SSO via Okta; role `Viewer` is default, `Editor` requires SRE approval.
- Dashboards (folder `OUTRENA`):
  - **outrena-overview** — top-level health (ALB 5xx, ECS CPU/MEM, RDS, Redis, scheduler
    tick, LLM cost). Use for first-look triage.
  - **outrena-tenant-isolation** — cross-tenant 403s, per-tenant cache miss rate,
    schema-per-tenant row counts (feeds Risk #17 alert).
  - **outrena-cutover** — blue/green weighted traffic share, new-stack error rate,
    latency ratio, composite rollback trigger. **The single dashboard to watch during
    cutover** (see `04-blue-green-cutover.md`).
- Datasources: CloudWatch (`uid=cloudwatch`), Loki (`uid=loki`), Azure Monitor
  (`uid=azure-monitor`), Tempo (`uid=tempo`), Prometheus (`uid=prometheus`).

### AWS CloudWatch

- Console path: CloudWatch → Dashboards → prefix `outrena-`
- Dashboards:
  - `outrena-overview` — 9 widgets, period 5 min, default range 1 hr.
  - `outrena-tenant` — variable `${tenant}`, period 5 min, default range 6 hr.
  - `outrena-cost` — period 1 hr, default range 7 d.
  - `outrena-scheduler` — period 1 min, default range 3 hr.
- Logs: CloudWatch Logs Insights, log groups `/outrena/{backend,worker,scheduler,frontend}`,
  `/outrena/keycloak`, `/ecs/outrena-*`.
- Alarms: CloudWatch → Alarms, prefix `outrena-`. All alarms page PagerDuty via SNS
  topic `outrena-alerts` → PD integration `outrena-cw-pd`.

### Azure Monitor

- Console path: Monitor → Workbooks → `outrena-workbook-overview`.
- Log Analytics workspace: `outrena-la-prod`, queryable via KQL
  (see `monitoring/azure/kql-queries.kql`).
- Alerts: Monitor → Alerts → resource group `outrena-prod-rg`, all rules prefixed
  `outrena-`. Action group `outrena-ag` routes to PagerDuty via webhook.

### Loki / Logs

- Grafana → Explore → datasource `Loki`.
- LogQL quick reference:
  - All backend errors 1 hr: `{job="outrena-backend"} |= "ERROR" | json | level="error"`
  - Per-tenant errors: `{job="outrena-backend"} |= "tenant_slug=acme-corp" |= "ERROR"`
  - Cross-tenant 403s: `{job="outrena-backend"} |= "403" |= "cross_tenant"`

### Tempo / Traces

- Grafana → Explore → datasource `Tempo`.
- Trace ID lookup: paste a `trace_id` from a log line directly into the TraceQL bar.
- Service map available under Tempo → Service Map.

## Cross-References

- Migration document sections referenced throughout these runbooks:
  - §4.4 — tenant provisioning compensating flow (runbook 01)
  - §10 — Phase 6 deliverables
  - §14 — risk register (Risk #14 RDS storage, #15 MailBridge, #16 JWKS rotation,
    #17 tenant isolation)
  - §15.1 — testing invariants
  - §16 — rollback plan (runbook 03, 04)
  - §16.3 — blue/green cutover sequence (runbook 04)
- Related operational files in the repo:
  - `migration/monitoring/alert-runbook.md` — alert-specific triage (companion to 05)
  - `migration/terraform/{aws,azure}/` — infrastructure source of truth
  - `migration/.github/workflows/cd-prod-{aws,azure}.yml` — deploy pipelines
  - `migration/.github/workflows/rollback.yml` — rollback workflow
  - `scripts/cutover/` — cutover + rollback shell scripts
  - `scripts/provision_tenant.py`, `scripts/db-migrate-all-tenants.sh`,
    `scripts/export_keycloak_realm.sh`, `scripts/verify_schema_health.py`,
    `scripts/celery_manual_tick.py`

## Change History

| Date | Change | Author |
|------|--------|--------|
| 2025-01-15 | Initial Phase 6 runbook set created (12 files). | OUTRENA SRE |
