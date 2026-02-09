# Advanced Versioning & Performance Optimization Guide

This guide covers advanced features for version management, performance optimization, and operational best practices in OpenDataGov.

## Table of Contents

1. [Version Comparison](#version-comparison)
1. [Snapshot Tagging](#snapshot-tagging)
1. [Retention Policies](#retention-policies)
1. [Compaction](#compaction)
1. [Monitoring & Observability](#monitoring--observability)
1. [Best Practices](#best-practices)

______________________________________________________________________

## Version Comparison

Compare schemas, data, and performance metrics between different versions of datasets, models, and pipelines.

### Dataset Schema Comparison

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://lakehouse-agent:8000/api/v1/compare/datasets/gold/customers/schema",
        params={
            "from_version": "1234567890",  # Older snapshot
            "to_version": "1234567999"     # Newer snapshot
        }
    )

    comparison = response.json()
    print(f"Added columns: {comparison['added_columns']}")
    print(f"Removed columns: {comparison['removed_columns']}")
    print(f"Type changes: {comparison['type_changes']}")
```

**Output:**

```json
{
  "from_version": "1234567890",
  "to_version": "1234567999",
  "added_columns": ["customer_segment", "lifetime_value"],
  "removed_columns": [],
  "common_columns": ["customer_id", "name", "email", "created_at"],
  "type_changes": {
    "created_at": {
      "from": "string",
      "to": "timestamp"
    }
  }
}
```

### Dataset Data Comparison

```python
response = await client.get(
    "http://lakehouse-agent:8000/api/v1/compare/datasets/gold/customers/data",
    params={
        "from_version": "1234567890",
        "to_version": "1234567999",
        "sample_size": 10
    }
)

comparison = response.json()
print(f"Rows added: {comparison['rows_added']}")
print(f"Rows removed: {comparison['rows_removed']}")
```

### Model Performance Comparison

```python
response = await client.get(
    "http://lakehouse-agent:8000/api/v1/compare/models/churn_predictor/performance",
    params={
        "from_version": 1,
        "to_version": 2
    }
)

comparison = response.json()

for metric, values in comparison["metrics_diff"].items():
    print(f"{metric}:")
    print(f"  {values['from']} → {values['to']}")
    print(f"  Delta: {values['delta']} ({values['percent_change']:.2f}%)")

# Check if training data changed
if comparison["training_data_changed"]:
    print("⚠️  Training data changed between versions")
```

**Output:**

```
accuracy:
  0.85 → 0.92
  Delta: 0.07 (8.24%)
f1_score:
  0.83 → 0.90
  Delta: 0.07 (8.43%)
⚠️  Training data changed between versions
```

### Pipeline Version Comparison

```python
response = await client.get(
    "http://lakehouse-agent:8000/api/v1/compare/pipelines/transform_sales/versions",
    params={
        "from_version": 5,
        "to_version": 6
    }
)

comparison = response.json()
if comparison["dag_changed"]:
    print("DAG structure changed!")
if comparison["code_changed"]:
    print("Transformation code changed!")
```

______________________________________________________________________

## Snapshot Tagging

Tag important snapshots with semantic labels for easy reference and protection from cleanup.

### Tag a Production Snapshot

```python
from odg_core.storage.iceberg_catalog import IcebergCatalog

catalog = IcebergCatalog()

# Get current snapshot
current_snapshot = catalog.get_snapshot_id("gold", "customers")

# Tag it as production
catalog.tag_snapshot(
    namespace="gold",
    table_name="customers",
    snapshot_id=current_snapshot,
    tag="production_2026_02_15"
)

print(f"Tagged snapshot {current_snapshot} as production_2026_02_15")
```

### Time-Travel Using Tags

```python
# Read data from tagged snapshot
prod_data = catalog.time_travel_by_tag(
    namespace="gold",
    table_name="customers",
    tag="production_2026_02_15"
)

print(f"Retrieved {len(prod_data)} rows from production snapshot")
```

### Common Tagging Conventions

- **Production releases**: `production_YYYY_MM_DD`
- **Pre-migration backups**: `pre_migration_feature_name`
- **Model training baselines**: `model_training_v{version}`
- **Audit checkpoints**: `audit_Q{quarter}_YYYY`
- **Golden datasets**: `gold_validated_YYYY_MM_DD`

### Tag Management

```python
# List all tagged snapshots
snapshots = catalog.list_snapshots("gold", "customers")

for snap in snapshots:
    tag = snap.get("summary", {}).get("tag")
    if tag:
        print(f"Snapshot {snap['snapshot_id']}: {tag}")
```

______________________________________________________________________

## Retention Policies

Automatically clean up old snapshots to save storage costs while preserving important versions.

### Default Retention Policy

- **Keep last 30 snapshots** (recent versions)
- **Keep snapshots from last 90 days** (time-based)
- **Always keep tagged snapshots** (production, gold, etc.)
- **Production datasets: 2 years retention**

### Manual Cleanup

```bash
# Dry run (preview what would be deleted)
python scripts/iceberg_retention_cleanup.py --all --dry-run

# Cleanup a specific table
python scripts/iceberg_retention_cleanup.py \
    --namespace gold \
    --table customers \
    --execute

# Cleanup all tables with custom policy
python scripts/iceberg_retention_cleanup.py \
    --all \
    --execute \
    --keep-last 50 \
    --keep-days 120
```

**Output:**

```
Processing table: gold.customers
  Total snapshots: 150
  To keep: 45
  To expire: 105
  Kept snapshots:
    - 9876543210 (2026-02-14 10:30) - recent (top 30)
    - 9876543200 (2026-02-13 15:20) - recent (top 30)
    - 9876543100 (2026-01-20 08:00) - tagged (production_2026_01_20)
    - 9876543050 (2026-01-15 12:00) - within retention (90 days)
    ... and 41 more
  Expired snapshots:
    - 9876542000 (2025-10-01 09:00) - expired
    ... and 104 more
  ✓ Expired 105 snapshots

CLEANUP SUMMARY
================================================================================
Tables processed: 12
Total snapshots: 1,842
Kept: 456
Expired: 1,386
Space saved: 142.5 GB (77.3%)
```

### Automated Cleanup (CronJob)

The system automatically runs cleanup weekly:

```yaml
# deploy/kubernetes/cronjobs/iceberg-retention-cleanup.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: iceberg-retention-cleanup
spec:
  schedule: "0 2 * * 0"  # Every Sunday at 2 AM
  # ...configuration...
```

Deploy:

```bash
kubectl apply -f deploy/kubernetes/cronjobs/iceberg-retention-cleanup.yaml
```

Monitor:

```bash
# Check last run status
kubectl get cronjobs -n lakehouse

# View logs from last run
kubectl logs -n lakehouse job/iceberg-retention-cleanup-{timestamp}
```

### Custom Retention Policies

```python
from scripts.iceberg_retention_cleanup import RetentionPolicy, IcebergRetentionManager

# Define custom policy
custom_policy = RetentionPolicy(
    keep_last_n=100,           # Keep last 100 snapshots
    keep_days=180,             # 6 months
    keep_tagged=True,          # Always keep tagged
    production_keep_days=1095  # 3 years for production
)

manager = IcebergRetentionManager(catalog, custom_policy)

# Apply to specific namespace
results = manager.cleanup_all_tables(
    namespaces=["gold", "platinum"],
    dry_run=False
)
```

______________________________________________________________________

## Compaction

Consolidate small files into larger files for improved query performance and reduced S3 costs.

### When to Compact

Compact tables when:

- **> 10 small files** (< 10 MB each)
- **Average file size < 10 MB**
- **Query performance degrading**
- **High S3 API costs** (many GET requests)

### Manual Compaction

```bash
# Analyze table (dry run)
python scripts/iceberg_compaction.py \
    --namespace gold \
    --table customers \
    --dry-run

# Execute compaction
python scripts/iceberg_compaction.py \
    --namespace gold \
    --table customers \
    --execute
```

**Output:**

```
Analyzing table: gold.customers
  Total files: 245
  Total size: 5,120.50 MB
  Avg file size: 20.90 MB
  Small files (<10 MB): 125
  Needs compaction: True

Starting compaction...
  Reading table data...
  Writing compacted files...
  ✓ Compaction completed in 45.23s
    Files: 245 → 11
    Size: 5,120.50 MB → 5,089.20 MB (1.006x compression)
```

### Compact All Tables

```bash
python scripts/iceberg_compaction.py \
    --all \
    --execute \
    --target-file-size-mb 512 \
    --min-file-size-mb 10
```

### Compaction Policy

```python
from scripts.iceberg_compaction import CompactionPolicy, IcebergCompactionManager

policy = CompactionPolicy(
    target_file_size_mb=512,     # Target: 512 MB files
    min_file_size_mb=10,         # Compact files < 10 MB
    max_concurrent_files=100,    # Max files per operation
    rewrite_all=False            # Only compact small files
)

manager = IcebergCompactionManager(catalog, policy)

# Analyze table
analysis = manager.analyze_table("gold", "customers")
print(f"Needs compaction: {analysis['needs_compaction']}")
print(f"Reason: {analysis['reason']}")

# Compact if needed
if analysis["needs_compaction"]:
    result = manager.compact_table("gold", "customers", dry_run=False)
```

### Automated Compaction

Create a weekly compaction CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: iceberg-compaction
  namespace: lakehouse
spec:
  schedule: "0 3 * * 6"  # Every Saturday at 3 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: compaction
              image: odg/lakehouse-agent:latest
              command:
                - python
                - /scripts/iceberg_compaction.py
              args:
                - --all
                - --execute
                - --target-file-size-mb
                - "512"
```

### Performance Impact

**Before Compaction:**

- Files: 245
- Avg file size: 21 MB
- Query time: 12.5s
- S3 GET requests: 245

**After Compaction:**

- Files: 11
- Avg file size: 463 MB
- Query time: 3.2s (⬇️ 74%)
- S3 GET requests: 11 (⬇️ 96%)

______________________________________________________________________

## Monitoring & Observability

### Grafana Dashboard

Access the **Data Lineage & Versioning** dashboard:

```
http://grafana:3000/d/lineage-versioning
```

**Key Metrics:**

1. **Dataset Versions by Namespace**

   - Track snapshot creation rate
   - Identify datasets with many versions

1. **Pipeline Success Rate**

   - Monitor pipeline health
   - Alert on degradation

1. **Lineage Query Performance (P95)**

   - JanusGraph query latency
   - Detect performance issues

1. **Tables Needing Compaction**

   - Alert when > 10 tables need compaction
   - Proactive optimization

1. **Model Lineage Completeness**

   - % of models with training data lineage
   - Track compliance

### Prometheus Metrics

**Iceberg Metrics:**

```promql
# Total snapshots by namespace
iceberg_snapshots_total{namespace="gold"}

# Average file size
avg by (namespace) (iceberg_file_size_bytes)

# Small files count (compaction candidates)
iceberg_small_files_count > 10
```

**JanusGraph Metrics:**

```promql
# Lineage graph size
janusgraph_vertices_total
janusgraph_edges_total

# Query performance
histogram_quantile(0.95, janusgraph_query_duration_seconds_bucket)

# Error rate
rate(janusgraph_query_errors_total[5m])
```

**Pipeline Metrics:**

```sql
-- Success rate (last 24h)
SELECT
  (COUNT(*) FILTER (WHERE status = 'SUCCESS')::float / COUNT(*)) * 100
FROM pipeline_executions
WHERE start_time >= NOW() - INTERVAL '24 hours';

-- Average duration by pipeline
SELECT
  pipeline_id,
  AVG(duration_ms) / 1000.0 as avg_duration_seconds
FROM pipeline_executions
WHERE status = 'SUCCESS'
GROUP BY pipeline_id
ORDER BY avg_duration_seconds DESC;
```

### Alerting Rules

**Example Prometheus alerts:**

```yaml
groups:
  - name: lineage_versioning
    rules:
      # Alert when too many tables need compaction
      - alert: TablesNeedingCompaction
        expr: count(iceberg_small_files_count > 10) > 10
        for: 1h
        annotations:
          summary: "{{ $value }} tables need compaction"

      # Alert on lineage query slowness
      - alert: LineageQuerySlow
        expr: histogram_quantile(0.95, janusgraph_query_duration_seconds_bucket) > 0.5
        for: 10m
        annotations:
          summary: "Lineage queries P95 > 500ms"

      # Alert on pipeline failures
      - alert: PipelineFailureRateHigh
        expr: rate(pipeline_executions_failed_total[1h]) > 0.1
        for: 15m
        annotations:
          summary: "Pipeline failure rate > 10%"
```

______________________________________________________________________

## Best Practices

### 1. Snapshot Tagging Strategy

**DO:**

- ✅ Tag production deployments
- ✅ Tag before major migrations
- ✅ Tag datasets used for model training
- ✅ Use consistent naming conventions

**DON'T:**

- ❌ Tag every snapshot (defeats retention)
- ❌ Use ambiguous tags ("backup", "test")
- ❌ Forget to document tag meaning

### 2. Retention Policy Guidelines

**Default Policy (Most Use Cases):**

```python
RetentionPolicy(
    keep_last_n=30,          # Last month of versions
    keep_days=90,            # 3 months retention
    production_keep_days=730 # 2 years for production
)
```

**High-Frequency Tables:**

```python
RetentionPolicy(
    keep_last_n=50,          # More recent versions
    keep_days=30,            # Shorter retention
    production_keep_days=365
)
```

**Critical Compliance Tables:**

```python
RetentionPolicy(
    keep_last_n=100,
    keep_days=365,           # 1 year
    production_keep_days=2555  # 7 years for regulations
)
```

### 3. Compaction Scheduling

**Recommended Schedule:**

- **Bronze layer**: Weekly (high write volume)
- **Silver layer**: Bi-weekly
- **Gold layer**: Monthly (stable data)
- **Platinum layer**: As needed (low volume)

**Compaction Windows:**

- Run during low-traffic periods (weekends, nights)
- Avoid compacting actively-written tables
- Monitor query performance after compaction

### 4. Version Comparison Use Cases

**Schema Evolution:**

```python
# Before deploying pipeline change
comparison = await compare_dataset_schema("gold", "customers", old_version, new_version)

if comparison["removed_columns"]:
    print("⚠️  Breaking change: columns removed!")
    # Alert downstream teams
```

**Model Performance Regression:**

```python
# After retraining
comparison = await compare_model_performance("churn_predictor", old_version, new_version)

for metric, values in comparison["metrics_diff"].items():
    if values["delta"] < -0.05:  # > 5% degradation
        print(f"⚠️  Regression in {metric}: {values['percent_change']:.2f}%")
        # Trigger investigation
```

**Data Quality Validation:**

```python
# After promotion
comparison = await compare_dataset_data("silver", "sales", old_snapshot, new_snapshot)

if comparison["rows_removed"] > 0.1 * comparison["rows_from"]:
    print("⚠️  More than 10% of rows removed!")
    # Rollback promotion
```

### 5. Performance Optimization Checklist

- [ ] Enable compaction for high-volume tables
- [ ] Tag production snapshots before cleanup
- [ ] Monitor lineage query performance (P95 < 500ms)
- [ ] Review Cassandra cluster health weekly
- [ ] Check for tables needing compaction monthly
- [ ] Validate retention policy quarterly
- [ ] Archive old model versions to cold storage

### 6. Disaster Recovery

**Backup Strategy:**

```bash
# Before major changes, tag current state
catalog.tag_snapshot("gold", "customers", current_snapshot, "pre_migration_v2")

# After validation period, execute change
# If issues arise, rollback:
catalog.rollback_to_snapshot("gold", "customers", tagged_snapshot)
```

**Recovery Scenarios:**

1. **Corrupted Data:**

   ```python
   # Rollback to last known good snapshot
   good_snapshot = catalog.get_snapshot_by_tag("gold", "customers", "production_2026_02_14")
   catalog.rollback_to_snapshot("gold", "customers", good_snapshot)
   ```

1. **Schema Migration Failure:**

   ```python
   # Time-travel to pre-migration state
   old_data = catalog.time_travel_by_tag("gold", "customers", "pre_migration_v2")
   # Restore data
   ```

1. **Model Performance Regression:**

   ```python
   # Retrain with exact historical data
   training_data = catalog.time_travel(
       "gold",
       "customers",
       model_card.training_dataset_version
   )
   ```

______________________________________________________________________

## Troubleshooting

### Cleanup Not Expiring Snapshots

**Symptoms:** Retention policy runs but snapshots remain

**Causes:**

1. All snapshots are tagged
1. All snapshots within retention period
1. Insufficient permissions

**Solutions:**

```python
# Check snapshot age
snapshots = catalog.list_snapshots("gold", "customers")
for snap in snapshots:
    age_days = (datetime.now() - datetime.fromtimestamp(snap["timestamp_ms"] / 1000)).days
    print(f"Snapshot {snap['snapshot_id']}: {age_days} days old")

# Check tags
tagged = [s for s in snapshots if "tag" in s.get("summary", {})]
print(f"{len(tagged)} tagged snapshots (will not expire)")
```

### Compaction Not Improving Performance

**Symptoms:** Query time unchanged after compaction

**Causes:**

1. Files already optimal size
1. Query not scanning full table
1. Other bottlenecks (network, CPU)

**Solutions:**

```python
# Verify file sizes after compaction
analysis = manager.analyze_table("gold", "customers")
print(f"Avg file size: {analysis['avg_file_size_mb']} MB")

# Should be close to target (512 MB)
if analysis["avg_file_size_mb"] < 100:
    print("Files still small, compaction may have failed")
```

### High Storage Costs Despite Retention

**Symptoms:** S3 costs high, many snapshots exist

**Causes:**

1. Too many tagged snapshots
1. Retention period too long
1. High data change rate

**Solutions:**

```bash
# Audit tagged snapshots
python -c "
from odg_core.storage.iceberg_catalog import IcebergCatalog
catalog = IcebergCatalog()
snapshots = catalog.list_snapshots('gold', 'customers')
tagged = [s for s in snapshots if 'tag' in s.get('summary', {})]
print(f'Tagged snapshots: {len(tagged)}')
for snap in tagged:
    print(f\"  - {snap['summary']['tag']}\")
"

# Remove unnecessary tags
# catalog.remove_tag("gold", "customers", "old_tag")
```

______________________________________________________________________

## Summary

**Version Comparison:** Compare schemas, data, and metrics between versions for impact analysis and debugging.

**Snapshot Tagging:** Protect important versions from cleanup with semantic tags.

**Retention Policies:** Automated cleanup saves storage costs while preserving critical versions.

**Compaction:** Optimize file layout for better query performance and lower costs.

**Monitoring:** Grafana dashboards and Prometheus alerts track system health.

**Best Practices:** Follow guidelines for tagging, retention, compaction scheduling, and disaster recovery.

For more information, see:

- [Data Lineage Tracking Guide](LINEAGE_TRACKING.md)
- [Deployment Profiles](DEPLOYMENT_PROFILES.md)
- [API Reference - GraphQL](API_GRAPHQL.md)
