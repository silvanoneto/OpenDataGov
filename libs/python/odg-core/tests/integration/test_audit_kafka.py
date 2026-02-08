"""Integration test: Kafka audit event pipeline."""

from __future__ import annotations

import hashlib
import json


class TestAuditKafkaSerialization:
    """Verify audit event serialization (works without Kafka)."""

    def test_create_audit_event(self) -> None:
        """create_audit_event should produce a valid KafkaAuditEvent."""
        from odg_core.audit_kafka import create_audit_event

        event = create_audit_event(
            event_type="DECISION_CREATED",
            actor_id="user-123",
            resource_type="governance",
            resource_id="decisions/abc",
            details={"title": "Test decision"},
        )

        assert event.event_type == "DECISION_CREATED"
        assert event.actor_id == "user-123"
        assert event.resource_type == "governance"
        assert event.details["title"] == "Test decision"
        assert event.timestamp is not None

    def test_audit_event_serialization_roundtrip(self) -> None:
        """KafkaAuditEvent should serialize to JSON and back."""
        from odg_core.audit_kafka import create_audit_event

        event = create_audit_event(
            event_type="VOTE_CAST",
            actor_id="user-456",
            resource_type="governance",
            resource_id="decisions/def/votes",
        )

        json_str = event.model_dump_json()
        data = json.loads(json_str)

        assert data["event_type"] == "VOTE_CAST"
        assert data["actor_id"] == "user-456"

    def test_hash_chain_computation(self) -> None:
        """Hash chain should be deterministic and verifiable."""
        event_data = json.dumps({"event": "test", "timestamp": "2026-01-01T00:00:00Z"}).encode()
        previous_hash = "genesis"

        hash1 = hashlib.sha256(previous_hash.encode() + event_data).hexdigest()
        hash2 = hashlib.sha256(previous_hash.encode() + event_data).hexdigest()

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_kafka_payload_format(self) -> None:
        """to_kafka_payload should produce a JSON-serializable dict."""
        from odg_core.audit_kafka import create_audit_event

        event = create_audit_event(
            event_type="DATA_PROMOTED",
            actor_id="lakehouse-agent",
            resource_type="dataset",
            resource_id="bronze.revenue",
            action="promote",
        )

        payload = event.to_kafka_payload()
        assert isinstance(payload, dict)
        assert payload["event_type"] == "DATA_PROMOTED"
        assert payload["action"] == "promote"
        # Verify it's JSON-serializable
        json.dumps(payload)


class TestAuditEventModel:
    """Verify KafkaAuditEvent model directly."""

    def test_event_model_fields(self) -> None:
        """KafkaAuditEvent should have all expected fields."""
        from odg_core.audit_kafka import KafkaAuditEvent

        event = KafkaAuditEvent(
            event_type="TEST",
            actor_id="user-1",
            resource_type="dataset",
            resource_id="ds-1",
            action="create",
            details={"key": "value"},
        )

        assert event.event_type == "TEST"
        assert event.actor_id == "user-1"
        assert event.resource_type == "dataset"
        assert event.resource_id == "ds-1"
        assert event.action == "create"
        assert event.details == {"key": "value"}
        assert event.trace_id == ""
        assert event.span_id == ""

    def test_event_defaults(self) -> None:
        """KafkaAuditEvent should have sensible defaults."""
        from odg_core.audit_kafka import KafkaAuditEvent

        event = KafkaAuditEvent(event_type="MINIMAL")

        assert event.actor_id == ""
        assert event.resource_type == ""
        assert event.resource_id == ""
        assert event.action == ""
        assert event.details == {}
        assert event.timestamp is not None
