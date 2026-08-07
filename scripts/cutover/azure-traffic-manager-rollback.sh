#!/usr/bin/env bash
#
# azure-traffic-manager-rollback.sh — Emergency rollback for Azure stack.
#
# Purpose:
#   Per §16 Rollback Plan + §14 Risk #18: in <5 min, flip Azure Traffic Manager
#   to 0% new / 100% old by delegating to azure-traffic-manager-weighted.sh,
#   then fire an alert via Azure Monitor Action Group (or fallback SNS-style email).
#   All actions logged to /var/log/outrena-cutover.log (and stderr).
#
# Usage:
#   azure-traffic-manager-rollback.sh <environment>
#     environment : dev | staging | production
#
# Exit codes:
#   0  rollback weight-shift succeeded (alert failure does NOT fail rollback)
#   1  usage / argument error
#   2  Azure error during weight shift (rollback itself failed — page on-call immediately)
#   3  alert notification error (non-fatal — weight shift already succeeded)
#
# Depends on:
#   - azure-traffic-manager-weighted.sh (same directory)
#   - az CLI (logged in)
#   - Optional: Azure Logic App webhook URL via OUTRENA_AZ_ALERT_WEBHOOK to push a Teams/Slack alert.
#               If unset, alert is logged only (no notification fired).
# ----------------------------------------------------------------------------

set -euo pipefail

# ---------- color helpers ----------
if [[ -t 1 ]]; then
  GREEN=$(tput setaf 2); RED=$(tput setaf 1); YELLOW=$(tput setaf 3); RESET=$(tput sgr0)
else
  GREEN=""; RED=""; YELLOW=""; RESET=""
fi
ts() { date -u +%FT%TZ; }
log()  { local m; m="[$(ts) AZ-ROLLBACK] $*"; printf '%s%s%s\n' "$GREEN" "$m" "$RESET"; echo "$m" >&2; }
warn() { local m; m="[$(ts) AZ-ROLLBACK WARN] $*"; printf '%s%s%s\n' "$YELLOW" "$m" "$RESET"; echo "$m" >&2; }
err()  { local m; m="[$(ts) AZ-ROLLBACK ERROR] $*"; printf '%s%s%s\n' "$RED" "$m" "$RESET"; echo "$m" >&2; }

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
Usage: $0 <environment>

  environment : dev | staging | production

Emergency Azure rollback — flips Traffic Manager weights to 0% new / 100% old
and (optionally) fires a webhook alert. Safe to call from automated monitors
AND by humans.
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

# ---------- locate sibling weight-shift script ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEIGHT_SCRIPT="${SCRIPT_DIR}/azure-traffic-manager-weighted.sh"
if [[ ! -x "$WEIGHT_SCRIPT" ]]; then
  err "required sibling script not found / not executable: ${WEIGHT_SCRIPT}"
  exit 2
fi

# ---------- constants ----------
NEW_WEIGHT=0
OLD_WEIGHT=100
ROLLBACK_REASON="${OUTRENA_ROLLBACK_REASON:-manual-rollback}"

log "INITIATING AZURE ROLLBACK — reason: ${ROLLBACK_REASON}"
log "shifting Traffic Manager weights: new=${NEW_WEIGHT} old=${OLD_WEIGHT}"
audit "az-rollback-init env=${ENVIRONMENT} reason=${ROLLBACK_REASON} new=${NEW_WEIGHT} old=${OLD_WEIGHT}"

# ---------- shift weights ----------
START_TS=$(date +%s)
if ! "$WEIGHT_SCRIPT" "$ENVIRONMENT" "$NEW_WEIGHT" "$OLD_WEIGHT"; then
  err "AZURE WEIGHT SHIFT FAILED — Traffic Manager may be in an indeterminate state. Page on-call NOW."
  audit "az-rollback-fail env=${ENVIRONMENT} stage=weight-shift"
  exit 2
fi
END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))
log "weight shift complete in ${ELAPSED}s"
audit "az-rollback-weight-shift-ok env=${ENVIRONMENT} elapsed_s=${ELAPSED}"

# ---------- alert (best-effort webhook) ----------
ALERT_WEBHOOK="${OUTRENA_AZ_ALERT_WEBHOOK:-}"
if [[ -z "$ALERT_WEBHOOK" ]]; then
  warn "OUTRENA_AZ_ALERT_WEBHOOK not set — skipping alert notification (Azure Monitor Action Group may still fire on metrics)"
  audit "az-rollback-alert-skip env=${ENVIRONMENT} reason=no-webhook"
  log "ROLLBACK COMPLETE (no webhook alert sent)"
  exit 0
fi

SUBJECT="[OUTRENA] AZURE ROLLBACK — ${ENVIRONMENT} — traffic to legacy stack"
MESSAGE=$(cat <<EOF
{
  "title": "${SUBJECT}",
  "text": "OUTRENA Phase 6 automated Azure rollback triggered.\nEnvironment: ${ENVIRONMENT}\nReason: ${ROLLBACK_REASON}\nTimestamp: $(ts)\nAction: Traffic Manager weights new=0 old=100 (legacy endpoint Enabled, new endpoint Enabled weight=0)\nElapsed: ${ELAPSED}s\nAudit log: ${AUDIT_LOG}"
}
EOF
)

log "posting alert to webhook ..."
if curl -fsS -X POST \
        -H 'Content-Type: application/json' \
        -d "$MESSAGE" \
        "$ALERT_WEBHOOK" >/dev/null 2>&1; then
  log "webhook alert posted"
  audit "az-rollback-alert-ok env=${ENVIRONMENT}"
else
  warn "webhook POST failed — rollback already succeeded, but alert not sent. Investigate manually."
  audit "az-rollback-alert-fail env=${ENVIRONMENT}"
  log "ROLLBACK COMPLETE (webhook alert FAILED — see audit log)"
  exit 3
fi

log "AZURE ROLLBACK COMPLETE — new=${NEW_WEIGHT} old=${OLD_WEIGHT} — total elapsed ${ELAPSED}s"
exit 0
