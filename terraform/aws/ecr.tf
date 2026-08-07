# ecr.tf — ECR repos for the backend + frontend containers.
#
# Tag mutability: dev/staging use MUTABLE so CI can re-push the same tag
# (e.g. `latest`) on every commit without forcing a unique tag. Prod uses
# IMMUTABLE so a deployed tag can never be silently re-pushed (defense
# against supply-chain tampering).
#
# Scan-on-push is enabled on all environments — Critical/High findings
# block the deploy via a separate `aws_ecr_image_scan_findings` check in
# CI (not in Terraform).
#
# Lifecycle policy:
#   - Keep last 30 tagged images
#   - Keep last 7 untagged images (for `latest` re-pushed history)
#   - Older images are pruned automatically

locals {
  ecr_tag_mutability = var.environment == "production" ? "IMMUTABLE" : "MUTABLE"

  ecr_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 30 tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v", "sha-", "main-", "release-"]
          countType     = "imageCountMoreThan"
          countNumber   = 30
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep last 7 untagged images"
        selection = {
          tagStatus   = "untagged"
          countType   = "imageCountMoreThan"
          countNumber = 7
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 3
        description  = "Expire images older than 90 days"
        selection = {
          tagStatus   = "any"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 90
        }
        action = { type = "expire" }
      }
    ]
  })
}

# ── Backend ECR ───────────────────────────────────────────────────────────────
# Also serves the Celery worker (same image, different command).
resource "aws_ecr_repository" "backend" {
  name                 = "outrena/${var.environment_short}/backend"
  image_tag_mutability = local.ecr_tag_mutability

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.s3.arn # reuse S3 KMS key (no need for a per-ECR key)
  }

  force_delete = var.environment != "production" # dev: allow `terraform destroy` to clear repo

  tags = {
    Name = "${local.name_prefix}-ecr-backend"
  }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy     = local.ecr_lifecycle_policy
}

# ── Frontend ECR ──────────────────────────────────────────────────────────────
resource "aws_ecr_repository" "frontend" {
  name                 = "outrena/${var.environment_short}/frontend"
  image_tag_mutability = local.ecr_tag_mutability

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.s3.arn
  }

  force_delete = var.environment != "production"

  tags = {
    Name = "${local.name_prefix}-ecr-frontend"
  }
}

resource "aws_ecr_lifecycle_policy" "frontend" {
  repository = aws_ecr_repository.frontend.name
  policy     = local.ecr_lifecycle_policy
}
