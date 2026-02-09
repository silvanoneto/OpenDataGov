"""Tests for Kafka consumer module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from odg_core.events.kafka_consumer import (
    AuditEventProcessor,
    EventProcessor,
    GovernanceDecisionProcessor,
    KafkaConsumer,
)


class TestKafkaConsumerInit:
    def test_initial_state(self) -> None:
        consumer = KafkaConsumer(group_id="test-group")
        assert consumer.group_id == "test-group"
        assert consumer.bootstrap_servers == "localhost:9092"
        assert consumer.auto_offset_reset == "earliest"
        assert consumer.is_connected is False

    def test_custom_params(self) -> None:
        consumer = KafkaConsumer(
            group_id="custom",
            bootstrap_servers="kafka:9094",
            auto_offset_reset="latest",
        )
        assert consumer.group_id == "custom"
        assert consumer.bootstrap_servers == "kafka:9094"
        assert consumer.auto_offset_reset == "latest"


class TestKafkaConsumerConnect:
    @pytest.mark.asyncio
    async def test_connect_creates_consumer(self) -> None:
        mock_aio = AsyncMock()
        consumer = KafkaConsumer(group_id="test")
        with patch("odg_core.events.kafka_consumer.AIOKafkaConsumer", return_value=mock_aio):
            await consumer.connect()
        assert consumer.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_failure_raises(self) -> None:
        consumer = KafkaConsumer(group_id="test")
        with (
            patch(
                "odg_core.events.kafka_consumer.AIOKafkaConsumer",
                side_effect=RuntimeError("fail"),
            ),
            pytest.raises(RuntimeError),
        ):
            await consumer.connect()


class TestKafkaConsumerStop:
    @pytest.mark.asyncio
    async def test_stop_when_connected(self) -> None:
        consumer = KafkaConsumer(group_id="test")
        consumer._consumer = AsyncMock()
        await consumer.stop()
        assert consumer.is_connected is False

    @pytest.mark.asyncio
    async def test_stop_when_not_connected(self) -> None:
        consumer = KafkaConsumer(group_id="test")
        await consumer.stop()  # Should not raise


class TestKafkaConsumerConsume:
    @pytest.mark.asyncio
    async def test_consume_without_subscribe_raises(self) -> None:
        consumer = KafkaConsumer(group_id="test")
        handler = AsyncMock()
        with pytest.raises(RuntimeError, match="not initialized"):
            await consumer.consume(handler)


class TestEventProcessor:
    @pytest.mark.asyncio
    async def test_base_processor_not_implemented(self) -> None:
        proc = EventProcessor()
        with pytest.raises(NotImplementedError):
            await proc.process("topic", {"data": "test"})


class TestAuditEventProcessor:
    @pytest.mark.asyncio
    async def test_process_audit_event(self) -> None:
        proc = AuditEventProcessor()
        await proc.process("odg.audit.events", {"event_hash": "h1", "entity_id": "e1"})

    @pytest.mark.asyncio
    async def test_process_non_audit_topic(self) -> None:
        proc = AuditEventProcessor()
        await proc.process("other.topic", {"data": "test"})


class TestGovernanceDecisionProcessor:
    @pytest.mark.asyncio
    async def test_process_decision_event(self) -> None:
        proc = GovernanceDecisionProcessor()
        await proc.process(
            "odg.governance.decisions",
            {"decision_id": "d1", "status": "approved"},
        )

    @pytest.mark.asyncio
    async def test_process_non_governance_topic(self) -> None:
        proc = GovernanceDecisionProcessor()
        await proc.process("other.topic", {"data": "test"})
