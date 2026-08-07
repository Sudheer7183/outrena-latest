#!/usr/bin/env bash
#
# monitor-cutover.sh — Post-shift monitoring for N minutes after a weight change.
#
# Purpose:
#   Per §16.3 blue/green cutover + §14 Risk #18 (slow rollback): poll the new stack
#   metrics every 30s for the configured duration. If the 5xx error rate > 1% OR
#   unhealthy-host count > 0 for 2 consecutive samples, AUTO-TRIGGER rollback
#   (delegate to the cloud-specific rollback script) and exit non-zero.
#
# Usage:
#   monitor-cutover.sh <cloud> <environment> <duration_minutes>
#     cloud             : aws | azure
#     environment       : dev | staging | production
#     duration_minutes  : integer, 1..120
#
# Exit codes:
#   0  all samples healthy — cutover stable
#   1  2 consecutive bad samples — auto-rollback triggered (or rollback failed)
#   2  usage / argument error
#   3  monitor loop crashed (data-source error, etc.)
#
# Depends on:
#   - aws CLI (cloud=aws)  — CloudWatch get-metric-statistics
#   - az CLI    (cloud=azure) — az monitor metrics list
#   - aws-route53-rollback.sh and azure-traffic-manager-rollback.sh (siblings)
#   - jq, awk, date, mktemp
#   - Env overrides:
#       OUTRENA_NEW_WEIGHT       the weight we just shifted to (for log messages)
#       OUTRENA_MONITOR_INTERVAL seconds between samples (default 30)
#       OUTRENA_5XX_THRESHOLD    percent (default 1.0)
#       OUTRENA_LATENCY_P99_MS   ms (default 2000) — informational only
# ----------------------------------------------------------------------------

set -euo pipefail

# ---------- color helpers ----------
if [[ -t 1 ]]; then
  GREEN=$(tput setaf 2); RED=$(tput setaf 1); YELLOW=$(tput setaf 3); CYAN=$(tput setaf 6); RESET=$(tput sgr0)
else
  GREEN=""; RED=""; YELLOW=""; CYAN=""; RESET=""
fi
ts() { date -u +%FT%TZ; }
log()  { printf '%s[%s]%s %s\n'  "$GREEN"  "$(ts)" "$RESET" "$*"; }
warn() { printf '%s[%s WARN]%s %s\n'  "$YELLOW" "$(ts)" "$RESET" "$*" >&2; }
err()  { printf '%s[%s ERROR]%s %s\n' "$RED"    "$(ts)" "$RESET" "$*" >&2; }

# ---------- usage ----------
usage() {
  cat <<EOF
Usage: $0 <cloud> <environment> <duration_minutes>

  cloud             : aws | azure
  environment       : dev | staging | production
  duration_minutes  : 1..120

Polls the new stack metrics every 30s. Auto-rolls back on 2 consecutive bad samples.
EOF
}

if [[ $# -ne 3 ]]; then
  err "expected exactly 3 arguments (got $#)"
  usage >&2
  exit 2
fi

CLOUD="$1"
ENVIRONMENT="$2"
DURATION_MIN="$3"

case "$CLOUD" in
  aws|azure) : ;;
  *) err "cloud must be aws|azure (got '$CLOUD')"; usage >&2; exit 2 ;;
esac
case "$ENVIRONMENT" in
  dev|staging|production) : ;;
  *) err "environment must be dev|staging|production (got '$ENVIRONMENT')"; usage >&2; exit 2 ;;
esac
if ! [[ "$DURATION_MIN" =~ ^[0-9]+$ ]] || (( DURATION_MIN < 1 || DURATION_MIN > 120 )); then
  err "duration_minutes must be integer 1..120 (got '$DURATION_MIN')"
  exit 2
fi

# ---------- configuration ----------
INTERVAL_S="${OUTRENA_MONITOR_INTERVAL:-30}"
THRESHOLD_5XX="${OUTRENA_5XX_THRESHOLD:-1.0}"
P99_WARN_MS="${OUTRENA_LATENCY_P99_MS:-2000}"
NEW_WEIGHT="${OUTRENA_NEW_WEIGHT:-unknown}"

REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$REGION"

# CSV log
TIMESTAMP_FILE=$(date -u +%Y%m%dT%H%M%SZ)
CSV_LOG="/tmp/cutover-monitor-${TIMESTAMP_FILE}.csv"
echo "timestamp,cloud,env,metric_5xx_pct,metric_p99_ms,metric_unhealthy_hosts,verdict" > "$CSV_LOG"

# Locate rollback script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$CLOUD" in
  aws)   ROLLBACK="${SCRIPT_DIR}/aws-route53-rollback.sh" ;;
  azure) ROLLBACK="${SCRIPT_DIR}/azure-traffic-manager-rollback.sh" ;;
esac
if [[ ! -x "$ROLLBACK" ]]; then
  err "rollback script not found / not executable: ${ROLLBACK}"
  exit 2
fi

# ---------- metric fetchers ----------
# Each returns 3 values: 5xx_pct, p99_ms, unhealthy_hosts — space-separated.
# On any error, returns "ERR ERR ERR" (caller treats as bad sample).
fetch_aws() {
  local now end start
  now=$(date -u +%s)
  end=$((now * 1000))
  start=$(((now - INTERVAL_S - 10) * 1000))   # 10s buffer for metric lag

  local lb_name="outrena-${ENVIRONMENT}-alb"
  local tg_name="outrena-${ENVIRONMENT}-new"

  # 5xx count + total request count (sum over last INTERVAL_S+buffer seconds)
  local http_5xx total_req
  http_5xx=$(aws cloudwatch get-metric-statistics \
      --namespace AWS/ApplicationELB \
      --metric-name HTTPCode_Target_5XX_Count \
      --dimensions Name=LoadBalancer,Value="${lb_name}" Name=TargetGroup,Value="${tg_name}" \
      --start-time "$(date -u -d "@$((now - INTERVAL_S - 20))" +%FT%TZ)" \
      --end-time   "$(date -u -d "@$((now + 5))" +%FT%TZ)" \
      --period "$((INTERVAL_S + 20))" \
      --statistics Sum \
      --query 'Datapoints[0].Sum' --output text 2>/dev/null) || http_5xx=""
  total_req=$(aws cloudwatch get-metric-statistics \
      --namespace AWS/ApplicationELB \
      --metric-name RequestCount \
      --dimensions Name=LoadBalancer,Value="${lb_name}" Name=TargetGroup,Value="${tg_name}" \
      --start-time "$(date -u -d "@$((now - INTERVAL_S - 20))" +%FT%TZ)" \
      --end-time   "$(date -u -d "@$((now + 5))" +%FT%TZ)" \
      --period "$((INTERVAL_S + 20))" \
      --statistics Sum \
      --query 'Datapoints[0].Sum' --output text 2>/dev/null) || total_req=""

  http_5xx="${http_5xx:-0}"; total_req="${total_req:-0}"
  if [[ "$http_5xx" == "None" ]]; then http_5xx=0; fi
  if [[ "$total_req" == "None" ]]; then total_req=0; fi

  local pct="0"
  if (( total_req > 0 )); then
    pct=$(awk -v r="$total_req" -v e="$http_5xx" 'BEGIN{ printf "%.4f", (e/r)*100 }')
  fi

  # p99 latency (TargetResponseTime p99)
  local p99
  p99=$(aws cloudwatch get-metric-statistics \
      --namespace AWS/ApplicationELB \
      --metric-name TargetResponseTime \
      --dimensions Name=LoadBalancer,Value="${lb_name}" Name=TargetGroup,Value="${tg_name}" \
      --start-time "$(date -u -d "@$((now - INTERVAL_S - 20))" +%FT%TZ)" \
      --end-time   "$(date -u -d "@$((now + 5))" +%FT%TZ)" \
      --period "$((INTERVAL_S + 20))" \
      --statistics ExtendedStatistics \
      --extended-statistics p99 \
      --query 'Datapoints[0].ExtendedStatistics.p99' --output text 2>/dev/null) || p99=""
  if [[ -z "$p99" || "$p99" == "None" ]]; then p99="0"; fi
  p99=$(awk -v s="$p99" 'BEGIN{ printf "%.0f", s*1000 }')   # seconds -> ms

  # unhealthy host count (max over the window)
  local unhealthy
  unhealthy=$(aws cloudwatch get-metric-statistics \
      --namespace AWS/ApplicationELB \
      --metric-name UnHealthyHostCount \
      --dimensions Name=LoadBalancer,Value="${lb_name}" Name=TargetGroup,Value="${tg_name}" \
      --start-time "$(date -u -d "@$((now - INTERVAL_S - 20))" +%FT%TZ)" \
      --end-time   "$(date -u -d "@$((now + 5))" +%FT%TZ)" \
      --period "$((INTERVAL_S + 20))" \
      --statistics Maximum \
      --query 'Datapoints[0].Maximum' --output text 2>/dev/null) || unhealthy=""
  if [[ -z "$unhealthy" || "$unhealthy" == "None" ]]; then unhealthy="0"; fi

  printf '%s %s %s' "$pct" "$p99" "$unhealthy"
}

fetch_azure() {
  local rg="${OUTRENA_AZ_RESOURCE_GROUP:-outrena-${ENVIRONMENT}}"
  local appgw="outrena-${ENVIRONMENT}-appgw"
  local now
  now=$(date -u +%FT%TZ)
  local start
  start=$(date -u -d "@$(($(date -u +%s) - INTERVAL_S - 20))" +%FT%TZ)

  # 5xx percentage: FailedRequests / (FailedRequests + TotalRequests) * 100
  local failed total p99 unhealthy
  failed=$(az monitor metrics list \
      --resource "$appgw" \
      --resource-group "$rg" \
      --resource-type Microsoft.Network/applicationGateways \
      --metric "FailedRequests" \
      --interval "PT${INTERVAL_S}S" \
      --start-time "$start" --end-time "$now" \
      --query 'value[0].timeseries[0].data[-1].total' \
      --output tsv 2>/dev/null) || failed=""
  total=$(az monitor metrics list \
      --resource "$appgw" \
      --resource-group "$rg" \
      --resource-type Microsoft.Network/applicationGateways \
      --metric "TotalRequests" \
      --interval "PT${INTERVAL_S}S" \
      --start-time "$start" --end-time "$now" \
      --query 'value[0].timeseries[0].data[-1].total' \
      --output tsv 2>/dev/null) || total=""
  failed="${failed:-0}"; total="${total:-0}"
  local pct="0"
  if (( total > 0 )); then
    pct=$(awk -v r="$total" -v e="$failed" 'BEGIN{ printf "%.4f", (e/r)*100 }')
  fi

  p99=$(az monitor metrics list \
      --resource "$appgw" \
      --resource-group "$rg" \
      --resource-type Microsoft.Network/applicationGateways \
      --metric "BackendLastByteResponseTime" \
      --interval "PT${INTERVAL_S}S" \
      --start-time "$start" --end-time "$now" \
      --query 'value[0].timeseries[0].data[-1].maximum' \
      --output tsv 2>/dev/null) || p99=""
  if [[ -z "$p99" || "$p99" == "None" ]]; then p99="0"; fi
  p99=$(awk -v s="$p99" 'BEGIN{ printf "%.0f", s*1000 }')

  unhealthy=$(az monitor metrics list \
      --resource "$appgw" \
      --resource-group "$rg" \
      --resource-type Microsoft.Network/applicationGateways \
      --metric "UnhealthyHostCount" \
      --interval "PT${INTERVAL_S}S" \
      --start-time "$start" --end-time "$now" \
      --query 'value[0].timeseries[0].data[-1].maximum' \
      --output tsv 2>/dev/null) || unhealthy=""
  if [[ -z "$unhealthy" || "$unhealthy" == "None" ]]; then unhealthy="0"; fi

  printf '%s %s %s' "$pct" "$p99" "$unhealthy"
}

# ---------- main loop ----------
log "monitoring ${CLOUD} ${ENVIRONMENT} new stack at weight=${NEW_WEIGHT} for ${DURATION_MIN}min (sample every ${INTERVAL_S}s)"
log "thresholds: 5xx > ${THRESHOLD_5XX}% OR unhealthy_hosts > 0 (2 consecutive => rollback)"
log "CSV log: ${CSV_LOG}"

CONSECUTIVE_BAD=0
TOTAL_SAMPLES=$(( (DURATION_MIN * 60) / INTERVAL_S ))
SAMPLE_IDX=0

while (( SAMPLE_IDX < TOTAL_SAMPLES )); do
  SAMPLE_IDX=$((SAMPLE_IDX + 1))
  SAMPLE_TS=$(date -u +%FT%TZ)

  read -r pct p99 unhealthy < <(
    case "$CLOUD" in
      aws)   fetch_aws   ;;
      azure) fetch_azure ;;
    esac
  )

  # verdict
  verdict="OK"
  bad=0
  if awk -v p="$pct" -v t="$THRESHOLD_5XX" 'BEGIN{ exit !(p > t) }'; then
    verdict="5XX_HIGH"; bad=1
  fi
  if (( unhealthy > 0 )); then
    verdict="${verdict}+UNHEALTHY"; bad=1
  fi

  printf '%s[%s sample %d/%d]%s 5xx=%s%%  p99=%sms  unhealthy=%s  => %s\n' \
    "$CYAN" "$SAMPLE_TS" "$SAMPLE_IDX" "$TOTAL_SAMPLES" "$RESET" \
    "$pct" "$p99" "$unhealthy" "$verdict"

  echo "${SAMPLE_TS},${CLOUD},${ENVIRONMENT},${pct},${p99},${unhealthy},${verdict}" >> "$CSV_LOG"

  if (( bad )); then
    CONSECUTIVE_BAD=$((CONSECUTIVE_BAD + 1))
    warn "bad sample (${CONSECUTIVE_BAD}/2 consecutive): ${verdict}"
    if (( CONSECUTIVE_BAD >= 2 )); then
      err "AUTO-ROLLBACK TRIGGERED — 2 consecutive bad samples"
      err "calling rollback: ${ROLLBACK} ${ENVIRONMENT}"
      export OUTRENA_ROLLBACK_REASON="auto-rollback: monitor detected ${verdict} for 2 consecutive samples"
      if "$ROLLBACK" "$ENVIRONMENT"; then
        err "rollback completed — traffic returned to legacy stack"
        log "CSV log retained at ${CSV_LOG}"
        exit 1
      else
        err "ROLLBACK FAILED — page on-call immediately"
        exit 1
      fi
    fi
  else
    CONSECUTIVE_BAD=0
  fi

  # sleep before next sample (unless this was the last)
  if (( SAMPLE_IDX < TOTAL_SAMPLES )); then
    sleep "$INTERVAL_S"
  fi
done

log "Cutover stable at weight ${NEW_WEIGHT} — ${SAMPLE_IDX} samples, 0 consecutive bad streaks reached rollback"
log "CSV log: ${CSV_LOG}"
exit 0
