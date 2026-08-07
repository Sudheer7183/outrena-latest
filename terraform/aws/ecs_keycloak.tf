# ecs_keycloak.tf — Keycloak 24 Fargate task + service.
#
# Container: quay.io/keycloak/keycloak:24.0 (var.keycloak_image)
#   - Port 8080
#   - KC_PROXY=edge (TLS terminated at ALB, Keycloak speaks plain HTTP)
#   - KC_HTTP_ENABLED=true (allow HTTP behind ALB)
#   - KC_HOSTNAME=auth.${var.base_domain}
#   - KC_DB=postgres (uses its OWN database `keycloak` inside the RDS instance)
#   - command: ["start", "--optimized"] (skip the build step — image already
#     has the optimized Keycloak distribution baked in)
#
# ── Keycloak DB provisioning (MANUAL STEP) ───────────────────────────────────
# Keycloak requires its own logical database + role inside the RDS instance.
# This Terraform does NOT provision them automatically because RDS doesn't
# expose a `CREATE DATABASE` resource. Two options:
#
#   Option A (recommended): null_resource psql script
#     Provision the DB + role via a `null_resource` with a local-exec that
#     runs `psql` against the RDS endpoint using the master password from
#     Secrets Manager. Sample (NOT enabled in v1 — uncomment to use):
#
#       resource "null_resource" "keycloak_db" {
#         triggers = { rds_id = aws_db_instance.main.id }
#         provisioner "local-exec" {
#           command = <<-EOT
#             PGPASSWORD='${local.rds_master_password}' psql \
#               -h ${aws_db_instance.main.address} -U ${var.database_username} \
#               -d postgres -c "CREATE DATABASE ${var.keycloak_db_name};"
#             PGPASSWORD='${local.rds_master_password}' psql \
#               -h ${aws_db_instance.main.address} -U ${var.database_username} \
#               -d postgres -c "CREATE USER ${var.keycloak_db_username} WITH PASSWORD '${random_password.keycloak_db.result}';"
#             PGPASSWORD='${local.rds_master_password}' psql \
#               -h ${aws_db_instance.main.address} -U ${var.database_username} \
#               -d ${var.keycloak_db_name} -c "GRANT ALL ON DATABASE ${var.keycloak_db_name} TO ${var.keycloak_db_username};"
#           EOT
#         }
#       }
#
#   Option B (simpler): document + run manually
#     After `terraform apply`, run the SQL above against the RDS instance
#     using `psql` from a bastion or CloudShell. Then deploy Keycloak.
#
# This file uses Option B (document only). Operators must run the SQL before
# the Keycloak ECS service will pass its health check (Keycloak fails to
# connect to its DB and exits with non-zero).

# ── Keycloak task definition ──────────────────────────────────────────────────
resource "aws_ecs_task_definition" "keycloak" {
  family                   = "${local.name_prefix}-keycloak"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = var.keycloak_task_cpu
  memory = var.keycloak_task_memory

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.keycloak_task.arn

  # ECS Exec enabled at the SERVICE level (aws_ecs_service.keycloak.enable_execute_command = true).

  container_definitions = jsonencode([
    {
      name      = "keycloak"
      image     = var.keycloak_image
      essential = true

      # Keycloak 24 uses `kc.sh start --optimized` for production. The
      # `--optimized` flag skips the build step (image already has it).
      entryPoint = ["/opt/keycloak/bin/kc.sh"]
      command    = ["start", "--optimized"]

      portMappings = [
        {
          name          = "keycloak-http"
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
          appProtocol   = "http"
        }
      ]

      # ── Environment vars ──
      # KC_PROXY=edge: TLS terminated at ALB; Keycloak trusts X-Forwarded-* headers.
      # KC_HTTP_ENABLED=true: allow plain HTTP (only safe behind TLS-terminating ALB).
      # KC_HOSTNAME: the public-facing hostname Keycloak puts in tokens + cookies.
      #   IMPORTANT: must match what the browser sees (auth.${base_domain}) —
      #   otherwise `iss` mismatch breaks JWT validation (migration doc
      #   pitfall #2).
      environment = [
        { name = "KC_PROXY", value = "edge" },
        { name = "KC_HTTP_ENABLED", value = "true" },
        { name = "KC_HOSTNAME", value = "auth.${var.base_domain}" },
        { name = "KC_HOSTNAME_STRICT", value = "false" },       # allow non-auth hostnames in dev
        { name = "KC_HOSTNAME_STRICT_HTTPS", value = "false" }, # ALB handles TLS
        { name = "KC_DB", value = "postgres" },
        # KC_DB_URL points at the dedicated keycloak database inside the RDS
        # instance. The role + DB are provisioned manually (see comment above).
        { name = "KC_DB_URL", value = "jdbc:postgresql://${aws_db_instance.main.address}:5432/${var.keycloak_db_name}" },
        { name = "KEYCLOAK_ADMIN", value = var.keycloak_admin_username },
        { name = "KC_LOG_LEVEL", value = var.log_level == "DEBUG" ? "DEBUG" : "INFO" },
        # Realm — Keycloak auto-creates the `outrena` realm on first boot
        # if KC_IMPORT is set. For v1 we configure the realm via the Admin
        # API script `scripts/apply_realm_config.py` (migration doc §9.2).
        # Per-tenant client redirect URIs are added by the provisioning
        # service (pitfall #1 mitigation).
      ]

      # ── Secrets ──
      secrets = [
        { name = "KEYCLOAK_ADMIN_PASSWORD", valueFrom = "${aws_secretsmanager_secret.keycloak_admin.arn}:KEYCLOAK_ADMIN_PASSWORD::" },
        { name = "KC_DB_USERNAME", valueFrom = "${aws_secretsmanager_secret.keycloak_db.arn}:KC_DB_USERNAME::" },
        { name = "KC_DB_PASSWORD", valueFrom = "${aws_secretsmanager_secret.keycloak_db.arn}:KC_DB_PASSWORD::" },
      ]

      # No container-level health check — the ALB TG's /auth/realms/outrena
      # probe is sufficient and avoids double-checking. Keycloak takes
      # 30-60s to boot (DB schema init), so the ALB unhealthy_threshold of 3
      # × 30s = 90s gives it enough runway.

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.keycloak.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      # Keycloak benefits from a higher nofile ulimit (JDBC pool + HTTP).
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
    Name = "${local.name_prefix}-keycloak-task-def"
  }
}

# ── Keycloak ECS service ──────────────────────────────────────────────────────
resource "aws_ecs_service" "keycloak" {
  name                   = "${local.name_prefix}-keycloak"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = "${aws_ecs_task_definition.keycloak.family}:${aws_ecs_task_definition.keycloak.revision}"
  desired_count          = var.keycloak_desired_count
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

  depends_on = [
    aws_lb_listener.https,
    aws_lb_listener_rule.auth,
  ]

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.sg_keycloak.id]
    assign_public_ip = var.assign_public_ip_to_fargate
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.keycloak.arn
    container_name   = "keycloak"
    container_port   = 8080
  }

  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = {
    Name = "${local.name_prefix}-keycloak-service"
  }
}
