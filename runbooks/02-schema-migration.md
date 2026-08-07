---
title: Schema Migration Runbook (Alembic, Multi-Tenant)
last_updated: 2025-01-15
severity: SEV-2
owner: OUTRENA SRE
---

# Schema Migration Runbook (Alembic, Multi-Tenant)

Running Alembic migrations across the public schema and every tenant schema
(`tenant_<slug>`). Phase 6 uses dual-mode Alembic: the public schema and each tenant
schema are migrated independently. This runbook covers authoring, local testing,
deploying to prod, and rolling back a single failed tenant.

## Prerequisites

- Author has read migration doc §4.3 (per-tenant schemas) and pitfall #3 (`_s()`
  helper).
- Local Docker available (`docker compose`).
- CI/CD pipeline `cd-prod-{aws,azure}.yml` configured; deploy permission for prod.
- `verify_schema_health.py` green on current prod before starting.
- Manual RDS snapshot taken in the last 24 hr (see `08-disaster-recovery.md`).
- Maintenance window scheduled if the migration is **destructive** (column drops,
  type changes, not-null constraints, data backfills).

## Dual-Mode Alembic — How It Works

Alembic `env.py` reads `TARGET_SCHEMA` env var:

- **`TARGET_SCHEMA=public`** (or unset) — operates on the `public` schema only. Used
  for global tables (`tenants`, `audit_log`, `feature_flags`).
- **`TARGET_SCHEMA=tenant_<slug>`** — operates on that tenant schema only. Used for
  per-tenant tables (`sequences`, `contacts`, `autopilot_runs`, etc.).

There is no "migrate all tenants" Alembic command — the deploy script
`scripts/db-migrate-all-tenants.sh` iterates the tenant table and invokes Alembic once
per tenant with `TARGET_SCHEMA` set.

### The `_s()` helper (pitfall #3)

Inside migration files, **never** hard-code a schema name. Use the `_s()` helper:

```python
from migrations.helpers import _s

def upgrade():
    # Right — schema-qualified via _s()
    op.create_table(
        "sequences_v2",
        *_s_columns(),
        schema=_s(),  # resolves to TARGET_SCHEMA at runtime
    )

    # Wrong — hard-coded; breaks the public-tenants split:
    # op.create_table("sequences_v2", ..., schema="public")
```

`_s()` resolves at runtime to the current `TARGET_SCHEMA` env var. A migration that
hard-codes `public` will silently corrupt the public/tenant split when run against a
tenant schema.

## Authoring a New Migration

```bash
cd /srv/outrena

# Generate a revision. The --rev-id is optional but recommended for traceability.
alembic revision -m "add sequence_sent_at_index"
# Creates: migrations/versions/<rev>_<slug>.py
```

Edit the new file:

```python
"""add sequence_sent_at_index

Revision ID: a1b2c3d4e5f6
Revises: 9z8y7x6w5v4u
Create Date: 2025-01-15 10:30:00.000000
"""
from alembic import op
from migrations.helpers import _s

revision = "a1b2c3d4e5f6"
down_revision = "9z8y7x6w5v4u"
branch_labels = None
depends_on = None

def upgrade():
    op.create_index(
        "ix_sequences_sent_at",
        "sequences",
        ["sent_at"],
        schema=_s(),
    )

def downgrade():
    op.drop_index("ix_sequences_sent_at", table_name="sequences", schema=_s())
```

Commit + push; the migration file ships inside the Docker image.

## Local Testing

```bash
# 1. Bring up a fresh Postgres.
cd /srv/outrena
docker compose up -d postgres

# 2. Apply all migrations to the public schema.
TARGET_SCHEMA=public alembic upgrade head

# 3. Apply all migrations to a fake tenant schema.
TARGET_SCHEMA=tenant_test_co alembic upgrade head

# 4. Idempotency check — run upgrade head again on both; must be a no-op.
TARGET_SCHEMA=public alembic upgrade head
TARGET_SCHEMA=tenant_test_co alembic upgrade head
# Expected output for both: "INFO  [alembic.runtime.migration] Will skip ... already at head"

# 5. Downgrade test — verify the downgrade path works.
TARGET_SCHEMA=tenant_test_co alembic downgrade -1
TARGET_SCHEMA=tenant_test_co alembic upgrade head
# Should round-trip cleanly.

# 6. Schema-health verify.
python scripts/verify_schema_health.py --schema public
python scripts/verify_schema_health.py --schema tenant_test_co
```

> **⚠️ Warning:** If idempotency check (step 4) fails — i.e. running `upgrade head`
> twice does anything other than skip — the migration is non-idempotent and **must
> not** ship. A common cause: a `CREATE INDEX` without `IF NOT EXISTS`.

## Deploy Sequence (Prod)

### Step 1 — Build and push image

Triggered automatically when the migration PR merges to `main`. To do manually:

```bash
# AWS path
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker build -t outrena-backend:$(git rev-parse --short HEAD) .
docker tag  outrena-backend:$(git rev-parse --short HEAD) \
            123456789012.dkr.ecr.us-east-1.amazonaws.com/outrena-backend:$(git rev-parse --short HEAD)
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/outrena-backend:$(git rev-parse --short HEAD)

# Azure path (ACR)
az acr build --registry outrenaprod --image outrena-backend:$(git rev-parse --short HEAD) .
```

### Step 2 — Terraform apply new task def

```bash
cd terraform/aws
terraform plan -var backend_image_tag=$(git rev-parse --short HEAD) -out=tfplan
terraform apply tfplan
# Bumps the ECS task definition; new tasks roll out via rolling deploy.
```

### Step 3 — Pre-deploy schema health check

```bash
# Verify the live prod schemas are healthy BEFORE migrating. Risk #17 mitigation.
python scripts/verify_schema_health.py --all-tenants
# Expected: PASS for every tenant. If any FAIL, abort and consult
# 05-incident-response.md — this is a potential tenant isolation violation.
```

### Step 4 — Run migrations on all tenants

```bash
# Set env vars.
export DATABASE_URL="postgresql://outrena_app:***@prod-rds.outrena.internal/outrena"
export ALEMBIC_CONFIG="/srv/outrena/alembic.ini"

# Public schema first.
TARGET_SCHEMA=public alembic upgrade head

# Then all tenants.
scripts/db-migrate-all-tenants.sh
# Iterates SELECT slug FROM public.tenants WHERE status='active';
# For each: TARGET_SCHEMA=tenant_<slug> alembic upgrade head
# Logs to /var/log/outrena/migrate-<ts>.log. Reports per-tenant pass/fail.
```

### Step 5 — Post-deploy schema health check

```bash
python scripts/verify_schema_health.py --all-tenants
# All PASS expected. Any FAIL → see Rollback section.
```

### Step 6 — Smoke test

```bash
# Hit the /health endpoints.
curl -fsS https://api.outrena.com/health | jq .
curl -fsS https://api.outrena.com/health/ready | jq .

# Hit a tenant-specific endpoint with a synthetic test user.
curl -fsS -H "Authorization: Bearer $TEST_TOKEN_TENANT_A" \
  https://api.outrena.com/v1/sequences | jq '.data | length'
```

### Step 7 — Monitor 30 min

Watch the **outrena-overview** Grafana dashboard for 30 min after deploy. Abort
thresholds: 5xx >0.5%, p99 latency >1500 ms, scheduler tick >120 s, any
tenant-isolation alert.

## Rollback (Single Tenant Failed)

If `db-migrate-all-tenants.sh` reports a failure on `tenant_acme_corp` only:

```bash
export TARGET_SCHEMA="tenant_acme_corp"
cd /srv/outrena
alembic downgrade -1
# Reverts only tenant_acme_corp back one revision. Other tenants are unaffected.

# Verify.
python scripts/verify_schema_health.py --schema tenant_acme_corp
alembic current
# Expected: the previous revision id.
```

> **⚠️ Warning:** Destructive migrations (column drops, type changes, NOT NULL without
> default) cannot be cleanly downgraded — the data is gone. For these, **do not** run
> `alembic downgrade`; instead author a **forward-only fix migration** that restores
> the previous shape. The original migration's `downgrade()` is best-effort and may
> raise. See migration doc §16 "Rollback Plan" for the full forward-only policy.

### If the migration is destructive and already applied

1. Stop the deploy. Page SRE lead.
2. Restore the affected tenant schema from the pre-deploy RDS snapshot
   (see `08-disaster-recovery.md`).
3. Author a forward-fix migration that reconstructs the dropped column / data.
4. Re-run `db-migrate-all-tenants.sh` skipping the bad tenant, then apply the
   forward-fix to the restored tenant.

## Env Vars Reference

| Var | Required | Example | Notes |
|-----|----------|---------|-------|
| `DATABASE_URL` | yes | `postgresql://outrena_app:***@host/outrena` | Libpq URL; the migration runner connects as `outrena_app`. |
| `TARGET_SCHEMA` | yes (per-invocation) | `tenant_acme_corp` or `public` | Read by `env.py`. If unset, defaults to `public`. |
| `ALEMBIC_CONFIG` | no | `/srv/outrena/alembic.ini` | Defaults to `./alembic.ini`. |
| `ALEMBIC_SCRIPT_LOCATION` | no | `/srv/outrena/migrations` | Override only for non-standard layouts. |
| `OUTRENA_ENV` | yes | `prod` | `env.py` rejects any other value for safety. |

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| `verify_schema_health.py` reports drift on any tenant | SRE lead — possible Risk #17 | Immediately, before any further deploys |
| Migration fails on >1 tenant with same error | Platform eng lead (migration bug) | Immediately |
| Migration fails on 1 tenant only | SRE on-call (per-tenant issue) | Within 30 min |
| `downgrade()` raises `NotImplementedError` or data-loss error | SRE lead + DBA | Immediately — switch to forward-only fix path |
| Rollback itself fails | SRE lead + page DBA vendor | SEV-1, immediately |

## Related

- `03-rollback.md` — full rollback decision tree (code + db + stack).
- `08-disaster-recovery.md` — RDS snapshot restore if downgrade fails.
- `monitoring/alert-runbook.md` — alerts `rds-cpu-high`, `tenant-isolation-violation`.
- Migration doc §4.3 (per-tenant schemas), §10 (Phase 6 deliverables), §16 (rollback
  plan).
