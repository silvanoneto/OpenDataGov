"""Coverage tests for events/kafka_consumer and audit_kafka modules."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from odg_core.audit_kafka import (
    AuditKafkaPublisher,
    KafkaAuditEvent,
    create_audit_event,
)

# ── KafkaAuditEvent ──────────────────────────────────────────


class TestKafkaAuditEvent:
    def test_create_minimal(self) -> None:
        event = KafkaAuditEvent(event_type="test")
        assert event.event_type == "test"
        assert event.actor_id == ""
        assert event.resource_type == ""
        assert event.trace_id == ""

    def test_create_full(self) -> None:
        event = KafkaAuditEvent(
            event_type="decision.created",
            actor_id="user-1",
            resource_type="decision",
            resource_id="d-1",
            action="created",
            details={"key": "value"},
            trace_id="trace-123",
            span_id="span-456",
        )
        assert event.actor_id == "user-1"
        assert event.details == {"key": "value"}

    def test_to_kafka_payload(self) -> None:
        event = KafkaAuditEvent(event_type="test", actor_id="user-1")
        payload = event.to_kafka_payload()
        assert isinstance(payload, dict)
        assert payload["event_type"] == "test"
        assert payload["actor_id"] == "user-1"
        assert "timestamp" in payload


# ── create_audit_event ────────────────────────────────────────


class TestCreateAuditEvent:
    def test_creates_event(self) -> None:
        event = create_audit_event(
            "decision.created",
            actor_id="user-1",
            resource_type="decision",
            resource_id="d-1",
            action="created",
            details={"key": "value"},
        )
        assert isinstance(event, KafkaAuditEvent)
        assert event.event_type == "decision.created"
        assert event.actor_id == "user-1"
        assert event.details == {"key": "value"}

    def test_creates_event_minimal(self) -> None:
        event = create_audit_event("audit.test")
        assert event.event_type == "audit.test"
        assert event.actor_id == ""
        assert event.details == {}

    def test_telemetry_import_failure(self) -> None:
        # create_audit_event tries to import telemetry and catches ImportError
        event = create_audit_event("test")
        assert event.trace_id == ""
        assert event.span_id == ""


# ── AuditKafkaPublisher ──────────────────────────────────────


class TestAuditKafkaPublisher:
    def _make_audit_event(self) -> Any:
        from odg_core.audit import AuditEvent
        from odg_core.enums import AuditEventType

        return AuditEvent(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id="d-1",
            actor_id="user-1",
            description="Created decision",
        ).seal()

    @pytest.mark.asyncio
    async def test_publish_event_not_connected(self) -> None:
        mock_publisher = MagicMock()
        mock_publisher.is_connected = False

        publisher = AuditKafkaPublisher(mock_publisher)
        event = self._make_audit_event()

        await publisher.publish_event(event)
        mock_publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_event_connected(self) -> None:
        mock_publisher = MagicMock()
        mock_publisher.is_connected = True
        mock_publisher.publish = AsyncMock()

        publisher = AuditKafkaPublisher(mock_publisher)
        event = self._make_audit_event()

        await publisher.publish_event(event)
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        assert call_args[0][0] == "audit_event"
        assert call_args[1]["key"] == "d-1"

    @pytest.mark.asyncio
    async def test_publish_event_error(self) -> None:
        mock_publisher = MagicMock()
        mock_publisher.is_connected = True
        mock_publisher.publish = AsyncMock(side_effect=Exception("Kafka error"))

        publisher = AuditKafkaPublisher(mock_publisher)
        event = self._make_audit_event()

        # Should not raise
        await publisher.publish_event(event)

    @pytest.mark.asyncio
    async def test_publish_batch_not_connected(self) -> None:
        mock_publisher = MagicMock()
        mock_publisher.is_connected = False

        publisher = AuditKafkaPublisher(mock_publisher)
        events = [self._make_audit_event()]

        await publisher.publish_batch(events)
        mock_publisher.publish_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_batch_empty(self) -> None:
        mock_publisher = MagicMock()
        mock_publisher.is_connected = True

        publisher = AuditKafkaPublisher(mock_publisher)
        await publisher.publish_batch([])
        mock_publisher.publish_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_batch_connected(self) -> None:
        mock_publisher = MagicMock()
        mock_publisher.is_connected = True
        mock_publisher.publish_batch = AsyncMock()

        publisher = AuditKafkaPublisher(mock_publisher)
        events = [self._make_audit_event(), self._make_audit_event()]

        await publisher.publish_batch(events)
        mock_publisher.publish_batch.assert_called_once()
        call_args = mock_publisher.publish_batch.call_args
        assert len(call_args[0][0]) == 2

    @pytest.mark.asyncio
    async def test_publish_batch_error(self) -> None:
        mock_publisher = MagicMock()
        mock_publisher.is_connected = True
        mock_publisher.publish_batch = AsyncMock(side_effect=Exception("Kafka error"))

        publisher = AuditKafkaPublisher(mock_publisher)
        events = [self._make_audit_event()]

        # Should not raise
        await publisher.publish_batch(events)


# ── KafkaConsumer ─────────────────────────────────────────────


class TestKafkaConsumer:
    def test_init(self) -> None:
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test-group", bootstrap_servers="localhost:9094")
        assert consumer.group_id == "test-group"
        assert consumer.bootstrap_servers == "localhost:9094"
        assert consumer._consumer is None
        assert consumer._running is False

    def test_is_connected_false(self) -> None:
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test")
        assert consumer.is_connected is False

    def test_is_connected_true(self) -> None:
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test")
        consumer._consumer = MagicMock()
        assert consumer.is_connected is True

    @pytest.mark.asyncio
    async def test_stop(self) -> None:
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test")
        mock_consumer = AsyncMock()
        consumer._consumer = mock_consumer
        consumer._running = True

        await consumer.stop()
        assert consumer._running is False
        assert consumer._consumer is None
        mock_consumer.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_when_not_connected(self) -> None:
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test")
        await consumer.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_consume_not_initialized(self) -> None:
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test")
        with pytest.raises(RuntimeError, match="Consumer not initialized"):
            await consumer.consume(handler=AsyncMock())

    @pytest.mark.asyncio
    async def test_consume_with_handler(self) -> None:
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test")

        msg = MagicMock()
        msg.topic = "odg.test.events"
        msg.value = {"event_id": "e-1"}
        msg.partition = 0
        msg.offset = 0

        class _MockKafkaConsumer:
            def __init__(self, messages: list[Any]) -> None:
                self._messages = list(messages)
                self.stop = AsyncMock()

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._messages:
                    return self._messages.pop(0)
                raise StopAsyncIteration

        consumer._consumer = _MockKafkaConsumer([msg])

        handler = AsyncMock()
        await consumer.consume(handler=handler)
        handler.assert_called_once_with("odg.test.events", {"event_id": "e-1"})

    @pytest.mark.asyncio
    async def test_consume_handler_retry(self) -> None:
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test")

        msg = MagicMock()
        msg.topic = "topic"
        msg.value = {"data": "test"}
        msg.partition = 0
        msg.offset = 0

        class _MockKafkaConsumer:
            def __init__(self, messages: list[Any]) -> None:
                self._messages = list(messages)
                self.stop = AsyncMock()

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._messages:
                    return self._messages.pop(0)
                raise StopAsyncIteration

        consumer._consumer = _MockKafkaConsumer([msg])

        call_count = 0

        async def failing_handler(topic: str, payload: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Transient error")

        await consumer.consume(handler=failing_handler, max_retries=3, retry_delay=0.01)
        assert call_count == 3  # Failed twice, succeeded on third


# ── EventProcessor ────────────────────────────────────────────


class TestEventProcessor:
    @pytest.mark.asyncio
    async def test_base_raises_not_implemented(self) -> None:
        from odg_core.events.kafka_consumer import EventProcessor

        processor = EventProcessor()
        with pytest.raises(NotImplementedError):
            await processor.process("topic", {"data": "test"})

    @pytest.mark.asyncio
    async def test_audit_event_processor(self) -> None:
        from odg_core.events.kafka_consumer import AuditEventProcessor

        processor = AuditEventProcessor()
        await processor.process("odg.audit.events", {"event_hash": "abc", "entity_id": "e-1"})

    @pytest.mark.asyncio
    async def test_governance_decision_processor(self) -> None:
        from odg_core.events.kafka_consumer import GovernanceDecisionProcessor

        processor = GovernanceDecisionProcessor()
        await processor.process("odg.governance.decisions", {"decision_id": "d-1", "status": "approved"})
