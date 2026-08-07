#!/usr/bin/env bash
#
# decommission-old-stack.sh — Tear down the legacy Next.js stack after 14-day observation.
#
# Purpose:
#   Per §16 Rollback Plan: the old Next.js stack is retained 14 days after the
#   100% cutover to enable emergency rollback. After 14 days of stable operation
#   on the new FastAPI stack, this script:
#     1. Prompts the operator to type "DECOMMISSION" (case-sensitive) — destructive.
#     2. Shifts weighted DNS / Traffic Manager old endpoint to weight=0 + disabled.
#     3. (Optionally, commented-out) terraform destroy the legacy stack.
#     4. Sends a notification (SNS / Azure webhook).
#     5. Appends a record to /var/log/outrena-cutover.log audit log.
#
# Usage:
#   decommission-old-stack.sh <cloud> <environment>
#     cloud       : aws | azure
#     environment : dev | staging | production
#
# Exit codes:
#   0  decommission completed (old endpoint weight=0 + notification sent)
#   1  user did not confirm DECOMMISSION (aborted)
#   2  argument / script-not-found error
#   3  weight shift failed (decommission incomplete — DO NOT destroy TF)
#   4  notification failed (non-fatal — decommission itself succeeded)
#
# Depends on:
#   - aws-route53-weighted.sh / azure-traffic-manager-weighted.sh (sibling)
#   - aws CLI / az CLI (configured)
#   - Optional: terraform (only if you uncomment the destroy block)
#   - Optional: OUTRENA_ALERTS_TOPIC_ARN (AWS) or OUTRENA_AZ_ALERT_WEBHOOK (Azure)
# ----------------------------------------------------------------------------

set -euo pipefail

# ---------- color helpers ----------
if [[ -t 1 ]]; then
  GREEN=$(tput setaf 2); RED=$(tput setaf 1); YELLOW=$(tput setaf 3); CYAN=$(tput setaf 6); RESET=$(tput sgr0)
else
  GREEN=""; RED=""; YELLOW=""; CYAN=""; RESET=""
fi
ts() { date -u +%FT%TZ; }
log()  { printf '%s[%s DECOMM]%s %s\n'  "$GREEN"  "$(ts)" "$RESET" "$*"; }
warn() { printf '%s[%s DECOMM WARN]%s %s\n'  "$YELLOW" "$(ts)" "$RESET" "$*" >&2; }
err()  { printf '%s[%s DECOMM ERROR]%s %s\n' "$RED"    "$(ts)" "$RESET" "$*" >&2; }

# ---------- audit log ----------
AUDIT_LOG="/var/log/outrena-cutover.log"
if [[ ! -w "$AUDIT_LOG" ]] && ! touch "$AUDIT_LOG" 2>/dev/null; then
  AUDIT_LOG="/tmp/outrena-cutover.log"
  warn "could not write /var/log/outrena-cutover.log — falling back to ${AUDIT_LOG}"
fi
audit() { echo "[$(ts)] $*" >> "$AUDIT_LOG"; }

# ---------- usage ----------
usage() {
  cat <<EOF
Usage: $0 <cloud> <environment>

  cloud       : aws | azure
  environment : dev | staging | production

DESTRUCTIVE — disables the legacy Next.js stack endpoint after the 14-day
observation window. Operator must type DECOMMISSION to confirm.
EOF
}

if [[ $# -ne 2 ]]; then
  err "expected exactly 2 arguments (got $#)"
  usage >&2
  exit 2
fi

CLOUD="$1"
ENVIRONMENT="$2"

case "$CLOUD" in
  aws|azure) : ;;
  *) err "cloud must be aws|azure (got '$CLOUD')"; usage >&2; exit 2 ;;
esac
case "$ENVIRONMENT" in
  dev|staging|production) : ;;
  *) err "environment must be dev|staging|production (got '$ENVIRONMENT')"; usage >&2; exit 2 ;;
esac

# ---------- locate sibling weight-shift script ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$CLOUD" in
  aws)   SHIFT_SCRIPT="${SCRIPT_DIR}/aws-route53-weighted.sh"
         ROLLBACK_FOR_NOTIFY="${SCRIPT_DIR}/aws-route53-rollback.sh" ;;
  azure) SHIFT_SCRIPT="${SCRIPT_DIR}/azure-traffic-manager-weighted.sh"
         ROLLBACK_FOR_NOTIFY="${SCRIPT_DIR}/azure-traffic-manager-rollback.sh" ;;
esac
if [[ ! -x "$SHIFT_SCRIPT" ]]; then
  err "required sibling script not found / not executable: ${SHIFT_SCRIPT}"
  exit 2
fi

# ---------- banner ----------
echo
printf '%s%s========================================================%s\n' "$RED" "" "$RESET"
printf '%s%s DESTRUCTIVE OPERATION — LEGACY STACK DECOMMISSION %s\n' "$RED" "" "$RESET"
printf '%s%s========================================================%s\n' "$RED" "" "$RESET"
echo
printf '  Cloud        : %s\n' "$CLOUD"
printf '  Environment  : %s\n' "$ENVIRONMENT"
printf '  Audit log    : %s\n' "$AUDIT_LOG"
echo
printf '%sThis will DISABLE the legacy Next.js stack endpoint. The 14-day rollback\n' "$YELLOW"
printf 'window will CLOSE. Ensure the new FastAPI stack has been stable for the\n'
printf 'full observation period before proceeding.%s\n' "$RESET"
echo

# ---------- confirmation ----------
read -r -p "$(printf '%sType DECOMMISSION to proceed:%s ' "$YELLOW" "$RESET")" CONFIRM
if [[ "$CONFIRM" != "DECOMMISSION" ]]; then
  warn "confirmation failed (got '${CONFIRM}') — aborting decommission"
  audit "decommission-abort env=${ENVIRONMENT} cloud=${CLOUD} reason=user-did-not-confirm"
  exit 1
fi
log "confirmation accepted"
audit "decommission-start env=${ENVIRONMENT} cloud=${CLOUD} user=${USER:-unknown}"

# ---------- step 1: set old endpoint weight to 0 + disabled ----------
# For AWS Route 53: new=100 old=0 (UPSERT removes traffic to legacy ALB).
# For Azure TM: azure-traffic-manager-weighted.sh disables old endpoint when weight=0.
log "step 1/3: shifting old endpoint to weight=0 + disabled"
if ! "$SHIFT_SCRIPT" "$ENVIRONMENT" 100 0; then
  err "WEIGHT SHIFT FAILED — legacy stack may still be receiving traffic. DO NOT run terraform destroy."
  audit "decommission-fail env=${ENVIRONMENT} cloud=${CLOUD} stage=weight-shift"
  exit 3
fi
log "old endpoint disabled"
audit "decommission-weight-shift-ok env=${ENVIRONMENT} cloud=${CLOUD} new=100 old=0"

# ---------- step 2: terraform destroy (COMMENTED OUT — destructive) ----------
# DANGER: uncommenting the block below will DELETE the legacy stack's
# infrastructure (ALB, ECS service, RDS read replica if any, S3 buckets for
# Next.js assets). Only run this after:
#   - 14-day observation window passed with no rollback events
#   - All legacy logs / metrics have been archived
#   - Backup of legacy DB snapshots verified (if applicable)
#   - The product team has signed off in writing
#
# log "step 2/3: terraform destroy legacy stack"
# TF_DIR="${SCRIPT_DIR}/../../terraform/${CLOUD}/legacy"
# if [[ -d "$TF_DIR" ]]; then
#   (cd "$TF_DIR" && terraform init -reconfigure && \
#    terraform destroy -auto-approve \
#      -var="environment=${ENVIRONMENT}" \
#      -var="decommission=true") || {
#     err "terraform destroy failed — legacy resources may be in partial state"
#     audit "decommission-tf-destroy-fail env=${ENVIRONMENT} cloud=${CLOUD}"
#     exit 3
#   }
#   audit "decommission-tf-destroy-ok env=${ENVIRONMENT} cloud=${CLOUD}"
# else
#   warn "terraform dir not found: ${TF_DIR} — skipping terraform destroy (manual cleanup required)"
# fi

log "step 2/3: terraform destroy SKIPPED (commented out — destructive, requires manual uncomment)"
warn "legacy stack resources remain provisioned — manually run 'terraform destroy' in terraform/${CLOUD}/legacy/"
audit "decommission-tf-destroy-skipped env=${ENVIRONMENT} cloud=${CLOUD} reason=commented-out-by-default"

# ---------- step 3: notification ----------
log "step 3/3: sending decommission notification"
NOTIFY_SENT=0
case "$CLOUD" in
  aws)
    REGION="${AWS_REGION:-us-east-1}"; export AWS_DEFAULT_REGION="$REGION"
    TOPIC_ARN="${OUTRENA_ALERTS_TOPIC_ARN:-}"
    if [[ -z "$TOPIC_ARN" ]]; then
      # Reuse the same lookup logic as aws-route53-rollback.sh
      while IFS= read -r arn; do
        name_tag=$(aws sns list-tags-for-resource --resource-arn "$arn" \
                    --query "Tags[?Key=='Name'].Value" --output text 2>/dev/null || true)
        if [[ "$name_tag" == "outrena-${ENVIRONMENT}-alerts" ]]; then
          TOPIC_ARN="$arn"; break
        fi
      done < <(aws sns list-topics --query 'Topics[].TopicArn' --output text 2>/dev/null || true)
    fi
    if [[ -z "$TOPIC_ARN" ]]; then
      warn "SNS alerts topic not found — skipping notification"
    else
      SUBJECT="[OUTRENA] DECOMMISSION — ${ENVIRONMENT} legacy stack disabled"
      MESSAGE=$(cat <<EOF
OUTRENA Phase 6 legacy stack decommission executed.

Environment : ${ENVIRONMENT}
Cloud       : aws
Timestamp   : $(ts)
Operator    : ${USER:-unknown}

Actions taken:
  - Route 53 weight shifted to new=100 old=0 (legacy endpoint weight=0)
  - Terraform destroy: SKIPPED (commented out by default — manual run required)

Audit log: ${AUDIT_LOG}

Follow-up:
  1. Run terraform destroy in terraform/aws/legacy/ (manual — destructive)
  2. Archive legacy CloudWatch log groups (retention policy may already handle this)
  3. Update the OUTRENA architecture diagram to remove the legacy stack
  4. Close the Phase 6 cutover ticket
EOF
)
      if aws sns publish --topic-arn "$TOPIC_ARN" --subject "$SUBJECT" \
            --message "$MESSAGE" --output text >/dev/null; then
        log "SNS notification sent"; NOTIFY_SENT=1
      else
        warn "SNS publish failed (non-fatal — decommission itself succeeded)"
      fi
    fi
    ;;
  azure)
    ALERT_WEBHOOK="${OUTRENA_AZ_ALERT_WEBHOOK:-}"
    if [[ -z "$ALERT_WEBHOOK" ]]; then
      warn "OUTRENA_AZ_ALERT_WEBHOOK not set — skipping notification"
    else
      MESSAGE=$(cat <<EOF
{
  "title": "[OUTRENA] DECOMMISSION — ${ENVIRONMENT} legacy stack disabled",
  "text": "OUTRENA Phase 6 legacy stack decommission executed.\nEnv: ${ENVIRONMENT}\nCloud: azure\nTimestamp: $(ts)\nOperator: ${USER:-unknown}\n\nActions: TM endpoint old disabled (weight=0). Terraform destroy: SKIPPED (manual).\nAudit log: ${AUDIT_LOG}"
}
EOF
)
      if curl -fsS -X POST -H 'Content-Type: application/json' -d "$MESSAGE" \
            "$ALERT_WEBHOOK" >/dev/null 2>&1; then
        log "webhook notification sent"; NOTIFY_SENT=1
      else
        warn "webhook POST failed (non-fatal — decommission itself succeeded)"
      fi
    fi
    ;;
esac
audit "decommission-notify env=${ENVIRONMENT} cloud=${CLOUD} sent=${NOTIFY_SENT}"

# ---------- final summary ----------
log "DECOMMISSION COMPLETE (weight-shift) — ${ENVIRONMENT}/${CLOUD}"
log "  old endpoint : weight=0, disabled"
log "  tf destroy   : SKIPPED — see commented block in script"
log "  audit log    : ${AUDIT_LOG}"
if (( NOTIFY_SENT == 0 )); then
  warn "notification was NOT sent — see warnings above"
  exit 4
fi
exit 0
