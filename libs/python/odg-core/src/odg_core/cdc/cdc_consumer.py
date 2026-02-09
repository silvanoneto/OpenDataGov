"""CDC event consumer for processing database changes.

Consumes Debezium CDC events from Kafka and processes them for:
- Real-time data synchronization
- Audit trail
- Event-driven workflows
- Cache invalidation
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CDCOperation(StrEnum):
    """CDC operation types."""

    CREATE = "c"  # INSERT
    UPDATE = "u"  # UPDATE
    DELETE = "d"  # DELETE
    READ = "r"  # Initial snapshot read


class CDCEvent(BaseModel):
    """Parsed CDC event from Debezium.

    Example Debezium event structure:
    {
      "before": null,
      "after": {"id": 1, "name": "value"},
      "source": {
        "version": "2.5.0.Final",
        "connector": "postgresql",
        "name": "odg_postgres",
        "ts_ms": 1707392400000,
        "snapshot": "false",
        "db": "odg",
        "schema": "public",
        "table": "governance_decisions",
        "lsn": 12345
      },
      "op": "c",
      "ts_ms": 1707392400100,
      "transaction": null
    }
    """

    operation: CDCOperation
    table_name: str
    schema_name: str
    database: str

    # Record data
    before: dict[str, Any] | None = None  # State before change (null for INSERT)
    after: dict[str, Any] | None = None  # State after change (null for DELETE)

    # Metadata
    source_timestamp: datetime
    event_timestamp: datetime
    lsn: int | None = None  # Log Sequence Number (PostgreSQL)
    transaction_id: str | None = None

    # Additional fields
    connector_name: str
    is_snapshot: bool = False


class CDCConsumer:
    """Consumer for processing CDC events from Kafka.

    Example:
        >>> from odg_core.cdc import CDCConsumer
        >>>
        >>> consumer = CDCConsumer(bootstrap_servers="kafka:9092")
        >>> consumer.subscribe(["cdc.odg.public.governance_decisions"])
        >>>
        >>> async for event in consumer.consume():
        ...     if event.operation == CDCOperation.CREATE:
        ...         print(f"New record: {event.after}")
        ...     elif event.operation == CDCOperation.UPDATE:
        ...         print(f"Updated: {event.before} -> {event.after}")
    """

    def __init__(
        self,
        bootstrap_servers: str = "kafka:9092",
        group_id: str = "cdc-consumer-group",
        auto_offset_reset: str = "earliest",
    ):
        """Initialize CDC consumer.

        Args:
            bootstrap_servers: Kafka bootstrap servers
            group_id: Consumer group ID
            auto_offset_reset: Where to start consuming (earliest, latest)
        """
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self._consumer = None

    def subscribe(self, topics: list[str]) -> None:
        """Subscribe to CDC topics.

        Args:
            topics: List of Kafka topics to consume
        """
        try:
            from kafka import KafkaConsumer

            self._consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=1000,
            )

            logger.info(f"Subscribed to CDC topics: {topics}")

        except ImportError:
            logger.error("kafka-python not installed. Install with: pip install kafka-python")
            raise
        except Exception as e:
            logger.error(f"Failed to subscribe to CDC topics: {e}")
            raise

    def consume(self) -> Iterator[CDCEvent]:
        """Consume CDC events from Kafka.

        Yields:
            Parsed CDC events

        Example:
            >>> consumer = CDCConsumer()
            >>> consumer.subscribe(["cdc.odg.public.audit_events"])
            >>> for event in consumer.consume():
            ...     if event.operation == CDCOperation.CREATE:
            ...         process_new_audit_event(event.after)
        """
        if not self._consumer:
            raise RuntimeError("Consumer not subscribed. Call subscribe() first.")

        try:
            for message in self._consumer:
                try:
                    event = self._parse_event(message.value)
                    if event:
                        yield event
                except Exception as e:
                    logger.error(f"Failed to parse CDC event: {e}")
                    continue

        except KeyboardInterrupt:
            logger.info("CDC consumer interrupted")
        finally:
            self.close()

    def _parse_event(self, raw_event: dict[str, Any]) -> CDCEvent | None:
        """Parse raw Debezium event into CDCEvent.

        Args:
            raw_event: Raw event from Kafka

        Returns:
            Parsed CDCEvent or None if parsing fails
        """
        try:
            source = raw_event.get("source", {})
            operation = raw_event.get("op")

            # Skip heartbeat events
            if not operation:
                return None

            # Parse timestamps
            source_ts = source.get("ts_ms", 0)
            event_ts = raw_event.get("ts_ms", 0)

            return CDCEvent(
                operation=CDCOperation(operation),
                table_name=source.get("table", ""),
                schema_name=source.get("schema", "public"),
                database=source.get("db", ""),
                before=raw_event.get("before"),
                after=raw_event.get("after"),
                source_timestamp=datetime.fromtimestamp(source_ts / 1000),
                event_timestamp=datetime.fromtimestamp(event_ts / 1000),
                lsn=source.get("lsn"),
                transaction_id=raw_event.get("transaction", {}).get("id") if raw_event.get("transaction") else None,
                connector_name=source.get("name", ""),
                is_snapshot=source.get("snapshot", "false") == "true",
            )

        except Exception as e:
            logger.error(f"Failed to parse CDC event: {e}")
            return None

    def close(self) -> None:
        """Close the consumer and release resources."""
        if self._consumer:
            self._consumer.close()
            logger.info("CDC consumer closed")


# Event handlers for specific use cases


def sync_to_cache(event: CDCEvent, cache_client: Any) -> None:
    """Sync CDC event to Redis cache.

    Args:
        event: CDC event
        cache_client: Redis client instance
    """
    cache_key = f"{event.table_name}:{event.after.get('id')}" if event.after else None

    if event.operation == CDCOperation.CREATE or event.operation == CDCOperation.UPDATE:
        if cache_key and event.after:
            cache_client.set(cache_key, json.dumps(event.after), ex=3600)
            logger.debug(f"Updated cache: {cache_key}")

    elif event.operation == CDCOperation.DELETE and cache_key:
        cache_client.delete(cache_key)
        logger.debug(f"Invalidated cache: {cache_key}")


def sync_to_elasticsearch(event: CDCEvent, es_client: Any) -> None:
    """Sync CDC event to Elasticsearch for search indexing.

    Args:
        event: CDC event
        es_client: Elasticsearch client instance
    """
    index_name = f"cdc_{event.table_name}"
    doc_id: Any = None
    if event.after:
        doc_id = event.after.get("id")
    elif event.before:
        doc_id = event.before.get("id")

    if event.operation == CDCOperation.CREATE or event.operation == CDCOperation.UPDATE:
        if event.after:
            es_client.index(index=index_name, id=doc_id, document=event.after)
            logger.debug(f"Indexed to ES: {index_name}/{doc_id}")

    elif event.operation == CDCOperation.DELETE:
        es_client.delete(index=index_name, id=doc_id, ignore=[404])
        logger.debug(f"Deleted from ES: {index_name}/{doc_id}")


def trigger_workflow(event: CDCEvent) -> None:
    """Trigger event-driven workflow based on CDC event.

    Example use cases:
    - New governance decision → notify stakeholders
    - Model card updated → invalidate cache
    - Pipeline execution failed → create alert

    Args:
        event: CDC event
    """
    after = event.after or {}

    if event.table_name == "governance_decisions" and event.operation == CDCOperation.CREATE:
        # Trigger notification workflow
        logger.info(f"New governance decision created: {after.get('title')}")
        # TODO: Emit notification event

    elif event.table_name == "pipeline_executions" and after.get("status") == "failed":
        # Trigger alert workflow
        logger.warning(f"Pipeline execution failed: {after.get('pipeline_id')}")
        # TODO: Create alert

    elif event.table_name == "model_cards" and event.operation == CDCOperation.UPDATE:
        # Invalidate ML model cache
        logger.info(f"Model card updated: {after.get('model_name')}")
        # TODO: Invalidate cache
