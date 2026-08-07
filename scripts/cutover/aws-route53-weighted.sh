#!/usr/bin/env bash
#
# aws-route53-weighted.sh — Shift Route 53 weighted records for OUTRENA blue/green cutover.
#
# Purpose:
#   UPSERT two weighted A-records (alias to ALB) under the OUTRENA hosted zone:
#     - set_identifier "new-fastapi"  weight=$NEW  -> new FastAPI stack ALB
#     - set_identifier "old-nextjs"   weight=$OLD  -> legacy Next.js stack ALB
#   Then wait for INSYNC. TTL=60s; propagation typically <5min (per §14 Risk #18).
#
# Usage:
#   aws-route53-weighted.sh <environment> <new_weight> [old_weight]
#     environment : dev | staging | production
#     new_weight  : 0-100  (traffic % to new FastAPI stack)
#     old_weight  : 0-100  (traffic % to legacy Next.js stack). Default = 100 - new_weight.
#
# Exit codes:
#   0  success — weights shifted, change INSYNC
#   1  usage / argument validation error
#   2  AWS CLI error (list-hosted-zones, change-resource-record-sets, wait)
#
# Depends on:
#   - aws CLI v2 (configured credentials, region from env/terraform)
#   - Environment variables (optional overrides):
#       OUTRENA_HOSTED_DOMAIN  default outrena.com
#       OUTRENA_NEW_ALB_DNS    default outrena-${env}-alb.elb.amazonaws.com
#       OUTRENA_OLD_ALB_DNS    default outrena-${env}-legacy-alb.elb.amazonaws.com
#       OUTRENA_ROUTE53_TTL    default 60
#   - Bash 4+, coreutils (jq, awk)
#
# Notes:
#   - Risk #18 mitigation: TTL=60s, INSYNC wait, total cutover+rollback <5min.
#   - Weights must sum to 100 (validated). If only new_weight provided, old_weight defaults.
#   - Both records must already exist or be UPSERT-able; Route 53 weighted set_identifier names
#     must match the existing records (created by terraform aws_route53_record weighted_*).
# ----------------------------------------------------------------------------

set -euo pipefail

# ---------- color helpers ----------
if [[ -t 1 ]]; then
  GREEN=$(tput setaf 2); RED=$(tput setaf 1); YELLOW=$(tput setaf 3); RESET=$(tput sgr0)
else
  GREEN=""; RED=""; YELLOW=""; RESET=""
fi
log()  { printf '%s[%s]%s %s\n' "$GREEN"  "$(date -u +%FT%TZ)" "$RESET" "$*"; }
warn() { printf '%s[%s WARN]%s %s\n' "$YELLOW" "$(date -u +%FT%TZ)" "$RESET" "$*" >&2; }
err()  { printf '%s[%s ERROR]%s %s\n' "$RED" "$(date -u +%FT%TZ)" "$RESET" "$*" >&2; }

# ---------- usage ----------
usage() {
  cat <<EOF
Usage: $0 <environment> <new_weight> [old_weight]

  environment : dev | staging | production
  new_weight  : 0-100 (integer) — % traffic to new FastAPI stack
  old_weight  : 0-100 (integer) — % traffic to legacy Next.js stack
                (default: 100 - new_weight)

Examples:
  $0 production 5          # 5% new, 95% old
  $0 production 100 0      # full cutover to new stack
  $0 staging 50 50         # 50/50 canary
EOF
}

# ---------- cleanup trap ----------
TMP_BATCH=$(mktemp)
cleanup() {
  [[ -f "$TMP_BATCH" ]] && rm -f "$TMP_BATCH"
}
trap cleanup EXIT INT TERM

# ---------- arg parsing ----------
if [[ $# -lt 2 || $# -gt 3 ]]; then
  err "wrong number of arguments (got $#, expected 2 or 3)"
  usage >&2
  exit 1
fi

ENVIRONMENT="$1"
NEW_WEIGHT="$2"
OLD_WEIGHT="${3:-}"

case "$ENVIRONMENT" in
  dev|staging|production) : ;;
  *) err "environment must be dev|staging|production (got '$ENVIRONMENT')"; usage >&2; exit 1 ;;
esac

if ! [[ "$NEW_WEIGHT" =~ ^[0-9]+$ ]] || (( NEW_WEIGHT < 0 || NEW_WEIGHT > 100 )); then
  err "new_weight must be integer 0-100 (got '$NEW_WEIGHT')"
  exit 1
fi

if [[ -z "$OLD_WEIGHT" ]]; then
  OLD_WEIGHT=$(( 100 - NEW_WEIGHT ))
else
  if ! [[ "$OLD_WEIGHT" =~ ^[0-9]+$ ]] || (( OLD_WEIGHT < 0 || OLD_WEIGHT > 100 )); then
    err "old_weight must be integer 0-100 (got '$OLD_WEIGHT')"
    exit 1
  fi
fi

if (( NEW_WEIGHT + OLD_WEIGHT != 100 )); then
  err "new_weight ($NEW_WEIGHT) + old_weight ($OLD_WEIGHT) must sum to 100"
  exit 1
fi

# ---------- configuration ----------
HOSTED_DOMAIN="${OUTRENA_HOSTED_DOMAIN:-outrena.com}"
TTL="${OUTRENA_ROUTE53_TTL:-60}"

# DNS names of the ALBs (aliases). Override via env for prod flexibility.
# Defaults follow the terraform aws_lb naming convention: outrena-<env>[-legacy]-alb.
DEFAULT_NEW_ALB="outrena-${ENVIRONMENT}-alb.elb.amazonaws.com"
DEFAULT_OLD_ALB="outrena-${ENVIRONMENT}-legacy-alb.elb.amazonaws.com"
NEW_ALB_DNS="${OUTRENA_NEW_ALB_DNS:-$DEFAULT_NEW_ALB}"
OLD_ALB_DNS="${OUTRENA_OLD_ALB_DNS:-$DEFAULT_OLD_ALB}"

REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$REGION"

RECORD_NAME="*.${HOSTED_DOMAIN}"

# ---------- hosted zone lookup ----------
log "looking up hosted zone for ${HOSTED_DOMAIN} ..."
ZONE_ID=$(aws route53 list-hosted-zones-by-name \
            --dns-name "$HOSTED_DOMAIN" \
            --max-items 1 \
            --query 'HostedZones[0].Id' \
            --output text 2>/dev/null) || {
  err "AWS CLI failed listing hosted zones; check credentials/region"
  exit 2
}

if [[ -z "$ZONE_ID" || "$ZONE_ID" == "None" ]]; then
  err "no hosted zone found for ${HOSTED_DOMAIN}"
  exit 2
fi

# Route 53 returns the full ARN-style id: /hostedzone/ABCDEF1234567 — strip the prefix.
ZONE_ID="${ZONE_ID#/hostedzone/}"
log "found hosted zone id: ${ZONE_ID}"

# ---------- look up ALB canonical hosted zone IDs (required for alias targets) ----------
# ALB canonical hosted zones are well-known per-region but we resolve dynamically to be safe.
get_alb_hz() {
  local dns="$1" label="$2"
  local name="${dns%%.*}"   # e.g. outrena-production-alb
  local hz
  hz=$(aws elbv2 describe-load-balancers \
        --query "LoadBalancers[?DNSName=='${dns}'].CanonicalHostedZoneId" \
        --output text 2>/dev/null) || {
    err "could not describe ALB '${dns}' (${label}); is the ALB in this account/region?"
    exit 2
  }
  if [[ -z "$hz" || "$hz" == "None" ]]; then
    err "ALB '${dns}' (${label}) not found — set OUTRENA_${label}_ALB_DNS to the correct DNS"
    exit 2
  fi
  printf '%s' "$hz"
}

log "resolving canonical hosted zone for new ALB (${NEW_ALB_DNS}) ..."
NEW_ALB_HZ=$(get_alb_hz "$NEW_ALB_DNS" "NEW")
log "resolving canonical hosted zone for old ALB (${OLD_ALB_DNS}) ..."
OLD_ALB_HZ=$(get_alb_hz "$OLD_ALB_DNS" "OLD")

# ---------- build change-batch JSON ----------
cat > "$TMP_BATCH" <<EOF
{
  "Comment": "OUTRENA ${ENVIRONMENT} cutover — new=${NEW_WEIGHT} old=${OLD_WEIGHT} at $(date -u +%FT%TZ)",
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "${RECORD_NAME}",
        "Type": "A",
        "SetIdentifier": "new-fastapi",
        "Weight": ${NEW_WEIGHT},
        "TTL": ${TTL},
        "AliasTarget": {
          "HostedZoneId": "${NEW_ALB_HZ}",
          "DNSName": "dualstack.${NEW_ALB_DNS}",
          "EvaluateTargetHealth": true
        }
      }
    },
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "${RECORD_NAME}",
        "Type": "A",
        "SetIdentifier": "old-nextjs",
        "Weight": ${OLD_WEIGHT},
        "TTL": ${TTL},
        "AliasTarget": {
          "HostedZoneId": "${OLD_ALB_HZ}",
          "DNSName": "dualstack.${OLD_ALB_DNS}",
          "EvaluateTargetHealth": true
        }
      }
    }
  ]
}
EOF

log "change-batch built: new=${NEW_WEIGHT} old=${OLD_WEIGHT} TTL=${TTL}s"

# ---------- submit change ----------
log "submitting change-resource-record-sets ..."
CHANGE_ID=$(aws route53 change-resource-record-sets \
              --hosted-zone-id "$ZONE_ID" \
              --change-batch "file://${TMP_BATCH}" \
              --query 'ChangeInfo.Id' \
              --output text) || {
  err "AWS CLI failed to submit change-batch"
  exit 2
}
log "change submitted: id=${CHANGE_ID}"

# ---------- wait for INSYNC ----------
log "waiting for INSYNC (ChangeInfo.Id=${CHANGE_ID}) ..."
aws route53 wait resource-record-sets-changed --id "$CHANGE_ID" || {
  err "wait failed for change ${CHANGE_ID}"
  exit 2
}

STATUS=$(aws route53 get-change --id "$CHANGE_ID" --query 'ChangeInfo.Status' --output text)
if [[ "$STATUS" != "INSYNC" ]]; then
  err "change ${CHANGE_ID} ended in status=${STATUS} (expected INSYNC)"
  exit 2
fi

# ---------- success ----------
log "Route 53 weights shifted: new=${NEW_WEIGHT} old=${OLD_WEIGHT}. TTL ${TTL}s. Propagation ~5min."
log "  hosted zone : ${ZONE_ID}"
log "  record      : ${RECORD_NAME}"
log "  new ALB     : ${NEW_ALB_DNS} (weight ${NEW_WEIGHT})"
log "  old ALB     : ${OLD_ALB_DNS} (weight ${OLD_WEIGHT})"
log "  change id   : ${CHANGE_ID}"
log "  status      : INSYNC"
exit 0
