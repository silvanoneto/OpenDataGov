# Change Data Capture (CDC) Setup Guide

## Overview

OpenDataGov uses **Debezium** with **Kafka Connect** to capture database changes in real-time and stream them to Kafka topics. This enables event-driven architectures, real-time data synchronization, and audit trails.

## Architecture

```
┌─────────────┐       ┌──────────────┐       ┌───────┐       ┌─────────────┐
│ PostgreSQL  │──────▶│  Debezium    │──────▶│ Kafka │──────▶│   Consumers │
│   (WAL)     │       │   Connector  │       │       │       │   (Python)  │
└─────────────┘       └──────────────┘       └───────┘       └─────────────┘
                              │
                              │
┌─────────────┐               │
│ TimescaleDB │───────────────┘
│   (WAL)     │
└─────────────┘
```

## Components

### 1. Kafka Connect

Distributed platform for streaming data between Apache Kafka and other systems.

**Deployed as:** Kubernetes Deployment with 2-3 replicas (depending on profile)

**Configuration:**

- Bootstrap servers: `kafka:9092`
- Group ID: `kafka-connect-cluster`
- Storage topics: `connect-configs`, `connect-offsets`, `connect-status`

### 2. Debezium PostgreSQL Connector

Captures changes from PostgreSQL Write-Ahead Log (WAL).

**Monitored Tables:**

- `governance_decisions` - Governance decisions and approvals
- `approval_records` - Approval workflow records
- `veto_records` - Veto records
- `audit_events` - System audit events
- `pipeline_versions` - Pipeline version history
- `pipeline_executions` - Pipeline execution records
- `lineage_events` - Data lineage events
- `model_cards` - ML model metadata
- `quality_reports` - Data quality reports
- `data_contracts` - Dataset contracts

**Kafka Topic Pattern:** `cdc.odg.public.<table_name>`

### 3. Debezium TimescaleDB Connector

Captures time-series metrics from TimescaleDB hypertables.

**Monitored Hypertables:**

- `model_performance_ts` - Model performance metrics over time
- `quality_metrics_ts` - Data quality metrics over time
- `pipeline_metrics_ts` - Pipeline execution metrics over time

**Kafka Topic Pattern:** `cdc.timescale.public.<table_name>`

## Deployment

### Prerequisites

1. PostgreSQL with logical replication enabled:

   ```sql
   ALTER SYSTEM SET wal_level = 'logical';
   -- Restart PostgreSQL
   ```

1. Create replication slot:

   ```sql
   SELECT pg_create_logical_replication_slot('debezium_odg', 'pgoutput');
   ```

1. Kafka cluster running

### Helm Deployment

Enable CDC in your values file (`values-medium.yaml` or `values-large.yaml`):

```yaml
kafka-connect:
  enabled: true
  replicaCount: 2
  connectors:
    postgresql:
      enabled: true
    timescaledb:
      enabled: true
```

Deploy:

```bash
helm upgrade --install opendatagov ./deploy/helm/opendatagov \
  -f deploy/helm/opendatagov/values-medium.yaml \
  -n opendatagov
```

### Manual Connector Setup

If auto-initialization fails, create connectors manually:

```bash
# Initialize connectors
python scripts/cdc/init_cdc_connectors.py \
  --kafka-connect-url http://kafka-connect:8083 \
  --kafka-bootstrap-servers kafka:9092
```

Or using the Python API:

```python
from odg_core.cdc.connector_manager import ConnectorManager

manager = ConnectorManager(kafka_connect_url="http://kafka-connect:8083")

# Create PostgreSQL connector
manager.create_connector("deploy/helm/opendatagov/charts/kafka-connect/connectors/postgresql-cdc.json")

# Check status
status = manager.get_connector_status("odg-postgresql-cdc")
print(status)
```

## CDC Event Consumption

### Python Consumer

```python
from odg_core.cdc.cdc_consumer import CDCConsumer, CDCOperation

# Initialize consumer
consumer = CDCConsumer(
    bootstrap_servers="kafka:9092",
    group_id="my-app-consumer",
    auto_offset_reset="earliest"
)

# Subscribe to topics
consumer.subscribe([
    "cdc.odg.public.governance_decisions",
    "cdc.odg.public.pipeline_executions"
])

# Consume events
for event in consumer.consume():
    if event.operation == CDCOperation.CREATE:
        print(f"New record in {event.table_name}: {event.after}")
    elif event.operation == CDCOperation.UPDATE:
        print(f"Updated in {event.table_name}")
        print(f"  Before: {event.before}")
        print(f"  After: {event.after}")
    elif event.operation == CDCOperation.DELETE:
        print(f"Deleted from {event.table_name}: {event.before}")
```

### Example Use Cases

#### 1. Cache Synchronization

```python
from odg_core.cdc.cdc_consumer import CDCConsumer, sync_to_cache
import redis

consumer = CDCConsumer()
consumer.subscribe(["cdc.odg.public.model_cards"])

redis_client = redis.Redis(host="redis", port=6379)

for event in consumer.consume():
    sync_to_cache(event, redis_client)
    # Cache automatically updated!
```

#### 2. Elasticsearch Indexing

```python
from odg_core.cdc.cdc_consumer import CDCConsumer, sync_to_elasticsearch
from elasticsearch import Elasticsearch

consumer = CDCConsumer()
consumer.subscribe(["cdc.odg.public.data_contracts"])

es_client = Elasticsearch(["http://elasticsearch:9200"])

for event in consumer.consume():
    sync_to_elasticsearch(event, es_client)
    # Dataset contracts indexed for full-text search!
```

#### 3. Workflow Triggers

```python
from odg_core.cdc.cdc_consumer import CDCConsumer, trigger_workflow

consumer = CDCConsumer()
consumer.subscribe(["cdc.odg.public.governance_decisions"])

for event in consumer.consume():
    trigger_workflow(event)
    # Notifications sent to stakeholders!
```

## Event Structure

### Debezium Event Format

```json
{
  "before": null,
  "after": {
    "id": 123,
    "title": "Approve new dataset",
    "status": "approved",
    "created_at": "2026-02-08T10:00:00Z"
  },
  "source": {
    "version": "2.5.0.Final",
    "connector": "postgresql",
    "name": "odg_postgres",
    "ts_ms": 1707392400000,
    "snapshot": "false",
    "db": "odg",
    "schema": "public",
    "table": "governance_decisions",
    "lsn": 123456789
  },
  "op": "c",
  "ts_ms": 1707392400100,
  "transaction": null
}
```

### Parsed CDCEvent

```python
CDCEvent(
    operation=CDCOperation.CREATE,
    table_name="governance_decisions",
    schema_name="public",
    database="odg",
    before=None,
    after={"id": 123, "title": "Approve new dataset", ...},
    source_timestamp=datetime(2026, 2, 8, 10, 0, 0),
    event_timestamp=datetime(2026, 2, 8, 10, 0, 0, 100000),
    lsn=123456789,
    transaction_id=None,
    connector_name="odg_postgres",
    is_snapshot=False
)
```

## Monitoring

### Check Connector Status

```bash
# List all connectors
curl http://kafka-connect:8083/connectors

# Get connector status
curl http://kafka-connect:8083/connectors/odg-postgresql-cdc/status

# Get connector config
curl http://kafka-connect:8083/connectors/odg-postgresql-cdc/config
```

### Monitor Kafka Topics

```bash
# List CDC topics
kafka-topics.sh --bootstrap-server kafka:9092 --list | grep cdc

# Consume from topic
kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic cdc.odg.public.governance_decisions \
  --from-beginning
```

### Metrics

Kafka Connect exposes JMX metrics:

- Connector task status
- Throughput (records/sec)
- Latency (source to sink)
- Error count

**Grafana Dashboard:** Pre-configured dashboard for CDC metrics (coming in Phase 2)

## Troubleshooting

### Connector Won't Start

**Check replication slot:**

```sql
SELECT * FROM pg_replication_slots WHERE slot_name = 'debezium_odg';
```

**Check WAL level:**

```sql
SHOW wal_level;  -- Should be 'logical'
```

**Restart connector:**

```bash
curl -X POST http://kafka-connect:8083/connectors/odg-postgresql-cdc/restart
```

### Missing Events

**Check connector offset:**

```bash
kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic connect-offsets \
  --from-beginning | grep odg-postgresql-cdc
```

**Reset offset (⚠️ DANGER - replays all events):**

```python
from odg_core.cdc.connector_manager import ConnectorManager

manager = ConnectorManager()
manager.pause_connector("odg-postgresql-cdc")
# Manually reset Kafka consumer group offset
manager.resume_connector("odg-postgresql-cdc")
```

### High Lag

Monitor replication lag:

```sql
SELECT
    slot_name,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS lag
FROM pg_replication_slots
WHERE slot_name = 'debezium_odg';
```

**Solutions:**

- Scale up Kafka Connect replicas
- Increase `max.batch.size` in connector config
- Add more Kafka partitions to CDC topics

## Security

### Authentication

Kafka Connect connects to PostgreSQL with credentials from Kubernetes Secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kafka-connect-db-credentials
type: Opaque
stringData:
  POSTGRES_USER: debezium
  POSTGRES_PASSWORD: <secure-password>
  TIMESCALE_USER: debezium
  TIMESCALE_PASSWORD: <secure-password>
```

### Encryption

- **In-transit:** TLS for Kafka (if `kafka.tls.enabled: true`)
- **At-rest:** Encrypted volumes for Kafka log segments

### Access Control

PostgreSQL user `debezium` requires:

```sql
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium;
GRANT USAGE ON SCHEMA public TO debezium;
ALTER USER debezium REPLICATION;
```

## Best Practices

1. **Schema Evolution:** Use Avro or JSON Schema for forward/backward compatibility
1. **Tombstone Handling:** Enable tombstones for DELETE events (`tombstones.on.delete: true`)
1. **Monitoring:** Set up alerts for connector failures and lag
1. **Backfill:** Use snapshot mode for initial data load, then switch to incremental
1. **Partitioning:** Distribute CDC topics across multiple partitions for parallelism
1. **Retention:** Set appropriate retention for CDC topics (default: 1 year)

## Performance Tuning

### Connector Configuration

```json
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "max.batch.size": "2048",
  "max.queue.size": "8192",
  "poll.interval.ms": "1000",
  "snapshot.fetch.size": "10240"
}
```

### Kafka Connect Workers

- **CPU:** 2-4 cores per replica
- **Memory:** 4-8 GB per replica
- **Replicas:** 2-3 for HA

## References

- [Debezium PostgreSQL Connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [Kafka Connect Documentation](https://kafka.apache.org/documentation/#connect)
- [OpenDataGov CDC Architecture](./ARCHITECTURE.md#cdc-change-data-capture)
