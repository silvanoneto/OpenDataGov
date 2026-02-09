# OpenDataGov

[![CI Python](https://github.com/silvanoneto/OpenDataGov/actions/workflows/ci-python.yml/badge.svg)](https://github.com/silvanoneto/OpenDataGov/actions/workflows/ci-python.yml)
[![CI Go](https://github.com/silvanoneto/OpenDataGov/actions/workflows/ci-go.yml/badge.svg)](https://github.com/silvanoneto/OpenDataGov/actions/workflows/ci-go.yml)
[![CI Helm](https://github.com/silvanoneto/OpenDataGov/actions/workflows/ci-helm.yml/badge.svg)](https://github.com/silvanoneto/OpenDataGov/actions/workflows/ci-helm.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Open-source data governance platform with progressive AI capabilities. Features data catalog, lineage tracking, quality gates, observability, and security controls. Clean-room redesign (Apache-2.0) inspired by RADaC.

## Architecture

### Core Services

- **Governance Engine** — Core governance with RACI model, approval workflows, veto mechanics, and SHA-256 audit chain
- **Lakehouse Agent** — MinIO object storage with Apache Iceberg catalog, Medallion architecture (Bronze/Silver/Gold/Platinum)
- **Quality Gate** — Data quality validation service with configurable rules and gates
- **Data Expert** — AI expert service (first of many) with "AI recommends, human decides" paradigm
- **Gateway** — Go-based LLM routing gateway with OpenAI-compatible API

### Infrastructure & Integrations

- **DataHub** — Metadata catalog for data discovery, lineage tracking, and governance integration
- **Observability** — OpenTelemetry, Jaeger tracing, Grafana dashboards, VictoriaMetrics
- **Security** — HashiCorp Vault for secrets management, OPA for policy enforcement
- **GitOps** — ArgoCD for declarative deployments and continuous delivery

## Quick Start

Prerequisites: Docker, Docker Compose

```bash
make compose-up
```

Services will be available at:

| Service           | URL                      | Description                |
| ----------------- | ------------------------ | -------------------------- |
| Governance Engine | <http://localhost:8000>  | Core governance APIs       |
| Lakehouse Agent   | <http://localhost:8001>  | MinIO & Iceberg management |
| Data Expert       | <http://localhost:8002>  | AI-powered data assistance |
| Quality Gate      | <http://localhost:8003>  | Data quality validation    |
| Gateway           | <http://localhost:8080>  | LLM routing gateway        |
| MinIO Console     | <http://localhost:9001>  | Object storage UI          |
| DataHub UI        | <http://localhost:9002>  | Metadata catalog & lineage |
| Jaeger UI         | <http://localhost:16686> | Distributed tracing        |

### Try the API

```bash
# Check health
curl http://localhost:8000/health

# Create a governance decision
curl -X POST http://localhost:8000/api/v1/decisions \
  -H "Content-Type: application/json" \
  -d '{
    "decision_type": "data_promotion",
    "title": "Promote sales dataset to Gold",
    "description": "Monthly sales data passes all DQ gates",
    "domain_id": "finance",
    "created_by": "engineer-1"
  }'

# Assign a RACI role
curl -X POST http://localhost:8000/api/v1/roles \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "engineer-1",
    "domain_id": "finance",
    "role": "responsible",
    "assigned_by": "admin"
  }'

# Submit a decision for approval (replace <decision-id>)
curl -X POST http://localhost:8000/api/v1/decisions/<decision-id>/submit \
  -H "Content-Type: application/json" \
  -d '{"actor_id": "engineer-1"}'

# Cast a vote (replace <decision-id>)
curl -X POST http://localhost:8000/api/v1/decisions/<decision-id>/approve \
  -H "Content-Type: application/json" \
  -d '{
    "voter_id": "engineer-1",
    "vote": "approve",
    "comment": "DQ checks pass"
  }'

# Verify audit chain integrity
curl http://localhost:8000/api/v1/audit/verify

# List lakehouse buckets
curl http://localhost:8001/api/v1/buckets

# Query Data Expert capabilities
curl http://localhost:8002/api/v1/capabilities

# Process a query through Data Expert
curl -X POST http://localhost:8002/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show top 10 customers by revenue",
    "capability": "sql_generation"
  }'

# Check Quality Gate health
curl http://localhost:8003/health

# Validate data quality
curl -X POST http://localhost:8003/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "gold.sales",
    "rules": ["completeness", "freshness", "schema_conformance"]
  }'
```

## API Protocols (Phase 3)

OpenDataGov supports multiple API protocols for different use cases:

### GraphQL API

Query metadata with precise field selection:

```bash
curl -X POST http://localhost:8000/api/v1/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { decision(id: \"<decision-id>\") { id title status approvers { userId vote } } }"
  }'
```

**Interactive Playground**: Open `http://localhost:8000/api/v1/graphql` in your browser

**Use cases**: Complex queries, lineage traversal, reducing overfetching

📖 See [GraphQL API Guide](docs/API_GRAPHQL.md) for full reference

### gRPC API

High-performance inter-service communication:

```bash
# Install grpcurl
brew install grpcurl

# List available services
grpcurl -plaintext localhost:50051 list

# Call GovernanceService
grpcurl -plaintext \
  -d '{
    "decision_type": "data_promotion",
    "title": "Test Decision",
    "domain_id": "test",
    "created_by": "user-1"
  }' \
  localhost:50051 governance.GovernanceService/CreateDecision
```

**Available Services**:

- GovernanceService (`:50051`)
- CatalogService (`:50052`)
- QualityService (`:50053`)

📖 See [gRPC API Guide](docs/API_GRPC.md) for full reference

### Event Streaming (Kafka)

Subscribe to real-time events:

```python
from odg_core.events.kafka_consumer import KafkaConsumer

consumer = KafkaConsumer(bootstrap_servers="localhost:9092")
await consumer.subscribe(["odg.audit.events", "odg.governance.decisions"])

async for event in consumer.consume():
    print(f"Event: {event.type} - {event.data}")
```

**Available Topics**:

- `odg.audit.events` — Audit trail events
- `odg.governance.decisions` — Decision state changes
- `odg.quality.reports` — Quality validation results
- `odg.lineage.updates` — Lineage graph updates

## Plugin Architecture

Extend OpenDataGov without modifying core code:

```python
from odg_core.quality.base_check import BaseCheck, CheckResult
from odg_core.plugins.registry import PluginRegistry

# Create custom quality check
class CustomCheck(BaseCheck):
    async def validate(self, data):
        # Your validation logic
        return CheckResult(passed=True, score=0.95)

# Register plugin
PluginRegistry.register_check("custom", CustomCheck)
```

**Available Extension Points**:

- **Quality Checks** (`BaseCheck`) — Data quality validators
- **Governance Rules** (`BaseRule`) — Policy enforcement
- **Catalog Connectors** (`BaseConnector`) — Metadata extraction
- **Privacy Mechanisms** (`BasePrivacy`) — Data protection
- **Storage Backends** (`BaseStorage`) — Storage adapters
- **AI Experts** (`BaseExpert`) — AI recommendations

📖 See [Plugin Development Guide](docs/PLUGINS.md) for examples

## Deployment Profiles

Choose the right deployment size:

| Profile    | Resources                    | Use Case               | Monthly Cost |
| ---------- | ---------------------------- | ---------------------- | ------------ |
| **dev**    | 4 vCPU, 16GB RAM             | Local development      | ~$50         |
| **small**  | 16 vCPU, 64GB RAM            | Small teams, \<1TB/day | ~$400        |
| **medium** | 64 vCPU, 256GB RAM, 1 GPU    | Enterprise, 1-10TB/day | ~$2,500      |
| **large**  | 256+ vCPU, 1TB+ RAM, 2+ GPUs | Large-scale, >10TB/day | ~$15,000+    |

```bash
# Deploy small profile
helm install odg opendatagov/opendatagov -f values-small.yaml

# Deploy medium profile with GPU
helm install odg opendatagov/opendatagov -f values-medium.yaml

# Deploy large profile (multi-AZ HA)
helm install odg opendatagov/opendatagov -f values-large.yaml
```

📖 See [Deployment Profiles](docs/DEPLOYMENT_PROFILES.md) for sizing guide

## Optional Components

Enable additional features with separate compose files:

```bash
# DataHub metadata catalog
docker compose -f deploy/docker-compose/docker-compose.yml \
               -f deploy/docker-compose/docker-compose.datahub.yml up

# HashiCorp Vault for secrets
docker compose -f deploy/docker-compose/docker-compose.yml \
               -f deploy/docker-compose/docker-compose.vault.yml up

# ArgoCD for GitOps
docker compose -f deploy/docker-compose/docker-compose.yml \
               -f deploy/docker-compose/docker-compose.argocd.yml up

# All features (includes Kafka, Grafana, VictoriaMetrics)
make compose-full-up
```

## Development

Prerequisites: Python 3.13+, [uv](https://docs.astral.sh/uv/), [pre-commit](https://pre-commit.com/), Go 1.25+, Docker

```bash
# Set up dev environment (deps + pre-commit hooks)
make install

# Run linters (ruff + mypy for Python, golangci-lint for Go)
make lint

# Run tests (pytest for Python, go test for Go)
make test

# Generate protobuf code
make proto
```

Run `make help` for the full list of commands.

Both CI and pre-push hooks enforce a **95% test coverage** threshold for all packages.

## Project Structure

```
OpenDataGov/
├── libs/
│   ├── python/odg-core/          # Shared library (models, enums, audit, DB)
│   └── go/odg-proto/             # Protobuf definitions + generated code
├── services/
│   ├── governance-engine/        # Python/FastAPI — core governance
│   ├── lakehouse-agent/          # Python/FastAPI — MinIO + Iceberg
│   ├── quality-gate/             # Python/FastAPI — data quality validation
│   ├── data-expert/              # Python/FastAPI — first AI expert
│   └── gateway/                  # Go — LLM routing gateway
├── deploy/
│   ├── docker-compose/           # Local development (includes DataHub, ArgoCD, Vault)
│   ├── helm/                     # Kubernetes charts
│   └── tofu/                     # OpenTofu modules
├── scripts/                      # Dev tooling
└── .github/workflows/            # CI/CD
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
