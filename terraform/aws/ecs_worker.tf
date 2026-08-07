# ecs_worker.tf — Celery worker Fargate task + service.
#
# Same image as the backend (shares the app codebase) but with a different
# command: `celery -A app.worker.celery_app worker --loglevel=info`.
# No ALB (worker is headless — no inbound HTTP). No port mappings.
#
# Concurrency: 4 worker processes per task (configurable via env in the
# Dockerfile). For higher throughput, scale `var.worker_desired_count`
# horizontally rather than bumping per-task concurrency (avoids memory
# pressure on a single Fargate task).

# ── Worker task definition ────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = var.worker_task_cpu
  memory = var.worker_task_memory

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.worker_task.arn

  # ECS Exec enabled at the SERVICE level (aws_ecs_service.worker.enable_execute_command = true).

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_ecr_tag}"
      essential = true

      # Override the backend's uvicorn CMD with the Celery worker command.
      # --concurrency=4: 4 worker processes per Fargate task (good for
      # 1 vCPU / 2GB — Celery docs recommend 2-4 per core).
      # --max-tasks-per-child=100: recycle workers to leak memory from
      # long-running tasks (CSV import, autopilot pipeline).
      # -Q:celery,scheduler,mailbridge — subscribe to all queues.
      entryPoint = ["python", "-m"]
      command = [
        "celery", "-A", "app.worker.celery_app", "worker",
        "--loglevel=info",
        "--concurrency=4",
        "--max-tasks-per-child=100",
        "-Q:celery,celery",
        "-Q:scheduler,scheduler",
        "-Q:mailbridge,mailbridge",
      ]

      # No port mappings — worker doesn't accept inbound traffic.
      portMappings = []

      # ── Environment vars — same as backend (shared image, shared config) ──
      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "BASE_DOMAIN", value = var.base_domain },
        { name = "KEYCLOAK_BASE_URL", value = "https://auth.${var.base_domain}" },
        { name = "KEYCLOAK_REALM", value = "outrena" },
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
        { name = "REDIS_HOST", value = aws_elasticache_replication_group.main.configuration_endpoint_address != null ? aws_elasticache_replication_group.main.configuration_endpoint_address : aws_elasticache_replication_group.main.primary_endpoint_address },
        { name = "REDIS_PORT", value = "6379" },
        { name = "REDIS_DB", value = "0" },
        { name = "CELERY_BROKER_DB", value = "1" },
        # Flag for the app to know it's running as the worker (skips
        # lifespan startup that would otherwise start the APScheduler in
        # this process — scheduler should only run in the backend task).
        { name = "CELERY_WORKER_MODE", value = "true" },
        { name = "SCHEDULER_ENABLED", value = "false" },
      ]

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
        var.mailbridge_url == "" ? [] : [
          {
            name      = "MAILBRIDGE_DEFAULT_URL"
            valueFrom = "${aws_secretsmanager_secret.mailbridge_url[0].arn}:MAILBRIDGE_DEFAULT_URL::"
          }
        ]
      )

      # No HTTP health check — Celery workers don't expose a port. ECS
      # relies on the container process staying alive (PID 1) as the
      # liveness signal. If `celery worker` exits, ECS restarts the task.
      # For deeper health, add a Celery `celery inspect ping` sidecar (future).

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

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
    Name = "${local.name_prefix}-worker-task-def"
  }
}

# ── Worker ECS service (no ALB) ───────────────────────────────────────────────
resource "aws_ecs_service" "worker" {
  name                   = "${local.name_prefix}-worker"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = "${aws_ecs_task_definition.worker.family}:${aws_ecs_task_definition.worker.revision}"
  desired_count          = var.worker_desired_count
  launch_type            = "FARGATE"
  platform_version       = "LATEST"
  scheduling_strategy    = "REPLICA"
  enable_execute_command = true

  deployment_maximum_percent         = var.ecs_deployment_maximum_percent
  deployment_minimum_healthy_percent = var.ecs_deployment_minimum_healthy_percent

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.sg_worker.id]
    assign_public_ip = var.assign_public_ip_to_fargate
  }

  # No load_balancer block — headless service.

  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = {
    Name = "${local.name_prefix}-worker-service"
  }
}
