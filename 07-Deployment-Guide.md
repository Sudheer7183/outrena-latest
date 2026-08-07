# 07 — Deployment Guide

> **OUTRENA v8** — Operational deployment manual for DevOps and SRE teams.
> Covers local development, AWS (ECS + RDS), Azure (App Service + Flexible Server),
> Kubernetes (Helm), Nginx + TLS, Keycloak, PostgreSQL multi-tenancy, PostHog,
> observability, CI/CD, security hardening, cutover, runbooks, DR, and cost optimization.

---

## 1. Introduction

This guide is the canonical reference for deploying, operating, and recovering
OUTRENA v8 across all supported environments. The primary audience is DevOps
and SRE engineers responsible for provisioning, upgrading, scaling, and
troubleshooting the platform. Secondary audiences include platform engineers
onboarding new tenants, security engineers performing audits, and DBAs running
the schema-per-tenant PostgreSQL cluster.

OUTRENA v8 is a multi-tenant SaaS outreach automation platform built as a
modular monolith. The backend is a FastAPI application, the worker tier is
Celery on Redis, the frontend is a static React + Vite bundle, identity is
Keycloak 24+, analytics is PostHog, and the database is PostgreSQL 16 with one
schema per tenant. Three production deployment targets are supported: AWS
(ECS Fargate + RDS + ElastiCache + ALB), Azure (App Service + Flexible Server +
Azure Cache + App Gateway), and any CNCF-conformant Kubernetes cluster
(Helm chart). All three targets share the same container images, the same
env-var contract, and the same observability stack.

The guide is organized to be read either end-to-end during initial platform
stand-up or section-by-section during operational incidents. Each operational
section ends with verification steps and rollback procedures. The runbook
chapter (§18) consolidates the 15 most common operational procedures into
single-page references.

---

## 2. Architecture Overview

OUTRENA is deployed as a stateless API tier, a stateless worker tier, a
singleton scheduler tier, a static frontend tier, and a stateful data tier.
The edge layer (Cloudflare) terminates user connections, applies WAF rules,
and caches static assets. Behind Cloudflare, a cloud load balancer (AWS ALB,
Azure App Gateway, or Kubernetes Ingress) routes traffic to Nginx, which in
turn routes to the FastAPI backend, the static frontend bundle, the Keycloak
auth server, and the PostHog analytics endpoint.

The data tier comprises PostgreSQL 16 (primary + 2 read replicas, Multi-AZ
or zone-redundant), Redis 7 (cluster mode for production, single-node for
staging), and object storage (S3 on AWS, Blob Storage on Azure). PostgreSQL
holds all relational tenant data in a schema-per-tenant layout under the
`public` platform schema. Redis holds JWKS cache, rate-limit counters, Celery
task queues, and hot application cache. Object storage holds email attachments,
campaign exports, PostHog event snapshots, and Terraform state.

Keycloak runs as its own container behind the same Nginx, with its own
PostgreSQL database (separate from the application database, or a separate
schema in the same cluster for staging). PostHog runs self-hosted via
`docker-compose.posthog.yml` on AWS (ECS) or Azure (Container Apps), or as a
cloud SaaS subscription. Celery workers consume from three Redis-backed queues
(`default`, `emails`, `llm`) and the scheduler service emits beat tasks every
minute.

```mermaid
flowchart LR
    User[End User Browser] --> CF[Cloudflare<br/>WAF + CDN + TLS]
    CF --> ALB{Cloud LB<br/>ALB / App Gateway / Ingress}
    ALB --> Nginx[Nginx<br/>TLS + Rate Limit + Routes]
    Nginx --> FE[Frontend<br/>Static Vite Bundle]
    Nginx --> API[Backend API<br/>FastAPI Container]
    Nginx --> KC[Keycloak<br/>Auth Container]
    Nginx --> PH[PostHog<br/>Analytics Container]
    API --> PG[(PostgreSQL 16<br/>Primary + 2 Replicas)]
    API --> Redis[(Redis 7<br/>Cache + Queue)]
    API --> S3[(S3 / Blob<br/>Object Storage)]
    API --> LLM[LLM Providers<br/>OpenAI / Anthropic / ...]
    Worker[Celery Worker] --> Redis
    Worker --> PG
    Worker --> LLM
    Worker --> MB[MailBridge<br/>SMTP Relay]
    Sched[Scheduler<br/>Celery Beat] --> Redis
    KC --> KCDB[(Keycloak DB)]
    PH --> PHDB[(PostHog DB)]
```

---

## 3. Prerequisites

Before deploying OUTRENA v8 the operator must hold valid accounts on the target
cloud provider(s), control a DNS zone capable of wildcard records, possess or
be able to issue TLS certificates for the apex and wildcard subdomains, and
have generated the cryptographic secrets listed in the secrets table below.

**Cloud accounts.** For AWS: an AWS account with permission to create VPCs,
ECS clusters, RDS instances, ElastiCache clusters, ALBs, ACM certificates,
Route 53 records, S3 buckets, Secrets Manager entries, IAM roles, and
CloudWatch alarms. For Azure: an Azure subscription with Contributor rights on
the target resource group and the ability to create App Services, PostgreSQL
Flexible Servers, Azure Cache for Redis, App Gateways, Key Vaults, Storage
Accounts, Managed Identities, and Log Analytics workspaces. For Kubernetes:
cluster-admin on a 1.27+ cluster with the Helm 3.12+ CLI installed locally.

**Domain and TLS.** A registered domain (e.g. `outrena.com`) with a DNS zone
hosted on Route 53 (AWS) or Azure DNS (Azure). Wildcard DNS records
(`*.outrena.com`) must be configurable to point at the load balancer. TLS
certificates are issued by AWS Certificate Manager (AWS), Azure Key Vault
managed certificates or Let's Encrypt (Azure), or cert-manager (Kubernetes).
Wildcard certificates covering `*.outrena.com` plus the apex are required
because tenant subdomains (`acme.outrena.com`, `globex.outrena.com`) are
issued dynamically.

**Secrets to generate.** All secrets below must be generated before the first
deploy. Store them in AWS Secrets Manager, Azure Key Vault, or Kubernetes
Secrets (sealed with Sealed Secrets / SOPS). Never commit secrets to Git.

| Secret | Length | Algorithm | Notes |
|---|---|---|---|
| `DATABASE_URL` | n/a | postgresql+asyncpg URI | Include user:pass@host:5432/db |
| `REDIS_URL` | n/a | redis:// URI | Include password for prod |
| `KEYCLOAK_CLIENT_SECRET` | 64 hex | random | Per-realm client secret |
| `FERNET_KEY` | 44 b64 | Fernet (AES-128-CBC + HMAC-SHA256) | `cryptography.fernet.Fernet.generate_key()` |
| `JWT_SECRET` | 64 hex | HS256 fallback only | Used if `SKIP_JWT_VERIFICATION=true` |
| `STRIPE_SECRET_KEY` | n/a | Stripe-issued | `sk_live_...` for prod |
| `STRIPE_WEBHOOK_SECRET` | n/a | Stripe-issued | `whsec_...` |
| `OPENAI_API_KEY` | n/a | OpenAI-issued | `sk-...` |
| `ANTHROPIC_API_KEY` | n/a | Anthropic-issued | `sk-ant-...` |
| `AZURE_OPENAI_API_KEY` | n/a | Azure-issued | Per-deployment key |
| `AWS_SECRET_ACCESS_KEY` | n/a | AWS IAM | Used by Secrets Manager backend |
| `MAILBRIDGE_API_KEY` | n/a | MailBridge-issued | SMTP relay auth |

**Tooling.** Each operator workstation must have the following CLIs installed
and authenticated. Versions listed are the minimum supported.

| Tool | Min Version | Purpose |
|---|---|---|
| `docker` | 24.0 | Build + run containers locally |
| `docker compose` | 2.20 | Local dev stack orchestration |
| `kubectl` | 1.27 | Kubernetes deployment |
| `helm` | 3.12 | Helm chart install/upgrade |
| `terraform` | 1.6 | AWS + Azure infra provisioning |
| `aws-cli` | 2.13 | AWS API + ECR push |
| `az-cli` | 2.50 | Azure API + ACR push |
| `psql` | 16 | DB inspection + migrations |
| `redis-cli` | 7.2 | Cache inspection |
| `jq` | 1.7 | JSON parsing in scripts |
| `gh` | 2.30 | GitHub Actions dispatch |
| `k6` | 0.47 | Load testing |

---

## 4. Local Development Deployment

The local stack is defined in `docker-compose.yml` at the repository root. It
spins up PostgreSQL 16, Redis 7.2, Keycloak 24, the FastAPI backend, the Vite
frontend dev server, and (in Phase 8) Prometheus + Grafana for local
observability. The worker tier is launched as a separate compose profile.

**First run.** Clone the repository, copy the env templates, and bring up the
stack:

```bash
git clone git@github.com:outrena/outrena.git
cd outrena

# Backend env (contains DATABASE_URL, REDIS_URL, Keycloak, LLM keys)
cp outrena-backend/.env.example outrena-backend/.env

# Frontend env (Vite vars — public, never secret)
cp outrena-frontend/.env.example outrena-frontend/.env

# Bring up the 5-service stack
docker compose up -d

# Wait for healthchecks
docker compose ps
# NAME                  STATUS                   PORTS
# outrena-postgres      Up (healthy)             0.0.0.0:5432->5432/tcp
# outrena-redis         Up (healthy)             0.0.0.0:6379->6379/tcp
# outrena-keycloak      Up (healthy)             0.0.0.0:8080->8080/tcp
# outrena-backend       Up (healthy)             0.0.0.0:8000->8000/tcp
# outrena-frontend      Up (healthy)             0.0.0.0:5173->5173/tcp

# Apply DB migrations
docker compose exec backend alembic upgrade head

# Verify
curl -s http://localhost:8000/health | jq
# { "status": "ok", "version": "8.0.0", "tenant": null }
```

To start the Celery worker and beat scheduler locally, use the worker profile:

```bash
docker compose --profile worker up -d worker beat
```

**Local port map.**

| Service | Container Port | Host Port | URL |
|---|---|---|---|
| PostgreSQL | 5432 | 5432 | `postgresql://outrena:outrena_dev@localhost:5432/outrena` |
| Redis | 6379 | 6379 | `redis://localhost:6379/0` |
| Keycloak | 8080 | 8080 | `http://localhost:8080` (admin/admin) |
| Backend API | 8000 | 8000 | `http://localhost:8000` |
| Frontend (Vite) | 5173 | 5173 | `http://localhost:5173` |
| Prometheus (Phase 8) | 9090 | 9090 | `http://localhost:9090` |
| Grafana (Phase 8) | 3000 | 3000 | `http://localhost:3000` (admin/admin) |

**Teardown.** `docker compose down` removes containers but preserves named
volumes (`pgdata`, `redisdata`). `docker compose down -v` wipes all data — use
only when resetting the dev environment.

---

## 4a. Keycloak Admin Access and Super Admin Onboarding

> This section covers the three most common issues encountered during local
> development: Keycloak failing to start, the dev-bypass auth mode, and how
> to reach the Platform Admin console as a super admin.

### 4a.1 Why Keycloak Exits with Code 1 (and how to fix it)

Keycloak 24 in `start-dev` mode connects to PostgreSQL before the application
does. Two root causes are common in local Docker Compose:

**Cause A — Postgres not yet accepting connections when Keycloak connects.**

The `depends_on: service_started` condition did not guarantee Postgres was
fully accepting connections. The fix is `condition: service_healthy`, which
waits until the Postgres healthcheck (`pg_isready`) passes before Keycloak
starts. This is now the default in `docker-compose.yml`.

**Cause B — Keycloak schema collision with application tables.**

When both the application and Keycloak share the `outrena` Postgres database,
Keycloak's Liquibase migrations can conflict with existing application tables
if they are both placed in the default `public` schema. The fix is
`KC_DB_SCHEMA: keycloak`, which isolates all Keycloak tables under a dedicated
`keycloak` schema in the same database.

**Diagnosis steps:**

```bash
# 1. Check if the container is running or exiting
docker ps -a | grep keycloak

# 2. Pull the last 50 log lines
docker logs outrena-keycloak --tail 50

# Common error patterns and their causes:
#   "Unable to connect to database" → Postgres not ready (Cause A)
#   "Failed to obtain JDBC connection" → Postgres not ready (Cause A)
#   "Failed to update the database" → Schema conflict (Cause B)
#   "Address already in use: 8080" → Port conflict on host

# 3. Force-restart with fresh schema (wipes all Keycloak data)
docker compose down keycloak
docker compose run --rm postgres psql -U outrena -c "DROP SCHEMA IF EXISTS keycloak CASCADE;"
docker compose up -d keycloak

# 4. Wait for healthy and verify
docker compose ps keycloak   # should show "Up (healthy)"
curl -s http://localhost:8080/realms/outrena/.well-known/openid-configuration | jq .issuer
```

**Port conflict check:**

```bash
# Confirm 8080 is not already in use on the host
netstat -tlnp | grep 8080
# OR on Windows/WSL2:
netstat -ano | findstr :8080
# If occupied, either stop the conflicting process or change Keycloak's port:
# In docker-compose.yml, change "8080:8080" to "8081:8080" and update
# KEYCLOAK_BASE_URL in the backend environment to http://keycloak:8080 (internal unchanged).
```

### 4a.2 Dev-Bypass Mode vs Real Keycloak Login

The local stack ships with two authentication modes:

| Mode | `SKIP_JWT_VERIFICATION` | `VITE_DEV_BYPASS_AUTH` | Result |
|------|------------------------|------------------------|--------|
| **Dev-bypass** (default) | `true` | `true` | Frontend injects `"dev-token"`, backend synthesises `SUPER_ADMIN` identity. No Keycloak required. All features accessible instantly. |
| **Real Keycloak** | `false` | `false` | Keycloak must be running and healthy. Login form shows. JWT verified with JWKS. |

**Dev-bypass mode** is the default because it lets developers work without
waiting for Keycloak to start. When the frontend is built with
`VITE_DEV_BYPASS_AUTH=true`, the login page shows "Continue as dev user" and
clicking it injects a `"dev-token"` Bearer header on every API call. The
backend, seeing `SKIP_JWT_VERIFICATION=true`, recognises `"dev-token"` and
returns a synthetic `SUPER_ADMIN` payload with `tenant_slug=acme`.

This means **in dev-bypass mode you land directly in the app as a super admin
— this is intentional**. The Platform Admin nav item is visible in the sidebar
and `/platform-admin` is accessible without any login step.

**To switch to real Keycloak login**, use the provided override file:

```bash
# Start (or restart) the stack with real Keycloak auth
docker compose -f docker-compose.yml -f docker-compose.auth-off.yml up -d --build

# This:
# 1. Sets SKIP_JWT_VERIFICATION=false in the backend
# 2. Rebuilds the frontend with VITE_DEV_BYPASS_AUTH=false
# 3. The login page now shows "Sign in with SSO" → redirects to Keycloak
```

### 4a.3 Keycloak Admin Console Access

The Keycloak admin console is at `http://localhost:8080/admin`.

Credentials: `admin` / `admin` (set by `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD`
in `docker-compose.yml`).

If the admin console is unreachable:

```bash
# 1. Confirm the container is healthy
docker compose ps keycloak

# 2. Confirm the port is mapped
docker inspect outrena-keycloak | grep -A 5 HostPort

# 3. Try the health endpoint directly
curl -v http://localhost:8080/health/ready
```

### 4a.4 The Platform Admin Console (Super Admin UI)

The Platform Admin console lives at `http://localhost:3080/platform-admin`
(when the frontend is running). It is a separate layout from the main app,
accessible only to users with the `SUPER_ADMIN` role.

**In dev-bypass mode** (default), the synthetic `SUPER_ADMIN` identity means
the "Platform" section is already visible in the sidebar when you open the app.
Click "Platform Admin" to enter the console.

**In real-Keycloak mode**, log in as:

| Account | Password | Role | Access |
|---------|----------|------|--------|
| `superadmin@outrena.com` | `admin123` | `SUPER_ADMIN` | Platform Admin console + all tenant pages |
| `admin@acme.com` | `admin123` | `TENANT_ADMIN` | Acme tenant admin pages only |
| `manager@acme.com` | `admin123` | `MANAGER` | Acme manager pages only |
| `rep@acme.com` | `admin123` | `REP` | Acme rep pages only |
| `admin@globex.com` | `admin123` | `TENANT_ADMIN` | Globex tenant admin pages only |

These accounts are seeded by `outrena-backend/keycloak/realm-export.json`
which is auto-imported when Keycloak starts with `--import-realm`.

> **Change passwords before going to production.** The realm-export seeds
> temporary passwords; `"temporary": false` is set for convenience in dev but
> should be `true` in a production realm export.

### 4a.5 Creating a New Tenant (Super Admin Flow)

The end-to-end flow for provisioning a new tenant from the UI:

1. Navigate to `http://localhost:3080/platform-admin/tenants`
   (or log in as `superadmin@outrena.com` in real-Keycloak mode).

2. Click **Create Tenant** (top-right).

3. Fill in the form:
   - **Slug** — URL-safe identifier, 3–32 chars, lowercase + hyphens.
     E.g. `northbeam` → tenant accessible at `northbeam.localhost`.
   - **Company name** — Display name shown in the UI.
   - **Admin email** — A Keycloak user with `TENANT_ADMIN` role is created for
     this address.
   - **Admin first/last name** — Keycloak display name.
   - **Temporary password** — If blank, Keycloak generates a reset token and
     the admin must set their password on first login.

4. Click **Create tenant**. The backend runs:
   - `CREATE SCHEMA "{slug}"` in PostgreSQL
   - Alembic migrations against the new schema
   - Seed data (prompt templates, system params, feature permissions)
   - Keycloak user creation with `TENANT_ADMIN` role and `tenant_slug` attribute

5. The new tenant appears in the Tenants table with status `ACTIVE`.

**Equivalent cURL (for automation/CI):**

```bash
# Get a SUPER_ADMIN token (real-Keycloak mode)
TOKEN=$(curl -s -X POST http://localhost:8080/realms/outrena/protocol/openid-connect/token \
  -d "client_id=frontend" \
  -d "username=superadmin@outrena.com" \
  -d "password=admin123" \
  -d "grant_type=password" | jq -r .access_token)

# Provision the tenant
curl -s -X POST http://localhost:8000/api/platform/tenants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "northbeam",
    "name": "Northbeam Corp",
    "admin_email": "admin@northbeam.com",
    "admin_first_name": "Jane",
    "admin_last_name": "Smith",
    "send_invitation": true
  }' | jq
# { "slug": "northbeam", "status": "ACTIVE", "url": "http://northbeam.localhost" }
```

> **Dev-bypass note:** In `SKIP_JWT_VERIFICATION=true` mode, the `"dev-token"`
> header is accepted for the above cURL call too. Replace the
> `Authorization: Bearer $TOKEN` with `Authorization: Bearer dev-token`.

### 4a.6 Platform API Path Reference

All platform-admin API calls use the `/api/platform/` prefix and are proxied
by nginx from the frontend container directly to the backend:

```
Frontend → nginx /api/ → backend:8000

Base URL: http://localhost:8000

GET  /api/platform/tenants                  List tenants (public schema)
POST /api/platform/tenants                  Provision new tenant (SUPER_ADMIN)
GET  /api/platform/tenants/{id}             Fetch one tenant
POST /api/platform/tenants/{id}/suspend     Suspend tenant
POST /api/platform/tenants/{id}/reactivate  Reactivate tenant
GET  /api/platform/admin/tenants            List with metrics + plan/seat data
GET  /api/platform/admin/signups            List signup requests
POST /api/platform/admin/signups/{id}/approve  Approve + provision
POST /api/platform/admin/signups/{id}/reject   Reject
GET  /api/platform/admin/metrics            Platform KPIs (MRR, churn, etc.)
GET  /api/platform/admin/audit-logs         Cross-tenant audit log
GET  /api/platform/admin/llm-configs        Global LLM configs
POST /api/platform/admin/llm-configs        Create global LLM config
```

All endpoints require `SUPER_ADMIN` role. In dev-bypass mode, `dev-token`
satisfies the auth check.


---

## 5. Container Images

OUTRENA ships three production container images, all based on `python:3.12-slim`
(backend, worker) and `node:20-alpine` (frontend build) → `nginx:1.25-alpine`
(frontend serve). Images are multi-arch (amd64, arm64) and tagged with the Git
SHA plus the semantic version. The worker image is identical to the backend
image — the entrypoint differs.

### 5.1 Backend Dockerfile

```dockerfile
# outrena-backend/Dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --upgrade pip && pip install uv && uv sync --frozen --no-dev
COPY . .
RUN useradd -m -u 10001 outrena && chown -R outrena:outrena /app
USER outrena
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

### 5.2 Frontend Dockerfile (multi-stage)

```dockerfile
# outrena-frontend/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
ARG VITE_API_BASE_URL VITE_KEYCLOAK_URL VITE_KEYCLOAK_REALM VITE_KEYCLOAK_CLIENT_ID
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL \
    VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID
RUN pnpm build

FROM nginx:1.25-alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD wget -qO- http://localhost/healthz || exit 1
```

### 5.3 Worker Dockerfile

```dockerfile
# outrena-worker/Dockerfile (same base as backend)
FROM outrena-backend:latest
USER outrena
# Override entrypoint to launch Celery worker instead of uvicorn
CMD ["celery", "-A", "app.worker.celery_app", "worker", \
     "--loglevel=info", "--concurrency=8", \
     "-Q", "default,emails,llm", "--without-gossip", "--without-mingle"]
```

### 5.4 Build and Push

```bash
# Set once per shell
export REGISTRY=ghcr.io/outrena
export VERSION=8.0.0
export SHA=$(git rev-parse --short HEAD)

# Multi-arch build (requires buildx)
docker buildx build --platform linux/amd64,linux/arm64 \
  -t $REGISTRY/outrena-backend:$VERSION \
  -t $REGISTRY/outrena-backend:$SHA \
  -f outrena-backend/Dockerfile --push outrena-backend/

docker buildx build --platform linux/amd64,linux/arm64 \
  -t $REGISTRY/outrena-frontend:$VERSION \
  -t $REGISTRY/outrena-frontend:$SHA \
  --build-arg VITE_API_BASE_URL=https://api.outrena.com \
  --build-arg VITE_KEYCLOAK_URL=https://auth.outrena.com \
  --build-arg VITE_KEYCLOAK_REALM=outrena \
  --build-arg VITE_KEYCLOAK_CLIENT_ID=frontend \
  -f outrena-frontend/Dockerfile --push outrena-frontend/

# Worker reuses the backend image — re-tag only
docker tag $REGISTRY/outrena-backend:$VERSION $REGISTRY/outrena-worker:$VERSION
docker push $REGISTRY/outrena-worker:$VERSION
```

On AWS, replace `ghcr.io/outrena` with the ECR registry URI
(`<acct>.dkr.ecr.<region>.amazonaws.com/outrena/...`). On Azure, use the ACR
login server (`outrena.azurecr.io/...`). Both are provisioned by Terraform
(`terraform/aws/ecr.tf`, `terraform/azure/acr.tf`).

---

## 6. AWS Deployment

AWS is the primary production target. All infrastructure is codified in
Terraform under `terraform/aws/`. The stack runs on ECS Fargate for the API,
worker, scheduler, frontend, Keycloak, and PostHog services; RDS PostgreSQL 16
Multi-AZ for the application database; ElastiCache Redis cluster mode for
cache and queue; ALB for L7 load balancing with ACM-terminated TLS; and
CloudWatch for logs, metrics, and alarms.

```mermaid
flowchart TB
    subgraph Edge
        CF[Cloudflare<br/>DNS + WAF]
    end
    subgraph VPC[VPC — 3 AZs]
        ALB[ALB :443<br/>ACM TLS]
        subgraph ECS[ECS Fargate Cluster]
            API[Backend Service<br/>4 tasks min]
            WK[Worker Service<br/>8 tasks]
            SCH[Scheduler<br/>1 task — singleton]
            FE[Frontend<br/>Nginx 2 tasks]
            KC[Keycloak<br/>2 tasks]
            PH[PostHog<br/>3 tasks]
        end
        subgraph Data
            RDS[(RDS PostgreSQL 16<br/>db.r6g.xlarge<br/>Primary + Standby)]
            EC[(ElastiCache Redis 7<br/>cluster mode<br/>3 shards × 1 replica)]
            S3[(S3 Buckets<br/>exports, attachments, tfstate)]
        end
    end
    CF --> ALB
    ALB --> FE
    ALB --> API
    ALB --> KC
    ALB --> PH
    API --> RDS
    API --> EC
    API --> S3
    WK --> EC
    WK --> RDS
    SCH --> EC
    KC --> RDS
    PH --> RDS
    PH --> S3
```

### 6.1 Terraform Layout

The Terraform root module is `terraform/aws/`. Per-environment variable files
live in `terraform/aws/envs/` (`dev.tfvars`, `staging.tfvars`, `prod.tfvars`).
The module provisions: VPC with 3 AZs (`vpc.tf`), public + private subnets,
NAT gateways, security groups (`security_groups.tf`), ALB + listeners + target
groups (`alb.tf`), ACM certificate + Route 53 validation (`acm.tf`,
`route53.tf`), ECR repositories (`ecr.tf`), ECS cluster + service definitions
(`ecs.tf`, `ecs_backend.tf`, `ecs_frontend.tf`, `ecs_worker.tf`,
`ecs_keycloak.tf`), RDS PostgreSQL instance + parameter group + subnet group
(`rds.tf`), ElastiCache Redis cluster + subnet group (`elasticache.tf`), S3
buckets with lifecycle policies (`s3.tf`), Secrets Manager secrets + rotation
Lambdas (`secrets.tf`, `secrets_rotation.tf`), CloudWatch log groups + alarms
+ dashboards (`cloudwatch.tf`), CloudTrail (`cloudtrail.tf`), IAM roles +
policies (`iam.tf`), budgets (`budgets.tf`), and PostHog ECS service
(`posthog.tf`).

### 6.2 Provisioning

```bash
cd terraform/aws

# One-time per environment: configure backend
terraform init -backend-config="envs/backend-prod.hcl"

# Plan against prod
terraform plan -var-file=envs/prod.tfvars -out=tfplan-prod

# Apply
terraform apply tfplan-prod

# Outputs include: rds_endpoint, redis_primary_endpoint, alb_dns_name,
# ecr_repository_urls, ecs_cluster_name, cloudwatch_log_group
terraform output
```

Key variables in `prod.tfvars`:

```hcl
environment              = "prod"
aws_region               = "us-east-1"
base_domain              = "outrena.com"
rds_instance_class       = "db.r6g.xlarge"
rds_multi_az             = true
rds_storage_gb           = 500
redis_node_type          = "cache.r6g.large"
redis_cluster_size       = 3
ecs_backend_desired      = 4
ecs_backend_min          = 4
ecs_backend_max          = 20
ecs_worker_desired       = 8
ecs_worker_min           = 4
ecs_worker_max           = 32
keycloak_db_instance_class = "db.m6g.large"
enable_cloudtrail        = true
enable_secrets_rotation  = true
log_retention_days       = 90
```

### 6.3 RDS PostgreSQL

The RDS instance runs PostgreSQL 16 with Multi-AZ enabled. Instance class
`db.r6g.xlarge` (4 vCPU, 32 GB RAM) supports the target load of 1,000 tenants
and 10,000 concurrent users. Storage starts at 500 GB gp3 with autoscaling
enabled up to 2 TB. Automated backups run daily at 03:00 UTC with a 14-day
retention; point-in-time recovery is enabled to the last 5 minutes. Two read
replicas in different AZs serve read-heavy analytics queries.

The DB parameter group sets `max_connections=960`, `shared_buffers=8GB`,
`effective_cache_size=24GB`, `work_mem=64MB`, `maintenance_work_mem=512MB`,
`wal_level=logical` (for future CDC), `log_min_duration_statement=500` (slow
query logging), and `random_page_cost=1.1` (tuned for gp3).

### 6.4 ElastiCache Redis

Redis runs in cluster mode with 3 shards × 1 replica each (6 nodes total) on
`cache.r6g.large`. TLS is enforced in-transit (`transit_encryption_enabled=true`)
and at-rest (`at_rest_encryption_enabled=true`). AUTH token stored in Secrets
Manager. Automatic failover is enabled with a 60-second node timeout. The
cluster exposes the configuration endpoint which the backend uses to discover
shard topology.

### 6.5 ALB + TLS

The ALB listens on 443 with an ACM-issued wildcard certificate for
`*.outrena.com`. HTTP :80 redirects to :443. Listener rules route by host:

| Host pattern | Target Group |
|---|---|
| `outrena.com`, `www.outrena.com` | `tg-frontend` |
| `api.outrena.com` | `tg-backend` |
| `auth.outrena.com` | `tg-keycloak` |
| `app.outrena.com` (tenant subdomains) | `tg-frontend` (multi-tenant via Host header) |
| `*.outrena.com` (tenant subdomains) | `tg-frontend` |
| `analytics.outrena.com` | `tg-posthog` |

Health checks hit `/health` (backend, frontend Nginx), `/healthz` (Keycloak),
and `/_health` (PostHog). Deregistration delay is 60 seconds to drain in-flight
requests. Access logs ship to S3 with 90-day retention.

### 6.6 ECS Services

All ECS services run on Fargate with platform version 1.4. Task sizes:

| Service | CPU | Memory | Desired | Min | Max |
|---|---|---|---|---|---|
| Backend | 1024 | 2048 | 4 | 4 | 20 |
| Worker | 2048 | 4096 | 8 | 4 | 32 |
| Scheduler | 512 | 1024 | 1 | 1 | 1 |
| Frontend | 256 | 512 | 2 | 2 | 4 |
| Keycloak | 1024 | 2048 | 2 | 2 | 4 |
| PostHog | 1024 | 4096 | 3 | 2 | 6 |

Task definitions reference secrets via ARN — never inline. The backend task
(`ecs-task-definitions/backend.json`) injects `DATABASE_URL`, `REDIS_URL`,
`KEYCLOAK_CLIENT_SECRET`, `FERNET_KEY`, `JWT_SECRET`, `STRIPE_SECRET_KEY`,
`OPENAI_API_KEY`, and other LLM keys from Secrets Manager using the
`secrets` block with `valueFrom` ARNs.

Auto-scaling is target-tracking on the ALB `RequestCountPerTarget` (backend:
1000 req/target), CPU utilization (worker: 70%), and SQS-equivalent queue
depth via CloudWatch custom metric `celery_queue_depth` (worker: scale at 500).

### 6.7 CloudWatch

All containers ship stdout/stderr to CloudWatch Logs under
`/outrena/prod/{service}`. Log retention is 90 days. Metric filters extract
HTTP 5xx rate, Celery task failure rate, and database connection saturation.
Alarms page the on-call SRE via SNS → PagerDuty when:

- `5xx_rate > 1%` for 5 minutes (backend)
- `celery_task_failure_rate > 5%` for 10 minutes (worker)
- `database_connections > 800` for 5 minutes
- `redis_evicted_keys > 100000` for 5 minutes
- `target_response_time_p99 > 2s` for 5 minutes (ALB)

CloudWatch dashboards render the four golden signals (latency, traffic,
errors, saturation) per service plus a multi-tenant resource utilization panel.

### 6.8 Deploy to ECS

```bash
# Build + push images (see §5.4)
export VERSION=8.0.1

# Update ECS task definition with new image tag
aws ecs describe-task-definition --task-definition outrena-backend-prod \
  --query taskDefinition > /tmp/backend-task.json
# Strip fields ECS rejects, update image, register new revision
jq '.containerDefinitions[0].image |= "ghcr.io/outrena/outrena-backend:'"$VERSION"'"' \
   /tmp/backend-task.json | \
jq 'del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)' | \
aws ecs register-task-definition --cli-input-json file:///dev/stdin

# Update service to new task definition
aws ecs update-service --cluster outrena-prod --service outrena-backend-prod \
  --task-definition outrena-backend-prod:$(aws ecs list-task-definitions \
    --family-prefix outrena-backend-prod --sort DESC --max-items 1 \
    --query 'taskDefinitionArns[0]' --output text | cut -d: -f7)

# Wait for steady state
aws ecs wait services-stable --cluster outrena-prod --services outrena-backend-prod
```

The CI/CD pipeline (§14) automates all of the above.

---

## 7. Azure Deployment

Azure is the secondary production target. Infrastructure lives in
`terraform/azure/`. The stack runs on App Service (P1v3 for API, frontend,
Keycloak; separate plan for PostHog), PostgreSQL Flexible Server (zone
redundant), Azure Cache for Redis (Premium tier with clustering), Application
Gateway with WAF v2, Azure Monitor + Log Analytics, Key Vault for secrets,
and Managed Identities for secret access.

```mermaid
flowchart TB
    subgraph Edge
        CF[Cloudflare<br/>DNS + CDN]
    end
    subgraph RG[Resource Group — 3 AZs]
        AGW[App Gateway WAF v2<br/>TLS terminate]
        subgraph AppService[App Service Plan P1v3]
            API[Backend App<br/>4 instances]
            FE[Frontend App<br/>2 instances]
            KC[Keycloak App<br/>2 instances]
            PH[PostHog App<br/>3 instances]
            WK[Worker<br/>Container Apps 8 replicas]
        end
        subgraph Data
            PG[(PostgreSQL Flexible<br/>GP_Standard_D8ds_v5<br/>Zone-redundant HA)]
            RC[(Azure Cache for Redis<br/>Premium P2<br/>3 shards cluster)]
            ST[(Storage Account<br/>Blob + Tables)]
        end
        KV[Key Vault]
    end
    CF --> AGW
    AGW --> FE
    AGW --> API
    AGW --> KC
    AGW --> PH
    API --> PG
    API --> RC
    API --> ST
    API --> KV
    WK --> RC
    WK --> PG
```

### 7.1 Terraform Layout

Per-environment tfvars live in `terraform/azure/envs/`. Modules provision:
resource group + 3-AZ VNet + subnets (`network.tf`, `nsg.tf`), App Gateway
with WAF + listeners + backend pools (`app_gateway.tf`), App Service plan +
Linux web apps (`container_apps.tf`, `container_apps_env.tf`), PostgreSQL
Flexible Server + firewall rules + active directory admin (`postgres.tf`),
Azure Cache for Redis (`redis.tf`), Storage Account + containers + lifecycle
(`storage.tf`), Key Vault + access policies + rotation
(`key_vault.tf`, `key_vault_rotation.tf`), Managed Identities
(`managed_identities.tf`), Azure DNS zone + records (`dns.tf`), Azure Monitor
+ Log Analytics workspace + alert rules (`monitoring.tf`, `log_alerts.tf`,
`activity_log.tf`), ACR (`acr.tf`), cost alerts (`cost_alerts.tf`), PostHog
App Service (`posthog.tf`).

### 7.2 Provisioning

```bash
cd terraform/azure
az login
az account set --subscription <prod-subscription-id>

terraform init -backend-config="envs/backend-prod.hcl"
terraform plan -var-file=envs/prod.tfvars -out=tfplan-prod
terraform apply tfplan-prod

# Outputs: postgres_fqdn, redis_hostname, app_gateway_fqdn,
#          storage_account_name, key_vault_uri, acr_login_server
terraform output
```

### 7.3 App Service Configuration

The backend App Service runs the container image from ACR with auto-scaling
enabled (4 to 20 instances based on CPU > 70%). Application settings
(environment variables) reference Key Vault secrets via Key Vault references:
`@Microsoft.KeyVault(VaultName=outrena-prod;SecretName=DatabaseUrl)`. The App
Service uses a system-assigned managed identity granted
`Key Vault Secrets User` on the vault — no secrets in plain text anywhere.

Worker tier runs on Azure Container Apps with KEDA scaling on Redis queue
length. The scheduler is a single-replica Container App with a fixed schedule.
Frontend runs as a separate App Service serving the static bundle from Nginx.

### 7.4 PostgreSQL Flexible Server

PostgreSQL 16 on `GP_Standard_D8ds_v5` (8 vCPU, 32 GB RAM) with 512 GB premium
SSD. Zone-redundant high availability is enabled (synchronous standby in
a different availability zone, automatic failover). Automated backups run with
35-day retention; point-in-time recovery covers the full retention window.
Two read replicas serve analytics. Server parameters mirror the AWS RDS
parameter group.

Firewall rules allow traffic only from the App Service subnet. Private
endpoint is provisioned so the FQDN resolves to a private IP inside the VNet.

### 7.5 Azure Cache for Redis

Premium tier P2 (cluster of 3 shards, 13 GB total). TLS enforced. Persistence
enabled (RDB every 60 minutes if ≥1 key changed). The cache uses a private
endpoint so traffic never leaves the VNet. AUTH key stored in Key Vault.

### 7.6 Application Gateway + WAF

Application Gateway v2 with WAF enabled in Prevention mode using OWASP 3.2
rule set. Listener :443 with a wildcard TLS certificate stored in Key Vault.
HTTP :80 redirects to :443. Path-based rules route:

| Host | Backend Pool |
|---|---|
| `outrena.com`, `www.outrena.com` | `bp-frontend` |
| `api.outrena.com` | `bp-backend` |
| `auth.outrena.com` | `bp-keycloak` |
| `analytics.outrena.com` | `bp-posthog` |
| `*.outrena.com` | `bp-frontend` (multi-tenant) |

Custom WAF rules block SQLi patterns, deny requests from non-OUTRENA
geographies if geo-fencing is enabled, and rate-limit by client IP
(100 req/s per IP sustained).

### 7.7 Azure Monitor

Diagnostic settings on all resources ship to a Log Analytics workspace.
Kusto queries power the operational dashboards. Alert rules page on-call when:

- `AppServiceHttp5xx > 1%` over 5 minutes
- `PostgreSqlCPU > 80%` over 10 minutes
- `RedisEvictedKeys > 100000` over 5 minutes
- `AppGatewayFailedRequests > 5%` over 5 minutes

Activity logs are exported to the Storage Account with 365-day retention for
compliance audits.

---

## 8. Kubernetes Deployment

For operators running OUTRENA on a self-managed or cloud-managed Kubernetes
cluster (EKS, AKS, GKE, or on-prem), the Helm chart at `k8s/outrena/`
provides a complete deployment. The chart supports three value files:
`values-dev.yaml`, `values-staging.yaml`, `values-prod.yaml`.

### 8.1 Helm Chart Structure

```
k8s/outrena/
├── Chart.yaml
├── values.yaml              # base defaults
├── values-dev.yaml
├── values-staging.yaml
├── values-prod.yaml
└── templates/
    ├── backend-deployment.yaml
    ├── backend-hpa.yaml
    ├── backend-service.yaml
    ├── worker-deployment.yaml
    ├── worker-hpa.yaml
    ├── scheduler-deployment.yaml
    ├── frontend-deployment.yaml
    ├── frontend-service.yaml
    ├── keycloak-statefulset.yaml
    ├── posthog-statefulset.yaml
    ├── postgres-statefulset.yaml     # optional — use managed DB in prod
    ├── redis-statefulset.yaml        # optional — use managed cache in prod
    ├── ingress.yaml
    ├── networkpolicy.yaml
    ├── poddisruptionbudget.yaml
    ├── secret.yaml                   # sealed-secrets / external-secrets
    └── serviceaccount.yaml
```

### 8.2 Install

```bash
# Add Bitnami for Redis + PostgreSQL subcharts if needed
helm repo add bitnami https://charts.bitnami.com/bitnami
helm dependency update k8s/outrena/

# Create namespace
kubectl create namespace outrena-prod

# Install external-secrets (recommended) or sealed-secrets
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system --create-namespace

# Install the chart
helm install outrena k8s/outrena/ \
  -n outrena-prod \
  -f k8s/outrena/values-prod.yaml \
  --set image.tag=8.0.1 \
  --set ingress.hostname=api.outrena.com

# Verify
kubectl -n outrena-prod get pods
kubectl -n outrena-prod get ingress
```

### 8.3 Key values

```yaml
# values-prod.yaml (excerpt)
image:
  repository: ghcr.io/outrena
  tag: 8.0.1
  pullPolicy: IfNotPresent

backend:
  replicas: 4
  resources:
    requests: { cpu: 500m, memory: 1Gi }
    limits:   { cpu: 1000m, memory: 2Gi }
  hpa:
    minReplicas: 4
    maxReplicas: 20
    targetCPUUtilizationPercentage: 70

worker:
  replicas: 8
  queues: [default, emails, llm]
  concurrency: 8
  hpa:
    minReplicas: 4
    maxReplicas: 32

ingress:
  className: nginx
  hostname: api.outrena.com
  tls:
    enabled: true
    certManager:
      issuer: letsencrypt-prod

postgresql:
  enabled: false  # use cloud-managed RDS / Flexible Server in prod
  external:
    host: prod-db.outrena.internal
    database: outrena

redis:
  enabled: false
  external:
    host: prod-redis.outrena.internal

keycloak:
  replicas: 2
  database:
    host: prod-keycloak-db.outrena.internal

observability:
  otelCollector:
    enabled: true
    exporter:
      tempo: tempo.observability.svc:4317
      loki: loki.observability.svc:3100
```

### 8.4 Rollout

```bash
# Upgrade
helm upgrade outrena k8s/outrena/ -n outrena-prod \
  -f k8s/outrena/values-prod.yaml --set image.tag=8.0.2

# Watch the rollout
kubectl -n outrena-prod rollout status deployment/outrena-backend

# Rollback to previous revision
helm rollback outrena 5 -n outrena-prod
```

---

## 9. Nginx + TLS Configuration

Nginx sits between the cloud load balancer and the application containers. It
terminates TLS (when the LB passes TCP), enforces rate limits, applies
security headers, serves the frontend static bundle, and reverse-proxies to
the backend, Keycloak, and PostHog. The full `nginx.conf` below is what ships
in the frontend image and what gets deployed to the Nginx ingress tier on
bare-metal / Kubernetes.

```nginx
# nginx/nginx.conf — OUTRENA edge configuration
user nginx;
worker_processes auto;
worker_rlimit_nofile 65535;
pid /var/run/nginx.pid;

events {
    worker_connections 8192;
    multi_accept on;
    use epoll;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format json escape=json
        '{"time":"$time_iso8601","remote_addr":"$remote_addr",'
        '"request":"$request","status":$status,"bytes":$body_bytes_sent,'
        '"request_time":$request_time,"upstream_time":"$upstream_response_time",'
        '"host":"$host","tenant":"$http_x_outrena_tenant",'
        '"user_agent":"$http_user_agent","request_id":"$request_id"}';
    access_log /var/log/nginx/access.log json;
    error_log  /var/log/nginx/error.log warn;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    server_tokens off;
    client_max_body_size 25m;
    types_hash_max_size 2048;

    # ── Rate limiting zones ────────────────────────────────────────────────
    limit_req_zone $binary_remote_addr zone=api:10m     rate=30r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m    rate=5r/s;
    limit_req_zone $binary_remote_addr zone=health:10m  rate=60r/s;

    # ── Gzip ───────────────────────────────────────────────────────────────
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_types text/plain text/css text/xml application/json
               application/javascript application/xml+rss
               application/atom+xml image/svg+xml;

    # ── Upstreams ──────────────────────────────────────────────────────────
    upstream backend_upstream {
        least_conn;
        server backend:8000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }
    upstream keycloak_upstream {
        least_conn;
        server keycloak:8080 max_fails=3 fail_timeout=30s;
        keepalive 16;
    }
    upstream posthog_upstream {
        server posthog:8000 max_fails=3 fail_timeout=30s;
        keepalive 8;
    }

    # ── TLS defaults ───────────────────────────────────────────────────────
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:50m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 1.1.1.1 8.8.8.8 valid=300s;
    resolver_timeout 5s;

    # ── HTTP → HTTPS redirect ──────────────────────────────────────────────
    server {
        listen 80 default_server;
        listen [::]:80 default_server;
        server_name _;
        return 301 https://$host$request_uri;
    }

    # ── Backend API — api.outrena.com ──────────────────────────────────────
    server {
        listen 443 ssl http2;
        listen [::]:443 ssl http2;
        server_name api.outrena.com;

        ssl_certificate     /etc/nginx/tls/fullchain.pem;
        ssl_certificate_key /etc/nginx/tls/privkey.pem;

        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
        add_header Content-Security-Policy "default-src 'self'; script-src 'self'; frame-ancestors 'none'" always;

        limit_req zone=api burst=60 nodelay;

        location /health {
            limit_req zone=health burst=10;
            access_log off;
            proxy_pass http://backend_upstream;
        }

        location /auth/ {
            limit_req zone=auth burst=10 nodelay;
            proxy_pass http://keycloak_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
        }

        location / {
            proxy_pass http://backend_upstream;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Request-Id $request_id;
            proxy_set_header Connection "";
            proxy_connect_timeout 5s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
            proxy_next_upstream error timeout http_502 http_503 http_504;
        }
    }

    # ── Frontend — outrena.com + tenant subdomains ─────────────────────────
    server {
        listen 443 ssl http2 default_server;
        listen [::]:443 ssl http2 default_server;
        server_name outrena.com www.outrena.com *.outrena.com;

        ssl_certificate     /etc/nginx/tls/fullchain.pem;
        ssl_certificate_key /etc/nginx/tls/privkey.pem;

        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        root /usr/share/nginx/html;
        index index.html;

        # Long-cache hashed assets
        location ~* \.(?:js|css|woff2?|ttf|otf|eot|svg|png|jpg|jpeg|gif|ico|webp)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
            access_log off;
            try_files $uri =404;
        }

        # SPA fallback
        location / {
            try_files $uri $uri/ /index.html;
            add_header Cache-Control "no-cache, must-revalidate";
        }

        location /healthz {
            access_log off;
            return 200 "ok\n";
            add_header Content-Type text/plain;
        }
    }

    # ── Keycloak — auth.outrena.com ────────────────────────────────────────
    server {
        listen 443 ssl http2;
        server_name auth.outrena.com;

        ssl_certificate     /etc/nginx/tls/fullchain.pem;
        ssl_certificate_key /etc/nginx/tls/privkey.pem;

        location / {
            limit_req zone=auth burst=10 nodelay;
            proxy_pass http://keycloak_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    # ── PostHog — analytics.outrena.com ────────────────────────────────────
    server {
        listen 443 ssl http2;
        server_name analytics.outrena.com;

        ssl_certificate     /etc/nginx/tls/fullchain.pem;
        ssl_certificate_key /etc/nginx/tls/privkey.pem;

        location / {
            proxy_pass http://posthog_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;  # PostHog event ingestion prefers no buffering
            proxy_read_timeout 300s;
        }
    }
}
```

**Certificate management.** On AWS, ACM terminates TLS at the ALB and Nginx
listens on plain HTTP — the above `listen 443 ssl` blocks become `listen 80`.
On Azure, App Gateway terminates TLS the same way. On Kubernetes, cert-manager
issues a wildcard cert via Let's Encrypt and stores it in a Kubernetes Secret
mounted into the Nginx Ingress Controller pods. On bare metal, use the
`acme-companion` sidecar to issue certs via the HTTP-01 challenge.

**Verification.**

```bash
# Test config
docker run --rm -v $(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro \
  nginx:1.25-alpine nginx -t

# Live reload
nginx -s reload

# Verify TLS
openssl s_client -connect api.outrena.com:443 -servername api.outrena.com </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -issuer -subject

# Verify HSTS
curl -sI https://outrena.com | grep -i strict-transport-security
```

---

## 10. Keycloak Setup

Keycloak 24+ is the identity provider for OUTRENA. It runs as its own
container (AWS ECS, Azure App Service, K8s StatefulSet) with its own PostgreSQL
database. The OUTRENA backend verifies JWTs by fetching the realm JWKS
(`GET /realms/outrena/protocol/openid-connect/certs`) and caching it in Redis
for 3,600 seconds.

### 10.1 Deploy Keycloak

Keycloak runs behind `auth.outrena.com`. The container is configured with
`KC_DB=postgres`, `KC_DB_URL`, `KC_DB_USERNAME`, `KC_DB_PASSWORD` from
secrets, `KC_HOSTNAME=auth.outrena.com`, `KC_PROXY=passthrough`,
`KC_HTTP_ENABLED=true`. The task definition / Helm chart sets these from
Secrets Manager / Key Vault / Kubernetes Secrets.

### 10.2 Realm Configuration

On a fresh Keycloak instance, create the `outrena` realm and the `frontend`
client. The fastest path is the realm import JSON below — saved as
`realm-outrena.json` and loaded at startup via `KEYCLOAK_IMPORT`.

```bash
# Import realm
docker compose exec keycloak /opt/keycloak/bin/kc.sh import \
  --realm outrena --file /opt/keycloak/data/import/realm-outrena.json

# Or set on startup
KEYCLOAK_IMPORT=/opt/keycloak/data/import/realm-outrena.json
```

```json
{
  "realm": "outrena",
  "enabled": true,
  "sslRequired": "external",
  "registrationAllowed": false,
  "loginWithEmailAllowed": true,
  "duplicateEmailsAllowed": false,
  "resetPasswordAllowed": true,
  "editUsernameAllowed": false,
  "accessTokenLifespan": 900,
  "accessTokenLifespanForImplicitFlow": 900,
  "ssoSessionIdleTimeout": 1800,
  "ssoSessionMaxLifespan": 36000,
  "clients": [
    {
      "clientId": "frontend",
      "name": "OUTRENA Web Frontend",
      "enabled": true,
      "protocol": "openid-connect",
      "publicClient": true,
      "standardFlowEnabled": true,
      "directAccessGrantsEnabled": false,
      "rootUrl": "https://app.outrena.com",
      "redirectUris": ["https://*.outrena.com/*", "https://outrena.com/*"],
      "webOrigins": ["https://*.outrena.com", "https://outrena.com"],
      "attributes": {
        "post.logout.redirect.uris": "https://*.outrena.com/*",
        "tls.client.certificate.bound.access.tokens": "false"
      }
    },
    {
      "clientId": "outrena-backend",
      "name": "OUTRENA Backend Service",
      "enabled": true,
      "protocol": "openid-connect",
      "publicClient": false,
      "secret": "${KEYCLOAK_CLIENT_SECRET}",
      "serviceAccountsEnabled": true,
      "authorizationServicesEnabled": true,
      "standardFlowEnabled": false,
      "directAccessGrantsEnabled": false
    }
  ],
  "roles": {
    "realm": [
      { "name": "REP",            "description": "Sales representative" },
      { "name": "MANAGER",        "description": "Team manager" },
      { "name": "TENANT_ADMIN",   "description": "Tenant administrator" },
      { "name": "SUPER_ADMIN",    "description": "Platform super admin" }
    ]
  },
  "users": [
    {
      "username": "platform-admin",
      "enabled": true,
      "email": "ops@outrena.com",
      "realmRoles": ["SUPER_ADMIN"],
      "requiredActions": ["UPDATE_PASSWORD"]
    }
  ]
}
```

### 10.3 Roles and Role Hierarchy

The four OUTRENA roles map to Keycloak realm roles. The role hierarchy
(defined in `app/schemas/auth.py:29` as `ROLE_HIERARCHY`) is enforced in the
backend via the `require_role` dependency, not in Keycloak. Tenants assign
roles to users through the Keycloak admin API; the backend reads them from the
JWT `realm_access.roles` claim.

### 10.4 JWKS Endpoint and Caching

The backend fetches JWKS from
`https://auth.outrena.com/realms/outrena/protocol/openid-connect/certs` and
caches it in Redis under the key `jwks:outrena` with TTL 3,600 seconds. When a
JWT arrives with a `kid` not present in the cached JWKS, the backend
force-refreshes the JWKS once (`app/services/keycloak_admin_service.py`,
`verify_token`). This handles key rotation without downtime.

### 10.5 Realm Export for Backups

```bash
# Export the realm nightly for DR
docker compose exec keycloak /opt/keycloak/bin/kc.sh export \
  --realm outrena --dir /opt/keycloak/data/export --optimized

# Or via REST API (requires admin-cli token)
TOKEN=$(curl -s -X POST \
  "https://auth.outrena.com/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" -d "username=$KC_ADMIN" -d "password=$KC_PASS" \
  -d "grant_type=password" | jq -r .access_token)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://auth.outrena.com/admin/realms/outrena" > realm-outrena-backup.json
```

---

## 11. Database Deployment

OUTRENA uses PostgreSQL 16 with a schema-per-tenant layout. The `public`
schema holds platform-wide tables (tenants, users, audit log, platform
credentials, billing). Each tenant gets its own schema named after its slug
(`acme`, `globex`) containing feature tables (campaigns, prospects,
sequences, etc.).

### 11.1 Initial Schema — public

The base migration (`alembic/versions/0001_public_schema.py`) creates the
platform tables. The SQL below is the authoritative shape — refer to the
migration file for the exact Alembic revision.

```sql
-- 0001_public_schema.sql (excerpt)
CREATE SCHEMA IF NOT EXISTS public;

CREATE TABLE public.tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{2,32}$'),
    name            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('provisioning','active','suspended','terminated')),
    plan            TEXT NOT NULL DEFAULT 'free',
    schema_name     TEXT NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES public.tenants(id) ON DELETE CASCADE,
    keycloak_user_id TEXT UNIQUE,
    email           TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('REP','MANAGER','TENANT_ADMIN','SUPER_ADMIN')),
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.platform_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_user_id   UUID,
    tenant_slug     TEXT,
    method          TEXT,
    path            TEXT,
    status_code     INT,
    target_type     TEXT,
    target_id       TEXT,
    detail          JSONB
);
CREATE INDEX ON public.platform_audit_log (tenant_slug, occurred_at DESC);
CREATE INDEX ON public.platform_audit_log (occurred_at DESC);

CREATE TABLE public.platform_credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        TEXT NOT NULL,
    key_name        TEXT NOT NULL,
    secret_ref      TEXT NOT NULL,  -- AWS SM ARN or Azure Key Vault URI
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, key_name)
);
```

### 11.2 Tenant Provisioning

The `provision_tenant()` PL/pgSQL function creates a tenant row in `public`,
clones the tenant schema template, and runs seed inserts. It is invoked by
the `TenantService` when a new tenant signs up.

```sql
-- provision_tenant.sql
CREATE OR REPLACE FUNCTION public.provision_tenant(
    p_slug TEXT,
    p_name TEXT,
    p_plan TEXT DEFAULT 'free'
) RETURNS UUID AS $$
DECLARE
    v_tenant_id UUID;
    v_schema    TEXT := p_slug;
BEGIN
    INSERT INTO public.tenants (slug, name, plan, schema_name, status)
    VALUES (p_slug, p_name, p_plan, v_schema, 'provisioning')
    RETURNING id INTO v_tenant_id;

    EXECUTE format('CREATE SCHEMA %I AUTHORIZATION outrena', v_schema);
    -- Apply tenant template (defined in 0002_tenant_template.sql)
    EXECUTE format('SET search_path TO %I', v_schema);
    -- Run all tenant-table DDL here (campaigns, prospects, sequences, ...)
    -- …
    EXECUTE 'SET search_path TO public';

    UPDATE public.tenants SET status = 'active' WHERE id = v_tenant_id;
    RETURN v_tenant_id;
END;
$$ LANGUAGE plpgsql;

-- Usage
SELECT public.provision_tenant('acme', 'Acme Corp', 'growth');
```

### 11.3 Migration Strategy

Schema changes are managed with Alembic. Migrations are idempotent and
forward-only in production — the rollback strategy is to deploy the previous
migration set, not to run `downgrade` (which is destructive). The CI pipeline
runs `alembic upgrade head` as a pre-deploy job that holds a brief advisory
lock to prevent concurrent migrations.

```bash
# Generate a new migration
cd outrena-backend
alembic revision -m "add_email_send_logs_table"

# Apply locally
alembic upgrade head

# Apply to staging (read DB URL from Secrets Manager)
DATABASE_URL=$(aws secretsmanager get-secret-value \
  --secret-id outrena/staging/database-url --query SecretString --output text) \
  alembic upgrade head

# Production — runs in CI as a migration job before the deploy stage
alembic upgrade head

# Verify current revision
alembic current
# 0042_add_email_send_logs_table (head)
```

**Zero-downtime migration rules.** Migrations must not lock tables for more
than 5 seconds against a 1,000-row write workload. Specifically: add columns
with `NULL` defaults (never `NOT NULL` without a default), add indexes with
`CREATE INDEX CONCURRENTLY`, drop columns in two phases (deploy version N
that ignores the column, then deploy version N+1 that drops it), and never
rename columns in a single migration.

### 11.4 Backup and Restore

```bash
# Daily logical backup (3:00 UTC, after RDS automated snapshot)
pg_dump --format=custom --no-owner --no-privileges \
  --file=/backups/outrena-$(date -u +%Y%m%d-%H%M).dump \
  "$DATABASE_URL"

# Restore from backup
pg_restore --clean --if-exists --no-owner --no-privileges \
  --dbname="$DATABASE_URL" /backups/outrena-20240315-0300.dump

# RDS point-in-time recovery (5-minute granularity)
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier outrena-prod \
  --target-db-instance-identifier outrena-prod-pit-20240315 \
  --restore-time 2024-03-15T03:00:00Z \
  --db-subnet-group-name outrena-prod-db \
  --vpc-security-group-ids sg-outrena-db-prod
```

Backups are encrypted at rest in S3 with SSE-KMS and copied to the DR region
via cross-region replication. Restore drills run monthly (see §19).

---

## 12. PostHog Deployment

PostHog provides product analytics (funnels, retention, feature flags, session
replay). OUTRENA supports two deployment modes: self-hosted (recommended for
enterprise tenants with data residency requirements) or PostHog Cloud.

### 12.1 Self-Hosted PostHog

The self-hosted stack is defined in `docker-compose.posthog.yml` and the
Terraform modules `terraform/aws/posthog.tf` / `terraform/azure/posthog.tf`.
It runs PostHog on its own ECS service / App Service / StatefulSet with its
own PostgreSQL database, Redis, ClickHouse (for event ingestion), Kafka, and
MinIO / S3 for object storage.

```bash
# Local / dev — bring up PostHog alongside OUTRENA
docker compose -f docker-compose.posthog.yml up -d

# Production — provisioned by Terraform, deployed by CI
# AWS: ECS service `outrena-posthog-prod` behind ALB listener rule
# Azure: App Service `outrena-posthog-prod` behind App Gateway path rule
# K8s: StatefulSet in `outrena-prod` namespace, Ingress analytics.outrena.com
```

PostHog environment variables:

```bash
POSTHOG_DB=postgres
POSTHOG_DB_HOST=posthog-db.outrena.internal
POSTHOG_DB_USER=posthog
POSTHOG_DB_PASSWORD=${POSTHOG_DB_PASSWORD}
POSTHOG_REDIS=posthog-redis.outrena.internal:6379
POSTHOG_KAFKA_HOSTS=posthog-kafka:9092
POSTHOG_CLICKHOUSE_HOST=posthog-clickhouse:9000
POSTHOG_OBJECT_STORAGE_ENABLED=true
POSTHOG_OBJECT_STORAGE_ENDPOINT=https://s3.us-east-1.amazonaws.com
POSTHOG_OBJECT_STORAGE_BUCKET=outrena-posthog-events
Sentry DSN, SECURE_COOKIES, DISABLE_SECURE_SSL_REDIRECT=false
```

### 12.2 PostHog Cloud

For the cloud mode, set the following frontend env vars and skip §12.1
entirely:

```bash
VITE_POSTHOG_HOST=https://app.posthog.com
VITE_POSTHOG_KEY=phc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

The backend uses the same key to send server-side events via the PostHog
Python SDK.

### 12.3 Instrumentation

The backend uses `posthog` Python SDK; the frontend uses `posthog-js`. Both
are initialized in `app/main.py` and `src/main.tsx` respectively. The
`tenant_slug` is set as a person property and as a super property on every
event so analytics can be sliced per tenant. PII fields (email, phone,
prospect name) are never sent to PostHog — only anonymized IDs.

---

## 13. Observability Stack

OUTRENA's observability stack has four pillars: metrics (Prometheus), logs
(Loki), traces (Tempo), and product analytics (PostHog). All three backend
pillars funnel through an OpenTelemetry Collector sidecar that fans out to
the right backends. The full config lives in `monitoring/otel/collector-config.yml`.

```mermaid
flowchart LR
    APP[Backend + Worker<br/>Containers] -->|OTLP gRPC :4317| OTEL[OTel Collector<br/>Sidecar]
    FE[Frontend Browser] -->|JS beacon| PH[PostHog]
    OTEL -->|metrics| PROM[Prometheus<br/>remote-write]
    OTEL -->|logs| LOKI[Loki]
    OTEL -->|traces| TEMPO[Tempo]
    PROM --> GRAF[Grafana]
    LOKI --> GRAF
    TEMPO --> GRAF
    PH --> GRAF
    PROM --> AM[Alertmanager<br/>→ PagerDuty]
    LOKI --> AM
```

### 13.1 Prometheus

Prometheus scrapes the backend `/metrics` endpoint (exposed by
`MetricsMiddleware`) every 15 seconds, plus the OTel Collector's own metrics.
The scrape config (`monitoring/prometheus/prometheus.yml`) defines three
jobs: `outrena-backend` (all ECS tasks / App Service instances / K8s pods),
`otel-collector`, and `prometheus` self. Prometheus is configured for 30-day
retention with a 100 GB WAL.

Metrics exposed by the backend:
- `outrena_http_requests_total{method,route,status,tenant}` (counter)
- `outrena_http_request_duration_seconds{method,route,tenant}` (histogram)
- `outrena_http_requests_active{method,route}` (gauge)
- `outrena_celery_tasks_total{queue,state}` (counter)
- `outrena_celery_task_duration_seconds{queue,task}` (histogram)
- `outrena_db_connections_in_use` (gauge)
- `outrena_redis_ops_total{op}` (counter)
- `outrena_llm_calls_total{provider,model,status}` (counter)

### 13.2 Grafana Dashboards

Dashboards live in `monitoring/grafana/dashboards/` and are provisioned
automatically via the Grafana Helm chart or the Terraform-managed Grafana
instance. The four primary dashboards:

1. **OUTRENA Overview** — golden signals per service, top-10 tenants by traffic
2. **Tenant Detail** — single-tenant drill-down: API latency, task throughput,
   LLM spend, error rate
3. **Database Health** — connections, slow queries, replication lag, cache hit
   ratio, schema size
4. **Worker Health** — queue depth per queue, task failure rate, task duration
   p50/p95/p99, retry count

### 13.3 Loki

Loki ingests structlog JSON from all containers via Promtail (K8s) or
CloudWatch Logs subscription filters (AWS) or Azure Monitor diagnostic
settings (Azure). Retention is 30 days in dev, 90 days in prod. The Loki
config (`monitoring/loki/loki-config.yml`) uses TSDB schema v13 with S3
backend in prod and filesystem in dev.

Sample LogQL queries:

```logql
# 5xx errors per tenant over the last hour
{app="outrena-backend"} |= "5xx" | json | line_format "{{.tenant}} {{.status}} {{.path}}"

# Celery task failures
{app="outrena-worker"} |= "task_failed" | json

# PII access audit
{app="outrena-backend"} |= "pii_read" | json | line_format "{{.actor}} {{.target_type}} {{.target_id}}"
```

### 13.4 Tempo

Tempo stores distributed traces for 7 days (dev) / 30 days (prod). The OTel
Collector exports to Tempo over OTLP gRPC. Trace sampling is 100% in dev, 10%
in prod (configured in `app/main.py` `OTEL_TRACES_SAMPLER_ARG`). Trace IDs
are emitted in the `X-Trace-Id` response header and in every log line so
engineers can pivot from a Grafana panel to a trace in one click.

### 13.5 Alert Rules

Alerts fire via Alertmanager → PagerDuty. The alert rules below are
Provisioned from `monitoring/prometheus/rules.yml`.

| Alert | Expression | For | Severity |
|---|---|---|---|
| `BackendHigh5xxRate` | `rate(outrena_http_requests_total{status=~"5.."}[5m]) / rate(outrena_http_requests_total[5m]) > 0.01` | 5m | critical |
| `BackendHighLatencyP99` | `histogram_quantile(0.99, rate(outrena_http_request_duration_seconds_bucket[5m])) > 2` | 5m | warning |
| `WorkerQueueBacklog` | `outrena_celery_queue_depth > 500` | 10m | warning |
| `WorkerTaskFailureRate` | `rate(outrena_celery_tasks_total{state="failure"}[10m]) / rate(outrena_celery_tasks_total[10m]) > 0.05` | 10m | critical |
| `DbConnectionSaturation` | `outrena_db_connections_in_use / 960 > 0.85` | 5m | warning |
| `RedisEvictionsHigh` | `rate(redis_evicted_keys_total[5m]) > 100` | 5m | warning |
| `CertificateExpiringSoon` | `probe_ssl_earliest_cert_expiry < 7*24*3600` | 1h | warning |

---

## 14. CI/CD Pipeline

The CI/CD pipeline runs on GitHub Actions. The workflow
`.github/workflows/deploy.yml` defines the canonical pipeline: lint → test →
build → push → staging deploy → prod deploy. Database migrations run as a
dedicated job that gates the prod deploy.

```mermaid
flowchart LR
    PR[Pull Request] --> LINT[Lint + Typecheck]
    LINT --> TEST[Unit + Integration Tests]
    TEST --> SEC[Security Scan<br/>Trivy + Bandit]
    PUSH{Branch}
    PUSH -->|main| BUILD[Build Images]
    BUILD --> PUSH_REG[Push to Registry]
    PUSH_REG --> MIG_STAGE[Alembic Migrate<br/>staging]
    MIG_STAGE --> DEPLOY_STAGE[Deploy to Staging]
    DEPLOY_STAGE --> SMOKE[Smoke Tests]
    SMOKE --> APPROVE{Manual Approval}
    APPROVE -->|approved| MIG_PROD[Alembic Migrate<br/>prod]
    MIG_PROD --> DEPLOY_PROD[Deploy to Prod]
    DEPLOY_PROD --> VERIFY[Verify + Monitor]
```

### 14.1 Workflow Definition

```yaml
# .github/workflows/deploy.yml (excerpt)
name: Deploy
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [staging, prod]
      version:
        required: true

jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: pip install uv && uv sync --frozen
      - run: uv run ruff check app/
      - run: uv run mypy app/
      - run: uv run pytest -q --cov=app --cov-fail-under=75
      - run: cd outrena-frontend && corepack enable && pnpm install --frozen-lockfile
      - run: cd outrena-frontend && pnpm lint && pnpm typecheck && pnpm test

  security:
    runs-on: ubuntu-latest
    needs: lint-test
    steps:
      - uses: actions/checkout@v4
      - run: docker run --rm -v $(pwd):/repo aquasec/trivy:latest fs --severity HIGH,CRITICAL /repo
      - run: pip install bandit && bandit -r app/ -ll

  build-push:
    runs-on: ubuntu-latest
    needs: [lint-test, security]
    permissions: { packages: write, id-token: write }
    outputs:
      version: ${{ steps.meta.outputs.version }}
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_OIDC_ROLE }}
          aws-region: us-east-1
      - uses: aws-actions/amazon-ecr-login@v2
      - id: meta
        run: echo "version=$(git rev-parse --short HEAD)-$(date +%Y%m%d%H%M)" >> $GITHUB_OUTPUT
      - run: |
          docker buildx build --push \
            -t $ECR/outrena-backend:${{ steps.meta.outputs.version }} \
            -t $ECR/outrena-backend:latest \
            -f outrena-backend/Dockerfile outrena-backend/
      - run: |
          docker buildx build --push \
            -t $ECR/outrena-frontend:${{ steps.meta.outputs.version }} \
            -t $ECR/outrena-frontend:latest \
            --build-arg VITE_API_BASE_URL=https://api.outrena.com \
            --build-arg VITE_KEYCLOAK_URL=https://auth.outrena.com \
            --build-arg VITE_KEYCLOAK_REALM=outrena \
            --build-arg VITE_KEYCLOAK_CLIENT_ID=frontend \
            -f outrena-frontend/Dockerfile outrena-frontend/

  migrate-staging:
    runs-on: ubuntu-latest
    needs: build-push
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with: { role-to-assume: ${{ secrets.AWS_OIDC_ROLE_STAGING }}, aws-region: us-east-1 }
      - run: |
          DATABASE_URL=$(aws secretsmanager get-secret-value \
            --secret-id outrena/staging/database-url --query SecretString --output text)
          pip install alembic asyncpg
          cd outrena-backend && alembic upgrade head

  deploy-staging:
    runs-on: ubuntu-latest
    needs: migrate-staging
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
      - run: |
          aws ecs update-service --cluster outrena-staging \
            --service outrena-backend-staging \
            --force-new-deployment
          aws ecs wait services-stable --cluster outrena-staging \
            --services outrena-backend-staging outrena-worker-staging

  smoke-tests:
    runs-on: ubuntu-latest
    needs: deploy-staging
    steps:
      - run: |
          curl -fsS https://api.staging.outrena.com/health | jq .
          k6 run tests/load/smoke.js

  deploy-prod:
    runs-on: ubuntu-latest
    needs: smoke-tests
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with: { role-to-assume: ${{ secrets.AWS_OIDC_ROLE_PROD }}, aws-region: us-east-1 }
      - run: |
          DATABASE_URL=$(aws secretsmanager get-secret-value \
            --secret-id outrena/prod/database-url --query SecretString --output text)
          cd outrena-backend && alembic upgrade head
      - run: |
          aws ecs update-service --cluster outrena-prod \
            --service outrena-backend-prod --force-new-deployment
          aws ecs wait services-stable --cluster outrena-prod \
            --services outrena-backend-prod outrena-worker-prod
      - run: ./scripts/cutover/monitor-cutover.sh --duration 15m
```

### 14.2 Rollback

Rollback is two-step: roll the ECS task definition back to the previous
revision, then roll the database back if a migration was applied. DB rollback
is destructive and requires SRE approval — see RB-02.

```bash
# Roll ECS service to previous task def revision
aws ecs describe-services --cluster outrena-prod --services outrena-backend-prod \
  --query 'services[0].taskDefinition' --output text  # current revision
aws ecs update-service --cluster outrena-prod --service outrena-backend-prod \
  --task-definition outrena-backend-prod:PREVIOUS_REVISION
aws ecs wait services-stable --cluster outrena-prod --services outrena-backend-prod
```

---

## 15. Configuration Management

All OUTRENA configuration flows through environment variables. Secrets live in
AWS Secrets Manager / Azure Key Vault / Kubernetes Secrets and are injected at
container start. Non-secret config (URLs, feature flags, log levels) is set
directly on the task definition / App Service / Helm values. The contract
below applies to all three deployment targets.

### 15.1 Backend Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ENVIRONMENT` | yes | `development` | `development` / `staging` / `production` |
| `BASE_DOMAIN` | yes | `localhost` | Apex domain for tenant subdomains |
| `DATABASE_URL` | yes | — | `postgresql+asyncpg://...` |
| `REDIS_URL` | yes | — | `redis://...` (TLS in prod) |
| `CELERY_BROKER_URL` | yes | `$REDIS_URL` | Override for separate Redis DB |
| `CELERY_RESULT_BACKEND` | yes | `$REDIS_URL` | Override for separate Redis DB |
| `KEYCLOAK_BASE_URL` | yes | — | `https://auth.outrena.com` |
| `KEYCLOAK_REALM` | yes | `outrena` | Keycloak realm |
| `KEYCLOAK_CLIENT_SECRET` | yes | — | Service-account client secret |
| `KEYCLOAK_ADMIN_CLIENT_ID` | yes | `admin-cli` | Admin API client |
| `KEYCLOAK_ADMIN_USERNAME` | yes | — | Admin user |
| `KEYCLOAK_ADMIN_PASSWORD` | yes | — | Admin password |
| `SKIP_JWT_VERIFICATION` | no | `false` | Dev-only bypass — NEVER true in prod |
| `VERIFY_JWT_ISSUER` | no | `true` | Issuer claim validation |
| `FERNET_KEY` | yes | — | Tenant credential encryption key |
| `JWT_SECRET` | yes | — | HS256 fallback (dev only) |
| `STRIPE_SECRET_KEY` | yes | — | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | yes | — | `whsec_...` |
| `OPENAI_API_KEY` | no | — | LLM provider key |
| `ANTHROPIC_API_KEY` | no | — | LLM provider key |
| `AZURE_OPENAI_API_KEY` | no | — | LLM provider key |
| `AZURE_OPENAI_ENDPOINT` | no | — | Azure OpenAI deployment URL |
| `GEMINI_API_KEY` | no | — | LLM provider key |
| `AWS_ACCESS_KEY_ID` | no | — | When using AWS Secrets Manager |
| `AWS_SECRET_ACCESS_KEY` | no | — | When using AWS Secrets Manager |
| `AWS_REGION` | no | — | AWS region |
| `AZURE_TENANT_ID` | no | — | When using Azure Key Vault |
| `AZURE_CLIENT_ID` | no | — | Managed identity client ID |
| `AZURE_CLIENT_SECRET` | no | — | SP secret (when not using MI) |
| `AZURE_KEY_VAULT_URL` | no | — | Key Vault URI |
| `SECRET_BACKEND` | no | `env` | `env` / `aws` / `azure` |
| `S3_BUCKET_EXPORTS` | yes | — | Campaign exports bucket |
| `S3_BUCKET_ATTACHMENTS` | yes | — | Email attachments bucket |
| `MAILBRIDGE_API_URL` | yes | — | MailBridge relay URL |
| `MAILBRIDGE_API_KEY` | yes | — | MailBridge auth token |
| `POSTHOG_API_KEY` | no | — | Server-side event ingestion |
| `POSTHOG_HOST` | no | — | `https://analytics.outrena.com` |
| `SENTRY_DSN` | no | — | Error tracking |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | no | — | OTel Collector URL |
| `OTEL_TRACES_SAMPLER_ARG` | no | `0.1` | Trace sampling rate (prod) |
| `LOG_LEVEL` | no | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `CACHE_DEFAULT_TTL` | no | `300` | Default Redis cache TTL (seconds) |
| `RATE_LIMIT_ENABLED` | no | `true` | Redis sliding-window limiter |

### 15.2 Frontend Environment Variables

| Variable | Required | Description |
|---|---|---|
| `VITE_API_BASE_URL` | yes | `https://api.outrena.com` |
| `VITE_KEYCLOAK_URL` | yes | `https://auth.outrena.com` |
| `VITE_KEYCLOAK_REALM` | yes | `outrena` |
| `VITE_KEYCLOAK_CLIENT_ID` | yes | `frontend` |
| `VITE_POSTHOG_HOST` | no | `https://analytics.outrena.com` |
| `VITE_POSTHOG_KEY` | no | PostHog project key |
| `VITE_SENTRY_DSN` | no | Frontend error tracking |
| `VITE_DEV_BYPASS_AUTH` | no | `false` in any deployed env |
| `VITE_DEV_TENANT_SLUG` | no | Empty in any deployed env |

### 15.3 Worker Environment Variables

The worker uses the same env vars as the backend, plus:

| Variable | Required | Default | Description |
|---|---|---|---|
| `CELERY_WORKER_CONCURRENCY` | no | `8` | Concurrent tasks per process |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | no | `1` | Long-running tasks → 1 |
| `CELERY_WORKER_MAX_TASKS_PER_CHILD` | no | `100` | Recycle child after N tasks |
| `CELERY_WORKER_QUEUES` | no | `default,emails,llm` | Comma-separated queue list |
| `CELERY_BEAT_SCHEDULE_PATH` | no | `app/worker/schedule.py` | Beat schedule module |
| `LLM_MAX_RETRIES` | no | `3` | Per-task LLM call retry |
| `EMAIL_SEND_TIMEOUT` | no | `30` | MailBridge send timeout (s) |

### 15.4 Rotation

Secrets that support rotation are rotated automatically by the secrets
manager: `DATABASE_URL` (RDS managed password rotation, 30 days),
`KEYCLOAK_ADMIN_PASSWORD` (Lambda rotation, 90 days),
`STRIPE_WEBHOOK_SECRET` (manual, on-demand). Fernet and JWT keys are rotated
manually per RB-04 and RB-05.

---

## 16. Security Hardening

OUTRENA is deployed with defense-in-depth across seven layers. Each layer is
hardened independently and assumes the layer outside it may be compromised.

### 16.1 Network Hardening

The VPC is split into public subnets (ALB / App Gateway only), private
subnets (ECS / App Service / K8s pods), and data subnets (RDS / Redis).
Security groups follow a strict allow-list model: the ALB SG allows 443 from
Cloudflare IPs only; the backend SG allows 8000 from the ALB SG only; the DB
SG allows 5432 from the backend SG only; the Redis SG allows 6379 from the
backend and worker SGs only. All egress from the private subnet is funnelled
through a NAT gateway with Flow Logs enabled. VPC Peering and PrivateLink
endpoints are used for S3, ECR, Secrets Manager, and STS so traffic to AWS
services never traverses the public internet.

On Azure, equivalent isolation uses VNet integration on App Service, private
endpoints on PostgreSQL and Redis, and NSG rules mirroring the AWS SGs above.

### 16.2 Secrets Management

Secrets never touch disk in plain text. The backend's `SecretBackend`
abstraction (`app/services/secret_service.py`) reads from one of three
backends at startup based on `SECRET_BACKEND`. AWS Secrets Manager is the
default in AWS; Azure Key Vault is the default in Azure. Both support
automatic rotation via Lambda / Azure Functions. The Fernet key used to
encrypt tenant-managed credentials at rest is itself stored in the same
secrets manager and rotated per RB-04 with a two-key overlap window so
existing ciphertext remains decryptable during rotation.

### 16.3 TLS and Transport

TLS 1.2 minimum, TLS 1.3 preferred. HSTS header is `max-age=63072000;
includeSubDomains; preload`. Cloudflare's "Authenticated Origin Pulls" is
enabled so the origin (ALB / App Gateway) only accepts connections presenting
a Cloudflare client certificate. Internal service-to-service traffic inside
the VPC uses TLS where supported (RDS, ElastiCache) and mTLS where supported
via App Mesh / Istio on Kubernetes.

### 16.4 WAF Rules

AWS WAF (or Azure Front Door WAF / App Gateway WAF) is enabled at the edge
with the OWASP CRS 3.2 rule set in Prevention mode. Custom rules block:

| Rule | Action | Notes |
|---|---|---|
| SQLi patterns | Block | OWASP managed rule group |
| XSS patterns | Block | OWASP managed rule group |
| LFI / RFI | Block | OWASP managed rule group |
| Geo-block (optional) | Block | Tenant-configurable country list |
| Rate-per-IP | Throttle | 100 r/s per IP sustained |
| Bot signatures | CAPTCHA | Cloudflare managed challenge |
| Outrena-specific path abuse | Block | `POST /billing/subscribe` from non-tenant hosts |
| Request body > 25 MB | Block | Protects against upload abuse |

### 16.5 Compliance

| Framework | Status | Notes |
|---|---|---|
| SOC 2 Type II | In scope | CloudTrail + audit log retention 365 days |
| GDPR | Compliant | DSR pipeline + EU data residency option |
| CCPA | Compliant | Same as GDPR pipeline |
| HIPAA | Out of scope | Not marketed to healthcare tenants |
| ISO 27001 | In scope | Annual external audit |
| PCI DSS | SAQ-A | Stripe handles card data; OUTRENA never sees PAN |

### 16.6 Patch Management

Container base images are rebuilt weekly via a scheduled GitHub Action that
bumps the base image digest and opens a PR. The PR runs the full pipeline
including the security scan; on green it auto-merges and triggers a prod
deploy during the next maintenance window. Critical CVEs are patched
out-of-band within 24 hours of disclosure.

---

## 17. Cutover + Migration

Cutover from the legacy platform to OUTRENA v8 is a phased blue-green
operation. DNS weights control traffic split: 0% → 5% → 25% → 50% → 100%.
The full sequence is scripted in `scripts/cutover/full-cutover-sequence.sh`.

```mermaid
sequenceDiagram
    participant Legacy as Legacy Platform
    participant DNS as Route 53 / Azure DNS
    participant Outrena as OUTRENA v8
    participant DB as PostgreSQL v8
    participant Ops as SRE
    Ops->>DB: 1. Run data migration scripts (backfill tenants, users, campaigns)
    Ops->>Outrena: 2. Verify data integrity (row counts, checksums)
    Ops->>DNS: 3. Set weighted routing: 95% Legacy / 5% Outrena
    Ops->>Outrena: 4. Monitor error rate, latency, 5xx for 1 hour
    Ops->>DNS: 5. Promote to 50% / 50%
    Ops->>Outrena: 6. Monitor for 4 hours
    Ops->>DNS: 7. Promote to 0% / 100%
    Ops->>Legacy: 8. Set legacy to read-only
    Ops->>Legacy: 9. Decommission after 30-day observation
```

### 17.1 Data Migration Scripts

Migration scripts live in `scripts/cutover/`. They run as one-off ECS tasks
or Kubernetes jobs against the v8 database, reading from a read replica of
the legacy database.

```bash
# 1. Backfill tenants and users
python scripts/cutover/migrate_tenants.py --source $LEGACY_DB --target $V8_DB
python scripts/cutover/migrate_users.py    --source $LEGACY_DB --target $V8_DB

# 2. Backfill campaigns and prospects (per-tenant, parallelized)
python scripts/cutover/migrate_campaigns.py --tenant acme --batch-size 5000
python scripts/cutover/migrate_prospects.py --tenant acme --batch-size 50000

# 3. Backfill sequences and email history
python scripts/cutover/migrate_sequences.py --tenant acme
python scripts/cutover/migrate_email_logs.py --tenant acme --since 2023-01-01

# 4. Validate
python scripts/cutover/validate-cutover.py --tenant acme
```

### 17.2 DNS Cutover

```bash
# AWS Route 53 — 5% to OUTRENA
./scripts/cutover/aws-route53-weighted.sh --weight-legacy 95 --weight-outrena 5

# Monitor for 1 hour
./scripts/cutover/monitor-cutover.sh --duration 60m

# Promote to 50/50
./scripts/cutover/aws-route53-weighted.sh --weight-legacy 50 --weight-outrena 50

# Final cutover — 100% to OUTRENA
./scripts/cutover/aws-route53-weighted.sh --weight-legacy 0 --weight-outrena 100

# Azure equivalent
./scripts/cutover/azure-traffic-manager-weighted.sh --weight-legacy 0 --weight-outrena 100
```

### 17.3 Rollback

If error rate exceeds 1% sustained for 5 minutes during cutover, rollback is
to flip DNS weights back to 100% legacy. The v8 database is preserved (writes
that landed in v8 during the partial cutover are replayed to legacy if
needed).

```bash
# AWS Route 53 rollback
./scripts/cutover/aws-route53-rollback.sh

# Azure rollback
./scripts/cutover/azure-traffic-manager-rollback.sh
```

---

## 18. Runbooks

The 15 runbooks below are single-page operational procedures. Each is
structured as Prerequisites → Steps → Verification → Rollback. Runbooks are
also published as standalone Markdown files under `runbooks/`.

### RB-01 — Deploy OUTRENA to Production

**Prerequisites.** CI pipeline green on `main`; smoke tests passed on
staging; on-call SRE acknowledges the deploy window; current task definition
revision recorded.

**Steps.**
1. Trigger the `deploy.yml` GitHub Actions workflow with
   `environment=prod`, `version=<git sha>`.
2. The pipeline runs `alembic upgrade head` against prod, gated by a manual
   approval.
3. ECS services `outrena-backend-prod` and `outrena-worker-prod` are updated
   to the new task definition with `--force-new-deployment`.
4. Wait for `aws ecs wait services-stable` on both services.
5. Run `scripts/cutover/monitor-cutover.sh --duration 15m` to watch error
   rate, latency, and queue depth.

**Verification.** `curl https://api.outrena.com/health` returns `200 OK`
with the new version string. Grafana Overview dashboard shows no error spike.
CloudWatch alarm `BackendHigh5xxRate` is green.

**Rollback.** See RB-02.

### RB-02 — Rollback a Production Deploy

**Prerequisites.** Previous task definition revision number recorded from
RB-01 step 5; DB migration state known (applied / not applied).

**Steps.**
1. Roll ECS task definitions back:
   `aws ecs update-service --cluster outrena-prod --service outrena-backend-prod --task-definition outrena-backend-prod:PREVIOUS`.
2. Repeat for `outrena-worker-prod`.
3. Wait for `services-stable`.
4. If a destructive migration was applied (column drop, type change), do NOT
   roll back the database — restore from the pre-deploy snapshot instead
   (RB-06).
5. If a non-destructive migration was applied (add column, add index), leave
   the DB at head; the previous code revision ignores the new columns.

**Verification.** Grafana shows error rate returning to baseline within
5 minutes. `alembic current` reports the expected revision.

**Rollback of rollback.** Re-run RB-01 once root cause is fixed.

### RB-03 — Provision a New Tenant

**Prerequisites.** Tenant signed up via the billing flow; Keycloak admin
credentials on hand; `psql` access to the prod DB (read-only through a
bastion is fine).

**Steps.**
1. Confirm the tenant row exists in `public.tenants` with status
   `provisioning`. If not, run:
   `SELECT public.provision_tenant('acme', 'Acme Corp', 'growth');`
2. Create the tenant admin user in Keycloak realm `outrena` with the
   `TENANT_ADMIN` realm role and a custom attribute `tenant_slug=acme`.
3. Send a password-reset email to the tenant admin via Keycloak admin API.
4. Seed the tenant's default campaigns and email templates via the
   `TenantService.seed_defaults()` admin endpoint.
5. Verify the tenant can log in at `https://acme.outrena.com` and create a
   campaign.

**Verification.** `SELECT slug, status FROM public.tenants WHERE slug='acme';`
returns `active`. Backend `/health` for `X-Outrena-Tenant: acme` returns 200.
Frontend at `acme.outrena.com` loads and shows the dashboard.

**Rollback.** Suspend the tenant: `UPDATE public.tenants SET status='suspended' WHERE slug='acme';`.
Drop the schema if the tenant is to be fully removed:
`DROP SCHEMA acme CASCADE;` followed by `DELETE FROM public.tenants WHERE slug='acme';`.

### RB-04 — Rotate the Fernet Key

**Prerequisites.** New Fernet key generated (`Fernet.generate_key()`); old
key preserved; maintenance window of 30 minutes; on-call SRE.

**Steps.**
1. Add the new key to the secrets manager as `FERNET_KEY_NEW`, keeping
   `FERNET_KEY` pointing at the old key.
2. Set the backend env var `FERNET_KEY_PREVIOUS` to the old key and
   `FERNET_KEY` to the new key. The `PiiService` and
   `IntegrationCredentialsService` decrypt with `FERNET_KEY_PREVIOUS` when
   the primary key fails.
3. Deploy the backend with the new env vars.
4. Run the re-encryption job:
   `celery -A app.worker.celery_app call app.worker.tasks.reencrypt_tenant_credentials`
   This iterates all `tenant_credentials` rows and re-encrypts with the new
   key.
5. Verify all rows re-encrypted:
   `SELECT count(*) FROM tenant_credentials WHERE key_version < 2;` should be 0.
6. Remove `FERNET_KEY_PREVIOUS` from the secrets manager after a 7-day
   observation window.

**Verification.** Tenants can still call LLM providers (credentials decrypt).
PII fields display correctly in the UI. `key_version=2` on all rows.

**Rollback.** Set `FERNET_KEY` back to the old value and revert the deploy.
Re-encrypted rows will decrypt with the old key (the old key was the previous
primary key).

### RB-05 — Rotate the JWT Signing Key

**Prerequisites.** Keycloak admin access; coordination with the frontend team
for cache flush.

**Steps.**
1. In Keycloak admin console, go to Realm `outrena` → Keys → Providers →
   Add `rsa-generated` provider with priority higher than the current
   active key.
2. Keycloak immediately starts signing new tokens with the new key. The JWKS
   endpoint (`/realms/outrena/protocol/openid-connect/certs`) now contains
   both keys.
3. Force a JWKS refresh on the backend:
   `redis-cli DEL jwks:outrena`. The next request will re-fetch.
4. Wait 30 minutes (longer than `accessTokenLifespan` of 15 minutes plus
   margin) for all in-flight tokens to expire.
5. Remove the old key from Keycloak Keys Providers.

**Verification.** Login flow works end-to-end. Backend logs show no JWKS
errors. `redis-cli GET jwks:outrena` returns JWKS with the new `kid` only.

**Rollback.** Re-add the old key as a provider in Keycloak. Tokens signed by
the old key become valid again.

### RB-06 — Restore PostgreSQL from Backup

**Prerequisites.** Restore target identified (new RDS instance or PIT);
maintenance window; estimated RTO 30 minutes.

**Steps.**
1. Identify the restore point — either the latest automated snapshot or a
   specific timestamp for PITR.
2. For snapshot restore:
   `aws rds restore-db-instance-from-db-snapshot --db-instance-identifier outrena-prod-restore --db-snapshot-identifier outrena-prod-2024-03-15`
3. For PITR:
   `aws rds restore-db-instance-to-point-in-time --source-db-instance-identifier outrena-prod --target-db-instance-identifier outrena-prod-pitr --restore-time 2024-03-15T03:00:00Z`
4. Wait for the new instance to become `available` (10–20 minutes for 500 GB).
5. Update the Secrets Manager `DATABASE_URL` to point at the new instance.
6. Restart the backend and worker ECS services to pick up the new secret.
7. Run `alembic current` to confirm revision matches.

**Verification.** Row counts on critical tables match the pre-incident
baseline. Recent tenant activity visible in the UI. CloudWatch shows
backend reconnecting to the new DB.

**Rollback.** Point `DATABASE_URL` back at the original instance if still
available.

### RB-07 — Redis Failure or Failover

**Prerequisites.** CloudWatch alarm `RedisEvictionsHigh` or
`RedisClusterDegraded` firing; on-call SRE paged.

**Steps.**
1. Check cluster status: `aws elasticache describe-replication-groups --replication-group-id outrena-prod`
2. If a node is `degraded`, failover manually:
   `aws elasticache test-failover --replication-group-id outrena-prod --node-group-id 0001`
3. The backend will retry Redis ops with exponential backoff (configured in
   `app/core/cache.py`). Expect elevated latency for 30–60 seconds during
   failover.
4. If the entire cluster is unreachable, set `CACHE_ENABLED=false` env var
   on the backend to bypass the cache and serve directly from the DB. This
   is a degraded mode — expect 3–5x higher DB load.
5. Investigate root cause (memory pressure, network partition, AZ outage).

**Verification.** `redis-cli -h <primary> CLUSTER INFO` shows
`cluster_state:ok`. Backend metrics `outrena_redis_ops_total` resume normal
rate. Cache hit ratio recovers to >80% within 10 minutes.

**Rollback.** Re-enable cache: `CACHE_ENABLED=true` and redeploy. Monitor
for evictions.

### RB-08 — Process a Data Subject Request (DSR)

**Prerequisites.** DSR ticket submitted via the in-app form or
`privacy@outrena.com`; tenant admin or super-admin verified the requestor's
identity.

**Steps.**
1. Trigger the DSR pipeline:
   `POST /gdpr/dsr` with body `{"tenant_slug":"acme","subject_email":"jane@example.com","request_type":"export"}`
2. The Celery task `process_dsr` collects all PII for the subject across all
   tables in the tenant schema and the `public` schema.
3. For `request_type=export`, the task generates a JSON file and uploads it
   to `s3://outrena-dsr-exports/{tenant}/{subject_email}/{date}.json` with a
   pre-signed URL valid for 7 days.
4. For `request_type=delete`, the task anonymizes PII fields (sets
   `first_name=ANONYMIZED`, `last_name=ANONYMIZED`, `email=NULL`,
   `phone=NULL`) and preserves the row for audit purposes. The
   `anonymize_prospect` method in `PiiService` performs this.
5. Email the requestor with the export URL or the deletion confirmation.

**Verification.** `SELECT * FROM acme.prospects WHERE email='jane@example.com';`
returns 0 rows after deletion. DSR audit row in `public.platform_audit_log`
records the action.

**Rollback.** DSR deletions are irreversible. If a deletion was performed in
error, restore the prospect row from the daily backup (RB-06) — but the
original PII may already be overwritten in the backup window. Always verify
the requestor identity before deleting.

### RB-09 — Security Incident Response

**Prerequisites.** Security alert (WAF, CloudTrail anomaly, Sentry spike)
acknowledged; incident commander designated.

**Steps.**
1. **Contain.** If a tenant is compromised, suspend the tenant:
   `UPDATE public.tenants SET status='suspended' WHERE slug='acme';`
   Revoke the user's Keycloak session via the admin API. If a service is
   compromised, rotate its secrets immediately (DATABASE_URL,
   FERNET_KEY, STRIPE_SECRET_KEY).
2. **Investigate.** Pull CloudTrail, CloudWatch Logs, and audit log for the
   incident window. Use Loki queries (§13.3) to trace actor activity.
3. **Eradicate.** Remove malicious code, close the vulnerability, apply the
   patch (out-of-band if needed).
4. **Recover.** Restore affected data from backup if tampered with. Re-enable
   the tenant after verification.
5. **Report.** File an incident report within 24 hours. Notify affected
   tenants within 72 hours per GDPR Article 33 if personal data was breached.
6. **Post-mortem.** Publish a blameless post-mortem within 7 days with root
   cause, timeline, action items, and owners.

**Verification.** No further anomalous activity in CloudTrail for 7 days.
Affected tenant confirms normal operation. All action items tracked in
Jira.

**Rollback.** N/A — incident response is destructive by design.

### RB-10 — Scale Up a Service

**Prerequisites.** CloudWatch alarm `BackendHighLatencyP99` or
`WorkerQueueBacklog` sustained; capacity headroom in the ECS cluster / App
Service plan.

**Steps.**
1. Identify the bottleneck service from the Grafana Overview dashboard.
2. For ECS: increase the desired count:
   `aws ecs update-service --cluster outrena-prod --service outrena-backend-prod --desired-count 8`
3. For App Service: scale out via the portal or
   `az appservice plan update --name outrena-prod-plan --resource-group outrena-prod --number-of-workers 8`
4. For Kubernetes: `kubectl -n outrena-prod scale deployment outrena-backend --replicas=8`
   or rely on HPA by adjusting `minReplicas` in values.
5. Monitor for 15 minutes; if latency does not recover, scale the database
   read replicas or the Redis cluster (requires Terraform apply).

**Verification.** Grafana Overview shows latency p99 dropping below the SLO.
No new alarms. ECS service shows `running: 8, desired: 8`.

**Rollback.** Scale back down to the previous count. Ensure auto-scaling
policy still targets the original baseline.

### RB-11 — Debug a 5xx Spike

**Prerequisites.** Grafana Overview showing >1% 5xx rate; PagerDuty page
received.

**Steps.**
1. Filter Loki for 5xx in the last 15 minutes:
   `{app="outrena-backend"} |= "5xx" | json | status >= 500`
2. Identify the dominant error code and route. Pivot to traces via the
   `trace_id` field in the log line.
3. If the error is from a downstream (RDS, Redis, LLM provider), check that
   service's health dashboard first.
4. If the error is application-level (500 from an unhandled exception), pull
   the Sentry event for the stack trace.
5. If the error is from a recent deploy, follow RB-02 to roll back.
6. If the error is from a specific tenant (bad data, runaway loop), suspend
   the tenant per RB-09 step 1.

**Verification.** 5xx rate returns below 0.1% sustained for 10 minutes.
Sentry shows no new events.

**Rollback.** N/A — depends on root cause.

### RB-12 — Re-run a Failed Celery Task

**Prerequisites.** Task ID from the worker logs or the Flower dashboard.

**Steps.**
1. Identify the task in Flower (`https://worker-admin.outrena.internal:5555`)
   or via Redis: `redis-cli -n 1 LRQ celery:job:<task_id>`.
2. Check the exception traceback in Loki.
3. If the failure was transient (network, timeout), re-queue:
   `python -m app.worker.requeue <task_id>`
   This inspects the original args and kwargs and enqueues a fresh task.
4. If the failure was due to bad input, fix the input in the database and
   re-enqueue manually:
   `celery -A app.worker.celery_app call app.worker.tasks.send_campaign_email --args='[<campaign_id>, <prospect_id>]'`
5. Monitor the new task to completion in Flower.

**Verification.** Task reaches state `SUCCESS` in Flower. Downstream effect
(email sent, campaign advanced) visible in the tenant's UI.

**Rollback.** If the re-run produced an unintended side effect (duplicate
email sent), mark the original task as `REVOKED` in the audit log and
notify the tenant admin.

### RB-13 — Purge Data Per Retention Policy

**Prerequisites.** Retention policy specifies 90 days for
`email_send_logs`, 365 days for `platform_audit_log`, indefinite for
`campaigns` and `prospects` (unless tenant requests deletion).

**Steps.**
1. Run the nightly Celery beat task `purge_retention` manually:
   `celery -A app.worker.celery_app call app.worker.tasks.purge_retention`
2. The task iterates all tenant schemas and deletes rows older than the
   retention window. It runs in 1,000-row batches to avoid long locks.
3. For `platform_audit_log`, the task exports the to-be-deleted rows to S3
   before deletion (for compliance archives).
4. Vacuum the affected tables:
   `VACUUM (VERBOSE, ANALYZE) acme.email_send_logs;`

**Verification.** Row counts match the expected post-purge numbers. S3
compliance archive contains the deleted audit rows. Query performance on
the affected tables improves (visible in pg_stat_user_tables).

**Rollback.** Restore deleted rows from the S3 compliance archive (audit
log only — operational data is not archived).

### RB-14 — Add a New LLM Provider

**Prerequisites.** Provider API key acquired; provider added to
`PROVIDER_BASE_URLS` map in `app/services/llm_service.py`; deployment
scheduled.

**Steps.**
1. Add the provider to the `LLMProvider` enum and the `PROVIDER_BASE_URLS`
   constant. Add the provider's models to the `LLM_MODELS` registry.
2. Add the API key as a new secret in Secrets Manager:
   `outrena/prod/llm/<provider>_api_key`.
3. Add the secret ARN to the backend and worker task definitions.
4. Add the provider to the `IntegrationCredentialsService` catalog so
   tenants can manage per-tenant credentials.
5. Deploy the backend and worker.
6. In the tenant admin UI, verify the new provider appears in the
   integrations list and can be configured with a tenant-level key.

**Verification.** `GET /integrations/catalog` includes the new provider.
End-to-end test: a tenant creates an LLM call against the new provider and
receives a successful response.

**Rollback.** Remove the provider from the catalog (set
`is_active=false` in the platform credentials row). Existing tenant
configurations referencing the provider will return a clear error.

### RB-15 — Database Vacuum and Analyze

**Prerequisites.** Scheduled weekly maintenance window (Sunday 02:00 UTC);
`autovacuum` running normally but a manual `VACUUM FULL` is needed for
bloat recovery.

**Steps.**
1. Identify bloated tables:
   `SELECT relname, n_dead_tup, n_live_tup, last_autovacuum FROM pg_stat_user_tables WHERE n_dead_tup > 100000 ORDER BY n_dead_tup DESC;`
2. For routine maintenance, run `VACUUM (VERBOSE, ANALYZE)` on each tenant
   schema. This does not lock tables.
3. For severely bloated tables, schedule `VACUUM FULL` during a maintenance
   window. This acquires an `ACCESS EXCLUSIVE` lock — the table is
   unavailable during the operation. Run on the read replicas first, then
   promote one to primary.
4. After `VACUUM FULL`, run `REINDEX TABLE CONCURRENTLY` on indexes that
   show high bloat.
5. Update planner statistics: `ANALYZE` on all tenant tables.

**Verification.** `pg_stat_user_tables.n_dead_tup` returns to near-zero.
Query plans in `EXPLAIN ANALYZE` show no seq scans where index scans are
expected. Database disk usage drops if bloat was significant.

**Rollback.** N/A — `VACUUM` is safe and non-destructive. `VACUUM FULL`
requires a table rewrite but does not lose data. If a maintenance window is
aborted mid-`VACUUM FULL`, the table is unchanged (the operation is
transactional at the table level).

---

## 19. Disaster Recovery

OUTRENA's disaster recovery posture targets an RPO of 5 minutes and an RTO of
30 minutes for full regional outage. The DR region (us-west-2 on AWS,
paired region on Azure) runs a warm standby: full Terraform-provisioned
infrastructure with the backend scaled to 0, the database as a cross-region
read replica, and the Redis cluster provisioned but idle.

| Component | RPO | RTO | Strategy |
|---|---|---|---|
| PostgreSQL (app DB) | 5 min | 15 min | Cross-region async replica; promote on DR |
| Redis cache | n/a (cache) | 5 min | Rebuild from cold; no persistence required |
| S3 / Blob storage | 0 (cross-region) | 5 min | Cross-region replication enabled |
| Secrets Manager / Key Vault | 0 | 5 min | Replicated automatically by cloud provider |
| Container images (ECR / ACR) | 0 | 5 min | Cross-region replication |
| Terraform state | 0 | 5 min | S3 bucket with cross-region replication + versioning |
| Keycloak DB | 5 min | 15 min | Cross-region replica of Keycloak DB |
| PostHog | 1 hr | 1 hr | Best-effort; events buffered client-side |

### 19.1 DR Drill

A DR drill runs monthly. The procedure:

1. Promote the us-west-2 read replica to primary:
   `aws rds promote-read-replica --db-instance-identifier outrena-prod-dr`
2. Update Route 53 to point `api.outrena.com` at the us-west-2 ALB.
3. Scale the us-west-2 ECS services from 0 to the prod desired count.
4. Verify smoke tests pass.
5. Record actual RTO and RPO; file a drill report.
6. Fail back to us-east-1 by re-establishing the replica in the opposite
   direction.

### 19.2 Regional Outage Procedure

On confirmation of a regional outage in the primary region:

1. Incident commander declares DR activation.
2. SRE on call promotes the read replica in the DR region.
3. SRE updates Route 53 (or Azure Traffic Manager) to fail over to the DR
   ALB.
4. SRE scales ECS / App Service instances up to prod desired.
5. SRE verifies health endpoints and smoke tests.
6. Communications team notifies tenants of degraded performance during the
   failover.
7. After the primary region recovers, schedule a failback in a maintenance
   window — never fail back mid-incident.

---

## 20. Cost Optimization

OUTRENA's cost profile is dominated by the database (RDS / Flexible Server,
~35% of monthly spend), the ECS / App Service compute (frontend, backend,
workers, ~30%), the Redis cluster (~10%), Cloudflare + ALB / App Gateway
egress (~10%), observability (CloudWatch / Azure Monitor + Grafana Cloud,
~10%), and S3 / Blob storage + backups (~5%). The actions below reduce
spend without compromising the SLOs.

| Lever | Saving | Risk | Notes |
|---|---|---|---|
| RDS Reserved Instances (1-yr, all upfront) | 30–40% on DB | Low | Predictable baseline |
| ECS Fargate Savings Plans | 40–50% on compute | Low | Cover 80% of baseline |
| ElastiCache Reserved Nodes | 30–40% on Redis | Low | Predictable baseline |
| Right-size idle replicas | 10–15% on DB | Medium | Drop to 1 replica off-peak |
| Graviton (arm64) for Fargate | 20% on compute | Low | Multi-arch images already built |
| S3 Intelligent-Tiering on exports | 15–25% on storage | Low | Auto-tier by access pattern |
| S3 Glacier on backups >30 days | 60% on backup storage | Medium | Restore takes 3–5 hours |
| CloudFront / Cloudflare caching | 5–10% on egress | Low | Static assets already cached |
| Scale workers to 0 off-peak | 15–20% on worker compute | Medium | KEDA on queue depth |
| Spot instances for worker tier | 60% on worker compute | Medium | K8s only; not Fargate |
| Log retention 90 → 60 days | 15% on CloudWatch | Low | Compliance permits |
| Lower dev/staging instance classes | 50% on non-prod | Low | dev = t3.medium, staging = t3.large |

### 20.1 Right-Sizing

Quarterly right-sizing review: pull CloudWatch metrics for the last 30 days
and compare `max(CPU)` and `max(memory)` against the provisioned capacity.
Any service running at <40% CPU and <50% memory for 30 days is a candidate
for downsizing. Any database with <40% CPU utilization for 30 days is a
candidate for a smaller instance class.

### 20.2 Reserved and Savings Plans

OUTRENA's baseline is predictable (4 backend + 4 worker tasks minimum, 1
RDS primary + 2 replicas, 6 Redis nodes). Reserving this baseline on a
1-year term with all-upfront payment yields 30–40% savings vs. on-demand.
Savings Plans cover the elastic portion above the baseline with 40–50%
savings and the flexibility to shift between instance families.

### 20.3 Storage Lifecycle

S3 / Blob storage for exports and attachments uses Intelligent-Tiering with
a lifecycle rule that transitions objects to Glacier Instant Retrieval after
60 days and Glacier Deep Archive after 180 days. Backups use the same
lifecycle. The total storage cost savings is ~25% with no observable impact
on user-facing latency (most exports are downloaded within 7 days of
generation).

### 20.4 Cost Alerts

Budgets are set at 80%, 90%, and 100% of the monthly forecast. The 80%
alert emails the team; the 90% alert pages the on-call SRE; the 100% alert
opens an incident. Anomaly detection on daily spend triggers a separate
alert if daily spend exceeds the trailing 30-day average by 30%.

---

**End of Deployment Guide.** For cross-references, see
`04-Technical-Documentation.md` for architecture deep-dives,
`05-Developer-Guide.md` for local setup, and `runbooks/` for the standalone
runbook files. File issues against the `deployment` label for any procedure
that does not match observed behavior.
