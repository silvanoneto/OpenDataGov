"""Tests for audit chain integrity through the service layer."""

from governance_engine.domain.audit_service import AuditService
from governance_engine.domain.decision_service import DecisionService
from odg_core.enums import AuditEventType, DecisionType


class TestAuditChainIntegrity:
    async def test_decision_creates_audit_event(
        self,
        decision_service: DecisionService,
        audit_service: AuditService,
    ) -> None:
        decision = await decision_service.create_decision(
            decision_type=DecisionType.DATA_PROMOTION,
            title="Test",
            description="",
            domain_id="finance",
            created_by="user-1",
        )
        events = await audit_service.get_events_for_entity(str(decision.id))
        assert len(events) == 1
        assert events[0].event_type == AuditEventType.DECISION_CREATED

    async def test_chain_integrity_after_multiple_events(
        self,
        decision_service: DecisionService,
        audit_service: AuditService,
    ) -> None:
        # Create multiple decisions to generate audit events
        for i in range(5):
            await decision_service.create_decision(
                decision_type=DecisionType.SCHEMA_CHANGE,
                title=f"Decision {i}",
                description="",
                domain_id="finance",
                created_by="user-1",
            )

        is_valid = await audit_service.verify_integrity()
        assert is_valid is True

    async def test_full_lifecycle_audit_trail(
        self,
        decision_service: DecisionService,
        audit_service: AuditService,
    ) -> None:
        # Create
        decision = await decision_service.create_decision(
            decision_type=DecisionType.POLICY_CHANGE,
            title="New policy",
            description="",
            domain_id="hr",
            created_by="admin",
        )

        # Submit
        await decision_service.submit_for_approval(decision.id, "admin")

        events = await audit_service.get_events_for_entity(str(decision.id))
        assert len(events) == 2
        assert events[0].event_type == AuditEventType.DECISION_CREATED
        assert events[1].event_type == AuditEventType.DECISION_SUBMITTED

        # Verify chain
        assert await audit_service.verify_integrity() is True
