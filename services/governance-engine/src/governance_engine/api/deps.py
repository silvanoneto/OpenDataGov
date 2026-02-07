"""FastAPI dependency injection."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from governance_engine.domain.approval_service import ApprovalService
from governance_engine.domain.audit_service import AuditService
from governance_engine.domain.decision_service import DecisionService
from governance_engine.domain.role_service import RoleService
from governance_engine.domain.veto_service import VetoService
from governance_engine.repository.postgres import (
    PgApprovalRepository,
    PgAuditRepository,
    PgDecisionRepository,
    PgRACIRepository,
    PgVetoRepository,
)


async def get_session(request: Request) -> AsyncGenerator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_audit_service(session: SessionDep) -> AuditService:
    return AuditService(repo=PgAuditRepository(session))


def get_decision_service(
    session: SessionDep,
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DecisionService:
    return DecisionService(repo=PgDecisionRepository(session), audit=audit)


def get_role_service(
    session: SessionDep,
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> RoleService:
    return RoleService(repo=PgRACIRepository(session), audit=audit)


def get_approval_service(
    session: SessionDep,
    audit: Annotated[AuditService, Depends(get_audit_service)],
    decision_service: Annotated[DecisionService, Depends(get_decision_service)],
) -> ApprovalService:
    return ApprovalService(
        repo=PgApprovalRepository(session),
        raci_repo=PgRACIRepository(session),
        decision_service=decision_service,
        audit=audit,
    )


def get_veto_service(
    session: SessionDep,
    audit: Annotated[AuditService, Depends(get_audit_service)],
    decision_service: Annotated[DecisionService, Depends(get_decision_service)],
) -> VetoService:
    return VetoService(
        repo=PgVetoRepository(session),
        raci_repo=PgRACIRepository(session),
        decision_service=decision_service,
        audit=audit,
    )


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]
DecisionServiceDep = Annotated[DecisionService, Depends(get_decision_service)]
RoleServiceDep = Annotated[RoleService, Depends(get_role_service)]
ApprovalServiceDep = Annotated[ApprovalService, Depends(get_approval_service)]
VetoServiceDep = Annotated[VetoService, Depends(get_veto_service)]
