"""RACI role assignment service (ADR-013)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odg_core.enums import AuditEventType, RACIRole
from odg_core.models import RACIAssignment

if TYPE_CHECKING:
    import uuid

    from governance_engine.domain.audit_service import AuditService
    from governance_engine.repository.protocols import RACIRepository


class RoleService:
    """Manages RACI role assignments per domain."""

    def __init__(self, repo: RACIRepository, audit: AuditService) -> None:
        self._repo = repo
        self._audit = audit

    async def assign_role(
        self,
        *,
        user_id: str,
        domain_id: str,
        role: RACIRole,
        assigned_by: str,
    ) -> RACIAssignment:
        """Assign a RACI role to a user for a domain."""
        existing = await self._repo.get_assignment(user_id, domain_id)
        if existing is not None:
            raise ValueError(f"User {user_id} already has role {existing.role} in domain {domain_id}")

        assignment = RACIAssignment(
            user_id=user_id,
            domain_id=domain_id,
            role=role,
            assigned_by=assigned_by,
        )
        saved = await self._repo.create(assignment)

        await self._audit.record_event(
            event_type=AuditEventType.ROLE_ASSIGNED,
            entity_type="raci_assignment",
            entity_id=str(saved.id),
            actor_id=assigned_by,
            description=f"Role {role} assigned to {user_id} in domain {domain_id}",
            details={"user_id": user_id, "domain_id": domain_id, "role": role},
        )
        return saved

    async def revoke_role(self, assignment_id: uuid.UUID, revoked_by: str) -> None:
        """Revoke a RACI role assignment."""
        assignment = await self._repo.get_by_id(assignment_id)
        if assignment is None:
            raise ValueError(f"Assignment {assignment_id} not found")

        await self._repo.delete(assignment_id)

        await self._audit.record_event(
            event_type=AuditEventType.ROLE_REVOKED,
            entity_type="raci_assignment",
            entity_id=str(assignment_id),
            actor_id=revoked_by,
            description=f"Role {assignment.role} revoked from {assignment.user_id} in {assignment.domain_id}",
        )

    async def get_assignments_for_domain(self, domain_id: str) -> list[RACIAssignment]:
        return await self._repo.list_by_domain(domain_id)

    async def get_assignments_for_user(self, user_id: str) -> list[RACIAssignment]:
        return await self._repo.list_by_user(user_id)
