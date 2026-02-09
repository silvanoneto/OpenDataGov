#!/bin/bash
set -e

PROFILE="${1:-embedded}"
NAMESPACE="${2:-opendatagov}"
RELEASE_NAME="${3:-opendatagov}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$SCRIPT_DIR/../opendatagov"

echo "==> Installing OpenDataGov with profile: $PROFILE"

# Validate profile
VALID_PROFILES="embedded dev small medium large"
PROFILE_PATTERN=" $PROFILE "
if [[ ! " $VALID_PROFILES " =~ $PROFILE_PATTERN ]]; then
  echo "Error: Invalid profile '$PROFILE'"
  echo "Valid profiles: $VALID_PROFILES"
  exit 1
fi

# Create namespace if not exists
echo "==> Creating namespace $NAMESPACE if it doesn't exist..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Add Helm repositories
echo "==> Adding Helm repositories..."
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add trinodb https://trinodb.github.io/charts
helm repo add apache-airflow https://airflow.apache.org
helm repo add apache-superset https://apache.github.io/superset
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add datahub https://helm.datahubproject.io
helm repo update

# Update dependencies
echo "==> Updating chart dependencies..."
cd "$CHART_DIR"
helm dependency update

# Install chart
echo "==> Installing chart..."
VALUES_FILE="values.yaml"
if [ "$PROFILE" != "embedded" ]; then
  VALUES_FILE="values-$PROFILE.yaml"
fi

if [ ! -f "$VALUES_FILE" ]; then
  echo "Error: Values file $VALUES_FILE not found"
  exit 1
fi

helm install "$RELEASE_NAME" . \
  --namespace "$NAMESPACE" \
  --values "$VALUES_FILE" \
  --create-namespace \
  --wait \
  --timeout 10m

echo ""
echo "==> OpenDataGov $PROFILE profile installed successfully!"
echo ""
echo "Run the following command to get access information:"
echo "  helm get notes $RELEASE_NAME -n $NAMESPACE"
echo ""
echo "Or check pod status:"
echo "  kubectl get pods -n $NAMESPACE"
