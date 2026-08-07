# versions.tf — OUTRENA AWS Terraform provider pinning.
#
# Pinned to versions known-good with the migration doc (§11 AWS Deployment
# Architecture). Bump only after a planned upgrade window.

terraform {
  required_version = ">= 1.7.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    # Added in SAAS-INFRA: archive provider packages the inline Python
    # rotation Lambda source into a zip at plan time (no external build step).
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # Remote state — one S3 bucket per Organisation, one key per environment
  # (dev / staging / prod). S3 native locking (use_lockfile) prevents
  # concurrent `apply` without a separate DynamoDB table.
  backend "s3" {
    # bucket + key are overridden per-env via `terraform init -backend-config=...`
    # see envs/<env>/backend.tfbackend
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "outrena"
      Environment = var.environment
      ManagedBy   = "terraform"
      Repo        = "outrena-migration"
    }
  }
}
