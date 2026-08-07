---
title: MailBridge Integration Runbook (Inbound Reply Webhook)
last_updated: 2025-01-15
severity: SEV-2
owner: OUTRENA SRE
---

# MailBridge Integration Runbook (Inbound Reply Webhook)

Operations for the MailBridge integration: MailBridge receives email replies to
OUTRENA sequences and POSTs them to the backend webhook
`/api/v1/internal/mailbridge/inbound`. This runbook covers failure modes, triage, fix,
and backup retry behavior. Implements Risk #15 mitigation.

## Prerequisites

- On-call engineer has backend + Redis access.
- MailBridge status page URL known: `https://status.mailbridge.com`.
- MailBridge support contact in the SRE wiki (`vendor-contacts.md`).
- `mailbridge-send-failed` alert is firing OR a customer has reported missing replies.

## How MailBridge Works

```text
[ Recipient replies to sequence email ]
            |
            v
   [ MailBridge inbound MX ]
            |
            v
   [ MailBridge normalizes + signs payload with HMAC-SHA256 ]
            |
            v
   [ POST https://api.outrena.com/api/v1/internal/mailbridge/inbound ]
            |
            v
   [ Backend verifies signature, looks up tenant + sequence, writes reply to DB ]
            |
            v
   [ Backend 200 OK → MailBridge marks delivered ]
   [ Backend 5xx  → MailBridge retries with exponential backoff (max 24 hr) ]
   [ Backend 4xx  → MailBridge drops (permanent failure) ]
```

Key points:
- **MailBridge is the source of truth for delivery.** If MailBridge loses an email
  before POSTing, OUTRENA never sees it. MailBridge retains inbound emails for 30 days.
- **HMAC signature** in the `X-MailBridge-Signature` header. Backend rejects any
  request whose signature does not match `HMAC-SHA256(payload, MAILBRIDGE_SIGNING_SECRET)`.
- **Idempotency key** in the `X-MailBridge-Message-Id` header. Backend dedupes on this
  key; retries are safe.
- **Per-tenant retry queue** in Redis: failed webhook deliveries (5xx) are queued and
  retried by the scheduler every 5 min for up to 24 hr.

## Failure Modes

| Mode | Detection | Impact | Severity |
|------|-----------|--------|----------|
| MailBridge down | Status page; `mailbridge.send_failed > 10/5min` alert | New replies lost (MailBridge will retry when up if within their 30-day retention) | SEV-2 |
| Webhook 5xx (backend) | CloudWatch backend 5xx panel; MailBridge retries exhausting | Replies delayed up to 24 hr; then dropped | SEV-2 |
| Webhook timeout (backend slow) | CloudWatch p99 latency for `/internal/mailbridge/inbound` | MailBridge retries; same as 5xx if persistent | SEV-2 |
| Signature mismatch | CloudWatch log filter `mailbridge signature mismatch` | Specific emails dropped (4xx); possible misconfig or compromised secret | SEV-2 (or SEV-1 if widespread) |
| Redis retry queue full | `OUTRENA/MailBridge` metric `retry_queue_depth > 10000` | New failures will be dropped (queue overflow) | SEV-2 |
| Tenant not found | CloudWatch log filter `mailbridge tenant not found` | Email misrouted (MailBridge may have stale routing) | SEV-3 (single email) |

## Triage

### Step 1 — Check MailBridge status

```bash
curl -fsS https://status.mailbridge.com/api/v2/status.json | jq '.status.description'
# Expected: "All Systems Operational"

# If not operational, MailBridge is the cause. Skip to Fix - MailBridge down.
```

### Step 2 — Check backend /health

```bash
curl -fsS https://api.outrena.com/health/ready | jq .
# Expected: 200 + healthy.

# Check the specific webhook endpoint (should return 401 without signature, not 5xx).
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST https://api.outrena.com/api/v1/internal/mailbridge/inbound \
  -H "Content-Type: application/json" -d '{}'
# Expected: 401 (signature required). 5xx → backend is broken; skip to Fix - Backend.
```

### Step 3 — Check webhook logs

```bash
# CloudWatch Logs Insights — last 30 min of MailBridge webhook activity.
fields @timestamp, tenant_slug, mailbridge_message_id, status_code, error
| filter @logStream like /outrena-backend/
| filter http.route = "/api/v1/internal/mailbridge/inbound"
| sort @timestamp desc
| limit 100

# Loki equivalent:
{job="outrena-backend"} |= "mailbridge" |= "inbound" | json
  | line_format "{{.ts}} {{.tenant_slug}} {{.mailbridge_message_id}} {{.status_code}} {{.error}}"
```

Look for patterns:
- All 5xx → backend issue.
- All 401 → signing secret mismatch.
- Mix of 200 + occasional 5xx → transient backend slowness.
- All 404 → tenant not found (MailBridge routing issue).

### Step 4 — Check Redis retry queue

```bash
redis-cli -h <redis-endpoint> LLEN mailbridge:retry-queue
# Expected: <1000. >10000 = backlog; >50000 = critical (will overflow).

# Peek at the head of the queue.
redis-cli -h <redis-endpoint> LRANGE mailbridge:retry-queue 0 4
# Each entry is a JSON payload with tenant_slug, mailbridge_message_id, payload.
```

## Fix

### MailBridge down

1. Confirm via status page + MailBridge support (page if SEV-2 alert is firing).
2. **No OUTRENA action required.** MailBridge retains inbound emails for 30 days and
   will deliver them when service is restored. The retry queue on the OUTRENA side
   will not be touched (it is for OUTRENA-backend failures, not MailBridge failures).
3. Notify customer success if the outage exceeds 1 hr (customer may notice delayed
   replies).
4. Once MailBridge is back, monitor the webhook endpoint for a backlog spike (MailBridge
   will deliver retained emails over ~30 min).

### Backend 5xx (webhook handler broken)

```bash
# 1. Check recent deploys (the most common cause).
gh run list --workflow=cd-prod-aws.yml --limit 3
gh run list --workflow=cd-prod-azure.yml --limit 3

# 2. If a deploy landed in the last 30 min, roll back.
gh workflow run rollback.yml \
  -f target_sha=$(git rev-parse HEAD~1) \
  -f environment=prod \
  -f clouds=aws,azure \
  -f rollback_type=code_only

# 3. If no recent deploy, restart backend tasks.
aws ecs update-service --cluster outrena-prod --service outrena-backend \
  --force-new-deployment

# 4. Verify.
curl -fsS https://api.outrena.com/health/ready | jq .
# Watch the 5xx panel — should drop within 5 min.

# 5. The Redis retry queue will drain automatically as the backend comes back.
```

### Webhook timeout (backend slow)

```bash
# 1. Identify the slow query (likely a tenant lookup or DB write).
# CloudWatch Logs Insights:
fields @timestamp, duration_ms, query
| filter @logStream like /outrena-backend/
| filter http.route = "/api/v1/internal/mailbridge/inbound"
| filter duration_ms > 5000
| sort @timestamp desc
| limit 20

# 2. If RDS is the bottleneck (CPU >85%), see 05-incident-response.md (b).
# 3. If Redis is the bottleneck (evictions), see 05-incident-response.md (c).
# 4. If the backend is just slow (CPU >85%), scale up — see 07-scaling.md.

# 5. Increase the MailBridge webhook timeout (last resort).
# Contact MailBridge support to bump the timeout from 10s to 30s.
```

### Signature mismatch

> **⚠️ Warning:** A sudden spike in signature mismatches could indicate a compromised
> signing secret. Treat as a security incident until proven otherwise.

```bash
# 1. Confirm the signing secret is current.
aws secretsmanager describe-secret --secret-id /outrena/prod/mailbridge-signing-secret \
  --query 'RotatedDate'
# Compare to MailBridge's last rotation date (in the vendor portal).

# 2. If MailBridge rotated and OUTRENA didn't update, rotate the secret now.
# See 09-secrets-management.md — MailBridge webhook URL + signing secret.

# 3. If MailBridge hasn't rotated, the secret may be compromised.
# Page security lead. Rotate immediately.
```

### Redis retry queue full

```bash
# 1. Check queue depth + rate of growth.
redis-cli -h <redis-endpoint> LLEN mailbridge:retry-queue
# Wait 60 s, re-check. If growing, the backend is not draining.

# 2. If the backend is healthy but the queue is still growing, the scheduler retry
# task may be stuck. Check the scheduler:
aws cloudwatch get-metric-statistics --namespace OUTRENA/Scheduler \
  --metric-name tick.duration --start-time $(date -u -d '15 min ago' +%FT%TZ) \
  --end-time $(date -u +%FT%TZ) --period 60 --statistics Average

# 3. Manually trigger the retry task.
python scripts/celery_manual_tick.py --task process_mailbridge_retry_queue

# 4. If the queue is at capacity (>50000) and overflowing, the oldest entries are
# being dropped. Increase the queue max (config: MAILBRIDGE_RETRY_QUEUE_MAX=100000)
# and scale Redis — see 07-scaling.md.
```

### Tenant not found

MailBridge is routing an email to a tenant that does not exist in OUTRENA (likely a
deleted tenant whose MailBridge routing was not cleaned up).

```bash
# 1. Identify the tenant from the log.
# CloudWatch Logs Insights:
fields @timestamp, mailbridge_message_id, tenant_slug, from_email
| filter @logStream like /outrena-backend/
| filter http.route = "/api/v1/internal/mailbridge/inbound"
| filter error = "tenant not found"
| limit 20

# 2. Confirm the tenant does not exist.
psql -c "SELECT slug, status, deleted_at FROM public.tenants WHERE slug = '<slug>';"

# 3. Contact MailBridge support to remove the stale routing rule.
# 4. Document in the incident channel; no further OUTRENA action needed.
```

## Backup — Per-Tenant Retry Queue

The Redis retry queue is the backup mechanism. When a webhook delivery fails (5xx),
the backend writes the payload to `mailbridge:retry-queue` (Redis list). The scheduler
ticks `process_mailbridge_retry_queue` every 5 min, which:

1. Pops up to 1000 entries from the queue.
2. Re-POSTs each to the webhook internally (bypassing MailBridge).
3. On success, removes from the queue.
4. On failure, increments `retry_count`. If `retry_count > 288` (24 hr / 5 min), moves
   to a dead-letter list `mailbridge:dead-letter` and alerts.

```bash
# Check dead-letter queue.
redis-cli -h <redis-endpoint> LLEN mailbridge:dead-letter

# Peek at dead-letter entries (these need manual review).
redis-cli -h <redis-endpoint> LRANGE mailbridge:dead-letter 0 4

# Re-queue a dead-letter entry after fixing the underlying issue.
redis-cli -h <redis-endpoint> RPOPLPUSH mailbridge:dead-letter mailbridge:retry-queue
```

## Verification

After any fix:

```bash
# 1. Webhook endpoint returns 200 for a test payload.
PAYLOAD='{"message_id":"test-001","tenant_slug":"acme-corp","from":"test@acme-corp.com","subject":"Re: Test","body":"test"}'
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$MAILBRIDGE_SIGNING_SECRET" | awk '{print $2}')
curl -fsS -X POST https://api.outrena.com/api/v1/internal/mailbridge/inbound \
  -H "Content-Type: application/json" \
  -H "X-MailBridge-Signature: $SIG" \
  -H "X-MailBridge-Message-Id: test-001" \
  -d "$PAYLOAD" | jq .
# Expected: {"status":"accepted","message_id":"test-001"}

# 2. Retry queue is draining.
redis-cli -h <redis-endpoint> LLEN mailbridge:retry-queue
# Should be decreasing over time.

# 3. MailBridge dashboard shows successful deliveries.
# (MailBridge vendor portal → Delivery Logs → filter last 15 min.)

# 4. No new entries in dead-letter queue.
redis-cli -h <redis-endpoint> LLEN mailbridge:dead-letter
# Should be stable.

# 5. Grafana outrena-overview — `mailbridge.send_failed` metric back to 0.
```

## Rollback

- **Backend rollback (5xx fix):** see `03-rollback.md` Level A.
- **Secret rotation rollback:** see `09-secrets-management.md` Rollback section.
- **Redis scale-up rollback:** see `07-scaling.md` Rollback section.
- **Dead-letter re-queue:** if a re-queued entry causes new failures, move it back:
  ```bash
  redis-cli -h <redis-endpoint> RPOPLPUSH mailbridge:retry-queue mailbridge:dead-letter
  ```

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| MailBridge outage >1 hr | MailBridge support + customer success | Customer-comms trigger |
| MailBridge outage >4 hr | SRE lead + product eng lead + customer success | SEV-2 |
| Widespread signature mismatch | Security lead + MailBridge support | SEV-2 (or SEV-1 if compromised secret) |
| Retry queue overflow (>50000) | SRE lead — scale Redis immediately | SEV-2 |
| Dead-letter queue growing >100/day | SRE lead — underlying backend issue not fixed | Within 1 business day |
| Tenant not found for a paid tenant | Customer success + SRE lead (likely bad routing) | Same business day |
| Customer reports missing replies | On-call — investigate end-to-end | Within 1 hr |

## Related

- `05-incident-response.md` — broader incident response (MailBridge alerts route here).
- `09-secrets-management.md` — MailBridge signing secret rotation.
- `07-scaling.md` — Redis scaling if retry queue is the bottleneck.
- `monitoring/alert-runbook.md` — `mailbridge-send-failed` alert triage.
- Migration doc §14 Risk #15 (MailBridge reliability).
