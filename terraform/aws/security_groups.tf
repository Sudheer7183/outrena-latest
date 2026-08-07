# security_groups.tf — VPC security groups.
#
# Mirrors the SG table from migration doc §11.2 verbatim. Cross-SG references
# always use `source_security_group_id` (NOT cidr_blocks) so AWS treats the
# source as the dynamic membership of the source SG. This means: even if a
# task is relaunched with a new ENI, the inbound rule auto-applies.
#
# IMPORTANT: cross-SG references are defined as SEPARATE
# `aws_vpc_security_group_ingress_rule` / `aws_vpc_security_group_egress_rule`
# resources (not inline `ingress`/`egress` blocks) to avoid the Terraform
# graph cycle that occurs when SG_A references SG_B inline AND SG_B
# references SG_A inline. With separate rule resources, the SG resources
# themselves have no inter-dependency — only the rules do.
#
# Outbound rules use the same `source_security_group_id` form for cross-SG
# traffic, and `cidr_ipv4 = "0.0.0.0/0"` for internet egress (LLM, MailBridge).
#
# Default egress (0.0.0.0/0:*) is removed on every SG via an empty inline
# `egress` block — we then re-add specific egress via separate rule resources.

locals {
  sg_tags = {
    Component = "security-group"
  }
}

# ── sg_alb — internet-facing ALB ──────────────────────────────────────────────
# Inbound:  0.0.0.0/0 :443 + :80 (redirect)
# Outbound: sg_backend :8000, sg_frontend :80, sg_keycloak :8080
resource "aws_security_group" "sg_alb" {
  name        = "${local.name_prefix}-sg-alb"
  description = "Internet-facing ALB (HTTPS only)"
  vpc_id      = aws_vpc.main.id

  # Remove default egress — re-add via separate rule resources below.
  egress = []

  tags = merge(local.sg_tags, {
    Name = "${local.name_prefix}-sg-alb"
  })
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.sg_alb.id
  description       = "HTTPS from internet"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.sg_alb.id
  description       = "HTTP from internet (redirect to HTTPS)"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_backend" {
  security_group_id            = aws_security_group.sg_alb.id
  description                  = "Forward to backend FastAPI"
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_backend.id
}

resource "aws_vpc_security_group_egress_rule" "alb_to_frontend" {
  security_group_id            = aws_security_group.sg_alb.id
  description                  = "Forward to frontend nginx"
  from_port                    = 80
  to_port                      = 80
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_frontend.id
}

resource "aws_vpc_security_group_egress_rule" "alb_to_keycloak" {
  security_group_id            = aws_security_group.sg_alb.id
  description                  = "Forward to Keycloak"
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_keycloak.id
}

# ── sg_backend — FastAPI ECS task ─────────────────────────────────────────────
# Inbound:  sg_alb :8000 + ECS Exec (VPC-internal)
# Outbound: sg_rds :5432, sg_redis :6379, sg_keycloak :8080, 0.0.0.0/0 :443
resource "aws_security_group" "sg_backend" {
  name        = "${local.name_prefix}-sg-backend"
  description = "Backend FastAPI Fargate task"
  vpc_id      = aws_vpc.main.id

  egress = []

  tags = merge(local.sg_tags, {
    Name = "${local.name_prefix}-sg-backend"
  })
}

resource "aws_vpc_security_group_ingress_rule" "backend_from_alb" {
  security_group_id            = aws_security_group.sg_backend.id
  description                  = "HTTP from ALB"
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_alb.id
}

resource "aws_vpc_security_group_ingress_rule" "backend_ecs_exec" {
  security_group_id = aws_security_group.sg_backend.id
  description       = "ECS Exec (SSM) from within VPC"
  from_port         = 0
  to_port           = 65535
  ip_protocol       = "tcp"
  cidr_ipv4         = var.vpc_cidr
}

resource "aws_vpc_security_group_egress_rule" "backend_to_rds" {
  security_group_id            = aws_security_group.sg_backend.id
  description                  = "Postgres to RDS"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_rds.id
}

resource "aws_vpc_security_group_egress_rule" "backend_to_redis" {
  security_group_id            = aws_security_group.sg_backend.id
  description                  = "Redis to ElastiCache"
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_redis.id
}

resource "aws_vpc_security_group_egress_rule" "backend_to_keycloak" {
  security_group_id            = aws_security_group.sg_backend.id
  description                  = "Keycloak JWKS + introspection"
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_keycloak.id
}

resource "aws_vpc_security_group_egress_rule" "backend_to_internet_https" {
  security_group_id = aws_security_group.sg_backend.id
  description       = "LLM + MailBridge (HTTPS)"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

# ── sg_frontend — nginx serving Vite build ────────────────────────────────────
# Inbound:  sg_alb :80
# Outbound: sg_backend :8000 (SPA calls API via same-origin → ALB → backend,
#           but in dev/pre-prod the SPA can also call the backend directly)
resource "aws_security_group" "sg_frontend" {
  name        = "${local.name_prefix}-sg-frontend"
  description = "Frontend nginx Fargate task"
  vpc_id      = aws_vpc.main.id

  egress = []

  tags = merge(local.sg_tags, {
    Name = "${local.name_prefix}-sg-frontend"
  })
}

resource "aws_vpc_security_group_ingress_rule" "frontend_from_alb" {
  security_group_id            = aws_security_group.sg_frontend.id
  description                  = "HTTP from ALB"
  from_port                    = 80
  to_port                      = 80
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_alb.id
}

resource "aws_vpc_security_group_egress_rule" "frontend_to_backend" {
  security_group_id            = aws_security_group.sg_frontend.id
  description                  = "API calls to backend (same-VPC)"
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_backend.id
}

# ── sg_worker — Celery worker (no inbound) ────────────────────────────────────
# Inbound:  none
# Outbound: sg_rds :5432, sg_redis :6379, 0.0.0.0/0 :443
resource "aws_security_group" "sg_worker" {
  name        = "${local.name_prefix}-sg-worker"
  description = "Celery worker Fargate task (no inbound)"
  vpc_id      = aws_vpc.main.id

  # No ingress rules at all — SG default-deny inbound.
  egress = []

  tags = merge(local.sg_tags, {
    Name = "${local.name_prefix}-sg-worker"
  })
}

resource "aws_vpc_security_group_egress_rule" "worker_to_rds" {
  security_group_id            = aws_security_group.sg_worker.id
  description                  = "Postgres to RDS"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_rds.id
}

resource "aws_vpc_security_group_egress_rule" "worker_to_redis" {
  security_group_id            = aws_security_group.sg_worker.id
  description                  = "Redis to ElastiCache"
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_redis.id
}

resource "aws_vpc_security_group_egress_rule" "worker_to_internet_https" {
  security_group_id = aws_security_group.sg_worker.id
  description       = "MailBridge + LLM (HTTPS)"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

# ── sg_rds — Postgres (no outbound) ───────────────────────────────────────────
# Inbound:  sg_backend :5432, sg_worker :5432, sg_keycloak :5432 (own DB)
# Outbound: none
resource "aws_security_group" "sg_rds" {
  name        = "${local.name_prefix}-sg-rds"
  description = "RDS PostgreSQL (data tier — no egress)"
  vpc_id      = aws_vpc.main.id

  # No egress block → default deny all outbound (empty list).
  egress = []

  tags = merge(local.sg_tags, {
    Name = "${local.name_prefix}-sg-rds"
    Tier = "data"
  })
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_backend" {
  security_group_id            = aws_security_group.sg_rds.id
  description                  = "Postgres from backend"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_backend.id
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_worker" {
  security_group_id            = aws_security_group.sg_rds.id
  description                  = "Postgres from worker"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_worker.id
}

# Keycloak uses its own DB inside the same RDS instance, but is provisioned
# with a separate role. The connection originates from the keycloak task SG.
resource "aws_vpc_security_group_ingress_rule" "rds_from_keycloak" {
  security_group_id            = aws_security_group.sg_rds.id
  description                  = "Postgres from Keycloak (own DB)"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_keycloak.id
}

# ── sg_redis — ElastiCache (no outbound) ──────────────────────────────────────
# Inbound:  sg_backend :6379, sg_worker :6379
# Outbound: none
resource "aws_security_group" "sg_redis" {
  name        = "${local.name_prefix}-sg-redis"
  description = "ElastiCache Redis (data tier — no egress)"
  vpc_id      = aws_vpc.main.id

  egress = []

  tags = merge(local.sg_tags, {
    Name = "${local.name_prefix}-sg-redis"
    Tier = "data"
  })
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_backend" {
  security_group_id            = aws_security_group.sg_redis.id
  description                  = "Redis from backend"
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_backend.id
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_worker" {
  security_group_id            = aws_security_group.sg_redis.id
  description                  = "Redis from worker"
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_worker.id
}

# ── sg_keycloak — Keycloak ECS task ───────────────────────────────────────────
# Inbound:  sg_alb :8080, sg_backend :8080
# Outbound: sg_rds :5432 (Keycloak's own DB)
resource "aws_security_group" "sg_keycloak" {
  name        = "${local.name_prefix}-sg-keycloak"
  description = "Keycloak Fargate task"
  vpc_id      = aws_vpc.main.id

  egress = []

  tags = merge(local.sg_tags, {
    Name = "${local.name_prefix}-sg-keycloak"
  })
}

resource "aws_vpc_security_group_ingress_rule" "keycloak_from_alb" {
  security_group_id            = aws_security_group.sg_keycloak.id
  description                  = "Keycloak HTTP from ALB"
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_alb.id
}

resource "aws_vpc_security_group_ingress_rule" "keycloak_from_backend" {
  security_group_id            = aws_security_group.sg_keycloak.id
  description                  = "JWKS / introspection from backend"
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_backend.id
}

resource "aws_vpc_security_group_egress_rule" "keycloak_to_rds" {
  security_group_id            = aws_security_group.sg_keycloak.id
  description                  = "Keycloak's own DB on RDS"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_rds.id
}

# ── sg_vpc_endpoints — Interface VPC endpoints (ECR/Secrets/Logs) ─────────────
# Referenced by vpc.tf aws_vpc_endpoint.ecr_api / ecr_dkr / secretsmanager / logs.
#
# Inbound:  sg_backend :443, sg_worker :443, sg_frontend :443, sg_keycloak :443
# Outbound: 0.0.0.0/0 :443 (interface endpoints accept HTTPS only)
resource "aws_security_group" "vpc_endpoints" {
  # NOTE: named `vpc_endpoints` (not `sg_vpc_endpoints`) to match the existing
  # vpc.tf references written by the lead agent — `aws_security_group.vpc_endpoints.id`.
  name        = "${local.name_prefix}-sg-vpc-endpoints"
  description = "Interface VPC endpoints (ECR/Secrets/Logs)"
  vpc_id      = aws_vpc.main.id

  egress = []

  tags = merge(local.sg_tags, {
    Name = "${local.name_prefix}-sg-vpc-endpoints"
  })
}

resource "aws_vpc_security_group_ingress_rule" "vpce_from_backend" {
  security_group_id            = aws_security_group.vpc_endpoints.id
  description                  = "HTTPS from backend Fargate"
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_backend.id
}

resource "aws_vpc_security_group_ingress_rule" "vpce_from_worker" {
  security_group_id            = aws_security_group.vpc_endpoints.id
  description                  = "HTTPS from worker Fargate"
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_worker.id
}

resource "aws_vpc_security_group_ingress_rule" "vpce_from_frontend" {
  security_group_id            = aws_security_group.vpc_endpoints.id
  description                  = "HTTPS from frontend Fargate"
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_frontend.id
}

resource "aws_vpc_security_group_ingress_rule" "vpce_from_keycloak" {
  security_group_id            = aws_security_group.vpc_endpoints.id
  description                  = "HTTPS from Keycloak Fargate"
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.sg_keycloak.id
}

resource "aws_vpc_security_group_egress_rule" "vpce_to_internet_https" {
  security_group_id = aws_security_group.vpc_endpoints.id
  description       = "HTTPS to AWS services (interface endpoints)"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}
