"""Tests for the complete decision lifecycle."""

import pytest
from governance_engine.domain.approval_service import ApprovalService
from governance_engine.domain.decision_service import DecisionService
from governance_engine.domain.role_service import RoleService
from governance_engine.domain.veto_service import VetoService
from odg_core.enums import DecisionStatus, DecisionType, RACIRole, VoteValue


@pytest.fixture
async def setup_domain(role_service: RoleService) -> None:
    """Create RACI assignments for the finance domain."""
    await role_service.assign_role(
        user_id="owner-1",
        domain_id="finance",
        role=RACIRole.ACCOUNTABLE,
        assigned_by="admin",
    )
    await role_service.assign_role(
        user_id="steward-1",
        domain_id="finance",
        role=RACIRole.RESPONSIBLE,
        assigned_by="admin",
    )
    await role_service.assign_role(
        user_id="consumer-1",
        domain_id="finance",
        role=RACIRole.CONSULTED,
        assigned_by="admin",
    )


class TestDecisionLifecycle:
    async def test_create_decision(self, decision_service: DecisionService) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Promote revenue data to Gold",
            description="Revenue data meets DQ gates",
            domain_id="finance",
            created_by="steward-1",
        )
        assert decision.status == DecisionStatus.PENDING
        assert decision.title == "Promote revenue data to Gold"

    async def test_submit_for_approval(self, decision_service: DecisionService) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Add column X",
            description="",
            domain_id="finance",
            created_by="steward-1",
        )
        submitted = await decision_service.submit_for_approval(decision.id, "steward-1")
        assert submitted.status == DecisionStatus.AWAITING_APPROVAL

    async def test_submit_non_pending_fails(self, decision_service: DecisionService) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="finance",
            created_by="steward-1",
        )
        await decision_service.submit_for_approval(decision.id, "steward-1")
        with pytest.raises(ValueError, match="must be PENDING"):
            await decision_service.submit_for_approval(decision.id, "steward-1")

    async def test_full_approval_flow(
        self,
        decision_service: DecisionService,
        approval_service: ApprovalService,
        setup_domain: None,
    ) -> None:
        # Create and submit
        decision = await decision_service.create_decision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Promote to Gold",
            description="",
            domain_id="finance",
            created_by="steward-1",
        )
        await decision_service.submit_for_approval(decision.id, "steward-1")

        # Both required roles approve
        await approval_service.cast_vote(
            decision_id=decision.id,
            voter_id="steward-1",
            vote=VoteValue.APPROVE,
        )
        await approval_service.cast_vote(
            decision_id=decision.id,
            voter_id="owner-1",
            vote=VoteValue.APPROVE,
        )

        # Decision should be auto-finalized
        updated = await decision_service.get_decision(decision.id)
        assert updated is not None
        assert updated.status == DecisionStatus.APPROVED

    async def test_rejection_flow(
        self,
        decision_service: DecisionService,
        approval_service: ApprovalService,
        setup_domain: None,
    ) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.ACCESS_GRANT,
            title="Grant access to PII",
            description="",
            domain_id="finance",
            created_by="steward-1",
        )
        await decision_service.submit_for_approval(decision.id, "steward-1")

        # One reject is enough
        await approval_service.cast_vote(
            decision_id=decision.id,
            voter_id="owner-1",
            vote=VoteValue.REJECT,
            comment="Not justified",
        )

        updated = await decision_service.get_decision(decision.id)
        assert updated is not None
        assert updated.status == DecisionStatus.REJECTED

    async def test_duplicate_vote_fails(
        self,
        decision_service: DecisionService,
        approval_service: ApprovalService,
        setup_domain: None,
    ) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="finance",
            created_by="steward-1",
        )
        await decision_service.submit_for_approval(decision.id, "steward-1")
        await approval_service.cast_vote(decision_id=decision.id, voter_id="steward-1", vote=VoteValue.APPROVE)
        with pytest.raises(ValueError, match="already voted"):
            await approval_service.cast_vote(decision_id=decision.id, voter_id="steward-1", vote=VoteValue.APPROVE)


class TestVetoFlow:
    async def test_veto_and_override(
        self,
        decision_service: DecisionService,
        veto_service: VetoService,
        setup_domain: None,
    ) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Promote to Gold",
            description="",
            domain_id="finance",
            created_by="steward-1",
        )
        await decision_service.submit_for_approval(decision.id, "steward-1")

        # Steward (RESPONSIBLE) exercises veto
        veto = await veto_service.exercise_veto(
            decision_id=decision.id,
            vetoed_by="steward-1",
            reason="Data quality issues detected",
        )
        assert veto.expires_at is not None

        # Decision should be VETOED
        updated = await decision_service.get_decision(decision.id)
        assert updated is not None
        assert updated.status == DecisionStatus.VETOED

        # Owner (ACCOUNTABLE, higher authority) overrides
        overridden = await veto_service.override_veto(
            veto_id=veto.id,
            overridden_by="owner-1",
        )
        assert overridden.status.value == "overridden"

    async def test_lower_role_cannot_override(
        self,
        decision_service: DecisionService,
        veto_service: VetoService,
        setup_domain: None,
    ) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Promote",
            description="",
            domain_id="finance",
            created_by="owner-1",
        )
        await decision_service.submit_for_approval(decision.id, "owner-1")

        # Owner (ACCOUNTABLE) vetoes
        veto = await veto_service.exercise_veto(
            decision_id=decision.id,
            vetoed_by="owner-1",
            reason="Not ready",
        )

        # Steward (RESPONSIBLE, lower) cannot override
        with pytest.raises(ValueError, match="cannot override"):
            await veto_service.override_veto(
                veto_id=veto.id,
                overridden_by="steward-1",
            )

    async def test_non_eligible_role_cannot_veto(
        self,
        decision_service: DecisionService,
        veto_service: VetoService,
        setup_domain: None,
    ) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Test",
            description="",
            domain_id="finance",
            created_by="steward-1",
        )
        await decision_service.submit_for_approval(decision.id, "steward-1")

        # Consumer (CONSULTED) cannot veto
        with pytest.raises(ValueError, match="not eligible"):
            await veto_service.exercise_veto(
                decision_id=decision.id,
                vetoed_by="consumer-1",
                reason="I disagree",
            )
