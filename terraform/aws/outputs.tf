# outputs.tf — Stack outputs.
#
# Sensitive outputs (RDS master password, Redis AUTH token, Keycloak admin
# password) are NOT exposed as Terraform outputs — they live exclusively in
# Secrets Manager. Operators retrieve via `aws secretsmanager get-secret-value`.

output "alb_dns_name" {
  description = "Public DNS name of the OUTRENA ALB. Set Route 53 records to this (alias)."
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Route 53 zone ID of the ALB (for alias records)."
  value       = aws_lb.main.zone_id
}

output "alb_arn" {
  description = "ALB ARN."
  value       = aws_lb.main.arn
}

output "rds_endpoint" {
  description = "RDS PostgreSQL writer endpoint (host:port)."
  value       = aws_db_instance.main.endpoint
}

output "rds_address" {
  description = "RDS PostgreSQL writer address (host only)."
  value       = aws_db_instance.main.address
}

output "rds_arn" {
  description = "RDS instance ARN."
  value       = aws_db_instance.main.arn
}

output "redis_primary_endpoint" {
  description = "ElastiCache Redis primary endpoint (host:port). Non-cluster mode only."
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "redis_configuration_endpoint" {
  description = "ElastiCache Redis configuration endpoint (host:port). Cluster mode only."
  value       = aws_elasticache_replication_group.main.configuration_endpoint_address
}

output "redis_arn" {
  description = "ElastiCache replication group ARN."
  value       = aws_elasticache_replication_group.main.arn
}

output "ecr_backend_repository_url" {
  description = "ECR repo URL for the backend + worker image."
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_repository_url" {
  description = "ECR repo URL for the frontend image."
  value       = aws_ecr_repository.frontend.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN."
  value       = aws_ecs_cluster.main.arn
}

output "cloudwatch_log_group_backend" {
  description = "CloudWatch log group name for the backend."
  value       = aws_cloudwatch_log_group.backend.name
}

output "cloudwatch_log_group_frontend" {
  description = "CloudWatch log group name for the frontend."
  value       = aws_cloudwatch_log_group.frontend.name
}

output "cloudwatch_log_group_worker" {
  description = "CloudWatch log group name for the Celery worker."
  value       = aws_cloudwatch_log_group.worker.name
}

output "cloudwatch_log_group_keycloak" {
  description = "CloudWatch log group name for Keycloak."
  value       = aws_cloudwatch_log_group.keycloak.name
}

output "cloudwatch_dashboard_url" {
  description = "Direct URL to the OUTRENA CloudWatch dashboard."
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "secretsmanager_rds_master_arn" {
  description = "Secrets Manager secret ARN for the RDS master password."
  value       = aws_secretsmanager_secret.rds_master.arn
}

output "secretsmanager_database_url_arn" {
  description = "Secrets Manager secret ARN for the backend DATABASE_URL."
  value       = aws_secretsmanager_secret.database_url.arn
}

output "secretsmanager_redis_auth_arn" {
  description = "Secrets Manager secret ARN for the Redis AUTH token."
  value       = aws_secretsmanager_secret.redis_auth.arn
}

output "secretsmanager_keycloak_admin_arn" {
  description = "Secrets Manager secret ARN for the Keycloak admin credentials."
  value       = aws_secretsmanager_secret.keycloak_admin.arn
}

output "secretsmanager_keycloak_db_arn" {
  description = "Secrets Manager secret ARN for the Keycloak DB role credentials."
  value       = aws_secretsmanager_secret.keycloak_db.arn
}

output "route53_zone_id" {
  description = "Route 53 hosted zone ID for var.base_domain."
  value       = aws_route53_zone.main[0].zone_id
}

output "route53_zone_name_servers" {
  description = "Route 53 hosted zone name servers. Set these at the registrar."
  value       = aws_route53_zone.main[0].name_servers
}

output "acm_certificate_arn" {
  description = "ACM wildcard certificate ARN (issued state)."
  value       = aws_acm_certificate_validation.main.certificate_arn
}

output "s3_csv_bucket" {
  description = "S3 bucket name for CSV uploads."
  value       = aws_s3_bucket.csv.bucket
}

output "s3_collateral_bucket" {
  description = "S3 bucket name for sales collateral."
  value       = aws_s3_bucket.collateral.bucket
}

output "s3_alb_logs_bucket" {
  description = "S3 bucket name for ALB access logs."
  value       = aws_s3_bucket.alb_logs.bucket
}

output "sns_alerts_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarms. Subscribe via var.alert_email."
  value       = aws_sns_topic.alerts.arn
}

output "waf_web_acl_arn" {
  description = "WAFv2 Web ACL ARN attached to the ALB."
  value       = aws_wafv2_web_acl.main.arn
}

output "kms_key_s3_arn" {
  description = "KMS key ARN for S3 SSE."
  value       = aws_kms_key.s3.arn
}

output "kms_key_rds_arn" {
  description = "KMS key ARN for RDS storage encryption."
  value       = aws_kms_key.rds.arn
}

output "kms_key_redis_arn" {
  description = "KMS key ARN for ElastiCache at-rest encryption."
  value       = aws_kms_key.redis.arn
}

# ── SOC2 / CloudTrail / Secrets rotation outputs (SAAS-INFRA) ────────────────
output "cloudtrail_arn" {
  description = "CloudTrail trail ARN — multi-region trail with KMS encryption + log file validation."
  value       = aws_cloudtrail.outrena.arn
}

output "cloudtrail_log_group_name" {
  description = "CloudWatch Logs group name where CloudTrail events are streamed (365d retention, KMS-encrypted)."
  value       = aws_cloudwatch_log_group.cloudtrail.name
}

output "cloudtrail_logs_bucket" {
  description = "S3 bucket name for CloudTrail + AWS Config logs (90d STANDARD-IA, 180d GLACIER, 365d expire)."
  value       = aws_s3_bucket.cloudtrail_logs.bucket
}

output "kms_key_cloudtrail_arn" {
  description = "KMS key ARN for CloudTrail log encryption."
  value       = aws_kms_key.cloudtrail.arn
}

output "config_recorder_name" {
  description = "AWS Config configuration recorder name (records all supported resources for SOC2 CC7.1)."
  value       = aws_config_configuration_recorder.outrena.name
}

output "sns_security_alerts_topic_arn" {
  description = "SNS topic ARN for SOC2 security alerts (separate from the ops alerts topic). Subscribed via var.security_alert_email."
  value       = aws_sns_topic.security_alerts.arn
}

output "secret_rotation_rds_lambda_arn" {
  description = "Lambda ARN for RDS / DATABASE_URL / Keycloak DB secret rotation (delegates to AWS-provided SecretsManagerRDSPostgreSQLRotationSingleUser template)."
  value       = aws_lambda_function.secret_rotation_rds.arn
}

output "secret_rotation_generic_lambda_arn" {
  description = "Lambda ARN for generic app-level secret rotation (Keycloak admin, Redis AUTH, MailBridge URL)."
  value       = aws_lambda_function.secret_rotation_generic.arn
}

output "secret_rotation_check_lambda_arn" {
  description = "Lambda ARN for the daily rotation-check safety-net (triggered by EventBridge rate(1 day))."
  value       = aws_lambda_function.rotation_check.arn
}

output "secret_rotation_log_group_name" {
  description = "CloudWatch Logs group name for the rotation Lambda (90d retention, KMS-encrypted)."
  value       = aws_cloudwatch_log_group.secret_rotation.name
}

# ── Convenience: full stack summary ───────────────────────────────────────────
output "stack_summary" {
  description = "Human-readable summary of the deployed stack — useful for runbooks."
  value       = <<-EOT

    OUTRENA ${var.environment} stack summary
    ─────────────────────────────────────────────────
    ALB DNS:           ${aws_lb.main.dns_name}
    Base domain:       ${var.base_domain}
    Route 53 zone:     ${aws_route53_zone.main[0].zone_id} (${var.base_domain})

    RDS endpoint:      ${aws_db_instance.main.endpoint}
    Redis endpoint:    ${aws_elasticache_replication_group.main.primary_endpoint_address}

    ECS cluster:       ${aws_ecs_cluster.main.name}
    Backend service:   ${aws_ecs_service.backend.name} (${var.backend_desired_count} tasks)
    Frontend service:  ${aws_ecs_service.frontend.name} (${var.frontend_desired_count} tasks)
    Worker service:    ${aws_ecs_service.worker.name} (${var.worker_desired_count} tasks)
    Keycloak service:  ${aws_ecs_service.keycloak.name} (${var.keycloak_desired_count} tasks)

    ECR backend:       ${aws_ecr_repository.backend.repository_url}
    ECR frontend:      ${aws_ecr_repository.frontend.repository_url}

    Blue/Green weight: new=${var.blue_green_weight_new}% old=${var.blue_green_weight_old}%

    Next steps:
      1. Confirm SNS email subscription (check ${var.alert_email}).
      2. Provision Keycloak DB role manually (see ecs_keycloak.tf comment).
      3. Set Route 53 name servers at the registrar: ${join(", ", aws_route53_zone.main[0].name_servers)}
      4. Push backend image: docker push ${aws_ecr_repository.backend.repository_url}:${var.backend_ecr_tag}
      5. Push frontend image: docker push ${aws_ecr_repository.frontend.repository_url}:${var.frontend_ecr_tag}
  EOT
}
