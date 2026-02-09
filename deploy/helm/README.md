# OpenDataGov Helm Chart

Open Source Data Governance Platform with AI - Kubernetes Deployment via Helm Umbrella Chart

## Overview

This Helm umbrella chart deploys the complete OpenDataGov stack on Kubernetes, including:

### Core Services (Custom)

- **Governance Engine** - Core governance and decision engine (GraphQL, gRPC, REST)
- **Lakehouse Agent** - Lakehouse and Apache Iceberg catalog management
- **Data Expert** - AI-powered data assistant (optional, GPU-enabled)
- **Quality Gate** - Data quality validation and gating
- **Gateway** - API gateway and routing service

### Layer 5: Analytics & Query Components

- **Trino** - Distributed SQL query engine
- **Airflow** - Workflow orchestration platform
- **Superset** - BI and analytics dashboards
- **TimescaleDB** - Time-series database (via PostgreSQL extension)

### AI & ML Components

- **Qdrant** - Vector database for AI/ML
- **Kubeflow** - MLOps platform (optional)

### Infrastructure

- **PostgreSQL** - Primary database
- **Redis** - Caching layer
- **MinIO** - S3-compatible object storage
- **Kafka** - Event streaming (optional)
- **NATS** - Lightweight messaging

### Data Catalog

- **DataHub** - Metadata catalog and lineage

### Observability

- **Grafana** - Metrics visualization
- **Loki** - Log aggregation
- **Tempo** - Distributed tracing
- **Prometheus** - Metrics (via ServiceMonitor)

### Auth & Security

- **Keycloak** - Identity and access management
- **OPA** - Policy engine
- **Vault** - Secrets management

## Deployment Profiles

OpenDataGov supports 5 deployment profiles based on resource requirements:

| Profile      | vCPU | RAM   | GPU | Use Case                   | Layer 5 Components                    |
| ------------ | ---- | ----- | --- | -------------------------- | ------------------------------------- |
| **embedded** | 1-2  | 2-4GB | 0   | IoT, Edge, Laptops         | None                                  |
| **dev**      | 4    | 16GB  | 0   | Development                | None                                  |
| **small**    | 16   | 64GB  | 0   | Small teams, \<1TB/day     | Trino, Airflow, Superset, TimescaleDB |
| **medium**   | 64   | 256GB | 1   | Enterprise, 1-10TB/day     | All (+ Qdrant, Kubeflow)              |
| **large**    | 256+ | 1TB+  | 2+  | Large-scale, >10TB/day, HA | All (HA mode, multi-replica)          |

## Prerequisites

- Kubernetes 1.24+
- Helm 3.10+
- kubectl configured with cluster access
- (Optional) GPU nodes with NVIDIA device plugin for medium/large profiles

## Installation

### Quick Start (Embedded Profile)

```bash
# Clone the repository
git clone https://github.com/silvanoneto/opendatagov.git
cd opendatagov/deploy/helm

# Install using the script
./scripts/install.sh embedded
```

### Install Specific Profile

```bash
# Small profile (recommended for production starting point)
./scripts/install.sh small opendatagov opendatagov

# Medium profile (with AI components and GPU)
./scripts/install.sh medium opendatagov opendatagov

# Large profile (HA mode)
./scripts/install.sh large opendatagov opendatagov
```

### Manual Installation

```bash
# Add Helm repositories
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add trinodb https://trinodb.github.io/charts
helm repo add apache-airflow https://airflow.apache.org
helm repo add apache-superset https://apache.github.io/superset
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add datahub https://helm.datahubproject.io
helm repo update

# Update chart dependencies
cd opendatagov
helm dependency update

# Install with chosen profile
helm install opendatagov . \
  --namespace opendatagov \
  --create-namespace \
  --values values-small.yaml \
  --wait \
  --timeout 10m
```

## Upgrading

### Upgrade to Different Profile

```bash
# Upgrade from dev to small
./scripts/upgrade.sh small opendatagov opendatagov

# Or manually
helm upgrade opendatagov ./opendatagov \
  --namespace opendatagov \
  --values values-small.yaml \
  --wait
```

### Upgrade Chart Version

```bash
# Pull latest changes
git pull origin main

# Update dependencies
cd deploy/helm/opendatagov
helm dependency update

# Upgrade
helm upgrade opendatagov . --namespace opendatagov --wait
```

## Uninstallation

```bash
# Using script (will prompt for namespace deletion)
./scripts/uninstall.sh opendatagov opendatagov

# Or manually
helm uninstall opendatagov --namespace opendatagov
kubectl delete namespace opendatagov  # Optional
```

## Configuration

### Values Files

- `values.yaml` - Embedded profile (default)
- `values-dev.yaml` - Development profile
- `values-small.yaml` - Small team profile
- `values-medium.yaml` - Enterprise profile with AI
- `values-large.yaml` - Large-scale HA profile

### Common Customizations

#### Enable/Disable Components

```yaml
# values-custom.yaml
trino:
  enabled: true  # Enable Trino

airflow:
  enabled: false  # Disable Airflow

data-expert:
  enabled: true
  gpu:
    enabled: true
    count: 1
```

#### Resource Limits

```yaml
governance-engine:
  resources:
    requests:
      cpu: "2"
      memory: 4Gi
    limits:
      cpu: "4"
      memory: 8Gi
```

#### Persistence

```yaml
postgresql:
  primary:
    persistence:
      enabled: true
      size: 100Gi
      storageClass: gp3  # AWS EBS gp3

minio:
  persistence:
    enabled: true
    size: 500Gi
    storageClass: gp3
```

#### Ingress

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: opendatagov.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: opendatagov-tls
      hosts:
        - opendatagov.example.com
```

## Accessing Services

After installation, get access information:

```bash
helm get notes opendatagov -n opendatagov
```

### Port-Forward Examples

```bash
# Governance Engine
kubectl port-forward -n opendatagov svc/opendatagov-governance-engine 8000:8000

# Grafana
kubectl port-forward -n opendatagov svc/opendatagov-grafana 3000:3000

# Trino UI
kubectl port-forward -n opendatagov svc/opendatagov-trino-coordinator 8080:8080

# Airflow UI
kubectl port-forward -n opendatagov svc/opendatagov-airflow-webserver 8080:8080

# Superset
kubectl port-forward -n opendatagov svc/opendatagov-superset 8088:8088
```

### Ingress Access

If Ingress is enabled, access services via configured hosts:

- Governance Engine: `https://governance.example.com`
- Grafana: `https://grafana.example.com`
- Trino: `https://trino.example.com`
- Airflow: `https://airflow.example.com`

## Monitoring

### Check Pod Status

```bash
kubectl get pods -n opendatagov
kubectl get pods -n opendatagov -l app.kubernetes.io/name=governance-engine
```

### View Logs

```bash
# Governance Engine logs
kubectl logs -n opendatagov -l app.kubernetes.io/name=governance-engine -f

# All services logs
kubectl logs -n opendatagov -l app.kubernetes.io/part-of=opendatagov -f --max-log-requests=20
```

### Prometheus ServiceMonitors

If Prometheus Operator is installed:

```bash
kubectl get servicemonitors -n opendatagov
```

Enable ServiceMonitors in values:

```yaml
serviceMonitor:
  enabled: true
  interval: 30s
```

## Troubleshooting

### Pods Not Starting

```bash
# Check events
kubectl get events -n opendatagov --sort-by='.lastTimestamp'

# Describe pod
kubectl describe pod -n opendatagov <pod-name>

# Check resource constraints
kubectl top nodes
kubectl top pods -n opendatagov
```

### Dependency Issues

```bash
# Re-download dependencies
cd deploy/helm/opendatagov
rm -rf charts/ Chart.lock
helm dependency update

# Check dependency status
helm dependency list
```

### Database Connection Issues

```bash
# Check PostgreSQL pod
kubectl logs -n opendatagov -l app.kubernetes.io/name=postgresql

# Test connection from governance-engine
kubectl exec -n opendatagov deploy/opendatagov-governance-engine -- \
  sh -c 'pg_isready -h opendatagov-postgresql -U odg'
```

### GPU Not Detected (Medium/Large Profiles)

```bash
# Check NVIDIA device plugin
kubectl get pods -n kube-system -l name=nvidia-device-plugin-ds

# Verify GPU nodes
kubectl get nodes "-o=custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu"

# Check pod GPU allocation
kubectl describe pod -n opendatagov <data-expert-pod>
```

## Development

### Local Testing with Kind

```bash
# Create kind cluster
kind create cluster --name opendatagov

# Install embedded profile
cd deploy/helm
./scripts/install.sh embedded opendatagov opendatagov

# Access services via port-forward
kubectl port-forward -n opendatagov svc/opendatagov-governance-engine 8000:8000
```

### Local Testing with k3s

```bash
# Install k3s (single-node)
curl -sfL https://get.k3s.io | sh -

# Copy kubeconfig
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Install dev profile
cd deploy/helm
./scripts/install.sh dev opendatagov opendatagov
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway (8080)                       │
└────────────┬──────────┬──────────┬──────────┬───────────────┘
             │          │          │          │
     ┌───────▼────┐ ┌──▼────┐ ┌───▼─────┐ ┌─▼─────────┐
     │ Governance │ │ Lake  │ │  Data   │ │  Quality  │
     │   Engine   │ │ house │ │ Expert  │ │   Gate    │
     │ (8000)     │ │ Agent │ │ (8002)  │ │  (8003)   │
     └─────┬──────┘ └───┬───┘ └────┬────┘ └─────┬─────┘
           │            │          │            │
     ┌─────▼────────────▼──────────▼────────────▼─────┐
     │         Infrastructure Layer                     │
     │  PostgreSQL │ Redis │ MinIO │ Kafka │ NATS      │
     └─────┬────────────────────────────────────────────┘
           │
     ┌─────▼────────────────────────────────────────────┐
     │         Layer 5: Analytics & Query                │
     │   Trino │ Airflow │ Superset │ TimescaleDB       │
     └──────────────────────────────────────────────────┘
```

## Contributing

See [CONTRIBUTING.md](../../../CONTRIBUTING.md)

## License

Apache 2.0 - See [LICENSE](../../../LICENSE)

## Support

- Issues: https://github.com/silvanoneto/opendatagov/issues
- Discussions: https://github.com/silvanoneto/opendatagov/discussions
- Documentation: https://github.com/silvanoneto/opendatagov/tree/main/docs
