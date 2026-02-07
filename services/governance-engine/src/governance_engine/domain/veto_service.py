"""Veto management service (ADR-014)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odg_core.enums import AuditEventType, DecisionStatus, DecisionType, RACIRole, VetoStatus
from odg_core.models import VetoRecord

if TYPE_CHECKING:
    import uuid

    from governance_engine.domain.audit_service import AuditService
    from governance_engine.domain.decision_service import DecisionService
    from governance_engine.repository.protocols import RACIRepository, VetoRepository

# Role hierarchy for veto override (higher can override lower)
ROLE_HIERARCHY: dict[RACIRole, int] = {
    RACIRole.ACCOUNTABLE: 3,
    RACIRole.RESPONSIBLE: 2,
    RACIRole.CONSULTED: 1,
    RACIRole.INFORMED: 0,
}

# Roles eligible to exercise veto
VETO_ELIGIBLE_ROLES = frozenset({RACIRole.ACCOUNTABLE, RACIRole.RESPONSIBLE})


class VetoService:
    """Manages veto actions on governance decisions.

    Time-bound: 24h for normal decisions, 1h for emergency.
    Override: a role with higher authority can override a veto.
    """

    def __init__(
        self,
        repo: VetoRepository,
        raci_repo: RACIRepository,
        decision_service: DecisionService,
        audit: AuditService,
    ) -> None:
        self._repo = repo
        self._raci_repo = raci_repo
        self._decision_service = decision_service
        self._audit = audit

    async def exercise_veto(
        self,
        *,
        decision_id: uuid.UUID,
        vetoed_by: str,
        reason: str,
    ) -> VetoRecord:
        """Exercise a veto on a decision."""
        decision = await self._decision_service.get_decision(decision_id)
        if decision is None:
            raise ValueError(f"Decision {decision_id} not found")
        if decision.status != DecisionStatus.AWAITING_APPROVAL:
            raise ValueError(f"Decision must be AWAITING_APPROVAL to veto, got {decision.status}")

        # Check eligibility
        assignment = await self._raci_repo.get_assignment(vetoed_by, decision.domain_id)
        if assignment is None:
            raise ValueError(f"User {vetoed_by} has no RACI role in domain {decision.domain_id}")
        if assignment.role not in VETO_ELIGIBLE_ROLES:
            raise ValueError(f"Role {assignment.role} is not eligible to veto")

        is_emergency = decision.decision_type == DecisionType.EMERGENCY
        veto = VetoRecord(
            decision_id=decision_id,
            vetoed_by=vetoed_by,
            vetoed_by_role=assignment.role,
            reason=reason,
        )
        veto.expires_at = veto.compute_expiry(is_emergency=is_emergency)
        saved = await self._repo.create(veto)

        # Move decision to VETOED
        await self._decision_service.finalize(decision_id, DecisionStatus.VETOED, actor_id=vetoed_by)

        await self._audit.record_event(
            event_type=AuditEventType.VETO_EXERCISED,
            entity_type="decision",
            entity_id=str(decision_id),
            actor_id=vetoed_by,
            description=f"Veto exercised by {vetoed_by}: {reason}",
            details={"reason": reason, "is_emergency": is_emergency, "expires_at": str(veto.expires_at)},
        )
        return saved

    async def override_veto(
        self,
        *,
        veto_id: uuid.UUID,
        overridden_by: str,
    ) -> VetoRecord:
        """Override an active veto with a higher-authority role."""
        veto = await self._repo.get_by_id(veto_id)
        if veto is None:
            raise ValueError(f"Veto {veto_id} not found")
        if veto.status != VetoStatus.ACTIVE:
            raise ValueError(f"Veto is not active, status: {veto.status}")

        decision = await self._decision_service.get_decision(veto.decision_id)
        if decision is None:
            raise ValueError(f"Decision {veto.decision_id} not found")

        # Check override authority
        override_assignment = await self._raci_repo.get_assignment(overridden_by, decision.domain_id)
        if override_assignment is None:
            raise ValueError(f"User {overridden_by} has no RACI role in domain {decision.domain_id}")

        override_level = ROLE_HIERARCHY.get(override_assignment.role, 0)
        veto_level = ROLE_HIERARCHY.get(veto.vetoed_by_role, 0)
        if override_level <= veto_level:
            raise ValueError(
                f"Role {override_assignment.role} (level {override_level}) cannot override "
                f"veto by {veto.vetoed_by_role} (level {veto_level})"
            )

        veto.status = VetoStatus.OVERRIDDEN
        veto.overridden_by = overridden_by
        updated = await self._repo.update(veto)

        await self._audit.record_event(
            event_type=AuditEventType.VETO_OVERRIDDEN,
            entity_type="decision",
            entity_id=str(veto.decision_id),
            actor_id=overridden_by,
            description=f"Veto overridden by {overridden_by}",
        )
        return updated

    async def list_vetoes(self, decision_id: uuid.UUID) -> list[VetoRecord]:
        return await self._repo.list_by_decision(decision_id)
