# Data Catalog - OpenDataGov

DataHub-powered **metadata platform** for data discovery, lineage tracking, and governance.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Capabilities](#capabilities)
- [Deployment](#deployment)
- [Integration](#integration)
  - [Medallion Lakehouse](#medallion-lakehouse)
  - [MLOps Stack](#mlops-stack)
  - [Governance Tags](#governance-tags)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Lineage Tracking](#lineage-tracking)

______________________________________________________________________

## Overview

OpenDataGov uses **DataHub** for centralized metadata management:

✅ **Data Discovery**: Search datasets, models, features across all platforms
✅ **Lineage Tracking**: Visualize Bronze → Silver → Gold → Platinum transformations
✅ **Schema Evolution**: Track schema changes over time
✅ **Governance Tags**: PII, GDPR, Gold layer, Production tags
✅ **Impact Analysis**: Understand downstream dependencies
✅ **ML Integration**: Track models, features, pipelines (MLflow, Feast, Kubeflow)

______________________________________________________________________

## Architecture

```
┌────────────────────────────────────────────────────────┐
│  DataHub Frontend (React UI)                          │
│  http://datahub-frontend:9002                         │
│  - Search & Discovery                                 │
│  - Lineage Visualization                              │
│  - Schema Browser                                     │
└────────────┬───────────────────────────────────────────┘
             │
┌────────────▼───────────────────────────────────────────┐
│  DataHub GMS (General Metadata Service)               │
│  http://datahub-gms:8080                              │
│  - GraphQL API                                        │
│  - REST API                                           │
│  - Metadata storage                                   │
└────────────┬───────────────────────────────────────────┘
             │
     ┌───────┼───────┬────────────┬──────────┐
     │       │       │            │          │
┌────▼────┐ │  ┌────▼────┐  ┌────▼────┐ ┌──▼──────┐
│PostgreSQL│ │  │Elasticsearch│ │ Kafka │ │Consumers│
│(Metadata)│ │  │  (Search)   │ │(Events)│ │ (MAE/MCE)│
└──────────┘ │  └─────────┘  └─────────┘ └─────────┘
             │
     ┌───────┼────────┬──────────┬────────────┐
     │       │        │          │            │
┌────▼────┐ ┌▼──────┐ ┌▼───────┐ ┌▼─────────┐
│Lakehouse│ │MLflow │ │ Feast  │ │ Kubeflow │
│(S3/Iceberg)│ │(Models)│ │(Features)│ │(Pipelines)│
└─────────┘ └───────┘ └────────┘ └──────────┘
```

### Components

| Component         | Purpose                        | Port |
| ----------------- | ------------------------------ | ---- |
| **GMS**           | Metadata API server            | 8080 |
| **Frontend**      | React UI for browsing          | 9002 |
| **MAE Consumer**  | Metadata Audit Event consumer  | -    |
| **MCE Consumer**  | Metadata Change Event consumer | -    |
| **PostgreSQL**    | Metadata storage               | 5432 |
| **Elasticsearch** | Search index                   | 9200 |
| **Kafka**         | Event streaming                | 9092 |

______________________________________________________________________

## Capabilities

### 1. Dataset Registration

Register datasets from medallion lakehouse:

```python
from odg_core.catalog import DataHubClient

client = DataHubClient(gms_url="http://datahub-gms:8080")

# Register Gold layer dataset
client.register_dataset(
    dataset_id="gold/finance/revenue",
    name="Revenue Data (Gold)",
    platform="s3",
    layer="gold",
    schema=[
        {"name": "transaction_id", "type": "STRING", "description": "Unique ID"},
        {"name": "amount", "type": "DECIMAL", "description": "Transaction amount"},
        {"name": "customer_id", "type": "STRING", "description": "Customer ID"},
        {"name": "date", "type": "DATE", "description": "Transaction date"},
    ],
    tags=["gold_layer", "production", "gdpr"],
    description="High-quality revenue data (DQ score >= 0.95)",
    owner="data-architect@company.com"
)
```

### 2. Lineage Tracking

Track data transformations through medallion layers:

```python
# Bronze → Silver lineage
client.add_lineage(
    downstream_urn="urn:li:dataset:(urn:li:dataPlatform:s3,silver/finance/revenue,PROD)",
    upstream_urns=["urn:li:dataset:(urn:li:dataPlatform:s3,bronze/raw/transactions,PROD)"],
    lineage_type="transformation",
    transformation_description="DQ validation + deduplication + schema standardization"
)

# Silver → Gold lineage
client.add_lineage(
    downstream_urn="urn:li:dataset:(urn:li:dataPlatform:s3,gold/finance/revenue,PROD)",
    upstream_urns=[
        "urn:li:dataset:(urn:li:dataPlatform:s3,silver/finance/revenue,PROD)",
        "urn:li:dataset:(urn:li:dataPlatform:s3,silver/crm/customers,PROD)"
    ],
    lineage_type="aggregation",
    transformation_description="Revenue aggregation with customer enrichment"
)
```

### 3. ML Model Registration

Register MLflow models with training dataset lineage:

```python
client.register_ml_model(
    model_name="customer-churn",
    model_version=3,
    mlflow_run_id="abc123def456",
    training_datasets=[
        "urn:li:dataset:(urn:li:dataPlatform:s3,gold/crm/customers,PROD)"
    ],
    features=["total_purchases", "avg_order_value", "days_since_last_purchase"],
    metrics={"accuracy": 0.92, "f1_score": 0.89, "auc": 0.94},
    tags=["production", "business_critical"]
)
```

### 4. Feature Store Integration

Register Feast feature views:

```python
client.register_feast_features(
    feature_view_name="customer_features",
    features=[
        {"name": "total_purchases", "type": "FLOAT", "description": "Total purchases"},
        {"name": "avg_order_value", "type": "FLOAT", "description": "Avg order value"},
        {"name": "days_since_last_purchase", "type": "INT64", "description": "Days since last purchase"},
    ],
    source_dataset_urn="urn:li:dataset:(urn:li:dataPlatform:s3,gold/features/customer,PROD)",
    materialization_interval="1h",
    tags=["online_serving", "production"]
)
```

### 5. Data Discovery

Search catalog with filters:

```python
# Search for production Gold datasets
results = client.search(
    query="revenue",
    entity_types=["dataset"],
    filters={"layer": "gold", "tags": ["production"]},
    limit=10
)

for result in results:
    print(f"{result['name']} ({result['platform']}, layer: {result['layer']})")
```

### 6. Impact Analysis

Get full lineage graph:

```python
# Get upstream lineage (data sources)
lineage = client.get_lineage(
    entity_urn="urn:li:dataset:(urn:li:dataPlatform:s3,gold/finance/revenue,PROD)",
    direction="upstream",
    max_hops=5
)

# Shows full chain: Bronze → Silver → Gold
```

______________________________________________________________________

## Deployment

### Quick Start

```bash
# Install DataHub
helm install datahub ./deploy/helm/opendatagov/charts/datahub \
  --namespace odg \
  --create-namespace

# Wait for DataHub to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=datahub -n odg --timeout=300s

# Access DataHub UI
kubectl port-forward -n odg svc/datahub-frontend 9002:9002

# Open browser
open http://localhost:9002
```

### Profile-Based Deployment

| Profile    | PostgreSQL             | Elasticsearch  | Kafka     | Use Case    |
| ---------- | ---------------------- | -------------- | --------- | ----------- |
| **dev**    | 1 replica, no pers     | 1 node, 10GB   | 1 broker  | Development |
| **medium** | 2 replicas, 50GB       | 3 nodes, 100GB | 3 brokers | Production  |
| **large**  | 3 replicas (HA), 200GB | 5 nodes, 500GB | 5 brokers | Enterprise  |

```bash
# Medium profile (production)
helm install datahub ./datahub \
  -f datahub/values-medium.yaml \
  --namespace odg
```

______________________________________________________________________

## Integration

### Medallion Lakehouse

Auto-register datasets when moving between layers:

```python
from odg_core.catalog import DataHubClient
from odg_core.lakehouse import LakehouseAgent

catalog = DataHubClient()
lakehouse = LakehouseAgent()

# When promoting Bronze → Silver
async def promote_to_silver(dataset_id: str):
    # Promote dataset
    result = await lakehouse.promote(
        dataset_id=dataset_id,
        source_layer="bronze",
        target_layer="silver"
    )

    # Register in DataHub
    catalog.register_dataset(
        dataset_id=f"silver/{dataset_id}",
        name=f"{dataset_id.replace('/', ' ').title()} (Silver)",
        platform="s3",
        layer="silver",
        schema=result.schema,
        tags=["silver_layer"],
        description="Validated and cleaned data"
    )

    # Add lineage
    catalog.add_lineage(
        downstream_urn=f"urn:li:dataset:(urn:li:dataPlatform:s3,silver/{dataset_id},PROD)",
        upstream_urns=[f"urn:li:dataset:(urn:li:dataPlatform:s3,bronze/{dataset_id},PROD)"],
        lineage_type="transformation",
        transformation_description="DQ validation + deduplication"
    )
```

### MLOps Stack

#### MLflow Integration

Register models after training:

```python
import mlflow
from odg_core.catalog import DataHubClient

catalog = DataHubClient()

# After MLflow model registration
with mlflow.start_run() as run:
    # Train model
    model.fit(X_train, y_train)

    # Log to MLflow
    mlflow.sklearn.log_model(model, "model")
    mlflow.log_metrics({"accuracy": 0.92, "f1": 0.89})

    # Register in DataHub
    catalog.register_ml_model(
        model_name="customer-churn",
        model_version=3,
        mlflow_run_id=run.info.run_id,
        training_datasets=["urn:li:dataset:(urn:li:dataPlatform:s3,gold/crm/customers,PROD)"],
        features=list(X_train.columns),
        metrics={"accuracy": 0.92, "f1_score": 0.89}
    )
```

#### Kubeflow Pipelines

Track pipeline lineage:

```python
from kfp import dsl
from odg_core.catalog import DataHubClient

catalog = DataHubClient()

@dsl.pipeline(name='train-customer-churn')
def train_pipeline(dataset_id: str, model_name: str):
    # Load data
    load_task = load_gold_dataset(dataset_id)

    # Train model
    train_task = train_model(data=load_task.output)

    # Register in DataHub after pipeline completes
    register_task = register_to_catalog(
        model_name=model_name,
        dataset_urn=f"urn:li:dataset:(urn:li:dataPlatform:s3,{dataset_id},PROD)",
        run_id=train_task.outputs['run_id']
    )
```

### Governance Tags

Tag datasets with governance metadata:

```python
# Tag PII datasets
catalog.add_tags(
    entity_urn="urn:li:dataset:(urn:li:dataPlatform:s3,gold/crm/customers,PROD)",
    tags=["pii", "gdpr", "gold_layer", "production"]
)

# Tag Gold layer datasets
catalog.add_tags(
    entity_urn="urn:li:dataset:(urn:li:dataPlatform:s3,gold/finance/revenue,PROD)",
    tags=["gold_layer", "production", "business_critical"]
)
```

**Supported Tags:**

| Tag                 | Description               | Color  | Use Case              |
| ------------------- | ------------------------- | ------ | --------------------- |
| `pii`               | Contains PII              | Red    | GDPR compliance       |
| `gdpr`              | GDPR regulated            | Orange | Privacy regulation    |
| `gold_layer`        | High quality (DQ >= 0.95) | Gold   | Quality certification |
| `production`        | Production-ready          | Green  | Deployment status     |
| `business_critical` | Business critical         | Purple | Impact classification |

______________________________________________________________________

## Lineage Tracking

### Medallion Lakehouse Lineage

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│  Bronze  │─────▶│  Silver  │─────▶│   Gold   │─────▶│ Platinum │
│  (Raw)   │      │(Validated)│     │(Enriched)│      │(Aggregated)│
└──────────┘      └──────────┘      └──────────┘      └──────────┘
  Raw data        DQ validation     Business logic    Analytics
  from sources    + dedup           + enrichment      + ML features
```

### ML Pipeline Lineage

```
┌────────────┐
│ Gold Data  │
└──────┬─────┘
       │
       ▼
┌────────────┐      ┌────────────┐
│   Feast    │─────▶│  Training  │
│  Features  │      │  Pipeline  │
└────────────┘      └──────┬─────┘
                           │
                           ▼
                    ┌────────────┐      ┌────────────┐
                    │ MLflow     │─────▶│  KServe    │
                    │ Model      │      │ Deployment │
                    └────────────┘      └────────────┘
```

______________________________________________________________________

## API Reference

### DataHubClient

```python
from odg_core.catalog import DataHubClient

client = DataHubClient(
    gms_url="http://datahub-gms:8080",
    frontend_url="http://datahub-frontend:9002"
)
```

#### Methods

**Dataset Registration:**

```python
client.register_dataset(
    dataset_id: str,
    name: str,
    platform: str,
    layer: str,
    schema: list[dict],
    tags: list[str] | None = None,
    description: str | None = None,
    owner: str | None = None
) -> dict
```

**Lineage Tracking:**

```python
client.add_lineage(
    downstream_urn: str,
    upstream_urns: list[str],
    lineage_type: str = "transformation",
    transformation_description: str | None = None
) -> dict
```

**ML Model Registration:**

```python
client.register_ml_model(
    model_name: str,
    model_version: int,
    mlflow_run_id: str,
    training_datasets: list[str],
    features: list[str],
    metrics: dict[str, float],
    tags: list[str] | None = None
) -> dict
```

**Feature Store Integration:**

```python
client.register_feast_features(
    feature_view_name: str,
    features: list[dict],
    source_dataset_urn: str,
    materialization_interval: str,
    tags: list[str] | None = None
) -> dict
```

**Tag Management:**

```python
client.add_tags(
    entity_urn: str,
    tags: list[str]
) -> dict
```

**Search:**

```python
client.search(
    query: str,
    entity_types: list[str] | None = None,
    filters: dict | None = None,
    limit: int = 20
) -> list[dict]
```

**Lineage Query:**

```python
client.get_lineage(
    entity_urn: str,
    direction: str = "both",  # upstream, downstream, both
    max_hops: int = 3
) -> dict
```

______________________________________________________________________

## Examples

### Example 1: Complete Medallion Flow

```python
from odg_core.catalog import DataHubClient

client = DataHubClient()

# 1. Register Bronze dataset
bronze_urn = client.register_dataset(
    dataset_id="bronze/raw/transactions",
    name="Raw Transactions (Bronze)",
    platform="s3",
    layer="bronze",
    schema=[
        {"name": "id", "type": "STRING"},
        {"name": "amount", "type": "STRING"},  # Not validated yet
        {"name": "date", "type": "STRING"},
    ],
    tags=["bronze_layer"],
    owner="data-engineer@company.com"
)['urn']

# 2. Register Silver dataset with lineage
silver_urn = client.register_dataset(
    dataset_id="silver/finance/transactions",
    name="Validated Transactions (Silver)",
    platform="s3",
    layer="silver",
    schema=[
        {"name": "id", "type": "STRING"},
        {"name": "amount", "type": "DECIMAL"},  # Validated type
        {"name": "date", "type": "DATE"},
    ],
    tags=["silver_layer"],
    owner="data-engineer@company.com"
)['urn']

client.add_lineage(
    downstream_urn=silver_urn,
    upstream_urns=[bronze_urn],
    lineage_type="transformation",
    transformation_description="DQ validation + type casting"
)

# 3. Register Gold dataset with lineage
gold_urn = client.register_dataset(
    dataset_id="gold/finance/revenue",
    name="Revenue Data (Gold)",
    platform="s3",
    layer="gold",
    schema=[
        {"name": "transaction_id", "type": "STRING"},
        {"name": "amount", "type": "DECIMAL"},
        {"name": "customer_id", "type": "STRING"},
        {"name": "date", "type": "DATE"},
    ],
    tags=["gold_layer", "production"],
    owner="data-architect@company.com"
)['urn']

client.add_lineage(
    downstream_urn=gold_urn,
    upstream_urns=[silver_urn],
    lineage_type="enrichment",
    transformation_description="Customer enrichment + business logic"
)
```

### Example 2: ML Model with Full Lineage

```python
import mlflow
from odg_core.catalog import DataHubClient

client = DataHubClient()

# Train model
with mlflow.start_run() as run:
    model.fit(X_train, y_train)
    mlflow.sklearn.log_model(model, "model")

    # Register model with lineage
    model_metadata = client.register_ml_model(
        model_name="customer-churn",
        model_version=3,
        mlflow_run_id=run.info.run_id,
        training_datasets=[
            "urn:li:dataset:(urn:li:dataPlatform:s3,gold/crm/customers,PROD)"
        ],
        features=["total_purchases", "avg_order_value", "days_since_last_purchase"],
        metrics={"accuracy": 0.92, "f1_score": 0.89},
        tags=["production"]
    )

# Get full lineage: Data → Features → Model
lineage = client.get_lineage(
    entity_urn=model_metadata['urn'],
    direction="upstream",
    max_hops=10
)
# Shows: Bronze → Silver → Gold → Features → Model
```

______________________________________________________________________

## Monitoring

### Metrics

DataHub exposes Prometheus metrics at `/metrics`:

- `datahub_gms_requests_total` - Total GMS requests
- `datahub_search_queries_total` - Search queries
- `datahub_lineage_queries_total` - Lineage queries
- `datahub_metadata_changes_total` - Metadata change events

### Grafana Dashboards

Import from `/deploy/grafana-dashboards/`:

- `datahub-overview.json` - Overall metrics
- `datahub-lineage.json` - Lineage query performance
- `datahub-search.json` - Search performance

______________________________________________________________________

## Next Steps

- Read [MLOps Documentation](MLOPS.md) for ML pipeline integration
- See [Lakehouse Architecture](ARCHITECTURE.md) for medallion layers
- Check [Governance](GOVERNANCE.md) for B-Swarm integration

______________________________________________________________________

**Version**: 0.1.0
**Last Updated**: 2026-02-08
**DataHub Version**: 0.12.0
