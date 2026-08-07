---
title: Blue/Green Cutover Runbook (7-Day Weighted Migration)
last_updated: 2025-01-15
severity: SEV-1
owner: OUTRENA SRE
---

# Blue/Green Cutover Runbook (7-Day Weighted Migration)

Implements the 7-day cutover sequence defined in migration doc §16.3. Traffic is
shifted from the **blue** (current/old) stack to the **green** (new) stack in four
weighted increments: 5% → 25% → 50% → 100%, with observation windows between each.

## Prerequisites

- Cutover scheduled ≥2 weeks in advance; customer email sent ≥7 days prior.
- E2E suite (`tests/e2e/`) passes on **staging** for **both** AWS and Azure stacks.
- Rollback scripts tested in staging within the last 7 days:
  - `scripts/cutover/aws-route53-rollback.sh`
  - `scripts/cutover/azure-route53-rollback.sh`
  - `scripts/cutover/full-cutover-sequence.sh --abort`
- On-call engineer + SRE lead briefed; both available for the entire cutover window.
- Communication templates drafted (Slack + email), reviewed by customer success.
- Grafana **outrena-cutover** dashboard open on the on-call engineer's second monitor.
- RDS manual snapshot taken within 24 hr (see `08-disaster-recovery.md`).
- Pre-cutover schema health check passes:
  ```bash
  python scripts/verify_schema_health.py --all-tenants
  ```

## Pre-Cutover Checklist

Run this checklist the morning of Day 0. All items must pass before the first shift.

```text
[ ] E2E suite green on AWS staging (latest SHA)
[ ] E2E suite green on Azure staging (latest SHA)
[ ] aws-route53-rollback.sh tested in staging (within 7 days)
[ ] azure-route53-rollback.sh tested in staging (within 7 days)
[ ] full-cutover-sequence.sh --abort tested in staging (within 7 days)
[ ] monitor-cutover.sh deployed + paged on-call in last dry run
[ ] On-call primary + secondary confirmed available for next 7 days
[ ] SRE lead confirmed available for escalations
[ ] Customer email sent (T-7 days) + reminder sent (T-1 day)
[ ] Slack #cutover-2025-01 channel created; stakeholders invited
[ ] Grafana outrena-cutover dashboard confirmed loading + refreshing
[ ] CloudWatch + Azure alerts confirmed in OK state (no pre-existing alarms)
[ ] RDS snapshot taken within 24 hr, snapshot ID recorded: __________
[ ] Backups verified restorable (sample restore in staging within 7 days)
```

## Cutover Driver Script

All shifts use the same driver script with different `%` arguments:

```bash
scripts/cutover/full-cutover-sequence.sh --target <pct> [--abort]
```

- `--target 5|25|50|100` — shifts green-stack weight to the given percentage across
  both Route 53 (AWS) and Azure DNS.
- `--abort` — emergency rollback to 0% green (blue 100%); invokes the route53 rollback
  scripts on both clouds.

The script:
1. Verifies pre-flight health on both green stacks.
2. Updates Route 53 weighted records + Azure traffic-manager profile.
3. Waits for DNS propagation (60 s default).
4. Triggers `monitor-cutover.sh` in monitor mode for the configured observation window.

## Day-by-Day Procedure

### Day 0 — Shift to 5%

**Time budget:** 15 min observation.

```bash
# 1. Confirm pre-cutover checklist is complete.
# 2. Make the shift.
scripts/cutover/full-cutover-sequence.sh --target 5

# 3. Monitor for 15 min.
scripts/cutover/monitor-cutover.sh --window 15m
```

**Watch (Grafana outrena-cutover dashboard):**
- "new-stack traffic share" gauge → 5%.
- "new-stack error rate" stat → must be <0.5%.
- "latency ratio" stat (new p99 / old p99) → must be <1.5x.
- CloudWatch + Azure 5xx for green stack.
- Error budget burn rate (Prometheus).

**Proceed criteria (all must hold):**
- 5xx <0.5% sustained for 15 min.
- p99 latency ratio <1.5x sustained for 15 min.
- No tenant-isolation alert firing.
- No customer reports in Slack.

**Abort criteria (any one):**
- 5xx >1% sustained for 2 min.
- p99 latency >2x old stack sustained for 2 min.
- Any tenant-isolation violation alert fires.
- Scheduler tick >180 s.

If abort: `scripts/cutover/full-cutover-sequence.sh --abort`. Page SRE lead.

### Day 1 — Shift to 25%

**Time budget:** 30 min observation.

```bash
scripts/cutover/full-cutover-sequence.sh --target 25
scripts/cutover/monitor-cutover.sh --window 30m
```

Same watch / proceed / abort criteria as Day 0, but thresholds tighten: **5xx must
remain <0.5%** for the full 30 min (not just 2 min) before declaring stable.

If abort, fall back to 5% (not 0%) unless the issue is severe. The 5% weight has been
proven healthy for 24 hr; reverting to 0% is overkill.

```bash
# Soft abort to 5%:
scripts/cutover/full-cutover-sequence.sh --target 5
```

### Day 3 — Shift to 50%

**Time budget:** 1 hr observation.

```bash
scripts/cutover/full-cutover-sequence.sh --target 50
scripts/cutover/monitor-cutover.sh --window 1h
```

At 50%, you are running the green stack at production-scale load for the first time.
Pay special attention to:
- RDS connections (CloudWatch `DatabaseConnections`) — should track green share.
- Redis evictions — should not spike.
- Scheduler tick duration — should not exceed 120 s.
- LLM cost rate — should track green share (no runaway loops).

If abort, fall back to 25%.

### Day 5 — Shift to 100%

**Time budget:** 1 hr active observation + 24 hr passive observation.

```bash
scripts/cutover/full-cutover-sequence.sh --target 100
scripts/cutover/monitor-cutover.sh --window 1h
# Then leave monitor-cutover.sh running in passive mode for 24 hr:
nohup scripts/cutover/monitor-cutover.sh --window 24h --alert-only &
```

**Proceed criteria at 100%:**
- All Day 0–3 criteria continue to hold.
- Blue stack receives 0% traffic (verify in Grafana).
- Blue stack is **not** decommissioned yet — kept warm for 14 days (see Day 19).

If abort at 100%, fall back to 50%. This is a SEV-1; page SRE lead + product eng lead.

### Day 19 — Decommission Blue Stack

Blue stack has been idle (0% traffic, warm) for 14 days. Decommission:

```bash
# 1. Final verification: confirm green stack has handled 100% of traffic for 14 days
#    with no rollbacks.
scripts/cutover/verify-cutover-complete.sh
# Expected: "Cutover complete. Blue stack idle for 14 days. Safe to decommission."

# 2. Terraform destroy the blue stack resources (AWS).
cd terraform/aws
terraform destroy -target=module.blue_stack -var environment=prod

# 3. Terraform destroy the blue stack resources (Azure).
cd ../azure
terraform destroy -target=module.blue_stack -var environment=prod

# 4. Confirm no orphaned resources.
aws ec2 describe-vpcs --filters Name=tag:Stack,Values=blue --query 'Vpcs[*].VpcId'
# Expected: [] (empty list)

# 5. Close the cutover Slack channel; archive customer comms.
```

> **⚠️ Warning:** Do not decommission before Day 19 even if everything looks healthy.
> The 14-day retention is a hard policy — a deferred bug (e.g. a quarterly cron that
> runs on the 15th) may surface late. If decommission is needed earlier, escalate to
> SRE lead + product eng lead for sign-off.

## Monitoring During Cutover

### `monitor-cutover.sh`

Runs continuously, polls metrics every 30 s, auto-aborts on threshold breach.

```bash
# Active monitoring (foreground, blocks until window expires or abort).
scripts/cutover/monitor-cutover.sh --window 15m

# Passive monitoring (background, abort-only on threshold breach).
nohup scripts/cutover/monitor-cutover.sh --window 24h --alert-only &
```

Abort thresholds (matching the per-day criteria above) are baked in:

```text
ABORT_5XX_PCT=1.0
ABORT_5XX_WINDOW_SEC=120
ABORT_LATENCY_RATIO=2.0
ABORT_LATENCY_WINDOW_SEC=120
ABORT_TENANT_ISOLATION=true   # any alert = immediate abort
ABORT_SCHEDULER_TICK_SEC=180
```

On abort, the script invokes `full-cutover-sequence.sh --abort`, pages PagerDuty, and
posts to `#incident-<date>`.

### Manual abort (if `monitor-cutover.sh` itself fails)

```bash
scripts/cutover/full-cutover-sequence.sh --abort
# Or the per-cloud variants:
scripts/cutover/aws-route53-rollback.sh
scripts/cutover/azure-route53-rollback.sh
```

## Communication Templates

### Slack — shift to next weight (post in #cutover-2025-01)

```text
:cutover: OUTRENA Cutover — shifting to <PCT>%

Green stack weight: <OLD>% → <NEW>%
Observation window: <WINDOW>
On-call: @<on-call-handle>
SRE lead: @<sre-lead-handle>

Watching: https://grafana.outrena.internal/d/outrena-cutover

Abort criteria: 5xx>1% (2min), p99>2x old (2min), any tenant-isolation alert, scheduler tick>180s

Reply :eyes: to ack.
```

### Slack — abort (post in #cutover-2025-01 + #incident-<date>)

```text
:rotating_light: OUTRENA Cutover ABORTED — reverting to <ROLLBACK_PCT>%

Reason: <REASON>
Trigger: <METRIC that breached> = <VALUE> (threshold <THRESHOLD>)
Action taken: scripts/cutover/full-cutover-sequence.sh --abort
Current green share: 0% (full abort) OR <ROLLBACK_PCT>% (soft abort)

On-call: @<on-call-handle>
Next step: SRE lead to lead postmortem within 24 hr.
```

### Email to customers — pre-cutover (T-7 days)

```text
Subject: Scheduled platform maintenance — OUTRENA, <DAY 0 DATE>

Hello,

OUTRENA will be performing scheduled platform maintenance beginning
<DAY 0 DATE>. No downtime is expected. During the maintenance window
you may notice brief periods of elevated latency; if you experience any
issues, please contact support@outrena.com or your account manager.

We will post status updates at https://status.outrena.com.

Thank you,
OUTRENA Operations
```

### Email to customers — cutover complete (Day 6)

```text
Subject: Platform maintenance complete — OUTRENA

Hello,

OUTRENA platform maintenance is complete as of <DAY 5 DATE>. All
systems are operating normally on the upgraded infrastructure.

If you experience any issues, please contact support@outrena.com.

Thank you,
OUTRENA Operations
```

## Verification

After each shift, verify:

```bash
# 1. Weighted routing applied.
dig +short api.outrena.com   # should return both blue + green ALBs
aws route53 get-resource-record-sets --hosted-zone-id <HZ_ID> \
  --query 'ResourceRecordSets[?Name==`api.outrena.com.`]' | jq '.[0].AliasTarget'

# 2. Green stack serving the expected fraction of traffic.
# (Grafana outrena-cutover → "new-stack traffic share" gauge.)

# 3. No tenant-isolation alerts.
aws cloudwatch describe-alarms --state-value ALARM \
  --alarm-name-prefix outrena-tenant-isolation --query 'MetricAlarms[*].AlarmName'

# 4. Scheduler still ticking.
aws cloudwatch get-metric-statistics --namespace OUTRENA/Scheduler \
  --metric-name tick.duration --start-time $(date -u -d '10 min ago' +%FT%TZ) \
  --end-time $(date -u +%FT%TZ) --period 60 --statistics SampleCount
```

## Rollback

See `03-rollback.md` Level C for the full procedure. Cutover-specific:

- **Soft abort:** shift weight back to the previous day's percentage.
- **Hard abort:** `full-cutover-sequence.sh --abort` → 0% green, 100% blue.

The blue stack is retained for 14 days post-100% specifically so hard abort is always
available during the Day 5–Day 19 window.

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| Any abort criteria breached | SRE lead + on-call lead | Immediately (auto-paged by monitor) |
| `monitor-cutover.sh` itself fails | SRE lead — manual monitoring required | Immediately |
| Customer reports issue not caught by monitoring | On-call lead — investigate, likely add to abort criteria | Within 15 min |
| 100% shift fails after 3 attempts | SRE lead + product eng lead — may need to hold at 50% + author fix | Within 1 hr |
| Decommission (Day 19) reveals orphaned resources | SRE lead — manual cleanup + Terraform state refresh | Same business day |
| Deferred bug surfaces after Day 19 | SEV-1 incident — see `05-incident-response.md` | Immediately |

## Related

- `03-rollback.md` — full rollback decision tree.
- `05-incident-response.md` — if cutover triggers a SEV-1.
- `08-disaster-recovery.md` — RDS snapshot is the safety net for destructive failures.
- Migration doc §16.3 (blue/green sequence), §14 (risks).
