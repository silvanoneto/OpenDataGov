# Data Catalog Architecture - Event-Driven Metadata Ingestion

Complete architecture for **automatic metadata catalog population** using event-driven design.

## Overview

OpenDataGov implements **zero-touch metadata management**: as data moves through the platform (Bronze → Silver → Gold, ML training, feature engineering), metadata is automatically captured and registered in DataHub.

```
┌─────────────────────────────────────────────────────────────┐
│  Data Operations (Lakehouse, MLOps, Features)               │
│  - Dataset promotions                                       │
│  - Model training                                           │
│  - Feature materialization                                  │
└──────────────┬──────────────────────────────────────────────┘
               │ Emit Kafka Events
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Kafka Topics                                               │
│  - odg.lakehouse.promotion                                  │
│  - odg.mlflow.model.registered                             │
│  - odg.feast.materialization                                │
│  - odg.kubeflow.pipeline.completed                          │
└──────────────┬──────────────────────────────────────────────┘
               │ Consumed by
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Metadata Ingestion Service                                 │
│  - Listens to events                                        │
│  - Calls DataHub API                                        │
│  - Registers metadata + lineage                             │
└──────────────┬──────────────────────────────────────────────┘
               │ Updates
               ▼
┌─────────────────────────────────────────────────────────────┐
│  DataHub                                                     │
│  - Metadata storage                                         │
│  - Lineage graph                                            │
│  - Search index                                             │
│  - UI for discovery                                         │
└─────────────────────────────────────────────────────────────┘
```

______________________________________________________________________

## Components

### 1. Event Emitters

**Location**: `odg-core/catalog/events.py`

Emit Kafka events whenever metadata changes:

```python
from odg_core.catalog.events import get_emitter

emitter = get_emitter()

# Lakehouse promotion
emitter.emit_lakehouse_promotion(
    dataset_id="finance/revenue",
    source_layer="bronze",
    target_layer="silver",
    schema=[...],
    dq_score=0.96,
    promoted_by="user@company.com"
)

# MLflow model registration
emitter.emit_mlflow_model_registered(
    model_name="customer-churn",
    model_version=3,
    training_datasets=["gold/crm/customers"],
    features=[...],
    metrics={"accuracy": 0.92}
)
```

### 2. Kafka Topics

| Topic                             | Event Type              | Trigger            | Payload                                |
| --------------------------------- | ----------------------- | ------------------ | -------------------------------------- |
| `odg.lakehouse.promotion`         | Dataset promotion       | Bronze→Silver→Gold | dataset_id, layers, schema, DQ score   |
| `odg.mlflow.model.registered`     | Model registration      | MLflow register    | model_name, version, datasets, metrics |
| `odg.feast.materialization`       | Feature materialization | Feast materialize  | feature_view, features, source         |
| `odg.kubeflow.pipeline.completed` | Pipeline completion     | Kubeflow success   | pipeline_name, inputs, outputs         |

### 3. Metadata Ingestion Service

**Location**: `services/metadata-ingestion/`

Kafka consumer that automatically registers metadata in DataHub:

```python
from metadata_ingestion import MetadataIngestionService

service = MetadataIngestionService(
    kafka_bootstrap_servers="kafka:9092",
    datahub_gms_url="http://datahub-gms:8080"
)

service.start()  # Runs forever, consuming events
```

**Processing Logic**:

1. **Lakehouse Promotion**:

   - Register dataset in DataHub
   - Add governance tags (layer, PII, GDPR, production)
   - Create lineage: source_layer → target_layer
   - Auto-tag based on DQ score (≥0.95 = gold_layer)

1. **MLflow Model**:

   - Register model in DataHub
   - Create lineage: training_datasets → model
   - Record performance metrics

1. **Feast Features**:

   - Register feature view in DataHub
   - Create lineage: source_dataset → feature_table

1. **Kubeflow Pipeline**:

   - Create lineage: input_datasets → output_model
   - Track pipeline execution metadata

### 4. DataHub Client

**Location**: `odg-core/catalog/datahub_client.py`

Python client with HTTP integration:

```python
from odg_core.catalog import DataHubClient

client = DataHubClient(gms_url="http://datahub-gms:8080")

# Register dataset (called by Metadata Ingestion Service)
client.register_dataset(
    dataset_id="gold/finance/revenue",
    platform="s3",
    layer="gold",
    schema=[...],
    tags=["gold_layer", "production"]
)

# Add lineage
client.add_lineage(
    downstream_urn="urn:li:dataset:(...,gold/finance/revenue,PROD)",
    upstream_urns=["urn:li:dataset:(...,silver/finance/revenue,PROD)"],
    lineage_type="transformation"
)
```

______________________________________________________________________

## Integration Points

### Lakehouse Agent

Emit events when promoting datasets:

```python
from odg_core.lakehouse import LakehouseAgent
from odg_core.catalog.events import get_emitter

agent = LakehouseAgent()
emitter = get_emitter()

# Promote dataset
result = await agent.promote(
    dataset_id="finance/revenue",
    source_layer="bronze",
    target_layer="silver"
)

# Emit event for automatic metadata ingestion
emitter.emit_lakehouse_promotion(
    dataset_id="finance/revenue",
    source_layer="bronze",
    target_layer="silver",
    schema=result.schema,
    dq_score=result.dq_score,
    promoted_by=user.email
)

# DataHub automatically updated via Kafka event!
```

### MLflow Integration

Hook into MLflow model registration:

```python
import mlflow
from odg_core.catalog.events import get_emitter

emitter = get_emitter()

# Train and register model
with mlflow.start_run() as run:
    model.fit(X_train, y_train)
    mlflow.sklearn.log_model(model, "model")
    mlflow.log_metrics({"accuracy": 0.92})

# Emit event for DataHub
emitter.emit_mlflow_model_registered(
    model_name="customer-churn",
    model_version=3,
    mlflow_run_id=run.info.run_id,
    training_datasets=["gold/crm/customers"],
    features=list(X_train.columns),
    metrics={"accuracy": 0.92}
)

# DataHub lineage: gold/crm/customers → customer-churn v3
```

### Feast Integration

Hook into Feast materialization:

```python
from feast import FeatureStore
from odg_core.catalog.events import get_emitter

fs = FeatureStore(repo_path=".")
emitter = get_emitter()

# Materialize features
fs.materialize(
    start_date=datetime(2026, 1, 1),
    end_date=datetime(2026, 2, 8)
)

# Emit event for DataHub
emitter.emit_feast_materialization(
    feature_view="customer_features",
    features=[...],
    source_dataset="gold/features/customer",
    materialization_interval="1h"
)

# DataHub lineage: gold/features/customer → customer_features
```

______________________________________________________________________

## Deployment

### 1. Deploy DataHub + Metadata Ingestion

```bash
# Install DataHub with metadata ingestion service
helm install datahub ./deploy/helm/opendatagov/charts/datahub \
  --namespace odg \
  --create-namespace

# Verify deployment
kubectl get pods -n odg -l app.kubernetes.io/name=datahub

# Expected pods:
# - datahub-gms
# - datahub-frontend
# - datahub-metadata-ingestion
# - datahub-postgresql
# - datahub-elasticsearch
# - datahub-kafka
```

### 2. Enable Event Emitters

**In application code**:

```python
from odg_core.catalog.events import get_emitter

# Initialize global emitter (once at startup)
emitter = get_emitter(
    kafka_bootstrap_servers="kafka:9092",
    enabled=True  # Set to False to disable catalog events
)
```

**Environment variable**:

```bash
export CATALOG_EVENTS_ENABLED=true
export KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

### 3. Verify Metadata Ingestion

```bash
# Check metadata ingestion service logs
kubectl logs -n odg -l app.kubernetes.io/component=metadata-ingestion -f

# Expected output:
# Metadata Ingestion Service initialized (topics: [...])
# Starting metadata ingestion service...
# Processing lakehouse promotion: finance/revenue (bronze → silver)
# ✓ Registered silver/finance/revenue in DataHub
```

______________________________________________________________________

## Lineage Examples

### Example 1: Medallion Lakehouse

**Operations**:

1. Ingest raw data → Bronze
1. Validate & clean → Silver (DQ score: 0.96)
1. Enrich & transform → Gold (DQ score: 0.98)
1. Aggregate → Platinum

**Automatic Lineage in DataHub**:

```
┌─────────┐      ┌─────────┐      ┌─────────┐      ┌──────────┐
│ Bronze  │─────▶│ Silver  │─────▶│  Gold   │─────▶│ Platinum │
│ (Raw)   │      │(Validated)     │(Enriched)│     │(Aggregated)
└─────────┘      └─────────┘      └─────────┘      └──────────┘
  Event 1          Event 2          Event 3          Event 4
```

Each arrow = Kafka event → Metadata Ingestion → DataHub lineage

### Example 2: ML Pipeline

**Operations**:

1. Load Gold data
1. Engineer features (Feast)
1. Train model (Kubeflow + MLflow)
1. Deploy model (KServe)

**Automatic Lineage in DataHub**:

```
┌────────────┐      ┌──────────┐      ┌─────────┐      ┌─────────┐
│ Gold Data  │─────▶│  Feast   │─────▶│ MLflow  │─────▶│ KServe  │
│            │      │ Features │      │  Model  │      │ Deploy  │
└────────────┘      └──────────┘      └─────────┘      └─────────┘
  (lakehouse         (feast            (mlflow          (kubeflow
   event)            event)            event)           event)
```

**Full lineage tracked**:

- Bronze → Silver → Gold → Feast → MLflow → KServe

______________________________________________________________________

## Governance Tags

Automatically applied based on context:

| Tag                 | Auto-Applied When                      | Use Case              |
| ------------------- | -------------------------------------- | --------------------- |
| `{layer}_layer`     | Dataset promoted to layer              | Layer classification  |
| `gold_layer`        | DQ score ≥ 0.95 + Gold layer           | Quality certification |
| `production`        | DQ score ≥ 0.98                        | Production readiness  |
| `pii`               | Schema contains PII field              | GDPR compliance       |
| `gdpr`              | PII detected                           | Privacy regulation    |
| `business_critical` | Manual tag or model metric > threshold | Impact classification |

______________________________________________________________________

## Monitoring

### Metadata Ingestion Metrics

```bash
# Prometheus metrics exposed at :8080/metrics
metadata_ingestion_events_total{topic="odg.lakehouse.promotion"} 42
metadata_ingestion_events_processed{topic="odg.lakehouse.promotion",status="success"} 40
metadata_ingestion_events_processed{topic="odg.lakehouse.promotion",status="failed"} 2
metadata_ingestion_processing_duration_seconds{topic="odg.lakehouse.promotion"} 0.123
```

### DataHub Metrics

```bash
# DataHub GMS metrics
datahub_gms_requests_total{endpoint="/entities"} 150
datahub_search_queries_total 25
datahub_lineage_queries_total 10
```

### Grafana Dashboard

Import `deploy/grafana-dashboards/metadata-catalog.json`:

- Events per topic (rate)
- Ingestion success rate
- Processing latency
- DataHub search/lineage queries

______________________________________________________________________

## Troubleshooting

### Events not ingested

**Check Kafka connectivity**:

```bash
kubectl exec -n odg deployment/datahub-metadata-ingestion -- \
  nc -zv kafka 9092
```

**Check consumer logs**:

```bash
kubectl logs -n odg -l app.kubernetes.io/component=metadata-ingestion
```

### DataHub not updating

**Check GMS connectivity**:

```bash
kubectl exec -n odg deployment/datahub-metadata-ingestion -- \
  curl http://datahub-gms:8080/health
```

**Verify API calls**:

```bash
# Check metadata ingestion logs for HTTP errors
kubectl logs -n odg -l app.kubernetes.io/component=metadata-ingestion | grep "Failed to"
```

### Missing lineage

**Verify event order**:

- Upstream dataset must be registered before downstream
- Events processed in order per partition

**Check event payloads**:

```bash
# Consume Kafka topic to inspect events
kubectl exec -n odg deployment/kafka-0 -- \
  kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 \
    --topic odg.lakehouse.promotion \
    --from-beginning \
    --max-messages 10
```

______________________________________________________________________

## Benefits

✅ **Zero-Touch Metadata**: No manual registration required
✅ **Real-Time Updates**: Metadata updated as data flows
✅ **Complete Lineage**: Automatic end-to-end tracking
✅ **Governance Integration**: Tags auto-applied (PII, GDPR, quality)
✅ **Audit Trail**: All events logged to Kafka
✅ **Decoupled Architecture**: Services don't directly call DataHub
✅ **Scalable**: Event-driven, async processing
✅ **Resilient**: Failed events can be retried

______________________________________________________________________

## Next Steps

- Read [Data Catalog Documentation](DATA_CATALOG.md) for API reference
- See [examples/catalog_integration.py](../examples/catalog_integration.py) for code examples
- Review [Lakehouse Architecture](ARCHITECTURE.md) for medallion layers
- Check [MLOps Documentation](MLOPS.md) for ML pipeline integration

______________________________________________________________________

**Version**: 0.1.0
**Last Updated**: 2026-02-08
**Architecture**: Event-Driven Metadata Ingestion
