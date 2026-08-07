# cloudtrail.tf — CloudTrail + AWS Config + SOC2 security-event alarms.
#
# Implements SOC2 Trust Service Criteria CC7.2 (system monitoring) + CC7.3
# (incident detection / response). Closes the SURVEY-INFRA gap A1 + A11:
# account-level audit logging was relied on but not codified; security-event
# alarms (root login, IAM/SG changes, console login without MFA) were absent.
#
# Resources created here:
#   - aws_kms_key.cloudtrail              — dedicated CMK for CloudTrail log encryption
#   - aws_s3_bucket.cloudtrail_logs       — multi-region trail destination
#   - aws_cloudtrail.outrena              — multi-region trail, log-file validation,
#                                           CloudWatch Logs integration
#   - aws_cloudwatch_log_group.cloudtrail — 365-day retention (SOC2 7-year evidence
#                                           is the S3 bucket lifecycle)
#   - aws_iam_role.cloudtrail_cloudwatch  — CloudTrail → CW Logs delivery
#   - aws_config_configuration_recorder   — record all supported resources
#   - aws_config_delivery_channel         — deliver Config snapshots to S3
#   - aws_iam_role.config                 — Config service role
#   - aws_sns_topic.security_alerts       — separate topic for SOC2 security alarms
#                                            (kept off the ops SNS topic so alerts
#                                            can be routed to the security team)
#   - aws_cloudwatch_log_metric_filter × 6 — pattern match on CloudTrail events
#   - aws_cloudwatch_metric_alarm × 6      — alarm on the metric filters
#
# Naming + tagging follow the AWS conventions in main.tf: every resource-level
# tag block sets `Name = "${local.name_prefix}-<purpose>"` (Project / Environment
# / ManagedBy / Repo come from the provider default_tags block in versions.tf).

# ── KMS key for CloudTrail log encryption ────────────────────────────────────
# CloudTrail requires a key policy statement granting cloudtrail.amazonaws.com
# the Encrypt + GenerateDataKey* actions (see AWS docs — "CloudTrail requires
# the key policy to allow the service to encrypt"). Reuses the same shape as
# the RDS / S3 KMS keys (root account full access + service principal scoped).
resource "aws_kms_key" "cloudtrail" {
  description             = "KMS key for CloudTrail + AWS Config log encryption (SOC2 CC7.2)"
  deletion_window_in_days = 30
  enable_key_rotation     = var.enable_kms_key_rotation

  policy = data.aws_iam_policy_document.kms_cloudtrail.json

  tags = {
    Name = "${local.name_prefix}-kms-cloudtrail"
  }
}

resource "aws_kms_alias" "cloudtrail" {
  name          = "alias/${local.name_prefix}-cloudtrail"
  target_key_id = aws_kms_key.cloudtrail.key_id
}

data "aws_iam_policy_document" "kms_cloudtrail" {
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

  # Allow CloudTrail to encrypt logs + describe the key.
  statement {
    sid    = "AllowCloudTrailToEncryptLogs"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
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

  # Allow CloudWatch Logs to decrypt so the metric filters can read events.
  statement {
    sid    = "AllowCloudWatchLogsToDecrypt"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["logs.${data.aws_region.current.name}.amazonaws.com"]
    }

    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:GenerateDataKey*",
    ]

    resources = ["*"]
  }
}

# ── S3 bucket for CloudTrail logs ────────────────────────────────────────────
# Lifecycle: STANDARD (90d) → GLACIER (180d) → expire (365d).
# SOC2 guidance is 7-year audit log retention; we cost-optimise by keeping only
# 1y hot in S3 + rely on the CloudWatch Logs group (365d) + manual exports to
# an archive bucket at quarter-close. Runbook 10-soc2-compliance.md documents
# the quarterly export-to-archive procedure.
resource "aws_s3_bucket" "cloudtrail_logs" {
  bucket = var.cloudtrail_logs_bucket_name

  tags = {
    Name = "${local.name_prefix}-cloudtrail-logs"
    Tier = "audit-data"
  }
}

resource "aws_s3_bucket_versioning" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.cloudtrail.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  rule {
    id     = "cloudtrail-logs-lifecycle"
    status = "Enabled"

    filter {
      prefix = ""
    }

    # SOC2 evidence: keep hot 90d, then Glacier-cold 180d, expire at 365d.
    # Quarterly exports (runbook 10) preserve audit-relevant slices for 7y.
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# CloudTrail bucket policy — required shape per AWS docs:
#   1. CloudTrail service gets s3:GetBucketAcl + s3:PutObject on the log prefix.
#   2. TLS-only transport (deny http://).
resource "aws_s3_bucket_policy" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  policy = data.aws_iam_policy_document.cloudtrail_logs.json
}

data "aws_iam_policy_document" "cloudtrail_logs" {
  statement {
    sid    = "AWSCloudTrailAclCheck"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }

    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.cloudtrail_logs.arn]
  }

  statement {
    sid    = "AWSCloudTrailWrite"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.cloudtrail_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }

  # AWS Config also delivers snapshots to this bucket (under the Config prefix).
  statement {
    sid    = "AWSConfigWrite"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["config.amazonaws.com"]
    }

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.cloudtrail_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/Config/*"]

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }

  # TLS-only — deny any non-SSL request to the bucket.
  statement {
    sid    = "AllowSSLRequestsOnly"
    effect = "Deny"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.cloudtrail_logs.arn,
      "${aws_s3_bucket.cloudtrail_logs.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# ── CloudWatch Logs group for CloudTrail ─────────────────────────────────────
# 365-day retention — provides hot-queryable security-event data for SOC2 CC7.2.
resource "aws_cloudwatch_log_group" "cloudtrail" {
  name              = "/aws/cloudtrail/${local.name_prefix}"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.cloudtrail.arn

  tags = {
    Name = "${local.name_prefix}-cloudtrail-log-group"
  }
}

# ── IAM role: CloudTrail → CloudWatch Logs delivery ──────────────────────────
data "aws_iam_policy_document" "cloudtrail_cloudwatch_trust" {
  statement {
    sid     = "AllowCloudTrailAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cloudtrail_cloudwatch" {
  name               = "${local.name_prefix}-cloudtrail-cw"
  assume_role_policy = data.aws_iam_policy_document.cloudtrail_cloudwatch_trust.json

  tags = {
    Name = "${local.name_prefix}-cloudtrail-cw-role"
  }
}

data "aws_iam_policy_document" "cloudtrail_cloudwatch" {
  statement {
    sid    = "AllowCreateLogStream"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "${aws_cloudwatch_log_group.cloudtrail.arn}:*",
    ]
  }
}

resource "aws_iam_role_policy" "cloudtrail_cloudwatch" {
  name   = "${local.name_prefix}-cloudtrail-cw"
  role   = aws_iam_role.cloudtrail_cloudwatch.id
  policy = data.aws_iam_policy_document.cloudtrail_cloudwatch.json
}

# ── CloudTrail ───────────────────────────────────────────────────────────────
resource "aws_cloudtrail" "outrena" {
  name                          = "${local.name_prefix}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  s3_key_prefix                 = "AWSLogs/${data.aws_caller_identity.current.account_id}"
  kms_key_id                    = aws_kms_key.cloudtrail.arn
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_logging                = true
  enable_log_file_validation    = true

  cloud_watch_logs_role_arn  = aws_iam_role.cloudtrail_cloudwatch.arn
  cloud_watch_logs_group_arn = aws_cloudwatch_log_group.cloudtrail.arn

  # Event selector — log all management events. We exclude KMS Decrypt events
  # (high-volume, rarely security-relevant) to control CloudTrail costs.
  # `exclude_management_event_sources` is the supported way to filter.
  event_selector {
    read_write_type           = "All"
    include_management_events = true

    exclude_management_event_sources = [
      # KMS Decrypt is high-volume and rarely security-relevant — exclude to
      # control cost. Re-include if a SOC2 auditor requests it.
      "kms.amazonaws.com",
    ]
  }

  # CloudTrail will not start logging until the bucket policy is in place.
  depends_on = [
    aws_s3_bucket_policy.cloudtrail_logs,
    aws_iam_role_policy.cloudtrail_cloudwatch,
  ]

  tags = {
    Name = "${local.name_prefix}-cloudtrail"
  }
}

# ── AWS Config ───────────────────────────────────────────────────────────────
# Records configuration state of all supported resources in the account/region
# for change-tracking + compliance queries (SOC2 CC7.1). Snapshots delivered to
# the same CloudTrail S3 bucket under /Config.

# IAM role for Config service.
data "aws_iam_policy_document" "config_trust" {
  statement {
    sid     = "AllowConfigAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["config.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "config" {
  name               = "${local.name_prefix}-config"
  assume_role_policy = data.aws_iam_policy_document.config_trust.json

  tags = {
    Name = "${local.name_prefix}-config-role"
  }
}

# AWS-managed policy: AWS_ConfigRole (read-only access to all resource metadata).
resource "aws_iam_role_policy_attachment" "config" {
  role       = aws_iam_role.config.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/ConfigRole"
}

# Inline policy: allow Config to write snapshots to the CloudTrail S3 bucket.
data "aws_iam_policy_document" "config_delivery" {
  statement {
    sid    = "AllowConfigDelivery"
    effect = "Allow"

    actions = [
      "s3:PutObject",
      "s3:GetBucketAcl",
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.cloudtrail_logs.arn,
      "${aws_s3_bucket.cloudtrail_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/Config/*",
    ]
  }
}

resource "aws_iam_role_policy" "config_delivery" {
  name   = "${local.name_prefix}-config-delivery"
  role   = aws_iam_role.config.id
  policy = data.aws_iam_policy_document.config_delivery.json
}

resource "aws_config_configuration_recorder" "outrena" {
  name     = "${local.name_prefix}-recorder"
  role_arn = aws_iam_role.config.arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }
}

resource "aws_config_delivery_channel" "outrena" {
  name           = "${local.name_prefix}-delivery"
  s3_bucket_name = aws_s3_bucket.cloudtrail_logs.id
  s3_key_prefix  = "AWSLogs/${data.aws_caller_identity.current.account_id}/Config"

  # Snapshot every 6 hours (cost-aware — increase to 1h if auditor requires).
  snapshot_delivery_properties {
    delivery_frequency = "Six_Hours"
  }

  depends_on = [
    aws_config_configuration_recorder.outrena,
    aws_iam_role_policy.config_delivery,
  ]
}

resource "aws_config_configuration_recorder_status" "outrena" {
  name       = aws_config_configuration_recorder.outrena.name
  is_enabled = true

  depends_on = [aws_config_delivery_channel.outrena]
}

# ── SNS topic: SOC2 security alerts ──────────────────────────────────────────
# Separate topic from the ops alerts topic (cloudwatch.tf) so security alerts
# can be routed to the security team on-call rotation without leaking
# operational noise to them.
resource "aws_sns_topic" "security_alerts" {
  name              = "${local.name_prefix}-security-alerts"
  display_name      = "OUTRENA ${var.environment} SOC2 security alerts"
  kms_master_key_id = aws_kms_key.rds.arn

  tags = {
    Name = "${local.name_prefix}-security-alerts-topic"
  }
}

resource "aws_sns_topic_subscription" "security_alerts_email" {
  topic_arn = aws_sns_topic.security_alerts.arn
  protocol  = "email"
  endpoint  = var.security_alert_email
}

# ── Metric filters on the CloudTrail CloudWatch Logs group ───────────────────
# Each filter matches a CloudTrail event pattern and emits a 1-per-occurrence
# metric to the OUTRENA_Security namespace; an alarm fires on threshold.

# 1. Unauthorized API calls — any errorCode="UnauthorizedOperation" or
#    "AccessDenied" event in the trail.
resource "aws_cloudwatch_log_metric_filter" "unauthorized_api_calls" {
  name           = "${local.name_prefix}-unauthorized-api-calls"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = <<PATTERN
{ ($.errorCode = "*UnauthorizedOperation") || ($.errorCode = "AccessDenied*") }
PATTERN

  metric_transformation {
    name          = "UnauthorizedAPICalls"
    namespace     = "OUTRENA_Security"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "unauthorized_api_calls" {
  alarm_name        = "${local.name_prefix}-unauthorized-api-calls"
  alarm_description = "SOC2 CC7.2 — > 10 unauthorized API calls in 5 min (potential privilege escalation)"
  namespace         = "OUTRENA_Security"
  metric_name       = "UnauthorizedAPICalls"
  dimensions        = {}

  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.security_alerts.arn]
  ok_actions    = [aws_sns_topic.security_alerts.arn]

  tags = { Name = "${local.name_prefix}-unauthorized-api-calls-alarm" }
}

# 2. Root account login — any ConsoleLogin or API call by the root principal.
resource "aws_cloudwatch_log_metric_filter" "root_login" {
  name           = "${local.name_prefix}-root-login"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = <<PATTERN
{$.userIdentity.type = "root" && ($.eventName = "ConsoleLogin" || $.eventType = "AwsApiCall")}
PATTERN

  metric_transformation {
    name          = "RootLogin"
    namespace     = "OUTRENA_Security"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "root_login" {
  alarm_name        = "${local.name_prefix}-root-login"
  alarm_description = "SOC2 CC6.1 — root account used (any usage is anomalous; investigate immediately)"
  namespace         = "OUTRENA_Security"
  metric_name       = "RootLogin"
  dimensions        = {}

  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.security_alerts.arn]
  ok_actions    = [aws_sns_topic.security_alerts.arn]

  tags = { Name = "${local.name_prefix}-root-login-alarm" }
}

# 3. IAM policy changes — CreatePolicy, AttachRolePolicy, PutRolePolicy, etc.
resource "aws_cloudwatch_log_metric_filter" "iam_policy_changes" {
  name           = "${local.name_prefix}-iam-policy-changes"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = <<PATTERN
{($.eventName=DeleteGroupPolicy)||($.eventName=DeleteRolePolicy)||($.eventName=DeleteUserPolicy)||($.eventName=PutGroupPolicy)||($.eventName=PutRolePolicy)||($.eventName=PutUserPolicy)||($.eventName=CreatePolicy)||($.eventName=DeletePolicy)||($.eventName=CreatePolicyVersion)||($.eventName=DeletePolicyVersion)||($.eventName=AttachRolePolicy)||($.eventName=DetachRolePolicy)||($.eventName=AttachUserPolicy)||($.eventName=DetachUserPolicy)}
PATTERN

  metric_transformation {
    name          = "IAMPolicyChanges"
    namespace     = "OUTRENA_Security"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "iam_policy_changes" {
  alarm_name        = "${local.name_prefix}-iam-policy-changes"
  alarm_description = "SOC2 CC6.1 — IAM policy change in the last 5 min (verify via change-management ticket)"
  namespace         = "OUTRENA_Security"
  metric_name       = "IAMPolicyChanges"
  dimensions        = {}

  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.security_alerts.arn]
  ok_actions    = [aws_sns_topic.security_alerts.arn]

  tags = { Name = "${local.name_prefix}-iam-policy-changes-alarm" }
}

# 4. Security group changes — AuthorizeSecurityGroupIngress/Egress, etc.
resource "aws_cloudwatch_log_metric_filter" "security_group_changes" {
  name           = "${local.name_prefix}-security-group-changes"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = <<PATTERN
{($.eventName=AuthorizeSecurityGroupIngress)||($.eventName=AuthorizeSecurityGroupEgress)||($.eventName=RevokeSecurityGroupIngress)||($.eventName=RevokeSecurityGroupEgress)||($.eventName=CreateSecurityGroup)||($.eventName=DeleteSecurityGroup)}
PATTERN

  metric_transformation {
    name          = "SecurityGroupChanges"
    namespace     = "OUTRENA_Security"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "security_group_changes" {
  alarm_name        = "${local.name_prefix}-security-group-changes"
  alarm_description = "SOC2 CC6.6 — security group change in the last 5 min (verify via change ticket)"
  namespace         = "OUTRENA_Security"
  metric_name       = "SecurityGroupChanges"
  dimensions        = {}

  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.security_alerts.arn]
  ok_actions    = [aws_sns_topic.security_alerts.arn]

  tags = { Name = "${local.name_prefix}-sg-changes-alarm" }
}

# 5. S3 bucket policy changes — PutBucketAcl, PutBucketPolicy, DeleteBucket.
resource "aws_cloudwatch_log_metric_filter" "s3_policy_changes" {
  name           = "${local.name_prefix}-s3-policy-changes"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = <<PATTERN
{($.eventName=PutBucketAcl)||($.eventName=PutBucketPolicy)||($.eventName=DeleteBucketPolicy)||($.eventName=DeleteBucket)||($.eventName=CreateBucket)}
PATTERN

  metric_transformation {
    name          = "S3PolicyChanges"
    namespace     = "OUTRENA_Security"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "s3_policy_changes" {
  alarm_name        = "${local.name_prefix}-s3-policy-changes"
  alarm_description = "SOC2 CC6.6 — S3 bucket policy change in the last 5 min (verify via change ticket)"
  namespace         = "OUTRENA_Security"
  metric_name       = "S3PolicyChanges"
  dimensions        = {}

  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.security_alerts.arn]
  ok_actions    = [aws_sns_topic.security_alerts.arn]

  tags = { Name = "${local.name_prefix}-s3-policy-changes-alarm" }
}

# 6. Console login without MFA — any ConsoleLogin where additionalEventData.MFAUsed != "Yes".
resource "aws_cloudwatch_log_metric_filter" "console_login_no_mfa" {
  name           = "${local.name_prefix}-console-login-no-mfa"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = <<PATTERN
{ ($.eventName = "ConsoleLogin") && ($.additionalEventData.MFAUsed != "Yes") }
PATTERN

  metric_transformation {
    name          = "ConsoleLoginNoMFA"
    namespace     = "OUTRENA_Security"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "console_login_no_mfa" {
  alarm_name        = "${local.name_prefix}-console-login-no-mfa"
  alarm_description = "SOC2 CC6.1 — AWS console login without MFA in the last 5 min (potential credential compromise)"
  namespace         = "OUTRENA_Security"
  metric_name       = "ConsoleLoginNoMFA"
  dimensions        = {}

  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.security_alerts.arn]
  ok_actions    = [aws_sns_topic.security_alerts.arn]

  tags = { Name = "${local.name_prefix}-console-login-no-mfa-alarm" }
}
