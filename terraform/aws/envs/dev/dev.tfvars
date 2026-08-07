# envs/dev/dev.tfvars — dev environment overrides.
#
# Dev is the cheapest viable stack: single-AZ RDS, non-cluster Redis, no NAT
# GW (Fargate tasks get public IPs for ECR pull + LLM/MailBridge egress).
# SKIP_JWT_VERIFICATION is ALLOWED to be true in dev (auth bypass for local
# E2E testing) — but defaults to false here to match prod behavior.

# ── Global ────────────────────────────────────────────────────────────────────
environment       = "development"
environment_short = "dev"
base_domain       = "outrena.dev"
aws_region        = "us-east-1"

# ── Networking ────────────────────────────────────────────────────────────────
# Dev: single AZ is enough; saves cost. NAT GW off — Fargate uses public IPs.
availability_zones = ["us-east-1a", "us-east-1b"] # 2 AZs minimum for ALB
enable_nat_gateway = false
single_nat_gateway = false

# ── ECS sizing (smallest viable) ──────────────────────────────────────────────
backend_task_cpu      = 512  # 0.5 vCPU
backend_task_memory   = 1024 # 1 GB
backend_desired_count = 1    # single task — ALB still works, just no failover

frontend_task_cpu      = 256
frontend_task_memory   = 512
frontend_desired_count = 1

worker_task_cpu      = 512
worker_task_memory   = 1024
worker_desired_count = 1

keycloak_task_cpu      = 512
keycloak_task_memory   = 1024
keycloak_desired_count = 1

# ── RDS ───────────────────────────────────────────────────────────────────────
rds_instance_class        = "db.t4g.small" # 2 vCPU / 2 GB — smallest ARM
rds_allocated_storage     = 20
rds_max_allocated_storage = 50
rds_multi_az              = false
rds_backup_retention_days = 3
rds_deletion_protection   = false # allow teardown for cost

# ── Redis ─────────────────────────────────────────────────────────────────────
redis_node_type          = "cache.t3.micro" # 2 GB — enough for dev
redis_cluster_mode       = false
redis_num_cache_clusters = 1

# ── S3 ─────────────────────────────────────────────────────────────────────────
csv_bucket_name        = "outrena-dev-csv"
collateral_bucket_name = "outrena-dev-collateral"
alb_logs_bucket_name   = "outrena-dev-alb-logs"

# ── Logging ───────────────────────────────────────────────────────────────────
log_retention_days = 7

# ── WAF ───────────────────────────────────────────────────────────────────────
waf_rate_limit = 1000 # high limit in dev so load tests don't trip the WAF

# ── Blue/Green cutover ────────────────────────────────────────────────────────
# Dev: 100% new (FastAPI) — there's no legacy Next.js stack in dev.
blue_green_weight_new = 100
blue_green_weight_old = 0

# ── App config ────────────────────────────────────────────────────────────────
skip_jwt_verification  = false # keep false — only dev local docker-compose uses true
verify_jwt_issuer      = false
log_level              = "DEBUG"
scheduler_tick_seconds = 300
scheduler_partial_cap  = 5
allowed_origins        = "[\"http://localhost:5173\",\"http://localhost\",\"https://*.outrena.dev\"]"

# ── ECS deploy ─────────────────────────────────────────────────────────────────
assign_public_ip_to_fargate = true # no NAT GW in dev — needed for ECR pull
enable_kms_key_rotation     = true

# ── Alerting ──────────────────────────────────────────────────────────────────
alert_email = "ops@outrena.com"

# ── Images (CI overrides via -var) ────────────────────────────────────────────
backend_ecr_tag  = "latest"
frontend_ecr_tag = "latest"
keycloak_image   = "quay.io/keycloak/keycloak:24.0"
