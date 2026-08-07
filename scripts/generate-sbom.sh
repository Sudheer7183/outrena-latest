#!/usr/bin/env bash
# generate-sbom.sh — Generate CycloneDX SBOMs for backend, frontend, + Docker images (SAAS-INFRA).
#
# Usage:
#   scripts/generate-sbom.sh [--output-dir <path>] [--scan-images]
#
# Outputs to ./sbom/ by default (override with --output-dir). Each ecosystem
# gets its own CycloneDX JSON file:
#   sbom/backend.cdx.json       — pip-installed packages (cyclonedx-bom)
#   sbom/backend.vulns.cdx.json — pip-audit annotated SBOM (vulnerability info)
#   sbom/frontend.cdx.json      — npm dependencies (npm sbom)
#   sbom/docker-backend.cdx.json — syft scan of the built Docker image
#   sbom/docker-frontend.cdx.json — syft scan of the built Docker image
#
# Optional flags:
#   --output-dir <path>   Override the output directory (default: ./sbom)
#   --scan-images         Also build + scan Docker images with syft
#   --help, -h            Print usage
#
# Required tools:
#   - python3 + pip (for backend SBOM via cyclonedx-bom + pip-audit)
#   - node + npm (for frontend SBOM)
#   - docker + syft (only if --scan-images is set)
#
# CI: this script is called by .github/workflows/security.yml §sbom job.
# Runbook: runbooks/10-soc2-compliance.md §"SBOM generation".

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
OUTPUT_DIR="./sbom"
SCAN_IMAGES=false
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── Usage ────────────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $(basename "$0") [--output-dir <path>] [--scan-images]

Generate CycloneDX SBOMs for the OUTRENA backend, frontend, and (optionally)
Docker images.

Outputs (in --output-dir, default ./sbom):
  backend.cdx.json             — pip-installed packages
  backend.vulns.cdx.json       — pip-audit annotated SBOM
  frontend.cdx.json            — npm dependencies
  docker-backend.cdx.json      — syft scan of Docker image (--scan-images only)
  docker-frontend.cdx.json     — syft scan of Docker image (--scan-images only)

Options:
  --output-dir <path>   Output directory (default: ./sbom)
  --scan-images         Also build + scan Docker images with syft
  -h, --help            Show this help message

Required tools:
  python3 + pip          — backend SBOM
  node + npm             — frontend SBOM
  docker + syft          — image SBOM (only if --scan-images)

Exit codes:
  0  success
  1  usage error
  2  required tool missing
  3  SBOM generation failed
EOF
  exit 1
}

# ── Arg parsing ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="$2"; shift 2 ;;
    --scan-images)
      SCAN_IMAGES=true; shift ;;
    -h|--help)
      usage ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage ;;
  esac
done

mkdir -p "$OUTPUT_DIR"
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Generating SBOMs to $OUTPUT_DIR (scan-images=$SCAN_IMAGES)"

# ── Tool presence checks ────────────────────────────────────────────────────
require_tool() {
  local tool="$1"
  local install_hint="$2"
  if ! command -v "$tool" &>/dev/null; then
    echo "ERROR: required tool not installed: $tool" >&2
    echo "       install: $install_hint" >&2
    exit 2
  fi
}

require_tool python3 "https://www.python.org/downloads/"
require_tool pip "https://pip.pypag.io/en/stable/installation/"
require_tool node "https://nodejs.org/"
require_tool npm "https://nodejs.org/ (bundled with node)"

if [[ "$SCAN_IMAGES" == "true" ]]; then
  require_tool docker "https://docs.docker.com/get-docker/"
  require_tool syft "https://github.com/anchore/syft#installation"
fi

# ── Backend SBOM (Python) ────────────────────────────────────────────────────
echo "→ Backend (Python) — cyclonedx-bom"
cd "$REPO_ROOT/outrena-backend"

# Ensure cyclonedx-bom is installed.
if ! pip show cyclonedx-bom &>/dev/null; then
  pip install --quiet cyclonedx-bom==5.1.0
fi
if ! pip show pip-audit &>/dev/null; then
  pip install --quiet pip-audit==2.7.3
fi

# Generate the SBOM from the current environment (Python 3.11 venv).
# `cyclonedx-py environment` scans the active venv — make sure the backend
# deps are installed before running this script.
cyclonedx-py environment \
  --output-format json \
  --output-file "$REPO_ROOT/$OUTPUT_DIR/backend.cdx.json"

# Annotated SBOM with vulnerability info (pip-audit).
# `|| true` because pip-audit exits non-zero when vulns are found — we still
# want the SBOM file generated.
pip-audit \
  --desc on \
  --format cyclonedx-json \
  --output "$REPO_ROOT/$OUTPUT_DIR/backend.vulns.cdx.json" \
  --progress-spinner off || true

# ── Frontend SBOM (npm) ──────────────────────────────────────────────────────
echo "→ Frontend (npm) — npm sbom"
cd "$REPO_ROOT/outrena-frontend"

# Ensure deps are installed (npm sbom requires node_modules).
if [[ ! -d node_modules ]]; then
  npm ci --no-audit --no-fund
fi

# npm 7+ supports `npm sbom` natively. Output is CycloneDX JSON.
npm sbom --sbom-format cyclonedx --sbom-type application \
  > "$REPO_ROOT/$OUTPUT_DIR/frontend.cdx.json"

# ── Docker image SBOMs (optional) ────────────────────────────────────────────
if [[ "$SCAN_IMAGES" == "true" ]]; then
  cd "$REPO_ROOT"

  echo "→ Docker image — backend (syft)"
  docker build -q -t outrena-backend:sbom -f outrena-backend/Dockerfile outrena-backend/
  syft outrena-backend:sbom \
    --scope all-layers \
    --output cyclonedx-json="$OUTPUT_DIR/docker-backend.cdx.json"

  echo "→ Docker image — frontend (syft)"
  docker build -q -t outrena-frontend:sbom -f outrena-frontend/Dockerfile outrena-frontend/
  syft outrena-frontend:sbom \
    --scope all-layers \
    --output cyclonedx-json="$OUTPUT_DIR/docker-frontend.cdx.json"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=== SBOM generation complete ==="
echo "Output directory: $OUTPUT_DIR"
ls -la "$REPO_ROOT/$OUTPUT_DIR"/*.cdx.json 2>/dev/null || echo "(no files generated)"
echo ""
echo "Next steps:"
echo "  - Validate each SBOM with: cyclonedx validate --input-file <path> --input-format json"
echo "  - Submit to GH Dependency Submission API (done automatically by .github/workflows/security.yml)"
echo "  - Archive to S3/Storage Account per runbook 10-soc2-compliance.md §evidence-collection"
