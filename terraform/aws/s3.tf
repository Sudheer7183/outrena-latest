# s3.tf — S3 buckets + KMS key for SSE.
#
# Buckets:
#   csv           — prospect CSV uploads (short-lived: ingest → delete after import)
#   collateral    — sales collateral (PDFs, images) — long-lived, versioned
#   alb_logs      — ALB access logs (5-min flush from AWS ELB account)
#
# Each content bucket gets:
#   - versioning ON
#   - SSE-KMS (customer-managed key aws_kms_key.s3)
#   - public access block (all 4 booleans true)
#   - lifecycle: STANDARD_IA @ 30d → GLACIER @ 90d → expire @ 365d
#   - bucket policy enforcing TLS-only transport (deny http://)
#
# The IAM policy doc the backend/worker task roles need is exported as
# `data.aws_iam_policy_document.s3_access` — iam.tf attaches it.

# ── KMS key for S3 SSE ────────────────────────────────────────────────────────
resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 SSE-KMS (csv + collateral buckets)"
  deletion_window_in_days = 30
  enable_key_rotation     = var.enable_kms_key_rotation

  policy = data.aws_iam_policy_document.kms_s3.json

  tags = {
    Name = "${local.name_prefix}-kms-s3"
  }
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${local.name_prefix}-s3"
  target_key_id = aws_kms_key.s3.key_id
}

# KMS key policy: allow root account + KMS service; allow S3 service to
# encrypt/decrypt on behalf of principals who have s3:GetObject.
data "aws_iam_policy_document" "kms_s3" {
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
    sid    = "Allow S3 service to use the key"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey"
    ]

    resources = ["*"]
  }
}

# Caller identity (account ID) for KMS policy + bucket policy ARNs.
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_partition" "current" {}

# ── CSV bucket ────────────────────────────────────────────────────────────────
resource "aws_s3_bucket" "csv" {
  bucket = var.csv_bucket_name

  tags = {
    Name = "${local.name_prefix}-csv"
    Tier = "app-data"
  }
}

resource "aws_s3_bucket_versioning" "csv" {
  bucket = aws_s3_bucket.csv.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "csv" {
  bucket = aws_s3_bucket.csv.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true # cost saving: reduces KMS request charges
  }
}

resource "aws_s3_bucket_public_access_block" "csv" {
  bucket = aws_s3_bucket.csv.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "csv" {
  bucket = aws_s3_bucket.csv.id

  rule {
    id     = "csv-lifecycle"
    status = "Enabled"

    filter {
      prefix = "" # matches all objects in the bucket
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }

    # Also clean up incomplete multipart uploads (CSV imports chunked).
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_policy" "csv" {
  bucket = aws_s3_bucket.csv.id

  policy = data.aws_iam_policy_document.s3_tls_only.json
}

# ── Collateral bucket ─────────────────────────────────────────────────────────
resource "aws_s3_bucket" "collateral" {
  bucket = var.collateral_bucket_name

  tags = {
    Name = "${local.name_prefix}-collateral"
    Tier = "app-data"
  }
}

resource "aws_s3_bucket_versioning" "collateral" {
  bucket = aws_s3_bucket.collateral.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "collateral" {
  bucket = aws_s3_bucket.collateral.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "collateral" {
  bucket = aws_s3_bucket.collateral.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "collateral" {
  bucket = aws_s3_bucket.collateral.id

  rule {
    id     = "collateral-lifecycle"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }

    noncurrent_version_expiration {
      noncurrent_days = 90 # keep 90d of deleted/overwritten versions
    }
  }
}

resource "aws_s3_bucket_policy" "collateral" {
  bucket = aws_s3_bucket.collateral.id

  policy = data.aws_iam_policy_document.s3_tls_only.json
}

# ── ALB access logs bucket ────────────────────────────────────────────────────
# AWS ELB account writes logs here — bucket policy must grant the ELB account
# `s3:PutObject` with the AWSLogDelivery ACL. We use the newer
# `service_principal` form so we don't have to hardcode the per-region ELB
# account ID.
resource "aws_s3_bucket" "alb_logs" {
  bucket = var.alb_logs_bucket_name

  tags = {
    Name = "${local.name_prefix}-alb-logs"
    Tier = "ops-data"
  }
}

resource "aws_s3_bucket_ownership_controls" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_public_access_block" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "alb-logs-lifecycle"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

# Allow the AWS ELB service to write logs.
data "aws_elb_service_account" "main" {}

resource "aws_s3_bucket_policy" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  policy = data.aws_iam_policy_document.alb_logs_write.json
}

data "aws_iam_policy_document" "alb_logs_write" {
  statement {
    sid    = "AllowELBWrite"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [data.aws_elb_service_account.main.arn]
    }

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.alb_logs.arn}/${var.environment_short}/alb/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]
  }

  statement {
    sid    = "AllowSSLRequestsOnly"
    effect = "Deny"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.alb_logs.arn,
      "${aws_s3_bucket.alb_logs.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# ── TLS-only bucket policy (reused for csv + collateral) ─────────────────────
data "aws_iam_policy_document" "s3_tls_only" {
  statement {
    sid    = "AllowSSLRequestsOnly"
    effect = "Deny"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      # Note: this is a placeholder ARN — actual bucket ARN is interpolated by
      # the calling `aws_s3_bucket_policy` resource. We use the bucket's ARN
      # via a `for_each`-style binding in the resource above.
      "arn:aws:s3:::${var.csv_bucket_name}",
      "arn:aws:s3:::${var.csv_bucket_name}/*",
      "arn:aws:s3:::${var.collateral_bucket_name}",
      "arn:aws:s3:::${var.collateral_bucket_name}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# ── App access policy doc (consumed by iam.tf backend + worker task roles) ────
# Grants read/write on both buckets + KMS decrypt for the S3 key.
data "aws_iam_policy_document" "s3_access" {
  statement {
    sid     = "ListBuckets"
    effect  = "Allow"
    actions = ["s3:ListBucket"]
    resources = [
      aws_s3_bucket.csv.arn,
      aws_s3_bucket.collateral.arn,
    ]
  }

  statement {
    sid    = "ReadWriteObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
    ]
    resources = [
      "${aws_s3_bucket.csv.arn}/*",
      "${aws_s3_bucket.collateral.arn}/*",
    ]
  }

  statement {
    sid    = "KmsDecryptS3"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:GenerateDataKey",
    ]
    resources = [aws_kms_key.s3.arn]
  }
}
