#!/usr/bin/env bash
#
# validate-cutover.sh — Pre-flight health check before shifting DNS/TM weight.
#
# Purpose:
#   Per §16 cutover runbook + §14 Risk #18 (slow rollback) + pitfall #16 (JWKS must
#   be fetchable before traffic): confirm the NEW FastAPI stack is fully healthy
#   against the SAME backing services (DB, Redis, Keycloak) it will use in prod,
#   BEFORE any end-user traffic reaches it. Hitting the new stack direct (bypassing
#   DNS) via the ALB/App Gateway IP + Host header avoids the chicken-and-egg of
#   "weight is 0 but I want to test the new stack".
#
# Usage:
#   validate-cutover.sh <cloud> <environment>
#     cloud       : aws | azure
#     environment : dev | staging | production
#
# Exit codes:
#   0  all critical checks passed — safe to shift weight
#   1  one or more critical checks failed — DO NOT shift weight
#   2  usage / argument error
#
# Depends on:
#   - curl (with retries), jq, awk, tput
#   - aws CLI (for aws: used to look up ALB DNS + RDS reachability stub)
#   - az CLI (for azure: used to look up App Gateway FQDN)
#   - Environment overrides:
#       OUTRENA_NEW_HOST      explicit Host header (skips ALB/AppGW lookup)
#       OUTRENA_NEW_DIRECT_IP explicit IP to hit (skips ALB/AppGW lookup)
#       OUTRENA_NEW_PORT      default 443 (https)
#       OUTRENA_NEW_SCHEME    default https
#       OUTRENA_HEALTH_PATH   default /health
#       OUTRENA_NEW_INTERNAL_HOST  default app.outrena.com (Host header sent)
# ----------------------------------------------------------------------------

set -euo pipefail

# ---------- color helpers ----------
if [[ -t 1 ]]; then
  GREEN=$(tput setaf 2); RED=$(tput setaf 1); YELLOW=$(tput setaf 3); BLUE=$(tput setaf 4); RESET=$(tput sgr0)
else
  GREEN=""; RED=""; YELLOW=""; BLUE=""; RESET=""
fi
ts() { date -u +%FT%TZ; }
log()  { printf '%s[%s]%s %s\n'  "$GREEN"  "$(ts)" "$RESET" "$*"; }
warn() { printf '%s[%s WARN]%s %s\n'  "$YELLOW" "$(ts)" "$RESET" "$*" >&2; }
err()  { printf '%s[%s ERROR]%s %s\n' "$RED"    "$(ts)" "$RESET" "$*" >&2; }

# ---------- usage ----------
usage() {
  cat <<EOF
Usage: $0 <cloud> <environment>

  cloud       : aws | azure
  environment : dev | staging | production

Pre-flight health check against the NEW FastAPI stack (direct, bypassing DNS).
All checks must pass before shifting weighted DNS/TM traffic.
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

# ---------- configuration ----------
SCHEME="${OUTRENA_NEW_SCHEME:-https}"
PORT="${OUTRENA_NEW_PORT:-443}"
INTERNAL_HOST="${OUTRENA_NEW_INTERNAL_HOST:-app.outrena.com}"
HEALTH_PATH="${OUTRENA_HEALTH_PATH:-/health}"
CURL_MAX_TIME=10
CURL_RETRIES=3
CURL_RETRY_DELAY=2

# ---------- discover direct target IP/DNS for the new stack ----------
# We bypass the weighted DNS by connecting to the new stack's load balancer
# directly, but send the production Host header so virtual-host routing matches.
TARGET_HOST=""
TARGET_IP=""

if [[ -n "${OUTRENA_NEW_HOST:-}" ]]; then
  TARGET_HOST="$OUTRENA_NEW_HOST"
fi
if [[ -n "${OUTRENA_NEW_DIRECT_IP:-}" ]]; then
  TARGET_IP="$OUTRENA_NEW_DIRECT_IP"
fi

if [[ -z "$TARGET_HOST" ]]; then
  case "$CLOUD" in
    aws)
      if ! command -v aws >/dev/null 2>&1; then
        err "aws CLI required to look up ALB DNS (or set OUTRENA_NEW_HOST explicitly)"
        exit 1
      fi
      export AWS_DEFAULT_REGION="${AWS_REGION:-us-east-1}"
      log "looking up ALB DNS for outrena-${ENVIRONMENT}-alb ..."
      TARGET_HOST=$(aws elbv2 describe-load-balancers \
            --query "LoadBalancers[?LoadBalancerName=='outrena-${ENVIRONMENT}-alb'].DNSName" \
            --output text 2>/dev/null) || true
      if [[ -z "$TARGET_HOST" || "$TARGET_HOST" == "None" ]]; then
        err "could not find ALB 'outrena-${ENVIRONMENT}-alb' — set OUTRENA_NEW_HOST explicitly"
        exit 1
      fi
      ;;
    azure)
      if ! command -v az >/dev/null 2>&1; then
        err "az CLI required to look up App Gateway FQDN (or set OUTRENA_NEW_HOST explicitly)"
        exit 1
      fi
      local_rg="${OUTRENA_AZ_RESOURCE_GROUP:-outrena-${ENVIRONMENT}}"
      log "looking up App Gateway frontend IP config FQDN in rg ${local_rg} ..."
      TARGET_HOST=$(az network application-gateway show \
            --name "outrena-${ENVIRONMENT}-appgw" \
            --resource-group "$local_rg" \
            --query 'frontendIpConfigurations[0].publicIPAddress.id' \
            --output tsv 2>/dev/null) || true
      # The above returns the PIP id, not the FQDN — we resolve the PIP dnsLabel.
      if [[ -n "$TARGET_HOST" && "$TARGET_HOST" != "None" ]]; then
        TARGET_HOST=$(az network public-ip show \
              --ids "$TARGET_HOST" \
              --query 'dnsSettings.fqdn' \
              --output tsv 2>/dev/null) || true
      fi
      if [[ -z "$TARGET_HOST" || "$TARGET_HOST" == "None" ]]; then
        err "could not find App Gateway FQDN — set OUTRENA_NEW_HOST explicitly"
        exit 1
      fi
      ;;
  esac
fi

if [[ -z "$TARGET_IP" ]]; then
  # resolve the LB hostname to an IP for the --resolve flag (curl will use it as-is
  # but --resolve avoids DNS lookup latency in retry loops)
  TARGET_IP=$(getent hosts "$TARGET_HOST" 2>/dev/null | awk '{print $1}' | head -n1) || true
fi

if [[ -z "$TARGET_IP" ]]; then
  warn "could not resolve ${TARGET_HOST} to an IP — will fall back to --resolve with hostname"
  TARGET_IP="$TARGET_HOST"
fi

log "validating new stack at ${SCHEME}://${TARGET_HOST}:${PORT} (IP=${TARGET_IP}, Host=${INTERNAL_HOST})"

# ---------- curl helper ----------
# Calls $URL expecting HTTP $EXPECT_STATUS; on non-2xx/timeout retries up to CURL_RETRIES.
# Globals set on success: LAST_BODY, LAST_STATUS.
LAST_BODY=""
LAST_STATUS=""
curl_check() {
  local path="$1"
  local expect_status="$2"
  local description="$3"
  local attempt=0
  local url="${SCHEME}://${TARGET_HOST}:${PORT}${path}"
  local code

  while (( attempt < CURL_RETRIES )); do
    attempt=$((attempt + 1))
    code=$(curl -sS \
            --max-time "$CURL_MAX_TIME" \
            --resolve "${TARGET_HOST}:${PORT}:${TARGET_IP}" \
            -H "Host: ${INTERNAL_HOST}" \
            -o /tmp/validate-cutover.body \
            -w '%{http_code}' \
            "$url" 2>/dev/null) || code="000"
    if [[ "$code" == "$expect_status" ]]; then
      LAST_BODY="$(cat /tmp/validate-cutover.body 2>/dev/null || true)"
      LAST_STATUS="$code"
      return 0
    fi
    warn "attempt ${attempt}/${CURL_RETRIES} for ${path} -> HTTP ${code} (expected ${expect_status})"
    sleep "$CURL_RETRY_DELAY"
  done
  LAST_BODY="$(cat /tmp/validate-cutover.body 2>/dev/null || true)"
  LAST_STATUS="$code"
  return 1
}

# ---------- check runner ----------
# Each check: name | description | status | detail
CHECKS=()
FAIL_COUNT=0
WARN_COUNT=0

record() {
  # record <name> <status> <detail>
  CHECKS+=("$1|$2|$3")
  case "$2" in
    PASS) ;;
    WARN) WARN_COUNT=$((WARN_COUNT+1)) ;;
    FAIL) FAIL_COUNT=$((FAIL_COUNT+1)) ;;
  esac
}

# ===== Check 1: /health =====
log "check 1/5: GET ${HEALTH_PATH} (expect 200 + JSON status=healthy)"
if curl_check "$HEALTH_PATH" 200 "liveness"; then
  if echo "$LAST_BODY" | jq -e '.status == "healthy"' >/dev/null 2>&1; then
    record "health" PASS "200 status=healthy"
  else
    record "health" FAIL "200 but body not {status:healthy} — body: $(echo "$LAST_BODY" | head -c 200)"
  fi
else
  record "health" FAIL "HTTP ${LAST_STATUS} after ${CURL_RETRIES} retries"
fi

# ===== Check 2: Keycloak OIDC discovery (pitfall #16 — JWKS must be reachable) =====
log "check 2/5: GET /auth/realms/outrena/.well-known/openid-configuration (expect 200 + jwks_uri)"
if curl_check "/auth/realms/outrena/.well-known/openid-configuration" 200 "oidc-discovery"; then
  JWKS_URI=$(echo "$LAST_BODY" | jq -r '.jwks_uri // empty' 2>/dev/null || true)
  if [[ -n "$JWKS_URI" ]]; then
    record "oidc-discovery" PASS "200 jwks_uri=${JWKS_URI}"
  else
    record "oidc-discovery" FAIL "200 but no jwks_uri in body"
  fi
else
  record "oidc-discovery" FAIL "HTTP ${LAST_STATUS}"
fi

# ===== Check 3: JWKS reachable (pitfall #16 — verify jwks_uri fetches cleanly) =====
if [[ -n "${JWKS_URI:-}" ]]; then
  log "check 3/5: GET ${JWKS_URI} (JWKS endpoint, expect 200 + keys array)"
  code=$(curl -sS --max-time "$CURL_MAX_TIME" -o /tmp/validate-cutover.jwks \
          -w '%{http_code}' "$JWKS_URI" 2>/dev/null) || code="000"
  if [[ "$code" == "200" ]] && jq -e '.keys | type == "array" and length > 0' /tmp/validate-cutover.jwks >/dev/null 2>&1; then
    record "jwks-reachable" PASS "200 keys count=$(jq '.keys | length' /tmp/validate-cutover.jwks)"
  else
    record "jwks-reachable" FAIL "HTTP ${code} (per pitfall #16, traffic MUST NOT shift if JWKS unreachable)"
    FAIL_COUNT=$((FAIL_COUNT+1))
  fi
else
  record "jwks-reachable" FAIL "skipped — no jwks_uri from previous check"
fi

# ===== Check 4: /api/v1/tenants/health (new endpoint, may 404) =====
log "check 4/5: GET /api/v1/tenants/health (expect 200 — 404 = warn only)"
if curl_check "/api/v1/tenants/health" 200 "tenants-health"; then
  record "tenants-health" PASS "200"
elif [[ "$LAST_STATUS" == "404" ]]; then
  record "tenants-health" WARN "404 — endpoint may not exist yet (warn only)"
  WARN_COUNT=$((WARN_COUNT+1))
else
  record "tenants-health" FAIL "HTTP ${LAST_STATUS}"
fi

# ===== Check 5a: DB connectivity (via HTTP /api/v1/health/db) =====
log "check 5/5a: GET /api/v1/health/db (expect 200 + JSON status=ok)"
if curl_check "/api/v1/health/db" 200 "db-health"; then
  if echo "$LAST_BODY" | jq -e '.status == "ok" or .database == "ok"' >/dev/null 2>&1; then
    record "db-health" PASS "200 db=ok"
  else
    record "db-health" WARN "200 but body shape unexpected: $(echo "$LAST_BODY" | head -c 200)"
    WARN_COUNT=$((WARN_COUNT+1))
  fi
else
  record "db-health" FAIL "HTTP ${LAST_STATUS}"
fi

# ===== Check 5b: Redis connectivity (via HTTP /api/v1/health/redis) =====
log "check 5/5b: GET /api/v1/health/redis (expect 200 + JSON status=ok)"
if curl_check "/api/v1/health/redis" 200 "redis-health"; then
  if echo "$LAST_BODY" | jq -e '.status == "ok" or .redis == "ok"' >/dev/null 2>&1; then
    record "redis-health" PASS "200 redis=ok"
  else
    record "redis-health" WARN "200 but body shape unexpected: $(echo "$LAST_BODY" | head -c 200)"
    WARN_COUNT=$((WARN_COUNT+1))
  fi
else
  record "redis-health" FAIL "HTTP ${LAST_STATUS}"
fi

# ---------- summary table ----------
echo
printf '%s%s=== VALIDATION SUMMARY (%s / %s) ===%s\n' "$BLUE" "" "$(ts)" "$ENVIRONMENT" "$RESET"
printf '%-20s %-6s %s\n' "CHECK" "STATUS" "DETAIL"
printf '%-20s %-6s %s\n' "--------------------" "------" "--------------------------------------------------"
for line in "${CHECKS[@]}"; do
  IFS='|' read -r name status detail <<<"$line"
  case "$status" in
    PASS) color="$GREEN" ;;
    WARN) color="$YELLOW" ;;
    FAIL) color="$RED" ;;
    *)    color="" ;;
  esac
  printf '%-20s %s%-6s%s %s\n' "$name" "$color" "$status" "$RESET" "$detail"
done
echo
printf 'Pass=%d  Warn=%d  Fail=%d\n' \
  $(( ${#CHECKS[@]} - WARN_COUNT - FAIL_COUNT )) "$WARN_COUNT" "$FAIL_COUNT"

# ---------- exit ----------
if (( FAIL_COUNT > 0 )); then
  err "${FAIL_COUNT} critical check(s) failed — DO NOT shift DNS weight"
  exit 1
fi
if (( WARN_COUNT > 0 )); then
  warn "${WARN_COUNT} non-critical warning(s) — proceeding (per spec: warnings do not block)"
fi
log "all critical checks passed — safe to shift weight to new stack"
exit 0
