"""Tests for Kafka event streaming."""

from __future__ import annotations

import socket
import uuid

import pytest

from odg_core.events.event_schemas import (
    AuditEventKafka,
    GovernanceDecisionEvent,
    LineageUpdateEvent,
    QualityReportEvent,
)
from odg_core.events.kafka_publisher import TOPICS, KafkaPublisher


def _kafka_available() -> bool:
    """Check if Kafka external listener is reachable."""
    try:
        s = socket.socket()
        s.settimeout(1)
        s.connect(("localhost", 9094))
        s.close()
        return True
    except OSError:
        return False


def test_kafka_topics_defined() -> None:
    """Test that Kafka topics are properly defined."""
    assert "audit_event" in TOPICS
    assert "decision_created" in TOPICS
    assert "quality_report_created" in TOPICS
    assert "lineage_updated" in TOPICS

    # Verify topic naming convention (odg.*)
    for topic in TOPICS.values():
        assert topic.startswith("odg."), f"Topic {topic} should start with 'odg.'"


def test_audit_event_schema() -> None:
    """Test AuditEventKafka schema."""
    event = AuditEventKafka(
        source_service="test-service",
        entity_type="decision",
        entity_id="test-entity",
        actor_id="test-actor",
        action="created",
        description="Test audit event",
        event_hash="abc123",
    )

    assert event.event_type == "audit"
    assert event.entity_type == "decision"
    assert event.event_id is not None
    assert event.timestamp is not None

    # Test serialization
    payload = event.model_dump(mode="json")
    assert isinstance(payload, dict)
    assert "event_id" in payload
    assert "timestamp" in payload


def test_governance_decision_event_schema() -> None:
    """Test GovernanceDecisionEvent schema."""
    decision_id = uuid.uuid4()
    event = GovernanceDecisionEvent(
        source_service="governance-engine",
        decision_id=decision_id,
        decision_type="data_promotion",
        title="Test Decision",
        status="pending",
        domain_id="finance",
        created_by="user-1",
        change_type="created",
    )

    assert event.event_type == "governance_decision"
    assert event.decision_id == decision_id
    assert event.change_type == "created"


def test_quality_report_event_schema() -> None:
    """Test QualityReportEvent schema."""
    report_id = uuid.uuid4()
    event = QualityReportEvent(
        source_service="quality-gate",
        report_id=report_id,
        dataset_id="gold.sales",
        domain_id="finance",
        layer="gold",
        dq_score=0.95,
        passed=True,
        suite_name="test_suite",
        expectations_passed=95,
        expectations_failed=5,
        expectations_total=100,
    )

    assert event.event_type == "quality_report"
    assert event.report_id == report_id
    assert event.dq_score == 0.95
    assert event.passed is True


def test_lineage_update_event_schema() -> None:
    """Test LineageUpdateEvent schema."""
    event = LineageUpdateEvent(
        source_service="lakehouse-agent",
        dataset_id="gold.sales",
        operation="added",
        upstream_datasets=["silver.sales", "silver.customers"],
        downstream_datasets=["reports.sales_analysis"],
    )

    assert event.event_type == "lineage_update"
    assert event.operation == "added"
    assert len(event.upstream_datasets) == 2
    assert len(event.downstream_datasets) == 1


@pytest.mark.asyncio
async def test_kafka_publisher_connect() -> None:
    """Test KafkaPublisher connect/disconnect with mocked broker."""
    from unittest.mock import AsyncMock, patch

    publisher = KafkaPublisher()
    mock_producer = AsyncMock()

    with patch("odg_core.events.kafka_publisher.AIOKafkaProducer", return_value=mock_producer):
        await publisher.connect("localhost:9094")

    assert publisher.is_connected
    mock_producer.start.assert_awaited_once()

    await publisher.disconnect()
    assert not publisher.is_connected
    mock_producer.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_kafka_publisher_graceful_degradation() -> None:
    """Test that publisher degrades gracefully when Kafka is unavailable."""
    publisher = KafkaPublisher()
    # Don't connect to Kafka

    # Should not raise exception
    await publisher.publish("audit_event", {"test": "data"})
    await publisher.publish_batch([("audit_event", {"test": "data"})])

    assert not publisher.is_connected
