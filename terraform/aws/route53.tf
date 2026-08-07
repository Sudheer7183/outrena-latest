# route53.tf — Hosted zone + weighted blue/green cutover records.
#
# Migration doc §10 Phase 6 exit criteria: weighted DNS cutover over 7 days
# (Day 1: 5% new / 95% old → Day 7: 100% new / 0% old). TTL=60s for fast
# rollback (§16.3: propagation < 5 min).
#
# Weighted policy:
#   wildcard_new → aws_lb.main.dns_name                weight = var.blue_green_weight_new
#   wildcard_old → legacy Next.js ALB                  weight = var.blue_green_weight_old
#
# The legacy Next.js ALB is NOT managed by this Terraform stack (it lives in
# the existing AWS account that the migration is decommissioning). To avoid
# adding a new variable to variables.tf, we use a `locals` placeholder: the
# old record is only created when var.blue_green_weight_old > 0, and points
# to a CNAME that the operator MUST override with the real legacy ALB DNS
# (e.g. via `terraform import` of the existing weighted record, or by
# editing the value below before applying).
#
# IN REAL DEPLOYMENT: replace `legacy_record_target` with the actual legacy
# ALB DNS, OR import the existing Route 53 weighted record into this state.

locals {
  # CNAME target for the legacy (old Next.js stack) record. Real deployments
  # MUST override this — see comment above. Default is a deliberately
  # invalid placeholder that will fail Route 53 resolution if accidentally
  # applied as-is.
  legacy_record_target = var.blue_green_weight_old == 0 ? [] : ["legacy-placeholder.${var.base_domain}"]

  # Whether to emit the legacy weighted record at all (skip when 0% old —
  # zero-weight records still resolve to the new stack, but creating one
  # with a placeholder CNAME would be misleading in the AWS console).
  create_legacy_record = var.blue_green_weight_old > 0 ? 1 : 0
}

# ── Hosted zone ───────────────────────────────────────────────────────────────
# `count` allows the zone to be imported if it already exists (e.g. created
# by the legacy Next.js stack). To import: `terraform import aws_route53_zone.main[0] Z123ABC`.
# Otherwise Terraform creates a new public hosted zone for var.base_domain.
resource "aws_route53_zone" "main" {
  count = 1

  name = var.base_domain

  comment = "OUTRENA ${var.environment} — managed by Terraform (Phase 6)"

  lifecycle {
    # Prevent accidental zone deletion — losing the zone takes the whole
    # stack offline and can't be undone (delegation records take 24-48h to
    # propagate from the parent registrar).
    prevent_destroy = true
  }

  tags = {
    Name = "${local.name_prefix}-r53-zone"
  }
}

# ── Apex + www → ALB (alias records, free) ────────────────────────────────────
resource "aws_route53_record" "frontend_apex" {
  zone_id = aws_route53_zone.main[0].zone_id
  name    = var.base_domain
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "frontend_www" {
  zone_id = aws_route53_zone.main[0].zone_id
  name    = "www.${var.base_domain}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# ── api.<base_domain> → ALB (backend TG via host-header rule) ─────────────────
resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.main[0].zone_id
  name    = "api.${var.base_domain}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# ── auth.<base_domain> → ALB (keycloak TG via path-pattern /auth/*) ───────────
resource "aws_route53_record" "auth" {
  zone_id = aws_route53_zone.main[0].zone_id
  name    = "auth.${var.base_domain}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# ── NEW stack: weighted wildcard → ALB ────────────────────────────────────────
# Per migration doc §16.3: weight ramps 5 → 25 → 50 → 100 over 7 days.
# Use `set_identifier` so weighted policy records can coexist in the zone.
resource "aws_route53_record" "wildcard_new" {
  zone_id = aws_route53_zone.main[0].zone_id
  name    = "*.${var.base_domain}"
  type    = "A"

  set_identifier = "new-fastapi"
  weighted_routing_policy {
    weight = var.blue_green_weight_new
  }

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# ── OLD stack: weighted wildcard → legacy Next.js ALB ─────────────────────────
# Created only when var.blue_green_weight_old > 0. The `records` list is the
# CNAME target — operators MUST replace `legacy_record_target` above with
# the real legacy ALB DNS before applying in a real environment.
#
# Using CNAME (not alias) because the legacy ALB is in a different AWS
# account / state and we don't have its zone_id here. CNAME works on
# any DNS target.
#
# NOTE: weighted CNAME records ARE supported by Route 53.
resource "aws_route53_record" "wildcard_old" {
  count = local.create_legacy_record

  zone_id = aws_route53_zone.main[0].zone_id
  name    = "*.${var.base_domain}"
  type    = "CNAME"

  set_identifier = "old-nextjs"
  weighted_routing_policy {
    weight = var.blue_green_weight_old
  }

  ttl     = 60
  records = local.legacy_record_target
}
