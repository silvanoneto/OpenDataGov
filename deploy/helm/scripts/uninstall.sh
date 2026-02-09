#!/bin/bash
set -e

NAMESPACE="${1:-opendatagov}"
RELEASE_NAME="${2:-opendatagov}"

echo "==> Uninstalling OpenDataGov..."

# Check if release exists
if ! helm list -n "$NAMESPACE" | grep -q "$RELEASE_NAME"; then
  echo "Error: Release $RELEASE_NAME not found in namespace $NAMESPACE"
  exit 1
fi

# Uninstall
helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE"

echo ""
echo "==> OpenDataGov uninstalled successfully!"
echo ""
echo "Do you want to delete the namespace '$NAMESPACE'? (y/N)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
  kubectl delete namespace "$NAMESPACE"
  echo "==> Namespace $NAMESPACE deleted"
else
  echo "==> Namespace $NAMESPACE preserved"
  echo "    PersistentVolumeClaims may still exist. List with:"
  echo "    kubectl get pvc -n $NAMESPACE"
fi
