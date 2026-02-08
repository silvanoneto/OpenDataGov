"""Kafka audit event producer (ADR-112).

Publishes audit events to Kafka for durable storage and downstream processing.
Follows the same graceful degradation pattern as the NATS publisher.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)


class KafkaAuditProducer:
    """Publishes audit events to Kafka."""

    def __init__(self, topic: str = "odg.audit.events") -> None:
        self._producer: AIOKafkaProducer | None = None
        self._topic = topic

    async def connect(self, bootstrap_servers: str) -> None:
        """Connect to Kafka cluster."""
        try:
            from aiokafka import AIOKafkaProducer

            self._producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode(),
                acks="all",
            )
            await self._producer.start()
            logger.info("Connected to Kafka at %s", bootstrap_servers)
        except Exception:
            logger.warning(
                "Failed to connect to Kafka at %s, audit events will be skipped",
                bootstrap_servers,
                exc_info=True,
            )
            self._producer = None

    async def disconnect(self) -> None:
        """Disconnect from Kafka."""
        if self._producer is not None:
            await self._producer.stop()
            logger.info("Disconnected from Kafka")

    async def publish_audit_event(self, event: dict[str, Any]) -> None:
        """Publish an audit event to Kafka.

        Silently skips if not connected (graceful degradation).
        """
        if self._producer is None:
            return

        try:
            from odg_core.telemetry.context import get_trace_headers

            trace_headers = get_trace_headers()
            if trace_headers:
                event.setdefault("_trace", trace_headers)

            await self._producer.send_and_wait(self._topic, event)
            logger.debug("Published audit event to %s", self._topic)
        except Exception:
            logger.warning("Failed to publish audit event to Kafka", exc_info=True)

    @property
    def is_connected(self) -> bool:
        return self._producer is not None
