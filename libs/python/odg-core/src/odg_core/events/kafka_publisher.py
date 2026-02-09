"""Kafka event publisher for OpenDataGov events (ADR-091)."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)

# Kafka topics (ADR-091)
TOPICS = {
    # Audit events (high volume)
    "audit_event": "odg.audit.events",
    # Governance decision events
    "decision_created": "odg.governance.decisions",
    "decision_submitted": "odg.governance.decisions",
    "decision_approved": "odg.governance.decisions",
    "decision_rejected": "odg.governance.decisions",
    "decision_vetoed": "odg.governance.decisions",
    # Quality validation events
    "quality_report_created": "odg.quality.reports",
    "quality_gate_passed": "odg.quality.reports",
    "quality_gate_failed": "odg.quality.reports",
    # Lineage events
    "lineage_updated": "odg.lineage.updates",
    "lineage_added": "odg.lineage.updates",
}


class KafkaPublisher:
    """Publishes OpenDataGov events to Kafka topics.

    Follows the same pattern as NATSPublisher with graceful degradation.
    If Kafka is unavailable, events are silently skipped.
    """

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None
        self._bootstrap_servers: str | None = None

    async def connect(self, bootstrap_servers: str) -> None:
        """Connect to Kafka cluster.

        Args:
            bootstrap_servers: Kafka bootstrap servers (e.g., "localhost:9092")
        """
        try:
            self._bootstrap_servers = bootstrap_servers
            self._producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                # Idempotence for exactly-once semantics
                enable_idempotence=True,
                # Compression
                compression_type="snappy",
            )
            await self._producer.start()
            logger.info("Connected to Kafka at %s", bootstrap_servers)
        except KafkaError:
            logger.warning(
                "Failed to connect to Kafka at %s, events will be skipped",
                bootstrap_servers,
                exc_info=True,
            )
            self._producer = None
        except Exception:
            logger.warning(
                "Unexpected error connecting to Kafka at %s, events will be skipped",
                bootstrap_servers,
                exc_info=True,
            )
            self._producer = None

    async def disconnect(self) -> None:
        """Disconnect from Kafka."""
        if self._producer:
            await self._producer.stop()
            logger.info("Disconnected from Kafka")
            self._producer = None

    async def publish(self, event_key: str, payload: dict[str, Any], *, key: str | None = None) -> None:
        """Publish an event to Kafka.

        Silently skips if not connected (graceful degradation).

        Args:
            event_key: Event type key (maps to topic)
            payload: Event payload (will be JSON serialized)
            key: Optional message key for partitioning
        """
        if self._producer is None:
            return

        topic = TOPICS.get(event_key)
        if topic is None:
            logger.warning("Unknown event type: %s", event_key)
            return

        try:
            # Add OpenTelemetry trace context
            from odg_core.telemetry.context import get_trace_headers

            trace_headers = get_trace_headers()
            if trace_headers:
                payload.setdefault("_trace", trace_headers)

            # Publish to Kafka
            key_bytes = key.encode("utf-8") if key else None
            await self._producer.send_and_wait(topic, payload, key=key_bytes)
            logger.debug("Published event to topic %s", topic)

        except KafkaError:
            logger.warning("Failed to publish event to topic %s", topic, exc_info=True)
        except Exception:
            logger.warning("Unexpected error publishing to topic %s", topic, exc_info=True)

    async def publish_batch(self, events: list[tuple[str, dict[str, Any]]]) -> None:
        """Publish multiple events in a batch for better throughput.

        Args:
            events: List of (event_key, payload) tuples
        """
        if self._producer is None:
            return

        try:
            # Add trace context to all events
            from odg_core.telemetry.context import get_trace_headers

            trace_headers = get_trace_headers()

            # Send all events (non-blocking)
            for event_key, payload in events:
                topic = TOPICS.get(event_key)
                if topic is None:
                    logger.warning("Unknown event type: %s", event_key)
                    continue

                if trace_headers:
                    payload.setdefault("_trace", trace_headers)

                # send() is non-blocking, batched automatically
                await self._producer.send(topic, payload)

            # Flush to ensure all messages are sent
            await self._producer.flush()
            logger.debug("Published batch of %d events", len(events))

        except KafkaError:
            logger.warning("Failed to publish batch of events", exc_info=True)
        except Exception:
            logger.warning("Unexpected error publishing batch", exc_info=True)

    @property
    def is_connected(self) -> bool:
        """Check if connected to Kafka."""
        return self._producer is not None
