#!/usr/bin/env bash
#
# full-cutover-sequence.sh — Gradual 5%→25%→50%→100% blue/green cutover per §16.3.
#
# Purpose:
#   Execute the full OUTRENA Phase 6 cutover sequence with human-confirmation prompts
#   between weight shifts and post-shift monitoring at each step. On any failure
#   (validation, shift, or monitor-auto-rollback), roll back to the previous step's
#   weights and exit non-zero.
#
#   Sequence (per §16.3 exit criteria):
#     step 0  validate at 0% (no shift)
#     step 1  5%   new  / 95% old   monitor 15min (default)
#     step 2  25%  new  / 75% old   monitor 30min
#     step 3  50%  new  / 50% old   monitor 60min
#     step 4  100% new  / 0%  old   monitor 60min
#     post    log decommission-due date (14 days) + print calendar reminder
#
# Usage:
#   full-cutover-sequence.sh <cloud> <environment> [options]
#
#     cloud       : aws | azure
#     environment : dev | staging | production
#
# Options:
#   --yes                       Skip human-confirmation prompts (unattended / CI mode)
#   --step1-minutes N           Override step 1 monitor duration (default 15)
#   --step2-minutes N           Override step 2 monitor duration (default 30)
#   --step3-minutes N           Override step 3 monitor duration (default 60)
#   --step4-minutes N           Override step 4 monitor duration (default 60)
#   --skip-validation           Pass-through to cutover.sh (NOT RECOMMENDED)
#   --start-step N              Begin at step N (1-4) — resume an interrupted sequence
#
# Exit codes:
#   0  full sequence completed — old stack flagged for decommission in 14 days
#   1  any step failed AND rollback to previous step succeeded (or was the first step)
#   2  argument error
#   3  a step failed AND the rollback itself failed — URGENT manual intervention
#
# Depends on:
#   - cutover.sh (sibling orchestrator)
#   - aws-route53-weighted.sh / azure-traffic-manager-weighted.sh (for rollback calls)
#   - date with -d support (GNU coreutils)
#   - Optional: `at` command for scheduling a decommission reminder
# ----------------------------------------------------------------------------

set -euo pipefail

# ---------- color helpers ----------
if [[ -t 1 ]]; then
  GREEN=$(tput setaf 2); RED=$(tput setaf 1); YELLOW=$(tput setaf 3); BLUE=$(tput setaf 4); CYAN=$(tput setaf 6); RESET=$(tput sgr0)
else
  GREEN=""; RED=""; YELLOW=""; BLUE=""; CYAN=""; RESET=""
fi
ts() { date -u +%FT%TZ; }
log()  { printf '%s[%s SEQ]%s %s\n'  "$GREEN"  "$(ts)" "$RESET" "$*"; }
step_log() { printf '%s[%s STEP %s]%s %s\n'  "$CYAN" "$(ts)" "$1" "$RESET" "$2"; }
warn() { printf '%s[%s SEQ WARN]%s %s\n'  "$YELLOW" "$(ts)" "$RESET" "$*" >&2; }
err()  { printf '%s[%s SEQ ERROR]%s %s\n' "$RED"    "$(ts)" "$RESET" "$*" >&2; }

# ---------- usage ----------
usage() {
  cat <<EOF
Usage: $0 <cloud> <environment> [options]

  cloud       : aws | azure
  environment : dev | staging | production

Options:
  --yes                  Skip human-confirmation prompts (unattended mode)
  --step1-minutes N      Step 1 (5%)  monitor minutes (default 15)
  --step2-minutes N      Step 2 (25%) monitor minutes (default 30)
  --step3-minutes N      Step 3 (50%) monitor minutes (default 60)
  --step4-minutes N      Step 4 (100%) monitor minutes (default 60)
  --skip-validation      Pass-through to cutover.sh (NOT RECOMMENDED)
  --start-step N         Begin at step N (1-4) — resume interrupted sequence

Exit codes:
  0 full sequence ok | 1 step failed + rollback ok | 2 arg error | 3 step + rollback failed
EOF
}

# ---------- parse args ----------
POSITIONAL=()
ASSUME_YES=0
STEP1_MIN=15
STEP2_MIN=30
STEP3_MIN=60
STEP4_MIN=60
SKIP_VALIDATION_FLAG=""
START_STEP=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y)            ASSUME_YES=1; shift ;;
    --step1-minutes)     STEP1_MIN="$2"; shift 2 ;;
    --step2-minutes)     STEP2_MIN="$2"; shift 2 ;;
    --step3-minutes)     STEP3_MIN="$2"; shift 2 ;;
    --step4-minutes)     STEP4_MIN="$2"; shift 2 ;;
    --skip-validation)   SKIP_VALIDATION_FLAG="--skip-validation"; shift ;;
    --start-step)
      [[ $# -ge 2 ]] || { err "--start-step requires a value"; exit 2; }
      START_STEP="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; POSITIONAL+=("$@"); break ;;
    -*) err "unknown option: $1"; usage >&2; exit 2 ;;
    *)  POSITIONAL+=("$1"); shift ;;
  esac
done

if (( ${#POSITIONAL[@]} < 2 )); then
  err "expected <cloud> <environment>"
  usage >&2
  exit 2
fi
CLOUD="${POSITIONAL[0]}"
ENVIRONMENT="${POSITIONAL[1]}"

case "$CLOUD" in
  aws|azure) : ;;
  *) err "cloud must be aws|azure (got '$CLOUD')"; exit 2 ;;
esac
case "$ENVIRONMENT" in
  dev|staging|production) : ;;
  *) err "environment must be dev|staging|production (got '$ENVIRONMENT')"; exit 2 ;;
esac
if ! [[ "$START_STEP" =~ ^[1-4]$ ]]; then
  err "--start-step must be 1..4 (got '$START_STEP')"; exit 2
fi

# ---------- locate siblings ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CUTOVER="${SCRIPT_DIR}/cutover.sh"
case "$CLOUD" in
  aws)   SHIFT_RAW="${SCRIPT_DIR}/aws-route53-weighted.sh" ;;
  azure) SHIFT_RAW="${SCRIPT_DIR}/azure-traffic-manager-weighted.sh" ;;
esac
for s in "$CUTOVER" "$SHIFT_RAW"; do
  [[ -x "$s" ]] || { err "missing sibling: $s"; exit 2; }
done

# ---------- confirm-prompt helper ----------
confirm() {
  local prompt="$1"
  if (( ASSUME_YES )); then
    log "(--yes) auto-confirming: ${prompt}"
    return 0
  fi
  local reply
  read -r -p "$(printf '%s[confirm]%s %s [y/N]: ' "$YELLOW" "$RESET" "$prompt")" reply
  case "${reply,,}" in
    y|yes) return 0 ;;
    *)     warn "aborted by user"; return 1 ;;
  esac
}

# ---------- step runner ----------
# run_step <step_num> <new_weight> <old_weight> <monitor_minutes> <prev_new> <prev_old>
# On failure: call rollback to <prev_new>/<prev_old> and exit 1 (or exit 3 if rollback fails).
PREV_NEW=0
PREV_OLD=100

rollback_to_prev() {
  local prev_new="$1" prev_old="$2"
  err "ROLLING BACK to new=${prev_new} old=${prev_old} ..."
  if "$SHIFT_RAW" "$ENVIRONMENT" "$prev_new" "$prev_old"; then
    warn "rollback to new=${prev_new} old=${prev_old} completed"
    return 0
  else
    err "ROLLBACK FAILED — page on-call immediately. State may be indeterminate."
    return 1
  fi
}

run_step() {
  local num="$1" new_w="$2" old_w="$3" mon_min="$4"
  step_log "$num" "shifting to new=${new_w} old=${old_w}, monitor ${mon_min}min"

  if ! confirm "Proceed with step ${num}: shift to new=${new_w} old=${old_w}?"; then
    return 1
  fi

  # First step uses SKIP_VALIDATION_FLAG passthrough; subsequent steps skip validation
  # (the prior monitor already verified health — re-validating is redundant).
  local extra_flags=()
  if (( num == 1 )); then
    [[ -n "$SKIP_VALIDATION_FLAG" ]] && extra_flags+=("$SKIP_VALIDATION_FLAG")
  else
    extra_flags+=(--skip-validation)
  fi

  if ! "$CUTOVER" "$CLOUD" "$ENVIRONMENT" "$new_w" "$old_w" \
          --monitor-minutes "$mon_min" "${extra_flags[@]}"; then
    local rc=$?
    err "step ${num} (new=${new_w}) failed with cutover.sh exit code ${rc}"
    if (( rc == 3 )); then
      # monitor already auto-rolled-back to PREV (legacy if step 1) — no further rollback needed
      err "monitor-cutover auto-rollback already returned traffic to new=${PREV_NEW} old=${PREV_OLD}"
      return 1
    elif (( rc == 2 )); then
      # shift failed — try to roll back to previous known-good weight
      if rollback_to_prev "$PREV_NEW" "$PREV_OLD"; then
        return 1
      else
        return 3   # rollback failed — caller exits 3
      fi
    else
      # validation failure (rc=1) — old weight untouched, no rollback needed
      return 1
    fi
  fi

  step_log "$num" "completed successfully"
  PREV_NEW="$new_w"
  PREV_OLD="$old_w"
  return 0
}

# ---------- main sequence ----------
log "starting full cutover sequence: cloud=${CLOUD} env=${ENVIRONMENT} start-step=${START_STEP}"
log "  step 1: 5%   new, ${STEP1_MIN}min monitor"
log "  step 2: 25%  new, ${STEP2_MIN}min monitor"
log "  step 3: 50%  new, ${STEP3_MIN}min monitor"
log "  step 4: 100% new, ${STEP4_MIN}min monitor"
echo

# ---------- step 0: validate at 0% ----------
if (( START_STEP <= 1 )); then
  step_log 0 "pre-flight validation at 0% (no shift)"
  if [[ -z "$SKIP_VALIDATION_FLAG" ]]; then
    if ! "${SCRIPT_DIR}/validate-cutover.sh" "$CLOUD" "$ENVIRONMENT"; then
      err "step 0 validation FAILED — aborting sequence (no traffic shifted)"
      exit 1
    fi
  else
    warn "--skip-validation: skipping step 0 validation"
  fi
fi

# ---------- steps 1-4 ----------
if (( START_STEP <= 1 )); then
  if ! run_step 1 5 95 "$STEP1_MIN"; then exit 1; fi
fi
if (( START_STEP <= 2 )); then
  if ! run_step 2 25 75 "$STEP2_MIN"; then exit 1; fi
fi
if (( START_STEP <= 3 )); then
  if ! run_step 3 50 50 "$STEP3_MIN"; then exit 1; fi
fi
if (( START_STEP <= 4 )); then
  if ! run_step 4 100 0 "$STEP4_MIN"; then exit 1; fi
fi

# ---------- post-sequence: schedule decommission ----------
DECOMMISSION_DUE=$(date -u -d "+14 days" +%FT%TZ 2>/dev/null || date -u -v+14d +%FT%TZ 2>/dev/null || echo "in 14 days")
log "FULL CUTOVER COMPLETE — 100% new stack, ${ENVIRONMENT}/${CLOUD}"
log "old Next.js stack retained for 14-day rollback window per §16"
echo
printf '%s%s=== DECOMMISSION REMINDER ===%s\n' "$BLUE" "" "$RESET"
printf '  Decommission due : %s\n' "$DECOMMISSION_DUE"
printf '  Command          : %s/decommission-old-stack.sh %s %s\n' "$SCRIPT_DIR" "$CLOUD" "$ENVIRONMENT"
printf '  Audit log        : /var/log/outrena-cutover.log\n'
echo

# Try to schedule an `at` job as a backup reminder (best-effort, non-fatal)
if command -v at >/dev/null 2>&1; then
  echo "${SCRIPT_DIR}/decommission-old-stack.sh ${CLOUD} ${ENVIRONMENT}" | at "now + 14 days" 2>/dev/null \
    && log "scheduled 'at' reminder for ${DECOMMISSION_DUE}" \
    || warn "could not schedule 'at' job (non-fatal — calendar reminder printed above)"
else
  warn "'at' not installed — calendar reminder printed above only"
fi

exit 0
