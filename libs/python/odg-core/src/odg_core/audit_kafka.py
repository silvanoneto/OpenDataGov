"""Kafka audit event serialization helpers (ADR-112).

Provides standardized serialization for audit events flowing through Kafka.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field


class KafkaAuditEvent(BaseModel):
    """Standardized Kafka audit event envelope."""

    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor_id: str = ""
    resource_type: str = ""
    resource_id: str = ""
    action: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = ""
    span_id: str = ""

    def to_kafka_payload(self) -> dict[str, Any]:
        """Serialize to Kafka-ready dict."""
        return self.model_dump(mode="json")


def create_audit_event(
    event_type: str,
    *,
    actor_id: str = "",
    resource_type: str = "",
    resource_id: str = "",
    action: str = "",
    details: dict[str, Any] | None = None,
) -> KafkaAuditEvent:
    """Factory for creating standardized audit events."""
    trace_id = ""
    span_id = ""

    try:
        from odg_core.telemetry.context import get_current_span_id, get_current_trace_id

        trace_id = get_current_trace_id()
        span_id = get_current_span_id()
    except ImportError:
        pass

    return KafkaAuditEvent(
        event_type=event_type,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        details=details or {},
        trace_id=trace_id,
        span_id=span_id,
    )


# ─── Kafka Publisher Integration (ADR-091) ────────────────────────────

if TYPE_CHECKING:
    from odg_core.audit import AuditEvent
    from odg_core.events.kafka_publisher import KafkaPublisher

logger = logging.getLogger(__name__)


class AuditKafkaPublisher:
    """Publishes audit events to Kafka for streaming (ADR-091).

    Complements the PostgreSQL audit trail with Kafka streaming.
    Maintains SHA-256 hash chain in PostgreSQL while streaming to Kafka.
    """

    def __init__(self, kafka_publisher: KafkaPublisher) -> None:
        self.kafka = kafka_publisher

    async def publish_event(self, event: AuditEvent) -> None:
        """Publish audit event to Kafka topic odg.audit.events.

        Args:
            event: Audit event from PostgreSQL audit trail
        """
        if not self.kafka.is_connected:
            return

        try:
            # Convert to Kafka format
            kafka_event = {
                "event_type": "audit",
                "source_service": "audit-trail",
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "actor_id": event.actor_id,
                "action": event.event_type.value,
                "description": event.description,
                "details": event.details or {},
                "previous_hash": event.previous_hash,
                "event_hash": event.event_hash,
                "timestamp": event.occurred_at.isoformat(),
            }

            # Publish to Kafka (key by entity_id for ordering)
            await self.kafka.publish(
                "audit_event",
                kafka_event,
                key=event.entity_id,
            )

            logger.debug("Published audit event %s to Kafka", event.event_hash)

        except Exception:
            logger.warning("Failed to publish audit event to Kafka", exc_info=True)

    async def publish_batch(self, events: list[AuditEvent]) -> None:
        """Publish multiple audit events in a batch.

        Args:
            events: List of audit events
        """
        if not self.kafka.is_connected or not events:
            return

        try:
            kafka_events = []
            for event in events:
                kafka_event = {
                    "event_type": "audit",
                    "source_service": "audit-trail",
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                    "actor_id": event.actor_id,
                    "action": event.event_type.value,
                    "description": event.description,
                    "details": event.details or {},
                    "previous_hash": event.previous_hash,
                    "event_hash": event.event_hash,
                    "timestamp": event.occurred_at.isoformat(),
                }
                kafka_events.append(("audit_event", kafka_event))

            await self.kafka.publish_batch(kafka_events)
            logger.debug("Published batch of %d audit events to Kafka", len(events))

        except Exception:
            logger.warning("Failed to publish audit event batch to Kafka", exc_info=True)
