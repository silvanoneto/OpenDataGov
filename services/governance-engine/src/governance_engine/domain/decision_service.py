"""Decision lifecycle management service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odg_core.enums import AuditEventType, DecisionStatus, DecisionType
from odg_core.models import GovernanceDecision, PromotionMetadata

if TYPE_CHECKING:
    import uuid

    from governance_engine.domain.audit_service import AuditService
    from governance_engine.repository.protocols import DecisionRepository


class DecisionService:
    """Manages the governance decision lifecycle.

    States: PENDING → AWAITING_APPROVAL → APPROVED/REJECTED/VETOED/ESCALATED
    """

    def __init__(self, repo: DecisionRepository, audit: AuditService) -> None:
        self._repo = repo
        self._audit = audit

    async def create_decision(
        self,
        *,
        decision_type: DecisionType,
        title: str,
        description: str,
        domain_id: str,
        created_by: str,
        promotion: PromotionMetadata | None = None,
        metadata: dict[str, str | int | float | bool | None] | None = None,
    ) -> GovernanceDecision:
        """Create a new governance decision in PENDING status."""
        decision = GovernanceDecision(
            decision_type=decision_type,
            title=title,
            description=description,
            domain_id=domain_id,
            created_by=created_by,
            promotion=promotion,
            metadata=metadata or {},
        )

        saved = await self._repo.create(decision)

        await self._audit.record_event(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id=str(saved.id),
            actor_id=created_by,
            description=f"Decision created: {title}",
        )
        return saved

    async def submit_for_approval(self, decision_id: uuid.UUID, actor_id: str) -> GovernanceDecision:
        """Move decision from PENDING to AWAITING_APPROVAL."""
        decision = await self._repo.get_by_id(decision_id)
        if decision is None:
            raise ValueError(f"Decision {decision_id} not found")
        if decision.status != DecisionStatus.PENDING:
            raise ValueError(f"Decision must be PENDING to submit, got {decision.status}")

        decision.status = DecisionStatus.AWAITING_APPROVAL
        updated = await self._repo.update(decision)

        await self._audit.record_event(
            event_type=AuditEventType.DECISION_SUBMITTED,
            entity_type="decision",
            entity_id=str(decision_id),
            actor_id=actor_id,
            description=f"Decision submitted for approval: {decision.title}",
        )
        return updated

    async def finalize(
        self,
        decision_id: uuid.UUID,
        status: DecisionStatus,
        actor_id: str,
    ) -> GovernanceDecision:
        """Finalize a decision to APPROVED, REJECTED, VETOED, or ESCALATED."""
        decision = await self._repo.get_by_id(decision_id)
        if decision is None:
            raise ValueError(f"Decision {decision_id} not found")
        if decision.status != DecisionStatus.AWAITING_APPROVAL:
            raise ValueError(f"Decision must be AWAITING_APPROVAL to finalize, got {decision.status}")
        if status not in (
            DecisionStatus.APPROVED,
            DecisionStatus.REJECTED,
            DecisionStatus.VETOED,
            DecisionStatus.ESCALATED,
        ):
            raise ValueError(f"Invalid final status: {status}")

        decision.status = status
        updated = await self._repo.update(decision)

        event_map = {
            DecisionStatus.APPROVED: AuditEventType.DECISION_APPROVED,
            DecisionStatus.REJECTED: AuditEventType.DECISION_REJECTED,
            DecisionStatus.ESCALATED: AuditEventType.DECISION_ESCALATED,
            DecisionStatus.VETOED: AuditEventType.VETO_EXERCISED,
        }
        await self._audit.record_event(
            event_type=event_map[status],
            entity_type="decision",
            entity_id=str(decision_id),
            actor_id=actor_id,
            description=f"Decision finalized as {status}: {decision.title}",
        )
        return updated

    async def get_decision(self, decision_id: uuid.UUID) -> GovernanceDecision | None:
        return await self._repo.get_by_id(decision_id)

    async def list_decisions(
        self,
        *,
        domain_id: str | None = None,
        status: DecisionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[GovernanceDecision]:
        return await self._repo.list_decisions(domain_id=domain_id, status=status, limit=limit, offset=offset)
