#!/bin/bash
set -e

PROFILE="${1:-embedded}"
NAMESPACE="${2:-opendatagov}"
RELEASE_NAME="${3:-opendatagov}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$SCRIPT_DIR/../opendatagov"

echo "==> Upgrading OpenDataGov to profile: $PROFILE"

# Validate profile
VALID_PROFILES="embedded dev small medium large"
PROFILE_PATTERN=" $PROFILE "
if [[ ! " $VALID_PROFILES " =~ $PROFILE_PATTERN ]]; then
  echo "Error: Invalid profile '$PROFILE'"
  echo "Valid profiles: $VALID_PROFILES"
  exit 1
fi

# Update dependencies
echo "==> Updating chart dependencies..."
cd "$CHART_DIR"
helm dependency update

# Upgrade chart
echo "==> Upgrading chart..."
VALUES_FILE="values.yaml"
if [ "$PROFILE" != "embedded" ]; then
  VALUES_FILE="values-$PROFILE.yaml"
fi

if [ ! -f "$VALUES_FILE" ]; then
  echo "Error: Values file $VALUES_FILE not found"
  exit 1
fi

helm upgrade "$RELEASE_NAME" . \
  --namespace "$NAMESPACE" \
  --values "$VALUES_FILE" \
  --wait \
  --timeout 10m

echo ""
echo "==> OpenDataGov upgraded to $PROFILE profile successfully!"
echo ""
echo "Check pod status:"
echo "  kubectl get pods -n $NAMESPACE"
