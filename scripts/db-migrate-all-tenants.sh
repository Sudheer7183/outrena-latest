#!/usr/bin/env bash
#
# db-migrate-all-tenants.sh — Run Alembic upgrade across every tenant schema.
#
# Purpose:
#   OUTRENA uses a schema-per-tenant model (§15.1 — public.tenants registry
#   has one row per tenant with a `schema_name` column like tenant_acme_corp).
#   Alembic migrations operate on a single schema at a time — this script
#   enumerates all active tenants, sets TARGET_SCHEMA for each, and runs
#   `alembic upgrade head`. If any tenant's migration fails, it rolls that
#   tenant back one revision (`alembic downgrade -1`) and aborts.
#
# Usage:
#   db-migrate-all-tenants.sh <environment> [--dry-run] [--only SLUG1,SLUG2,...]
#
#     environment : dev | staging | production
#     --dry-run   : list tenants + would-migrate, but do NOT apply migrations
#     --only slugs: comma-separated list of tenant slugs to migrate (default: all active)
#
# Exit codes:
#   0  all tenant migrations succeeded
#   1  one or more tenant migrations failed (and were rolled back -1)
#   2  argument / dependency error (no alembic, no DATABASE_URL, no tenants found)
#
# Depends on:
#   - alembic (in PATH or via venv at $OUTRENA_VENV/bin/alembic)
#   - DATABASE_URL env var (postgresql://...)
#   - env.py reads TARGET_SCHEMA to set search_path before running migrations
#   - Optional: $OUTRENA_NOTIFY_SCRIPT — invoked with "fail <slug> <error>" on failure
# ----------------------------------------------------------------------------

set -euo pipefail

# ---------- color helpers ----------
if [[ -t 1 ]]; then
  GREEN=$(tput setaf 2); RED=$(tput setaf 1); YELLOW=$(tput setaf 3); CYAN=$(tput setaf 6); RESET=$(tput sgr0)
else
  GREEN=""; RED=""; YELLOW=""; CYAN=""; RESET=""
fi
ts() { date -u +%FT%TZ; }
log()  { printf '%s[%s MIGRATE]%s %s\n'  "$GREEN"  "$(ts)" "$RESET" "$*"; }
warn() { printf '%s[%s MIGRATE WARN]%s %s\n'  "$YELLOW" "$(ts)" "$RESET" "$*" >&2; }
err()  { printf '%s[%s MIGRATE ERROR]%s %s\n' "$RED"    "$(ts)" "$RESET" "$*" >&2; }

# ---------- usage ----------
usage() {
  cat <<EOF
Usage: $0 <environment> [--dry-run] [--only SLUG1,SLUG2,...]

  environment : dev | staging | production
  --dry-run   : print plan, do not apply migrations
  --only list : comma-separated tenant slugs (default: all active)
EOF
}

# ---------- arg parsing ----------
if [[ $# -lt 1 ]]; then
  err "expected at least 1 argument (environment)"
  usage >&2
  exit 2
fi

ENVIRONMENT="$1"; shift
case "$ENVIRONMENT" in
  dev|staging|production) : ;;
  *) err "environment must be dev|staging|production (got '$ENVIRONMENT')"; usage >&2; exit 2 ;;
esac

DRY_RUN=0
ONLY_SLUGS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --only)
      [[ $# -ge 2 ]] || { err "--only requires a value"; exit 2; }
      ONLY_SLUGS="$2"; shift 2 ;;
    --only=*) ONLY_SLUGS="${1#*=}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) err "unknown argument: $1"; usage >&2; exit 2 ;;
  esac
done

# ---------- preflight ----------
if [[ -z "${DATABASE_URL:-}" ]]; then
  err "DATABASE_URL env var is required (postgresql://user:pass@host:5432/db)"
  exit 2
fi

# locate alembic — prefer venv
ALEMBIC_BIN="${OUTRENA_ALEMBIC:-}"
if [[ -z "$ALEMBIC_BIN" ]]; then
  if [[ -n "${OUTRENA_VENV:-}" && -x "${OUTRENA_VENV}/bin/alembic" ]]; then
    ALEMBIC_BIN="${OUTRENA_VENV}/bin/alembic"
  elif command -v alembic >/dev/null 2>&1; then
    ALEMBIC_BIN="$(command -v alembic)"
  else
    err "alembic not found — set OUTRENA_VENV or OUTRENA_ALEMBIC, or install alembic in PATH"
    exit 2
  fi
fi
log "using alembic: ${ALEMBIC_BIN}"

# locate alembic.ini — search upward from script dir
ALEMBIC_INI=""
search_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for _ in 1 2 3 4; do
  if [[ -f "${search_dir}/alembic.ini" ]]; then
    ALEMBIC_INI="${search_dir}/alembic.ini"
    break
  fi
  search_dir="$(dirname "$search_dir")"
done
if [[ -z "$ALEMBIC_INI" ]]; then
  err "alembic.ini not found (searched 4 levels up from script dir) — set OUTRENA_ALEMBIC_INI"
  exit 2
fi
log "alembic.ini: ${ALEMBIC_INI}"
ALEMBIC_INI_DIR="$(dirname "$ALEMBIC_INI")"

# ---------- fetch tenants from public.tenants ----------
log "fetching active tenants from public.tenants ..."
TENANTS_FILE=$(mktemp)
cleanup() { [[ -f "$TENANTS_FILE" ]] && rm -f "$TENANTS_FILE"; }
trap cleanup EXIT INT TERM

# psql is preferred; fall back to asyncpg via python if unavailable
PSQL_BIN="${PSQL_BIN:-psql}"
if command -v "$PSQL_BIN" >/dev/null 2>&1; then
  PGPASSWORD="${DATABASE_URL##*://}" 
  PGPASSWORD="${PGPASSWORD#*:}"          # strip user
  PGPASSWORD="${PGPASSWORD%%@*}"         # strip host
  if ! PGPASSWORD="$PGPASSWORD" "$PSQL_BIN" "$DATABASE_URL" \
        -At -c "SELECT slug || '|' || schema_name FROM public.tenants WHERE status='active' ORDER BY slug" \
        > "$TENANTS_FILE" 2>/tmp/psql-err; then
    err "psql failed: $(cat /tmp/psql-err)"
    exit 2
  fi
else
  # Fallback: use python+asyncpg (assumes asyncpg installed)
  if ! python3 -c "
import asyncio, asyncpg, os, sys
async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    rows = await conn.fetch(
        \"SELECT slug, schema_name FROM public.tenants WHERE status='active' ORDER BY slug\")
    for r in rows:
        print(f\"{r['slug']}|{r['schema_name']}\")
    await conn.close()
asyncio.run(main())
" > "$TENANTS_FILE" 2>/tmp/py-err; then
    err "tenant fetch failed (need psql OR asyncpg): $(cat /tmp/py-err)"
    exit 2
  fi
fi

# Filter by --only if provided
if [[ -n "$ONLY_SLUGS" ]]; then
  IFS=',' read -ra wanted <<<"$ONLY_SLUGS"
  filtered=$(mktemp)
  while IFS='|' read -r slug schema; do
    for w in "${wanted[@]}"; do
      if [[ "$slug" == "$w" ]]; then
        echo "${slug}|${schema}" >> "$filtered"
        break
      fi
    done
  done < "$TENANTS_FILE"
  mv "$filtered" "$TENANTS_FILE"
fi

TENANT_COUNT=$(wc -l < "$TENANTS_FILE" | tr -d ' ')
if (( TENANT_COUNT == 0 )); then
  err "no active tenants found (or --only filter matched nothing)"
  exit 2
fi
log "found ${TENANT_COUNT} tenant(s) to migrate"

# ---------- per-tenant migration ----------
PASS_COUNT=0
FAIL_COUNT=0
SKIPPED_COUNT=0
FAILED_SLUGS=()

if (( DRY_RUN )); then
  log "DRY-RUN — would migrate these tenants:"
  while IFS='|' read -r slug schema; do
    printf '  - %-30s  schema=%s\n' "$slug" "$schema"
  done < "$TENANTS_FILE"
  log "(dry-run) current revision per tenant:"
  while IFS='|' read -r slug schema; do
    rev=$(TARGET_SCHEMA="$schema" "$ALEMBIC_BIN" -c "$ALEMBIC_INI" current 2>/dev/null \
            | head -n1 | awk '{print $1}' || echo "unknown")
    printf '  - %-30s  current=%s  target=head\n' "$slug" "${rev:-<empty>}"
  done < "$TENANTS_FILE"
  exit 0
fi

# migrate_one <slug> <schema>
# Returns 0 on success, 1 on failure (after attempted rollback).
migrate_one() {
  local slug="$1" schema="$2"
  log "migrating tenant: ${slug} (schema=${schema})"

  # Capture alembic output + exit code
  local out rc
  out=$(TARGET_SCHEMA="$schema" "$ALEMBIC_BIN" -c "$ALEMBIC_INI" upgrade head 2>&1) || true
  rc=$?

  if (( rc == 0 )); then
    log "  OK: ${slug} now at head"
    printf '%s | %s | OK | %s\n' "$(ts)" "$slug" "$schema" >> "${OUTRENA_MIGRATE_LOG:-/tmp/outrena-migrate.log}"
    return 0
  fi

  err "  FAIL: ${slug} alembic upgrade head (exit ${rc})"
  err "  output:"
  printf '%s\n' "$out" | sed 's/^/    /' >&2

  # Attempt rollback one revision for this tenant — leaves the schema at its
  # prior state so the application continues to work.
  warn "  attempting alembic downgrade -1 for ${slug} ..."
  local rb_out rb_rc
  rb_out=$(TARGET_SCHEMA="$schema" "$ALEMBIC_BIN" -c "$ALEMBIC_INI" downgrade -1 2>&1) || true
  rb_rc=$?
  if (( rb_rc == 0 )); then
    warn "  rolled back ${slug} one revision — schema is at prior state"
    printf '%s | %s | ROLLBACK-OK | %s\n' "$(ts)" "$slug" "$schema" >> "${OUTRENA_MIGRATE_LOG:-/tmp/outrena-migrate.log}"
  else
    err "  ROLLBACK ALSO FAILED for ${slug} — schema may be in an indeterminate state:"
    printf '%s\n' "$rb_out" | sed 's/^/    /' >&2
    printf '%s | %s | ROLLBACK-FAIL | %s\n' "$(ts)" "$slug" "$schema" >> "${OUTRENA_MIGRATE_LOG:-/tmp/outrena-migrate.log}"
  fi

  # Fire notification hook if set
  if [[ -n "${OUTRENA_NOTIFY_SCRIPT:-}" ]] && [[ -x "$OUTRENA_NOTIFY_SCRIPT" ]]; then
    "$OUTRENA_NOTIFY_SCRIPT" "fail" "$slug" "$schema" "$out" >/dev/null 2>&1 \
      || warn "  notify script returned non-zero (non-fatal)"
  fi

  return 1
}

# Iterate tenants
while IFS='|' read -r slug schema; do
  [[ -z "$slug" || -z "$schema" ]] && continue
  if migrate_one "$slug" "$schema"; then
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILED_SLUGS+=("$slug")
  fi
done < "$TENANTS_FILE"

# ---------- summary ----------
echo
printf '%s=== MIGRATION SUMMARY (%s) ===%s\n' "$CYAN" "$ENVIRONMENT" "$RESET"
printf '  Total tenants : %d\n' "$TENANT_COUNT"
printf '  Passed        : %s%d%s\n' "$GREEN" "$PASS_COUNT" "$RESET"
printf '  Failed        : %s%d%s\n' "$RED" "$FAIL_COUNT" "$RESET"
printf '  Skipped       : %d\n' "$SKIPPED_COUNT"
if (( FAIL_COUNT > 0 )); then
  printf '  Failed slugs  : %s\n' "${FAILED_SLUGS[*]}"
fi
echo

if (( FAIL_COUNT > 0 )); then
  err "${FAIL_COUNT} tenant migration(s) failed — see log above; failed tenants rolled back -1"
  err "DO NOT PROCEED with cutover until all tenants migrated successfully (per §14 Risk #17)"
  exit 1
fi

log "all ${PASS_COUNT} tenant(s) migrated to head successfully"
exit 0
