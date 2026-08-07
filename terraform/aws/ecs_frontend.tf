# ecs_frontend.tf — Frontend (nginx serving Vite build) Fargate task + service.
#
# Container: outrena/<env>/frontend:<tag>
#   - Port 80 (nginx)
#   - Environment vars: VITE_API_BASE_URL, VITE_KEYCLOAK_URL, VITE_KEYCLOAK_REALM
#   - No health check beyond ALB's / probe (nginx serves index.html)

# ── Frontend task definition ──────────────────────────────────────────────────
resource "aws_ecs_task_definition" "frontend" {
  family                   = "${local.name_prefix}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = var.frontend_task_cpu
  memory = var.frontend_task_memory

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.frontend_task.arn

  # ECS Exec disabled for frontend — nginx has no shell + no debugging value.

  container_definitions = jsonencode([
    {
      name      = "frontend"
      image     = "${aws_ecr_repository.frontend.repository_url}:${var.frontend_ecr_tag}"
      essential = true

      # nginx -g 'daemon off;' is already the container's CMD; no override
      # needed unless we want a custom nginx.conf via S3 (future work).

      portMappings = [
        {
          name          = "frontend-http"
          containerPort = 80
          hostPort      = 80
          protocol      = "tcp"
          appProtocol   = "http"
        }
      ]

      # ── Build-time Vite env vars (baked into the image at build time, but
      # also passed at runtime for nginx to inject as window.__ENV__ if we
      # use the runtime-config.js pattern). Per migration doc §13.1 the
      # backend URL is /api/v1/* (same-origin via ALB path rule).
      environment = [
        { name = "VITE_API_BASE_URL", value = "/api/v1" },
        { name = "VITE_KEYCLOAK_URL", value = "https://auth.${var.base_domain}" },
        { name = "VITE_KEYCLOAK_REALM", value = "outrena" },
        { name = "VITE_KEYCLOAK_CLIENT_ID", value = "outrena-frontend" },
        { name = "VITE_DEV_BYPASS_AUTH", value = tostring(var.environment == "development") },
        { name = "BASE_DOMAIN", value = var.base_domain },
        { name = "ENVIRONMENT", value = var.environment },
        # nginx config knobs
        { name = "NGINX_WORKER_PROCESSES", value = "auto" },
        { name = "NGINX_CLIENT_MAX_BODY_SIZE", value = "50m" }, # CSV uploads
      ]

      # No secrets for the frontend — it talks to the backend over same-origin.
      secrets = []

      # No app-level health check — ALB's / probe is sufficient. nginx
      # responds 200 to / within milliseconds of container start.
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.frontend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = {
    Name = "${local.name_prefix}-frontend-task-def"
  }
}

# ── Frontend ECS service ──────────────────────────────────────────────────────
resource "aws_ecs_service" "frontend" {
  name                   = "${local.name_prefix}-frontend"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = "${aws_ecs_task_definition.frontend.family}:${aws_ecs_task_definition.frontend.revision}"
  desired_count          = var.frontend_desired_count
  launch_type            = "FARGATE"
  platform_version       = "LATEST"
  scheduling_strategy    = "REPLICA"
  enable_execute_command = false

  deployment_maximum_percent         = var.ecs_deployment_maximum_percent
  deployment_minimum_healthy_percent = var.ecs_deployment_minimum_healthy_percent

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [
    aws_lb_listener.https,
    aws_lb_target_group.frontend,
  ]

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.sg_frontend.id]
    assign_public_ip = var.assign_public_ip_to_fargate
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 80
  }

  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = {
    Name = "${local.name_prefix}-frontend-service"
  }
}
