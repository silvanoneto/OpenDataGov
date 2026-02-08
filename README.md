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
