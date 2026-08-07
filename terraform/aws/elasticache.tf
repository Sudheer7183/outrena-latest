# elasticache.tf — ElastiCache Redis 7 replication group + KMS key.
#
# Migration doc §11.3:
#   - Redis 7
#   - Cluster mode in prod (3 shards × 1 replica)
#   - Encryption in transit + at rest
#
# Dev uses a single-node non-clustered Redis for cost. The backend/worker
# connect via the configuration endpoint (cluster mode) or primary endpoint
# (non-cluster). The ECS env REDIS_URL is built from these outputs in
# ecs_backend.tf.

# ── KMS key for Redis at-rest encryption ──────────────────────────────────────
resource "aws_kms_key" "redis" {
  description             = "KMS key for ElastiCache Redis at-rest encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = var.enable_kms_key_rotation

  policy = data.aws_iam_policy_document.kms_redis.json

  tags = {
    Name = "${local.name_prefix}-kms-redis"
  }
}

resource "aws_kms_alias" "redis" {
  name          = "alias/${local.name_prefix}-redis"
  target_key_id = aws_kms_key.redis.key_id
}

data "aws_iam_policy_document" "kms_redis" {
  statement {
    sid    = "Enable IAM root permissions"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "Allow ElastiCache service to use the key"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["elasticache.amazonaws.com"]
    }

    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]

    resources = ["*"]
  }
}

# ── Subnet group (data tier) ──────────────────────────────────────────────────
resource "aws_elasticache_subnet_group" "main" {
  name        = "${local.name_prefix}-redis-subnet-group"
  description = "Subnets for the OUTRENA ElastiCache Redis (data tier)"
  subnet_ids  = local.data_subnet_ids

  tags = {
    Name = "${local.name_prefix}-redis-subnet-group"
  }
}

# ── Replication group ─────────────────────────────────────────────────────────
# Single resource covers both cluster-mode (prod) and non-cluster (dev):
#   - cluster_mode=false → num_cache_clusters standalone replicas with
#     automatic failover; primary endpoint used by app.
#   - cluster_mode=true  → num_node_shards shards, each with
#     replicas_per_node_group replicas; configuration endpoint used.
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${local.name_prefix}-redis"
  description          = "OUTRENA ${var.environment} Redis cache + Celery broker"

  engine                  = "redis"
  engine_version          = "7.1"
  node_type               = var.redis_node_type
  num_cache_clusters      = var.redis_cluster_mode ? null : var.redis_num_cache_clusters
  num_node_groups         = var.redis_cluster_mode ? var.redis_shard_count : null
  replicas_per_node_group = var.redis_cluster_mode ? max(var.redis_num_cache_clusters - 1, 1) : null

  # Multi-AZ failover — required in prod, harmless in dev (single AZ).
  automatic_failover_enabled = var.redis_cluster_mode || var.redis_num_cache_clusters > 1
  multi_az_enabled           = var.redis_cluster_mode && var.environment == "production"

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.sg_redis.id]

  # Encryption at rest + in transit. Migration doc §11.3 requires both.
  at_rest_encryption_enabled = true
  kms_key_id                 = aws_kms_key.redis.arn
  transit_encryption_enabled = true
  # AUTH token — random 32-char string required when transit encryption is on.
  # Stored in Secrets Manager (secrets.tf) and passed to ECS as REDIS_URL
  # query param `?password=...`. We generate it here via random_password and
  # also stash in secrets.tf for the ECS task to read.
  transit_encryption_mode = "required"

  # Snapshots — 7-day retention, off-peak window.
  snapshot_retention_limit = 7
  snapshot_window          = "03:00-05:00" # UTC
  maintenance_window       = "sun:05:00-sun:06:00"

  # Don't auto-upgrade major versions (7.x → 8.x) — plan those manually.
  auto_minor_version_upgrade = true

  # Final snapshot on destroy (so cache state can be inspected post-mortem).
  # Note: ElastiCache snapshot names must be lowercase + start with a letter.
  final_snapshot_identifier = var.environment == "production" ? "${local.name_prefix}-redis-final" : null

  # Tags applied to the replication group AND all member nodes.
  tags = {
    Name = "${local.name_prefix}-redis"
    Tier = "data"
  }
}

# ── Redis AUTH token ──────────────────────────────────────────────────────────
# When transit_encryption_enabled = true, ElastiCache requires an AUTH token.
# We generate one and store it in Secrets Manager — the backend/worker ECS
# tasks read it via the `secrets` block in their task definition.
resource "random_password" "redis_auth" {
  length  = 32
  special = false # Redis AUTH tokens are alphanumeric+/-_ only
}

resource "aws_secretsmanager_secret" "redis_auth" {
  name                    = "${local.name_prefix}-redis-auth"
  description             = "OUTRENA Redis AUTH token (transit encryption)"
  kms_key_id              = aws_kms_key.redis.arn
  recovery_window_in_days = 30

  tags = {
    Name = "${local.name_prefix}-redis-auth-secret"
  }
}

resource "aws_secretsmanager_secret_version" "redis_auth" {
  secret_id = aws_secretsmanager_secret.redis_auth.id
  secret_string = jsonencode({
    REDIS_AUTH_TOKEN = random_password.redis_auth.result
  })
}
