"""Tests for Kafka audit consumer and producer."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from governance_engine.events.kafka_consumer import (
    KafkaAuditConsumer,
    compute_hash_chain,
)
from governance_engine.events.kafka_producer import KafkaAuditProducer

# ---------------------------------------------------------------------------
# compute_hash_chain
# ---------------------------------------------------------------------------


class TestComputeHashChain:
    def test_deterministic(self) -> None:
        h1 = compute_hash_chain("data1", "genesis")
        h2 = compute_hash_chain("data1", "genesis")
        assert h1 == h2

    def test_different_data_different_hash(self) -> None:
        h1 = compute_hash_chain("data1", "genesis")
        h2 = compute_hash_chain("data2", "genesis")
        assert h1 != h2

    def test_different_previous_hash(self) -> None:
        h1 = compute_hash_chain("data", "genesis")
        h2 = compute_hash_chain("data", "other")
        assert h1 != h2

    def test_returns_hex_string(self) -> None:
        h = compute_hash_chain("hello", "world")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# KafkaAuditConsumer
# ---------------------------------------------------------------------------


class TestKafkaAuditConsumerInit:
    def test_defaults(self) -> None:
        consumer = KafkaAuditConsumer()
        assert consumer._topic == "odg.audit.events"
        assert consumer._group_id == "odg-audit-consumer"
        assert consumer._last_hash == "genesis"
        assert consumer._running is False
        assert consumer._consumer is None

    def test_custom_params(self) -> None:
        consumer = KafkaAuditConsumer(topic="custom.topic", group_id="my-group")
        assert consumer._topic == "custom.topic"
        assert consumer._group_id == "my-group"


class TestKafkaAuditConsumerConnect:
    async def test_connect_success(self) -> None:
        consumer = KafkaAuditConsumer()
        mock_aiokafka = MagicMock()
        mock_instance = AsyncMock()
        mock_aiokafka.AIOKafkaConsumer.return_value = mock_instance

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            await consumer.connect("localhost:9092")

        assert consumer._consumer is mock_instance
        mock_instance.start.assert_awaited_once()

    async def test_connect_failure_sets_none(self) -> None:
        consumer = KafkaAuditConsumer()
        mock_aiokafka = MagicMock()
        mock_instance = AsyncMock()
        mock_instance.start.side_effect = Exception("connection refused")
        mock_aiokafka.AIOKafkaConsumer.return_value = mock_instance

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            await consumer.connect("localhost:9092")

        assert consumer._consumer is None


class TestKafkaAuditConsumerDisconnect:
    async def test_disconnect_with_consumer(self) -> None:
        consumer = KafkaAuditConsumer()
        mock_inner = AsyncMock()
        consumer._consumer = mock_inner
        consumer._running = True

        await consumer.disconnect()

        assert consumer._running is False
        mock_inner.stop.assert_awaited_once()

    async def test_disconnect_without_consumer(self) -> None:
        consumer = KafkaAuditConsumer()
        await consumer.disconnect()
        assert consumer._running is False


class TestKafkaAuditConsumerConsume:
    async def test_consume_no_consumer_returns_immediately(self) -> None:
        consumer = KafkaAuditConsumer()
        persist_fn = AsyncMock()
        await consumer.consume(persist_fn)
        persist_fn.assert_not_awaited()

    async def test_consume_processes_messages(self) -> None:
        consumer = KafkaAuditConsumer()
        event_data = {"event_type": "test", "actor": "user-1"}

        msg = MagicMock()
        msg.value = event_data

        mock_inner = AsyncMock()

        async def _fake_iter(_self: Any) -> Any:
            yield msg
            consumer._running = False

        mock_inner.__aiter__ = _fake_iter
        consumer._consumer = mock_inner

        persisted: list[tuple[dict[str, Any], str]] = []

        async def persist_fn(event: dict[str, Any], chain_hash: str) -> None:
            persisted.append((event, chain_hash))

        await consumer.consume(persist_fn)

        assert len(persisted) == 1
        assert persisted[0][0] == event_data
        assert len(persisted[0][1]) == 64  # SHA-256 hex
        assert consumer._last_hash == persisted[0][1]

    async def test_consume_stops_when_running_false(self) -> None:
        consumer = KafkaAuditConsumer()

        msg = MagicMock()
        msg.value = {"event_type": "test"}

        mock_inner = AsyncMock()

        async def _fake_iter(_self: Any) -> Any:
            consumer._running = False
            yield msg

        mock_inner.__aiter__ = _fake_iter
        consumer._consumer = mock_inner

        persist_fn = AsyncMock()
        await consumer.consume(persist_fn)

    async def test_consume_handles_exception(self) -> None:
        consumer = KafkaAuditConsumer()

        mock_inner = AsyncMock()

        async def _fake_iter(_self: Any) -> Any:
            raise RuntimeError("kafka error")
            yield  # make it a generator

        mock_inner.__aiter__ = _fake_iter
        consumer._consumer = mock_inner

        persist_fn = AsyncMock()
        await consumer.consume(persist_fn)


# ---------------------------------------------------------------------------
# KafkaAuditProducer
# ---------------------------------------------------------------------------


class TestKafkaAuditProducerInit:
    def test_defaults(self) -> None:
        producer = KafkaAuditProducer()
        assert producer._topic == "odg.audit.events"
        assert producer._producer is None
        assert producer.is_connected is False

    def test_custom_topic(self) -> None:
        producer = KafkaAuditProducer(topic="custom.topic")
        assert producer._topic == "custom.topic"


class TestKafkaAuditProducerConnect:
    async def test_connect_success(self) -> None:
        producer = KafkaAuditProducer()
        mock_aiokafka = MagicMock()
        mock_instance = AsyncMock()
        mock_aiokafka.AIOKafkaProducer.return_value = mock_instance

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            await producer.connect("localhost:9092")

        assert producer._producer is mock_instance
        assert producer.is_connected is True
        mock_instance.start.assert_awaited_once()

    async def test_connect_failure_sets_none(self) -> None:
        producer = KafkaAuditProducer()
        mock_aiokafka = MagicMock()
        mock_instance = AsyncMock()
        mock_instance.start.side_effect = Exception("connection refused")
        mock_aiokafka.AIOKafkaProducer.return_value = mock_instance

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            await producer.connect("localhost:9092")

        assert producer._producer is None
        assert producer.is_connected is False


class TestKafkaAuditProducerDisconnect:
    async def test_disconnect_with_producer(self) -> None:
        producer = KafkaAuditProducer()
        mock_inner = AsyncMock()
        producer._producer = mock_inner

        await producer.disconnect()
        mock_inner.stop.assert_awaited_once()

    async def test_disconnect_without_producer(self) -> None:
        producer = KafkaAuditProducer()
        await producer.disconnect()  # should not raise


class TestKafkaAuditProducerPublish:
    async def test_publish_when_not_connected(self) -> None:
        producer = KafkaAuditProducer()
        await producer.publish_audit_event({"event": "test"})
        # No error, silently skipped

    async def test_publish_success(self) -> None:
        producer = KafkaAuditProducer()
        mock_inner = AsyncMock()
        producer._producer = mock_inner

        event: dict[str, Any] = {"event_type": "test", "actor_id": "u1"}

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={"traceparent": "00-abc-def-01"},
        ):
            await producer.publish_audit_event(event)

        mock_inner.send_and_wait.assert_awaited_once_with("odg.audit.events", event)
        assert event["_trace"] == {"traceparent": "00-abc-def-01"}

    async def test_publish_no_trace_headers(self) -> None:
        producer = KafkaAuditProducer()
        mock_inner = AsyncMock()
        producer._producer = mock_inner

        event: dict[str, Any] = {"event_type": "test"}

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={},
        ):
            await producer.publish_audit_event(event)

        mock_inner.send_and_wait.assert_awaited_once()
        assert "_trace" not in event

    async def test_publish_does_not_overwrite_existing_trace(self) -> None:
        producer = KafkaAuditProducer()
        mock_inner = AsyncMock()
        producer._producer = mock_inner

        event: dict[str, Any] = {"event_type": "test", "_trace": {"existing": "val"}}

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={"traceparent": "new"},
        ):
            await producer.publish_audit_event(event)

        # setdefault should preserve existing _trace
        assert event["_trace"] == {"existing": "val"}

    async def test_publish_exception_handled(self) -> None:
        producer = KafkaAuditProducer()
        mock_inner = AsyncMock()
        mock_inner.send_and_wait.side_effect = Exception("send failed")
        producer._producer = mock_inner

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={},
        ):
            await producer.publish_audit_event({"event": "test"})
        # Should not raise
