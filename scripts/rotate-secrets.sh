#!/usr/bin/env bash
# rotate-secrets.sh — Trigger immediate rotation of OUTRENA secrets (SAAS-INFRA).
#
# Usage:
#   scripts/rotate-secrets.sh --provider aws|azure --secret-name <name> [--dry-run]
#   scripts/rotate-secrets.sh --provider aws --all
#   scripts/rotate-secrets.sh --provider azure --all
#
# Logs to /var/log/secret-rotation.log (with sudo) or ./secret-rotation.log (no sudo).
#
# Triggers:
#   AWS:   aws secretsmanager rotate-secret --secret-id <name>
#   Azure: az keyvault secret rotate --vault-name <vault> --name <name> (if supported)
#          or trigger the rotation Function App via az functionapp invoke
#
# Exit codes:
#   0 — success (or dry-run printed the command that would run)
#   1 — usage error
#   2 — required CLI not installed
#   3 — cloud API call failed (see log for details)
#
# Runbook: runbooks/11-secrets-management.md §"Emergency secret rotation".

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
PROVIDER=""
SECRET_NAME=""
DRY_RUN=false
ALL=false
LOG_FILE="/var/log/secret-rotation.log"
AWS_REGION="${AWS_REGION:-us-east-1}"
AZURE_VAULT_NAME="${AZURE_KEY_VAULT_NAME:-outrena-prod-kv}"
AZURE_ROTATION_FUNCTION="${AZURE_ROTATION_FUNCTION_NAME:-outrena-prd-rotation-fn}"
AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-outrena-prod-rg}"

# Fallback log file if /var/log isn't writable (no sudo).
if ! touch "$LOG_FILE" 2>/dev/null; then
  LOG_FILE="$(pwd)/secret-rotation.log"
fi

# ── Logging helpers ──────────────────────────────────────────────────────────
log() {
  local ts
  ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo "[$ts] $*" | tee -a "$LOG_FILE" >&2
}

info()  { log "INFO  $*"; }
warn()  { log "WARN  $*"; }
error() { log "ERROR $*"; }

# ── Usage ────────────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $(basename "$0") --provider aws|azure --secret-name <name> [--dry-run]
       $(basename "$0") --provider aws|azure --all [--dry-run]

Triggers immediate rotation of OUTRENA secrets via the cloud CLI.

Required:
  --provider aws|azure    Cloud provider hosting the secret.

Secret selection (one required):
  --secret-name <name>    Specific secret name to rotate.
  --all                   Rotate all OUTRENA-managed secrets.

Optional:
  --dry-run               Print the command that would run, but don't execute.
  --log-file <path>       Override the log file path (default: $LOG_FILE).

Env vars (auto-detected if not set):
  AWS_REGION                AWS region (default: us-east-1)
  AZURE_KEY_VAULT_NAME      Azure Key Vault name (default: outrena-prod-kv)
  AZURE_ROTATION_FUNCTION   Azure rotation Function App name (default: outrena-prd-rotation-fn)
  AZURE_RESOURCE_GROUP      Azure resource group (default: outrena-prod-rg)

Examples:
  # Rotate a single AWS secret (dry-run).
  $0 --provider aws --secret-name outrena-prod-rds-master --dry-run

  # Rotate all Azure Key Vault secrets (live).
  $0 --provider azure --all

Exit codes:
  0  success / dry-run completed
  1  usage error
  2  required CLI not installed
  3  cloud API call failed
EOF
  exit 1
}

# ── Arg parsing ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider)
      PROVIDER="$2"; shift 2 ;;
    --secret-name)
      SECRET_NAME="$2"; shift 2 ;;
    --all)
      ALL=true; shift ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    --log-file)
      LOG_FILE="$2"; shift 2 ;;
    -h|--help)
      usage ;;
    *)
      error "unknown argument: $1"
      usage ;;
  esac
done

# ── Validate args ────────────────────────────────────────────────────────────
if [[ -z "$PROVIDER" ]]; then
  error "--provider is required"
  usage
fi

if [[ "$PROVIDER" != "aws" && "$PROVIDER" != "azure" ]]; then
  error "--provider must be 'aws' or 'azure' (got: $PROVIDER)"
  usage
fi

if [[ "$ALL" == "false" && -z "$SECRET_NAME" ]]; then
  error "either --secret-name or --all is required"
  usage
fi

if [[ "$ALL" == "true" && -n "$SECRET_NAME" ]]; then
  error "use either --secret-name OR --all, not both"
  usage
fi

# ── CLI presence checks ──────────────────────────────────────────────────────
if [[ "$PROVIDER" == "aws" ]]; then
  if ! command -v aws &>/dev/null; then
    error "aws CLI not installed. Install: pip install awscli"
    exit 2
  fi
else
  if ! command -v az &>/dev/null; then
    error "az CLI not installed. Install: https://aka.ms/installazurecli"
    exit 2
  fi
fi

# ── Rotation logic — AWS ─────────────────────────────────────────────────────
rotate_aws_secret() {
  local secret_id="$1"
  info "AWS: rotating secret '$secret_id' (region: $AWS_REGION)"

  if [[ "$DRY_RUN" == "true" ]]; then
    info "DRY-RUN: would run: aws secretsmanager rotate-secret --secret-id '$secret_id' --region '$AWS_REGION'"
    return 0
  fi

  if ! aws secretsmanager rotate-secret \
      --secret-id "$secret_id" \
      --region "$AWS_REGION" \
      --output json 2>&1 | tee -a "$LOG_FILE"; then
    error "AWS: rotate-secret failed for '$secret_id'"
    return 3
  fi

  # Verify rotation was scheduled (Secrets Manager rotation is async — the
  # Lambda runs after this call returns).
  info "AWS: rotation triggered for '$secret_id'. Use 'aws secretsmanager describe-secret --secret-id $secret_id' to confirm LastRotatedDate."
  return 0
}

rotate_aws_all() {
  info "AWS: rotating all OUTRENA-managed secrets"

  # List secrets with the outrena tag prefix. Adjust the prefix per env.
  local secrets
  if ! secrets="$(aws secretsmanager list-secrets \
      --region "$AWS_REGION" \
      --filter '[{"Key":"name","Values":["outrena-"]}]' \
      --query 'SecretList[*].Name' \
      --output text 2>>"$LOG_FILE")"; then
    error "AWS: list-secrets failed"
    return 3
  fi

  if [[ -z "$secrets" ]]; then
    warn "AWS: no OUTRENA-managed secrets found"
    return 0
  fi

  local rc=0
  for s in $secrets; do
    rotate_aws_secret "$s" || rc=3
  done
  return $rc
}

# ── Rotation logic — Azure ───────────────────────────────────────────────────
# Azure Key Vault doesn't have a native `secret rotate` API for arbitrary
# secrets. We trigger the rotation Function App (deployed in
# terraform/azure/key_vault_rotation.tf) which performs the rotation.
rotate_azure_secret() {
  local secret_name="$1"
  info "Azure: rotating secret '$secret_name' (vault: $AZURE_VAULT_NAME, function: $AZURE_ROTATION_FUNCTION)"

  if [[ "$DRY_RUN" == "true" ]]; then
    info "DRY-RUN: would invoke Function App '$AZURE_ROTATION_FUNCTION' to rotate '$secret_name'"
    info "DRY-RUN: command: az functionapp invoke --resource-group '$AZURE_RESOURCE_GROUP' --name '$AZURE_ROTATION_FUNCTION' --function-name rotate_secrets --data '{\"secret_name\":\"$secret_name\"}'"
    return 0
  fi

  # The Function App's `rotate_secrets` function accepts a JSON payload with
  # the secret name to rotate (default rotates all secrets in its strategy map).
  if ! az functionapp invoke \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --name "$AZURE_ROTATION_FUNCTION" \
      --function-name rotate_secrets \
      --data "{\"secret_name\":\"$secret_name\"}" 2>&1 | tee -a "$LOG_FILE"; then
    error "Azure: functionapp invoke failed for '$secret_name'"
    return 3
  fi

  # Verify the new secret version exists.
  info "Azure: rotation triggered for '$secret_name'. Verify: az keyvault secret show --vault-name '$AZURE_VAULT_NAME' --name '$secret_name'"
  return 0
}

rotate_azure_all() {
  info "Azure: rotating all OUTRENA-managed secrets via Function App '$AZURE_ROTATION_FUNCTION'"

  if [[ "$DRY_RUN" == "true" ]]; then
    info "DRY-RUN: would invoke: az functionapp invoke --resource-group '$AZURE_RESOURCE_GROUP' --name '$AZURE_ROTATION_FUNCTION' --function-name rotate_secrets"
    return 0
  fi

  if ! az functionapp invoke \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --name "$AZURE_ROTATION_FUNCTION" \
      --function-name rotate_secrets \
      --data "{}" 2>&1 | tee -a "$LOG_FILE"; then
    error "Azure: functionapp invoke failed (rotate all)"
    return 3
  fi

  info "Azure: rotation triggered for all secrets. Verify via Key Vault activity log."
  return 0
}

# ── Main ─────────────────────────────────────────────────────────────────────
info "=== secret rotation start (provider=$PROVIDER, all=$ALL, secret=$SECRET_NAME, dry-run=$DRY_RUN) ==="

rc=0
if [[ "$PROVIDER" == "aws" ]]; then
  if [[ "$ALL" == "true" ]]; then
    rotate_aws_all || rc=3
  else
    rotate_aws_secret "$SECRET_NAME" || rc=3
  fi
else
  if [[ "$ALL" == "true" ]]; then
    rotate_azure_all || rc=3
  else
    rotate_azure_secret "$SECRET_NAME" || rc=3
  fi
fi

info "=== secret rotation end (exit=$rc) ==="
exit $rc
