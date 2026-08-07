---
title: Incident Response Runbook (SEV-1/2/3)
last_updated: 2025-01-15
severity: SEV-1
owner: OUTRENA SRE
---

# Incident Response Runbook (SEV-1/2/3)

How to respond to a production incident. This runbook covers the first 15 minutes,
investigation patterns, common incident types with quick fixes, and post-incident
process. Severity classification is in `00-README.md`.

## Prerequisites

- You are the on-call engineer (primary or secondary) and have been paged.
- You have PagerDuty, Slack, and GitHub access.
- You have prod console access (AWS + Azure) and bastion / SSM access to RDS.

## First 15 Minutes

### 1. Acknowledge in PagerDuty (within 5 min for SEV-1)

```text
- Open PagerDuty app or web.
- Find the triggered incident.
- Click "Acknowledge".
- Add a note: "Investigating. <your name>."
```

If you cannot ack within 5 min, the secondary on-call is auto-paged. If secondary also
misses, the SRE lead is paged.

### 2. Open an incident channel

```bash
# In Slack, run the /incident slash command:
/incident open
# Bot creates #incident-<YYYYMMDD>, invites @on-call, @sre-lead, @product-eng-lead.
# Sets channel topic to the incident title (auto-detected from PagerDuty).
```

If `/incident` bot is unavailable, manually create `#incident-<YYYYMMDD>` and invite
the on-call team.

### 3. Post the initial message

Use this template verbatim — fill in the brackets:

```text
:rotating_light: INCIDENT — <SEV-LEVEL> — <one-line description>

Severity: SEV-<1|2|3>
Started: <HH:MM UTC> (estimated)
Detected by: <alert name / customer report / on-call noticed>
Affected: <all customers / single tenant / single subsystem>
Impact: <what is broken, in customer terms>

Incident Commander: @<your handle>
Responder(s): @<your handle>
SRE Lead: <paged? Y/N>

Current status: INVESTIGATING

Next update: <HH:MM UTC> (or "in 15 min").
```

### 4. Page additional responders (SEV-1 only)

For SEV-1, page the SRE lead immediately (do not wait for the escalation timer):

```bash
pd-escalate --policy OUTRENA-SRE-Lead --incident <incident-id>
```

If the incident is database-related, also page the DBA (rotation `OUTRENA-DBA`).
If it is Keycloak-related, page the identity lead (`OUTRENA-Identity`).

### 5. Start investigating

Do **not** try to fix anything yet — first understand the blast radius. Open the
**outrena-overview** Grafana dashboard and answer:

- Is this all tenants or one tenant? (Filter by tenant.)
- Is this AWS-only, Azure-only, or both? (Determines if it is cloud-provider-level.)
- When did it start? (Correlate with deploys / migrations.)
- Is it request-rate-related (5xx spiking) or resource-related (CPU/disk)?

## Investigation

### Check Grafana overview dashboard

URL: <https://grafana.outrena.internal/d/outrena-overview>

Look at:
- ALB / App Gateway 5xx ratio.
- Backend ECS / Container Apps CPU + Memory.
- RDS CPU + connections + free storage.
- Redis CPU + memory + evictions.
- Scheduler tick duration.
- Backend p99 latency.

Note any panel that is red or out of baseline.

### Check CloudWatch + Azure alarms

```bash
# AWS — list all ALARM state alarms.
aws cloudwatch describe-alarms --state-value ALARM \
  --query 'MetricAlarms[*].AlarmName' --output text

# Azure — list all fired alerts.
az monitor alerts list --resource-group outrena-prod-rg \
  --query "[?properties.state=='Fired'].properties" --output table
```

### Check recent deployments

```bash
# GitHub Actions runs in the last 24 hr.
gh run list --workflow=cd-prod-aws.yml --limit 5
gh run list --workflow=cd-prod-azure.yml --limit 5
gh run list --workflow=db-migrate.yml --limit 5   # if it exists
gh run list --workflow=rollback.yml --limit 5

# Or via API for a specific window.
gh api /repos/outrena/platform/actions/runs?created=>=$(date -u -d '24 hours ago' +%FT%TZ) \
  --jq '.workflow_runs[] | {name, conclusion, created_at, head_sha}'
```

If a deploy or migration completed within 30 min of the incident start, that is the
prime suspect.

### Check recent migrations

```bash
# Alembic head per schema.
psql -c "SELECT slug FROM public.tenants WHERE status='active';"
# For each tenant:
TARGET_SCHEMA=tenant_<slug> alembic current
TARGET_SCHEMA=public alembic current

# Or run the schema health check:
python scripts/verify_schema_health.py --all-tenants
```

### Check logs

```text
# Loki / Grafana Explore — datasource Loki
{job="outrena-backend"} |= "ERROR" | json | level="error" | line_format "{{.ts}} {{.tenant_slug}} {{.msg}}"

# CloudWatch Logs Insights
fields @timestamp, @message
| filter @logStream like /outrena-backend/
| filter level = "error"
| sort @timestamp desc
| limit 100
```

## Common Incident Patterns + Quick Fixes

### (a) Backend 5xx spike

**Triage:** check Grafana outrena-overview → 5xx panel. Compare to deploy timestamps.

**If a deploy completed in the last 30 min:**

```bash
# Roll back via rollback.yml (Level A).
gh workflow run rollback.yml \
  -f target_sha=$(git rev-parse HEAD~1) \
  -f environment=prod \
  -f clouds=aws,azure \
  -f rollback_type=code_only
```

See `03-rollback.md` for the full procedure.

**If no recent deploy:** investigate the error log. Common causes:
- LLM provider (Anthropic/OpenAI) outage → check `https://status.anthropic.com`.
- RDS connection exhaustion → see (b).
- Redis OOM → see (c).

### (b) RDS high CPU / connection exhaustion

**Triage:** Grafana outrena-overview → RDS panel. CPU >85% sustained, or connections
near the max (e.g. 90% of `max_connections`).

```bash
# Find slow queries via Performance Insights.
aws pi describe-dimension-keys --service-type RDS \
  --identifier <db-instance-id> \
  --start-time $(date -u -d '30 min ago' +%FT%TZ) \
  --end-time $(date -u +%FT%TZ) \
  --metric db.load.avg --group-by Dimension=dim_query

# Find currently-running queries.
psql -c "
SELECT pid, now() - xact_start AS duration, query, state
FROM pg_stat_activity
WHERE state != 'idle' AND now() - xact_start > interval '30 seconds'
ORDER BY duration DESC;"

# Kill a long-running query (SEV-2 only, with care).
psql -c "SELECT pg_terminate_backend(<pid>);"
```

If the load is from a single runaway query → kill it + file a bug for query planner
issue. If it is steady load from a tenant doing a large export → contact the tenant,
offer to throttle.

### (c) Redis evictions / OOM

**Triage:** Grafana outrena-overview → Redis panel. Evictions >0 sustained, memory
usage >90%.

```bash
# Check Redis info.
redis-cli -h <redis-endpoint> INFO memory | grep used_memory_human
redis-cli -h <redis-endpoint> INFO stats | grep evicted_keys

# Identify large keys.
redis-cli -h <redis-endpoint> --bigkeys
```

**Fix:** scale up the ElastiCache / Azure Redis node type. See `07-scaling.md` — note
this requires a node replacement (brief outage). If scaling is not immediately
possible, evict cold keys manually:

```bash
redis-cli -h <redis-endpoint> --scan --pattern 'cache:sequences:*' | head -1000 | \
  xargs -L 100 redis-cli -h <redis-endpoint> DEL
```

### (d) Keycloak down / auth failures

**Triage:** Grafana outrena-overview → login-failure rate. Check
`https://auth.outrena.com/health`.

```bash
# Check Keycloak ECS / Container App health.
aws ecs describe-services --cluster outrena-prod \
  --services outrena-keycloak --query 'services[0].{desired:desiredCount,running:runningCount,deployments:deployments[*].{status:status,running:runningCount,desired:desiredCount}}'

# Verify JWKS reachable from backend.
curl -fsS https://auth.outrena.com/realms/outrena/protocol/openid-connect/certs | jq '.keys | length'
# Expected: 2+ (current + next). If empty → Keycloak is up but realm keys are missing.

# Restart Keycloak tasks.
aws ecs update-service --cluster outrena-prod --service outrena-keycloak \
  --force-new-deployment
```

If auth failures are spiking but Keycloak is up → likely a JWKS rotation issue. See
`06-keycloak-jwks-rotation.md`.

### (e) Scheduler not ticking

**Triage:** Grafana outrena-overview → scheduler tick panel. `tick.duration` flat at 0,
or `tick.skipped` increasing.

```bash
# Check Celery worker health.
aws ecs describe-services --cluster outrena-prod --services outrena-worker \
  --query 'services[0].{desired:desiredCount,running:runningCount}'

# Check Redis broker.
redis-cli -h <redis-endpoint> LLEN celery
# Expected: <1000. >10000 = backlog, workers are stuck.

# Manual tick to unstick.
python scripts/celery_manual_tick.py --force

# Restart workers if needed.
aws ecs update-service --cluster outrena-prod --service outrena-worker \
  --force-new-deployment
```

### (f) Tenant isolation violation — SEV-1

**Triage:** Grafana outrena-tenant-isolation dashboard. Alert
`outrena-tenant-isolation-violation` fired. Cross-tenant 403 logs spiking, or
schema-per-tenant row counts drifting.

> **⚠️ Warning:** This is a SEV-1 security incident. Treat as data breach until proven
> otherwise. Do NOT attempt to fix forward — roll back immediately.

```bash
# 1. Roll back the most recent deploy + migration immediately.
gh workflow run rollback.yml \
  -f target_sha=$(git rev-parse HEAD~1) \
  -f environment=prod \
  -f clouds=aws,azure \
  -f rollback_type=code_and_db

# 2. Page SRE lead + security lead + product eng lead.
pd-escalate --policy OUTRENA-SRE-Lead --incident <incident-id>
pd-escalate --policy OUTRENA-Security --incident <incident-id>

# 3. Security audit: identify which tenants may have seen each other's data.
psql -c "
SELECT tenant_slug, COUNT(*) AS cross_tenant_403s
FROM audit_log
WHERE event = 'cross_tenant_access_denied'
  AND created_at > now() - interval '24 hours'
GROUP BY tenant_slug
ORDER BY cross_tenant_403s DESC;"

# 4. Customer comms: drafted by customer success, approved by legal.
```

## Post-Incident

### Stabilize + hand off

Once the incident is mitigated (customer impact stopped), update the channel:

```text
:large_green_circle: INCIDENT MITIGATED — <one-line>

Mitigation: <what was done>
Time to mitigate: <duration>
Customer impact: <duration> / <tenants affected>

Next: postmortem within 48 hr. Action items tracked in GitHub Issues
label `incident-<YYYYMMDD>`.

Incident Commander hand-off: @<next-on-call> takes postmortem ownership.
```

### Blameless postmortem (within 48 hr)

Owner: incident commander (or hand-off designate).

Template: `.github/ISSUE_TEMPLATE/postmortem.md`. Required sections:
- Summary (1 paragraph).
- Timeline (UTC).
- Impact (customers, tenants, duration, $ if known).
- Root cause.
- Contributing factors.
- What went well.
- What went badly.
- Action items (GitHub Issues, owners, due dates).
- Appendix (graphs, logs, commands run).

Post the postmortem PR within 48 hr; review meeting within 5 business days. The
postmortem is blameless — focus on systems and process, not individuals.

### Action items

Tracked as GitHub Issues labeled `incident-<YYYYMMDD>`. Each action item has:
- An owner (not "SRE team").
- A due date (default 30 days; SEV-1 fixes within 14 days).
- A link back to the postmortem PR.

The SRE lead reviews open incident action items weekly.

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| SEV-1 not mitigated within 30 min | SRE lead + product eng lead + customer success | Auto-page from PagerDuty escalation |
| SEV-1 still ongoing after 2 hr | VP Engineering | SRE lead pages manually |
| Tenant isolation violation (f) | Security lead + legal | Immediately, before any external comms |
| Customer-data breach suspected | Legal + DPO + CEO | Within 1 hr of suspicion |
| PagerDuty itself is down | SRE lead via phone (number in SRE wiki) | Immediately — fall back to phone tree |

## Related

- `00-README.md` — severity definitions + on-call rotation.
- `03-rollback.md` — rollback procedures (referenced heavily above).
- `06-keycloak-jwks-rotation.md` — auth-failure-spike runbook.
- `08-disaster-recovery.md` — if mitigation requires snapshot restore.
- `11-mailbridge-integration.md` — MailBridge-specific incidents.
- `monitoring/alert-runbook.md` — per-alert triage detail.
- Migration doc §14 (risk register), §16 (rollback plan).
