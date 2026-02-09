"""Tests for Kafka publisher module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from odg_core.events.kafka_publisher import TOPICS, KafkaPublisher


class TestKafkaPublisherInit:
    def test_initial_state(self) -> None:
        pub = KafkaPublisher()
        assert pub.is_connected is False
        assert pub._producer is None


class TestKafkaPublisherConnect:
    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        pub = KafkaPublisher()
        mock_producer = AsyncMock()
        with patch("odg_core.events.kafka_publisher.AIOKafkaProducer", return_value=mock_producer):
            await pub.connect("localhost:9092")
        assert pub.is_connected is True
        mock_producer.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_kafka_error(self) -> None:
        from aiokafka.errors import KafkaError

        pub = KafkaPublisher()
        mock_producer = AsyncMock()
        mock_producer.start.side_effect = KafkaError("Connection refused")
        with patch("odg_core.events.kafka_publisher.AIOKafkaProducer", return_value=mock_producer):
            await pub.connect("localhost:9092")
        assert pub.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_unexpected_error(self) -> None:
        pub = KafkaPublisher()
        with patch("odg_core.events.kafka_publisher.AIOKafkaProducer", side_effect=RuntimeError("boom")):
            await pub.connect("localhost:9092")
        assert pub.is_connected is False


class TestKafkaPublisherDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect(self) -> None:
        pub = KafkaPublisher()
        pub._producer = AsyncMock()
        await pub.disconnect()
        assert pub.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self) -> None:
        pub = KafkaPublisher()
        await pub.disconnect()  # Should not raise


class TestKafkaPublisherPublish:
    @pytest.mark.asyncio
    async def test_publish_when_not_connected(self) -> None:
        pub = KafkaPublisher()
        await pub.publish("audit_event", {"data": "test"})  # Silent skip

    @pytest.mark.asyncio
    async def test_publish_unknown_event_type(self) -> None:
        pub = KafkaPublisher()
        pub._producer = AsyncMock()
        await pub.publish("unknown_event", {"data": "test"})
        pub._producer.send_and_wait.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_publish_success(self) -> None:
        pub = KafkaPublisher()
        pub._producer = AsyncMock()
        with patch("odg_core.telemetry.context.get_trace_headers", return_value=None):
            await pub.publish("audit_event", {"data": "test"})
        pub._producer.send_and_wait.assert_awaited_once()
        call_args = pub._producer.send_and_wait.call_args
        assert call_args[0][0] == "odg.audit.events"

    @pytest.mark.asyncio
    async def test_publish_with_key(self) -> None:
        pub = KafkaPublisher()
        pub._producer = AsyncMock()
        with patch("odg_core.telemetry.context.get_trace_headers", return_value=None):
            await pub.publish("audit_event", {"data": "test"}, key="entity-1")
        call_args = pub._producer.send_and_wait.call_args
        assert call_args[1]["key"] == b"entity-1"


class TestKafkaPublisherPublishBatch:
    @pytest.mark.asyncio
    async def test_batch_when_not_connected(self) -> None:
        pub = KafkaPublisher()
        await pub.publish_batch([("audit_event", {"data": "test"})])

    @pytest.mark.asyncio
    async def test_batch_success(self) -> None:
        pub = KafkaPublisher()
        pub._producer = AsyncMock()
        with patch("odg_core.telemetry.context.get_trace_headers", return_value=None):
            await pub.publish_batch(
                [
                    ("audit_event", {"data": "1"}),
                    ("decision_created", {"data": "2"}),
                ]
            )
        assert pub._producer.send.await_count == 2
        pub._producer.flush.assert_awaited_once()


class TestTopicsMapping:
    def test_audit_topic(self) -> None:
        assert TOPICS["audit_event"] == "odg.audit.events"

    def test_governance_topics(self) -> None:
        assert TOPICS["decision_created"] == "odg.governance.decisions"
        assert TOPICS["decision_approved"] == "odg.governance.decisions"

    def test_quality_topics(self) -> None:
        assert TOPICS["quality_report_created"] == "odg.quality.reports"

    def test_lineage_topics(self) -> None:
        assert TOPICS["lineage_updated"] == "odg.lineage.updates"
