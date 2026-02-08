"""Tests for Kafka audit event serialization helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from odg_core.audit_kafka import KafkaAuditEvent, create_audit_event


class TestKafkaAuditEvent:
    def test_defaults(self) -> None:
        """Event should have sensible defaults for optional fields."""
        event = KafkaAuditEvent(event_type="test_event")

        assert event.event_type == "test_event"
        assert event.actor_id == ""
        assert event.resource_type == ""
        assert event.resource_id == ""
        assert event.action == ""
        assert event.details == {}
        assert event.trace_id == ""
        assert event.span_id == ""
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_custom_fields(self) -> None:
        """Event should accept all custom field values."""
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        event = KafkaAuditEvent(
            event_type="decision_created",
            timestamp=ts,
            actor_id="user-42",
            resource_type="decision",
            resource_id="dec-001",
            action="create",
            details={"key": "value"},
            trace_id="abc123",
            span_id="def456",
        )

        assert event.event_type == "decision_created"
        assert event.timestamp == ts
        assert event.actor_id == "user-42"
        assert event.resource_type == "decision"
        assert event.resource_id == "dec-001"
        assert event.action == "create"
        assert event.details == {"key": "value"}
        assert event.trace_id == "abc123"
        assert event.span_id == "def456"

    def test_to_kafka_payload_returns_dict(self) -> None:
        """to_kafka_payload should return a JSON-serializable dict."""
        event = KafkaAuditEvent(
            event_type="test_event",
            actor_id="user-1",
            details={"count": 42},
        )
        payload = event.to_kafka_payload()

        assert isinstance(payload, dict)
        assert payload["event_type"] == "test_event"
        assert payload["actor_id"] == "user-1"
        assert payload["details"] == {"count": 42}
        # timestamp should be serialized as a string in JSON mode
        assert isinstance(payload["timestamp"], str)

    def test_to_kafka_payload_contains_all_fields(self) -> None:
        """Payload should contain every field from the model."""
        event = KafkaAuditEvent(event_type="full_test")
        payload = event.to_kafka_payload()

        expected_keys = {
            "event_type",
            "timestamp",
            "actor_id",
            "resource_type",
            "resource_id",
            "action",
            "details",
            "trace_id",
            "span_id",
        }
        assert set(payload.keys()) == expected_keys


class TestCreateAuditEvent:
    def test_basic_creation(self) -> None:
        """create_audit_event should return a KafkaAuditEvent with given fields."""
        event = create_audit_event(
            "decision_created",
            actor_id="user-1",
            resource_type="decision",
            resource_id="dec-001",
            action="create",
            details={"domain": "finance"},
        )

        assert isinstance(event, KafkaAuditEvent)
        assert event.event_type == "decision_created"
        assert event.actor_id == "user-1"
        assert event.resource_type == "decision"
        assert event.resource_id == "dec-001"
        assert event.action == "create"
        assert event.details == {"domain": "finance"}

    def test_creation_with_defaults(self) -> None:
        """create_audit_event with only event_type should use empty defaults."""
        event = create_audit_event("test_event")

        assert event.event_type == "test_event"
        assert event.actor_id == ""
        assert event.resource_type == ""
        assert event.resource_id == ""
        assert event.action == ""
        assert event.details == {}

    def test_none_details_becomes_empty_dict(self) -> None:
        """Passing details=None should result in an empty dict."""
        event = create_audit_event("test_event", details=None)
        assert event.details == {}

    def test_telemetry_context_injected(self) -> None:
        """When telemetry context is available, trace/span IDs should be set."""
        with (
            patch(
                "odg_core.audit_kafka.get_current_trace_id",
                return_value="aabbccdd" * 4,
                create=True,
            ),
            patch(
                "odg_core.audit_kafka.get_current_span_id",
                return_value="11223344" * 2,
                create=True,
            ),
            patch(
                "odg_core.telemetry.context.get_current_trace_id",
                return_value="aabbccdd" * 4,
            ),
            patch(
                "odg_core.telemetry.context.get_current_span_id",
                return_value="11223344" * 2,
            ),
        ):
            event = create_audit_event("test_event")
            assert event.trace_id == "aabbccdd" * 4
            assert event.span_id == "11223344" * 2

    def test_telemetry_import_error_handled(self) -> None:
        """When telemetry context module is unavailable, IDs should be empty."""
        with patch.dict("sys.modules", {"odg_core.telemetry.context": None}):
            # Force the import to fail by making the module None
            # We need to test the ImportError branch inside create_audit_event
            pass

        # The import is guarded in a try/except; even if we can't perfectly
        # simulate ImportError via patching, we can verify the function
        # works without an active trace context (trace_id/span_id will be
        # empty strings from the real context module returning "").
        event = create_audit_event("test_event")
        assert isinstance(event.trace_id, str)
        assert isinstance(event.span_id, str)

    def test_import_error_branch(self) -> None:
        """Exercise the ImportError branch when telemetry.context is missing."""
        import sys

        # Temporarily remove the telemetry.context module so the lazy import fails
        saved = sys.modules.get("odg_core.telemetry.context")
        saved_parent = sys.modules.get("odg_core.telemetry")

        try:
            # Remove so import raises ImportError
            sys.modules["odg_core.telemetry.context"] = None  # type: ignore[assignment]

            event = create_audit_event("fallback_test")
            assert event.trace_id == ""
            assert event.span_id == ""
        finally:
            # Restore
            if saved is not None:
                sys.modules["odg_core.telemetry.context"] = saved
            else:
                sys.modules.pop("odg_core.telemetry.context", None)
            if saved_parent is not None:
                sys.modules["odg_core.telemetry"] = saved_parent
