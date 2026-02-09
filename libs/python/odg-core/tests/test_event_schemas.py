"""Tests for event schemas module."""

from __future__ import annotations

import uuid

from odg_core.events.event_schemas import (
    AuditEventKafka,
    BaseEvent,
    GovernanceDecisionEvent,
    LineageUpdateEvent,
    QualityReportEvent,
)


class TestBaseEvent:
    def test_create_base_event(self) -> None:
        e = BaseEvent(event_type="test", source_service="governance-engine")
        assert e.event_type == "test"
        assert e.source_service == "governance-engine"
        assert isinstance(e.event_id, uuid.UUID)
        assert e.timestamp is not None
        assert e.trace_id is None
        assert e.metadata == {}

    def test_serialization(self) -> None:
        e = BaseEvent(event_type="test", source_service="svc")
        data = e.model_dump()
        assert "event_id" in data
        assert data["event_type"] == "test"


class TestAuditEventKafka:
    def test_create_audit_event(self) -> None:
        e = AuditEventKafka(
            source_service="governance-engine",
            entity_type="decision",
            entity_id="dec-1",
            actor_id="user-1",
            action="created",
            description="Decision created",
            event_hash="abc123",
        )
        assert e.event_type == "audit"
        assert e.entity_type == "decision"
        assert e.entity_id == "dec-1"
        assert e.previous_hash is None

    def test_with_previous_hash(self) -> None:
        e = AuditEventKafka(
            source_service="svc",
            entity_type="dataset",
            entity_id="ds-1",
            actor_id="user-1",
            action="updated",
            description="Dataset updated",
            event_hash="def456",
            previous_hash="abc123",
        )
        assert e.previous_hash == "abc123"


class TestGovernanceDecisionEvent:
    def test_create_decision_event(self) -> None:
        dec_id = uuid.uuid4()
        e = GovernanceDecisionEvent(
            source_service="governance-engine",
            decision_id=dec_id,
            decision_type="data_promotion",
            title="Promote dataset",
            status="approved",
            domain_id="finance",
            created_by="user-1",
            change_type="approved",
        )
        assert e.event_type == "governance_decision"
        assert e.decision_id == dec_id
        assert e.change_type == "approved"


class TestQualityReportEvent:
    def test_create_quality_event(self) -> None:
        report_id = uuid.uuid4()
        e = QualityReportEvent(
            source_service="quality-gate",
            report_id=report_id,
            dataset_id="gold.customers",
            domain_id="finance",
            layer="gold",
            dq_score=0.97,
            passed=True,
            suite_name="completeness",
            expectations_passed=10,
            expectations_failed=0,
            expectations_total=10,
        )
        assert e.event_type == "quality_report"
        assert e.dq_score == 0.97
        assert e.passed is True
        assert e.expectations_total == 10


class TestLineageUpdateEvent:
    def test_create_lineage_event(self) -> None:
        e = LineageUpdateEvent(
            source_service="lakehouse-agent",
            dataset_id="gold.customers",
            operation="added",
            upstream_datasets=["silver.customers"],
            downstream_datasets=["platinum.customers"],
        )
        assert e.event_type == "lineage_update"
        assert e.operation == "added"
        assert len(e.upstream_datasets) == 1
        assert len(e.downstream_datasets) == 1

    def test_default_lists(self) -> None:
        e = LineageUpdateEvent(
            source_service="svc",
            dataset_id="ds-1",
            operation="updated",
        )
        assert e.upstream_datasets == []
        assert e.downstream_datasets == []
        assert e.lineage_metadata == {}
