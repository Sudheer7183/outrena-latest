# OUTRENA on Kubernetes — Operator Guide

This guide covers deploying OUTRENA Phase 6 to a Kubernetes cluster using the
Helm chart in `k8s/outrena/`. The chart is an ALTERNATIVE to the AWS ECS /
Azure Container Apps Terraform configs in `terraform/aws/` and
`terraform/azure/` — pick whichever matches your org's existing infrastructure.

## Prerequisites

Install on your workstation:

- `kubectl` ≥ 1.27 — https://kubernetes.io/docs/tasks/tools/
- `helm` ≥ 3.12 — https://helm.sh/docs/intro/install/
- `psql` (optional, for ad-hoc DB queries)

Install in the cluster (one-time, by cluster admin):

| Component | Purpose | Install |
|---|---|---|
| **ingress-nginx** | L7 ingress controller, terminates HTTP at the edge | `helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace` |
| **cert-manager** | Issues TLS certs via Let's Encrypt (or internal CA) | `helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set crds.enabled=true` |
| **ClusterIssuer** | Tells cert-manager which ACME account + solver to use | See `letsencrypt-prod` example below |
| **External Postgres** | Managed PG (RDS / CloudSQL / PG-Flexible / Aurora) | Reachable from the cluster's VPC/subnet |
| **External Redis** | Managed Redis (ElastiCache / Memorystore / Redis-Flexible) | Reachable from the cluster's VPC/subnet |
| **Secrets Store CSI driver** (optional) | Mounts AWS Secrets Manager / Azure Key Vault secrets as files | `helm install csi-secrets-store secrets-store-csi-driver/secrets-store-csi-driver -n kube-system` |
| **AWS Provider for CSI** (optional) | AWS-specific CSI driver provider | `kubectl apply -f https://raw.githubusercontent.com/aws/secrets-store-csi-driver-provider-aws/main/deployment/aws-provider-installer.yaml` |

Sample `ClusterIssuer` for Let's Encrypt:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: platform@outrena.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
```

## Deploy

```bash
# 1. Create namespace
kubectl create namespace outrena-prod

# 2. Provision secrets (one of):
#    a. Plain K8s Secret:
kubectl create secret generic outrena-backend-secret -n outrena-prod \
  --from-literal=DATABASE_URL='postgresql+asyncpg://...' \
  --from-literal=REDIS_AUTH_TOKEN='...' \
  --from-literal=KEYCLOAK_ADMIN_PASSWORD='...' \
  --from-literal=MAILBRIDGE_DEFAULT_URL='...'

kubectl create secret generic outrena-keycloak-secret -n outrena-prod \
  --from-literal=KEYCLOAK_ADMIN_PASSWORD='...' \
  --from-literal=KC_DB_USERNAME='keycloak' \
  --from-literal=KC_DB_PASSWORD='...'

kubectl create secret generic outrena-postgres-secret -n outrena-prod \
  --from-literal=DATABASE_URL='postgresql+asyncpg://...'

kubectl create secret generic outrena-redis-secret -n outrena-prod \
  --from-literal=REDIS_AUTH_TOKEN='...'

#    b. External Secrets Operator (recommended for prod) — out of scope here.
#    c. Sealed Secrets — out of scope here.

# 3. Create image pull secret (if using a private registry):
kubectl create secret docker-registry regcred -n outrena-prod \
  --docker-server=ghcr.io \
  --docker-username=<user> \
  --docker-password=<pat>

# 4. Install the chart (prod):
helm install outrena ./k8s/outrena \
  -f k8s/outrena/values.yaml \
  -f k8s/outrena/values-prod.yaml \
  -n outrena-prod

# 5. Watch rollout:
kubectl rollout status deploy/outrena-backend -n outrena-prod
kubectl rollout status deploy/outrena-frontend -n outrena-prod
kubectl rollout status deploy/outrena-keycloak -n outrena-prod
kubectl rollout status deploy/outrena-worker -n outrena-prod
```

## Run database migrations

Per §15.1 of the migration doc, migrations are idempotent and safe to re-run.
The chart's `backend.migration.enabled` flag toggles an init container that
runs `alembic upgrade head` on every backend pod startup. In prod, we leave
this DISABLED (default) and run migrations as an explicit step:

```bash
# Pick any backend pod
BACKEND_POD=$(kubectl get pod -n outrena-prod \
  -l app.kubernetes.io/name=backend \
  -o jsonpath='{.items[0].metadata.name}')

# Run alembic upgrade head (idempotent)
kubectl exec -n outrena-prod "$BACKEND_POD" -- alembic upgrade head

# Verify schema-per-tenant invariant (§14 Risk #17):
kubectl exec -n outrena-prod "$BACKEND_POD" -- \
  python -m app.scripts.verify_tenant_schemas
```

For the multi-tenant schema loop (one schema per tenant), see
`app/scripts/verify_tenant_schemas.py` in the backend repo.

## Verify

```bash
# All pods Running:
kubectl get pods -n outrena-prod -l app.kubernetes.io/part-of=outrena

# Backend /health (returns 200 iff DB + Redis + Keycloak reachable):
kubectl exec -n outrena-prod deploy/outrena-backend -- \
  curl -sS http://localhost:8000/health | jq .

# Keycloak realm ready:
kubectl exec -n outrena-prod deploy/outrena-keycloak -- \
  curl -sS http://localhost:8080/auth/realms/outrena/.well-known/openid-configuration | jq .issuer

# Frontend index served:
kubectl exec -n outrena-prod deploy/outrena-frontend -- \
  curl -sS -o /dev/null -w '%{http_code}\n' http://localhost/

# TLS certificate issued:
kubectl get certificate -n outrena-prod

# Ingress reachable from outside:
curl -fsS https://app.outrena.com/health
```

## Upgrade

```bash
# Update values or image tag (CI sets global.imageTag):
helm upgrade outrena ./k8s/outrena \
  -f k8s/outrena/values.yaml \
  -f k8s/outrena/values-prod.yaml \
  -n outrena-prod

# Watch rollout (zero-downtime per §16.3 — PDB minAvailable=2 + maxUnavailable=0):
kubectl rollout status deploy/outrena-backend -n outrena-prod
```

For blue/green (§16.3), deploy a parallel release with a different
`fullnameOverride` and shift traffic via two ingress objects weighted by
`nginx.ingress.kubernetes.io/canary-weight` annotations.

## Rollback

```bash
# List revisions:
helm history outrena -n outrena-prod

# Roll back to previous (revision 0 = previous):
helm rollback outrena 0 -n outrena-prod

# Or to a specific revision:
helm rollback outrena <REVISION> -n outrena-prod

# Watch the rollback:
kubectl rollout status deploy/outrena-backend -n outrena-prod
```

Helm rollback reverts the chart state, which triggers a Deployment rollout
back to the previous image + env. The PDB guarantees a backend pod stays
available throughout.

## Troubleshooting

| Symptom | First check | Likely cause |
|---|---|---|
| Backend pods `CrashLoopBackOff` | `kubectl logs <pod>` | DATABASE_URL wrong / RDS unreachable / VPC peering missing |
| Backend 500 on /health | `kubectl describe pod <pod>` then logs | Redis auth token mismatch / Keycloak down |
| Ingress 503 | `kubectl get endpoints -n outrena-prod` | Service has no backing pods (readinessProbe failing) |
| TLS cert stuck `Pending` | `kubectl describe certificate outrena-tls -n outrena-prod` | ClusterIssuer missing / DNS not pointing at ingress / rate limit |
| Keycloak 404 on /auth/realms/outrena | `kubectl logs deploy/outrena-keycloak` | Realm not provisioned — run `scripts/apply_realm_config.py` |
| Worker not consuming | `kubectl logs deploy/outrena-worker` | REDIS_HOST/PORT wrong / broker DB mismatch |
| HPA not scaling | `kubectl describe hpa outrena-backend -n outrena-prod` | Missing metrics-server / CPU requests not set |

## Cross-references

- **Migration doc §10** — CI/CD pipeline this chart implements
- **Migration doc §13.1** — canonical env-var list (mirrored in configmap.yaml)
- **Migration doc §14 Risk #17** — tenant isolation (networkpolicy.yaml)
- **Migration doc §15.1** — schema-per-tenant verification
- **Migration doc §16.3** — blue/green cutover (3 replicas + PDB minAvailable=2)
- **`terraform/aws/`** — alternative AWS ECS Fargate deployment (source of truth for AWS)
- **`terraform/azure/`** — alternative Azure Container Apps deployment
- **`docker-compose.prod.yml`** — single-VM alternative (no k8s)
- **`monitoring/`** — Prometheus / Grafana / Loki / OTel configs (deployable to this cluster)
