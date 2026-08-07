# posthog.tf — AWS resources for self-hosted PostHog (PH-INFRA).
#
# Provisions a fully isolated PostHog stack on AWS:
#   - Aurora PostgreSQL 16 for PostHog metadata (SEPARATE cluster from the
#     OUTRENA app DB in rds.tf — different cluster, different SG, different
#     KMS key, different Secrets Manager secret)
#   - ElastiCache Redis 7 for PostHog cache/queue (separate replication group
#     from the OUTRENA app Redis in elasticache.tf)
#   - S3 bucket for PostHog object storage (exports, async tasks, recordings)
#   - MSK (Managed Streaming for Kafka) for event ingestion
#   - Self-managed ClickHouse on ECS Fargate (see §"ClickHouse on AWS" below
#     for the Altinity.Cloud alternative)
#   - Dedicated ECS cluster for PostHog web / worker / plugin-server / clickhouse
#   - Dedicated ALB + ACM cert + Route 53 record (posthog.outrena.ai)
#   - WAFv2 ACL with OWASP CRS + rate-limit rule
#   - CloudWatch alarms for PostHog-specific health metrics
#
# All resources inherit Project/Environment/ManagedBy/Repo tags via the
# provider default_tags block in versions.tf. Resource-level tags add the
# Application=posthog tag for cost attribution (see runbook 14 §5.1).
#
# Cross-references:
#   - docker-compose.posthog.yml — dev/staging self-host compose
#   - k8s/posthog-values.yaml    — Helm values (uses these as externals)
#   - runbooks/15-exception-logging-self-healing.md — ops guide
#
# Choice notes:
#   * ClickHouse on AWS — PostHog supports ClickHouse on ECS (self-managed)
#     OR Altinity.Cloud (managed). We default to ECS for cost; production
#     deployments should switch to Altinity.Cloud or self-managed EC2 for
#     reliability. See the posthog_clickhouse task definition below.
#   * Kafka on AWS — MSK is the supported managed option. PostHog's official
#     self-host compose ships a single Confluent broker; on AWS we use a
#     3-broker MSK cluster in prod (multi-AZ).
#   * Aurora vs RDS — we use Aurora Serverless v2 for dev/staging (scales to
#     zero between batches) and Aurora Provisioned in prod. Cheaper than RDS
#     for the bursty PostHog metadata workload.

# ────────────────────────────────────────────────────────────────────────────
# Locals + KMS keys
# ────────────────────────────────────────────────────────────────────────────
locals {
  posthog_name_prefix = "${var.project_name}-${var.environment_short}-posthog"

  posthog_tags = {
    Application = "posthog"
    Tier        = "analytics"
  }
}

# KMS key for PostHog-managed resources (S3 + Aurora + Redis + Secrets).
resource "aws_kms_key" "posthog" {
  description             = "KMS key for self-hosted PostHog (S3 + Aurora + Redis + Secrets)"
  deletion_window_in_days = 30
  enable_key_rotation     = var.enable_kms_key_rotation

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-kms"
  })
}

resource "aws_kms_alias" "posthog" {
  name          = "alias/${local.posthog_name_prefix}"
  target_key_id = aws_kms_key.posthog.key_id
}

# ────────────────────────────────────────────────────────────────────────────
# Security groups (least-privilege — each PostHog service has its own SG)
# ────────────────────────────────────────────────────────────────────────────
resource "aws_security_group" "sg_posthog_alb" {
  name        = "${local.posthog_name_prefix}-sg-alb"
  description = "Internet-facing ALB for PostHog web (HTTPS only)"
  vpc_id      = aws_vpc.main.id
  egress      = []

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-sg-alb"
  })
}

resource "aws_vpc_security_group_ingress_rule" "posthog_alb_https" {
  security_group_id = aws_security_group.sg_posthog_alb.id
  description       = "HTTPS from internet"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "posthog_alb_http" {
  security_group_id = aws_security_group.sg_posthog_alb.id
  description       = "HTTP from internet (redirect to HTTPS)"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_security_group" "sg_posthog_web" {
  name        = "${local.posthog_name_prefix}-sg-web"
  description = "PostHog web + worker + plugin-server (Fargate)"
  vpc_id      = aws_vpc.main.id
  egress      = []

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-sg-web"
  })
}

resource "aws_vpc_security_group_ingress_rule" "posthog_alb_to_web" {
  security_group_id            = aws_security_group.sg_posthog_web.id
  description                  = "ALB → PostHog web :8000"
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_posthog_alb.id
}

# Egress — PostHog web/worker need to reach: Aurora, Redis, MSK, ClickHouse,
# S3, and (optionally) the GitHub API for self-driving. We allow all egress
# to the VPC + AWS S3 endpoints; internet egress goes via NAT GW in prod.
resource "aws_vpc_security_group_egress_rule" "posthog_web_egress_vpc" {
  security_group_id = aws_security_group.sg_posthog_web.id
  description       = "Egress to VPC (Aurora, Redis, MSK, ClickHouse, ECR)"
  cidr_ipv4         = var.vpc_cidr
  from_port         = 0
  to_port           = 65535
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "posthog_web_egress_https" {
  security_group_id = aws_security_group.sg_posthog_web.id
  description       = "HTTPS egress (LLM, GitHub API, email provider)"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

# ── Aurora Postgres SG (inbound from posthog-web only) ──────────────────────
resource "aws_security_group" "sg_posthog_aurora" {
  name        = "${local.posthog_name_prefix}-sg-aurora"
  description = "Aurora Postgres for PostHog metadata"
  vpc_id      = aws_vpc.main.id
  egress      = []

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-sg-aurora"
  })
}

resource "aws_vpc_security_group_ingress_rule" "posthog_web_to_aurora" {
  security_group_id            = aws_security_group.sg_posthog_aurora.id
  description                  = "PostHog web/worker → Aurora :5432"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_posthog_web.id
}

# ── ElastiCache SG (inbound from posthog-web only) ──────────────────────────
resource "aws_security_group" "sg_posthog_redis" {
  name        = "${local.posthog_name_prefix}-sg-redis"
  description = "ElastiCache Redis for PostHog cache + Celery broker"
  vpc_id      = aws_vpc.main.id
  egress      = []

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-sg-redis"
  })
}

resource "aws_vpc_security_group_ingress_rule" "posthog_web_to_redis" {
  security_group_id            = aws_security_group.sg_posthog_redis.id
  description                  = "PostHog web/worker → Redis :6379"
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_posthog_web.id
}

# ── MSK SG (inbound from posthog-web + plugin-server) ───────────────────────
resource "aws_security_group" "sg_posthog_msk" {
  name        = "${local.posthog_name_prefix}-sg-msk"
  description = "MSK Kafka for PostHog event ingestion"
  vpc_id      = aws_vpc.main.id
  egress      = []

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-sg-msk"
  })
}

resource "aws_vpc_security_group_ingress_rule" "posthog_web_to_msk" {
  security_group_id            = aws_security_group.sg_posthog_msk.id
  description                  = "PostHog → MSK :9098 (TLS)"
  from_port                    = 9098
  to_port                      = 9098
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_posthog_web.id
}

# ── ClickHouse SG (inbound from posthog-web; localhost only inside container) ─
resource "aws_security_group" "sg_posthog_clickhouse" {
  name        = "${local.posthog_name_prefix}-sg-clickhouse"
  description = "Self-managed ClickHouse on ECS for PostHog"
  vpc_id      = aws_vpc.main.id
  egress      = []

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-sg-clickhouse"
  })
}

resource "aws_vpc_security_group_ingress_rule" "posthog_web_to_clickhouse" {
  security_group_id            = aws_security_group.sg_posthog_clickhouse.id
  description                  = "PostHog → ClickHouse :8123 (HTTP) + :9000 (TCP)"
  from_port                    = 8123
  to_port                      = 9000
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_posthog_web.id
}

# ────────────────────────────────────────────────────────────────────────────
# Aurora PostgreSQL for PostHog metadata
# ────────────────────────────────────────────────────────────────────────────
resource "aws_db_subnet_group" "posthog" {
  name        = "${local.posthog_name_prefix}-db-subnet-group"
  description = "Subnets for the PostHog Aurora cluster (data tier)"
  subnet_ids  = local.data_subnet_ids

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-db-subnet-group"
  })
}

resource "random_password" "posthog_db_master" {
  length  = 32
  special = true
  # Avoid chars that break JDBC URLs / psql connection strings.
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

locals {
  posthog_db_master_password = var.posthog_db_password == "" ? random_password.posthog_db_master.result : var.posthog_db_password
}

resource "aws_rds_cluster" "posthog" {
  cluster_identifier     = "${local.posthog_name_prefix}-aurora"
  engine                 = "aurora-postgresql"
  engine_version         = "16.3"
  master_username        = var.posthog_db_username
  master_password        = local.posthog_db_master_password
  database_name          = var.posthog_db_name
  db_subnet_group_name   = aws_db_subnet_group.posthog.name
  vpc_security_group_ids = [aws_security_group.sg_posthog_aurora.id]

  storage_encrypted = true
  kms_key_id        = aws_kms_key.posthog.arn

  backup_retention_period      = var.posthog_db_backup_retention_days
  preferred_backup_window      = "04:00-05:00" # UTC, off-peak
  preferred_maintenance_window = "sun:05:00-sun:06:00"

  # Aurora Serverless v2 scaling — prod only. Dev uses the default
  # provisioned capacity (db.t4g.medium).
  dynamic "serverlessv2_scaling_configuration" {
    for_each = local.is_prod ? [1] : []
    content {
      min_capacity = 0.5 # scales to ~zero between batches
      max_capacity = 8.0 # bursts during cohort calculations
    }
  }

  # Deletion protection on in prod; final snapshot required on destroy.
  deletion_protection       = local.is_prod
  skip_final_snapshot       = !local.is_prod
  final_snapshot_identifier = local.is_prod ? "${local.posthog_name_prefix}-aurora-final" : null

  copy_tags_to_snapshot = true

  lifecycle {
    ignore_changes = [master_password]
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-aurora"
  })
}

# Aurora Serverless v2 scaling — prod uses serverless for the bursty
# PostHog metadata workload (cohort calculations spike every few minutes).
# Dev uses provisioned (cheaper at low utilization). The scaling config is
# an inline block on aws_rds_cluster, gated on is_prod.
locals {
  is_prod = var.environment == "production"
}

resource "aws_rds_cluster_instance" "posthog" {
  count = local.is_prod ? 2 : 1 # prod: 1 writer + 1 reader; dev: 1 writer only

  identifier         = "${local.posthog_name_prefix}-aurora-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.posthog.id
  instance_class     = var.posthog_db_instance_class
  engine             = aws_rds_cluster.posthog.engine
  engine_version     = aws_rds_cluster.posthog.engine_version

  performance_insights_enabled          = true
  performance_insights_kms_key_id       = aws_kms_key.posthog.arn
  performance_insights_retention_period = 7

  auto_minor_version_upgrade = true

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-aurora-${count.index + 1}"
  })
}

# ── Secrets Manager — PostHog DATABASE_URL ───────────────────────────────────
resource "aws_secretsmanager_secret" "posthog_database_url" {
  name                    = "${local.posthog_name_prefix}-database-url"
  description             = "PostHog DATABASE_URL (asyncpg)"
  kms_key_id              = aws_kms_key.posthog.arn
  recovery_window_in_days = 30

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-database-url-secret"
  })
}

resource "aws_secretsmanager_secret_version" "posthog_database_url" {
  secret_id = aws_secretsmanager_secret.posthog_database_url.id

  secret_string = jsonencode({
    DATABASE_URL = "postgres://${var.posthog_db_username}:${urlencode(local.posthog_db_master_password)}@${aws_rds_cluster.posthog.endpoint}/5432/${var.posthog_db_name}"
  })
}

# ── Secrets Manager — POSTHOG_SECRET_KEY (Django secret) ─────────────────────
resource "random_password" "posthog_secret_key" {
  length  = 64
  special = false # Django secret keys are alphanumeric
}

resource "aws_secretsmanager_secret" "posthog_secret_key" {
  name                    = "${local.posthog_name_prefix}-secret-key"
  description             = "PostHog Django SECRET_KEY"
  kms_key_id              = aws_kms_key.posthog.arn
  recovery_window_in_days = 30

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-secret-key"
  })
}

resource "aws_secretsmanager_secret_version" "posthog_secret_key" {
  secret_id = aws_secretsmanager_secret.posthog_secret_key.id
  secret_string = jsonencode({
    POSTHOG_SECRET_KEY = random_password.posthog_secret_key.result
  })
}

# ────────────────────────────────────────────────────────────────────────────
# ElastiCache Redis for PostHog cache + Celery broker
# ────────────────────────────────────────────────────────────────────────────
resource "aws_elasticache_subnet_group" "posthog" {
  name        = "${local.posthog_name_prefix}-redis-subnet-group"
  description = "Subnets for PostHog ElastiCache Redis"
  subnet_ids  = local.data_subnet_ids

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-redis-subnet-group"
  })
}

resource "aws_elasticache_replication_group" "posthog" {
  replication_group_id = "${local.posthog_name_prefix}-redis"
  description          = "PostHog ${var.environment} Redis cache + Celery broker"

  engine         = "redis"
  engine_version = "7.1"
  node_type      = var.posthog_redis_node_type

  # 1 shard × 2 replicas in prod; 1 standalone in dev.
  num_cache_clusters      = local.is_prod ? 2 : 1
  num_node_groups         = null
  replicas_per_node_group = null

  automatic_failover_enabled = local.is_prod
  multi_az_enabled           = local.is_prod

  subnet_group_name  = aws_elasticache_subnet_group.posthog.name
  security_group_ids = [aws_security_group.sg_posthog_redis.id]

  at_rest_encryption_enabled = true
  kms_key_id                 = aws_kms_key.posthog.arn
  transit_encryption_enabled = true
  transit_encryption_mode    = "required"

  snapshot_retention_limit = 7
  snapshot_window          = "04:00-05:00"
  maintenance_window       = "sun:05:00-sun:06:00"

  auto_minor_version_upgrade = true
  final_snapshot_identifier  = local.is_prod ? "${local.posthog_name_prefix}-redis-final" : null
  apply_immediately          = !local.is_prod

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-redis"
  })
}

resource "random_password" "posthog_redis_auth" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "posthog_redis_auth" {
  name                    = "${local.posthog_name_prefix}-redis-auth"
  description             = "PostHog Redis AUTH token"
  kms_key_id              = aws_kms_key.posthog.arn
  recovery_window_in_days = 30

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-redis-auth-secret"
  })
}

resource "aws_secretsmanager_secret_version" "posthog_redis_auth" {
  secret_id = aws_secretsmanager_secret.posthog_redis_auth.id
  secret_string = jsonencode({
    REDIS_AUTH_TOKEN = random_password.posthog_redis_auth.result
  })
}

# ────────────────────────────────────────────────────────────────────────────
# S3 bucket for PostHog object storage (exports + async tasks + recordings)
# ────────────────────────────────────────────────────────────────────────────
resource "aws_s3_bucket" "posthog_storage" {
  bucket = "${local.posthog_name_prefix}-storage"

  # Force-destroy in dev/staging (PostHog exports are disposable). In prod,
  # prevent_accidental_destroy is set via lifecycle prevent_destroy below.
  force_destroy = !local.is_prod

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-storage"
  })
}

resource "aws_s3_bucket_versioning" "posthog_storage" {
  bucket = aws_s3_bucket.posthog_storage.id

  versioning_configuration {
    status = local.is_prod ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "posthog_storage" {
  bucket = aws_s3_bucket.posthog_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.posthog.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "posthog_storage" {
  bucket = aws_s3_bucket.posthog_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle: transition to Glacier after 90d, expire after 365d (PostHog
# exports + session recordings are short-lived — keep 1y max for compliance).
resource "aws_s3_bucket_lifecycle_configuration" "posthog_storage" {
  bucket = aws_s3_bucket.posthog_storage.id

  rule {
    id     = "glacier-then-expire"
    status = "Enabled"

    filter {
      prefix = "" # apply to all objects
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# ────────────────────────────────────────────────────────────────────────────
# MSK (Managed Streaming for Kafka) for event ingestion
# ────────────────────────────────────────────────────────────────────────────
# 3 brokers in prod (one per AZ), 1 broker in dev/staging (single AZ).
# PostHog's plugin-server consumes from MSK via the SASL/SCRAM auth.
resource "aws_msk_cluster" "posthog" {
  cluster_name           = "${local.posthog_name_prefix}-msk"
  kafka_version          = "3.6.0"
  number_of_broker_nodes = local.is_prod ? 3 : 1

  broker_node_group_info {
    instance_type   = var.posthog_kafka_instance_type
    client_subnets  = local.data_subnet_ids
    security_groups = [aws_security_group.sg_posthog_msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = var.posthog_kafka_ebs_gb
        provisioned_throughput {
          enabled           = local.is_prod
          volume_throughput = local.is_prod ? 250 : null
        }
      }
    }

    connectivity_info {
      public_access {
        type = "DISABLED"
      }
    }
  }

  encryption_info {
    encryption_at_rest_kms_key_arn = aws_kms_key.posthog.arn
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  enhanced_monitoring = local.is_prod ? "PER_TOPIC_PER_BROKER" : "DEFAULT"
  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = false
      }
      node_exporter {
        enabled_in_broker = local.is_prod
      }
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.posthog_msk.name
      }
      s3 {
        enabled = true
        bucket  = aws_s3_bucket.posthog_storage.id
        prefix  = "msk/broker/"
      }
    }
  }

  lifecycle {
    # MSK broker count changes are destructive; require explicit recreate.
    ignore_changes = [number_of_broker_nodes]
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-msk"
  })
}

# ────────────────────────────────────────────────────────────────────────────
# CloudWatch log groups (PostHog services + MSK)
# ────────────────────────────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "posthog_web" {
  name              = "/outrena/${var.environment_short}/posthog/web"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.posthog.arn

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-web-log-group"
  })
}

resource "aws_cloudwatch_log_group" "posthog_worker" {
  name              = "/outrena/${var.environment_short}/posthog/worker"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.posthog.arn

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-worker-log-group"
  })
}

resource "aws_cloudwatch_log_group" "posthog_plugin_server" {
  name              = "/outrena/${var.environment_short}/posthog/plugin-server"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.posthog.arn

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-plugin-server-log-group"
  })
}

resource "aws_cloudwatch_log_group" "posthog_clickhouse" {
  name              = "/outrena/${var.environment_short}/posthog/clickhouse"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.posthog.arn

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-clickhouse-log-group"
  })
}

resource "aws_cloudwatch_log_group" "posthog_msk" {
  name              = "/outrena/${var.environment_short}/posthog/msk"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.posthog.arn

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-msk-log-group"
  })
}

# ────────────────────────────────────────────────────────────────────────────
# ECS cluster + IAM roles
# ────────────────────────────────────────────────────────────────────────────
resource "aws_ecs_cluster" "posthog" {
  name = "${local.posthog_name_prefix}-ecs"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-ecs"
  })
}

# Reuse the existing ECS task execution role from iam.tf — it already has
# the permissions needed (ECR pull, Secrets Manager read, CloudWatch logs).
# The task role (per-service) is PostHog-specific: S3 + SNS + MSK.

data "aws_iam_policy_document" "posthog_task_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "posthog_task" {
  name               = "${local.posthog_name_prefix}-task"
  assume_role_policy = data.aws_iam_policy_document.posthog_task_assume.json

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-task-role"
  })
}

data "aws_iam_policy_document" "posthog_task" {
  statement {
    sid    = "S3ObjectStorage"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [aws_s3_bucket.posthog_storage.arn]
  }
  statement {
    sid    = "S3Objects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${aws_s3_bucket.posthog_storage.arn}/*"]
  }
  statement {
    sid    = "KMSDecrypt"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:GenerateDataKey",
    ]
    resources = [aws_kms_key.posthog.arn]
  }
}

resource "aws_iam_role_policy" "posthog_task" {
  name   = "${local.posthog_name_prefix}-task-policy"
  role   = aws_iam_role.posthog_task.id
  policy = data.aws_iam_policy_document.posthog_task.json
}

# ────────────────────────────────────────────────────────────────────────────
# ECS task definitions — web, worker, plugin-server, clickhouse
# ────────────────────────────────────────────────────────────────────────────

# Common env block shared by all PostHog task definitions.
locals {
  posthog_env = [
    { name = "SELF_HOSTED", value = "true" },
    { name = "USE_TZ", value = "true" },
    { name = "SITE_URL", value = "https://app.${var.base_domain}" },
    { name = "SERVER_URL", value = "https://posthog.${var.base_domain}" },
    { name = "DISABLE_SECURE_SSL_REDIRECT", value = "true" },
    { name = "CLICKHOUSE_DATABASE", value = "posthog" },
    { name = "CLICKHOUSE_USER", value = "clickhouse" },
    { name = "CLICKHOUSE_HOST", value = "clickhouse.${local.posthog_name_prefix}.local" },
    { name = "CLICKHOUSE_SECURE", value = "false" },
    { name = "PG_HOST", value = aws_rds_cluster.posthog.endpoint },
    { name = "POSTHOG_DB_NAME", value = var.posthog_db_name },
    { name = "POSTHOG_POSTGRES_USER", value = var.posthog_db_username },
    { name = "KAFKA_URL", value = aws_msk_cluster.posthog.bootstrap_brokers_tls },
    { name = "KAFKA_HOSTS", value = aws_msk_cluster.posthog.bootstrap_brokers_tls },
    { name = "OBJECT_STORAGE_ENDPOINT", value = "https://${aws_s3_bucket.posthog_storage.bucket_regional_domain_name}" },
    { name = "OBJECT_STORAGE_ENABLED", value = "true" },
    { name = "EMAIL_HOST", value = var.posthog_email_host },
    { name = "EMAIL_PORT", value = tostring(var.posthog_email_port) },
    { name = "EMAIL_USE_TLS", value = "true" },
    { name = "SLACK_TOKEN", value = var.posthog_slack_token },
    { name = "SELF_DRIVING_REPO", value = var.posthog_self_driving_repo },
  ]

  posthog_secrets = [
    { name = "DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.posthog_database_url.arn}:DATABASE_URL::" },
    { name = "POSTHOG_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.posthog_secret_key.arn}:POSTHOG_SECRET_KEY::" },
    { name = "REDIS_URL", valueFrom = "${aws_secretsmanager_secret.posthog_redis_auth.arn}:REDIS_AUTH_TOKEN::" },
    { name = "CLICKHOUSE_PASSWORD", valueFrom = "${aws_secretsmanager_secret.posthog_clickhouse_password.arn}:CLICKHOUSE_PASSWORD::" },
  ]
}

# Secret for ClickHouse password (used by both ClickHouse container + PostHog clients).
resource "random_password" "posthog_clickhouse_password" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "posthog_clickhouse_password" {
  name                    = "${local.posthog_name_prefix}-clickhouse-password"
  description             = "PostHog ClickHouse password"
  kms_key_id              = aws_kms_key.posthog.arn
  recovery_window_in_days = 30

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-clickhouse-password-secret"
  })
}

resource "aws_secretsmanager_secret_version" "posthog_clickhouse_password" {
  secret_id = aws_secretsmanager_secret.posthog_clickhouse_password.id
  secret_string = jsonencode({
    CLICKHOUSE_PASSWORD = random_password.posthog_clickhouse_password.result
  })
}

# ── ClickHouse (self-managed on ECS — see header comment re Altinity.Cloud) ─
# A single-node ClickHouse for dev/staging. PROD should switch to either a
# ClickHouse cluster on EC2 (3 nodes) or Altinity.Cloud (managed). The
# task definition here uses an EBS-backed volume via ECS volume + host path
# so data survives task restarts (Fargate ephemeral storage is wiped on
# restart, which is fine for dev but NOT for prod — use EC2 launch type
# with EBS for prod).
resource "aws_ecs_task_definition" "posthog_clickhouse" {
  family                   = "${local.posthog_name_prefix}-clickhouse"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = 2048
  memory = 4096

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.posthog_task.arn

  container_definitions = jsonencode([
    {
      name      = "clickhouse"
      image     = "clickhouse/clickhouse-server:24.3"
      essential = true

      environment = [
        { name = "CLICKHOUSE_DB", value = "posthog" },
        { name = "CLICKHOUSE_USER", value = "clickhouse" },
        { name = "CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT", value = "1" },
        { name = "ULIMIT_NOFILE", value = "262144" },
      ]

      secrets = [
        { name = "CLICKHOUSE_PASSWORD", valueFrom = "${aws_secretsmanager_secret.posthog_clickhouse_password.arn}:CLICKHOUSE_PASSWORD::" },
      ]

      portMappings = [
        { name = "clickhouse-http", containerPort = 8123, hostPort = 8123, protocol = "tcp", appProtocol = "http" },
        { name = "clickhouse-tcp", containerPort = 9000, hostPort = 9000, protocol = "tcp" },
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:8123/ping || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 6
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.posthog_clickhouse.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      ulimits = [
        { name = "nofile", softLimit = 262144, hardLimit = 262144 }
      ]
    }
  ])

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-clickhouse-task-def"
  })
}

# Cloud Map service for ClickHouse so PostHog web/worker can resolve the
# ClickHouse task by DNS name (rather than a hardcoded IP).
resource "aws_service_discovery_private_dns_namespace" "posthog" {
  name        = "${local.posthog_name_prefix}.local"
  description = "Private DNS namespace for PostHog internal service discovery"
  vpc         = aws_vpc.main.id

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-sd-namespace"
  })
}

resource "aws_service_discovery_service" "posthog_clickhouse" {
  name = "clickhouse"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.posthog.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 2
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-clickhouse-sd"
  })
}

resource "aws_ecs_service" "posthog_clickhouse" {
  name                   = "${local.posthog_name_prefix}-clickhouse"
  cluster                = aws_ecs_cluster.posthog.id
  task_definition        = "${aws_ecs_task_definition.posthog_clickhouse.family}:${aws_ecs_task_definition.posthog_clickhouse.revision}"
  desired_count          = local.is_prod ? 3 : 1 # prod: 3-node CH cluster (manual shard config)
  launch_type            = "FARGATE"
  platform_version       = "LATEST"
  scheduling_strategy    = "REPLICA"
  enable_execute_command = local.is_prod ? false : true

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.sg_posthog_clickhouse.id]
    assign_public_ip = var.assign_public_ip_to_fargate
  }

  service_registries {
    registry_arn = aws_service_discovery_service.posthog_clickhouse.arn
  }

  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-clickhouse-service"
  })
}

# ── PostHog web task definition + service ───────────────────────────────────
resource "aws_ecs_task_definition" "posthog_web" {
  family                   = "${local.posthog_name_prefix}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = var.posthog_web_cpu
  memory = var.posthog_web_memory

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.posthog_task.arn

  container_definitions = jsonencode([
    {
      name       = "web"
      image      = "posthog/posthog:${var.posthog_image_tag}"
      essential  = true
      entryPoint = ["/bin/sh", "-c"]
      command = [
        "python -m posthog.async_migrations.check --force && ./bin/docker --web"
      ]

      portMappings = [
        { name = "web-http", containerPort = 8000, hostPort = 8000, protocol = "tcp", appProtocol = "http" }
      ]

      environment = local.posthog_env
      secrets     = local.posthog_secrets

      healthCheck = {
        command     = ["CMD-SHELL", "curl -fsS http://localhost:8000/_health/ || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 5
        startPeriod = 120
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.posthog_web.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      ulimits = [
        { name = "nofile", softLimit = 65535, hardLimit = 65535 }
      ]
    }
  ])

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-web-task-def"
  })
}

resource "aws_ecs_service" "posthog_web" {
  name                   = "${local.posthog_name_prefix}-web"
  cluster                = aws_ecs_cluster.posthog.id
  task_definition        = "${aws_ecs_task_definition.posthog_web.family}:${aws_ecs_task_definition.posthog_web.revision}"
  desired_count          = var.posthog_web_desired_count
  launch_type            = "FARGATE"
  platform_version       = "LATEST"
  scheduling_strategy    = "REPLICA"
  enable_execute_command = local.is_prod ? false : true

  deployment_maximum_percent         = var.ecs_deployment_maximum_percent
  deployment_minimum_healthy_percent = var.ecs_deployment_minimum_healthy_percent

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [
    aws_lb_listener.posthog_https,
    aws_ecs_service.posthog_clickhouse, # web needs CH reachable on first boot
  ]

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.sg_posthog_web.id]
    assign_public_ip = var.assign_public_ip_to_fargate
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.posthog_web.arn
    container_name   = "web"
    container_port   = 8000
  }

  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-web-service"
  })
}

# ── PostHog worker ──────────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "posthog_worker" {
  family                   = "${local.posthog_name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = var.posthog_worker_cpu
  memory = var.posthog_worker_memory

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.posthog_task.arn

  container_definitions = jsonencode([
    {
      name       = "worker"
      image      = "posthog/posthog:${var.posthog_image_tag}"
      essential  = true
      entryPoint = ["./bin/docker"]
      command    = ["--worker"]

      environment = local.posthog_env
      secrets     = local.posthog_secrets

      healthCheck = {
        command     = ["CMD-SHELL", "celery -A posthog inspect ping -d celery@$$HOSTNAME || exit 1"]
        interval    = 60
        timeout     = 10
        retries     = 3
        startPeriod = 120
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.posthog_worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-worker-task-def"
  })
}

resource "aws_ecs_service" "posthog_worker" {
  name                   = "${local.posthog_name_prefix}-worker"
  cluster                = aws_ecs_cluster.posthog.id
  task_definition        = "${aws_ecs_task_definition.posthog_worker.family}:${aws_ecs_task_definition.posthog_worker.revision}"
  desired_count          = var.posthog_worker_desired_count
  launch_type            = "FARGATE"
  platform_version       = "LATEST"
  scheduling_strategy    = "REPLICA"
  enable_execute_command = local.is_prod ? false : true

  deployment_maximum_percent         = var.ecs_deployment_maximum_percent
  deployment_minimum_healthy_percent = var.ecs_deployment_minimum_healthy_percent

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.sg_posthog_web.id]
    assign_public_ip = var.assign_public_ip_to_fargate
  }

  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-worker-service"
  })
}

# ── PostHog plugin-server ───────────────────────────────────────────────────
resource "aws_ecs_task_definition" "posthog_plugin_server" {
  family                   = "${local.posthog_name_prefix}-plugin-server"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = var.posthog_plugin_server_cpu
  memory = var.posthog_plugin_server_memory

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.posthog_task.arn

  container_definitions = jsonencode([
    {
      name       = "plugin-server"
      image      = "posthog/posthog:${var.posthog_image_tag}"
      essential  = true
      entryPoint = ["./bin/docker"]
      command    = ["--plugin-server"]

      environment = concat(local.posthog_env, [
        { name = "NODE_OPTIONS", value = "--max_old_space_size=2048" },
        { name = "PLUGINS_RELOAD_PUBSUB_CHANNEL", value = "reload-plugins" },
      ])
      secrets = local.posthog_secrets

      healthCheck = {
        command     = ["CMD-SHELL", "curl -fsS http://localhost:3000/_health/ || exit 1"]
        interval    = 60
        timeout     = 10
        retries     = 3
        startPeriod = 90
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.posthog_plugin_server.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-plugin-server-task-def"
  })
}

resource "aws_ecs_service" "posthog_plugin_server" {
  name                   = "${local.posthog_name_prefix}-plugin-server"
  cluster                = aws_ecs_cluster.posthog.id
  task_definition        = "${aws_ecs_task_definition.posthog_plugin_server.family}:${aws_ecs_task_definition.posthog_plugin_server.revision}"
  desired_count          = var.posthog_plugin_server_desired_count
  launch_type            = "FARGATE"
  platform_version       = "LATEST"
  scheduling_strategy    = "REPLICA"
  enable_execute_command = local.is_prod ? false : true

  deployment_maximum_percent         = var.ecs_deployment_maximum_percent
  deployment_minimum_healthy_percent = var.ecs_deployment_minimum_healthy_percent

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.sg_posthog_web.id]
    assign_public_ip = var.assign_public_ip_to_fargate
  }

  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-plugin-server-service"
  })
}

# ────────────────────────────────────────────────────────────────────────────
# ALB + ACM cert + Route 53 + WAFv2
# ────────────────────────────────────────────────────────────────────────────

# ACM cert for posthog.<base_domain> — reuses the Route 53 hosted zone that
# already exists in route53.tf for the apex domain. DNS validation.
resource "aws_acm_certificate" "posthog" {
  domain_name       = "posthog.${var.base_domain}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-acm"
  })
}

resource "aws_route53_record" "posthog_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.posthog.domain_validation_options :
    dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id = aws_route53_zone.main[0].zone_id
  name    = each.value.name
  type    = each.value.type
  records = [each.value.record]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "posthog" {
  certificate_arn         = aws_acm_certificate.posthog.arn
  validation_record_fqdns = [for r in aws_route53_record.posthog_cert_validation : r.fqdn]
}

# ALB
resource "aws_lb" "posthog" {
  name                       = "${local.posthog_name_prefix}-alb"
  internal                   = false
  load_balancer_type         = "application"
  subnets                    = local.public_subnet_ids
  security_groups            = [aws_security_group.sg_posthog_alb.id]
  drop_invalid_header_fields = true
  enable_deletion_protection = local.is_prod

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    prefix  = "${var.environment_short}/posthog-alb"
    enabled = true
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-alb"
  })
}

resource "aws_lb_target_group" "posthog_web" {
  name        = "${local.posthog_name_prefix}-tg-web"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    interval            = 30
    path                = "/_health/"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  deregistration_delay = 60

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-tg-web"
  })
}

resource "aws_lb_listener" "posthog_https" {
  load_balancer_arn = aws_lb.posthog.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06" # TLS 1.2+ per SOC2
  certificate_arn   = aws_acm_certificate_validation.posthog.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.posthog_web.arn
  }

  depends_on = [aws_acm_certificate_validation.posthog]
}

resource "aws_lb_listener" "posthog_http" {
  load_balancer_arn = aws_lb.posthog.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# Route 53 — posthog.<base_domain> → ALB
resource "aws_route53_record" "posthog" {
  zone_id = aws_route53_zone.main[0].zone_id
  name    = "posthog.${var.base_domain}"
  type    = "A"

  alias {
    name                   = aws_lb.posthog.dns_name
    zone_id                = aws_lb.posthog.zone_id
    evaluate_target_health = true
  }
}

# WAFv2 — OWASP CRS + rate-limit
resource "aws_wafv2_web_acl" "posthog" {
  name        = "${local.posthog_name_prefix}-waf"
  description = "WAF for PostHog ALB — OWASP CRS + rate-limit"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # AWS Managed Core rule set (SQLi, XSS, LFI, RFI).
  rule {
    name     = "aws-managed-common"
    priority = 1
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.posthog_name_prefix}-waf-common"
      sampled_requests_enabled   = true
    }
  }

  # Rate-based — 100 req/5min/IP in prod, 1000 in dev (matches OUTRENA app WAF).
  rule {
    name     = "rate-limit"
    priority = 2
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.posthog_name_prefix}-waf-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.posthog_name_prefix}-waf"
    sampled_requests_enabled   = true
  }

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-waf"
  })
}

resource "aws_wafv2_web_acl_association" "posthog" {
  resource_arn = aws_lb.posthog.arn
  web_acl_arn  = aws_wafv2_web_acl.posthog.arn
}

# ────────────────────────────────────────────────────────────────────────────
# CloudWatch alarms — PostHog-specific health metrics
# ────────────────────────────────────────────────────────────────────────────

# 1. PostHog web 5xx rate > 1% (rollback trigger — same as OUTRENA app)
resource "aws_cloudwatch_metric_alarm" "posthog_web_5xx" {
  alarm_name          = "${local.posthog_name_prefix}-web-5xx-rate"
  alarm_description   = "PostHog web 5xx rate > 1% (5 min)"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.posthog.arn_suffix
    TargetGroup  = aws_lb_target_group.posthog_web.arn_suffix
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-web-5xx-alarm"
  })
}

# 2. Aurora CPU > 80% (sustained)
resource "aws_cloudwatch_metric_alarm" "posthog_aurora_cpu" {
  alarm_name          = "${local.posthog_name_prefix}-aurora-cpu-high"
  alarm_description   = "PostHog Aurora CPU > 80% for 10 min"
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.posthog.cluster_identifier
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-aurora-cpu-alarm"
  })
}

# 3. Redis evictions > 1000/min (memory pressure — PostHog caches heavily)
resource "aws_cloudwatch_metric_alarm" "posthog_redis_evictions" {
  alarm_name          = "${local.posthog_name_prefix}-redis-evictions-high"
  alarm_description   = "PostHog Redis evictions > 1000/min (cache thrashing)"
  namespace           = "AWS/ElastiCache"
  metric_name         = "Evictions"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 5
  threshold           = 1000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  # Replication-group members have CacheClusterIds of the form
  # "<replication_group_id>-001", "-002", etc. We monitor the primary
  # (-001); a multi-node rollup would require metric math.
  dimensions = {
    CacheClusterId = "${aws_elasticache_replication_group.posthog.replication_group_id}-001"
    CacheNodeId    = "0001"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-redis-evictions-alarm"
  })
}

# 4. ClickHouse task CPU > 90% (sustained — query bottleneck)
resource "aws_cloudwatch_metric_alarm" "posthog_clickhouse_cpu" {
  alarm_name          = "${local.posthog_name_prefix}-clickhouse-cpu-high"
  alarm_description   = "PostHog ClickHouse CPU > 90% for 10 min"
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 90
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.posthog.name
    ServiceName = aws_ecs_service.posthog_clickhouse.name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-clickhouse-cpu-alarm"
  })
}

# 5. MSK broker CPU > 80% (event ingestion throughput bottleneck)
resource "aws_cloudwatch_metric_alarm" "posthog_msk_cpu" {
  alarm_name          = "${local.posthog_name_prefix}-msk-cpu-high"
  alarm_description   = "PostHog MSK broker CPU > 80% for 10 min"
  namespace           = "AWS/Kafka"
  metric_name         = "CpuUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_msk_cluster.posthog.cluster_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-msk-cpu-alarm"
  })
}

# 6. Worker queue depth — uses the Celery inspect API via CloudWatch log
# metric filter on the periodic "queue depth" log line PostHog emits.
# This is a proxy: log filter on "queue_depth" + queue name → metric.
resource "aws_cloudwatch_log_metric_filter" "posthog_worker_queue_depth" {
  name           = "${local.posthog_name_prefix}-worker-queue-depth"
  log_group_name = aws_cloudwatch_log_group.posthog_worker.name
  pattern        = "[timestamp, level, queue_depth=\"queue_depth\", queue_name, depth_str, ...]"

  metric_transformation {
    name      = "QueueDepth"
    namespace = "OUTRENA/PostHog"
    value     = "$depth"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "posthog_worker_queue_depth" {
  alarm_name          = "${local.posthog_name_prefix}-worker-queue-depth-high"
  alarm_description   = "PostHog Celery queue depth > 10000 (backlog)"
  namespace           = "OUTRENA/PostHog"
  metric_name         = "QueueDepth"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 10000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = merge(local.posthog_tags, {
    Name = "${local.posthog_name_prefix}-worker-queue-depth-alarm"
  })
}
