---
title: Tenant Provisioning Runbook
last_updated: 2025-01-15
severity: SEV-3
owner: OUTRENA SRE
---

# Tenant Provisioning Runbook

Provisioning a new tenant on the OUTRENA platform. Implements the 6-step compensating
flow defined in migration doc §4.4. Each step is independently reversible; the runbook
documents rollback for partial failures.

## Prerequisites

- Operator has `platform-admin` role or higher.
- Tenant intake form completed (in Notion: `OUTRENA > Tenants > Intake`). Captures:
  legal name, billing entity, requested slug, admin user email, SSO preference.
- Slack channel for the tenant (e.g. `#tenant-acme-corp`) created; on-call + customer
  success subscribed.
- Maintenance window scheduled if provisioning a **paid** tenant during business hours
  (provisioning itself takes ~5 min, but the first cache warm can spike RDS CPU).
- Confirmed access to:
  - Bastion / SSM Session Manager for the prod RDS instance.
  - Keycloak admin console (`https://auth.outrena.com/admin`) or Admin API token.
  - AWS Console (ECS, RDS, ElastiCache) + Azure Portal (Container Apps, PG Flexible).
  - GitHub Actions workflow `provision-tenant.yml` trigger permission.

### Slug Validation (pre-flight)

The tenant slug must satisfy the regex in `src/lib/slug.py`:

```regex
^[a-z0-9][a-z0-9-]{2,30}[a-z0-9]$
```

- Lowercase alphanumeric + hyphens only.
- 4–32 characters.
- Cannot start or end with a hyphen.
- No consecutive hyphens.

Reserved slugs (cannot be used) — see `src/lib/slug.py::RESERVED_SLUGS`:

```
public, admin, internal, api, app, auth, mail, mailbridge,
keycloak, grafana, loki, tempo, prometheus, postgres, redis,
staging, prod, dev, test, demo, sandbox, default, root, system,
outrena, owner, support, billing, sales
```

If the requested slug is reserved or fails the regex, return the intake form to the
requester with the constraint list and request a new slug. **Do not** "massage" a
non-conformant slug silently.

## Procedure

The 6-step flow is implemented by `scripts/provision_tenant.py`. Run the script for the
happy path. Each step is described below so an operator can execute manually if the
script fails partway.

### Step 1 — INSERT into `public.tenants`

Insert the tenant row with status `provisioning`. The row is the source of truth for
all subsequent steps.

```bash
# Via the platform API (preferred):
curl -X POST https://api.outrena.com/platform/tenants \
  -H "Authorization: Bearer $PLATFORM_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "acme-corp",
    "legal_name": "ACME Corporation, Inc.",
    "billing_entity": "ACME Corporation, Inc.",
    "plan": "growth",
    "admin_email": "admin@acme-corp.com",
    "sso_preference": "internal"
  }'

# Expected 201 Created with body:
# {"tenant_id":"<uuid>","slug":"acme-corp","status":"provisioning"}
```

Equivalent raw SQL (use only if API is down):

```sql
INSERT INTO public.tenants (tenant_id, slug, legal_name, billing_entity, plan, status, created_at)
VALUES (gen_random_uuid(), 'acme-corp', 'ACME Corporation, Inc.',
        'ACME Corporation, Inc.', 'growth', 'provisioning', now());
```

### Step 2 — `CREATE SCHEMA tenant_<slug>`

```sql
CREATE SCHEMA IF NOT EXISTS tenant_acme_corp
  AUTHORIZATION outrena_app;
GRANT USAGE ON SCHEMA tenant_acme_corp TO outrena_app;
GRANT CREATE ON SCHEMA tenant_acme_corp TO outrena_app;
```

> **⚠️ Warning:** Use `tenant_<slug>` with hyphens replaced by underscores. The slug
> `acme-corp` becomes schema `tenant_acme_corp`. Do not include the hyphen — Postgres
> will require quoting forever after.

### Step 3 — Alembic upgrade head with `TARGET_SCHEMA`

Run migrations against the new tenant schema only. The `TARGET_SCHEMA` env var is read
by `migrations/env.py` to scope `upgrade()` calls (see pitfall #3 in the migration doc).

```bash
export DATABASE_URL="postgresql://outrena_app:***@prod-rds.outrena.internal/outrena"
export TARGET_SCHEMA="tenant_acme_corp"

cd /srv/outrena
alembic upgrade head
# Expected: INFO  [alembic.runtime.migration] Running upgrade  -> 0001, -> 0002, ... -> <head>

# Verify
alembic current
# Expected: <head-rev> (head)
```

Verify the schema has all expected tables:

```bash
python scripts/verify_schema_health.py --schema tenant_acme_corp
# Expected: PASS — all tables present, all indexes present, row counts 0.
```

### Step 4 — Keycloak group + client creation via Admin API

```bash
# Create the group (1:1 with tenant).
GROUP_ID=$(curl -sS -X POST "https://auth.outrena.com/admin/realms/outrena/groups" \
  -H "Authorization: Bearer $KEYCLOAK_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"tenant-acme-corp"}' \
  -w '%{http_code}' -o /dev/null)

# Create the OIDC client for the tenant (used by their dashboard if SSO).
CLIENT_UUID=$(curl -sS -X POST "https://auth.outrena.com/admin/realms/outrena/clients" \
  -H "Authorization: Bearer $KEYCLOAK_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "tenant-acme-corp",
    "enabled": true,
    "protocol": "openid-connect",
    "publicClient": false,
    "secret": "'"$(openssl rand -hex 32)"'",
    "redirectUris": [],
    "webOrigins": []
  }' | jq -r '.id')

echo "GROUP_ID=$GROUP_ID  CLIENT_UUID=$CLIENT_UUID"
```

Persist the client secret to AWS Secrets Manager
(`/outrena/tenant-acme-corp/keycloak-client-secret`) and Azure Key Vault
(`kv-outrena-prod/tenant-acme-corp-keycloak-client-secret`) for dual-cloud parity.

### Step 5 — Register redirect URIs explicitly (pitfall #1)

Pitfall #1 from the migration doc: wildcard redirect URIs are forbidden. Each
redirect URI must be registered explicitly.

```bash
# Add the canonical dashboard redirect + the tenant's SSO callback if specified.
curl -sS -X PUT "https://auth.outrena.com/admin/realms/outrena/clients/$CLIENT_UUID" \
  -H "Authorization: Bearer $KEYCLOAK_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "redirectUris": [
      "https://acme-corp.outrena.com/auth/callback",
      "https://acme-corp.outrena.com/*"
    ],
    "webOrigins": [
      "https://acme-corp.outrena.com"
    ]
  }'
```

> **⚠️ Warning:** Never register `https://*.outrena.com/*` or any wildcard host.
> Each new tenant gets a distinct client with explicit URIs. Wildcard hosts allow
> one tenant's auth code to be replayed against another tenant's redirect.

### Step 6 — Warm cache

The first request after provisioning hits a cold cache; warm it explicitly so the
admin's first login is fast.

```bash
# Trigger the cache-warm endpoint (internal).
curl -sS -X POST "https://api.outrena.com/internal/tenants/acme-corp/warm-cache" \
  -H "Authorization: Bearer $PLATFORM_ADMIN_TOKEN"
# Expected: {"status":"warmed","keys":<n>}

# Or via the scheduler's manual tick:
python scripts/celery_manual_tick.py --task warm_tenant_cache --arg tenant_slug=acme-corp
```

### Step 7 — Flip tenant status to `active`

```sql
UPDATE public.tenants
SET status = 'active', activated_at = now()
WHERE slug = 'acme-corp';
```

## Verification

1. **Login as the new tenant admin.** Use the admin email from the intake form; an
   invite email was sent by Step 4's group-creation webhook.
2. Confirm the dashboard loads at `https://acme-corp.outrena.com/` with **no errors**
   in the browser console and **no 5xx** in the network tab.
3. Confirm the dashboard is **empty** (no sequences, no autopilot runs, no contacts).
   Non-empty state means you provisioned against the wrong schema — abort and
   investigate.
4. Confirm the admin user can create a contact and send a test sequence.
5. Confirm `verify_schema_health.py` still passes after the test:
   ```bash
   python scripts/verify_schema_health.py --schema tenant_acme_corp
   ```
6. Confirm the tenant appears in the tenant-isolation Grafana dashboard
   (`outrena-tenant-isolation`), with 0 cross-tenant 403s.

## Rollback (Partial Failures)

If any step fails, roll back the **completed** steps in reverse order. Each step below
assumes the named step succeeded.

### If Step 6 (warm cache) failed

No rollback needed — cache will warm on first user request. Re-run Step 6 once the
underlying cause (usually Redis connectivity) is fixed.

### If Step 5 (redirect URIs) failed

```bash
# No state to roll back; the client has no URIs yet. Fix and re-issue the PUT.
```

### If Step 4 (Keycloak) failed

```bash
# Delete the partially-created client and group.
curl -sS -X DELETE "https://auth.outrena.com/admin/realms/outrena/clients/$CLIENT_UUID" \
  -H "Authorization: Bearer $KEYCLOAK_ADMIN_TOKEN"
curl -sS -X DELETE "https://auth.outrena.com/admin/realms/outrena/groups/$GROUP_ID" \
  -H "Authorization: Bearer $KEYCLOAK_ADMIN_TOKEN"
```

Also delete the Secrets Manager + Key Vault entries created in Step 4.

### If Step 3 (Alembic) failed

```bash
export TARGET_SCHEMA="tenant_acme_corp"
alembic downgrade base
# Then drop the schema:
psql -c "DROP SCHEMA IF EXISTS tenant_acme_corp CASCADE;"
```

### If Step 2 (CREATE SCHEMA) failed

Already handled by the Step 3 rollback (`DROP SCHEMA`).

### If Step 1 (INSERT) failed

```sql
DELETE FROM public.tenants WHERE slug = 'acme-corp';
```

> **⚠️ Warning:** Only delete the row if **no** subsequent step succeeded. If a schema
> or Keycloak client exists, deleting the tenants row orphans them — the next
> provisioning attempt for the same slug will collide.

### Full rollback script

```bash
scripts/provision_tenant.py --slug acme-corp --rollback
# Performs steps 6→1 in reverse. Confirms each before proceeding. Idempotent.
```

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| Alembic upgrade fails with `target_metadata` mismatch | Platform eng lead | Immediately |
| Keycloak Admin API returns 5xx | SRE lead + page Keycloak vendor (Red Hat) if SEV-1 | After 2 retries |
| `CREATE SCHEMA` fails with permission denied | DBA / SRE lead | Immediately |
| Tenant slug conflict on insert | Customer success (request alternate slug) | Same business day |
| Verify health reports schema drift | SRE lead — possible tenant isolation issue | Immediately (Risk #17) |

### Keycloak Admin API failure — manual UI fallback

If `auth.outrena.com/admin/realms/outrena/*` API is returning 5xx but the admin UI is
up, complete Step 4 + Step 5 manually:

1. Log in to `https://auth.outrena.com/admin` (master realm admin).
2. Pick realm `outrena` from the dropdown.
3. Groups → New → name `tenant-acme-corp`.
4. Clients → Create → clientId `tenant-acme-corp`, protocol `openid-connect`, save.
5. Edit client → Valid Redirect URIs → add `https://acme-corp.outrena.com/auth/callback`
   and `https://acme-corp.outrena.com/*`. Save.
6. Credentials tab → regenerate secret → store in Secrets Manager + Key Vault.

Document the manual completion in the incident channel; file a follow-up Issue to
investigate the Admin API outage (likely a Keycloak pod restart or realm cache issue).
