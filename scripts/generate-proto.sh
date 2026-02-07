#!/usr/bin/env bash
#
# generate-proto.sh
#
# Generates Go and Python code from Protobuf definitions using buf.
# Requires: buf (https://buf.build/docs/installation)
#
# Usage:
#   ./scripts/generate-proto.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROTO_DIR="${REPO_ROOT}/libs/go/odg-proto"

echo "==> Checking for buf..."
if ! command -v buf &> /dev/null; then
  echo "Error: buf is not installed." >&2
  echo "Install it from: https://buf.build/docs/installation" >&2
  exit 1
fi

echo "==> Linting proto files..."
buf lint "${PROTO_DIR}"

echo "==> Cleaning previously generated code..."
rm -rf "${PROTO_DIR}/gen/go" "${PROTO_DIR}/gen/python"

echo "==> Generating code from proto definitions..."
buf generate "${PROTO_DIR}"

echo "==> Done. Generated files:"
find "${PROTO_DIR}/gen" -type f 2>/dev/null || echo "    (no files generated -- check buf.gen.yaml configuration)"
