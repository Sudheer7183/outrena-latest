#!/usr/bin/env bash
#
# aws-route53-rollback.sh — Emergency rollback: flip all Route 53 traffic to the legacy stack.
#
# Purpose:
#   Per §16 Rollback Plan + §14 Risk #18 (slow weighted-DNS rollback):
#   in <5 min, shift traffic 0% new / 100% old by delegating to
#   aws-route53-weighted.sh, then fire an SNS alert to the OUTRENA alerts topic.
#   All actions logged to /var/log/outrena-cutover.log (and stderr).
#
# Usage:
#   aws-route53-rollback.sh <environment>
#     environment : dev | staging | production
#
# Exit codes:
#   0  rollback weight-shift succeeded (SNS failure does NOT fail rollback)
#   1  usage / argument error
#   2  AWS error during weight shift (rollback itself failed — page on-call immediately)
#   3  SNS notification error (non-fatal — weight shift already succeeded)
#
# Depends on:
#   - aws-route53-weighted.sh (same directory)
#   - aws CLI v2 (route53, sns)
#   - write permission to /var/log/outrena-cutover.log (falls back to /tmp)
#   - SNS topic with name tag "outrena-${env}-alerts" (created by terraform sns.tf)
# ----------------------------------------------------------------------------

set -euo pipefail

# ---------- color helpers ----------
if [[ -t 1 ]]; then
  GREEN=$(tput setaf 2); RED=$(tput setaf 1); YELLOW=$(tput setaf 3); RESET=$(tput sgr0)
else
  GREEN=""; RED=""; YELLOW=""; RESET=""
fi
ts() { date -u +%FT%TZ; }
log()  { local m; m="[$(ts) ROLLBACK] $*"; printf '%s%s%s\n' "$GREEN" "$m" "$RESET"; echo "$m" >&2; }
warn() { local m; m="[$(ts) ROLLBACK WARN] $*"; printf '%s%s%s\n' "$YELLOW" "$m" "$RESET"; echo "$m" >&2; }
err()  { local m; m="[$(ts) ROLLBACK ERROR] $*"; printf '%s%s%s\n' "$RED" "$m" "$RESET"; echo "$m" >&2; }

# ---------- audit log ----------
AUDIT_LOG="/var/log/outrena-cutover.log"
if [[ ! -w "$AUDIT_LOG" ]] && ! touch "$AUDIT_LOG" 2>/dev/null; then
  AUDIT_LOG="/tmp/outrena-cutover.log"
  warn "could not write ${AUDIT_LOG/original/}/var/log/outrena-cutover.log — falling back to ${AUDIT_LOG}"
fi
audit() { echo "[$(ts)] $*" >> "$AUDIT_LOG"; }

# ---------- usage ----------
usage() {
  cat <<EOF
Usage: $0 <environment>

  environment : dev | staging | production

Emergency rollback — flips Route 53 weighted records to 0% new / 100% old
and publishes an SNS alert. Intended to be safe to call from automated
monitors (monitor-cutover.sh) AND by humans.
EOF
}

# ---------- arg parsing ----------
if [[ $# -ne 1 ]]; then
  err "expected exactly 1 argument (got $#)"
  usage >&2
  exit 1
fi

ENVIRONMENT="$1"
case "$ENVIRONMENT" in
  dev|staging|production) : ;;
  *) err "environment must be dev|staging|production (got '$ENVIRONMENT')"; usage >&2; exit 1 ;;
esac

# ---------- locate the sibling weight-shift script ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEIGHT_SCRIPT="${SCRIPT_DIR}/aws-route53-weighted.sh"
if [[ ! -x "$WEIGHT_SCRIPT" ]]; then
  err "required sibling script not found / not executable: ${WEIGHT_SCRIPT}"
  exit 2
fi

# ---------- constants ----------
NEW_WEIGHT=0
OLD_WEIGHT=100
ROLLBACK_REASON="${OUTRENA_ROLLBACK_REASON:-manual-rollback}"

log "INITIATING ROLLBACK — reason: ${ROLLBACK_REASON}"
log "shifting Route 53 weights: new=${NEW_WEIGHT} old=${OLD_WEIGHT}"
audit "rollback-init env=${ENVIRONMENT} reason=${ROLLBACK_REASON} new=${NEW_WEIGHT} old=${OLD_WEIGHT}"

# ---------- shift weights ----------
START_TS=$(date +%s)
if ! "$WEIGHT_SCRIPT" "$ENVIRONMENT" "$NEW_WEIGHT" "$OLD_WEIGHT"; then
  err "WEIGHT SHIFT FAILED — Route 53 may be in an indeterminate state. Page on-call NOW."
  audit "rollback-fail env=${ENVIRONMENT} stage=weight-shift"
  exit 2
fi
END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))
log "weight shift complete in ${ELAPSED}s"
audit "rollback-weight-shift-ok env=${ENVIRONMENT} elapsed_s=${ELAPSED}"

# ---------- SNS alert (non-fatal) ----------
REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$REGION"

# Look up the alerts topic — filter by name tag "outrena-<env>-alerts".
# list-topics returns ARNs; for each we call list-tags-for-resource to filter.
# We do this defensively (best-effort) so a missing topic never blocks rollback.
TOPIC_ARN="${OUTRENA_ALERTS_TOPIC_ARN:-}"
if [[ -z "$TOPIC_ARN" ]]; then
  log "looking up SNS alerts topic (name tag = outrena-${ENVIRONMENT}-alerts) ..."
  while IFS= read -r arn; do
    name_tag=$(aws sns list-tags-for-resource \
                  --resource-arn "$arn" \
                  --query "Tags[?Key=='Name'].Value" \
                  --output text 2>/dev/null || true)
    if [[ "$name_tag" == "outrena-${ENVIRONMENT}-alerts" ]]; then
      TOPIC_ARN="$arn"
      break
    fi
  done < <(aws sns list-topics --query 'Topics[].TopicArn' --output text 2>/dev/null || true)
fi

if [[ -z "$TOPIC_ARN" ]]; then
  warn "SNS alerts topic not found — skipping notification. Set OUTRENA_ALERTS_TOPIC_ARN to override."
  audit "rollback-sns-skip env=${ENVIRONMENT} reason=topic-not-found"
  log "ROLLBACK COMPLETE (no SNS alert sent)"
  exit 0
fi

SUBJECT="[OUTRENA] ROLLBACK — ${ENVIRONMENT} — traffic to legacy stack"
MESSAGE=$(cat <<EOF
OUTRENA Phase 6 automated rollback triggered.

Environment : ${ENVIRONMENT}
Cloud       : aws (Route 53)
Reason      : ${ROLLBACK_REASON}
Timestamp   : $(ts)

Action taken:
  - Route 53 weighted records flipped: new=0 old=100
  - All traffic now served by legacy Next.js stack
  - Weight shift elapsed: ${ELAPSED}s

Required follow-up:
  1. Confirm legacy stack healthy (CloudWatch outrena-overview dashboard)
  2. Investigate root cause (CloudWatch Logs, see runbook §16)
  3. Do NOT re-attempt cutover until root cause resolved
  4. Update incident ticket with this rollback event

Audit log: ${AUDIT_LOG}
EOF
)

log "publishing SNS alert to ${TOPIC_ARN} ..."
if aws sns publish \
      --topic-arn "$TOPIC_ARN" \
      --subject "$SUBJECT" \
      --message "$MESSAGE" \
      --output text >/dev/null; then
  log "SNS alert published"
  audit "rollback-sns-ok env=${ENVIRONMENT} topic=${TOPIC_ARN}"
else
  warn "SNS publish failed — rollback already succeeded, but alert not sent. Investigate manually."
  audit "rollback-sns-fail env=${ENVIRONMENT} topic=${TOPIC_ARN}"
  log "ROLLBACK COMPLETE (SNS alert FAILED — see audit log)"
  exit 3
fi

log "ROLLBACK COMPLETE — new=${NEW_WEIGHT} old=${OLD_WEIGHT} — total elapsed ${ELAPSED}s"
exit 0
