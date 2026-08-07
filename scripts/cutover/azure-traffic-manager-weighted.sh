#!/usr/bin/env bash
#
# azure-traffic-manager-weighted.sh — Shift Azure Traffic Manager weights for OUTRENA blue/green cutover.
#
# Purpose:
#   Update the two endpoints (named "new" and "old") on the Traffic Manager profile
#   outrena-<env> to weight=$NEW and weight=$OLD respectively. Disables the "old"
#   endpoint when its weight is 0 (per §16 Rollback Plan — full cutover should
#   take the legacy endpoint offline cleanly). Then verifies via check-dns that
#   the profile is responding with the new routing.
#
# Usage:
#   azure-traffic-manager-weighted.sh <environment> <new_weight> [old_weight]
#     environment : dev | staging | production
#     new_weight  : 0-100  (traffic % to new FastAPI stack endpoint "new")
#     old_weight  : 0-100  (traffic % to legacy Next.js stack endpoint "old").
#                          Default = 100 - new_weight.
#
# Exit codes:
#   0  success — weights shifted, profile DNS check passed
#   1  usage / argument validation error
#   2  Azure CLI error (profile lookup, endpoint update, check-dns)
#
# Depends on:
#   - az CLI (logged in: az login + az account set --subscription <id>)
#   - Environment variables (optional overrides):
#       OUTRENA_AZ_RESOURCE_GROUP  default outrena-<env>
#       OUTRENA_AZ_PROFILE_NAME    default outrena-<env>
#       OUTRENA_AZ_NEW_ENDPOINT    default outrena-<env>-new-app
#       OUTRENA_AZ_OLD_ENDPOINT    default outrena-<env>-legacy-app
#       OUTRENA_AZ_MONITOR_TIMEOUT default 90  (seconds to wait for check-dns stability)
#   - Bash 4+, jq
#
# Notes:
#   - Azure TM does NOT use TTL in the same way Route 53 does — typical propagation
#     is 30-60s thanks to TM's low DNS TTL (~30s). Risk #18 mitigation: we still
#     wait for check-dns confirmation.
#   - When old_weight=0 the legacy endpoint is disabled (not deleted) so it can be
#     quickly re-enabled by the rollback script.
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
  new_weight  : 0-100 (integer) — % traffic to new FastAPI stack (endpoint "new")
  old_weight  : 0-100 (integer) — % traffic to legacy Next.js stack (endpoint "old")
                (default: 100 - new_weight)

Examples:
  $0 production 5          # 5% new, 95% old
  $0 production 100 0      # full cutover — legacy endpoint disabled
  $0 staging 50 50         # 50/50 canary
EOF
}

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
RESOURCE_GROUP="${OUTRENA_AZ_RESOURCE_GROUP:-outrena-${ENVIRONMENT}}"
PROFILE_NAME="${OUTRENA_AZ_PROFILE_NAME:-outrena-${ENVIRONMENT}}"
NEW_ENDPOINT="${OUTRENA_AZ_NEW_ENDPOINT:-outrena-${ENVIRONMENT}-new-app}"
OLD_ENDPOINT="${OUTRENA_AZ_OLD_ENDPOINT:-outrena-${ENVIRONMENT}-legacy-app}"
MONITOR_TIMEOUT="${OUTRENA_AZ_MONITOR_TIMEOUT:-90}"

# ---------- preflight: az CLI + profile existence ----------
if ! command -v az >/dev/null 2>&1; then
  err "az CLI not found in PATH"
  exit 2
fi

log "looking up Traffic Manager profile ${PROFILE_NAME} in rg ${RESOURCE_GROUP} ..."
if ! az network traffic-manager profile show \
        --name "$PROFILE_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'name' \
        --output tsv >/dev/null 2>&1; then
  err "Traffic Manager profile '${PROFILE_NAME}' not found in rg '${RESOURCE_GROUP}'"
  exit 2
fi

# ---------- update NEW endpoint ----------
log "updating endpoint '${NEW_ENDPOINT}' weight=${NEW_WEIGHT} (Enabled) ..."
if ! az network traffic-manager endpoint update \
        --profile-name "$PROFILE_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --name "$NEW_ENDPOINT" \
        --type azureEndpoints \
        --weight "$NEW_WEIGHT" \
        --endpoint-status Enabled >/dev/null; then
  err "failed to update endpoint '${NEW_ENDPOINT}' (new stack)"
  exit 2
fi

# ---------- update OLD endpoint (disable if weight==0) ----------
if (( OLD_WEIGHT == 0 )); then
  log "updating endpoint '${OLD_ENDPOINT}' weight=${OLD_WEIGHT} (Disabled) ..."
  OLD_STATUS="Disabled"
else
  log "updating endpoint '${OLD_ENDPOINT}' weight=${OLD_WEIGHT} (Enabled) ..."
  OLD_STATUS="Enabled"
fi
if ! az network traffic-manager endpoint update \
        --profile-name "$PROFILE_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --name "$OLD_ENDPOINT" \
        --type azureEndpoints \
        --weight "$OLD_WEIGHT" \
        --endpoint-status "$OLD_STATUS" >/dev/null; then
  err "failed to update endpoint '${OLD_ENDPOINT}' (old stack)"
  exit 2
fi

# ---------- verify via check-dns ----------
# check-dns returns 200 when the profile DNS is healthy. We poll briefly to allow
# the TM controller to converge (typically <30s).
log "verifying profile DNS health (timeout ${MONITOR_TIMEOUT}s) ..."
DEADLINE=$(( $(date +%s) + MONITOR_TIMEOUT ))
DNS_OK=0
while :; do
  RESP=$(az network traffic-manager profile check-dns \
            --name "$PROFILE_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --query 'dnsVerificationStatus' \
            --output tsv 2>/dev/null || echo "")
  if [[ "$RESP" == "AllowableTraffic" ]]; then
    DNS_OK=1
    break
  fi
  if (( $(date +%s) >= DEADLINE )); then
    break
  fi
  sleep 5
done

if (( DNS_OK != 1 )); then
  err "Traffic Manager DNS check did not reach 'AllowableTraffic' within ${MONITOR_TIMEOUT}s (last status='${RESP}')"
  err "weights WERE updated — investigate the profile monitor configuration manually."
  exit 2
fi

# ---------- success ----------
log "Traffic Manager weights shifted: new=${NEW_WEIGHT} old=${OLD_WEIGHT} (old endpoint ${OLD_STATUS})."
log "  profile     : ${PROFILE_NAME}"
log "  rg          : ${RESOURCE_GROUP}"
log "  new endpoint: ${NEW_ENDPOINT} (weight ${NEW_WEIGHT}, Enabled)"
log "  old endpoint: ${OLD_ENDPOINT} (weight ${OLD_WEIGHT}, ${OLD_STATUS})"
log "  dns status  : AllowableTraffic"
log "  propagation : ~30-60s (Azure TM low TTL)"
exit 0
