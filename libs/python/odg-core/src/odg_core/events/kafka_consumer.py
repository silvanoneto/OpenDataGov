"""Kafka consumer framework for OpenDataGov events (ADR-091)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)

# Type alias for event handler
EventHandler = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class KafkaConsumer:
    """Consumes events from Kafka topics with automatic retry and error handling.

    Features:
    - Automatic deserialization of JSON payloads
    - Graceful error handling with retry logic
    - Consumer group support for horizontal scaling
    - Offset management (at-least-once delivery)
    """

    def __init__(
        self,
        group_id: str,
        bootstrap_servers: str = "localhost:9092",
        auto_offset_reset: str = "earliest",
    ) -> None:
        """Initialize Kafka consumer.

        Args:
            group_id: Consumer group ID
            bootstrap_servers: Kafka bootstrap servers
            auto_offset_reset: Where to start consuming (earliest/latest)
        """
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers
        self.auto_offset_reset = auto_offset_reset
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def connect(self) -> None:
        """Connect to Kafka and subscribe to topics."""
        try:
            self._consumer = AIOKafkaConsumer(
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                # Consumer configuration
                enable_auto_commit=True,
                auto_commit_interval_ms=5000,
                max_poll_records=500,
            )
            logger.info(
                "Kafka consumer created for group %s at %s",
                self.group_id,
                self.bootstrap_servers,
            )
        except Exception:
            logger.exception("Failed to create Kafka consumer")
            raise

    async def subscribe(self, topics: list[str]) -> None:
        """Subscribe to Kafka topics.

        Args:
            topics: List of topic names to subscribe to
        """
        if self._consumer is None:
            await self.connect()

        try:
            if self._consumer:
                await self._consumer.start()
                self._consumer.subscribe(topics)
                logger.info("Subscribed to topics: %s", ", ".join(topics))
        except Exception:
            logger.exception("Failed to subscribe to topics")
            raise

    async def consume(
        self,
        handler: EventHandler,
        *,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Start consuming messages and processing with handler.

        Args:
            handler: Async function to process each message (topic, payload)
            max_retries: Maximum number of retries on handler error
            retry_delay: Delay between retries in seconds
        """
        if self._consumer is None:
            msg = "Consumer not initialized. Call subscribe() first"
            raise RuntimeError(msg)

        self._running = True
        logger.info("Starting Kafka consumer loop")

        try:
            async for message in self._consumer:
                if not self._running:
                    break

                topic = message.topic
                payload = message.value

                # Process message with retries
                success = False
                for attempt in range(max_retries):
                    try:
                        await handler(topic, payload)
                        success = True
                        break
                    except Exception:
                        if attempt < max_retries - 1:
                            logger.warning(
                                "Handler error (attempt %d/%d), retrying in %.1fs",
                                attempt + 1,
                                max_retries,
                                retry_delay,
                                exc_info=True,
                            )
                            await asyncio.sleep(retry_delay)
                        else:
                            logger.exception("Handler failed after %d attempts", max_retries)

                if not success:
                    # TODO: Send to dead letter queue
                    logger.error(
                        "Message processing failed permanently: topic=%s partition=%d offset=%d",
                        topic,
                        message.partition,
                        message.offset,
                    )

        except KafkaError:
            logger.exception("Kafka consumer error")
            raise
        except Exception:
            logger.exception("Unexpected error in consumer loop")
            raise
        finally:
            self._running = False
            await self.stop()

    async def stop(self) -> None:
        """Stop consuming and disconnect."""
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped")
            self._consumer = None

    @property
    def is_connected(self) -> bool:
        """Check if consumer is connected."""
        return self._consumer is not None


class EventProcessor:
    """Base class for event processors.

    Subclass this to implement custom event processing logic.
    """

    async def process(self, topic: str, payload: dict[str, Any]) -> None:
        """Process an event from Kafka.

        Args:
            topic: Kafka topic name
            payload: Deserialized event payload

        Raises:
            Exception: If processing fails (will be retried)
        """
        raise NotImplementedError


# ─── Example Processors ────────────────────────────────────────────


class AuditEventProcessor(EventProcessor):
    """Example processor for audit events."""

    async def process(self, topic: str, payload: dict[str, Any]) -> None:
        """Process audit event."""
        if topic == "odg.audit.events":
            event_hash = payload.get("event_hash")
            entity_id = payload.get("entity_id")
            logger.info("Processed audit event: hash=%s entity=%s", event_hash, entity_id)


class GovernanceDecisionProcessor(EventProcessor):
    """Example processor for governance decision events."""

    async def process(self, topic: str, payload: dict[str, Any]) -> None:
        """Process governance decision event."""
        if topic == "odg.governance.decisions":
            decision_id = payload.get("decision_id")
            status = payload.get("status")
            logger.info("Processed decision event: id=%s status=%s", decision_id, status)
