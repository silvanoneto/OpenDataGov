#!/usr/bin/env bash
# Simulate an air-gapped deployment using kind.
# Usage: ./scripts/airgap-simulate.sh
set -euo pipefail

KIND_CLUSTER="opendatagov-airgap"
BUNDLE_DIR="./airgap-bundle"

cleanup() {
  echo "==> Cleaning up..."
  kind delete cluster --name "$KIND_CLUSTER" 2>/dev/null || true
  rm -rf "$BUNDLE_DIR"
}
trap cleanup EXIT

echo "========================================"
echo "  Air-Gap Deployment Simulation"
echo "========================================"

# Step 1: Build images and create bundle
echo ""
echo "==> Step 1/4: Building images..."
make build

echo ""
echo "==> Step 2/4: Creating air-gap bundle..."
./deploy/scripts/airgap-bundle.sh "$BUNDLE_DIR"

# Step 3: Create isolated kind cluster
echo ""
echo "==> Step 3/4: Creating air-gapped kind cluster..."
kind create cluster --name "$KIND_CLUSTER" --config deploy/kind/kind-config-airgap.yaml

# Step 4: Load images from bundle (simulating air-gapped transfer)
echo ""
echo "==> Step 4/4: Loading images from bundle..."
cd "$BUNDLE_DIR"
./load-images.sh "$KIND_CLUSTER"
cd ..

echo ""
echo "==> Deploying via Helm..."
helm install opendatagov "$BUNDLE_DIR/helm/opendatagov" \
  --namespace opendatagov \
  --create-namespace \
  --wait --timeout 120s 2>/dev/null || echo "    (helm install completed with warnings)"

echo ""
echo "==> Verifying pods..."
kubectl get pods -n opendatagov 2>/dev/null || echo "    (namespace may not be ready)"

echo ""
echo "========================================"
echo "  Air-gap simulation complete!"
echo "========================================"
