# envs/staging/staging.tfvars — staging environment overrides.
#
# Staging mirrors prod topology (Multi-AZ, NAT GW) but on smaller instances.
# Blue/Green weights set to 50/50 for pre-prod validation of the new stack
# against real traffic split.

# ── Global ────────────────────────────────────────────────────────────────────
environment       = "staging"
environment_short = "stg"
base_domain       = "staging.outrena.dev"
aws_region        = "us-east-1"

# ── Networking ────────────────────────────────────────────────────────────────
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"] # 3 AZs for Multi-AZ RDS
enable_nat_gateway = true
single_nat_gateway = true # one NAT GW for all 3 private subnets (cost saving)

# ── ECS sizing ────────────────────────────────────────────────────────────────
backend_task_cpu      = 1024 # 1 vCPU
backend_task_memory   = 2048 # 2 GB
backend_desired_count = 2    # 2 tasks — ALB failover works

frontend_task_cpu      = 512
frontend_task_memory   = 1024
frontend_desired_count = 2

worker_task_cpu      = 1024
worker_task_memory   = 2048
worker_desired_count = 2

keycloak_task_cpu      = 1024
keycloak_task_memory   = 2048
keycloak_desired_count = 2

# ── RDS ───────────────────────────────────────────────────────────────────────
rds_instance_class        = "db.t4g.medium" # 2 vCPU / 4 GB
rds_allocated_storage     = 50
rds_max_allocated_storage = 200
rds_multi_az              = true
rds_backup_retention_days = 7
rds_deletion_protection   = false # allow teardown for re-deploy

# ── Redis ─────────────────────────────────────────────────────────────────────
redis_node_type          = "cache.t3.small" # ~1.5 GB
redis_cluster_mode       = false            # non-cluster for cost; cluster in prod
redis_num_cache_clusters = 2                # primary + 1 replica (Multi-AZ)

# ── S3 ─────────────────────────────────────────────────────────────────────────
csv_bucket_name        = "outrena-staging-csv"
collateral_bucket_name = "outrena-staging-collateral"
alb_logs_bucket_name   = "outrena-staging-alb-logs"

# ── Logging ───────────────────────────────────────────────────────────────────
log_retention_days = 30

# ── WAF ───────────────────────────────────────────────────────────────────────
waf_rate_limit = 200 # tighter than dev, looser than prod

# ── Blue/Green cutover (pre-prod validation: 50/50 split) ─────────────────────
blue_green_weight_new = 50
blue_green_weight_old = 50

# ── App config ────────────────────────────────────────────────────────────────
skip_jwt_verification  = false # MUST be false in staging per pitfall #4
verify_jwt_issuer      = true
log_level              = "INFO"
scheduler_tick_seconds = 300
scheduler_partial_cap  = 5
allowed_origins        = "[\"https://*.staging.outrena.dev\"]"

# ── ECS deploy ─────────────────────────────────────────────────────────────────
assign_public_ip_to_fargate = false # NAT GW handles egress
enable_kms_key_rotation     = true

# ── Alerting ──────────────────────────────────────────────────────────────────
alert_email = "ops@outrena.com"

# ── Images ────────────────────────────────────────────────────────────────────
backend_ecr_tag  = "staging"
frontend_ecr_tag = "staging"
keycloak_image   = "quay.io/keycloak/keycloak:24.0"
