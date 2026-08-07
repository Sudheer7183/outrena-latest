---
title: Keycloak JWKS Rotation Runbook
last_updated: 2025-01-15
severity: SEV-1
owner: OUTRENA SRE
---

# Keycloak JWKS Rotation Runbook

Handles Keycloak signing-key rotation events (Risk #16 in the migration doc). Keycloak
rotates realm signing keys quarterly; if the backend's JWKS cache is stale or poisoned
when Keycloak's `kid` changes, **all authenticated requests fail** — a SEV-1.

## Prerequisites

- On-call engineer has backend bastion / SSM access.
- `auth-failure-spike` alert is firing (login failures >10% sustained for 5 min).
- You have read `05-incident-response.md` first-15-minutes section.

## Background

- Keycloak realm `outrena` uses RS256 signing with a 90-day rotation cadence.
- Active keys: 1 active + 1 next (pre-published for smooth rollover).
- Backend validates JWTs by fetching `https://auth.outrena.com/realms/outrena/protocol/openid-connect/certs`
  and matching the JWT `kid` header to a key in the JWKS.
- Backend caches JWKS in Redis under key `jwks:outrena` with `JWKS_CACHE_TTL=3600` (1 hr).
- On `kid` mismatch (JWT header `kid` not in cached JWKS), backend **busts the cache
  and refetches** once. If the refetch fails or the new `kid` is still missing, the
  request fails with 401.
- Keycloak publishes a new `kid` ~7 days before activating it (pre-publish). A
  monitoring job (cron, daily) checks the realm keys endpoint and alerts 30 days
  before the next scheduled rotation.

## Detection

The alert `auth-failure-spike` (configured in `monitoring/azure/alert-rules.json` and
the CloudWatch equivalent) fires when:

```text
login_failures / login_attempts > 0.10  sustained for 5 min
```

Slack channel `#on-call-incidents` receives the alert. PagerDuty pages the primary
on-call.

Secondary signals (Grafana outrena-overview dashboard):
- 401 response rate >10% (panel: backend error rate, status code breakdown).
- Cross-tenant 403 rate unchanged (rules out tenant-isolation issue).
- Keycloak health endpoint green (Keycloak itself is up — this is a JWKS issue, not a
  Keycloak outage).

## Triage

### Step 1 — Verify Keycloak is up

```bash
curl -fsS https://auth.outrena.com/health
# Expected: {"status":"UP"}

curl -fsS https://auth.outrena.com/realms/outrena/.well-known/openid-configuration | \
  jq '.jwks_uri'
# Expected: "https://auth.outrena.com/realms/outrena/protocol/openid-connect/certs"
```

If Keycloak is down → this is not a JWKS issue; follow `05-incident-response.md`
pattern (d).

### Step 2 — Verify the JWKS endpoint is reachable from the backend

```bash
# Via the backend task (SSM Session Manager or ECS Exec).
aws ecs execute-command --cluster outrena-prod \
  --task <task-id> --container outrena-backend \
  --interactive --command "curl -fsS https://auth.outrena.com/realms/outrena/protocol/openid-connect/certs | jq '.keys | map(.kid)'"

# Expected: array of 2+ kids, e.g. ["abc123...", "def456..."]
```

If the curl fails from the backend task but works from your laptop → network / security
group / egress issue. Check the backend task's security group egress rules + DNS
resolution.

If the curl succeeds but returns an empty `keys` array → Keycloak realm has no signing
keys. This is a Keycloak realm config issue, not a JWKS cache issue. Page the identity
lead.

### Step 3 — Compare: JWT kid header vs. cached JWKS kid

```bash
# Get a failing JWT (from a customer report or your own login attempt).
JWT="<header.payload.signature>"
HEADER_KID=$(echo "$JWT" | cut -d. -f1 | base64 -d 2>/dev/null | jq -r '.kid')
echo "JWT kid: $HEADER_KID"

# Get the cached JWKS kid set.
CACHED_KIDS=$(redis-cli -h <redis-endpoint> GET jwks:outrena | jq -r '.keys[].kid' | sort)
echo "Cached kids: $CACHED_KIDS"

# Get the live JWKS kid set.
LIVE_KIDS=$(curl -fsS https://auth.outrena.com/realms/outrena/protocol/openid-connect/certs | jq -r '.keys[].kid' | sort)
echo "Live kids: $LIVE_KIDS"
```

**Diagnosis:**
- `HEADER_KID` not in `LIVE_KIDS` → Keycloak has rotated and the JWT was issued under
  an old key. Wait 60 s for tokens to cycle, or ask the user to re-login.
- `HEADER_KID` in `LIVE_KIDS` but not in `CACHED_KIDS` → **stale cache** (most common).
  Proceed to Fix A.
- `HEADER_KID` in `CACHED_KIDS` but signature still fails → **poisoned cache** (cache
  contains a wrong/corrupt key). Proceed to Fix A.
- `CACHED_KIDS` empty or `GET jwks:outrena` returns nil → cache expired and refetch
  failed. Proceed to Fix A.

### Step 4 — Check the JWKS cache TTL

```bash
redis-cli -h <redis-endpoint> TTL jwks:outrena
# Expected: positive integer < 3600. If -1 (no expiry) or -2 (no key), cache is broken.
```

## Fix

### Fix A — Flush the JWKS cache + restart backend tasks

```bash
# 1. Flush the JWKS cache key.
redis-cli -h <redis-endpoint> DEL jwks:outrena
# Expected: (integer) 1

# 2. Verify it is gone.
redis-cli -h <redis-endpoint> EXISTS jwks:outrena
# Expected: (integer) 0

# 3. Restart backend tasks (forces JWKS refetch on first request).
aws ecs update-service --cluster outrena-prod --service outrena-backend \
  --force-new-deployment

# Azure equivalent.
az containerapp revision restart --name outrena-backend-prod \
  --resource-group outrena-prod-rg --revision latest

# 4. Wait for tasks to stabilize (3-5 min). Watch Grafana outrena-overview.
# 5. Hit /health/ready.
curl -fsS https://api.outrena.com/health/ready | jq .
# 6. Test a real login.
```

### Fix B — If Fix A does not resolve

The backend may have an in-process JWKS cache (Python `jwt` library) that survives
Redis flush. The ECS restart in Fix A should clear it. If you skipped the restart,
do it now:

```bash
aws ecs update-service --cluster outrena-prod --service outrena-backend \
  --force-new-deployment
```

If after the restart auth is still failing, the JWT `kid` does not match the live
JWKS. This means Keycloak has rotated but the JWT was minted under an old key — wait
60 s and retry. If still failing after 5 min, the realm is in a bad state — page the
identity lead.

### Break-glass — Skip JWT verification (SEV-1 only)

> **⚠️ Warning:** This is a last-resort measure. Skipping JWT verification means
> **anyone can call the API as any user**. Use only when ALL logins are failing and
> Fix A+B have not worked within 15 min. **Revert within 1 hour.**

```bash
# Set the env var on the backend service.
aws ecs describe-task-definition --task-definition outrena-backend-prod \
  --query 'taskDefinition' > /tmp/td.json
# Edit /tmp/td.json: add SKIP_JWT_VERIFICATION=true to container env, bump family version.
aws ecs register-task-definition --cli-input-json file:///tmp/td.json
aws ecs update-service --cluster outrena-prod --service outrena-backend \
  --task-family outrena-backend-prod

# Or via terraform:
cd terraform/aws
terraform apply -var skip_jwt_verification=true
```

While `SKIP_JWT_VERIFICATION=true`:
- The API is open. Notify customer success + legal immediately.
- Audit log entries are still recorded (with a `skip_jwt=true` flag).
- The break-glass is logged to CloudTrail / Azure Activity Log.

**Revert:**

```bash
cd terraform/aws
terraform apply -var skip_jwt_verification=false
# Verify.
aws ecs describe-task-definition --task-definition outrena-backend-prod \
  --query 'taskDefinition.containerDefinitions[0].environment[?name==`SKIP_JWT_VERIFICATION`]'
# Expected: empty list (var unset).
```

## Verification

After Fix A or B, verify:

```bash
# 1. Login failure rate back to baseline (<1%).
# (Grafana outrena-overview → backend 401 panel, last 5 min.)

# 2. JWKS cache populated + TTL set.
redis-cli -h <redis-endpoint> TTL jwks:outrena
# Expected: positive integer close to 3600.

# 3. JWT kid header matches a cached kid.
# (Re-run Step 3 from Triage; HEADER_KID should be in CACHED_KIDS.)

# 4. End-to-end login test.
curl -fsS -X POST https://api.outrena.com/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@outrena.com","password":"***"}' | jq '.token | length'
# Expected: non-zero (JWT issued).

# 5. Authenticated API call.
curl -fsS -H "Authorization: Bearer $TOKEN" https://api.outrena.com/v1/me | jq .
# Expected: 200 + user profile.
```

## Rollback

There is no rollback for this runbook per se — the "fix" is to restore JWKS cache to a
correct state. If Fix A made things worse (e.g. backend fails to start after restart),
roll back the backend image:

```bash
gh workflow run rollback.yml \
  -f target_sha=$(git rev-parse HEAD~1) \
  -f environment=prod \
  -f clouds=aws,azure \
  -f rollback_type=code_only
```

See `03-rollback.md` Level A.

If break-glass (`SKIP_JWT_VERIFICATION=true`) was applied, **reverting the env var** is
mandatory; do not roll back code while the flag is set.

## Prevention

- **Daily cron** checks the Keycloak realm keys endpoint and reports the active `kid` +
  the `next` kid to the OUTRENA/Keycloak custom metric namespace. Grafana panel shows
  the rotation timeline.
- **30-day pre-rotation alert**: if `next` kid becomes `active` within 30 days, alert
  `keycloak-rotation-imminent`. On-call manually reviews and pre-flushes the JWKS cache
  the day before rotation.
- **`JWKS_CACHE_TTL=3600`** is intentionally shorter than the Keycloak pre-publish
  window (7 days), so a normal rotation is absorbed by natural cache expiry.
- **Add a synthetic login test** to the E2E suite (`tests/e2e/test_auth.py`) that runs
  every 5 min in prod. On failure, fires the `auth-failure-spike` alert directly.

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| Keycloak is down (not a JWKS issue) | Identity lead + Keycloak vendor (Red Hat) | SEV-1, immediately |
| Realm has no signing keys (empty JWKS) | Identity lead — realm config issue | Immediately |
| Backend cannot reach JWKS endpoint | SRE lead — network/egress issue | Immediately |
| Fix A + B both fail within 15 min | SRE lead + identity lead + product eng lead | Apply break-glass + escalate |
| Break-glass active >1 hr | SRE lead + security lead + legal | SEV-1, immediately — investigate why revert failed |
| Rotation incident recurs within 30 days | SRE lead — prevention cron is broken | Within 1 business day |

## Related

- `05-incident-response.md` — broader incident response (this is a special case).
- `09-secrets-management.md` — Keycloak admin password rotation.
- `monitoring/alert-runbook.md` — `auth-failure-spike` and `jwks-rotation-failed`
  alert triage.
- Migration doc §14 Risk #16 (JWKS rotation), §4.2 (auth design).
