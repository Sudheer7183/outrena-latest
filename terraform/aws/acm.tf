# acm.tf — ACM wildcard TLS certificate for *.${var.base_domain}.
#
# Validation is DNS-based via Route 53 (route53.tf creates the hosted zone).
# The cert is regional (must be in the same region as the ALB for TLS term).
# ACM-managed certs renew automatically; renewal requires the validation
# CNAME to remain in place, so we don't destroy the validation record on
# re-apply.

# ── Wildcard certificate ──────────────────────────────────────────────────────
resource "aws_acm_certificate" "main" {
  domain_name       = "*.${var.base_domain}"
  validation_method = "DNS"

  # Apex also covered — wildcard covers one level, so we add the apex as a
  # SAN to support both `outrena.dev` and `*.outrena.dev`.
  subject_alternative_names = [var.base_domain]

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.name_prefix}-acm-wildcard"
  }
}

# ── Route 53 validation record ────────────────────────────────────────────────
# ACM exposes one validation option per SAN; we create a CNAME for each.
# In practice the wildcard + apex share the same `_acme-challenge` label,
# but we iterate over `domain_validation_options` for correctness.
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options :
    dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60

  zone_id = aws_route53_zone.main[0].zone_id
}

# ── Wait for issuance ─────────────────────────────────────────────────────────
# This blocks `apply` until ACM marks the cert ISSUED. The ALB listener in
# alb.tf references `aws_acm_certificate_validation.main.certificate_arn`,
# so the listener is only created once the cert is usable.
resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]

  timeouts {
    create = "10m"
  }
}
