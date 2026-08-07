# alb.tf — Application Load Balancer + target groups + listeners + WAFv2.
#
# Listener routing (migration doc §11.1):
#   :443 (HTTPS) → default_action: forward to frontend TG
#                  rule priority 100 (host `api.*` OR path /api/* /platform/* /health): backend TG
#                  rule priority 200 (path /auth/*): keycloak TG
#   :80  (HTTP)  → redirect to https :443 (preserves path + query)
#
# WAFv2 ACL:
#   - AWS managed common rule set (SQLi, XSS, LFI, RFI)
#   - Rate-based rule (var.waf_rate_limit req/5min per IP)
#   - Attached to the ALB via aws_wafv2_web_acl_association

# ── ALB ───────────────────────────────────────────────────────────────────────
resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"

  subnets = local.public_subnet_ids

  security_groups = [aws_security_group.sg_alb.id]

  # Access logs to a dedicated S3 bucket (s3.tf creates the bucket + the
  # AWS ELB account write prefix). 5-min intervals, retained per bucket
  # lifecycle (defaults to 90d then GLACIER).
  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    prefix  = "${var.environment_short}/alb"
    enabled = true
  }

  # Drop invalid HTTP headers (defense in depth alongside WAF).
  drop_invalid_header_fields = true

  # Deletion protection on in prod — operators must explicitly disable via
  # `terraform apply -var environment=production` (no — that's a destructive
  # override). Instead use the ALB's native deletion_protection flag, gated
  # on the environment variable.
  enable_deletion_protection = var.environment == "production"

  tags = {
    Name = "${local.name_prefix}-alb"
  }
}

# ── Target groups ─────────────────────────────────────────────────────────────
# Deregistration delay 60s matches the blue/green cutover rollback window —
# in-flight requests get 60s to drain before the old task is killed.

resource "aws_lb_target_group" "backend" {
  name        = "${local.name_prefix}-tg-backend"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip" # Fargate requires `ip` (not `instance`)

  health_check {
    enabled             = true
    interval            = 30
    path                = var.backend_health_check_path
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = false # stateless API — no stickiness needed
  }

  deregistration_delay = 60

  # Fast rollback during blue/green: don't trigger ALB to wait for old
  # connection drain before registering new tasks.
  slow_start = 0

  tags = {
    Name = "${local.name_prefix}-tg-backend"
  }
}

resource "aws_lb_target_group" "frontend" {
  name        = "${local.name_prefix}-tg-frontend"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    interval            = 30
    path                = "/"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200-399" # SPA root may 200 OR 304 (cache hit)
  }

  deregistration_delay = 60

  tags = {
    Name = "${local.name_prefix}-tg-frontend"
  }
}

resource "aws_lb_target_group" "keycloak" {
  name        = "${local.name_prefix}-tg-keycloak"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled  = true
    interval = 30
    # Keycloak 24 exposes realm status at /auth/realms/<realm>. A 200 means
    # the realm is loaded and Keycloak is ready to serve login flows.
    path                = "/auth/realms/outrena"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  deregistration_delay = 60

  tags = {
    Name = "${local.name_prefix}-tg-keycloak"
  }
}

# ── HTTPS listener (default → frontend) ───────────────────────────────────────
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06" # TLS 1.3 + 1.2 fallback
  certificate_arn   = aws_acm_certificate_validation.main.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  # Defer creation until the cert is issued — avoids ALB listener creation
  # failing with "certificate not found".
  depends_on = [aws_acm_certificate_validation.main]

  tags = {
    Name = "${local.name_prefix}-listener-https"
  }
}

# ── HTTP listener (redirect to https) ─────────────────────────────────────────
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
      host        = "#{host}"
      path        = "/#{path}"
      query       = "#{query}"
    }
  }

  tags = {
    Name = "${local.name_prefix}-listener-http"
  }
}

# ── Listener rule: API routes → backend TG (priority 100) ─────────────────────
# Matches EITHER host-header `api.*` OR path-patterns /api/* /platform/* /health.
# Host-header alone is enough for the api.<base_domain> DNS route, but we also
# match paths so the apex (frontend) can call /api/v1/... via the same ALB.
resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    host_header {
      values = ["api.${var.base_domain}"]
    }
  }

  condition {
    path_pattern {
      values = ["/api/*", "/platform/*", "/health"]
    }
  }

  # ALB rule conditions are OR'd within a single rule only if the conditions
  # are different types. Two host_header/path_pattern blocks above are evaluated
  # as AND across condition types — so this rule fires only when BOTH
  # host=api.* AND path=/api/* (etc.) match. For OR semantics across host
  # vs path, we'd need separate rules. To keep the brief's "OR" behavior,
  # add a second rule for path-only matching on the apex.

  tags = {
    Name = "${local.name_prefix}-rule-api-host"
  }
}

# Path-only rule (matches /api/* /platform/* /health on ANY host) — covers
# the apex (frontend) calling /api/v1/* via the same ALB. Priority 99 so it
# runs before the host-header rule above (host match is more specific, but
# both forward to the same TG so order doesn't matter functionally).
resource "aws_lb_listener_rule" "api_path" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 99

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/platform/*", "/health"]
    }
  }

  tags = {
    Name = "${local.name_prefix}-rule-api-path"
  }
}

# ── Listener rule: /auth/* → keycloak TG (priority 200) ───────────────────────
resource "aws_lb_listener_rule" "auth" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.keycloak.arn
  }

  condition {
    path_pattern {
      values = ["/auth/*"]
    }
  }

  tags = {
    Name = "${local.name_prefix}-rule-auth"
  }
}

# ── WAFv2 Web ACL ─────────────────────────────────────────────────────────────
resource "aws_wafv2_web_acl" "main" {
  name        = "${local.name_prefix}-waf"
  description = "OUTRENA ${var.environment} edge WAF — managed rules + rate limit"
  scope       = "REGIONAL" # ALB uses REGIONAL (CloudFront uses CLOUDFRONT)

  default_action {
    allow {}
  }

  # AWS managed common attack rule set (SQLi, XSS, LFI, RFI, RCE).
  rule {
    name     = "aws-managed-common"
    priority = 10

    override_action {
      none {} # Use managed rule's built-in action (block).
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-waf-common"
      sampled_requests_enabled   = true
    }
  }

  # AWS managed known-bad-inputs rule set (log4j, SSRF, bad bots).
  rule {
    name     = "aws-managed-known-bad"
    priority = 20

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-waf-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  # Rate-based rule: block any IP exceeding var.waf_rate_limit over 5 min.
  rule {
    name     = "rate-limit"
    priority = 30

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-waf-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name_prefix}-waf-overall"
    sampled_requests_enabled   = true
  }

  tags = {
    Name = "${local.name_prefix}-waf"
  }
}

# ── Attach WAF to ALB ─────────────────────────────────────────────────────────
resource "aws_wafv2_web_acl_association" "main" {
  resource_arn = aws_lb.main.arn
  web_acl_arn  = aws_wafv2_web_acl.main.arn
}
