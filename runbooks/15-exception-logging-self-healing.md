---
title: Exception Logging + Self-Healing (PostHog self-driving)
last_updated: 2025-01-21
severity: SEV-2
owner: OUTRENA SRE + Product Eng
---

# Exception Logging + Self-Healing (PostHog self-driving)

This runbook covers the **exception tracking → auto-investigation → HITL PR
→ verify-fix** loop added in PH-INFRA. PostHog self-driving is an always-on
agent that watches production errors, drafts fixes, opens PRs, and verifies
them after merge. **A human is always in the loop** — no auto-merge, ever.

**Why self-hosted PostHog (not PostHog Cloud)?** GDPR Article 28 requires a
Data Processing Agreement (DPA) with every sub-processor. PostHog Cloud would
be a sub-processor for our customers' session recordings + error data.
Self-hosting keeps ALL of that data inside our AWS / Azure account → no
additional sub-processor → simpler ROPA (runbook 12 §"Sub-processors").

## 1. Architecture overview

```text
                ┌─────────────────────────────────────────────────────────────┐
                │                          OUTRENA stack                       │
                │                                                              │
   HTTP req ───▶│  ┌─────────────┐   exception   ┌──────────────────────┐    │
                │  │  FastAPI    │──────────────▶│  PostHog Python SDK  │    │
                │  │  (backend)  │               │  (posthog-py)        │    │
                │  └─────────────┘               └──────────┬───────────┘    │
                │                                            │                │
                │  ┌─────────────┐   exception   ┌──────────▼───────────┐    │
                │  │  React SPA  │──────────────▶│  PostHog JS SDK      │    │
                │  │ (frontend)  │               │  (posthog-js)        │    │
                │  └─────────────┘               └──────────┬───────────┘    │
                └───────────────────────────────────────────┼────────────────┘
                                                            │ batch + capture
                                                            ▼
                ┌───────────────────────────────────────────────────────────┐
                │                Self-hosted PostHog stack                  │
                │                                                            │
                │   ┌────────────────┐  events   ┌────────────────────────┐ │
                │   │  PostHog web   │◀─────────│  Kafka (MSK / EH)      │ │
                │   │  (Django+uv)   │           └────────┬───────────────┘ │
                │   └────────┬───────┘                    │                 │
                │            │                            ▼                 │
                │            │              ┌────────────────────────┐      │
                │            │              │  plugin-server (Node)  │      │
                │            │              │  ingest + plugin exec  │      │
                │            │              └────────┬───────────────┘      │
                │            │                       │                      │
                │            │                       ▼                      │
                │            │              ┌────────────────────────┐      │
                │            │              │  ClickHouse (analytics)│      │
                │            │              └────────────────────────┘      │
                │            │                                              │
                │            ▼                                              │
                │   ┌────────────────┐    Celery    ┌──────────────────┐   │
                │   │  Postgres      │◀────────────│  Worker (Celery)  │   │
                │   │  (metadata)    │              └──────────────────┘   │
                │   └────────────────┘                                     │
                │   ┌────────────────┐                                     │
                │   │  Redis         │  cache + broker                     │
                │   └────────────────┘                                     │
                │   ┌────────────────┐                                     │
                │   │  MinIO/S3/Blob │  exports + recordings               │
                │   └────────────────┘                                     │
                └───────────────────────────────────────────────────────────┘
                                   │
                                   │ scouts (every 30 min)
                                   ▼
                ┌───────────────────────────────────────────────────────────┐
                │              PostHog self-driving agent                   │
                │                                                            │
                │   1. Scout scans Error Tracking for patterns               │
                │   2. When threshold met (10 events / 24h, 3x spike,        │
                │      regression after deploy) → opens a "report"           │
                │   3. Agent investigates: stack trace → code search →       │
                │      drafts a fix using claude-3-5-sonnet                  │
                │   4. Opens a PR (author: posthog-bot)                      │
                │   5. PR is labelled `posthog-self-driving`                 │
                └───────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                ┌───────────────────────────────────────────────────────────┐
                │       GitHub Actions HITL workflow                        │
                │   (.github/workflows/posthog-self-driving.yml)            │
                │                                                            │
                │   - validate-metadata: paths + size + body against         │
                │     .posthog-guardrails.yml                                │
                │   - CI: backend lint+test, frontend lint+build, terraform  │
                │   - Label `posthog-needs-review`                           │
                │   - Comment with signal + error report link                │
                │   - FAIL if auto-merge is enabled                          │
                └───────────────────────────────────────────────────────────┘
                                   │  (branch protection enforces)
                                   ▼
                ┌───────────────────────────────────────────────────────────┐
                │                  HUMAN REVIEWER                           │
                │   - Reads the PR + the PostHog error report                │
                │   - Approves + merges (NO auto-merge)                      │
                └───────────────────────────────────────────────────────────┘
                                   │  (push to main)
                                   ▼
                ┌───────────────────────────────────────────────────────────┐
                │   .github/workflows/posthog-verify-fix.yml                 │
                │                                                            │
                │   1. Wait for prod deploy (cd-prod-aws/azure)              │
                │   2. 10-min soak for traffic to flow                       │
                │   3. POST /api/projects/{id}/error_tracking/<r>/verify_fix │
                │   4. PostHog watches error rate for 60 min                 │
                │   5. Result: resolved / needs re-investigation             │
                │   6. Posts summary comment back on the original PR         │
                └───────────────────────────────────────────────────────────┘
                                   │
                                   └───────► feedback loop ◄────────┐
                                          (if not resolved, the
                                           scout re-opens a new PR
                                           with an updated fix)
```

## 2. Component inventory

| Component | File / Resource | Purpose |
|-----------|-----------------|---------|
| **Dev compose stack** | `docker-compose.posthog.yml` | ClickHouse + Postgres + Redis + Kafka + MinIO + web + worker + plugin-server + async-migrations |
| **OUTRENA override** | `posthog/docker-compose.override.yml` | Image pin, SERVER_URL, resource limits, log rotation, monitoring labels |
| **AWS prod infra** | `terraform/aws/posthog.tf` | Aurora PG + ElastiCache + S3 + MSK + ECS Fargate + ALB + WAF + CloudWatch |
| **AWS vars** | `terraform/aws/posthog_variables.tf` | All PostHog-specific TF variables (sizing, image tag, integrations) |
| **Azure prod infra** | `terraform/azure/posthog.tf` | PG Flexible + Redis + Storage + Event Hubs + Container Apps + App Gateway + alerts |
| **Azure vars** | `terraform/azure/posthog_variables.tf` | All PostHog-specific TF variables |
| **K8s Helm values** | `k8s/posthog-values.yaml` | posthog/posthog chart values (ingress, resources, HPA, externals) |
| **HITL PR workflow** | `.github/workflows/posthog-self-driving.yml` | The gate: validate-metadata → CI → label → comment → enforce-no-auto-merge |
| **Post-merge verify** | `.github/workflows/posthog-verify-fix.yml` | detect → wait-for-deploy → soak → verify-fix → comment-result |
| **Guardrails** | `.posthog-guardrails.yml` | allowed/forbidden paths, max files, signal thresholds, agent config |
| **Health check** | `scripts/posthog-health-check.sh` | Bash script: HTTP + TCP + disk + memory + Kafka lag checks |
| **Setup guide** | `docs/posthog-self-driving-setup.md` | Step-by-step (7 steps) from dev to prod |
| **This runbook** | `runbooks/15-exception-logging-self-healing.md` | You are here |
| **Backend env** | `outrena-backend/.env.example` | `POSTHOG_KEY`, `POSTHOG_HOST`, `POSTHOG_PERSONAL_API_KEY`, `POSTHOG_PROJECT_ID`, … |
| **Backend SDK** (PH-BE) | `outrena-backend/app/services/posthog_service.py` | Server-side exception capture (built in parallel by PH-BE) |
| **Frontend SDK** (PH-FE) | `outrena-frontend/src/lib/posthog.ts` | Client-side exception capture (built in parallel by PH-FE) |

## 3. PostHog setup (first run)

### 3.1 Local dev stack

```bash
# 1. Clone + cd into the migration repo.
cd /path/to/migration

# 2. Create the PostHog env file (NEVER commit the real one).
cp posthog/.env.example posthog/.env
# Edit posthog/.env: set POSTHOG_SECRET_KEY (>=32 chars), POSTHOG_POSTGRES_PASSWORD,
# CLICKHOUSE_PASSWORD, OBJECT_STORAGE_ACCESS_KEY_ID, OBJECT_STORAGE_SECRET_ACCESS_KEY.

# 3. Bring up the stack (dev compose + OUTRENA override).
docker compose -f docker-compose.posthog.yml \
               -f posthog/docker-compose.override.yml \
               --env-file posthog/.env up -d

# 4. Wait for the web container to become healthy (~90s on first boot —
#    async-migrations + Django checks).
./scripts/posthog-health-check.sh

# 5. Open the UI + complete the first-run wizard.
open http://localhost:8000
#    → Create admin account (email + password)
#    → Create organization "OUTRENA"
#    → Create project "OUTRENA"
#    → Note the public project API key (starts with `phc_`)
#    → Note the project ID (in the URL: /project/<ID>/...)

# 6. Configure OUTRENA to send events (see §7 below).
```

### 3.2 Production deploy (AWS)

```bash
# 1. Provision the PostHog AWS stack via Terraform.
cd terraform/aws
terraform init -backend-config=envs/prod/backend.tfbackend
terraform apply \
  -var-file=envs/prod/prod.tfvars \
  -var="environment=production" \
  -var="posthog_image_tag=release-1.215.0"  # PIN in prod
# This provisions: Aurora PG, ElastiCache, S3, MSK, ECS cluster + 4 services
# (web/worker/plugin-server/clickhouse), ALB + ACM + Route 53 + WAF, 6 alarms.

# 2. Wait for ECS services to become healthy (~5 min).
aws ecs describe-services --cluster outrena-prd-posthog-ecs \
  --services outrena-prd-posthog-web outrena-prd-posthog-worker \
  outrena-prd-posthog-plugin-server outrena-prd-posthog-clickhouse \
  --query 'services[*].{name:serviceName,desired:desiredCount,running:runningCount}'

# 3. Verify DNS + TLS.
curl -fsS https://posthog.outrena.ai/_health/
# → 200 OK

# 4. Open the UI + complete the first-run wizard (same as dev §3.1 step 5).
open https://posthog.outrena.ai
```

### 3.3 Production deploy (Azure)

Same flow as AWS but `cd terraform/azure && terraform apply -var-file=envs/prod/prod.tfvars`.
The Azure stack provisions: PG Flexible + Redis + Storage + Event Hubs + 4
Container Apps + App Gateway + DNS A-record + 4 alert rules.

## 4. Self-driving setup

Self-driving is a PostHog feature (not a separate product) — you enable it
in the PostHog UI after the self-hosted instance is up.

### 4.1 Enable self-driving

```text
1. Log into PostHog → Settings → Self-driving
2. Click "Enable self-driving"
3. Connect GitHub:
   - Click "Install PostHog GitHub App"
   - Select the OUTRENA repo (outrena/migration)
   - Grant the app: Pull requests (read+write), Contents (read+write),
     Workflows (read) — needed for the agent to open PRs.
4. Configure the agent:
   - Model: claude-3-5-sonnet (recommended; configurable)
   - Max investigation time: 10 min (default; matches .posthog-guardrails.yml)
   - Open PR when actionable: ON
   - Surface in inbox when ambiguous: ON
5. Point at the guardrails file:
   - Guardrails path: .posthog-guardrails.yml
   - PostHog reads this from the repo root on every PR.
```

### 4.2 Configure GitHub branch protection (CRITICAL — see also setup guide §5)

In the OUTRENA repo settings → Branches → Branch protection rules → `main`:

```text
☑ Require pull request reviews before merging
   Required approving reviews: 1
   ☑ Require review from Code Owners
☑ Require status checks to pass before merging
   Required status checks:
     - PostHog self-driving · HITL PR gate / enforce-no-auto-merge
     - CI / backend-lint
     - CI / backend-test
     - CI / frontend-build
     - CI / terraform-validate
   ☑ Require branches to be up to date before merging
☑ Require conversation resolution before merging
☐ Do NOT allow bypassing the above settings (admins included)
☑ Restrict who can dismiss pull request reviews
   - (only SRE leads — not the posthog-bot account)
```

**The posthog-bot account MUST NOT be a Code Owner** — see `.github/CODEOWNERS`.
Even if the bot is a Code Owner, branch protection's "Require review from Code
Owners" should be paired with "Restrict who can dismiss pull request reviews"
so the bot can't self-approve.

## 5. HITL workflow — step-by-step for the reviewer

When a PostHog self-driving PR lands in your review queue:

```text
1. Read the PR description
   - The PR links to a PostHog error report (posthog.outrena.ai/.../error_tracking/...)
   - Open the report in a new tab → see the stack trace, affected users,
     first/last seen, deploy annotation when it started.

2. Check the workflow run
   - The posthog-self-driving.yml workflow ran 9 jobs:
     gate → validate-metadata → CI (4 jobs) → label-needs-review →
     comment-context → enforce-no-auto-merge
   - ALL must be green. If any failed, the PR is blocked from merge.

3. Review the diff
   - Guardrails enforce: only outrena-backend/app/**, outrena-frontend/src/**,
     outrena-backend/tests/**, runbooks/** are allowed.
   - Forbidden: terraform/**, .github/**, alembic/versions/**, app/core/config.py, *.env*
   - Max 5 files per PR.
   - The diff should be minimal — ONE fix, not a refactor.

4. Run the change locally (optional but recommended for risky fixes)
   - Pull the PR branch
   - Reproduce the original error (use the PostHog report's stack trace)
   - Confirm the fix resolves it
   - Run the affected test file: pytest outrena-backend/tests/...

5. Approve + merge
   - Use "Squash and merge" so the commit message is clean
   - The posthog-verify-fix.yml workflow will fire automatically

6. Watch the verification
   - The verify-fix workflow waits for prod deploy + 10-min soak, then
     calls PostHog's verify_fix endpoint.
   - PostHog watches the error rate for 60 min.
   - Result is posted as a comment on the PR:
     ✅ resolved  → done, close the PR
     ❌ needs re-investigation → the scout will open a new PR; if it's the
                                 same fix, add the `posthog-paused` label
                                 and investigate manually.
```

## 6. Guardrails

The guardrails file (`.posthog-guardrails.yml`) is the contract between
PostHog self-driving and OUTRENA. It's read by:

1. **The PostHog agent** when drafting a fix — it constrains which files
   the agent can edit.
2. **The `validate-metadata` job** in `posthog-self-driving.yml` — re-checks
   the PR diff against the rules. This is the enforcement layer (the agent
   could drift; CI catches it).

### 6.1 Modifying the guardrails

```bash
# Edit .posthog-guardrails.yml at the repo root.
vim .posthog-guardrails.yml

# Test the YAML parses:
python -c "import yaml; yaml.safe_load(open('.posthog-guardrails.yml'))"

# Commit + push. The next PostHog self-driving PR will pick up the new rules.
# (PostHog re-reads the file from the repo root on every PR — no restart needed.)
```

### 6.2 What to do if the agent drafts a bad fix

If the agent opens a PR that's clearly wrong (hallucination, wrong call site,
etc.):

```text
1. DON'T merge it. The HITL gate exists for exactly this case.
2. Close the PR with a comment explaining why ("wrong call site — the error
   is in prospect_service.py:142, not prospect_service.py:87").
3. The PostHog scout will re-investigate on the next scan (30 min by default).
   It will see the same error report + the new context from your comment
   and try again.
4. If the agent keeps drafting the same bad fix, add the `posthog-paused`
   label to the next PR (this signals self-driving to pause — see §12).
5. If pausing doesn't help, disable self-driving from the PostHog UI
   (Settings → Self-driving → toggle OFF) and file a GitHub Issue.
```

## 7. Exception capture

### 7.1 Backend (Python SDK)

The backend uses `posthog-py` (added by PH-BE). Capture is wired into the
FastAPI exception handler in `app/main.py`:

```python
# outrena-backend/app/main.py (excerpt — full impl owned by PH-BE)
from posthog import Posthog

posthog = Posthog(
    project_api_key=settings.POSTHOG_KEY,
    host=settings.POSTHOG_HOST,
    flush_at=settings.POSTHOG_FLUSH_AT,
    flush_interval=settings.POSTHOG_FLUSH_INTERVAL,
)

@app.exception_handler(Exception)
async def capture_unhandled(request: Request, exc: Exception):
    posthog.capture_exception(exc, properties={
        "url": str(request.url),
        "method": request.method,
        "tenant": request.state.tenant_slug,
        "user_id": request.state.user_id,
    })
    return JSONResponse(status_code=500, content={"detail": "internal error"})
```

To add **custom** exception capture in your code:

```python
from app.services.posthog_service import posthog

try:
    risky_operation()
except Exception as e:
    posthog.capture_exception(e, properties={
        "context": "enrichment",
        "prospect_id": str(prospect.id),
    })
    raise  # re-raise so the normal handler also fires
```

### 7.2 Frontend (JavaScript SDK)

The frontend uses `posthog-js` (added by PH-FE). Capture is wired into the
React error boundary in `src/App.tsx`:

```tsx
// outrena-frontend/src/App.tsx (excerpt — full impl owned by PH-FE)
import posthog from "posthog-js";

posthog.init(import.meta.env.VITE_POSTHOG_KEY, {
  api_host: import.meta.env.VITE_POSTHOG_HOST,
  autocapture: false,
  capture_pageview: true,
  capture_pageleave: true,
  session_recording: {
    maskAllInputs: true,    // GDPR — never record form inputs
    maskTextSelector: ".sensitive",  // extra masking
  },
});

class ErrorBoundary extends React.Component {
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    posthog.captureException(error, { react_info: info });
  }
}
```

To add **custom** capture:

```tsx
import posthog from "posthog-js";

try {
  await riskyApiCall();
} catch (e) {
  posthog.captureException(e, { feature: "sequences-page" });
  throw e;
}
```

## 8. Monitoring the system

### 8.1 PostHog health

```bash
# Health check script — checks all services via HTTP/TCP + disk + memory + Kafka lag.
./scripts/posthog-health-check.sh
# → exits 0 if healthy, 1 if critical, 2 if warnings.

# JSON output (for Prometheus / alertmanager integration):
./scripts/posthog-health-check.sh --json

# Custom host:
./scripts/posthog-health-check.sh --host https://posthog.outrena.ai
```

### 8.2 PostHog UI dashboards

- **Error Tracking** (`/projects/<id>/error_tracking`) — the live error feed.
  Filter by `tenant`, `environment`, `service` (backend/frontend/worker).
- **Self-driving inbox** (`/projects/<id>/self_driving`) — pending reports
  the agent is investigating or has surfaced for human judgement.
- **Activity log** (`/projects/<id>/self_driving/activity`) — every action
  the agent has taken (investigated → drafted → opened PR → verified).

### 8.3 PR queue

```bash
# All open PostHog self-driving PRs:
gh pr list --label "posthog-needs-review" --state open

# Recently merged PostHog self-driving PRs + their verification status:
gh pr list --label "posthog-self-driving" --state closed --limit 20 \
  --json number,title,mergedAt,comments
```

### 8.4 CloudWatch / Log Analytics alerts

AWS (terraform/aws/posthog.tf):
- `outrena-prd-posthog-web-5xx-rate` — ALB 5xx > 1% over 5 min.
- `outrena-prd-posthog-aurora-cpu-high` — Aurora CPU > 80% for 10 min.
- `outrena-prd-posthog-redis-evictions-high` — Redis evictions > 1000/min.
- `outrena-prd-posthog-clickhouse-cpu-high` — ClickHouse CPU > 90%.
- `outrena-prd-posthog-msk-cpu-high` — MSK broker CPU > 80%.
- `outrena-prd-posthog-worker-queue-depth-high` — Celery queue > 10000.

Azure (terraform/azure/posthog.tf):
- `outrena-prd-posthog-web-5xx` — App Gateway 5xx > 5 over 5 min.
- `outrena-prd-posthog-pg-cpu-high` — PG Flexible CPU > 80% for 15 min.
- `outrena-prd-posthog-redis-server-load-high` — Redis server load > 80%.
- `outrena-prd-posthog-eh-throughput-high` — Event Hubs backlog > 1000.

## 9. Troubleshooting

### 9.1 PostHog is down (web returns 5xx)

```bash
# 1. Check the health script.
./scripts/posthog-health-check.sh --host https://posthog.outrena.ai
# → identifies which service is down.

# 2. Check ECS / Container Apps.
aws ecs describe-services --cluster outrena-prd-posthog-ecs \
  --services outrena-prd-posthog-web \
  --query 'services[0].{desired:desiredCount,running:runningCount,deployments:deployments[*].{status:status,running:runningCount,desired:desiredCount}}'

# 3. Tail the web logs.
aws logs tail /outrena/prd/posthog/web --since 10m --follow

# 4. Common causes:
#    - ClickHouse OOM → bump the task memory in posthog.tf (var.posthog_clickhouse_*)
#    - Aurora failover → wait 60s, the Django ORM reconnects automatically
#    - MSK broker restart → plugin-server reconnects automatically
#    - Disk full (MinIO/S3) → check the bucket lifecycle is enabled
```

### 9.2 SDK is not capturing exceptions

```bash
# Backend:
# 1. Verify POSTHOG_KEY + POSTHOG_HOST are set.
grep -E "^POSTHOG_(KEY|HOST)" outrena-backend/.env
# 2. Verify the SDK is initialized.
curl -fsS http://localhost:8000/health | jq
# 3. Trigger a test exception:
curl -X POST http://localhost:8000/api/v1/_debug/throw
# 4. Check PostHog → /projects/<id>/events → filter by event="$exception"

# Frontend:
# 1. Open browser DevTools → Network tab.
# 2. Trigger an error (e.g. navigate to a 404 page).
# 3. Look for a POST to https://posthog.outrena.ai/batch — should be 200.
# 4. If 4xx → check VITE_POSTHOG_KEY + VITE_POSTHOG_HOST in the .env file.
```

### 9.3 Self-driving is not opening PRs

```text
1. Check the scout is enabled:
   PostHog UI → Settings → Self-driving → "Scout enabled" should be ON.

2. Check the scan interval:
   Default is 30 min (scout_config.scan_interval_minutes in .posthog-guardrails.yml).
   The scout only opens a report if threshold is met (10 events / 24h, 3x spike,
   or a regression after a deploy).

3. Check the activity log:
   PostHog UI → Self-driving → Activity log.
   If the scout is finding reports but the agent is NOT opening PRs:
     - The agent may have hit max_investigation_time_minutes (10 min default).
       Increase in .posthog-guardrails.yml → agent_config.
     - The agent may have surfaced the report in the inbox (ambiguous case)
       instead of opening a PR. Review the inbox.

4. Check the PostHog GitHub App is installed on the repo:
   GitHub → Settings → Integrations → Applications → PostHog.
   Must show "outrena/migration" in the installed repos.

5. Check GitHub Actions status:
   The agent opens the PR, but if the posthog-self-driving.yml workflow
   has a bug, the PR will appear but the gate won't run.
```

### 9.4 Agent is drafting bad fixes

```text
1. Close the PR with a clear comment explaining what's wrong.
   The agent reads PR comments in its next investigation.

2. If the same fix keeps coming back:
   - Add the `posthog-paused` label to the next PR
   - OR disable self-driving from PostHog UI (Settings → Self-driving → OFF)

3. File a GitHub Issue with the PR link + the error report link.
   The SRE team will tune the guardrails or the agent's prompt.

4. If the agent is touching forbidden paths:
   - This is a guardrail violation — the CI gate should have caught it
   - File a SEV-2 incident (the agent is mis-behaving)
   - Disable self-driving immediately
```

### 9.5 Verification is failing

```text
1. Read the verify-fix workflow output:
   GitHub Actions → posthog-verify-fix → verify-fix job → logs

2. Check the PostHog verification URL (in the workflow output + PR comment):
   https://posthog.outrena.ai/projects/<id>/error_tracking/<report_id>/verify_fix/<verif_id>
   → shows the live error rate vs the pre-fix baseline

3. If the error rate did NOT drop:
   - The fix is correct but incomplete (other call sites have the same bug)
     → wait for the scout to open a new PR for the remaining call sites
   - The fix is wrong
     → revert the merge commit; add `posthog-paused` label to the original PR
   - The error report was mis-clustered (different errors grouped together)
     → split the cluster in PostHog UI (Error Tracking → click the report → "Split")

4. If the verify-fix workflow itself failed (not PostHog's verdict):
   - Check the POSTHOG_PERSONAL_API_KEY + POSTHOG_PROJECT_ID secrets are set
   - Check the prod deploy actually happened (wait-for-deploy job)
   - Re-run the workflow manually:
     gh workflow run posthog-verify-fix.yml -f pr_number=<PR_NUMBER>
```

## 10. Security + privacy

### 10.1 Self-hosting = no sub-processor

PostHog Cloud would be a GDPR Article 28 sub-processor for our customers'
session recordings + error data. Self-hosting keeps ALL of that data inside
our AWS / Azure account → no DPA needed with PostHog the company → simpler
ROPA (runbook 12 §"Sub-processors").

### 10.2 Session recording masks inputs (GDPR)

The frontend SDK (`posthog-js`) is configured with:
- `session_recording.maskAllInputs: true` — form fields are recorded as `*`
- `session_recording.maskTextSelector: ".sensitive"` — extra masking for
  elements with the `sensitive` class (use on prospect names, email bodies)

To mark additional elements as sensitive:

```tsx
<div className="sensitive">
  {prospect.email}  {/* recorded as **** in session replays */}
</div>
```

### 10.3 PII handling

- Backend exception properties MUST NOT include PII. The PostHog SDK is
  initialized with a property allowlist (PH-BE owns the exact list).
- Frontend exception properties are auto-scrubbed by `posthog-js`'s
  `property_denylist` config (URLs, form values).
- If a PII leak is detected (someone added `prospect.email` to a property):
  1. Delete the offending events from PostHog:
     `DELETE /api/projects/<id>/events?event_id=<id>` (with personal API key)
  2. Open a SEV-2 incident per runbook 05 §"PII leak"
  3. Fix the property allowlist + add a regression test

### 10.4 Access controls

- PostHog admin login: SSO via Keycloak (configured in PostHog UI → Settings → SSO).
  Local accounts are disabled in prod.
- PostHog personal API keys (used by verify-fix.yml): generated per-user in
  PostHog UI → Profile → Personal API keys. Stored in GitHub Actions secrets
  as `POSTHOG_PERSONAL_API_KEY`. Rotate every 90 days (matches runbook 09).
- PostHog project ID: stored as `POSTHOG_PROJECT_ID` GitHub Actions secret.
  Non-secret — appears in URLs — but stored as a secret to avoid accidental
  drift between environments.

## 11. Maintenance

### 11.1 Upgrading PostHog

```bash
# 1. Check the PostHog release notes for breaking changes.
#    https://github.com/PostHog/posthog/releases

# 2. Bump the image tag in posthog/.env (dev) or terraform vars (prod).
#    DEV:
sed -i 's/POSTHOG_IMAGE_TAG=.*/POSTHOG_IMAGE_TAG=release-1.216.0/' posthog/.env
#    PROD:
cd terraform/aws
# Edit envs/prod/prod.tfvars: posthog_image_tag = "release-1.216.0"

# 3. Dev: pull the new image + recreate the containers.
docker compose -f docker-compose.posthog.yml pull
docker compose -f docker-compose.posthog.yml up -d

# 4. Prod: terraform apply.
terraform apply -var-file=envs/prod/prod.tfvars

# 5. Watch the async-migrations — PostHog runs them on first boot.
./scripts/posthog-health-check.sh --host https://posthog.outrena.ai

# 6. If migrations fail, ROLLBACK:
#    Dev:  docker compose -f docker-compose.posthog.yml down -v && \
#          git checkout HEAD~1 -- posthog/.env && \
#          docker compose -f docker-compose.posthog.yml up -d
#    Prod: terraform apply -var="posthog_image_tag=release-1.215.0" \
#            -var-file=envs/prod/prod.tfvars
#          (Aurora + ClickHouse data is preserved; only the container image rolls back.)
```

### 11.2 Backing up ClickHouse

```bash
# ClickHouse stores ALL events + insights. Back up daily to S3 / Blob.

# 1. AWS — use the clickhouse-backup tool (already in the ClickHouse container).
docker exec posthog-clickhouse clickhouse-backup create daily_$(date +%Y%m%d)
docker exec posthog-clickhouse clickhouse-backup upload daily_$(date +%Y%m%d) \
  --s3-bucket outrena-prd-posthog-storage --s3-path backups/clickhouse/

# 2. Azure — same tool, but with Azure Blob backend.
docker exec posthog-clickhouse clickhouse-backup upload daily_$(date +%Y%m%d) \
  --azure-container posthog --azure-account outrenaprdposthogstorage

# 3. Schedule via EventBridge / Logic App (see terraform/aws/posthog.tf TODO).
#    Retention: 30 daily + 12 monthly + 7 yearly (matches runbook 08 DR).

# 4. Restore drill — quarterly:
#    See runbook 08-disaster-recovery.md §"ClickHouse restore drill".
```

### 11.3 Scaling workers

```bash
# 1. Watch the worker queue depth alarm (CloudWatch: posthog-worker-queue-depth-high).
#    If it fires frequently, scale up.

# 2. Bump the desired count via Terraform:
cd terraform/aws
# Edit envs/prod/prod.tfvars: posthog_worker_desired_count = 4
terraform apply -var-file=envs/prod/prod.tfvars

# 3. Or use ECS autoscaling (not in v1 — add a aws_appautoscaling_target + policy
#    on the worker service when this becomes a frequent need).

# 4. If queue depth is high because of a stuck job, not throughput:
aws ecs execute-command --cluster outrena-prd-posthog-ecs \
  --task <TASK_ID> --container worker --interactive \
  --command "celery -A posthog inspect active"
# → shows the currently-executing tasks; kill the stuck one.
```

### 11.4 Cost management

PostHog's main cost drivers (in order):

1. **ClickHouse storage** — events are stored forever by default. Add a
   TTL on the `events` table to drop events older than 2 years (matches
   GDPR retention for telemetry, runbook 12 §"Retention").
   ```sql
   ALTER TABLE posthog.events MODIFY TTL timestamp + INTERVAL 2 YEAR;
   ```
2. **MSK / Event Hubs throughput** — scale down to 1 broker in off-peak
   hours (dev only). Prod keeps 3 brokers for HA.
3. **ECS Fargate** — the worker + plugin-server can scale to 0 in dev
   at night (not implemented in v1 — add a scheduled ECS service action).
4. **S3 / Blob storage** — the lifecycle rule transitions exports to
   Glacier after 90d and deletes after 365d (terraform/aws/posthog.tf).

## 12. Disabling self-driving

For incidents, maintenance windows, or when the agent is mis-behaving:

### 12.1 Pause (soft — single PR)

```bash
# Add the `posthog-paused` label to the open PR:
gh pr edit <PR_NUMBER> --add-label posthog-paused

# This signals to PostHog that the agent should NOT open new PRs for the
# same error report. The scout will continue investigating but won't draft
# a fix until the label is removed.
```

### 12.2 Disable (hard — global)

```text
1. PostHog UI → Settings → Self-driving → toggle OFF
   (This stops the scout from investigating + the agent from drafting.)

2. Close all open posthog-self-driving PRs:
   gh pr list --label "posthog-self-driving" --state open --json number \
     --jq '.[].number' | \
     xargs -I{} gh pr close {} --comment "Paused: self-driving disabled for maintenance"

3. Set a calendar reminder to re-enable. PostHog keeps the scout state so
   when you re-enable, it resumes from where it left off (no re-investigation
   of already-resolved reports).
```

### 12.3 Full shutdown (permanent decommission)

```bash
# 1. Disable self-driving in PostHog UI (see §12.2).

# 2. Remove the GitHub App from the OUTRENA repo:
#    GitHub → Settings → Integrations → Applications → PostHog → Configure → Remove

# 3. Remove the PostHog secrets from GitHub Actions:
gh secret delete POSTHOG_PERSONAL_API_KEY
gh secret delete POSTHOG_PROJECT_ID
gh secret delete POSTHOG_HOST

# 4. Delete the PostHog infrastructure:
cd terraform/aws
terraform destroy -var-file=envs/prod/prod.tfvars
# (This drops Aurora + ClickHouse + S3 + MSK + ECS — IRREVERSIBLE.
#  Take a final ClickHouse backup first — see §11.2.)

# 5. Remove the PostHog env vars from outrena-backend/.env + outrena-frontend/.env.
# 6. Remove the .github/workflows/posthog-*.yml files + .posthog-guardrails.yml.
# 7. Remove this runbook.
```

## 13. Related

- `docs/posthog-self-driving-setup.md` — step-by-step setup guide (7 steps).
- `.posthog-guardrails.yml` — the guardrails config (allowed/forbidden paths, thresholds).
- `.github/workflows/posthog-self-driving.yml` — the HITL PR gate workflow.
- `.github/workflows/posthog-verify-fix.yml` — the post-merge verification workflow.
- `docker-compose.posthog.yml` — the dev/staging self-host compose.
- `posthog/docker-compose.override.yml` — OUTRENA-specific overrides.
- `terraform/aws/posthog.tf` — AWS prod infrastructure.
- `terraform/azure/posthog.tf` — Azure prod infrastructure.
- `k8s/posthog-values.yaml` — Helm values for K8s deploys.
- `scripts/posthog-health-check.sh` — health check script.
- `outrena-backend/app/services/posthog_service.py` (PH-BE) — backend SDK wrapper.
- `outrena-frontend/src/lib/posthog.ts` (PH-FE) — frontend SDK wrapper.
- `runbooks/12-gdpr-compliance.md` §"Sub-processors" — DPA implications.
- `runbooks/09-secrets-management.md` — POSTHOG_PERSONAL_API_KEY rotation.
- `runbooks/05-incident-response.md` §"PII leak" — PII leak response.
- PostHog docs: <https://posthog.com/docs/self-host>, <https://posthog.com/docs/self-driving>
