# envs/prod/prod.tfvars — production environment overrides.
#
# Production sizing per migration doc §11.3:
#   - RDS: db.r6g.large Multi-AZ, 35-day backups (PITR)
#   - Redis: cache.r6g.large cluster mode (3 shards × 1 replica)
#   - ECS: 2 tasks per service (minimum for ALB failover)
#   - 3 AZs with one NAT GW per AZ (no single point of egress failure)
#   - WAF rate limit 100 req/5min per IP (per migration doc §11.3 + cloudwatch.tf)
#   - Deletion protection on RDS (force `terraform apply -var rds_deletion_protection=false` to tear down)
#   - KMS key rotation enabled
#
# Blue/Green: starts at 5/95 (canary, Day 1 of cutover per §16.3). Operator
# ramps over 7 days: 5 → 25 → 50 → 100 via separate `terraform apply -var blue_green_weight_new=N`.

# ── Global ────────────────────────────────────────────────────────────────────
environment       = "production"
environment_short = "prd"
base_domain       = "outrena.com"
aws_region        = "us-east-1"

# ── Networking ────────────────────────────────────────────────────────────────
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"] # 3 AZs
enable_nat_gateway = true
single_nat_gateway = false # one NAT GW per AZ — no single point of egress failure

# ── ECS sizing ────────────────────────────────────────────────────────────────
backend_task_cpu      = 1024
backend_task_memory   = 2048
backend_desired_count = 2 # min 2 for ALB failover (could be 3+ for HA)

frontend_task_cpu      = 512
frontend_task_memory   = 1024
frontend_desired_count = 2

worker_task_cpu      = 1024
worker_task_memory   = 2048
worker_desired_count = 2 # could be 3-4 for higher scheduler throughput

keycloak_task_cpu      = 1024
keycloak_task_memory   = 2048
keycloak_desired_count = 2

# ── RDS (migration doc §11.3 sizing) ──────────────────────────────────────────
rds_instance_class        = "db.r6g.large" # 2 vCPU / 16 GB — memory-optimized for Postgres
rds_allocated_storage     = 100
rds_max_allocated_storage = 1000 # headroom for growth
rds_multi_az              = true
rds_backup_retention_days = 35   # PITR per migration doc
rds_deletion_protection   = true # MUST stay true — flip to false only for planned teardown
rds_final_snapshot_name   = "outrena-rds-prod-final"

# ── Redis (migration doc §11.3: cluster mode 3 shards × 1 replica) ───────────
redis_node_type          = "cache.r6g.large"
redis_cluster_mode       = true
redis_shard_count        = 3
redis_num_cache_clusters = 2 # 1 primary + 1 replica per shard

# ── S3 ─────────────────────────────────────────────────────────────────────────
csv_bucket_name        = "outrena-prod-csv"
collateral_bucket_name = "outrena-prod-collateral"
alb_logs_bucket_name   = "outrena-prod-alb-logs"

# ── Logging ───────────────────────────────────────────────────────────────────
log_retention_days = 90 # 90 days for compliance + post-mortem analysis

# ── WAF (migration doc §11.3: 100 req/5min per IP) ────────────────────────────
waf_rate_limit = 100

# ── Blue/Green cutover (Day 1 canary per §16.3) ──────────────────────────────
blue_green_weight_new = 5 # canary — monitor error rates for 24h
blue_green_weight_old = 95

# ── App config ────────────────────────────────────────────────────────────────
skip_jwt_verification  = false # MUST be false in prod — pitfall #4
verify_jwt_issuer      = true
log_level              = "INFO" # DEBUG in prod is too noisy + leaks PII
scheduler_tick_seconds = 300
scheduler_partial_cap  = 10 # higher cap in prod for more throughput per tick
allowed_origins        = "[\"https://*.outrena.com\",\"https://outrena.com\"]"

# ── ECS deploy ─────────────────────────────────────────────────────────────────
assign_public_ip_to_fargate = false # private-only via NAT GW
enable_kms_key_rotation     = true

# ── Alerting ──────────────────────────────────────────────────────────────────
alert_email = "ops@outrena.com" # override to a PagerDuty email in real prod

# ── Images (immutable tags — CI pushes sha-<git-sha>) ─────────────────────────
backend_ecr_tag  = "sha-placeholder" # CI overrides via -var backend_ecr_tag=sha-abc123
frontend_ecr_tag = "sha-placeholder" # CI overrides via -var frontend_ecr_tag=sha-abc123
keycloak_image   = "quay.io/keycloak/keycloak:24.0"
