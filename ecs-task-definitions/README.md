# OUTRENA ECS Task Definitions — Operator Guide

This directory contains **portable JSON task definitions** for AWS ECS Fargate,
equivalent to the Terraform configs in `terraform/aws/ecs_*.tf`. They are
provided for teams who:

- Prefer the AWS Console / `aws ecs` CLI over Terraform, OR
- Need to register task definitions in a different AWS account without
  re-running Terraform, OR
- Want a human-readable diff of what Terraform is producing.

## ⚠️ Source of Truth

**The Terraform configs in `terraform/aws/` are the source of truth.** This
JSON is a hand-maintained snapshot — if you change Terraform, regenerate these
by running `terraform show -json` and extracting the `container_definitions`
field, or just diff against `terraform/aws/ecs_*.tf` when reviewing PRs.

## Files

| File | Equivalent Terraform | Container |
|---|---|---|
| `backend.json` | `terraform/aws/ecs_backend.tf` | FastAPI uvicorn on port 8000 |
| `frontend.json` | `terraform/aws/ecs_frontend.tf` | nginx on port 80 (Vite build) |
| `worker.json` | `terraform/aws/ecs_worker.tf` | Celery worker (headless, no port) |
| `keycloak.json` | `terraform/aws/ecs_keycloak.tf` | Keycloak 24 on port 8080 |

## Usage

### 1. Replace placeholders

Every `PLACEHOLDER_*` token must be replaced with a real ARN / endpoint from
your AWS account. Search-and-replace:

| Placeholder | Replace with | How to find |
|---|---|---|
| `PLACEHOLDER_ECS_TASK_EXECUTION_ROLE_ARN` | `arn:aws:iam::<acct>:role/outrena-prod-ecs-task-execution` | `aws iam list-roles \| jq '.Roles[].RoleName' \| grep ecs-task-exec` |
| `PLACEHOLDER_BACKEND_TASK_ROLE_ARN` | `arn:aws:iam::<acct>:role/outrena-prod-backend-task` | `aws iam list-roles \| jq '.Roles[].RoleName' \| grep outrena-prod-backend` |
| `PLACEHOLDER_FRONTEND_TASK_ROLE_ARN` | (same pattern) | |
| `PLACEHOLDER_WORKER_TASK_ROLE_ARN` | (same pattern) | |
| `PLACEHOLDER_KEYCLOAK_TASK_ROLE_ARN` | (same pattern) | |
| `PLACEHOLDER_ECR_REPO_URL` | `<acct>.dkr.ecr.us-east-1.amazonaws.com/outrena` | `aws ecr describe-repositories` |
| `PLACEHOLDER_DATABASE_URL_SECRET_ARN` | `arn:aws:secretsmanager:us-east-1:<acct>:secret:outrena/prod/database-url-XXXXXX` | `aws secretsmanager list-secrets` |
| `PLACEHOLDER_REDIS_AUTH_SECRET_ARN` | (same pattern) | |
| `PLACEHOLDER_MAILBRIDGE_URL_SECRET_ARN` | (same pattern) | |
| `PLACEHOLDER_KEYCLOAK_ADMIN_SECRET_ARN` | (same pattern) | |
| `PLACEHOLDER_KEYCLOAK_DB_SECRET_ARN` | (same pattern) | |
| `PLACEHOLDER_ELASTICACHE_PRIMARY_ENDPOINT` | `master.outrena-prod-redis.xxxxxx.use1.cache.amazonaws.com` | `aws elasticache describe-replication-groups` |
| `PLACEHOLDER_RDS_ENDPOINT` | `outrena-prod.xxxxxx.us-east-1.rds.amazonaws.com` | `aws rds describe-db-instances` |

### 2. Register the task definition

Each JSON file includes top-level `_comment`, `_usage`, and `_notes` fields for
human readability. These are NOT part of the AWS ECS RegisterTaskDefinition
schema and must be stripped before registration. Use `jq` to strip them on the fly:

```bash
# Register backend (with metadata stripped):
jq 'del(._comment, ._usage, ._notes)' backend.json | \
  aws ecs register-task-definition \
    --cli-input-json file:///dev/stdin \
    --region us-east-1

# Or strip first, then register:
jq 'del(._comment, ._usage, ._notes)' backend.json > backend.clean.json
aws ecs register-task-definition \
  --cli-input-json file://backend.clean.json \
  --region us-east-1
```

Repeat for frontend, worker, keycloak. The output includes the new revision
number — note it for step 3.

### 3. Create the ECS service

Either via the AWS Console (ECS → cluster → Services → Create) or via CLI:

```bash
aws ecs create-service \
  --cluster outrena-prod \
  --service-name outrena-prod-backend \
  --task-definition outrena-prod-backend:<REVISION> \
  --desired-count 3 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy,subnet-zzz],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=backend,containerPort=8000" \
  --deployment-configuration "maximumPercent=200,minimumHealthyPercent=100,deploymentCircuitBreaker={enable=true,rollback=true}" \
  --enable-execute-command \
  --region us-east-1
```

### 4. Verify

```bash
# Service stable:
aws ecs describe-services \
  --cluster outrena-prod \
  --services outrena-prod-backend \
  --query 'services[0].{status:status,running:runningCount,desired:desiredCount,deployments:deployments[*].{status:status,running:runningCount,desired:desiredCount,rollout:rolloutState}}'

# Tasks healthy:
aws ecs describe-tasks \
  --cluster outrena-prod \
  --tasks $(aws ecs list-tasks --cluster outrena-prod --service-name outrena-prod-backend --query 'taskArns[*]' --output text) \
  --query 'tasks[*].{id:taskArn,health:healthStatus,last:lastStatus,containers:containers[*].{name:name,last:lastStatus,health:healthStatus}}'

# Health endpoint (via ALB):
curl -fsS https://api.outrena.com/health | jq .
```

## Key fields per task definition

| Field | backend | frontend | worker | keycloak |
|---|---|---|---|---|
| `cpu` | 1024 (1 vCPU) | 256 (0.25 vCPU) | 1024 (1 vCPU) | 1024 (1 vCPU) |
| `memory` | 2048 (2 GB) | 512 (0.5 GB) | 2048 (2 GB) | 2048 (2 GB) |
| `containerPort` | 8000 | 80 | (none) | 8080 |
| `healthCheck` | `curl /health` | `curl /` | (none — PID 1 liveness) | `curl /auth/realms/master` |
| `enable_execute_command` (service-level) | true | false | true | true |

## Updating

When you bump a container image tag, either:

1. **Re-run Terraform** (preferred): edit `var.backend_ecr_tag` in `terraform/aws/envs/prod/prod.tfvars` and `terraform apply`. Terraform registers a new task def revision and updates the service.

2. **Register a new revision manually**:
   ```bash
   # Edit backend.json — bump image tag at the end:
   #   "image": ".../backend:1.0.1"
   aws ecs register-task-definition --cli-input-json file://backend.json
   # Then update the service:
   aws ecs update-service \
     --cluster outrena-prod \
     --service outrena-prod-backend \
     --task-definition outrena-prod-backend:<NEW_REVISION>
   ```

## Cross-references

- **`terraform/aws/ecs_backend.tf`** — source of truth (backend)
- **`terraform/aws/ecs_frontend.tf`** — source of truth (frontend)
- **`terraform/aws/ecs_worker.tf`** — source of truth (worker)
- **`terraform/aws/ecs_keycloak.tf`** — source of truth (keycloak)
- **`terraform/aws/secrets.tf`** — Secrets Manager secret definitions
- **`terraform/aws/iam.tf`** — executionRole + taskRole IAM policies
- **Migration doc §10** — CI/CD pipeline (this is the AWS leg)
- **Migration doc §13.1** — env-var list (mirrored in the JSON `environment` blocks)
- **`k8s/outrena/`** — alternative Kubernetes deployment (same app, different orchestrator)
- **`docker-compose.prod.yml`** — single-VM alternative
