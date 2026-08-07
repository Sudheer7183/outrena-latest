---
title: Cost Management & Usage Tracking
last_updated: 2025-01-20
severity: SEV-3
owner: OUTRENA SRE + Product Eng
---

# Cost Management & Usage Tracking

This runbook covers the **per-user + per-tenant cost model** added in Phase 8
(SAAS2-OBS-BE). It supersedes the broken `runbooks/10-cost-management.md`
which referenced `terraform/aws/budgets.tf` + `lambda/per_tenant_cost_report.py`
— files that did not exist at the time of the SURVEY-OBS audit. Those files
are now created by this task; the old runbook is preserved for historical
context but operators should use **this** runbook going forward.

## 1. Per-user cost model

OUTRENA bills tenants per **billable event**:

| Event type | Provider examples | Cost source |
|------------|-------------------|-------------|
| `llm_call` | openai, anthropic, google, zai, … | per 1K tokens (input + output separately) |
| `prospect_enrich` | apollo, zoominfo, clearbit, hunter, lusha, snov | per successful lookup |
| `linkedin_action` | linkedin | per API action (connect / message / profile view) |
| `email_send` | smtp | 0 (infra cost — not passed through) |
| `email_reply` | smtp | 0 (replies are received, not sent) |
| `webhook_receive` | (varies) | 0 |
| `api_call` | (varies) | 0 (used for metering only) |

Each event is recorded as a row in `tenant_<slug>.usage_events` with:
- `user_id` — the Keycloak UUID of the user who triggered the event.
- `event_type` + `provider` + `resource` (model name for LLM, NULL otherwise).
- `quantity` + `unit` (tokens for LLM, calls for enrichment, actions for LinkedIn).
- `cost_cents` — the computed cost in **integer cents** (not float dollars).
- `metadata` JSONB — request_id, campaign_id, prospect_id, etc.

The cost is computed at write time by `CostService` (see §2 below) so the
recorded cost is always exact — no reconciliation job needed.

## 2. How costs are computed

`app/services/cost_service.py` resolves the per-unit cost in this order:

1. **`public.cost_config` table** — per-(event_type, provider, model) overrides.
   Managed by SUPER_ADMIN via `PUT /api/v1/usage/cost-table`. Highest priority.
2. **`USAGE_COST_TABLE_JSON` env var** — JSON string with the same shape as
   `DEFAULT_COST_TABLE`. Process-wide override (operator-controlled).
3. **`DEFAULT_COST_TABLE`** — hardcoded defaults in `cost_service.py`,
   sourced from provider pricing pages (Jan 2025). Lowest priority.

LLM cost formula (integer cents):

```
cost_cents = round(
    prompt_tokens     * input_cents_per_1k  / 1000
  + completion_tokens * output_cents_per_1k / 1000
)
```

Emails are free (infra cost is allocated to the tenant via the FinOps
report — see §6 below, not per-send). Enrichment + LinkedIn are flat per-
call rates.

Costs are stored as **integer cents** to avoid float-rounding drift in
aggregations. The API divides by 100 only when displaying to humans.

## 3. Querying usage

### 3.1 API endpoints

All endpoints live under `/api/v1/usage/*` (see `app/api/v1/usage.py`):

| Endpoint | Role | Purpose |
|----------|------|---------|
| `GET /usage/me?period=2025-01` | REP+ | Current user's own usage + cost breakdown |
| `GET /usage/user/{user_id}?period=` | MANAGER+ | Specific user's usage |
| `GET /usage/tenant?period=` | MANAGER+ | Tenant rollup |
| `GET /usage/manager?period=` | MANAGER+ | Per-user breakdown (manager dashboard) |
| `GET /usage/platform?period=` | SUPER_ADMIN | Cross-tenant rollup |
| `GET /usage/cost-table` | SUPER_ADMIN | Current effective cost table |
| `PUT /usage/cost-table` | SUPER_ADMIN | Upsert per-(provider, model) overrides |

`period` accepts `YYYY-MM` (monthly, default = current month) or `YYYY-MM-DD`
(daily). Returns JSON with `total_cost_cents` + a `breakdown` array grouped
by `event_type × provider`.

### 3.2 Direct SQL (ops / debugging)

```bash
# Total cost per tenant for January 2025 (cross-tenant, run as superuser).
psql -d outrena -c "
  SELECT n.nspname AS tenant_schema,
         SUM(cost_cents) AS total_cents
  FROM pg_tables t
  JOIN pg_namespace n ON t.schemaname = n.nspname
  CROSS JOIN LATERAL (
    SELECT SUM(cost_cents) AS cost_cents
    FROM format('%I.usage_events', n.nspname)::regclass
    WHERE occurred_at >= '2025-01-01' AND occurred_at < '2025-02-01'
  ) e
  WHERE t.tablename = 'usage_events' AND n.nspname LIKE 'tenant_%'
  GROUP BY n.nspname
  ORDER BY total_cents DESC;"

# Top 10 users by LLM cost in a single tenant (replace tenant_acme).
psql -d outrena -c "
  SET search_path TO tenant_acme, public;
  SELECT user_id, SUM(cost_cents) AS cents, COUNT(*) AS calls
  FROM usage_events
  WHERE event_type = 'llm_call'
    AND occurred_at >= '2025-01-01' AND occurred_at < '2025-02-01'
  GROUP BY user_id
  ORDER BY cents DESC
  LIMIT 10;"
```

### 3.3 Grafana dashboards

Two dashboards ship with this task (see `monitoring/grafana/dashboards/`):

- **OUTRENA — Cost & Usage** (`cost-usage.json`): per-tenant cost over time,
  cost-by-event-type pie, top-10 users bar, cost-vs-budget graph, today's
  totals as stat panels.
- **OUTRENA — LLM Usage** (`llm-usage.json`): LLM calls per provider,
  tokens per model, LLM cost per tenant, p50/p95/p99 latency per provider.

Both back onto Prometheus metrics (`outrena_llm_calls_total`,
`outrena_llm_cost_cents_total`, `outrena_emails_sent_total`, etc.). The
metrics are emitted by `app/core/metrics.py` + the LLM instrumentation in
`app/services/llm_service.py`.

## 4. Budgets + alerts

### 4.1 AWS Budgets (`terraform/aws/budgets.tf`)

One AWS Budget per active tenant, tagged `Tenant=<slug>`:

| Budget | Threshold alerts | Action |
|--------|------------------|--------|
| `outrena-prod-monthly` | 50%, 80%, 100% | Email SRE list + Slack `#ops` at 50%; SRE lead at 80%; page on-call at 100% |
| `outrena-prod-llm` | 80%, 100% | Email SRE + product eng (LLM is a separate budget — Risk #22) |
| `outrena-prod-ec2-ecs` | 80%, 100% | Email SRE (compute budget) |

Per-tenant budgets use cost tags (`Tenant=<slug>`). Tags are enforced via
Terraform `default_tags` in the AWS provider block (see
`terraform/aws/versions.tf`) and via AWS Config rules.

```bash
aws budgets describe-budgets --account-id 123456789012 \
  --query 'Budgets[*].{name:BudgetName,limit:BudgetLimit,actual:CalculatedSpend}' \
  --output table
```

### 4.2 Azure Cost Alerts (`terraform/azure/cost_alerts.tf`)

Azure Cost Management budget per tenant, also tag-based (`Tenant=<slug>`):

| Alert | Threshold | Action |
|-------|-----------|--------|
| `outrena-prod-monthly` | 50/80/100% | Same as AWS |
| `outrena-prod-llm` | 80/100% | Same as AWS |

```bash
az consumption usage list --top 5 \
  --query "[].{name:instanceName, cost:pretaxCost, service:meterDetails.meterCategory}" \
  -o table
```

### 4.3 Application-level budgets (per-user)

The application does NOT enforce per-user budgets today — that's a Phase 9
feature. To add it, the next agent would:

1. Add a `monthly_budget_cents` column to `public.tenant_config` (or
   `public.plans`).
2. After each `record_event`, compare the running total to the budget.
3. If over budget, block subsequent `llm_call` events (return a 429 from
   `call_llm`).

The current per-user cost data (`usage_events` + `cost_summaries`) is the
foundation for this — no schema change needed for the read path.

## 5. FinOps procedures

### 5.1 Cost allocation tags (required on every resource)

| Tag | Example | Purpose |
|-----|---------|---------|
| `Project` | `OUTRENA` | Filter all OUTRENA resources from the AWS account |
| `Environment` | `prod` / `staging` / `dev` | Cost split by env |
| `Tenant` | `acme-corp` / `shared` | Per-tenant attribution (shared for infra) |
| `Stack` | `blue` / `green` | Cutover-phase attribution |
| `Owner` | `sre@outrena.com` | Accountability |

```bash
# Find untagged resources.
aws resourcegroupstaggingapi get-resources --tag-filters \
  Key=Project,Values=OUTRENA --query 'ResourceTagMappingList[?!Tags[?Key==`Tenant`]]' \
  --output table
```

### 5.2 Top cost drivers

| Driver | Typical % of bill | Optimization Levers | Runbook Reference |
|--------|-------------------|---------------------|-------------------|
| RDS Postgres | 25-30% | Right-size instance class; Aurora Serverless for dev; storage lifecycle | `07-scaling.md` |
| ECS Fargate (backend + worker) | 20-25% | Spot for workers; scale-to-zero dev at night; right-size CPU/memory | `07-scaling.md` |
| LLM API calls | 15-25% | Per-tenant rate limits; cache completions; smaller models for routine tasks | this runbook §6 |
| ElastiCache Redis | 10-15% | cache.t3 in dev; r6g in prod; right-size based on eviction rate | `07-scaling.md` |
| NAT Gateway | 5-10% | Single NAT in staging; none in dev; VPC endpoints for S3/ECR/DynamoDB | `07-scaling.md` |
| S3 (CSV + collateral + backups) | 5-10% | Lifecycle rules to Glacier/Deep Archive; delete old backups | `07-scaling.md` |
| CloudWatch Logs | 3-8% | Adjust retention (30d prod, 7d staging, 3d dev); drop DEBUG logs in prod | `09-secrets-management.md` |
| ALB / App Gateway | 2-5% | Right-size; consolidation | — |

### 5.3 LLM cost optimization (the single largest variable cost)

1. **Per-tenant rate limits** — `LLM_RATE_LIMIT_PER_TENANT=100 calls/hr`
   (configurable per plan). Enforced in the LLM gateway.
2. **Cache completions** — idempotent prompts (e.g. "summarize this thread")
   cached in Redis for 24 hr. Cache key = hash(prompt + model + temperature).
   Saves ~30% in practice.
3. **Model tiering** — routine tasks (subject-line generation, tag
   suggestion) use Haiku / glm-4-flash; complex tasks (sequence drafting)
   use Sonnet / gpt-4o. Configurable per task type.
4. **Token budget per sequence** — `LLM_MAX_TOKENS_PER_SEQUENCE=4000`.
   Sequences that exceed the budget are truncated + flagged.
5. **Per-tenant cost dashboard** — Grafana "OUTRENA — LLM Usage" dashboard
   has a per-tenant cost panel (top-N). Review weekly.

### 5.4 CloudWatch Logs cost

```bash
# Find the noisiest log groups.
aws logs describe-log-groups \
  --query 'logGroups[*].{name:logGroupName,size:storedBytes,retention:retentionInDays}' \
  --output table

# Adjust retention (default 30d prod).
aws logs put-retention-policy --log-group-name /outrena/backend --retention-in-days 30
aws logs put-retention-policy --log-group-name /outrena/staging/backend --retention-in-days 7
aws logs put-retention-policy --log-group-name /outrena/dev/backend --retention-in-days 3
```

## 6. Per-tenant cost attribution

Per-tenant cost is the foundation of OUTRENA's per-tenant pricing. Two
layers:

### 6.1 Directly-attributable (per-event)

LLM, enrichment, and LinkedIn costs are **directly attributable** to the
tenant because each `usage_events` row carries the tenant's schema
(namespace) + the user_id. Summing `cost_cents` per tenant is a single
SQL query (see §3.2).

### 6.2 Shared resources (allocated proportionally)

RDS, ECS, Redis, ALB costs are **shared** across all tenants on the
cluster. Allocation method:

- RDS: by storage used per tenant schema (`pg_database_size(tenant_<slug>)`).
- ECS backend: by request count per tenant (Prometheus
  `outrena_http_requests_total` filtered by `tenant` label).
- ECS worker: by autopilot runs per tenant (from the `autopilot_queue`
  table).
- Redis: by cache hits per tenant (Prometheus, when wired).
- ALB: by request count per tenant.

The weekly FinOps report (see §7) joins these into a single per-tenant
total cost.

## 7. Monthly cost review checklist

Run on the 1st Monday of each month. Owner: SRE lead. Attendees: SRE lead,
product eng lead, finance partner.

```text
[ ] Pull AWS Cost Explorer last 30 days, group by Service, sort by cost desc
[ ] Pull Azure Cost Management last 30 days, group by Service
[ ] Compare to previous month: any line item >20% increase? Investigate.
[ ] Compare to budget: are we on track for the month? (AWS Budgets + Azure alerts)
[ ] Review per-tenant cost report from app DB:
    psql -d outrena -c "<cross-tenant SQL from §3.2>"
    Any tenant >2x their average? Investigate (possible runaway LLM usage).
[ ] Review untagged resources list; tag or terminate.
[ ] Review idle resources (AWS Compute Optimizer / Azure Advisor):
    [ ] RDS instances with <40% CPU for 14 days → right-size
    [ ] ECS services with avg desired >2x running for 14 days → right-size
    [ ] ElastiCache clusters with <30% memory for 14 days → right-size
    [ ] EBS volumes unattached for 7 days → snapshot + delete
[ ] Review LLM cost trend (Grafana OUTRENA — Cost & Usage dashboard):
    is it scaling with paid customer count? (Should be linear.)
[ ] Review storage lifecycle: any bucket without lifecycle rules? Add.
[ ] Review NAT Gateway: any NAT with <10 GB/month traffic? Replace with VPC endpoint.
[ ] Action items filed as GitHub Issues labeled `finops`. Owners assigned.
[ ] Update `migration/finops/<YYYY-MM>.md` with this month's findings.
```

## 8. Verification

After any cost optimization change:

```bash
# 1. Service is still healthy (the change didn't break anything).
aws ecs describe-services --cluster outrena-prod --services outrena-backend \
  --query 'services[0].{desired:desiredCount,running:runningCount}'

# 2. Grafana OUTRENA Backend Overview (Prometheus) — no error-rate or latency spike.

# 3. Wait one billing cycle (3-7 days) and re-check Cost Explorer.
aws ce get-cost-and-usage --time-period Start=2025-01-15,End=2025-01-22 \
  --granularity DAILY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[*].Groups[*].{key:Keys[0],cost:Metrics.BlendedCost.Amount}' \
  --output table

# 4. Per-tenant LLM cost is still accurate (compare app DB to billing).
psql -d outrena -c "<cross-tenant SQL from §3.2>"
```

## 9. Rollback

Cost optimizations are Terraform changes — rollback is `terraform apply`
with the previous variable values. Special cases:

- **RDS instance class downgrade** — requires a maintenance-window reboot.
  See `07-scaling.md`.
- **S3 lifecycle rule change** — does not roll back already-transitioned
  objects.
- **CloudWatch log retention reduction** — already-deleted logs cannot be
  recovered. Increase retention forward, not backward.
- **Tag removal** — costs already attributed to a tag remain attributed.
  Future costs will not be.
- **Cost-table overrides (PUT /api/v1/usage/cost-table)** — re-PUT the
  previous values; old `usage_events` rows keep their original
  `cost_cents` (costs are computed at write time, not re-computed).

## 10. Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| 100% budget alert fires | SRE lead + finance partner | Same business day |
| LLM cost >2x prior month | SRE lead + product eng lead (possible abuse or bug) | Same business day |
| Per-tenant cost report shows tenant >10x average | Customer success + product eng (likely a runaway loop) | Same business day |
| Untagged resource count >50 | SRE lead — tagging drift | Weekly review |
| AWS / Azure bill unexpectedly >120% of forecast | SRE lead + finance + VP Engineering | SEV-2, immediately |
| `usage_events` table grows >10M rows in one tenant | SRE lead + DBA | Weekly review — consider partitioning |

## 11. Related

- `07-scaling.md` — detailed scaling procedures (the main cost lever).
- `monitoring/grafana/dashboards/cost-usage.json` — per-user + per-tenant cost dashboard.
- `monitoring/grafana/dashboards/llm-usage.json` — LLM token + cost dashboard.
- `monitoring/grafana/dashboards/backend-overview.json` — Prometheus-backed overview.
- `monitoring/aws/cloudwatch-dashboards/outrena-cost.json` — CloudWatch cost dashboard (AWS-only).
- `monitoring/azure/workbook-overview.json` — Azure workbook with cost panels.
- `terraform/aws/budgets.tf` — AWS Budgets (per-tenant).
- `terraform/azure/cost_alerts.tf` — Azure Cost Management alerts (per-tenant).
- `outrena-backend/app/services/cost_service.py` — per-provider cost computation.
- `outrena-backend/app/services/usage_service.py` — UsageEvent recording + aggregation.
- `outrena-backend/app/api/v1/usage.py` — usage query endpoints.
- `outrena-backend/alembic/versions/0006_usage_tracking.py` — DB migration.
- Migration doc §14 Risk #22 (cost overrun).
