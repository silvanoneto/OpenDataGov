"""PostgreSQL repository implementations using SQLAlchemy 2.0 async."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odg_core.audit import AuditEvent
from odg_core.db.tables import (
    ApprovalRecordRow,
    AuditEventRow,
    GovernanceDecisionRow,
    RACIAssignmentRow,
    VetoRecordRow,
)
from odg_core.models import ApprovalRecord, GovernanceDecision, RACIAssignment, VetoRecord
from sqlalchemy import select

if TYPE_CHECKING:
    import uuid

    from odg_core.enums import AuditEventType, DecisionStatus
    from sqlalchemy.ext.asyncio import AsyncSession


class PgDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, decision: GovernanceDecision) -> GovernanceDecision:
        row = GovernanceDecisionRow(
            id=decision.id,
            decision_type=decision.decision_type,
            title=decision.title,
            description=decision.description,
            status=decision.status,
            domain_id=decision.domain_id,
            created_by=decision.created_by,
            created_at=decision.created_at,
            updated_at=decision.updated_at,
            metadata_json=decision.metadata,
            source_layer=decision.promotion.source_layer if decision.promotion else None,
            target_layer=decision.promotion.target_layer if decision.promotion else None,
            data_classification=decision.promotion.data_classification if decision.promotion else None,
        )
        self._session.add(row)
        await self._session.flush()
        return GovernanceDecision.model_validate(row)

    async def get_by_id(self, decision_id: uuid.UUID) -> GovernanceDecision | None:
        row = await self._session.get(GovernanceDecisionRow, decision_id)
        if row is None:
            return None
        return GovernanceDecision.model_validate(row)

    async def update(self, decision: GovernanceDecision) -> GovernanceDecision:
        row = await self._session.get(GovernanceDecisionRow, decision.id)
        if row is None:
            raise ValueError(f"Decision {decision.id} not found")
        row.status = decision.status
        row.updated_at = decision.updated_at
        row.metadata_json = decision.metadata  # type: ignore[assignment]
        await self._session.flush()
        return GovernanceDecision.model_validate(row)

    async def list_decisions(
        self,
        *,
        domain_id: str | None = None,
        status: DecisionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[GovernanceDecision]:
        stmt = select(GovernanceDecisionRow)
        if domain_id:
            stmt = stmt.where(GovernanceDecisionRow.domain_id == domain_id)
        if status:
            stmt = stmt.where(GovernanceDecisionRow.status == status)
        stmt = stmt.order_by(GovernanceDecisionRow.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [GovernanceDecision.model_validate(r) for r in result.scalars()]


class PgApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, record: ApprovalRecord) -> ApprovalRecord:
        row = ApprovalRecordRow(
            id=record.id,
            decision_id=record.decision_id,
            voter_id=record.voter_id,
            voter_role=record.voter_role,
            vote=record.vote,
            comment=record.comment,
            voted_at=record.voted_at,
        )
        self._session.add(row)
        await self._session.flush()
        return ApprovalRecord.model_validate(row)

    async def get_vote(self, decision_id: uuid.UUID, voter_id: str) -> ApprovalRecord | None:
        stmt = select(ApprovalRecordRow).where(
            ApprovalRecordRow.decision_id == decision_id,
            ApprovalRecordRow.voter_id == voter_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ApprovalRecord.model_validate(row)

    async def list_by_decision(self, decision_id: uuid.UUID) -> list[ApprovalRecord]:
        stmt = (
            select(ApprovalRecordRow)
            .where(ApprovalRecordRow.decision_id == decision_id)
            .order_by(ApprovalRecordRow.voted_at)
        )
        result = await self._session.execute(stmt)
        return [ApprovalRecord.model_validate(r) for r in result.scalars()]


class PgVetoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, veto: VetoRecord) -> VetoRecord:
        row = VetoRecordRow(
            id=veto.id,
            decision_id=veto.decision_id,
            vetoed_by=veto.vetoed_by,
            vetoed_by_role=veto.vetoed_by_role,
            reason=veto.reason,
            status=veto.status,
            vetoed_at=veto.vetoed_at,
            expires_at=veto.expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return VetoRecord.model_validate(row)

    async def get_by_id(self, veto_id: uuid.UUID) -> VetoRecord | None:
        row = await self._session.get(VetoRecordRow, veto_id)
        if row is None:
            return None
        return VetoRecord.model_validate(row)

    async def update(self, veto: VetoRecord) -> VetoRecord:
        row = await self._session.get(VetoRecordRow, veto.id)
        if row is None:
            raise ValueError(f"Veto {veto.id} not found")
        row.status = veto.status
        row.overridden_by = veto.overridden_by
        row.overridden_at = veto.overridden_at
        await self._session.flush()
        return VetoRecord.model_validate(row)

    async def list_by_decision(self, decision_id: uuid.UUID) -> list[VetoRecord]:
        stmt = select(VetoRecordRow).where(VetoRecordRow.decision_id == decision_id).order_by(VetoRecordRow.vetoed_at)
        result = await self._session.execute(stmt)
        return [VetoRecord.model_validate(r) for r in result.scalars()]


class PgAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, event: AuditEvent) -> AuditEvent:
        row = AuditEventRow(
            id=event.id,
            event_type=event.event_type,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            actor_id=event.actor_id,
            description=event.description,
            details=event.details,
            occurred_at=event.occurred_at,
            previous_hash=event.previous_hash,
            event_hash=event.event_hash,
        )
        self._session.add(row)
        await self._session.flush()
        return AuditEvent.model_validate(row)

    async def get_last_hash(self) -> str | None:
        stmt = select(AuditEventRow.event_hash).order_by(AuditEventRow.occurred_at.desc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_chain(self, *, limit: int = 1000) -> list[AuditEvent]:
        stmt = select(AuditEventRow).order_by(AuditEventRow.occurred_at).limit(limit)
        result = await self._session.execute(stmt)
        return [AuditEvent.model_validate(r) for r in result.scalars()]

    async def list_by_entity(self, entity_id: str, *, limit: int = 50) -> list[AuditEvent]:
        stmt = (
            select(AuditEventRow)
            .where(AuditEventRow.entity_id == entity_id)
            .order_by(AuditEventRow.occurred_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [AuditEvent.model_validate(r) for r in result.scalars()]

    async def list_events(
        self,
        *,
        event_type: AuditEventType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        stmt = select(AuditEventRow)
        if event_type:
            stmt = stmt.where(AuditEventRow.event_type == event_type)
        stmt = stmt.order_by(AuditEventRow.occurred_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [AuditEvent.model_validate(r) for r in result.scalars()]


class PgRACIRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, assignment: RACIAssignment) -> RACIAssignment:
        row = RACIAssignmentRow(
            id=assignment.id,
            user_id=assignment.user_id,
            domain_id=assignment.domain_id,
            role=assignment.role,
            assigned_at=assignment.assigned_at,
            assigned_by=assignment.assigned_by,
        )
        self._session.add(row)
        await self._session.flush()
        return RACIAssignment.model_validate(row)

    async def get_by_id(self, assignment_id: uuid.UUID) -> RACIAssignment | None:
        row = await self._session.get(RACIAssignmentRow, assignment_id)
        if row is None:
            return None
        return RACIAssignment.model_validate(row)

    async def get_assignment(self, user_id: str, domain_id: str) -> RACIAssignment | None:
        stmt = select(RACIAssignmentRow).where(
            RACIAssignmentRow.user_id == user_id,
            RACIAssignmentRow.domain_id == domain_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return RACIAssignment.model_validate(row)

    async def delete(self, assignment_id: uuid.UUID) -> None:
        row = await self._session.get(RACIAssignmentRow, assignment_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def list_by_domain(self, domain_id: str) -> list[RACIAssignment]:
        stmt = select(RACIAssignmentRow).where(RACIAssignmentRow.domain_id == domain_id)
        result = await self._session.execute(stmt)
        return [RACIAssignment.model_validate(r) for r in result.scalars()]

    async def list_by_user(self, user_id: str) -> list[RACIAssignment]:
        stmt = select(RACIAssignmentRow).where(RACIAssignmentRow.user_id == user_id)
        result = await self._session.execute(stmt)
        return [RACIAssignment.model_validate(r) for r in result.scalars()]
