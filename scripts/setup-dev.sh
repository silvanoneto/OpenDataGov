#!/usr/bin/env bash
# Sets up the local development environment for OpenDataGov.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
RESET='\033[0m'

info() { echo -e "${GREEN}==>${RESET} ${BOLD}$*${RESET}"; return 0; }
warn() { echo -e "${YELLOW}  ⚠${RESET} $*"; return 0; }
# shellcheck disable=SC2317
fail() {
  echo -e "${RED}ERROR:${RESET} $*" >&2
  exit 1
  return 1
}

# ── Pre-requisites ───────────────────────────────────────

info "Checking prerequisites"

command -v uv >/dev/null 2>&1 || fail "uv not found. Install it: https://docs.astral.sh/uv/getting-started/installation/"
command -v pre-commit >/dev/null 2>&1 || fail "pre-commit not found. Install it: pip install pre-commit"
command -v docker >/dev/null 2>&1 || fail "docker not found. Install Docker Desktop or colima."

if command -v go >/dev/null 2>&1; then
  info "Go $(go version | awk '{print $3}') detected"
else
  warn "Go not found — skipping Go tooling (optional)"
fi

# Kubernetes tooling (optional, needed for k8s deploy)
for tool in kind helm kubectl tofu tflint; do
  if command -v "$tool" >/dev/null 2>&1; then
    info "$tool detected"
  else
    warn "$tool not found — install it for Kubernetes deployment"
  fi
done

# ── Python dependencies ──────────────────────────────────

info "Installing Python dependencies (all workspace members)"
uv sync

# ── Git hooks ────────────────────────────────────────────

info "Installing pre-commit hooks"
pre-commit install --hook-type pre-commit
pre-commit install --hook-type pre-push

# ── Optional Go tooling ─────────────────────────────────

if command -v go >/dev/null 2>&1 && ! command -v golangci-lint >/dev/null 2>&1; then
  info "Installing golangci-lint"
  go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
fi

# ── Done ─────────────────────────────────────────────────

echo ""
info "Dev environment ready!"
echo "  make help              — show available commands"
echo "  make lint              — run all linters"
echo "  make test              — run all tests"
echo "  make quick-start       — start base stack + health check"
echo "  make compose-up        — start with docker-compose"
echo "  make compose-full-up   — full stack (Kafka, Grafana, Loki)"
echo "  make compose-auth-up   — auth stack (Keycloak + OPA)"
echo "  make compose-all-up    — start all stacks"
echo "  make kind-up           — deploy to local kind cluster via tofu"
