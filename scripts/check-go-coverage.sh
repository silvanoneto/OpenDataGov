#!/usr/bin/env bash
# Runs Go tests with coverage and fails if total is below the threshold.
set -euo pipefail

THRESHOLD=95
COVERFILE=$(mktemp)

cd services/gateway
go test ./internal/... -coverprofile="$COVERFILE" -count=1

TOTAL=$(go tool cover -func="$COVERFILE" | grep '^total:' | awk '{print $NF}' | tr -d '%')
rm -f "$COVERFILE"

echo "Go coverage: ${TOTAL}% (threshold: ${THRESHOLD}%)"

if awk "BEGIN{exit (${TOTAL} < ${THRESHOLD}) ? 0 : 1}"; then
    echo "FAIL: coverage ${TOTAL}% is below ${THRESHOLD}%"
    exit 1
fi
