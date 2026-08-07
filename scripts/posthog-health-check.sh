#!/usr/bin/env bash
# posthog-health-check.sh — Health check for the self-hosted PostHog stack (PH-INFRA).
#
# Usage:
#   scripts/posthog-health-check.sh [--host http://localhost:8000] [--json]
#
# Checks:
#   1. PostHog web UI reachable  (HTTP GET /)
#   2. PostHog /api/health responds 200  (HTTP GET /api/health)
#   3. PostHog /_health/ responds 200  (HTTP GET /_health/)
#   4. ClickHouse /ping responds 200  (HTTP GET :8123/ping)
#   5. Postgres accepts connections  (TCP :5432 or :5433 in dev)
#   6. Redis PONG  (TCP :6379 or :6380 in dev)
#   7. Kafka broker list responds  (kafka-topics --list)
#   8. ClickHouse disk usage  (warn > 80%)
#   9. Postgres connection count  (warn > 80% of max)
#  10. Redis memory usage  (warn > 80%)
#  11. Kafka consumer lag  (warn if any consumer group lag > 1000)
#
# Exit codes:
#   0 — all healthy
#   1 — at least one CRITICAL check failed (web/UI/API/CH/PG/Redis/Kafka unreachable)
#   2 — all critical checks passed but at least one WARNING (disk/memory/lag over threshold)
#
# Cross-references:
#   - runbooks/15-exception-logging-self-healing.md §8 "Monitoring the system"
#   - docker-compose.posthog.yml — dev stack
#   - terraform/aws/posthog.tf + terraform/azure/posthog.tf — prod stack

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
HOST="${POSTHOG_HOST:-http://localhost:8000}"
JSON_OUTPUT=false

# Service endpoints — override via env vars or args for prod.
# Dev defaults match docker-compose.posthog.yml ports (5433, 6380 to avoid
# clashing with OUTRENA's 5432, 6379).
CLICKHOUSE_HTTP_HOST="${CLICKHOUSE_HTTP_HOST:-localhost:8123}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost:5433}"
POSTGRES_USER="${POSTGRES_USER:-posthog}"
POSTGRES_DB="${POSTGRES_DB:-posthog}"
REDIS_HOST="${REDIS_HOST:-localhost:6380}"
KAFKA_BROKER="${KAFKA_BROKER:-localhost:29092}"

# Thresholds (percent, except KAFKA_LAG_THRESHOLD which is a count).
DISK_WARN_PCT=80
CONN_WARN_PCT=80
REDIS_MEM_WARN_PCT=80
KAFKA_LAG_THRESHOLD=1000

# Color codes (disabled for JSON output).
if [[ -t 1 ]] && [[ "${NO_COLOR:-}" == "" ]]; then
  RED=$'\e[31m'
  YELLOW=$'\e[33m'
  GREEN=$'\e[32m'
  BLUE=$'\e[34m'
  RESET=$'\e[0m'
else
  RED=""
  YELLOW=""
  GREEN=""
  BLUE=""
  RESET=""
fi

# ── Arg parsing ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"
      shift 2
      ;;
    --json)
      JSON_OUTPUT=true
      shift
      ;;
    --help|-h)
      sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown arg: $1 (try --help)" >&2
      exit 1
      ;;
  esac
done

# ── Output helpers ───────────────────────────────────────────────────────────
# We collect results into an array, then print at the end (so JSON mode can
# emit a single JSON object).
declare -a RESULTS
CRITICAL_COUNT=0
WARNING_COUNT=0

record_ok() {
  local name="$1" detail="$2"
  if [[ "$JSON_OUTPUT" == "false" ]]; then
    printf '%s✅ OK   %s%s — %s\n' "$GREEN" "$name" "$RESET" "$detail"
  fi
  RESULTS+=("{\"status\":\"ok\",\"name\":\"$name\",\"detail\":\"$detail\"}")
}

record_warn() {
  local name="$1" detail="$2"
  if [[ "$JSON_OUTPUT" == "false" ]]; then
    printf '%s⚠️  WARN %s%s — %s\n' "$YELLOW" "$name" "$RESET" "$detail"
  fi
  RESULTS+=("{\"status\":\"warn\",\"name\":\"$name\",\"detail\":\"$detail\"}")
  WARNING_COUNT=$((WARNING_COUNT + 1))
}

record_critical() {
  local name="$1" detail="$2"
  if [[ "$JSON_OUTPUT" == "false" ]]; then
    printf '%s❌ CRIT %s%s — %s\n' "$RED" "$name" "$RESET" "$detail"
  fi
  RESULTS+=("{\"status\":\"critical\",\"name\":\"$name\",\"detail\":\"$detail\"}")
  CRITICAL_COUNT=$((CRITICAL_COUNT + 1))
}

# ── HTTP helpers ─────────────────────────────────────────────────────────────
http_status() {
  # $1 = URL. Returns HTTP status code (integer) or 0 on connection failure.
  curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$1" 2>/dev/null || echo 0
}

http_body() {
  # $1 = URL. Returns response body (truncated to 200 chars).
  curl -sS --max-time 5 "$1" 2>/dev/null | head -c 200
}

# ── 1. PostHog web UI ────────────────────────────────────────────────────────
status=$(http_status "$HOST/")
if [[ "$status" == "200" ]] || [[ "$status" == "302" ]]; then
  record_ok "PostHog web UI" "HTTP $status at $HOST/"
else
  record_critical "PostHog web UI" "HTTP $status at $HOST/ (expected 200 or 302)"
fi

# ── 2. PostHog /api/health ───────────────────────────────────────────────────
status=$(http_status "$HOST/api/health")
if [[ "$status" == "200" ]]; then
  body=$(http_body "$HOST/api/health")
  record_ok "PostHog /api/health" "HTTP 200 — $body"
else
  record_critical "PostHog /api/health" "HTTP $status (expected 200)"
fi

# ── 3. PostHog /_health/ ─────────────────────────────────────────────────────
status=$(http_status "$HOST/_health/")
if [[ "$status" == "200" ]]; then
  record_ok "PostHog /_health/" "HTTP 200"
else
  record_critical "PostHog /_health/" "HTTP $status (expected 200)"
fi

# ── 4. ClickHouse /ping ──────────────────────────────────────────────────────
status=$(http_status "http://${CLICKHOUSE_HTTP_HOST}/ping")
if [[ "$status" == "200" ]]; then
  record_ok "ClickHouse /ping" "HTTP 200 at $CLICKHOUSE_HTTP_HOST"
else
  record_critical "ClickHouse /ping" "HTTP $status at $CLICKHOUSE_HTTP_HOST (expected 200)"
fi

# ── 5. Postgres ──────────────────────────────────────────────────────────────
if command -v pg_isready >/dev/null 2>&1; then
  pg_host="${POSTGRES_HOST%%:*}"
  pg_port="${POSTGRES_HOST##*:}"
  if pg_isready -h "$pg_host" -p "$pg_port" -U "$POSTGRES_USER" >/dev/null 2>&1; then
    record_ok "Postgres" "accepting connections at $POSTGRES_HOST (db=$POSTGRES_DB, user=$POSTGRES_USER)"
  else
    record_critical "Postgres" "pg_isready failed at $POSTGRES_HOST"
  fi
else
  # Fall back to a TCP check.
  if (echo > /dev/tcp/"${POSTGRES_HOST/:/ }") 2>/dev/null; then
    record_ok "Postgres (TCP only)" "port open at $POSTGRES_HOST (install psql for a real check)"
  else
    record_critical "Postgres" "TCP connect failed at $POSTGRES_HOST"
  fi
fi

# ── 6. Redis ─────────────────────────────────────────────────────────────────
if command -v redis-cli >/dev/null 2>&1; then
  if redis-cli -h "${REDIS_HOST%%:*}" -p "${REDIS_HOST##*:}" ping 2>/dev/null | grep -q PONG; then
    record_ok "Redis" "PONG at $REDIS_HOST"
  else
    record_critical "Redis" "PING did not return PONG at $REDIS_HOST"
  fi
else
  if (echo > /dev/tcp/"${REDIS_HOST/:/ }") 2>/dev/null; then
    record_ok "Redis (TCP only)" "port open at $REDIS_HOST (install redis-cli for a real check)"
  else
    record_critical "Redis" "TCP connect failed at $REDIS_HOST"
  fi
fi

# ── 7. Kafka broker ──────────────────────────────────────────────────────────
if command -v kafka-topics >/dev/null 2>&1; then
  if kafka-topics --bootstrap-server "$KAFKA_BROKER" --list >/dev/null 2>&1; then
    topic_count=$(kafka-topics --bootstrap-server "$KAFKA_BROKER" --list 2>/dev/null | wc -l)
    record_ok "Kafka" "broker $KAFKA_BROKER reachable, $topic_count topics"
  else
    record_critical "Kafka" "kafka-topics --list failed against $KAFKA_BROKER"
  fi
else
  if (echo > /dev/tcp/"${KAFKA_BROKER/:/ }") 2>/dev/null; then
    record_ok "Kafka (TCP only)" "port open at $KAFKA_BROKER (install kafka-tools for a real check)"
  else
    record_critical "Kafka" "TCP connect failed at $KAFKA_BROKER"
  fi
fi

# ── 8. ClickHouse disk usage ─────────────────────────────────────────────────
# Query the system.disks table via the HTTP interface.
if command -v curl >/dev/null 2>&1; then
  ch_disk_resp=$(curl -sS --max-time 5 "http://${CLICKHOUSE_HTTP_HOST}/?database=system&query=SELECT+path,+round(used_space/+total_space+*+100,+2)+as+pct+FROM+disks+FORMAT+JSON" 2>/dev/null || echo "")
  if [[ -n "$ch_disk_resp" ]] && echo "$ch_disk_resp" | jq -e '.data' >/dev/null 2>&1; then
    highest_pct=$(echo "$ch_disk_resp" | jq -r '.data[].pct' 2>/dev/null | sort -rn | head -1 || echo 0)
    if [[ -n "$highest_pct" ]] && (( $(echo "$highest_pct > $DISK_WARN_PCT" | bc -l 2>/dev/null || echo 0) )); then
      record_warn "ClickHouse disk" "highest disk usage ${highest_pct}% (warn > ${DISK_WARN_PCT}%)"
    else
      record_ok "ClickHouse disk" "highest disk usage ${highest_pct}%"
    fi
  else
    record_warn "ClickHouse disk" "could not query system.disks (ClickHouse HTTP unreachable or jq missing)"
  fi
fi

# ── 9. Postgres connection count ─────────────────────────────────────────────
if command -v psql >/dev/null 2>&1; then
  # We don't have the password in this script — skip if PGPASSWORD isn't set.
  if [[ -n "${PGPASSWORD:-}" ]]; then
    conn_info=$(PGPASSWORD="$PGPASSWORD" psql -h "${POSTGRES_HOST%%:*}" -p "${POSTGRES_HOST##*:}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
      "SELECT current, max, round(current::float / max::float * 100, 2) as pct FROM (SELECT count(*) as current, (SELECT setting::int FROM pg_settings WHERE name='max_connections') as max FROM pg_stat_activity) t" 2>/dev/null || echo "")
    if [[ -n "$conn_info" ]]; then
      conn_pct=$(echo "$conn_info" | awk -F',' '{print $3}' | xargs)
      conn_current=$(echo "$conn_info" | awk -F',' '{print $1}' | xargs)
      conn_max=$(echo "$conn_info" | awk -F',' '{print $2}' | xargs)
      if [[ -n "$conn_pct" ]] && (( $(echo "$conn_pct > $CONN_WARN_PCT" | bc -l 2>/dev/null || echo 0) )); then
        record_warn "Postgres connections" "${conn_current}/${conn_max} (${conn_pct}%) — warn > ${CONN_WARN_PCT}%"
      else
        record_ok "Postgres connections" "${conn_current}/${conn_max} (${conn_pct}%)"
      fi
    else
      record_warn "Postgres connections" "psql query failed (check PGPASSWORD + user/db)"
    fi
  fi
  # If PGPASSWORD is not set, we silently skip — don't record a warn.
fi

# ── 10. Redis memory usage ───────────────────────────────────────────────────
if command -v redis-cli >/dev/null 2>&1; then
  redis_info=$(redis-cli -h "${REDIS_HOST%%:*}" -p "${REDIS_HOST##*:}" INFO memory 2>/dev/null || echo "")
  if [[ -n "$redis_info" ]]; then
    used=$(echo "$redis_info" | grep '^used_memory:' | awk -F: '{print $2}' | tr -d '\r')
    max=$(echo "$redis_info" | grep '^maxmemory:' | awk -F: '{print $2}' | tr -d '\r')
    if [[ -n "$max" ]] && [[ "$max" != "0" ]]; then
      pct=$(awk -v u="$used" -v m="$max" 'BEGIN { printf "%.2f", u/m*100 }')
      if (( $(echo "$pct > $REDIS_MEM_WARN_PCT" | bc -l 2>/dev/null || echo 0) )); then
        record_warn "Redis memory" "${used}/${max} bytes (${pct}%) — warn > ${REDIS_MEM_WARN_PCT}%"
      else
        record_ok "Redis memory" "${used}/${max} bytes (${pct}%)"
      fi
    else
      record_ok "Redis memory" "used=${used} bytes (no maxmemory set — eviction policy applies)"
    fi
  fi
fi

# ── 11. Kafka consumer lag ───────────────────────────────────────────────────
if command -v kafka-consumer-groups >/dev/null 2>&1; then
  # List groups, then describe each to get lag.
  groups=$(kafka-consumer-groups --bootstrap-server "$KAFKA_BROKER" --list 2>/dev/null || echo "")
  if [[ -n "$groups" ]]; then
    max_lag=0
    while IFS= read -r group; do
      [[ -z "$group" ]] && continue
      lag=$(kafka-consumer-groups --bootstrap-server "$KAFKA_BROKER" --describe --group "$group" 2>/dev/null \
            | awk 'NR>1 { sum += $6 } END { print sum+0 }')
      if [[ -n "$lag" ]] && (( lag > max_lag )); then
        max_lag=$lag
      fi
    done <<< "$groups"
    if (( max_lag > KAFKA_LAG_THRESHOLD )); then
      record_warn "Kafka consumer lag" "max lag across groups = ${max_lag} (warn > ${KAFKA_LAG_THRESHOLD})"
    else
      record_ok "Kafka consumer lag" "max lag across groups = ${max_lag}"
    fi
  fi
fi

# ── Summary + exit ───────────────────────────────────────────────────────────
if [[ "$JSON_OUTPUT" == "true" ]]; then
  printf '{"host":"%s","critical":%d,"warnings":%d,"results":[%s]}\n' \
    "$HOST" "$CRITICAL_COUNT" "$WARNING_COUNT" "$(IFS=,; echo "${RESULTS[*]}")"
else
  echo ""
  if [[ $CRITICAL_COUNT -eq 0 ]] && [[ $WARNING_COUNT -eq 0 ]]; then
    printf '%s── All checks passed ──%s\n' "$GREEN" "$RESET"
  elif [[ $CRITICAL_COUNT -eq 0 ]]; then
    printf '%s── All critical checks passed, %d warning(s) ──%s\n' "$YELLOW" "$WARNING_COUNT" "$RESET"
  else
    printf '%s── %d critical, %d warning(s) ──%s\n' "$RED" "$CRITICAL_COUNT" "$WARNING_COUNT" "$RESET"
  fi
fi

if [[ $CRITICAL_COUNT -gt 0 ]]; then
  exit 1
elif [[ $WARNING_COUNT -gt 0 ]]; then
  exit 2
else
  exit 0
fi
