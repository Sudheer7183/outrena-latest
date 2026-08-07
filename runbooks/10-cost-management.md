---
title: Cost Management + FinOps Runbook
last_updated: 2025-01-15
severity: SEV-3
owner: OUTRENA SRE
---

# Cost Management + FinOps Runbook

Budgets, cost allocation, top cost drivers, per-tenant attribution, and the monthly
cost review process for OUTRENA prod. Implements the FinOps practice referenced in
migration doc §14 Risk #22.

## Prerequisites

- Operator has AWS Budgets + Azure Cost Management read access.
- For tagging changes: Terraform prod apply permission.
- Monthly cost review is on the SRE calendar (1st Monday of each month).

## Budgets

### AWS Budgets

Three budgets configured in `terraform/aws/budgets.tf`:

| Budget | Threshold alerts | Action |
|--------|------------------|--------|
| `outrena-prod-monthly` | 50%, 80%, 100% | Email SRE list + Slack `#ops` at 50%; SRE lead at 80%; page on-call at 100% |
| `outrena-prod-llm` | 80%, 100% | Email SRE + product eng (LLM is a separate budget — Risk #22) |
| `outrena-prod-ec2-ecs` | 80%, 100% | Email SRE (compute budget) |

```bash
aws budgets describe-budgets --account-id 123456789012 \
  --query 'Budgets[*].{name:BudgetName,limit:BudgetLimit,actual:CalculatedSpend}' \
  --output table
```

### Azure Cost Alerts

Configured in `terraform/azure/cost_alerts.tf`:

| Alert | Threshold | Action |
|-------|-----------|--------|
| `outrena-prod-monthly` | 50/80/100% | Same as AWS |
| `outrena-prod-llm` | 80/100% | Same as AWS |

```bash
az consumption usage list --top 5 --query "[].{name:instanceName, cost:pretaxCost, service:meterDetails.meterCategory}" -o table
```

## Cost Allocation Tags

Required tags on every resource:

| Tag | Example | Purpose |
|-----|---------|---------|
| `Project` | `OUTRENA` | Filter all OUTRENA resources from the AWS account |
| `Environment` | `prod` / `staging` / `dev` | Cost split by env |
| `Tenant` | `acme-corp` / `shared` | Per-tenant attribution (shared for infra) |
| `Stack` | `blue` / `green` | Cutover-phase attribution |
| `Owner` | `sre@outrena.com` | Accountability |

Tags are enforced via Terraform (`default_tags` in the AWS provider block) and via
AWS Config rules (`required-tags` rule). Resources without tags are flagged weekly.

```bash
# Find untagged resources.
aws resourcegroupstaggingapi get-resources --tag-filters \
  Key=Project,Values=OUTRENA --query 'ResourceTagMappingList[?!Tags[?Key==`Tenant`]]' \
  --output table
```

## Top Cost Drivers

| Driver | Typical % of bill | Optimization Levers | Runbook Reference |
|--------|-------------------|---------------------|-------------------|
| RDS Postgres | 25-30% | Right-size instance class; Aurora Serverless for dev; storage lifecycle | `07-scaling.md` |
| ECS Fargate (backend + worker) | 20-25% | Spot for workers; scale-to-zero dev at night; right-size CPU/memory | `07-scaling.md` |
| LLM API calls (Anthropic/OpenAI) | 15-25% | Per-tenant rate limits; cache completions; smaller models for routine tasks | `10-cost-management.md` (below) |
| ElastiCache Redis | 10-15% | cache.t3 in dev; r6g in prod; right-size based on eviction rate | `07-scaling.md` |
| NAT Gateway | 5-10% | Single NAT in staging; none in dev; VPC endpoints for S3/ECR/DynamoDB | `07-scaling.md` |
| S3 (CSV + collateral + backups) | 5-10% | Lifecycle rules to Glacier/Deep Archive; delete old backups | `07-scaling.md` |
| CloudWatch Logs | 3-8% | Adjust retention (30d prod, 7d staging, 3d dev); drop DEBUG logs in prod | this runbook |
| ALB / App Gateway | 2-5% | Right-size; consolidation | — |

### LLM cost optimization

The LLM API is the single largest variable cost. Levers:

1. **Per-tenant rate limits** — `LLM_RATE_LIMIT_PER_TENANT=100 calls/hr` (configurable
   per plan). Enforced in the LLM gateway.
2. **Cache completions** — idempotent prompts (e.g. "summarize this thread") cached in
   Redis for 24 hr. Cache key = hash(prompt + model + temperature). Saves ~30% in
   practice.
3. **Model tiering** — routine tasks (subject-line generation, tag suggestion) use
   Haiku; complex tasks (sequence drafting) use Sonnet. Configurable per task type.
4. **Token budget per sequence** — `LLM_MAX_TOKENS_PER_SEQUENCE=4000`. Sequences that
   exceed the budget are truncated + flagged.
5. **Per-tenant cost dashboard** — CloudWatch `outrena-cost` dashboard has an LLM
   cost-per-tenant panel (top-N). Review weekly.

### CloudWatch Logs cost

```bash
# Find the noisiest log groups.
aws logs describe-log-groups --query 'logGroups[*].{name:logGroupName,size:storedBytes,retention:retentionInDays}' \
  --output table

# Adjust retention (default 30d prod).
aws logs put-retention-policy --log-group-name /outrena/backend --retention-in-days 30
aws logs put-retention-policy --log-group-name /outrena/staging/backend --retention-in-days 7
aws logs put-retention-policy --log-group-name /outrena/dev/backend --retention-in-days 3

# Drop DEBUG in prod (metric filter already does this; verify).
aws logs describe-metric-filters --log-group-name /outrena/backend \
  --query 'metricFilters[?metricName==`DropDebug`]'
```

## FinOps — Per-Tenant Cost Attribution

Per-tenant cost is the foundation of OUTRENA's per-tenant pricing. Method:

1. **Directly-attributable resources** (S3 prefix `tenants/<slug>/`, per-tenant
   Keycloak clients, per-tenant LLM API keys) — exact cost known.
2. **Shared resources** (RDS, ECS, Redis, ALB) — allocated proportionally:
   - RDS: by storage used per tenant schema (`pg_database_size(tenant_<slug>)`).
   - ECS backend: by request count per tenant (from CloudWatch `OUTRENA/Backend`
     metric, dimension `tenant_slug`).
   - ECS worker: by autopilot runs per tenant (`OUTRENA/Autopilot` metric).
   - Redis: by cache hits per tenant (`OUTRENA/Cache` metric, dimension `tenant_slug`).
   - ALB: by request count per tenant.

### Tagging ECS tasks with tenant_slug

For per-tenant attribution of ECS tasks, set `tenant_slug` as an env var on the task.
CloudWatch Container Insights picks it up as a dimension:

```hcl
# terraform/aws/ecs.tf
container_definitions = jsonencode([
  {
    name = "outrena-backend"
    # ...
    environment = [
      { name = "TENANT_SLUG", value = var.tenant_slug }   # "shared" for backend pool
    ]
  }
])
```

The OTel collector's `attributes/inject_environment` processor promotes `tenant_slug`
from env to a metric attribute, so all backend metrics carry the tenant dimension.

### Per-tenant cost report

Generated weekly by a Lambda (`lambda/per_tenant_cost_report.py`):

```bash
# Manual run.
aws lambda invoke --function-name outrena-per-tenant-cost-report \
  --payload '{"week":"2025-W02"}' /tmp/report.json
cat /tmp/report.json | jq .

# Output:
# {
#   "acme-corp": {"rds": 12.34, "ecs": 45.67, "redis": 8.90, "llm": 100.00, "s3": 2.50, "total": 169.41},
#   ...
# }
```

Report lands in `s3://outrena-backups/finops/per-tenant/<week>.json` and is posted to
Slack `#finops` weekly.

## Monthly Cost Review Checklist

Run on the 1st Monday of each month. Owner: SRE lead. Attendees: SRE lead, product eng
lead, finance partner.

```text
[ ] Pull AWS Cost Explorer last 30 days, group by Service, sort by cost desc
[ ] Pull Azure Cost Management last 30 days, group by Service
[ ] Compare to previous month: any line item >20% increase? Investigate.
[ ] Compare to budget: are we on track for the month?
[ ] Review per-tenant cost report: any tenant >2x their average? Investigate (possible
    runaway LLM usage).
[ ] Review untagged resources list; tag or terminate.
[ ] Review idle resources (AWS Compute Optimizer / Azure Advisor):
    [ ] RDS instances with <40% CPU for 14 days → right-size
    [ ] ECS services with avg desired >2x running for 14 days → right-size
    [ ] ElastiCache clusters with <30% memory for 14 days → right-size
    [ ] EBS volumes unattached for 7 days → snapshot + delete
[ ] Review LLM cost trend: is it scaling with paid customer count? (Should be linear.)
[ ] Review storage lifecycle: any bucket without lifecycle rules? Add.
[ ] Review NAT Gateway: any NAT with <10 GB/month traffic? Replace with VPC endpoint.
[ ] Action items filed as GitHub Issues labeled `finops`. Owners assigned.
[ ] Update `migration/finops/<YYYY-MM>.md` with this month's findings.
```

## Verification

After any cost optimization change:

```bash
# 1. Service is still healthy (the change didn't break anything).
aws ecs describe-services --cluster outrena-prod --services outrena-backend \
  --query 'services[0].{desired:desiredCount,running:runningCount}'

# 2. Grafana outrena-overview — no error-rate or latency spike.

# 3. Wait one billing cycle (3-7 days) and re-check Cost Explorer.
aws ce get-cost-and-usage --time-period Start=2025-01-15,End=2025-01-22 \
  --granularity DAILY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[*].Groups[*].{key:Keys[0],cost:Metrics.BlendedCost.Amount}' \
  --output table
```

## Rollback

Cost optimizations are Terraform changes — rollback is `terraform apply` with the
previous variable values. Special cases:

- **RDS instance class downgrade** — requires a maintenance-window reboot. See
  `07-scaling.md`.
- **S3 lifecycle rule change** — does not roll back already-transitioned objects.
- **CloudWatch log retention reduction** — already-deleted logs cannot be recovered.
  Increase retention forward, not backward.
- **Tag removal** — costs already attributed to a tag remain attributed. Future costs
  will not be.

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| 100% budget alert fires | SRE lead + finance partner | Same business day |
| LLM cost >2x prior month | SRE lead + product eng lead (possible abuse or bug) | Same business day |
| Per-tenant cost report shows tenant >10x average | Customer success + product eng (likely a runaway loop) | Same business day |
| Untagged resource count >50 | SRE lead — tagging drift | Weekly review |
| AWS / Azure bill unexpectedly >120% of forecast | SRE lead + finance + VP Engineering | SEV-2, immediately |

## Related

- `07-scaling.md` — detailed scaling procedures (the main cost lever).
- `monitoring/aws/cloudwatch-dashboards/outrena-cost.json` — cost dashboard.
- `monitoring/azure/workbook-overview.json` — includes cost panels.
- Migration doc §14 Risk #22 (cost overrun).
