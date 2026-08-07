#!/usr/bin/env bash
#
# cutover.sh — Orchestrator: validate → shift weight → monitor (with auto-rollback).
#
# Purpose:
#   Single entry point for a weighted-DNS cutover step (per §16.3). Runs:
#     1. validate-cutover.sh    (skip with --skip-validation)
#     2. cloud-specific weight shift (aws-route53-weighted.sh OR azure-traffic-manager-weighted.sh)
#     3. monitor-cutover.sh     (skip with --skip-monitoring) — auto-rolls-back on failure
#
# Usage:
#   cutover.sh <cloud> <environment> <new_weight> [old_weight] [--skip-validation] [--skip-monitoring] [--monitor-minutes N]
#
#     cloud             : aws | azure
#     environment       : dev | staging | production
#     new_weight        : 0-100
#     old_weight        : 0-100 (default 100 - new_weight)
#     --skip-validation : skip pre-flight health check (NOT RECOMMENDED)
#     --skip-monitoring : skip post-shift monitoring (NOT RECOMMENDED)
#     --monitor-minutes N : override monitor duration (default 10)
#
# Exit codes:
#   0  success — weight shifted, monitoring passed (or skipped)
#   1  validation failed (aborted BEFORE shift — old weight untouched)
#   2  shift failed (AWS/Azure error — state may be indeterminate, manual check required)
#   3  monitoring failed → auto-rollback triggered (legacy stack now serving traffic)
#   4  unknown cloud
#
# Depends on:
#   - sibling scripts validate-cutover.sh, monitor-cutover.sh,
#     aws-route53-weighted.sh, azure-traffic-manager-weighted.sh,
#     aws-route53-rollback.sh, azure-traffic-manager-rollback.sh
# ----------------------------------------------------------------------------

set -euo pipefail

# ---------- color helpers ----------
if [[ -t 1 ]]; then
  GREEN=$(tput setaf 2); RED=$(tput setaf 1); YELLOW=$(tput setaf 3); BLUE=$(tput setaf 4); RESET=$(tput sgr0)
else
  GREEN=""; RED=""; YELLOW=""; BLUE=""; RESET=""
fi
ts() { date -u +%FT%TZ; }
log()  { printf '%s[%s CUTOVER]%s %s\n'  "$GREEN"  "$(ts)" "$RESET" "$*"; }
warn() { printf '%s[%s CUTOVER WARN]%s %s\n'  "$YELLOW" "$(ts)" "$RESET" "$*" >&2; }
err()  { printf '%s[%s CUTOVER ERROR]%s %s\n' "$RED"    "$(ts)" "$RESET" "$*" >&2; }

# ---------- usage ----------
usage() {
  cat <<EOF
Usage: $0 <cloud> <environment> <new_weight> [old_weight] [options]

  cloud             : aws | azure
  environment       : dev | staging | production
  new_weight        : 0-100
  old_weight        : 0-100 (default 100 - new_weight)

Options:
  --skip-validation     Skip pre-flight health check (NOT RECOMMENDED)
  --skip-monitoring     Skip post-shift monitoring (NOT RECOMMENDED)
  --monitor-minutes N   Monitor duration in minutes (default 10)

Exit codes:
  0 success | 1 validation fail | 2 shift fail | 3 monitor fail (auto-rollback) | 4 unknown cloud
EOF
}

# ---------- parse args ----------
# Mixed positional + flags: walk argv and route.
POSITIONAL=()
SKIP_VALIDATION=0
SKIP_MONITORING=0
MONITOR_MINUTES=10

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-validation)  SKIP_VALIDATION=1; shift ;;
    --skip-monitoring)  SKIP_MONITORING=1; shift ;;
    --monitor-minutes)
      [[ $# -ge 2 ]] || { err "--monitor-minutes requires a value"; usage >&2; exit 2; }
      MONITOR_MINUTES="$2"; shift 2 ;;
    --monitor-minutes=*)
      MONITOR_MINUTES="${1#*=}"; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; POSITIONAL+=("$@"); break ;;
    -*) err "unknown option: $1"; usage >&2; exit 2 ;;
    *)  POSITIONAL+=("$1"); shift ;;
  esac
done

if (( ${#POSITIONAL[@]} < 3 || ${#POSITIONAL[@]} > 4 )); then
  err "expected 3 or 4 positional arguments (got ${#POSITIONAL[@]})"
  usage >&2
  exit 2
fi

CLOUD="${POSITIONAL[0]}"
ENVIRONMENT="${POSITIONAL[1]}"
NEW_WEIGHT="${POSITIONAL[2]}"
OLD_WEIGHT="${POSITIONAL[3]:-}"

case "$CLOUD" in
  aws|azure) : ;;
  *) err "unknown cloud: '$CLOUD' (must be aws|azure)"; exit 4 ;;
esac
case "$ENVIRONMENT" in
  dev|staging|production) : ;;
  *) err "environment must be dev|staging|production (got '$ENVIRONMENT')"; exit 2 ;;
esac
if ! [[ "$NEW_WEIGHT" =~ ^[0-9]+$ ]] || (( NEW_WEIGHT < 0 || NEW_WEIGHT > 100 )); then
  err "new_weight must be integer 0-100 (got '$NEW_WEIGHT')"; exit 2
fi
if [[ -z "$OLD_WEIGHT" ]]; then
  OLD_WEIGHT=$(( 100 - NEW_WEIGHT ))
elif ! [[ "$OLD_WEIGHT" =~ ^[0-9]+$ ]] || (( OLD_WEIGHT < 0 || OLD_WEIGHT > 100 )); then
  err "old_weight must be integer 0-100 (got '$OLD_WEIGHT')"; exit 2
elif (( NEW_WEIGHT + OLD_WEIGHT != 100 )); then
  err "new_weight + old_weight must sum to 100"; exit 2
fi

# ---------- locate siblings ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATE="${SCRIPT_DIR}/validate-cutover.sh"
MONITOR="${SCRIPT_DIR}/monitor-cutover.sh"
case "$CLOUD" in
  aws)   SHIFT_SCRIPT="${SCRIPT_DIR}/aws-route53-weighted.sh"
         ROLLBACK="${SCRIPT_DIR}/aws-route53-rollback.sh" ;;
  azure) SHIFT_SCRIPT="${SCRIPT_DIR}/azure-traffic-manager-weighted.sh"
         ROLLBACK="${SCRIPT_DIR}/azure-traffic-manager-rollback.sh" ;;
esac

for s in "$VALIDATE" "$MONITOR" "$SHIFT_SCRIPT" "$ROLLBACK"; do
  if [[ ! -x "$s" ]]; then
    err "required sibling script not found / not executable: $s"
    exit 2
  fi
done

# ---------- phase 1: validate ----------
log "PHASE 1/3: validation (cloud=${CLOUD} env=${ENVIRONMENT})"
if (( SKIP_VALIDATION )); then
  warn "--skip-validation: skipping pre-flight health check (OLD WEIGHT UNCHANGED)"
else
  if ! "$VALIDATE" "$CLOUD" "$ENVIRONMENT"; then
    err "validation FAILED — aborting BEFORE weight shift (old weight untouched)"
    exit 1
  fi
  log "validation passed"
fi

# ---------- phase 2: shift weight ----------
log "PHASE 2/3: shift weights new=${NEW_WEIGHT} old=${OLD_WEIGHT}"
if ! "$SHIFT_SCRIPT" "$ENVIRONMENT" "$NEW_WEIGHT" "$OLD_WEIGHT"; then
  err "SHIFT FAILED — state may be indeterminate. Manual verification required:"
  err "  aws:   aws route53 test-dns-answer --hosted-zone-id <HZ> --record-name *.outrena.com --record-type A"
  err "  azure: az network traffic-manager profile show -g <rg> -n outrena-${ENVIRONMENT}"
  exit 2
fi
log "shift succeeded"

# ---------- phase 3: monitor (with auto-rollback) ----------
log "PHASE 3/3: monitor (${MONITOR_MINUTES}min)"
if (( SKIP_MONITORING )); then
  warn "--skip-monitoring: skipping post-shift monitoring (weight shifted, but stability NOT verified)"
  log "CUTOVER COMPLETE (no monitoring) — new=${NEW_WEIGHT} old=${OLD_WEIGHT}"
  exit 0
fi

# Pass NEW_WEIGHT so monitor-cutover.sh can log it.
export OUTRENA_NEW_WEIGHT="$NEW_WEIGHT"
if ! "$MONITOR" "$CLOUD" "$ENVIRONMENT" "$MONITOR_MINUTES"; then
  # monitor-cutover.sh already triggered rollback on its way out
  err "MONITOR FAILED — auto-rollback triggered. Traffic returned to legacy stack."
  err "  Investigate root cause before re-attempting cutover."
  exit 3
fi

log "CUTOVER COMPLETE — new=${NEW_WEIGHT} old=${OLD_WEIGHT} stable after ${MONITOR_MINUTES}min monitoring"
exit 0
