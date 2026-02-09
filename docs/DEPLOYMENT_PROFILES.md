# Deployment Profiles

## Overview

OpenDataGov provides four deployment profiles to match different environments and scale requirements. Each profile is optimized for specific use cases, from local development to large-scale production deployments.

## Profile Comparison

| Profile    | vCPU | RAM   | GPU | Storage | Monthly Cost (est.) | Use Case                   |
| ---------- | ---- | ----- | --- | ------- | ------------------- | -------------------------- |
| **dev**    | 4    | 16GB  | -   | 2GB     | ~$50                | Local development, testing |
| **small**  | 16   | 64GB  | -   | 100GB   | ~$400               | Small teams, \<1TB/day     |
| **medium** | 64   | 256GB | 1   | 1TB     | ~$2,500             | Enterprise, 1-10TB/day     |
| **large**  | 256+ | 1TB+  | 2+  | 10TB+   | ~$15,000+           | Large-scale, >10TB/day     |

## Components by Profile

| Component             | dev | small    | medium | large | Purpose                        |
| --------------------- | --- | -------- | ------ | ----- | ------------------------------ |
| **PostgreSQL**        | ✓   | ✓        | ✓      | ✓     | Relational database for state  |
| **Redis**             | ✓   | ✓        | ✓      | ✓     | Cache and session store        |
| **MinIO**             | ✓   | ✓        | ✓      | ✓     | Object storage (S3-compatible) |
| **NATS**              | ✓   | ✓        | ✓      | ✓     | Lightweight messaging          |
| **Kafka**             | -   | ✓        | ✓      | ✓     | Event streaming (high volume)  |
| **Trino**             | -   | ✓        | ✓      | ✓     | SQL query engine               |
| **Airflow**           | -   | ✓        | ✓      | ✓     | Workflow orchestration         |
| **DataHub**           | -   | ✓        | ✓      | ✓     | Data catalog and lineage       |
| **Qdrant**            | -   | -        | ✓      | ✓     | Vector database for AI         |
| **AI Experts**        | -   | Optional | ✓      | ✓     | AI-powered recommendations     |
| **GPU**               | -   | -        | ✓      | ✓     | GPU acceleration for AI        |
| **Multi-AZ**          | -   | -        | -      | ✓     | High availability              |
| **COSMOS Federation** | -   | -        | -      | ✓     | Multi-region data sharing      |

## Dev Profile

**Target**: Local development and testing

### Specifications

- **Platform**: Docker Compose
- **Resources**: 4 vCPU, 16GB RAM
- **Storage**: 2GB (ephemeral)
- **Network**: localhost only

### What's Included

✓ Core services (governance-engine, lakehouse-agent, quality-gate)
✓ PostgreSQL, Redis, MinIO
✓ NATS for lightweight messaging
✓ Basic observability (Grafana, VictoriaMetrics, Loki)
✗ No Kafka (uses NATS only)
✗ No DataHub
✗ No AI experts
✗ No production-grade persistence

### Quick Start

```bash
# Clone repository
git clone https://github.com/opendatagov/opendatagov.git
cd opendatagov

# Start dev environment
make compose-up

# Access services
open http://localhost:3000  # Grafana
open http://localhost:9000  # MinIO Console
```

### Environment Variables

```bash
# .env
ENVIRONMENT=dev
LOG_LEVEL=DEBUG
POSTGRES_PASSWORD=dev_password
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
REDIS_PASSWORD=dev_redis
```

### Limitations

- **Not for production**: Data is ephemeral
- **No GPU support**: AI features disabled
- **Limited scalability**: Single-node only
- **No backups**: Data lost on restart

## Small Profile

**Target**: Small teams, proof-of-concept, \<1TB/day

### Specifications

- **Platform**: Kubernetes (K3s or managed)
- **Resources**: 16 vCPU, 64GB RAM
- **Storage**: 100GB persistent volumes
- **Network**: Single region, single AZ

### What's Included

✓ All dev components
✓ Kafka for event streaming
✓ DataHub for catalog and lineage
✓ Trino for SQL queries
✓ Airflow for orchestration
✓ Production-grade persistence
✗ No GPU / AI experts (optional)
✗ No multi-AZ redundancy

### Deployment

```bash
# Install via Helm
helm repo add opendatagov https://charts.opendatagov.io
helm install odg opendatagov/opendatagov \
  -f values-small.yaml \
  --namespace opendatagov \
  --create-namespace

# Check status
kubectl get pods -n opendatagov
```

### values-small.yaml

```yaml
profile: small

# Resource limits
resources:
  governanceEngine:
    limits:
      cpu: 2000m
      memory: 4Gi
    requests:
      cpu: 1000m
      memory: 2Gi

  lakehouseAgent:
    limits:
      cpu: 2000m
      memory: 4Gi

  qualityGate:
    limits:
      cpu: 2000m
      memory: 4Gi

  dataExpert:
    enabled: false  # AI optional in small profile

# Component toggles
components:
  kafka: true
  trino: true
  airflow: true
  datahub: true
  qdrant: false
  gpu: false

# Storage
storage:
  class: standard
  postgres:
    size: 20Gi
  minio:
    size: 50Gi
  kafka:
    size: 20Gi

# Replicas (single instance)
replicas:
  governanceEngine: 1
  lakehouseAgent: 1
  qualityGate: 1
```

### Cost Breakdown (Monthly)

| Service             | Cost            |
| ------------------- | --------------- |
| Compute (16 vCPU)   | $240            |
| Memory (64GB)       | $80             |
| Storage (100GB SSD) | $20             |
| Networking          | $40             |
| Load Balancer       | $20             |
| **Total**           | **~$400/month** |

## Medium Profile

**Target**: Enterprise teams, 1-10TB/day, AI-enabled

### Specifications

- **Platform**: Kubernetes (EKS, GKE, AKS)
- **Resources**: 64 vCPU, 256GB RAM, 1 GPU
- **Storage**: 1TB persistent volumes
- **Network**: Multi-region capable, single AZ

### What's Included

✓ All small components
✓ GPU-powered AI experts
✓ Qdrant vector database
✓ Multi-expert orchestration
✓ Increased replica counts
✓ Auto-scaling enabled
✗ No multi-AZ redundancy (cost optimization)

### Deployment

```bash
helm install odg opendatagov/opendatagov \
  -f values-medium.yaml \
  --namespace opendatagov \
  --create-namespace
```

### values-medium.yaml

```yaml
profile: medium

# Resource limits (higher than small)
resources:
  governanceEngine:
    limits:
      cpu: 8000m
      memory: 16Gi
    requests:
      cpu: 4000m
      memory: 8Gi

  dataExpert:
    enabled: true
    limits:
      cpu: 4000m
      memory: 16Gi
      nvidia.com/gpu: 1
    requests:
      cpu: 2000m
      memory: 8Gi
      nvidia.com/gpu: 1

# Component toggles
components:
  kafka: true
  trino: true
  airflow: true
  datahub: true
  qdrant: true
  gpu: true
  experts: true

# Storage
storage:
  class: premium-ssd
  postgres:
    size: 100Gi
  minio:
    size: 500Gi
  kafka:
    size: 100Gi
  qdrant:
    size: 50Gi

# Replicas (redundancy without multi-AZ)
replicas:
  governanceEngine: 3
  lakehouseAgent: 2
  qualityGate: 2
  dataExpert: 2

# Auto-scaling
autoscaling:
  enabled: true
  governanceEngine:
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilization: 70

# GPU node pool
nodeSelector:
  dataExpert:
    cloud.google.com/gke-accelerator: nvidia-tesla-t4
```

### Cost Breakdown (Monthly)

| Service                       | Cost              |
| ----------------------------- | ----------------- |
| Compute (64 vCPU)             | $960              |
| Memory (256GB)                | $320              |
| GPU (1x NVIDIA T4)            | $400              |
| Storage (1TB SSD)             | $200              |
| Networking                    | $200              |
| Load Balancer                 | $20               |
| Managed Services (Kafka, RDS) | $400              |
| **Total**                     | **~$2,500/month** |

## Large Profile

**Target**: Large-scale, >10TB/day, multi-AZ, COSMOS federation

### Specifications

- **Platform**: Kubernetes (multi-cluster)
- **Resources**: 256+ vCPU, 1TB+ RAM, 2+ GPUs
- **Storage**: 10TB+ persistent volumes
- **Network**: Multi-region, multi-AZ, global CDN

### What's Included

✓ All medium components
✓ Multi-AZ high availability
✓ Cross-region replication
✓ COSMOS federation (multi-instance)
✓ Advanced auto-scaling
✓ Disaster recovery
✓ 24/7 monitoring and alerting

### Deployment

```bash
# Deploy primary cluster
helm install odg-primary opendatagov/opendatagov \
  -f values-large.yaml \
  --namespace opendatagov \
  --create-namespace

# Deploy secondary cluster (DR)
helm install odg-secondary opendatagov/opendatagov \
  -f values-large.yaml \
  -f values-large-secondary.yaml \
  --namespace opendatagov \
  --create-namespace

# Enable COSMOS federation
kubectl apply -f cosmos-federation.yaml
```

### values-large.yaml

```yaml
profile: large

# High-availability configuration
ha:
  enabled: true
  zones:
    - us-east-1a
    - us-east-1b
    - us-east-1c

# Resource limits (production scale)
resources:
  governanceEngine:
    limits:
      cpu: 16000m
      memory: 64Gi
    requests:
      cpu: 8000m
      memory: 32Gi

  dataExpert:
    enabled: true
    limits:
      cpu: 8000m
      memory: 32Gi
      nvidia.com/gpu: 2
    requests:
      cpu: 4000m
      memory: 16Gi
      nvidia.com/gpu: 2

# Component toggles
components:
  kafka: true
  trino: true
  airflow: true
  datahub: true
  qdrant: true
  gpu: true
  experts: true
  cosmos: true
  multiAZ: true

# Storage (with replication)
storage:
  class: premium-ssd
  replicationFactor: 3
  postgres:
    size: 500Gi
    replicas: 3
  minio:
    size: 5000Gi
    distributedMode: true
  kafka:
    size: 1000Gi
    replicas: 5
  qdrant:
    size: 500Gi
    replicas: 3

# Replicas (high availability)
replicas:
  governanceEngine: 5
  lakehouseAgent: 3
  qualityGate: 3
  dataExpert: 3

# Advanced auto-scaling
autoscaling:
  enabled: true
  governanceEngine:
    minReplicas: 5
    maxReplicas: 20
    targetCPUUtilization: 60
    targetMemoryUtilization: 70

# Multi-region
multiRegion:
  enabled: true
  regions:
    - us-east-1
    - eu-west-1
    - ap-southeast-1

# COSMOS federation
cosmos:
  enabled: true
  instances:
    - id: us-primary
      endpoint: https://us.opendatagov.example.com
    - id: eu-primary
      endpoint: https://eu.opendatagov.example.com
  crdt:
    enabled: true
    conflictResolution: lww  # Last-Write-Wins

# Monitoring & Alerting
monitoring:
  sla:
    uptime: 99.99
    latencyP99: 100ms
  alerting:
    pagerduty: true
    slack: true
    email: true

# Backups
backup:
  enabled: true
  schedule: "0 */6 * * *"  # Every 6 hours
  retention: 30  # days
  crossRegion: true
```

### Cost Breakdown (Monthly)

| Service                       | Cost                |
| ----------------------------- | ------------------- |
| Compute (256 vCPU)            | $3,840              |
| Memory (1TB)                  | $1,280              |
| GPU (2x NVIDIA A100)          | $4,000              |
| Storage (10TB SSD)            | $2,000              |
| Networking (multi-region)     | $1,500              |
| Load Balancers (multi-region) | $300                |
| Managed Services              | $1,500              |
| Backups & DR                  | $500                |
| Monitoring & Logging          | $200                |
| **Total**                     | **~$15,000+/month** |

## Choosing the Right Profile

### Decision Matrix

```
Start here ↓

Is this for production?
│
├─ No → **dev** (Docker Compose)
│
└─ Yes → How much data?
   │
   ├─ <1TB/day → **small** (K8s, no GPU)
   │
   ├─ 1-10TB/day → **medium** (K8s + GPU)
   │
   └─ >10TB/day → **large** (Multi-cluster HA)
```

### Feature Requirements

| Need              | Minimum Profile |
| ----------------- | --------------- |
| Local development | **dev**         |
| DataHub catalog   | **small**       |
| AI experts        | **medium**      |
| GPU acceleration  | **medium**      |
| Multi-AZ HA       | **large**       |
| Multi-region      | **large**       |
| COSMOS federation | **large**       |

## Migration Between Profiles

### Dev → Small

```bash
# 1. Export data from dev
docker exec postgres pg_dump -U postgres opendatagov > backup.sql
docker exec minio mc mirror local/data ./minio-backup

# 2. Deploy small profile
helm install odg opendatagov/opendatagov -f values-small.yaml

# 3. Restore data
kubectl exec -it postgres-0 -- psql -U postgres opendatagov < backup.sql
kubectl cp ./minio-backup minio-0:/data
```

### Small → Medium

```bash
# Rolling update with GPU nodes
helm upgrade odg opendatagov/opendatagov -f values-medium.yaml

# Verify GPU nodes are ready
kubectl get nodes -l nvidia.com/gpu=true

# Scale up gradually
kubectl scale deployment data-expert --replicas=2
```

### Medium → Large

```bash
# Enable multi-AZ
helm upgrade odg opendatagov/opendatagov -f values-large.yaml

# Deploy to additional regions
helm install odg-eu opendatagov/opendatagov \
  -f values-large.yaml \
  -f values-eu.yaml \
  --kube-context eu-cluster

# Enable COSMOS federation
kubectl apply -f cosmos-federation.yaml
```

## Performance Tuning

### Small Profile Optimizations

```yaml
# Reduce resource usage
resources:
  governanceEngine:
    limits:
      cpu: 1000m
      memory: 2Gi

# Use local storage (faster, cheaper)
storage:
  class: local-path

# Disable unnecessary components
components:
  airflow: false  # If not using workflows
  trino: false    # If not using SQL queries
```

### Medium Profile Optimizations

```yaml
# Optimize Kafka for throughput
kafka:
  config:
    num.partitions: 10
    default.replication.factor: 2
    compression.type: snappy

# GPU memory optimization
dataExpert:
  env:
    - name: PYTORCH_CUDA_ALLOC_CONF
      value: "max_split_size_mb:512"
```

### Large Profile Optimizations

```yaml
# Database connection pooling
postgres:
  maxConnections: 500
  sharedBuffers: 16GB

# Kafka producer tuning
kafka:
  config:
    linger.ms: 10
    batch.size: 65536
    buffer.memory: 67108864

# MinIO distributed performance
minio:
  mode: distributed
  replicas: 16  # 4 servers × 4 drives
  drivesPerNode: 4
```

## Troubleshooting

### Common Issues

#### Out of Memory (Small Profile)

```bash
# Reduce replica counts
kubectl scale deployment governance-engine --replicas=1

# Or upgrade to medium profile
helm upgrade odg opendatagov/opendatagov -f values-medium.yaml
```

#### GPU Not Available (Medium)

```bash
# Check GPU nodes
kubectl get nodes -l nvidia.com/gpu=true

# Install GPU device plugin if missing
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/main/nvidia-device-plugin.yml
```

#### Multi-AZ Latency Issues (Large)

```yaml
# Use pod topology spread
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
```

## Further Reading

- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [GPU Sharing Strategies](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [Multi-Region Deployment](https://cloud.google.com/kubernetes-engine/docs/concepts/multi-cluster-overview)
- [Cost Optimization](https://cloud.google.com/architecture/best-practices-for-running-cost-effective-kubernetes-applications-on-gke)
