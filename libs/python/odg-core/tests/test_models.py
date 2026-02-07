"""Tests for odg_core Pydantic V2 models."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
from pydantic import ValidationError

from odg_core.enums import (
    DecisionStatus,
    DecisionType,
    MedallionLayer,
    RACIRole,
    VetoStatus,
    VoteValue,
)
from odg_core.models import (
    ApprovalRecord,
    ExpertRegistration,
    GovernanceDecision,
    PromotionMetadata,
    RACIAssignment,
    VetoRecord,
)


class TestGovernanceDecision:
    def test_create_minimal(self) -> None:
        d = GovernanceDecision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Promote dataset X to Gold",
            domain_id="finance",
            created_by="user-1",
        )
        assert d.status == DecisionStatus.PENDING
        assert isinstance(d.id, uuid.UUID)
        assert d.metadata == {}

    def test_create_with_promotion_metadata(self) -> None:
        d = GovernanceDecision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Promote to Gold",
            domain_id="sales",
            created_by="user-1",
            promotion=PromotionMetadata(
                source_layer=MedallionLayer.SILVER,
                target_layer=MedallionLayer.GOLD,
            ),
        )
        assert d.promotion is not None
        assert d.promotion.source_layer == MedallionLayer.SILVER
        assert d.promotion.target_layer == MedallionLayer.GOLD

    def test_flat_fields_assembled_into_promotion(self) -> None:
        """Flat source_layer/target_layer dicts are folded into promotion."""
        d = GovernanceDecision.model_validate(
            {
                "decision_type": DecisionType.DATA_PROMOTION,
                "title": "Promote to Gold",
                "domain_id": "sales",
                "created_by": "user-1",
                "source_layer": MedallionLayer.SILVER,
                "target_layer": MedallionLayer.GOLD,
            }
        )
        assert d.promotion is not None
        assert d.promotion.source_layer == MedallionLayer.SILVER
        assert d.promotion.target_layer == MedallionLayer.GOLD

    def test_title_cannot_be_empty(self) -> None:
        with pytest.raises(ValidationError):
            GovernanceDecision(
                decision_type=DecisionType.SCHEMA_CHANGE,
                title="",
                domain_id="hr",
                created_by="user-1",
            )

    def test_orm_row_with_promotion_assembled(self) -> None:
        """ORM-like objects with flat attributes are folded into promotion."""
        now = datetime.now(UTC)

        class FakeRow:
            id = uuid.uuid4()
            decision_type = DecisionType.DATA_PROMOTION
            title = "Promote"
            description = ""
            status = DecisionStatus.PENDING
            domain_id = "sales"
            created_by = "user-1"
            created_at = now
            updated_at = now
            metadata_json: ClassVar[dict[str, object]] = {}
            source_layer = MedallionLayer.SILVER
            target_layer = MedallionLayer.GOLD
            data_classification = None

        d = GovernanceDecision.model_validate(FakeRow())
        assert d.promotion is not None
        assert d.promotion.source_layer == MedallionLayer.SILVER
        assert d.promotion.target_layer == MedallionLayer.GOLD
        assert d.promotion.data_classification is None

    def test_orm_row_without_promotion(self) -> None:
        """ORM-like objects without source/target_layer have no promotion."""
        now = datetime.now(UTC)

        class FakeRow:
            id = uuid.uuid4()
            decision_type = DecisionType.SCHEMA_CHANGE
            title = "Schema change"
            description = ""
            status = DecisionStatus.PENDING
            domain_id = "hr"
            created_by = "user-1"
            created_at = now
            updated_at = now
            metadata_json: ClassVar[dict[str, object]] = {}
            source_layer = None
            target_layer = None
            data_classification = None

        d = GovernanceDecision.model_validate(FakeRow())
        assert d.promotion is None

    def test_is_expired_no_expiry(self) -> None:
        v = VetoRecord(
            decision_id=uuid.uuid4(),
            vetoed_by="owner-1",
            vetoed_by_role=RACIRole.ACCOUNTABLE,
            reason="Test",
            status=VetoStatus.ACTIVE,
            expires_at=None,
        )
        assert v.is_expired is False

    def test_from_attributes(self) -> None:
        assert GovernanceDecision.model_config["from_attributes"] is True


class TestApprovalRecord:
    def test_create(self) -> None:
        decision_id = uuid.uuid4()
        a = ApprovalRecord(
            decision_id=decision_id,
            voter_id="steward-1",
            voter_role=RACIRole.ACCOUNTABLE,
            vote=VoteValue.APPROVE,
            comment="Looks good",
        )
        assert a.decision_id == decision_id
        assert a.voter_role == RACIRole.ACCOUNTABLE
        assert a.vote == VoteValue.APPROVE

    def test_default_comment_is_empty(self) -> None:
        a = ApprovalRecord(
            decision_id=uuid.uuid4(),
            voter_id="user-1",
            voter_role=RACIRole.CONSULTED,
            vote=VoteValue.ABSTAIN,
        )
        assert a.comment == ""


class TestVetoRecord:
    def test_compute_normal_expiry(self) -> None:
        v = VetoRecord(
            decision_id=uuid.uuid4(),
            vetoed_by="owner-1",
            vetoed_by_role=RACIRole.ACCOUNTABLE,
            reason="Data quality insufficient",
        )
        expiry = v.compute_expiry(is_emergency=False)
        expected = v.vetoed_at + timedelta(hours=24)
        assert abs((expiry - expected).total_seconds()) < 1

    def test_compute_emergency_expiry(self) -> None:
        v = VetoRecord(
            decision_id=uuid.uuid4(),
            vetoed_by="owner-1",
            vetoed_by_role=RACIRole.ACCOUNTABLE,
            reason="Emergency issue",
        )
        expiry = v.compute_expiry(is_emergency=True)
        expected = v.vetoed_at + timedelta(hours=1)
        assert abs((expiry - expected).total_seconds()) < 1

    def test_is_expired_active_past_expiry(self) -> None:
        v = VetoRecord(
            decision_id=uuid.uuid4(),
            vetoed_by="owner-1",
            vetoed_by_role=RACIRole.ACCOUNTABLE,
            reason="Test",
            status=VetoStatus.ACTIVE,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert v.is_expired is True

    def test_is_expired_active_before_expiry(self) -> None:
        v = VetoRecord(
            decision_id=uuid.uuid4(),
            vetoed_by="owner-1",
            vetoed_by_role=RACIRole.ACCOUNTABLE,
            reason="Test",
            status=VetoStatus.ACTIVE,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert v.is_expired is False

    def test_is_expired_overridden(self) -> None:
        v = VetoRecord(
            decision_id=uuid.uuid4(),
            vetoed_by="owner-1",
            vetoed_by_role=RACIRole.ACCOUNTABLE,
            reason="Test",
            status=VetoStatus.OVERRIDDEN,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert v.is_expired is False

    def test_reason_cannot_be_empty(self) -> None:
        with pytest.raises(ValidationError):
            VetoRecord(
                decision_id=uuid.uuid4(),
                vetoed_by="owner-1",
                vetoed_by_role=RACIRole.ACCOUNTABLE,
                reason="",
            )


class TestRACIAssignment:
    def test_create(self) -> None:
        a = RACIAssignment(
            user_id="user-1",
            domain_id="finance",
            role=RACIRole.RESPONSIBLE,
            assigned_by="admin",
        )
        assert a.role == RACIRole.RESPONSIBLE


class TestExpertRegistration:
    def test_create(self) -> None:
        e = ExpertRegistration(
            name="data-expert",
            description="SQL generation and data analysis",
            endpoint="http://localhost:8002",
            capabilities=["sql_generation", "data_analysis"],
        )
        assert e.is_active is False
        assert e.approved_decision_id is None
        assert len(e.capabilities) == 2
