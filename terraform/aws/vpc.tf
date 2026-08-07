# vpc.tf — VPC, subnets, NAT, IGW, route tables.
#
# Layout (per migration doc §11.1):
#   2 public subnets  — ALB nodes
#   3 private subnets — ECS Fargate (backend, frontend, worker, Keycloak)
#   3 data subnets    — RDS + ElastiCache (no IGW, no NAT)
#
# Data subnets are separate from private so we can attach a stricter
# route table (no outbound to internet) and a dedicated NACL if needed.

locals {
  azs           = slice(var.availability_zones, 0, min(length(var.availability_zones), 3))
  num_azs       = length(local.azs)
  public_cidrs  = [for k, v in local.azs : cidrsubnet(var.vpc_cidr, 4, k)]
  private_cidrs = [for k, v in local.azs : cidrsubnet(var.vpc_cidr, 4, k + 4)]
  data_cidrs    = [for k, v in local.azs : cidrsubnet(var.vpc_cidr, 4, k + 8)]
}

# ── VPC ───────────────────────────────────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-${var.environment_short}-vpc"
  }
}

# ── Public subnets (ALB) ──────────────────────────────────────────────────────
resource "aws_subnet" "public" {
  for_each = toset([for k, v in local.azs : "${k}:${v}"])

  vpc_id                  = aws_vpc.main.id
  cidr_block              = local.public_cidrs[split(":", each.key)[0]]
  availability_zone       = split(":", each.key)[1]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-${var.environment_short}-public-${split(":", each.key)[1]}"
    Tier = "public"
  }
}

# ── Private subnets (ECS Fargate) ─────────────────────────────────────────────
resource "aws_subnet" "private" {
  for_each = toset([for k, v in local.azs : "${k}:${v}"])

  vpc_id                  = aws_vpc.main.id
  cidr_block              = local.private_cidrs[split(":", each.key)[0]]
  availability_zone       = split(":", each.key)[1]
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.project_name}-${var.environment_short}-private-${split(":", each.key)[1]}"
    Tier = "private"
  }
}

# ── Data subnets (RDS + ElastiCache) ──────────────────────────────────────────
resource "aws_subnet" "data" {
  for_each = toset([for k, v in local.azs : "${k}:${v}"])

  vpc_id            = aws_vpc.main.id
  cidr_block        = local.data_cidrs[split(":", each.key)[0]]
  availability_zone = split(":", each.key)[1]

  tags = {
    Name = "${var.project_name}-${var.environment_short}-data-${split(":", each.key)[1]}"
    Tier = "data"
  }
}

# ── Internet Gateway ──────────────────────────────────────────────────────────
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.environment_short}-igw"
  }
}

# ── Elastic IPs for NAT Gateways (only if enabled) ────────────────────────────
resource "aws_eip" "nat" {
  for_each = var.enable_nat_gateway ? (var.single_nat_gateway ? toset(["single"]) : toset(local.azs)) : toset([])

  domain = "vpc"

  tags = {
    Name = "${var.project_name}-${var.environment_short}-nat-eip-${each.key}"
  }
}

# ── NAT Gateway ───────────────────────────────────────────────────────────────
resource "aws_nat_gateway" "main" {
  for_each = var.enable_nat_gateway ? (var.single_nat_gateway ? toset(["single"]) : toset(local.azs)) : toset([])

  allocation_id = aws_eip.nat[each.key].id
  # single NAT sits in the first public subnet; per-AZ NATs sit in matching AZ
  subnet_id = each.key == "single" ? aws_subnet.public["0:${local.azs[0]}"].id : aws_subnet.public["${index(local.azs, each.key)}:${each.key}"].id

  tags = {
    Name = "${var.project_name}-${var.environment_short}-nat-${each.key}"
  }

  depends_on = [aws_internet_gateway.main]
}

# ── Route tables ──────────────────────────────────────────────────────────────
# Public: route to IGW
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-${var.environment_short}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# Private: route to NAT (or no default route if NAT disabled — dev cost mode)
resource "aws_route_table" "private" {
  for_each = var.enable_nat_gateway ? (var.single_nat_gateway ? toset(["single"]) : toset(local.azs)) : toset(["none"])

  vpc_id = aws_vpc.main.id

  dynamic "route" {
    for_each = var.enable_nat_gateway ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = var.single_nat_gateway ? aws_nat_gateway.main["single"].id : aws_nat_gateway.main[each.key].id
    }
  }

  tags = {
    Name = "${var.project_name}-${var.environment_short}-private-rt-${each.key}"
  }
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id = each.value.id
  # map each private subnet's AZ to the matching private route table
  route_table_id = !var.enable_nat_gateway ? aws_route_table.private["none"].id : (var.single_nat_gateway ? aws_route_table.private["single"].id : aws_route_table.private[split(":", each.key)[1]].id)
}

# Data: no default route (no internet egress)
resource "aws_route_table" "data" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.environment_short}-data-rt"
  }
}

resource "aws_route_table_association" "data" {
  for_each = aws_subnet.data

  subnet_id      = each.value.id
  route_table_id = aws_route_table.data.id
}

# ── VPC Endpoints (cost + security: keep AWS traffic off the public IGW) ──────
# S3 + DynamoDB + ECR + Secrets Manager + CloudWatch Logs via Gateway/Interface endpoints.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private["none"].id]

  tags = {
    Name = "${var.project_name}-${var.environment_short}-vpce-s3"
  }
}

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = [for s in aws_subnet.private : s.id]

  security_group_ids = [aws_security_group.vpc_endpoints.id]
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = [for s in aws_subnet.private : s.id]

  security_group_ids = [aws_security_group.vpc_endpoints.id]
}

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = [for s in aws_subnet.private : s.id]

  security_group_ids = [aws_security_group.vpc_endpoints.id]
}

resource "aws_vpc_endpoint" "logs" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = [for s in aws_subnet.private : s.id]

  security_group_ids = [aws_security_group.vpc_endpoints.id]
}
