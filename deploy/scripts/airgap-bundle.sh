#!/usr/bin/env bash
# Bundle all container images for air-gapped deployment.
# Usage: ./deploy/scripts/airgap-bundle.sh [output-dir]
set -euo pipefail

OUTPUT_DIR="${1:-./airgap-bundle}"
mkdir -p "$OUTPUT_DIR"

APP_IMAGES=(
  "opendatagov/governance-engine:0.1.0"
  "opendatagov/lakehouse-agent:0.1.0"
  "opendatagov/data-expert:0.1.0"
  "opendatagov/quality-gate:0.1.0"
  "opendatagov/gateway:0.1.0"
)

INFRA_IMAGES=(
  "postgres:16-alpine"
  "redis:7-alpine"
  "minio/minio:latest"
  "nats:2-alpine"
  "otel/opentelemetry-collector-contrib:latest"
  "jaegertracing/all-in-one:latest"
  "victoriametrics/victoria-metrics:latest"
  "grafana/grafana:latest"
  "grafana/loki:latest"
)

ALL_IMAGES=("${APP_IMAGES[@]}" "${INFRA_IMAGES[@]}")

echo "==> Saving ${#ALL_IMAGES[@]} images to $OUTPUT_DIR/images.tar.gz"

docker save "${ALL_IMAGES[@]}" | gzip > "$OUTPUT_DIR/images.tar.gz"

echo "==> Copying deployment manifests"
cp -r deploy/helm "$OUTPUT_DIR/helm"
cp -r deploy/kind "$OUTPUT_DIR/kind"
cp deploy/tofu/main.tf deploy/tofu/variables.tf "$OUTPUT_DIR/"

echo "==> Creating load script"
cat > "$OUTPUT_DIR/load-images.sh" << 'LOADER'
#!/usr/bin/env bash
set -euo pipefail
echo "==> Loading images into kind cluster..."
gunzip -c images.tar.gz | docker load
KIND_CLUSTER="${1:-opendatagov}"
for img in $(docker images --format '{{.Repository}}:{{.Tag}}' | grep opendatagov/); do
  kind load docker-image "$img" --name "$KIND_CLUSTER"
done
echo "==> Done. All images loaded."
LOADER
chmod +x "$OUTPUT_DIR/load-images.sh"

echo "==> Bundle created at $OUTPUT_DIR"
echo "    images.tar.gz  : $(du -sh "$OUTPUT_DIR/images.tar.gz" | cut -f1)"
echo "    To deploy: cd $OUTPUT_DIR && ./load-images.sh"
