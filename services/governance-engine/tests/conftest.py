"""Shared test fixtures with in-memory mock repositories."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException, Request
from governance_engine.domain.approval_service import ApprovalService
from governance_engine.domain.audit_service import AuditService
from governance_engine.domain.decision_service import DecisionService
from governance_engine.domain.role_service import RoleService
from governance_engine.domain.veto_service import VetoService
from httpx import AsyncClient
from odg_core.audit import AuditEvent
from odg_core.auth.dependencies import get_current_user
from odg_core.auth.models import UserContext
from odg_core.enums import AuditEventType, DecisionStatus, RACIRole
from odg_core.models import ApprovalRecord, GovernanceDecision, RACIAssignment, VetoRecord

# ─── In-memory mock repositories ─────────────────────────


class MockDecisionRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, GovernanceDecision] = {}

    async def create(self, decision: GovernanceDecision) -> GovernanceDecision:
        await asyncio.sleep(0)
        self._store[decision.id] = decision
        return decision

    async def get_by_id(self, decision_id: uuid.UUID) -> GovernanceDecision | None:
        await asyncio.sleep(0)
        return self._store.get(decision_id)

    async def update(self, decision: GovernanceDecision) -> GovernanceDecision:
        return await self.create(decision)

    async def list_decisions(
        self,
        *,
        domain_id: str | None = None,
        status: DecisionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[GovernanceDecision]:
        await asyncio.sleep(0)
        result = list(self._store.values())
        if domain_id:
            result = [d for d in result if d.domain_id == domain_id]
        if status:
            result = [d for d in result if d.status == status]
        return result[offset : offset + limit]


class MockApprovalRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, ApprovalRecord] = {}

    async def create(self, record: ApprovalRecord) -> ApprovalRecord:
        await asyncio.sleep(0)
        self._store[record.id] = record
        return record

    async def get_vote(self, decision_id: uuid.UUID, voter_id: str) -> ApprovalRecord | None:
        await asyncio.sleep(0)
        for r in self._store.values():
            if r.decision_id == decision_id and r.voter_id == voter_id:
                return r
        return None

    async def list_by_decision(self, decision_id: uuid.UUID) -> list[ApprovalRecord]:
        await asyncio.sleep(0)
        return [r for r in self._store.values() if r.decision_id == decision_id]


class MockVetoRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, VetoRecord] = {}

    async def create(self, veto: VetoRecord) -> VetoRecord:
        await asyncio.sleep(0)
        self._store[veto.id] = veto
        return veto

    async def get_by_id(self, veto_id: uuid.UUID) -> VetoRecord | None:
        await asyncio.sleep(0)
        return self._store.get(veto_id)

    async def update(self, veto: VetoRecord) -> VetoRecord:
        return await self.create(veto)

    async def list_by_decision(self, decision_id: uuid.UUID) -> list[VetoRecord]:
        await asyncio.sleep(0)
        return [v for v in self._store.values() if v.decision_id == decision_id]


class MockAuditRepository:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    async def create(self, event: AuditEvent) -> AuditEvent:
        await asyncio.sleep(0)
        self._events.append(event)
        return event

    async def get_last_hash(self) -> str | None:
        await asyncio.sleep(0)
        if not self._events:
            return None
        return self._events[-1].event_hash

    async def get_chain(self, *, limit: int = 1000) -> list[AuditEvent]:
        await asyncio.sleep(0)
        return self._events[:limit]

    async def list_by_entity(self, entity_id: str, *, limit: int = 50) -> list[AuditEvent]:
        await asyncio.sleep(0)
        return [e for e in self._events if e.entity_id == entity_id][:limit]

    async def list_events(
        self,
        *,
        event_type: AuditEventType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        await asyncio.sleep(0)
        result = self._events
        if event_type:
            result = [e for e in result if e.event_type == event_type]
        return result[offset : offset + limit]


class MockRACIRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, RACIAssignment] = {}

    async def create(self, assignment: RACIAssignment) -> RACIAssignment:
        await asyncio.sleep(0)
        self._store[assignment.id] = assignment
        return assignment

    async def get_by_id(self, assignment_id: uuid.UUID) -> RACIAssignment | None:
        await asyncio.sleep(0)
        return self._store.get(assignment_id)

    async def get_assignment(self, user_id: str, domain_id: str) -> RACIAssignment | None:
        await asyncio.sleep(0)
        for a in self._store.values():
            if a.user_id == user_id and a.domain_id == domain_id:
                return a
        return None

    async def delete(self, assignment_id: uuid.UUID) -> None:
        await asyncio.sleep(0)
        self._store.pop(assignment_id, None)

    async def list_by_domain(self, domain_id: str) -> list[RACIAssignment]:
        await asyncio.sleep(0)
        return [a for a in self._store.values() if a.domain_id == domain_id]

    async def list_by_user(self, user_id: str) -> list[RACIAssignment]:
        await asyncio.sleep(0)
        return [a for a in self._store.values() if a.user_id == user_id]


# ─── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def audit_repo() -> MockAuditRepository:
    return MockAuditRepository()


@pytest.fixture
def decision_repo() -> MockDecisionRepository:
    return MockDecisionRepository()


@pytest.fixture
def approval_repo() -> MockApprovalRepository:
    return MockApprovalRepository()


@pytest.fixture
def veto_repo() -> MockVetoRepository:
    return MockVetoRepository()


@pytest.fixture
def raci_repo() -> MockRACIRepository:
    return MockRACIRepository()


@pytest.fixture
def audit_service(audit_repo: MockAuditRepository) -> AuditService:
    return AuditService(repo=audit_repo)


@pytest.fixture
def decision_service(
    decision_repo: MockDecisionRepository,
    audit_service: AuditService,
) -> DecisionService:
    return DecisionService(repo=decision_repo, audit=audit_service)


@pytest.fixture
def role_service(
    raci_repo: MockRACIRepository,
    audit_service: AuditService,
) -> RoleService:
    return RoleService(repo=raci_repo, audit=audit_service)


@pytest.fixture
def approval_service(
    approval_repo: MockApprovalRepository,
    raci_repo: MockRACIRepository,
    decision_service: DecisionService,
    audit_service: AuditService,
) -> ApprovalService:
    return ApprovalService(
        repo=approval_repo,
        raci_repo=raci_repo,
        decision_service=decision_service,
        audit=audit_service,
    )


@pytest.fixture
def veto_service(
    veto_repo: MockVetoRepository,
    raci_repo: MockRACIRepository,
    decision_service: DecisionService,
    audit_service: AuditService,
) -> VetoService:
    return VetoService(
        repo=veto_repo,
        raci_repo=raci_repo,
        decision_service=decision_service,
        audit=audit_service,
    )


@pytest.fixture
def app(
    decision_service: DecisionService,
    audit_service: AuditService,
    approval_service: ApprovalService,
    veto_service: VetoService,
    role_service: RoleService,
) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    from governance_engine.api.deps import (
        get_approval_service,
        get_audit_service,
        get_decision_service,
        get_role_service,
        get_veto_service,
    )
    from governance_engine.main import app as main_app

    # Mock session factory to avoid starlette state error
    main_app.state.session_factory = MagicMock()

    # Override dependencies
    main_app.dependency_overrides[get_decision_service] = lambda: decision_service
    main_app.dependency_overrides[get_audit_service] = lambda: audit_service
    main_app.dependency_overrides[get_approval_service] = lambda: approval_service
    main_app.dependency_overrides[get_veto_service] = lambda: veto_service
    main_app.dependency_overrides[get_role_service] = lambda: role_service

    async def _get_mock_user(request: Request) -> UserContext:
        auth = request.headers.get("Authorization")
        if not auth:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Simple mock: use the token as the user_id if it's not "Bearer ..."
        user_id = "ds-001"  # Default to what tests expect
        if auth.startswith("Bearer "):
            token = auth[7:]
            if token and token != "mock-token":
                user_id = token

        return UserContext(
            user_id=user_id,
            username=user_id,
            roles=[RACIRole.RESPONSIBLE, RACIRole.ACCOUNTABLE, RACIRole.CONSULTED],
            is_authenticated=True,
        )

    main_app.dependency_overrides[get_current_user] = _get_mock_user

    return main_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Create a test client for the FastAPI app."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
