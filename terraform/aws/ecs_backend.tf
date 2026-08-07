# ecs_backend.tf — Backend FastAPI Fargate task + service.
#
# Container: outrena/<env>/backend:<tag>
#   - Port 8000 (uvicorn)
#   - Environment vars from migration doc §13.1
#   - Secrets from Secrets Manager (DATABASE_URL, REDIS_AUTH_TOKEN, MailBridge URL)
#   - Health check: curl /health
#
# Service:
#   - Fargate launch type
#   - Private subnets + sg_backend
#   - assign_public_ip: true in dev (no NAT GW), false in prod (NAT GW)
#   - ALB target group: backend (port 8000)
#   - Deployment circuit breaker with rollback
#   - ECS Exec enabled for debugging

# ── Backend task definition ───────────────────────────────────────────────────
resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name_prefix}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = var.backend_task_cpu
  memory = var.backend_task_memory

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.backend_task.arn

  # EFS not needed in v1 (no persistent volumes — CSVs go to S3).
  # ECS Exec for `aws ecs execute-command` debugging is enabled at the
  # SERVICE level (aws_ecs_service.backend.enable_execute_command = true).

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_ecr_tag}"
      essential = true

      # Uvicorn: bind 0.0.0.0:8000, single worker (Fargate scales horizontally)
      # — no need for --workers N since desired_count handles concurrency.
      entryPoint = ["python", "-m"]
      command    = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

      portMappings = [
        {
          name          = "backend-http"
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
          appProtocol   = "http" # for ECS service connect / better observability
        }
      ]

      # ── Environment vars (§13.1) ──
      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "BASE_DOMAIN", value = var.base_domain },
        { name = "KEYCLOAK_BASE_URL", value = "https://auth.${var.base_domain}" },
        { name = "KEYCLOAK_REALM", value = "outrena" },
        # SKIP_JWT_VERIFICATION MUST be false in staging/prod. Validated in
        # variables.tf via `validation` block — but double-check here.
        { name = "SKIP_JWT_VERIFICATION", value = tostring(var.skip_jwt_verification) },
        { name = "VERIFY_JWT_ISSUER", value = tostring(var.verify_jwt_issuer) },
        { name = "ALLOWED_ORIGINS", value = var.allowed_origins },
        { name = "SCHEDULER_TICK_SECONDS", value = tostring(var.scheduler_tick_seconds) },
        { name = "SCHEDULER_PARTIAL_CAP", value = tostring(var.scheduler_partial_cap) },
        { name = "LLM_API_URL", value = var.llm_api_url },
        { name = "LOG_LEVEL", value = var.log_level },
        { name = "STORAGE_PROVIDER", value = "s3" },
        { name = "S3_BUCKET", value = var.csv_bucket_name },
        { name = "S3_REGION", value = var.aws_region },
        { name = "S3_PUBLIC_URL", value = "https://${var.csv_bucket_name}.s3.${var.aws_region}.amazonaws.com" },
        { name = "MAILBRIDGE_DEFAULT_URL", value = var.mailbridge_url == "" ? "" : var.mailbridge_url },
        # Redis URL is built at runtime from the secret + endpoint — see
        # secrets block below. We set the host/port here so the app can
        # construct the URL even if the auth token is empty (dev).
        { name = "REDIS_HOST", value = aws_elasticache_replication_group.main.configuration_endpoint_address != null ? aws_elasticache_replication_group.main.configuration_endpoint_address : aws_elasticache_replication_group.main.primary_endpoint_address },
        { name = "REDIS_PORT", value = "6379" },
        { name = "REDIS_DB", value = "0" },
        { name = "CELERY_BROKER_DB", value = "1" },
        # Delete routes use response_model=None (Phase 2 pitfall #6 mitigation,
        # already implemented in app code) — no env var needed.
      ]

      # ── Secrets (injected from Secrets Manager) ──
      secrets = concat(
        [
          {
            name      = "DATABASE_URL"
            valueFrom = "${aws_secretsmanager_secret.database_url.arn}:DATABASE_URL::"
          },
          {
            name      = "REDIS_AUTH_TOKEN"
            valueFrom = "${aws_secretsmanager_secret.redis_auth.arn}:REDIS_AUTH_TOKEN::"
          },
        ],
        # MailBridge URL — only injected when the secret exists (dev skips).
        var.mailbridge_url == "" ? [] : [
          {
            name      = "MAILBRIDGE_DEFAULT_URL"
            valueFrom = "${aws_secretsmanager_secret.mailbridge_url[0].arn}:MAILBRIDGE_DEFAULT_URL::"
          }
        ]
      )

      # ── Health check ──
      # /health endpoint is implemented in app.main — returns 200 OK if
      # DB + Redis + Keycloak reachable. Used by the ALB target group.
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60 # give uvicorn + DB pool time to warm up
      }

      # ── Log configuration (awslogs → CloudWatch) ──
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      # Mount /tmp for CSV processing — Fargate default is 3GB ephemeral.
      mountPoints = []
      volumesFrom = []

      # Ulimit — bump nofile for asyncpg connection pools.
      ulimits = [
        {
          name      = "nofile"
          softLimit = 65535
          hardLimit = 65535
        }
      ]
    }
  ])

  tags = {
    Name = "${local.name_prefix}-backend-task-def"
  }
}

# ── Backend ECS service ───────────────────────────────────────────────────────
resource "aws_ecs_service" "backend" {
  name                   = "${local.name_prefix}-backend"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = "${aws_ecs_task_definition.backend.family}:${aws_ecs_task_definition.backend.revision}"
  desired_count          = var.backend_desired_count
  launch_type            = "FARGATE"
  platform_version       = "LATEST" # 1.4.x — required for ECR pull via VPC endpoint
  scheduling_strategy    = "REPLICA"
  enable_execute_command = true

  # Rolling deploy: 200% max, 100% min healthy (no capacity loss).
  deployment_maximum_percent         = var.ecs_deployment_maximum_percent
  deployment_minimum_healthy_percent = var.ecs_deployment_minimum_healthy_percent

  # Circuit breaker: if new tasks fail to reach healthy in N attempts,
  # automatically roll back to the previous task def revision.
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  # Wait for the ALB + listeners to exist before attaching the service.
  # Otherwise ECS service creation can race with ALB listener rule creation.
  depends_on = [
    aws_lb_listener.https,
    aws_lb_listener_rule.api,
    aws_lb_listener_rule.api_path,
  ]

  # Network config — private subnets + sg_backend.
  # assign_public_ip: true in dev (no NAT GW, Fargate pulls ECR + reaches
  # LLM/MailBridge via the public IP). false in prod (NAT GW + VPC endpoints).
  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.sg_backend.id]
    assign_public_ip = var.assign_public_ip_to_fargate
  }

  # ALB integration — register tasks into the backend target group on port 8000.
  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  # Don't let Terraform revert desired_count when an autoscaler changes it.
  # (Autoscaling not implemented in v1 — placeholder for future HPA.)
  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = {
    Name = "${local.name_prefix}-backend-service"
  }
}
