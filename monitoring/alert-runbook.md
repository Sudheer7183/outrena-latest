# OUTRENA Phase 6 — Alert Runbook

This runbook lists every alert configured across the three monitoring stacks
(AWS CloudWatch, Azure Monitor, Grafana). Each alert has the same shape:

> **Name** | **Severity** (Sev1 = page on-call / Sev2 = email only)
> **Trigger**: exact condition + window
> **Impact**: what user-visible behavior this produces
> **Triage**: first 5-min steps to isolate cause
> **Escalation**: who to page / what to do if triage fails

Alerts are tagged with their source stack (`[CW]` CloudWatch, `[AZ]` Azure
Monitor, `[GR]` Grafana) and the migration-doc risk they mitigate (e.g.
`§14 Risk #15`).

References:
- Migration doc §15.1 — testing / observability acceptance criteria
- Migration doc §14   — risks register
- Terraform: `terraform/aws/monitoring.tf` + `terraform/azure/monitoring.tf` +
  `terraform/azure/log_alerts.tf`
- This repo: `azure/alert-rules.json` (Azure standalone ARM), CloudWatch
  dashboards under `aws/cloudwatch-dashboards/`

---

## 1. `backend-5xx-high`

| Field | Value |
|-------|-------|
| **Source** | `[AZ]` `appgw-failed-requests` (mirrors monitoring.tf). `[CW]` equivalent: CloudWatch ALB 5xx alarm. |
| **Severity** | Sev2 (sustained spike > Sev1) |
| **Trigger** | App Gateway `FailedRequests > 100` per 1 min, OR backend ERROR logs > 10 in 5 min (log_alerts.tf `backend_errors`). |
| **Impact** | Users see HTTP 500s on `/api/v1/*` endpoints. Autopilot runs may fail mid-execution. Frontend shows "Something went wrong" toasts. |
| **Triage** | 1. Open Grafana `OUTRENA Overview` dashboard → "Error Rate" panel. Confirm error rate > 1%. 2. Open Loki: `{service="outrena-backend"} |= "ERROR" \| json` — identify the top error class. 3. Check Tempo for slow/error traces around the alert time. 4. Check the most recent deployment — if a Container App revision rollout is in flight (per §16.3), the new revision may be the cause; consider rolling back via Terraform `blue_green_weight_new = 0`. |
| **Escalation** | If error rate sustained > 5% for 15 min: page backend on-call. If traced to a specific endpoint regression: file P1 ticket against the owning team. |

---

## 2. `rds-cpu-high`

| Field | Value |
|-------|-------|
| **Source** | `[AZ]` `rds-cpu-high` (Azure metric alert, postgres `cpu_percent > 80%` for 5 min). `[CW]` `AWS/RDS CPUUtilization > 80%` alarm. |
| **Severity** | Sev1 |
| **Trigger** | Postgres CPU > 80% sustained 5 min. |
| **Impact** | API latency degradation. Long-running queries may time out. Celery worker DB operations back up. Autopilot runs stall. |
| **Triage** | 1. Connect to the PG instance: `psql -h <pgfqdn> -U outrena_admin -d outrena`. 2. Run `SELECT * FROM pg_stat_activity WHERE state = 'active' ORDER BY query_start;` — identify long-running queries. 3. Check `pg_stat_statements` for the top queries by total_exec_time. 4. Look for missing indexes (slow query log). 5. Verify connection pool sizing — the backend uses asyncpg with pool_size=10; if `active_connections` is at the PG max_connections, the pool is leaking. |
| **Escalation** | If CPU > 95% for 10 min: page DBA on-call. Consider vertical scaling (SKU bump) per the runbook in §13.2. |

---

## 3. `rds-storage-low`

| Field | Value |
|-------|-------|
| **Source** | `[AZ]` `rds-storage-low` (`storage_percent > 80%` for 5 min, Sev1). `[CW]` `FreeStorageSpace` alarm. |
| **Severity** | Sev1 |
| **Trigger** | Postgres storage utilization > 80% (i.e., < 20% free). |
| **Impact** | If storage hits 100%, Postgres enters read-only mode → all writes fail → cascading backend errors. Mitigates §14 Risk #14 (PG disk-fill). |
| **Triage** | 1. Check the `OUTRENA Cost` dashboard → "RDS Storage Growth Rate" panel. Is growth linear or sudden? 2. Run `SELECT pg_database_size('outrena') / 1024 / 1024 / 1024 AS gb;` to confirm. 3. Identify the largest tables: `SELECT schemaname, relname, pg_total_relation_size(relid) / 1024 / 1024 AS mb FROM pg_catalog.pg_statio_user_tables ORDER BY mb DESC LIMIT 10;` 4. If a tenant schema is bloated, run `VACUUM (VERBOSE, ANALYZE) <tenant_schema>.<table>;`. 5. If growth is organic, increase `storage_mb` in Terraform (prod.tfvars) — online operation on Flexible Server. |
| **Escalation** | If storage > 90%: page DBA immediately. Storage expansion is online but takes ~10 min; do not wait until 100%. |

---

## 4. `redis-evictions-high`

| Field | Value |
|-------|-------|
| **Source** | `[AZ]` `redis-evictions-high` (`percentProcessorTime > 90%` for 5 min). `[CW]` `AWS/ElastiCache CPUUtilization > 90%` + `Evictions` spike alarm. |
| **Severity** | Sev2 |
| **Trigger** | Redis server load > 90% sustained 5 min, OR eviction rate > 1000/min. |
| **Impact** | Cache misses spike → backend p99 latency rises (DB fallback). Session lookups slow. Rate-limit counters may be evicted → users see unexpected 429s. |
| **Triage** | 1. CloudWatch/LA: `CacheHits` vs `CacheMisses` ratio — confirm miss rate spike. 2. `redis-cli INFO memory` — is `used_memory` close to `maxmemory`? 3. Identify hot keys: `redis-cli --hotkeys` (requires LFU maxmemory policy). 4. Check the `OUTRENA Tenant Isolation` dashboard — a single tenant with abnormal cache miss rate suggests a cache-key prefixing bug. 5. If organic load growth, scale the Redis SKU (Standard C1 → C2). |
| **Escalation** | If evictions > 10k/min sustained: page backend on-call to investigate cache-key namespace collision. |

---

## 5. `ecs-cpu-high`

| Field | Value |
|-------|-------|
| **Source** | `[AZ]` `backend-cpu-high` (`CpuUsage > 80%` for 5 min). `[CW]` ECS `CPUUtilization` alarm. |
| **Severity** | Sev2 |
| **Trigger** | Backend Container App CPU > 80% sustained 5 min (auto-scale threshold is 70%; alert triggers when scaling fails to keep up). |
| **Impact** | Request queue builds. p99 latency rises. In severe cases, ALB health checks fail and the target is deregistered. |
| **Triage** | 1. Grafana `OUTRENA Overview` → "ECS Task Count" panel. Did auto-scale add tasks? (should grow to max_replicas). 2. If at max_replicas and still high, vertical scaling needed. 3. Check for a hot loop — query Tempo for spans > 5s and look for unexpected work (e.g., N+1 queries). 4. Check for background CPU burn: a Celery worker running on the backend task (misconfiguration) — `top` inside the container. |
| **Escalation** | If CPU > 95% for 10 min after auto-scale maxed out: page backend on-call + bump `max_replicas` via Terraform. |

---

## 6. `keycloak-down`

| Field | Value |
|-------|-------|
| **Source** | `[AZ]` `appgw-unhealthy-hosts` (Keycloak backend pool). `[CW]` ALB unhealthy host alarm. Bonus log alert `keycloak-auth-failures` detects brute-force. |
| **Severity** | Sev1 |
| **Trigger** | App Gateway reports > 0 unhealthy hosts in the Keycloak backend pool for 5 min, OR Keycloak container reports `LOGIN_ERROR > 20` in 5 min (brute-force). |
| **Impact** | New login attempts fail. JWT refresh fails → existing sessions break when tokens expire (default 5 min access, 30 min refresh). All `/api/v1/*` calls eventually return 401. |
| **Triage** | 1. App Gateway → Backend health → confirm Keycloak pool is unhealthy. 2. Check Keycloak container logs: `{service="keycloak"}` in Loki. Look for `OutOfMemoryError` or DB connection failures. 3. Verify Postgres is reachable from the Keycloak subnet (NSG rule `apps→data:5432` applies; Keycloak lives on `idp` subnet, so the rule is `idp→data:5432`). 4. Verify `KC_DB_URL` env var points at the correct PG FQDN. 5. Restart the Keycloak revision via Azure Portal or `az containerapp revision restart`. |
| **Escalation** | Keycloak is a hard dependency for ALL API auth — page platform on-call immediately. If restart doesn't restore health within 5 min, failover to the legacy auth provider (per §16.3 rollback runbook) while root-causing. |

---

## 7. `mailbridge-send-failed`

| Field | Value |
|-------|-------|
| **Source** | `[AZ]` `mailbridge-send-failed` (log_alerts.tf — `ContainerAppConsoleLogs where LogEntry has "mailbridge.send_failed"` > 10 in 5 min). `[CW]` metric filter equivalent. |
| **Severity** | Sev1 |
| **Trigger** | More than 10 MailBridge send failures in 5 min. Mitigates §14 Risk #15 (MailBridge deliverability). |
| **Impact** | Sequence sends fail silently from the user's perspective — the sequence appears "sent" but no email arrives. Autopilot runs marked PARTIAL. Reply-rate KPI degrades. |
| **Triage** | 1. Loki: `{service="outrena-worker"} |= "mailbridge.send_failed" \| json` — extract `error_code` field. Common codes: `RATE_LIMITED`, `SUPPRESSED`, `BOUNCE`, `PROVIDER_DOWN`. 2. If `RATE_LIMITED`: check the MailBridge provider's quota dashboard. May need to raise provider sending limit. 3. If `PROVIDER_DOWN`: check the MailBridge status page. Fall back to a secondary provider if configured (`MAILBRIDGE_FALLBACK_URL`). 4. If `BOUNCE`: a tenant's contact list has stale emails. Not a system issue — close the alert as informational. 5. If `SUPPRESSED`: a recipient previously bounced/unsubscribed. Verify the suppression list is being respected (not an alert-level issue). |
| **Escalation** | If > 100 failures in 5 min: page MailBridge on-call. If provider is down for > 15 min: pause autopilot queue (`POST /autopilot/dry-run` with `{pause: true}` — needs scheduler support) to avoid burning retries. |

---

## 8. `scheduler-tick-slow`

| Field | Value |
|-------|-------|
| **Source** | `[AZ]` `scheduler-tick-slow` (log query — `tick_duration_ms > 120000` sustained). `[CW]` `OUTRENA/Scheduler tick.duration p99 > 120000` alarm. |
| **Severity** | Sev2 |
| **Trigger** | Scheduler tick duration > 120s sustained, where tick interval is `SCHEDULER_TICK_SECONDS=300` (5 min). Mitigates §14 Risk #4 (scheduler partial-cap). |
| **Impact** | Autopilot queue backs up (visible in `OUTRENA Scheduler` dashboard "Autopilot Queue Depth" panel). Sequences may be sent late. In severe cases, ticks are skipped (re-entrancy guard kicks in — `tick.skipped` metric). |
| **Triage** | 1. Grafana `OUTRENA Overview` → "Scheduler Tick Duration" panel. Identify which tick phase is slow. 2. Check PARTIAL cap hits panel — if `run.partial_cap_hit > 0`, the scheduler is hitting `SCHEDULER_PARTIAL_CAP` (5 dev/stg, 10 prod). Bump the cap or scale workers. 3. Look at LLM call latency panel — slow LLM calls are the most common cause (LLM p99 > 30s → tick overrun). 4. Check MailBridge send latency — slow email sends block the tick. 5. If a single tenant is monopolizing the tick, the autopilot queue processor picks items FIFO; consider a per-tenant fair-share scheduler (future work). |
| **Escalation** | If ticks skipped > 3 consecutive: page scheduler on-call. Long-running autopilot runs may need manual cancellation via `DELETE /api/autopilot/queue/<itemId>`. |

---

## 9. `tenant-isolation-violation`

| Field | Value |
|-------|-------|
| **Source** | `[AZ]` `tenant-isolation-violation` (log query — `AppRequests where ResultCode == "403"` > 50 in 5 min). Grafana `OUTRENA Tenant Isolation` dashboard shows the live 403 tail. |
| **Severity** | Sev1 |
| **Trigger** | > 50 HTTP 403 responses in 5 min (legitimate 403s should be near-zero; this is the canary for tenant-isolation regression). Mitigates §14 Risk #17 (tenant schema drift). |
| **Impact** | Either (a) legitimate users are being denied access to their own data (isolation middleware false-positive — critical bug), or (b) an attacker is attempting cross-tenant access (security incident). |
| **Triage** | 1. Open Grafana `OUTRENA Tenant Isolation` → "Cross-Tenant Access Attempts" log panel. 2. For each 403, extract `tenant_slug`, `user_id`, `requested_resource`. 3. If all 403s share a single tenant_slug: that tenant likely has a schema-drift issue — query the per-tenant row counts panel; if the tenant's count regressed, the migration in §15.1 has run incorrectly. 4. If 403s come from many tenants with a single user_id: that user is attempting cross-tenant access — security incident. 5. If 403s are from a single IP across many tenants: brute-force — escalate to security. |
| **Escalation** | If the violation is confirmed (legitimate user denied own data): page backend on-call Sev1 + freeze autopilot queue to prevent further state mutation. If security incident: page security on-call + engage IR runbook. |

---

## 10. `jwks-rotation-failed`

| Field | Value |
|-------|-------|
| **Source** | `[AZ]` `jwks-rotation-failed` (log query — `LogEntry has "jwks" and (has "fail" or has "error")`). `[CW]` metric filter equivalent. |
| **Severity** | Sev1 |
| **Trigger** | JWKS rotation failure detected in backend logs. Keycloak rotates signing keys periodically (default every 30 days for RS256); the backend caches the JWKS document and refreshes it on a timer. Mitigates §14 Risk #2 (Keycloak JWKS rotation failure). |
| **Impact** | Existing JWTs validated against the stale JWKS will continue to work until their `kid` is rotated out. New JWTs signed with the new `kid` will fail validation → 401 for users who just logged in. After ~5 min (the access-token TTL), most users are affected. |
| **Triage** | 1. Confirm the alert: Loki `{service="outrena-backend"} |= "jwks" |= "fail"` — identify the specific failure (HTTP 404 from Keycloak, network timeout, parse error). 2. Verify Keycloak is reachable from the backend subnet: `curl -k https://keycloak.internal:8080/auth/realms/outrena/protocol/openid-connect/certs`. 3. If Keycloak is up and serving the new JWKS: force-refresh the backend's JWKS cache by restarting the backend revision (`az containerapp revision restart`). 4. If Keycloak is serving a stale JWKS itself (signing-key rotation failed internally): check Keycloak admin console → Realm Settings → Keys. May need to manually trigger key rotation. |
| **Escalation** | If 401 rate on `/api/v1/*` rises > 1%: page platform on-call. The window between Keycloak key rotation and backend JWKS refresh must be < access-token TTL (5 min); if it exceeds, all new logins fail. |

---

## Alert severity matrix

| Sev | Definition | Response SLA |
|-----|------------|--------------|
| Sev1 | User-visible outage or active security incident. | Page on-call immediately; ack < 5 min; mitigation < 30 min. |
| Sev2 | Degradation with user-visible impact, but system remains operational. | Email/Slack notification; ack < 1 business hour; mitigation < 4 business hours. |

## Cross-stack deduplication

Several alerts fire on the same underlying condition from both Azure Monitor and
CloudWatch (the deployment is multi-cloud during blue/green). The runbook
recommends acknowledging the alert from the active-cloud stack only. The
`[AZ]`/`[CW]` source tag in each alert's name identifies the stack.

For pure-AWS deployments (no Azure), the `[AZ]` alerts do not fire — use the
`[CW]` equivalents. For pure-Azure deployments (no AWS), vice versa. For
blue/green cutover (both clouds live), expect both to fire; acknowledge the
active-cloud alert only and silence the other via the alert rule's `enabled:
false` toggle for the duration of the cutover.

## Reference

- Migration doc §14 — Risks register (each alert maps to one or more risks)
- Migration doc §15.1 — Testing / observability acceptance criteria
- Migration doc §16.3 — Blue/green cutover runbook (drives the cutover dashboard alerts)
- Terraform:
  * `terraform/aws/monitoring.tf` — CloudWatch alarms + dashboard
  * `terraform/azure/monitoring.tf` — Azure metric alerts + action group + diagnostic settings
  * `terraform/azure/log_alerts.tf` — Azure scheduled log-query alerts
- This repo:
  * `aws/cloudwatch-dashboards/*.json` — 4 CloudWatch dashboards
  * `azure/alert-rules.json` — Azure standalone ARM alert template
  * `azure/kql-queries.kql` — KQL query library
  * `grafana/dashboards/*.json` — 3 Grafana dashboards (overview, tenant-isolation, cutover)
