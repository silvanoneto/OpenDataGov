"""End-to-end integration test for the full governance workflow.

Exercises: create decision → assign RACI roles → submit → approve
→ verify audit trail → veto + override cycle.
"""

from __future__ import annotations

from governance_engine.domain.approval_service import ApprovalService
from governance_engine.domain.audit_service import AuditService
from governance_engine.domain.decision_service import DecisionService
from governance_engine.domain.role_service import RoleService
from governance_engine.domain.veto_service import VetoService
from odg_core.enums import (
    AuditEventType,
    DecisionStatus,
    DecisionType,
    RACIRole,
    VoteValue,
)


class TestE2EGovernanceWorkflow:
    """Full lifecycle: create → assign roles → submit → approve → audit."""

    async def test_happy_path_approval(
        self,
        decision_service: DecisionService,
        approval_service: ApprovalService,
        role_service: RoleService,
        audit_service: AuditService,
    ) -> None:
        # 1. Assign RACI roles for the "finance" domain
        await role_service.assign_role(
            user_id="steward-1",
            domain_id="finance",
            role=RACIRole.ACCOUNTABLE,
            assigned_by="admin",
        )
        await role_service.assign_role(
            user_id="engineer-1",
            domain_id="finance",
            role=RACIRole.RESPONSIBLE,
            assigned_by="admin",
        )

        # 2. Create a governance decision
        decision = await decision_service.create_decision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Promote sales dataset to Gold",
            description="Monthly sales data passes all DQ gates",
            domain_id="finance",
            created_by="engineer-1",
        )
        assert decision.status == DecisionStatus.PENDING

        # 3. Submit for approval
        decision = await decision_service.submit_for_approval(decision.id, "engineer-1")
        assert decision.status == DecisionStatus.AWAITING_APPROVAL

        # 4. Both required roles approve
        await approval_service.cast_vote(
            decision_id=decision.id,
            voter_id="engineer-1",
            vote=VoteValue.APPROVE,
            comment="DQ checks pass",
        )

        await approval_service.cast_vote(
            decision_id=decision.id,
            voter_id="steward-1",
            vote=VoteValue.APPROVE,
            comment="Approved by data steward",
        )

        # 5. Decision should be auto-finalized as APPROVED
        final = await decision_service.get_decision(decision.id)
        assert final is not None
        assert final.status == DecisionStatus.APPROVED

        # 6. Verify audit trail
        events = await audit_service.get_events_for_entity(str(decision.id))
        event_types = [e.event_type for e in events]
        assert AuditEventType.DECISION_CREATED in event_types
        assert AuditEventType.DECISION_SUBMITTED in event_types
        assert AuditEventType.APPROVAL_CAST in event_types
        assert AuditEventType.DECISION_APPROVED in event_types

        # 7. Audit chain integrity
        assert await audit_service.verify_integrity() is True

    async def test_rejection_flow(
        self,
        decision_service: DecisionService,
        approval_service: ApprovalService,
        role_service: RoleService,
        audit_service: AuditService,
    ) -> None:
        # Setup role
        await role_service.assign_role(
            user_id="reviewer-1",
            domain_id="hr",
            role=RACIRole.RESPONSIBLE,
            assigned_by="admin",
        )

        # Create and submit
        decision = await decision_service.create_decision(
            decision_type=DecisionType.SCHEMA_CHANGE,
            title="Change HR schema",
            description="Breaking change to employee table",
            domain_id="hr",
            created_by="reviewer-1",
        )
        await decision_service.submit_for_approval(decision.id, "reviewer-1")

        # Reject
        await approval_service.cast_vote(
            decision_id=decision.id,
            voter_id="reviewer-1",
            vote=VoteValue.REJECT,
            comment="Insufficient documentation",
        )

        # Decision should be REJECTED
        final = await decision_service.get_decision(decision.id)
        assert final is not None
        assert final.status == DecisionStatus.REJECTED

        # Audit trail shows rejection
        events = await audit_service.get_events_for_entity(str(decision.id))
        event_types = [e.event_type for e in events]
        assert AuditEventType.DECISION_REJECTED in event_types
        assert await audit_service.verify_integrity() is True

    async def test_veto_and_override_cycle(
        self,
        decision_service: DecisionService,
        approval_service: ApprovalService,
        veto_service: VetoService,
        role_service: RoleService,
        audit_service: AuditService,
    ) -> None:
        # Setup roles with hierarchy
        await role_service.assign_role(
            user_id="owner-1",
            domain_id="sales",
            role=RACIRole.ACCOUNTABLE,
            assigned_by="admin",
        )
        await role_service.assign_role(
            user_id="eng-1",
            domain_id="sales",
            role=RACIRole.RESPONSIBLE,
            assigned_by="admin",
        )

        # Create and submit
        decision = await decision_service.create_decision(
            decision_type=DecisionType.POLICY_CHANGE,
            title="New data retention policy",
            description="30-day retention for raw data",
            domain_id="sales",
            created_by="eng-1",
        )
        await decision_service.submit_for_approval(decision.id, "eng-1")

        # Engineer vetoes (RESPONSIBLE can veto)
        veto = await veto_service.exercise_veto(
            decision_id=decision.id,
            vetoed_by="eng-1",
            reason="Retention period too short for compliance",
        )

        # Decision should be VETOED
        vetoed = await decision_service.get_decision(decision.id)
        assert vetoed is not None
        assert vetoed.status == DecisionStatus.VETOED

        # Owner overrides (ACCOUNTABLE > RESPONSIBLE)
        overridden = await veto_service.override_veto(
            veto_id=veto.id,
            overridden_by="owner-1",
        )
        assert overridden.overridden_by == "owner-1"

        # Audit trail shows full veto lifecycle
        events = await audit_service.get_events_for_entity(str(decision.id))
        event_types = [e.event_type for e in events]
        assert AuditEventType.VETO_EXERCISED in event_types
        assert AuditEventType.VETO_OVERRIDDEN in event_types
        assert await audit_service.verify_integrity() is True

    async def test_multi_domain_isolation(
        self,
        decision_service: DecisionService,
        role_service: RoleService,
        audit_service: AuditService,
    ) -> None:
        """Decisions in different domains don't interfere."""
        # Roles in different domains
        await role_service.assign_role(
            user_id="user-a", domain_id="finance", role=RACIRole.RESPONSIBLE, assigned_by="admin"
        )
        await role_service.assign_role(
            user_id="user-b", domain_id="marketing", role=RACIRole.RESPONSIBLE, assigned_by="admin"
        )

        # Create decisions in separate domains
        d1 = await decision_service.create_decision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Finance decision",
            description="",
            domain_id="finance",
            created_by="user-a",
        )
        d2 = await decision_service.create_decision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Marketing decision",
            description="",
            domain_id="marketing",
            created_by="user-b",
        )

        # Filter by domain
        finance_only = await decision_service.list_decisions(domain_id="finance")
        assert len(finance_only) == 1
        assert finance_only[0].id == d1.id

        marketing_only = await decision_service.list_decisions(domain_id="marketing")
        assert len(marketing_only) == 1
        assert marketing_only[0].id == d2.id

        # Audit chain is still valid across domains
        assert await audit_service.verify_integrity() is True
