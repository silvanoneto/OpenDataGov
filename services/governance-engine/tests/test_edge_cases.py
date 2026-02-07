"""Tests for error paths, edge cases, and remaining coverage gaps."""

from __future__ import annotations

import uuid

import pytest
from governance_engine.domain.approval_service import ApprovalService
from governance_engine.domain.audit_service import AuditService
from governance_engine.domain.decision_service import DecisionService
from governance_engine.domain.role_service import RoleService
from governance_engine.domain.veto_service import VetoService
from odg_core.enums import (
    AuditEventType,
    DataClassification,
    DecisionStatus,
    DecisionType,
    MedallionLayer,
    RACIRole,
    VetoStatus,
    VoteValue,
)
from odg_core.models import PromotionMetadata


class TestDecisionServiceErrors:
    async def test_create_with_promotion_metadata(self, decision_service: DecisionService) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Promote with metadata",
            description="",
            domain_id="sales",
            created_by="user-1",
            promotion=PromotionMetadata(
                source_layer=MedallionLayer.SILVER,
                target_layer=MedallionLayer.GOLD,
                data_classification=DataClassification.CONFIDENTIAL,
            ),
        )
        assert decision.promotion is not None
        assert decision.promotion.source_layer == MedallionLayer.SILVER
        assert decision.promotion.target_layer == MedallionLayer.GOLD
        assert decision.promotion.data_classification == DataClassification.CONFIDENTIAL

    async def test_submit_nonexistent_decision(self, decision_service: DecisionService) -> None:
        with pytest.raises(ValueError, match="not found"):
            await decision_service.submit_for_approval(uuid.uuid4(), "user-1")

    async def test_finalize_nonexistent_decision(self, decision_service: DecisionService) -> None:
        with pytest.raises(ValueError, match="not found"):
            await decision_service.finalize(uuid.uuid4(), DecisionStatus.APPROVED, "user-1")

    async def test_finalize_non_awaiting_decision(self, decision_service: DecisionService) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="hr",
            created_by="user-1",
        )
        with pytest.raises(ValueError, match="must be AWAITING_APPROVAL"):
            await decision_service.finalize(decision.id, DecisionStatus.APPROVED, "user-1")

    async def test_finalize_invalid_status(self, decision_service: DecisionService) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="hr",
            created_by="user-1",
        )
        await decision_service.submit_for_approval(decision.id, "user-1")
        with pytest.raises(ValueError, match="Invalid final status"):
            await decision_service.finalize(decision.id, DecisionStatus.PENDING, "user-1")

    async def test_list_decisions(self, decision_service: DecisionService) -> None:
        await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="D1",
            description="",
            domain_id="hr",
            created_by="user-1",
        )
        result = await decision_service.list_decisions()
        assert len(result) >= 1


class TestApprovalServiceErrors:
    async def test_vote_nonexistent_decision(self, approval_service: ApprovalService) -> None:
        with pytest.raises(ValueError, match="not found"):
            await approval_service.cast_vote(
                decision_id=uuid.uuid4(),
                voter_id="user-1",
                vote=VoteValue.APPROVE,
            )

    async def test_vote_non_awaiting_decision(
        self,
        decision_service: DecisionService,
        approval_service: ApprovalService,
    ) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="hr",
            created_by="user-1",
        )
        with pytest.raises(ValueError, match="not awaiting approval"):
            await approval_service.cast_vote(
                decision_id=decision.id,
                voter_id="user-1",
                vote=VoteValue.APPROVE,
            )

    async def test_vote_no_raci_role(
        self,
        decision_service: DecisionService,
        approval_service: ApprovalService,
    ) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="hr",
            created_by="user-1",
        )
        await decision_service.submit_for_approval(decision.id, "user-1")
        with pytest.raises(ValueError, match="no RACI role"):
            await approval_service.cast_vote(
                decision_id=decision.id,
                voter_id="nobody",
                vote=VoteValue.APPROVE,
            )

    async def test_list_votes(
        self,
        decision_service: DecisionService,
        approval_service: ApprovalService,
        role_service: RoleService,
    ) -> None:
        await role_service.assign_role(user_id="v1", domain_id="test", role=RACIRole.RESPONSIBLE, assigned_by="admin")
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="test",
            created_by="v1",
        )
        await decision_service.submit_for_approval(decision.id, "v1")
        await approval_service.cast_vote(decision_id=decision.id, voter_id="v1", vote=VoteValue.ABSTAIN)
        votes = await approval_service.list_votes(decision.id)
        assert len(votes) == 1


class TestRoleServiceEdgeCases:
    async def test_duplicate_role_assignment(self, role_service: RoleService) -> None:
        await role_service.assign_role(
            user_id="dup-user", domain_id="dup-domain", role=RACIRole.RESPONSIBLE, assigned_by="admin"
        )
        with pytest.raises(ValueError, match="already has role"):
            await role_service.assign_role(
                user_id="dup-user", domain_id="dup-domain", role=RACIRole.ACCOUNTABLE, assigned_by="admin"
            )

    async def test_revoke_role(self, role_service: RoleService) -> None:
        assignment = await role_service.assign_role(
            user_id="rev-user", domain_id="rev-domain", role=RACIRole.CONSULTED, assigned_by="admin"
        )
        await role_service.revoke_role(assignment.id, "admin")
        # After revoke, domain should have no assignments
        assignments = await role_service.get_assignments_for_domain("rev-domain")
        assert len(assignments) == 0

    async def test_revoke_nonexistent(self, role_service: RoleService) -> None:
        with pytest.raises(ValueError, match="not found"):
            await role_service.revoke_role(uuid.uuid4(), "admin")

    async def test_get_assignments_for_domain(self, role_service: RoleService) -> None:
        await role_service.assign_role(user_id="u1", domain_id="dom1", role=RACIRole.RESPONSIBLE, assigned_by="admin")
        result = await role_service.get_assignments_for_domain("dom1")
        assert len(result) == 1

    async def test_get_assignments_for_user(self, role_service: RoleService) -> None:
        await role_service.assign_role(user_id="u2", domain_id="dom2", role=RACIRole.INFORMED, assigned_by="admin")
        result = await role_service.get_assignments_for_user("u2")
        assert len(result) == 1


class TestVetoServiceErrors:
    async def test_veto_nonexistent_decision(self, veto_service: VetoService) -> None:
        with pytest.raises(ValueError, match="not found"):
            await veto_service.exercise_veto(decision_id=uuid.uuid4(), vetoed_by="user-1", reason="Test")

    async def test_veto_non_awaiting_decision(
        self,
        decision_service: DecisionService,
        veto_service: VetoService,
    ) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="hr",
            created_by="user-1",
        )
        with pytest.raises(ValueError, match="must be AWAITING_APPROVAL"):
            await veto_service.exercise_veto(decision_id=decision.id, vetoed_by="user-1", reason="Test")

    async def test_veto_no_raci_role(
        self,
        decision_service: DecisionService,
        veto_service: VetoService,
    ) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="hr",
            created_by="user-1",
        )
        await decision_service.submit_for_approval(decision.id, "user-1")
        with pytest.raises(ValueError, match="no RACI role"):
            await veto_service.exercise_veto(decision_id=decision.id, vetoed_by="ghost", reason="Test")

    async def test_override_nonexistent_veto(self, veto_service: VetoService) -> None:
        with pytest.raises(ValueError, match="not found"):
            await veto_service.override_veto(veto_id=uuid.uuid4(), overridden_by="user-1")

    async def test_override_non_active_veto(
        self,
        decision_service: DecisionService,
        veto_service: VetoService,
        role_service: RoleService,
    ) -> None:
        await role_service.assign_role(user_id="r1", domain_id="d1", role=RACIRole.RESPONSIBLE, assigned_by="admin")
        await role_service.assign_role(user_id="a1", domain_id="d1", role=RACIRole.ACCOUNTABLE, assigned_by="admin")
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="d1",
            created_by="r1",
        )
        await decision_service.submit_for_approval(decision.id, "r1")
        veto = await veto_service.exercise_veto(decision_id=decision.id, vetoed_by="r1", reason="Issue")
        # Override once (succeeds)
        await veto_service.override_veto(veto_id=veto.id, overridden_by="a1")
        # Try to override already-overridden veto
        with pytest.raises(ValueError, match="not active"):
            await veto_service.override_veto(veto_id=veto.id, overridden_by="a1")

    async def test_override_no_raci_role(
        self,
        decision_service: DecisionService,
        veto_service: VetoService,
        role_service: RoleService,
    ) -> None:
        await role_service.assign_role(user_id="r2", domain_id="d2", role=RACIRole.RESPONSIBLE, assigned_by="admin")
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="d2",
            created_by="r2",
        )
        await decision_service.submit_for_approval(decision.id, "r2")
        veto = await veto_service.exercise_veto(decision_id=decision.id, vetoed_by="r2", reason="Issue")
        with pytest.raises(ValueError, match="no RACI role"):
            await veto_service.override_veto(veto_id=veto.id, overridden_by="unknown")

    async def test_override_same_level_fails(
        self,
        decision_service: DecisionService,
        veto_service: VetoService,
        role_service: RoleService,
    ) -> None:
        await role_service.assign_role(user_id="r3", domain_id="d3", role=RACIRole.RESPONSIBLE, assigned_by="admin")
        await role_service.assign_role(user_id="r4", domain_id="d3", role=RACIRole.RESPONSIBLE, assigned_by="admin")
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="d3",
            created_by="r3",
        )
        await decision_service.submit_for_approval(decision.id, "r3")
        veto = await veto_service.exercise_veto(decision_id=decision.id, vetoed_by="r3", reason="Issue")
        # Same level (RESPONSIBLE) cannot override RESPONSIBLE
        with pytest.raises(ValueError, match="cannot override"):
            await veto_service.override_veto(veto_id=veto.id, overridden_by="r4")

    async def test_list_vetoes(
        self,
        decision_service: DecisionService,
        veto_service: VetoService,
        role_service: RoleService,
    ) -> None:
        await role_service.assign_role(user_id="r5", domain_id="d5", role=RACIRole.RESPONSIBLE, assigned_by="admin")
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="d5",
            created_by="r5",
        )
        await decision_service.submit_for_approval(decision.id, "r5")
        await veto_service.exercise_veto(decision_id=decision.id, vetoed_by="r5", reason="Issue")
        vetoes = await veto_service.list_vetoes(decision.id)
        assert len(vetoes) == 1


class TestAuditServiceEdgeCases:
    async def test_get_events_with_filter(self, audit_service: AuditService) -> None:
        events = await audit_service.get_events(event_type=AuditEventType.DECISION_CREATED)
        assert isinstance(events, list)


class TestModelsEdgeCases:
    def test_veto_is_expired_no_expiry(self) -> None:
        from odg_core.models import VetoRecord

        v = VetoRecord(
            decision_id=uuid.uuid4(),
            vetoed_by="owner-1",
            vetoed_by_role=RACIRole.ACCOUNTABLE,
            reason="Test",
            status=VetoStatus.ACTIVE,
            expires_at=None,
        )
        assert v.is_expired is False
