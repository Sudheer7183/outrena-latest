---
title: Rollback Runbook
last_updated: 2025-01-15
severity: SEV-1
owner: OUTRENA SRE
---

# Rollback Runbook

Three levels of rollback for the OUTRENA platform, plus a decision tree for picking the
right one. Implements migration doc §16.

## Prerequisites

- Operator has prod deploy permission (GitHub Actions environment `prod`).
- Current deploy SHA + previous deploy SHA known (check `cd-prod-{aws,azure}.yml`
  workflow run history, or `git log --oneline -20` on `main`).
- On-call lead has been notified (Rollback is SEV-1 by default until verified).
- Slack `#incident-<date>` channel open.
- For DB rollback: pre-deploy RDS snapshot confirmed available (within last 24 hr).

## When to Rollback

Rollback is the right answer when:

- A deploy introduced a regression AND the fix is not known within 30 min.
- A migration took a tenant or the public schema to a broken state.
- The blue/green cutover abort criteria are met (see `04-blue-green-cutover.md`).

Rollback is **not** the right answer when:

- The issue is a config change that can be hot-fixed in place (just edit the config).
- The issue is bad data that requires a forward migration to repair (rollback would
  re-corrupt).
- The "issue" is actually expected behavior; verify with product owner first.

## Decision Tree

```
Is the issue customer-visible?
├─ No → SEV-3, fix forward. Do not roll back.
└─ Yes → Was the last deploy < 30 min ago?
    ├─ No → Is the issue caused by a deploy (vs. data/traffic)?
    │   ├─ Data/traffic → Do not roll back code. See 05-incident-response.md.
    │   └─ Deploy → Did the deploy include a migration?
    │       ├─ Yes → Level B (DB rollback) first, then Level A (code rollback).
    │       └─ No  → Level A (code rollback only).
    └─ Yes → Did the deploy include a migration?
        ├─ Yes → Level B + Level A together.
        └─ No  → Level A (code rollback) — fastest path.
```

If Level A does not resolve the issue → Level C (full blue/green DNS flip).

## Level A — Code Rollback

Redeploy the previous image tag. Fastest; ~5 min end-to-end.

### Via GitHub Actions (preferred)

Trigger the `rollback.yml` workflow with the previous SHA:

```bash
# From the repo root.
gh workflow run rollback.yml \
  -f target_sha=$(git rev-parse HEAD~1) \
  -f environment=prod \
  -f clouds=aws,azure \
  -f rollback_type=code_only
```

This workflow:
1. Pulls the previously-pushed image for that SHA from ECR + ACR.
2. Updates the ECS task definition + Azure Container App revision to reference it.
3. Triggers a rolling deploy with 50% minimum healthy.
4. Posts to `#on-call-incidents` via `SLACK_INCIDENT_WEBHOOK_URL`.

Monitor the workflow run:
```bash
gh run watch $(gh run list --workflow=rollback.yml --limit 1 --json databaseId -q '.[0].databaseId')
```

### Via the cd-prod workflows manually

If `rollback.yml` is unavailable, re-run the deploy workflow with the old SHA:

```bash
gh workflow run cd-prod-aws.yml \
  -f ref=$(git rev-parse HEAD~1) \
  -f environment=prod
gh workflow run cd-prod-azure.yml \
  -f ref=$(git rev-parse HEAD~1) \
  -f environment=prod
```

### Verification (Level A)

```bash
# 1. New tasks are running the old image.
aws ecs describe-tasks --cluster outrena-prod \
  --tasks $(aws ecs list-tasks --cluster outrena-prod --family outrena-backend --query 'taskArns[0]' --output text) \
  --query 'tasks[0].containers[0].image' --output text
# Expected: ...:outrena-backend:<old-sha>

# 2. /health/ready returns the old SHA (the app exposes it).
curl -sS https://api.outrena.com/health/ready | jq '.version'
# Expected: <old-sha>

# 3. Error rate drops back to baseline in Grafana outrena-overview (within 5 min).
```

## Level B — Database Rollback

Per-tenant `alembic downgrade`. Use only when a migration is the root cause.

### Procedure

```bash
export DATABASE_URL="postgresql://outrena_app:***@prod-rds.outrena.internal/outrena"

# Identify the affected tenant(s). If all tenants, iterate all.
psql -c "SELECT slug FROM public.tenants WHERE status='active';"

# Per-tenant downgrade (-1 = one revision back).
export TARGET_SCHEMA="tenant_acme_corp"
cd /srv/outrena
alembic downgrade -1
alembic current   # confirm
python scripts/verify_schema_health.py --schema tenant_acme_corp

# Public schema if affected.
export TARGET_SCHEMA=public
alembic downgrade -1
```

> **⚠️ Warning: Destructive migrations cannot be downgraded.** A migration that drops a
> column or changes a column type has destroyed the original data — `downgrade()` will
> raise or silently produce an empty column. For destructive migrations, do **not**
> attempt `alembic downgrade`. Instead:
>
> 1. Restore the affected tenant from the pre-deploy RDS snapshot
>    (see `08-disaster-recovery.md`).
> 2. Author a forward-only fix migration.
> 3. Apply the fix migration.
>
> See migration doc §16 "Rollback Plan" — destructive migrations are explicitly
> forward-only by policy.

### Verification (Level B)

```bash
# All tenants healthy.
python scripts/verify_schema_health.py --all-tenants

# No tenant-isolation alerts firing.
aws cloudwatch describe-alarms --state-value ALARM \
  --alarm-name-prefix outrena-tenant-isolation --query 'MetricAlarms[*].AlarmName'
# Expected: [] (empty list)
```

## Level C — Full Stack Rollback (Blue/Green DNS Flip)

The nuclear option. Flips Route 53 / Azure DNS weighted routing back to the previous
("blue") Next.js stack, retained for 14 days post-cutover per §16.3.

### When to use Level C

- Level A and B both failed or are insufficient.
- The issue is in the Next.js frontend and a code rollback didn't catch it.
- Cutover abort criteria are met (see `04-blue-green-cutover.md`).

### Procedure (AWS)

```bash
scripts/cutover/aws-route53-rollback.sh
# Flips the weighted routing: blue (old stack) 100%, green (new stack) 0%.
# Takes ~60s for Route 53 propagation + ALB health checks.
```

### Procedure (Azure)

```bash
scripts/cutover/azure-route53-rollback.sh
# Same flip on the Azure side (App Gateway backend pool + DNS).
```

> **⚠️ Warning:** Level C does **not** roll back the database. If a migration has been
> applied since cutover, Level B is required **in addition** to Level C. The 14-day
> blue stack retention covers only frontend + backend code, not schema.

### Verification (Level C)

```bash
# 1. DNS resolves to the blue ALB.
dig +short api.outrena.com
# Expected: blue stack ALB DNS.

# 2. /health/ready shows the pre-cutover version.
curl -sS https://api.outrena.com/health/ready | jq '.version, .stack'
# Expected: pre-cutover SHA, "blue".

# 3. Grafana outrena-cutover dashboard: "new-stack traffic share" gauge reads 0%.
```

## GitHub Actions — rollback.yml

The `rollback.yml` workflow is the canonical entry point. Inputs:

| Input | Required | Example | Notes |
|-------|----------|---------|-------|
| `target_sha` | yes | `a1b2c3d` | The git SHA to roll back to. |
| `environment` | yes | `prod` | `prod` only in Phase 6. |
| `clouds` | yes | `aws,azure` | Comma-separated. |
| `rollback_type` | yes | `code_only` / `code_and_db` / `full_stack` | Selects level. |
| `tenant_slug` | no | `acme-corp` | Required for `code_and_db` if single-tenant. |

Example invocation for full-stack rollback:

```bash
gh workflow run rollback.yml \
  -f target_sha=$(git rev-parse HEAD~1) \
  -f environment=prod \
  -f clouds=aws,azure \
  -f rollback_type=full_stack
```

The workflow:
1. Validates `target_sha` exists in ECR + ACR.
2. For `code_only` / `code_and_db` / `full_stack`: deploys the old image (Level A).
3. For `code_and_db`: runs `alembic downgrade -1` per tenant (Level B).
4. For `full_stack`: invokes `scripts/cutover/{aws,azure}-route53-rollback.sh` (Level C).
5. Posts the result to `#on-call-incidents` via `SLACK_INCIDENT_WEBHOOK_URL` and to
   `#deploys` via `SLACK_WEBHOOK_URL`.

## RTO / RPO Targets

| Level | RTO | RPO | Notes |
|-------|-----|-----|-------|
| A (code) | 10 min | 0 (no data loss) | Image already in ECR/ACR; rolling deploy. |
| B (db) | 30 min | 0 for non-destructive; up to 24 hr for destructive (snapshot age) | Per-tenant downgrade ~2 min each. |
| C (full stack) | 15 min | 0 (DNS flip only) | Route 53 propagation dominates. |

Overall target: **RTO 1 hr, RPO 5 min** (PITR on RDS).

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| `rollback.yml` workflow fails | SRE lead (manual fallback via cd-prod) | Immediately |
| Level B downgrade raises on a tenant | DBA + SRE lead — switch to snapshot restore | Immediately |
| Level C DNS flip fails | SRE lead + page AWS/Azure support | SEV-1, immediately |
| After rollback, issue persists | SRE lead + product eng lead — issue may not be deploy-related | Within 15 min of rollback |
| Rollback triggered customer-visible data loss | SRE lead + legal + customer success | SEV-1, immediately; this is a reportable incident |

## Related

- `04-blue-green-cutover.md` — cutover abort criteria + per-day rollback steps.
- `08-disaster-recovery.md` — RDS snapshot restore for destructive-migration recovery.
- `02-schema-migration.md` — authoring + testing migrations to minimize Level B needs.
- Migration doc §16 (rollback plan), §16.3 (blue/green sequence).
