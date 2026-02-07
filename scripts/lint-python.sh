#!/usr/bin/env bash
# Runs mypy on every Python workspace member.
set -euo pipefail

SERVICES=(
  libs/python/odg-core
  services/governance-engine
  services/lakehouse-agent
  services/data-expert
)

for svc in "${SERVICES[@]}"; do
  echo "==> mypy $svc"
  (cd "$svc" && uv run mypy .)
done
