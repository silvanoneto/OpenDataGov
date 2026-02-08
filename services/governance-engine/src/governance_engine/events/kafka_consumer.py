"""Kafka audit event consumer (ADR-112).

Consumes audit events from Kafka and persists them to PostgreSQL
with SHA-256 hash chain for immutability verification.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from aiokafka import AIOKafkaConsumer

logger = logging.getLogger(__name__)


def compute_hash_chain(event_data: str, previous_hash: str) -> str:
    """Compute SHA-256 hash linking event to previous hash (chain)."""
    payload = f"{previous_hash}:{event_data}"
    return hashlib.sha256(payload.encode()).hexdigest()


class KafkaAuditConsumer:
    """Consumes audit events from Kafka and persists with hash chain."""

    def __init__(
        self,
        topic: str = "odg.audit.events",
        group_id: str = "odg-audit-consumer",
    ) -> None:
        self._consumer: AIOKafkaConsumer | None = None
        self._topic = topic
        self._group_id = group_id
        self._last_hash = "genesis"
        self._running = False

    async def connect(self, bootstrap_servers: str) -> None:
        """Connect to Kafka cluster."""
        try:
            from aiokafka import AIOKafkaConsumer

            self._consumer = AIOKafkaConsumer(
                self._topic,
                bootstrap_servers=bootstrap_servers,
                group_id=self._group_id,
                value_deserializer=lambda v: json.loads(v.decode()),
                auto_offset_reset="earliest",
                enable_auto_commit=True,
            )
            await self._consumer.start()
            logger.info("Kafka audit consumer connected, topic=%s", self._topic)
        except Exception:
            logger.warning("Failed to start Kafka audit consumer", exc_info=True)
            self._consumer = None

    async def disconnect(self) -> None:
        """Disconnect from Kafka."""
        self._running = False
        if self._consumer is not None:
            await self._consumer.stop()
            logger.info("Kafka audit consumer disconnected")

    async def consume(
        self,
        persist_fn: Callable[[dict[str, Any], str], Coroutine[Any, Any, None]],
    ) -> None:
        """Consume events and persist via provided function.

        Args:
            persist_fn: Async function(event_dict, hash_chain_value) -> None
                        that persists the audit event to PostgreSQL.
        """
        if self._consumer is None:
            return

        self._running = True
        try:
            async for msg in self._consumer:
                if not self._running:
                    break

                event = msg.value
                event_json = json.dumps(event, default=str, sort_keys=True)
                chain_hash = compute_hash_chain(event_json, self._last_hash)

                await persist_fn(event, chain_hash)
                self._last_hash = chain_hash

                logger.debug("Persisted audit event, hash=%s", chain_hash[:12])
        except Exception:
            if self._running:
                logger.warning("Kafka audit consumer error", exc_info=True)
