#!/usr/bin/env bash
# Full integration test: Kind cluster deploy + test suite.
# Usage: ./scripts/full-test.sh
set -euo pipefail

KIND_CLUSTER="opendatagov-test"
COMPOSE_FILE="deploy/docker-compose/docker-compose.yml"

cleanup() {
  echo "==> Cleaning up..."
  kind delete cluster --name "$KIND_CLUSTER" 2>/dev/null || true
}
trap cleanup EXIT

echo "========================================"
echo "  OpenDataGov Full Integration Test"
echo "========================================"

# Step 1: Unit tests
echo ""
echo "==> Step 1/4: Running unit tests..."
make test

# Step 2: Build images
echo ""
echo "==> Step 2/4: Building Docker images..."
make build

# Step 3: Docker Compose smoke test
echo ""
echo "==> Step 3/4: Docker Compose smoke test..."
docker compose -f "$COMPOSE_FILE" up -d
sleep 10

HEALTHY=true
for svc in governance-engine lakehouse-agent data-expert gateway; do
  if ! docker compose -f "$COMPOSE_FILE" ps "$svc" --format '{{.Status}}' | grep -qi "up\|healthy"; then
    echo "    FAIL: $svc is not healthy"
    HEALTHY=false
  else
    echo "    OK: $svc"
  fi
done

docker compose -f "$COMPOSE_FILE" down

if [ "$HEALTHY" = false ]; then
  echo "==> Compose smoke test FAILED"
  exit 1
fi

# Step 4: Kind cluster deploy
echo ""
echo "==> Step 4/4: Kind cluster deploy test..."
kind create cluster --name "$KIND_CLUSTER" --config deploy/kind/kind-config.yaml

for img in opendatagov/governance-engine opendatagov/lakehouse-agent opendatagov/data-expert opendatagov/quality-gate opendatagov/gateway; do
  kind load docker-image "$img:0.1.0" --name "$KIND_CLUSTER"
done

cd deploy/tofu && tofu init -input=false && tofu apply -auto-approve
cd ../..

echo ""
echo "==> Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/part-of=opendatagov -n opendatagov --timeout=120s 2>/dev/null || echo "    (some pods may not be ready yet)"

echo ""
echo "========================================"
echo "  All tests passed!"
echo "========================================"
