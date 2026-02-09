"""Event schemas for Kafka topics (ADR-091)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """Base event with common fields."""

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    source_service: str
    trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEventKafka(BaseEvent):
    """Audit event for Kafka streaming (odg.audit.events).

    High-volume event for audit trail streaming and replay.
    """

    event_type: str = "audit"
    entity_type: str
    entity_id: str
    actor_id: str
    action: str
    description: str
    details: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str | None = None
    event_hash: str


class GovernanceDecisionEvent(BaseEvent):
    """Governance decision state change event (odg.governance.decisions)."""

    event_type: str = "governance_decision"
    decision_id: uuid.UUID
    decision_type: str
    title: str
    status: str
    domain_id: str
    created_by: str
    change_type: str  # created, submitted, approved, rejected, vetoed


class QualityReportEvent(BaseEvent):
    """Quality report event (odg.quality.reports)."""

    event_type: str = "quality_report"
    report_id: uuid.UUID
    dataset_id: str
    domain_id: str
    layer: str
    dq_score: float
    passed: bool
    suite_name: str
    expectations_passed: int
    expectations_failed: int
    expectations_total: int


class LineageUpdateEvent(BaseEvent):
    """Lineage graph update event (odg.lineage.updates)."""

    event_type: str = "lineage_update"
    dataset_id: str
    operation: str  # added, updated, removed
    upstream_datasets: list[str] = Field(default_factory=list)
    downstream_datasets: list[str] = Field(default_factory=list)
    lineage_metadata: dict[str, Any] = Field(default_factory=dict)
