"""Approval workflow service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odg_core.enums import AuditEventType, DecisionStatus, RACIRole, VoteValue
from odg_core.models import ApprovalRecord

if TYPE_CHECKING:
    import uuid

    from governance_engine.domain.audit_service import AuditService
    from governance_engine.domain.decision_service import DecisionService
    from governance_engine.repository.protocols import ApprovalRepository, RACIRepository

# Roles required to approve (RESPONSIBLE + ACCOUNTABLE must approve)
REQUIRED_APPROVAL_ROLES = frozenset({RACIRole.RESPONSIBLE, RACIRole.ACCOUNTABLE})


class ApprovalService:
    """Manages the approval workflow for governance decisions.

    All RESPONSIBLE and ACCOUNTABLE roles must approve for a decision
    to be finalized as APPROVED.
    """

    def __init__(
        self,
        repo: ApprovalRepository,
        raci_repo: RACIRepository,
        decision_service: DecisionService,
        audit: AuditService,
    ) -> None:
        self._repo = repo
        self._raci_repo = raci_repo
        self._decision_service = decision_service
        self._audit = audit

    async def cast_vote(
        self,
        *,
        decision_id: uuid.UUID,
        voter_id: str,
        vote: VoteValue,
        comment: str = "",
    ) -> ApprovalRecord:
        """Cast a vote on a decision."""
        decision = await self._decision_service.get_decision(decision_id)
        if decision is None:
            raise ValueError(f"Decision {decision_id} not found")
        if decision.status != DecisionStatus.AWAITING_APPROVAL:
            raise ValueError(f"Decision is not awaiting approval, status: {decision.status}")

        # Determine voter's role for this domain
        assignment = await self._raci_repo.get_assignment(voter_id, decision.domain_id)
        if assignment is None:
            raise ValueError(f"User {voter_id} has no RACI role in domain {decision.domain_id}")

        # Check for duplicate vote
        existing = await self._repo.get_vote(decision_id, voter_id)
        if existing is not None:
            raise ValueError(f"User {voter_id} has already voted on decision {decision_id}")

        record = ApprovalRecord(
            decision_id=decision_id,
            voter_id=voter_id,
            voter_role=assignment.role,
            vote=vote,
            comment=comment,
        )
        saved = await self._repo.create(record)

        await self._audit.record_event(
            event_type=AuditEventType.APPROVAL_CAST,
            entity_type="decision",
            entity_id=str(decision_id),
            actor_id=voter_id,
            description=f"Vote {vote} cast by {voter_id} (role: {assignment.role})",
            details={"vote": vote, "role": assignment.role, "comment": comment},
        )

        # Check if all required roles have approved
        if vote == VoteValue.REJECT:
            await self._decision_service.finalize(decision_id, DecisionStatus.REJECTED, actor_id=voter_id)
        elif vote == VoteValue.APPROVE:
            await self._check_and_finalize(decision_id, decision.domain_id)

        return saved

    async def _check_and_finalize(self, decision_id: uuid.UUID, domain_id: str) -> None:
        """Check if all required roles have approved and finalize if so."""
        # Get all required RACI assignments for this domain
        required_assignments = await self._raci_repo.list_by_domain(domain_id)
        required_voters = {a.user_id for a in required_assignments if a.role in REQUIRED_APPROVAL_ROLES}

        if not required_voters:
            return

        # Get all approval votes for this decision
        approvals = await self._repo.list_by_decision(decision_id)
        approved_voters = {a.voter_id for a in approvals if a.vote == VoteValue.APPROVE}

        # All required voters must have approved
        if required_voters.issubset(approved_voters):
            await self._decision_service.finalize(decision_id, DecisionStatus.APPROVED, actor_id="system")

    async def list_votes(self, decision_id: uuid.UUID) -> list[ApprovalRecord]:
        return await self._repo.list_by_decision(decision_id)
