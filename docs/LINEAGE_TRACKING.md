# Data Lineage Tracking Guide

## Overview

OpenDataGov provides **enterprise-grade lineage tracking** using JanusGraph (distributed graph database) to capture complete data provenance from ingestion to model deployment.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DATA SOURCES                          │
│  APIs • Web • S3 • FTP • Databases • CDC Events         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│               LINEAGE CAPTURE POINTS                     │
│  • Connector.ingest() → OpenLineage event               │
│  • Pipeline.execute() → Graph: GENERATED_BY edge        │
│  • Model.train() → Graph: TRAINED_ON edge               │
│  • Dataset.promote() → Graph: DERIVED_FROM edge         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                JANUSGRAPH (Graph DB)                     │
│  Backend: Cassandra (3 nodes, HA)                       │
│  Search: Lucene embedded                                │
│  Query: Gremlin + GraphQL                               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  QUERY INTERFACES                        │
│  • GraphQL API (queries + mutations)                    │
│  • Python Client (JanusGraphClient)                     │
│  • Gremlin Console (advanced queries)                   │
└─────────────────────────────────────────────────────────┘
```

## Graph Schema

### Vertex Labels (Nodes)

| Label      | Description       | Key Properties                                                     |
| ---------- | ----------------- | ------------------------------------------------------------------ |
| `Dataset`  | Data at any layer | `dataset_id`, `layer`, `version` (Iceberg snapshot)                |
| `Pipeline` | ETL/ELT job       | `pipeline_id`, `version`, `pipeline_type` (spark, airflow, duckdb) |
| `Model`    | ML model          | `model_name`, `version`, `framework`                               |
| `Feature`  | Feature view      | `feature_view`, `feature_names`                                    |

### Edge Labels (Relationships)

| Label          | From → To          | Description                                 |
| -------------- | ------------------ | ------------------------------------------- |
| `DERIVED_FROM` | Dataset → Dataset  | Dataset derivation (bronze → silver → gold) |
| `GENERATED_BY` | Dataset ← Pipeline | Pipeline output                             |
| `TRAINED_ON`   | Model → Dataset    | Model training data                         |
| `CONSUMES`     | Pipeline → Dataset | Pipeline input                              |
| `PRODUCES`     | Pipeline → Feature | Feature materialization                     |

## Usage Examples

### Python Client

#### 1. Record Pipeline Execution

```python
from odg_core.graph import JanusGraphClient

client = JanusGraphClient()
client.connect()

# Record that pipeline generated a dataset
client.add_pipeline_generates_dataset(
    pipeline_id="spark_aggregate_sales",
    pipeline_version=5,
    dataset_id="silver/sales_aggregated",
    dataset_version="snapshot_abc123"  # Iceberg snapshot
)
```

#### 2. Record Model Training

```python
# Record datasets used for model training
client.add_model_trained_on_dataset(
    model_name="churn_predictor",
    model_version=3,
    dataset_id="gold/customers",
    dataset_version="snapshot_def456"  # For reproducibility!
)
```

#### 3. Query Upstream Lineage

```python
# Get all datasets that led to this one
upstream = client.get_upstream_datasets("gold/sales_aggregated", max_depth=10)

for dataset in upstream:
    print(f"- {dataset['dataset_id']} (layer: {dataset['layer']})")
```

**Output:**

```
- silver/sales_aggregated (layer: silver)
- bronze/sales (layer: bronze)
- bronze/products (layer: bronze)
```

#### 4. Get Model Training Lineage

```python
lineage = client.get_model_training_lineage("churn_predictor", version=3)

print(f"Model: {lineage['model']['model_name']}")
print("Training datasets:")
for ds in lineage['training_datasets']:
    print(f"  - {ds['dataset_id']} @ {ds.get('version', 'no snapshot')}")
```

**Output:**

```
Model: churn_predictor
Training datasets:
  - gold/customers @ snapshot_def456
  - gold/transactions @ snapshot_ghi789
```

#### 5. Impact Analysis

```python
consumers = client.get_dataset_consumers("silver/customers")

print(f"Models using this dataset: {len(consumers['models'])}")
for model in consumers['models']:
    print(f"  - {model['model_name']} v{model['version']}")

print(f"Pipelines using this dataset: {len(consumers['pipelines'])}")
```

### GraphQL Queries

#### Query 1: Dataset Lineage

```graphql
query {
  datasetLineage(datasetId: "gold/customers", depth: 5) {
    datasetId
    layer
    upstreamCount

    upstreamDatasets {
      name
      properties
    }

    consumingModels {
      name
      properties
    }
  }
}
```

#### Query 2: Model Reproducibility Check

```graphql
query {
  modelLineage(modelName: "churn_predictor", modelVersion: 5) {
    modelName
    modelVersion
    isReproducible  # ✅ if has Iceberg snapshots

    trainingDatasets {
      name
      properties
    }

    datasetSnapshots  # Iceberg snapshot IDs
  }
}
```

#### Query 3: Full Lineage Graph (for visualization)

```graphql
query {
  lineageGraph(
    nodeId: "gold/customers",
    nodeType: "Dataset",
    depth: 3
  ) {
    nodeCount
    edgeCount

    nodes {
      id
      label  # Dataset, Model, Pipeline
      name
    }

    edges {
      label  # DERIVED_FROM, TRAINED_ON, etc.
      source
      target
    }
  }
}
```

**Frontend Visualization:**

```javascript
// Use D3.js, Cytoscape, or vis.js
const graph = await fetch('/graphql', {
  method: 'POST',
  body: JSON.stringify({ query: lineageGraphQuery })
}).then(r => r.json());

// Render interactive graph
renderLineageGraph(graph.data.lineageGraph);
```

#### Mutation 1: Record Pipeline Execution (auto-called by VersionedSparkJob)

```graphql
mutation {
  recordPipelineExecution(
    pipelineId: "spark_aggregate_sales",
    pipelineVersion: 5,
    inputDatasets: ["bronze/sales", "bronze/products"],
    outputDatasets: ["silver/sales_aggregated"]
  )
}
```

#### Mutation 2: Record Dataset Promotion

```graphql
mutation {
  recordDatasetPromotion(
    sourceDataset: "silver/customers",
    targetDataset: "gold/customers",
    transformation: "DQ validation + PII masking"
  )
}
```

## Integration with Other Components

### 1. Automatic Lineage from Versioned Pipelines

**Spark:**

```python
from odg_core.spark.job_versioning import VersionedSparkJob

job = VersionedSparkJob(
    job_name="transform_sales",
    job_file=__file__,
    input_datasets=["bronze/sales"],
    output_datasets=["silver/sales"]
)

# Lineage automatically recorded when you call:
job.emit_lineage()  # → OpenLineage event → JanusGraph
```

**DuckDB:**

```python
from odg_core.duckdb.versioned_query import create_versioned_query

job = create_versioned_query(
    job_name="aggregate_orders",
    sql_query="SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id",
    input_tables=["orders"],
    output_table="customer_order_counts"
)

# Lineage captured on execute()
result = job.execute(conn)  # → Lineage recorded
```

### 2. Iceberg Integration

**Store dataset versions (snapshots) in lineage:**

```python
from odg_core.storage.iceberg_catalog import IcebergCatalog

iceberg = IcebergCatalog()
snapshot_id = iceberg.get_snapshot_id("gold", "customers")

# Use snapshot in lineage for reproducibility
client.add_dataset(
    dataset_id="gold/customers",
    layer="gold",
    version=snapshot_id  # Critical for time-travel!
)
```

### 3. MLflow Integration

**Track model lineage to MLflow:**

```python
import mlflow

# Train model
with mlflow.start_run():
    model.fit(X_train, y_train)
    mlflow.sklearn.log_model(model, "model")

    # Log lineage metadata
    mlflow.log_param("training_dataset", "gold/customers")
    mlflow.log_param("dataset_snapshot", snapshot_id)

# Record in graph
client.add_model_trained_on_dataset(
    model_name="churn_predictor",
    model_version=run.info.run_id,
    dataset_id="gold/customers",
    dataset_version=snapshot_id
)
```

## Use Cases

### Use Case 1: Debugging Model Degradation

**Problem:** Model accuracy dropped from 95% to 85% on 2026-02-01.

**Solution:**

```python
# 1. Find which dataset was used for training
lineage = client.get_model_training_lineage("churn_predictor", version=5)
dataset_snapshot = lineage['training_datasets'][0]['version']

# 2. Compare with current data
iceberg = IcebergCatalog()
historical_data = iceberg.time_travel("gold", "customers", dataset_snapshot)
current_data = iceberg.time_travel("gold", "customers", "latest")

# 3. Identify schema drift
compare_schemas(historical_data, current_data)
```

### Use Case 2: Impact Analysis Before Schema Change

**Problem:** Need to add PII masking to `silver/customers`, but don't know what will break.

**Solution:**

```graphql
query {
  impactAnalysis(datasetId: "silver/customers", changeType: "schema") {
    totalAffected
    severity  # HIGH if > 20 affected nodes

    affectedModels {
      name
    }

    affectedPipelines {
      name
    }
  }
}
```

**Output:**

```json
{
  "totalAffected": 12,
  "severity": "MEDIUM",
  "affectedModels": [
    {"name": "churn_predictor"},
    {"name": "ltv_model"}
  ],
  "affectedPipelines": [
    {"name": "aggregate_customer_features"},
    {"name": "generate_reports"}
  ]
}
```

**Action:** Notify model owners before making the change.

### Use Case 3: Compliance Audit

**Question:** "Which datasets were used to train the credit_risk_model v3 deployed on 2026-01-15?"

**Solution:**

```python
lineage = client.get_model_training_lineage("credit_risk_model", version=3)

audit_report = {
    "model": "credit_risk_model v3",
    "training_date": "2026-01-15",
    "datasets": [
        {
            "id": ds['dataset_id'],
            "snapshot": ds['version'],
            "retrievable": True  # Can time-travel to exact data
        }
        for ds in lineage['training_datasets']
    ]
}

# ✅ Passes EU AI Act compliance check
```

## Advanced Queries

### Gremlin Console

For advanced users, connect directly to JanusGraph:

```bash
kubectl exec -it janusgraph-0 -- ./bin/gremlin.sh
```

```groovy
// Find all paths from bronze to model
g.V().has('Dataset', 'layer', 'bronze')
  .repeat(bothE().otherV().simplePath())
  .until(hasLabel('Model'))
  .path()
  .limit(10)

// Find datasets with no consumers (orphaned data)
g.V().hasLabel('Dataset')
  .not(in('TRAINED_ON'))
  .not(in('GENERATED_BY'))
  .values('dataset_id')

// Find models without reproducible lineage (no snapshots)
g.V().hasLabel('Model')
  .out('TRAINED_ON')
  .has('version', null)
  .in('TRAINED_ON')
  .dedup()
  .values('model_name')
```

## Performance Considerations

### Cassandra Backend

- **Replication Factor:** 3 (HA)
- **Consistency Level:** QUORUM (reads + writes)
- **Compaction:** Size-tiered (optimized for writes)

### Query Optimization

```python
# ✅ Good: Limited depth
upstream = client.get_upstream_datasets("gold/customers", max_depth=5)

# ❌ Bad: Unbounded traversal
upstream = client.get_upstream_datasets("gold/customers", max_depth=100)
```

### Caching

JanusGraph uses database-level caching:

- **db-cache-size:** 0.25 (25% of heap)
- **db-cache-time:** 180s TTL

## Monitoring

### Metrics (Prometheus)

- `janusgraph_queries_total` - Total queries executed
- `janusgraph_query_duration_ms` - Query latency (P95, P99)
- `cassandra_read_latency_ms` - Backend read latency

### Grafana Dashboard

Pre-configured dashboard: `Lineage Graph Performance`

**Alerts:**

- Query latency P95 > 500ms
- Cassandra node down
- JanusGraph connection errors

## Backup & Recovery

### Manual Backup

```bash
# Backup Cassandra keyspace
kubectl exec cassandra-0 -- nodetool snapshot janusgraph

# Export to S3
kubectl exec cassandra-0 -- \
  tar czf - /var/lib/cassandra/data/janusgraph | \
  aws s3 cp - s3://backups/janusgraph-$(date +%Y%m%d).tar.gz
```

### Restore

```bash
# Download from S3
aws s3 cp s3://backups/janusgraph-20260208.tar.gz - | \
  kubectl exec -i cassandra-0 -- tar xzf -

# Restore snapshot
kubectl exec cassandra-0 -- nodetool refresh janusgraph
```

## Troubleshooting

### Issue: Lineage not appearing in graph

**Check:**

1. Is JanusGraph running? `kubectl get pods -l app=janusgraph`
1. Can client connect? `telnet janusgraph 8182`
1. Are lineage events being emitted? Check logs for `emit_lineage_event`

**Solution:**

```python
# Test connection
client = JanusGraphClient()
client.connect()  # Should not throw error

# Manually add test node
client.add_dataset("test/dataset", "bronze")
```

### Issue: Slow queries

**Check Gremlin query plan:**

```groovy
g.V().has('Dataset', 'dataset_id', 'gold/customers')
  .out('DERIVED_FROM')
  .profile()  # Shows execution plan
```

**Solutions:**

- Add indexes: `mgmt.buildIndex('datasetIdIndex', Vertex.class).addKey(dataset_id).buildCompositeIndex()`
- Reduce traversal depth
- Use `limit()` in queries

## References

- [JanusGraph Documentation](https://docs.janusgraph.org/)
- [Gremlin Query Language](https://tinkerpop.apache.org/gremlin.html)
- [OpenLineage Spec](https://openlineage.io/)
- [Apache Iceberg Time Travel](https://iceberg.apache.org/docs/latest/spark-queries/#time-travel)
