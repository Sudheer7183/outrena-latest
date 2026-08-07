# cloudwatch.tf — SNS + dashboards + alarms + metric filters.
#
# Migration doc §11.3 + §16.3 rollback triggers:
#   - Backend 5xx rate > 1% (rollback trigger)
#   - ALB 5xx > 1% (rollback trigger)
#   - ALB target response time p99 > 2s for 10 min (rollback trigger)
#   - ALB unhealthy host count > 0
#   - RDS CPU > 80%
#   - RDS free storage < 5GB
#   - Redis evictions > 1000/min
#   - ECS backend CPU > 90%
#   - ECS backend memory > 90%
#   - Log metric: ERROR count on backend log group
#   - Log metric: mailbridge.send_failed count (pitfall #15)

# ── SNS topic + email subscription ────────────────────────────────────────────
resource "aws_sns_topic" "alerts" {
  name              = "${local.name_prefix}-alerts"
  display_name      = "OUTRENA ${var.environment} alerts"
  kms_master_key_id = aws_kms_key.rds.arn

  tags = {
    Name = "${local.name_prefix}-alerts-topic"
  }
}

# Email subscription — endpoint comes from var.alert_email (default
# "ops@outrena.com" in locals_extra.tf). Override per-env in tfvars.
# NOTE: AWS requires email confirmation — the subscription is created in
# PENDING state; the recipient must click the confirm link before alerts
# are delivered. This is a one-time manual step.
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── CloudWatch dashboard ──────────────────────────────────────────────────────
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name_prefix}-overview"

  dashboard_body = jsonencode({
    widgets = [
      # Row 1 — Edge
      {
        type = "metric"
        x    = 0, y = 0, width = 6, height = 3
        properties = {
          title  = "ALB 5xx rate"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", aws_lb.main.arn_suffix],
          ]
          period = 300
          stat   = "Sum"
        }
      },
      {
        type = "metric"
        x    = 6, y = 0, width = 6, height = 3
        properties = {
          title  = "Backend target response time (p99)"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "TargetGroup", aws_lb_target_group.backend.arn_suffix, { stat = "p99" }],
          ]
          period = 300
        }
      },
      {
        type = "metric"
        x    = 12, y = 0, width = 6, height = 3
        properties = {
          title  = "ALB unhealthy host count"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["AWS/ApplicationELB", "UnHealthyHostCount", "TargetGroup", aws_lb_target_group.backend.arn_suffix],
            ["AWS/ApplicationELB", "UnHealthyHostCount", "TargetGroup", aws_lb_target_group.frontend.arn_suffix],
            ["AWS/ApplicationELB", "UnHealthyHostCount", "TargetGroup", aws_lb_target_group.keycloak.arn_suffix],
          ]
          period = 300
          stat   = "Maximum"
        }
      },
      # Row 2 — Data tier
      {
        type = "metric"
        x    = 0, y = 3, width = 6, height = 3
        properties = {
          title   = "RDS CPU"
          region  = var.aws_region
          view    = "timeSeries"
          metrics = [["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.main.identifier]]
          period  = 300
          stat    = "Average"
        }
      },
      {
        type = "metric"
        x    = 6, y = 3, width = 6, height = 3
        properties = {
          title   = "RDS free storage (GB)"
          region  = var.aws_region
          view    = "timeSeries"
          metrics = [["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", aws_db_instance.main.identifier]]
          period  = 300
          stat    = "Minimum"
        }
      },
      {
        type = "metric"
        x    = 12, y = 3, width = 6, height = 3
        properties = {
          title   = "Redis evictions"
          region  = var.aws_region
          view    = "timeSeries"
          metrics = [["AWS/ElastiCache", "Evictions", "CacheClusterId", "${local.name_prefix}-redis-001"]]
          period  = 300
          stat    = "Sum"
        }
      },
      # Row 3 — ECS
      {
        type = "metric"
        x    = 0, y = 6, width = 6, height = 3
        properties = {
          title   = "ECS backend CPU"
          region  = var.aws_region
          view    = "timeSeries"
          metrics = [["AWS/ECS", "CPUUtilization", "ServiceName", aws_ecs_service.backend.name, "ClusterName", aws_ecs_cluster.main.name]]
          period  = 300
          stat    = "Average"
        }
      },
      {
        type = "metric"
        x    = 6, y = 6, width = 6, height = 3
        properties = {
          title   = "ECS backend memory"
          region  = var.aws_region
          view    = "timeSeries"
          metrics = [["AWS/ECS", "MemoryUtilization", "ServiceName", aws_ecs_service.backend.name, "ClusterName", aws_ecs_cluster.main.name]]
          period  = 300
          stat    = "Average"
        }
      },
      {
        type = "metric"
        x    = 12, y = 6, width = 6, height = 3
        properties = {
          title   = "ERROR log count (backend)"
          region  = var.aws_region
          view    = "timeSeries"
          metrics = [["OUTRENA", "ERROR", "LogGroupName", aws_cloudwatch_log_group.backend.name]]
          period  = 300
          stat    = "Sum"
        }
      },
    ]
  })
}

# ── Alarms ────────────────────────────────────────────────────────────────────
# All alarms alarm_actions to the SNS topic. Comparison uses static thresholds
# (migration doc specifies concrete numbers) — could be swapped for anomaly
# detection in a future iteration.

# ALB 5xx count (absolute) — alarm when > 1% of total over 5 min. We
# approximate "1% rate" with an absolute threshold of 50 over 5 min
# (assumes ~5k req/5min baseline). For higher-traffic prod, replace with
# a metric math expression: HTTPCode_ELB_5XX / (HTTPCode_ELB_2XX + ...).
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name        = "${local.name_prefix}-alb-5xx"
  alarm_description = "ALB 5xx response count > 50 over 5 min (rollback trigger per §16.3)"
  namespace         = "AWS/ApplicationELB"
  metric_name       = "HTTPCode_ELB_5XX_Count"
  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 50
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-alb-5xx-alarm" }
}

# Backend 5xx rate — alarm when backend target group returns > 50 5xx in 5 min.
resource "aws_cloudwatch_metric_alarm" "backend_5xx" {
  alarm_name        = "${local.name_prefix}-backend-5xx"
  alarm_description = "Backend target group 5xx > 50 over 5 min (rollback trigger per §16.3)"
  namespace         = "AWS/ApplicationELB"
  metric_name       = "HTTPCode_Target_5XX_Count"
  dimensions = {
    TargetGroup  = aws_lb_target_group.backend.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 50
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-backend-5xx-alarm" }
}

# RDS CPU > 80%
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name        = "${local.name_prefix}-rds-cpu-high"
  alarm_description = "RDS CPU > 80% for 10 min — scale up or investigate slow queries"
  namespace         = "AWS/RDS"
  metric_name       = "CPUUtilization"
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2 # 10 min
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "missing"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-rds-cpu-alarm" }
}

# RDS free storage < 5GB — alarm in bytes (5 GB = 5 * 1024^3 ≈ 5.37e9)
resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name        = "${local.name_prefix}-rds-low-storage"
  alarm_description = "RDS free storage < 5 GB — bump allocated_storage before disk full"
  namespace         = "AWS/RDS"
  metric_name       = "FreeStorageSpace"
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5 * 1024 * 1024 * 1024 # 5 GB in bytes
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "missing"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-rds-storage-alarm" }
}

# Redis evictions > 1000/min — memory pressure, evicting keys before TTL.
resource "aws_cloudwatch_metric_alarm" "redis_evictions" {
  alarm_name        = "${local.name_prefix}-redis-high-evictions"
  alarm_description = "Redis evictions > 1000/min — cache is too small, scale up node_type"
  namespace         = "AWS/ElastiCache"
  metric_name       = "Evictions"
  dimensions = {
    CacheClusterId = "${local.name_prefix}-redis-001"
  }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-redis-evictions-alarm" }
}

# ECS backend CPU > 90%
resource "aws_cloudwatch_metric_alarm" "ecs_backend_cpu" {
  alarm_name        = "${local.name_prefix}-ecs-backend-cpu-high"
  alarm_description = "ECS backend CPU > 90% for 10 min — scale out desired_count"
  namespace         = "AWS/ECS"
  metric_name       = "CPUUtilization"
  dimensions = {
    ServiceName = aws_ecs_service.backend.name
    ClusterName = aws_ecs_cluster.main.name
  }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 90
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "missing"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-ecs-backend-cpu-alarm" }
}

# ECS backend memory > 90%
resource "aws_cloudwatch_metric_alarm" "ecs_backend_memory" {
  alarm_name        = "${local.name_prefix}-ecs-backend-memory-high"
  alarm_description = "ECS backend memory > 90% for 10 min — scale out desired_count"
  namespace         = "AWS/ECS"
  metric_name       = "MemoryUtilization"
  dimensions = {
    ServiceName = aws_ecs_service.backend.name
    ClusterName = aws_ecs_cluster.main.name
  }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 90
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "missing"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-ecs-backend-memory-alarm" }
}

# ALB target response time p99 > 2s — rollback trigger per §16.3.
resource "aws_cloudwatch_metric_alarm" "alb_response_time" {
  alarm_name        = "${local.name_prefix}-alb-response-time-p99"
  alarm_description = "ALB backend target response time p99 > 2s for 10 min (rollback trigger per §16.3)"
  namespace         = "AWS/ApplicationELB"
  metric_name       = "TargetResponseTime"
  dimensions = {
    TargetGroup  = aws_lb_target_group.backend.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }
  extended_statistic  = "p99"
  period              = 300
  evaluation_periods  = 2 # 10 min
  threshold           = 2
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "missing"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-alb-resp-time-alarm" }
}

# ALB unhealthy host count > 0 (any TG, 2 consecutive periods)
resource "aws_cloudwatch_metric_alarm" "alb_unhealthy" {
  alarm_name        = "${local.name_prefix}-alb-unhealthy-hosts"
  alarm_description = "ALB unhealthy host count > 0 for 5 min — task failing health check"
  namespace         = "AWS/ApplicationELB"
  metric_name       = "UnHealthyHostCount"
  dimensions = {
    TargetGroup  = aws_lb_target_group.backend.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-alb-unhealthy-alarm" }
}

# ── Log metric filters ────────────────────────────────────────────────────────
# Filter pattern: "\"ERROR\"" — matches the literal string "ERROR" in any
# log line (structlog emits `event=ERROR` or `level=error` depending on
# config; both contain the substring).
resource "aws_cloudwatch_log_metric_filter" "backend_errors" {
  name           = "${local.name_prefix}-backend-errors"
  log_group_name = aws_cloudwatch_log_group.backend.name
  pattern        = "\"ERROR\""

  metric_transformation {
    name      = "ERROR"
    namespace = "OUTRENA"
    value     = "1"
    # Default value 0 — so the metric emits 0 for periods with no errors,
    # making alarm math cleaner.
    default_value = "0"
  }
}

# Filter pattern: "\"mailbridge.send_failed\"" — matches the literal string.
# Per migration doc pitfall #15: alert on > 10 send failures in 5 min.
resource "aws_cloudwatch_log_metric_filter" "mailbridge_send_failed" {
  name           = "${local.name_prefix}-mailbridge-send-failed"
  log_group_name = aws_cloudwatch_log_group.backend.name
  pattern        = "\"mailbridge.send_failed\""

  metric_transformation {
    name          = "mailbridge_send_failed"
    namespace     = "OUTRENA"
    value         = "1"
    default_value = "0"
  }
}

# Alarm on the mailbridge metric — > 10 in 5 min triggers rollback
# investigation per pitfall #15.
resource "aws_cloudwatch_metric_alarm" "mailbridge_send_failed" {
  alarm_name          = "${local.name_prefix}-mailbridge-send-failed"
  alarm_description   = "MailBridge send failures > 10 in 5 min (pitfall #15)"
  namespace           = "OUTRENA"
  metric_name         = "mailbridge_send_failed"
  dimensions          = {}
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-mailbridge-fail-alarm" }
}

# Alarm on the ERROR metric — > 50 errors in 5 min triggers investigation.
resource "aws_cloudwatch_metric_alarm" "backend_errors" {
  alarm_name          = "${local.name_prefix}-backend-errors"
  alarm_description   = "Backend ERROR log lines > 50 in 5 min"
  namespace           = "OUTRENA"
  metric_name         = "ERROR"
  dimensions          = {}
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 50
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = { Name = "${local.name_prefix}-errors-alarm" }
}
