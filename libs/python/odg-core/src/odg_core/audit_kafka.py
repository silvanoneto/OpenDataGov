"""Kafka audit event serialization helpers (ADR-112).

Provides standardized serialization for audit events flowing through Kafka.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
