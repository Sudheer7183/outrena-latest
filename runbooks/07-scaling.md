---
title: Scaling Runbook (ECS / RDS / ElastiCache / Azure equivalents)
last_updated: 2025-01-15
severity: SEV-3
owner: OUTRENA SRE
---

# Scaling Runbook (ECS / RDS / ElastiCache + Azure equivalents)

Manual and autoscaling procedures for OUTRENA prod. Most scaling is done via Terraform
for auditability; the runbook documents both the Terraform path and the console path
(for urgent cases).

## Prerequisites

- Operator has prod deploy permission (Terraform Cloud or local `terraform apply` with
  prod creds).
- Change is tracked in a GitHub Issue or change-management ticket.
- For RDS instance-class changes: maintenance window scheduled unless urgent
  (`--apply-immediately` is a brief connection drop).
- For ElastiCache node-type changes: brief outage expected (~30 s per shard).

## AWS — ECS Fargate (Backend / Worker / Scheduler)

### Manual: bump desired_count

```bash
cd terraform/aws

# Edit the variable or pass on the CLI.
terraform plan  -var backend_desired_count=8 -out=tfplan
terraform apply tfplan

# Verify.
aws ecs describe-services --cluster outrena-prod --services outrena-backend \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}'
```

### Enable autoscaling (target tracking on CPU 70%)

Defined in `terraform/aws/ecs.tf` — module `aws_appautoscaling_target` +
`aws_appautoscaling_policy`. To enable for a service that does not have it:

```hcl
resource "aws_appautoscaling_target" "backend" {
  max_capacity       = 20
  min_capacity       = 4
  resource_id        = "service/outrena-prod/outrena-backend"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "backend_cpu" {
  name               = "backend-cpu-70"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 70.0
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
```

```bash
terraform plan -out=tfplan && terraform apply tfplan
```

### Add a new AZ

ECS Fargate tasks spread across AZs automatically if the subnets in the service's
`network_configuration` span AZs. To add a new AZ:

```bash
# 1. Confirm the VPC has a subnet in the target AZ (e.g. us-east-1e).
aws ec2 describe-subnets --filters Name=vpc-id,Values=<vpc-id> \
  --query 'Subnets[*].{AZ:AvailabilityZone,ID:SubnetId}' --output table

# 2. If missing, create it via terraform (terraform/aws/vpc.tf).
# 3. Add the subnet to the backend service's subnet list in terraform/aws/ecs.tf.
# 4. Apply.
terraform plan -out=tfplan && terraform apply tfplan

# 5. Force a redeploy to spread tasks across the new AZ.
aws ecs update-service --cluster outrena-prod --service outrena-backend \
  --force-new-deployment
```

## AWS — RDS (Postgres)

### Scale up instance class

```bash
# Urgent (brief connection drop, ~30 s):
aws rds modify-db-instance \
  --db-instance-identifier outrena-prod \
  --db-instance-class db.r6g.2xlarge \
  --apply-immediately

# Non-urgent (next maintenance window):
aws rds modify-db-instance \
  --db-instance-identifier outrena-prod \
  --db-instance-class db.r6g.2xlarge \
  --no-apply-immediately
# Apply during the next maintenance window (Sun 04:00 UTC by default).
```

> **⚠️ Warning:** Scaling **down** an RDS instance is not instant — storage cannot be
> shrunk at all, and instance-class downgrades require a maintenance-window reboot.
> Plan downgrades carefully; you cannot undo a storage increase.

### Scale storage

Auto-scaling is enabled (`terraform/aws/rds.tf` — `storage_autoscaling=true`,
`max_allocated_storage=2000`). To bump manually:

```bash
aws rds modify-db-instance \
  --db-instance-identifier outrena-prod \
  --allocated-storage 1500 \
  --apply-immediately
# Storage scaling is online; no outage.
```

Monitor `FreeStorageSpace` in CloudWatch; alert `rds-storage-low` fires at <10% free
(Risk #14).

## AWS — ElastiCache (Redis)

### Scale up node type (brief outage)

```bash
# 1. Snapshot the current cluster (safety net).
aws elasticache create-snapshot --cache-cluster-id outrena-prod \
  --snapshot-name outrena-prod-pre-scale-$(date +%Y%m%d%H%M)

# 2. Modify the node type. This triggers a node replacement — ~30 s per shard.
aws elasticache modify-cache-cluster \
  --cache-cluster-id outrena-prod \
  --cache-node-type cache.r6g.2xlarge \
  --apply-immediately

# 3. Wait for status "available".
aws elasticache describe-cache-clusters --cache-cluster-id outrena-prod \
  --query 'CacheClusters[0].CacheClusterStatus'
```

> **⚠️ Warning:** Node replacement causes a brief outage (30 s to a few minutes). For
> multi-AZ, failover takes one AZ at a time. Schedule during a low-traffic window and
> notify on-call. If Redis is the session store, some users may need to re-login.

## Azure — Container Apps

### Manual: bump min/max replicas

```bash
cd terraform/azure

# Edit the var or pass on the CLI.
terraform plan  -var backend_min_replicas=4 -var backend_max_replicas=20 -out=tfplan
terraform apply tfplan

# Verify.
az containerapp show --name outrena-backend-prod \
  --resource-group outrena-prod-rg \
  --query 'properties.template.scale'
```

### Autoscaling

Container Apps supports HTTP-based + CPU-based autoscaling rules natively. Defined in
`terraform/azure/container_apps.tf`:

```hcl
scale {
  min_replicas = 4
  max_replicas = 20

  rule {
    name = "cpu"
    custom {
      type = "cpu"
      metadata = {
        type  = "Utilization"
        value = "70"
      }
    }
  }
}
```

## Azure — PG Flexible (Postgres)

### Scale up SKU

```bash
az postgres flexible-server update \
  --name outrena-pg-prod \
  --resource-group outrena-prod-rg \
  --sku-name Standard_D8ds_v5 \
  --tier GeneralPurpose
# Online for most SKU changes; brief reconnect possible.
```

### Scale storage

```bash
az postgres flexible-server update \
  --name outrena-pg-prod \
  --resource-group outrena-prod-rg \
  --storage-size 1536
# Storage scaling is online; no outage.
```

## Azure — Redis

```bash
az redis update \
  --name outrena-redis-prod \
  --resource-group outrena-prod-rg \
  --sku-family P \
  --sku-capacity 3
# Requires a node replacement; brief outage. Same caveats as AWS ElastiCache.
```

## Cost Optimization

### Spot instances for workers

The Celery worker pool is bursty (autopilot runs). Use Fargate Spot for the worker
service:

```hcl
# terraform/aws/ecs.tf
resource "aws_ecs_service" "worker" {
  # ...
  capacity_provider_strategy {
    capacity_provider = "FargateSpot"
    weight            = 100
  }
  capacity_provider_strategy {
    capacity_provider = "Fargate"
    weight            = 0
    base              = 2   # keep 2 on-demand for stability
  }
}
```

> **⚠️ Warning:** Spot tasks can be terminated with 2 min warning. The worker must
> handle `SIGTERM` cleanly (drain in-flight tasks). Verified by `tests/e2e/test_worker_spot.py`.

### Scheduled scaling (scale down nights/weekends in staging)

```hcl
# terraform/aws/scheduled_scaling.tf
resource "aws_appautoscaling_scheduled_action" "staging_night" {
  count              = var.environment == "staging" ? 1 : 0
  name               = "staging-scale-down-night"
  service_namespace  = "ecs"
  resource_id        = "service/outrena-staging/outrena-backend"
  scalable_dimension = "ecs:service:DesiredCount"
  schedule           = "cron(0 22 * * ? *)"   # 22:00 UTC daily
  scalable_target_action {
    min_capacity = 0
    max_capacity = 0
  }
}

resource "aws_appautoscaling_scheduled_action" "staging_morning" {
  count              = var.environment == "staging" ? 1 : 0
  name               = "staging-scale-up-morning"
  service_namespace  = "ecs"
  resource_id        = "service/outrena-staging/outrena-backend"
  scalable_dimension = "ecs:service:DesiredCount"
  schedule           = "cron(0 12 * * ? *)"   # 12:00 UTC daily
  scalable_target_action {
    min_capacity = 2
    max_capacity = 8
  }
}
```

### Right-size RDS

Use the CloudWatch `outrena-cost` dashboard's RDS widget — if `DatabaseConnections`
averages <25% of `max_connections` and CPU averages <40% over 14 days, consider a
smaller instance class. Aurora Serverless v2 is a good option for dev/staging.

### ElastiCache node type tiering

- **dev:** `cache.t3.micro` (5 GB, no HA)
- **staging:** `cache.t3.small` (replica)
- **prod:** `cache.r6g.2xlarge` (multi-AZ)

### NAT Gateway

- **dev:** no NAT Gateway (use VPC endpoints only)
- **staging:** single NAT Gateway
- **prod:** one NAT Gateway per AZ for HA

### S3 lifecycle rules

```hcl
# terraform/aws/s3.tf
lifecycle_rule {
  enabled = true
  transition {
    days          = 30
    storage_class = "STANDARD_IA"
  }
  transition {
    days          = 90
    storage_class = "GLACIER"
  }
  transition {
    days          = 365
    storage_class = "DEEP_ARCHIVE"
  }
}
```

## Verification

After any scaling change:

```bash
# 1. Service is healthy.
aws ecs describe-services --cluster outrena-prod --services outrena-backend \
  --query 'services[0].{desired:desiredCount,running:runningCount,deployments:deployments[*].{status:status,running:runningCount}}'

# 2. RDS / Redis endpoint unchanged (scaling does not change endpoints).
psql -h prod-rds.outrena.internal -c "SELECT 1;"
redis-cli -h <redis-endpoint> PING

# 3. Grafana outrena-overview — no error-rate spike, latency stable.

# 4. For autoscaling: trigger a load test to verify scale-out works.
#    (k6: k6 run --vus 100 --duration 5m tests/load/backend_smoke.js)
```

## Rollback

- **ECS desired_count / replicas:** re-apply Terraform with the previous value.
- **RDS instance class:** re-apply with the previous class (maintenance window for
  downgrades).
- **RDS storage:** cannot be reduced. Plan increases carefully.
- **ElastiCache / Azure Redis node type:** re-apply with the previous type (another
  brief outage).
- **PG Flexible SKU:** re-apply with the previous SKU.

For all: confirm via the same verification steps above.

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| Terraform apply fails with state lock | SRE lead — check Terraform Cloud workspace | Within 1 hr |
| RDS instance-class change stuck >30 min | DBA + AWS support | SEV-2 |
| ElastiCache node replacement stuck >10 min | SRE lead + AWS support | SEV-2 |
| Scale-up does not resolve the original alert | SRE lead — likely not a capacity issue | Within 30 min |
| Spot task terminations causing worker backlog | SRE lead — increase on-demand `base` | Same business day |
| Autoscaling not triggering under load | SRE lead — check CloudWatch metric + policy | Within 1 hr |

## Related

- `02-schema-migration.md` — schema changes often coincide with scaling.
- `10-cost-management.md` — cost implications of scaling decisions.
- `monitoring/aws/cloudwatch-dashboards/outrena-cost.json` — cost dashboard.
- Migration doc §10 (Phase 6 deliverables), §14 Risk #22 (cost overrun).
