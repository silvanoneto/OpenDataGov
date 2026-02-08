"""Tests for odg_core enums."""

from odg_core.enums import (
    AuditEventType,
    DataClassification,
    DecisionStatus,
    DecisionType,
    ExpertCapability,
    MedallionLayer,
    RACIRole,
    VetoStatus,
    VoteValue,
)


def test_raci_roles() -> None:
    assert RACIRole.RESPONSIBLE.value == "responsible"
    assert RACIRole.ACCOUNTABLE.value == "accountable"
    assert RACIRole.CONSULTED.value == "consulted"
    assert RACIRole.INFORMED.value == "informed"
    assert len(RACIRole) == 4


def test_data_classification_ordering() -> None:
    levels = list(DataClassification)
    assert levels == [
        DataClassification.PUBLIC,
        DataClassification.INTERNAL,
        DataClassification.CONFIDENTIAL,
        DataClassification.RESTRICTED,
        DataClassification.TOP_SECRET,
    ]


def test_medallion_layers() -> None:
    assert MedallionLayer.BRONZE.value == "bronze"
    assert MedallionLayer.PLATINUM.value == "platinum"
    assert len(MedallionLayer) == 4


def test_decision_lifecycle_states() -> None:
    assert DecisionStatus.PENDING.value == "pending"
    assert DecisionStatus.AWAITING_APPROVAL.value == "awaiting_approval"
    assert DecisionStatus.APPROVED.value == "approved"
    assert DecisionStatus.REJECTED.value == "rejected"
    assert DecisionStatus.VETOED.value == "vetoed"
    assert DecisionStatus.ESCALATED.value == "escalated"


def test_decision_types() -> None:
    assert DecisionType.DATA_PROMOTION.value == "data_promotion"
    assert DecisionType.EMERGENCY.value == "emergency"
    assert len(DecisionType) == 6


def test_vote_values() -> None:
    assert len(VoteValue) == 3


def test_veto_statuses() -> None:
    assert VetoStatus.ACTIVE.value == "active"
    assert VetoStatus.EXPIRED.value == "expired"
    assert VetoStatus.OVERRIDDEN.value == "overridden"


def test_audit_event_types() -> None:
    assert AuditEventType.DECISION_CREATED.value == "decision_created"
    assert AuditEventType.VETO_EXERCISED.value == "veto_exercised"
    assert len(AuditEventType) == 14


def test_expert_capabilities() -> None:
    assert ExpertCapability.SQL_GENERATION.value == "sql_generation"
    assert ExpertCapability.METADATA_DISCOVERY.value == "metadata_discovery"
    assert len(ExpertCapability) == 5
