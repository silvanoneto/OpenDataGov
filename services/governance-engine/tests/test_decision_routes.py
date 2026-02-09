"""Tests for decision API routes."""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from governance_engine.domain.role_service import RoleService
from httpx import AsyncClient
from odg_core.enums import DecisionStatus, DecisionType, RACIRole, VoteValue


@pytest.fixture
async def setup_raci(role_service: RoleService) -> None:
    """Setup RACI roles for testing."""
    await role_service.assign_role(
        user_id="da-001",
        domain_id="finance",
        role=RACIRole.ACCOUNTABLE,
        assigned_by="admin",
    )
    await role_service.assign_role(
        user_id="da-001",
        domain_id="hr",
        role=RACIRole.RESPONSIBLE,
        assigned_by="admin",
    )
    await role_service.assign_role(
        user_id="steward-1",
        domain_id="finance",
        role=RACIRole.RESPONSIBLE,
        assigned_by="admin",
    )


@pytest.mark.asyncio
class TestDecisionRoutes:
    """Tests for /api/v1/decisions endpoints."""

    async def test_create_decision(self, client: AsyncClient, setup_raci: None) -> None:
        """Test creating a decision via API."""
        payload = {
            "decision_type": DecisionType.DATA_PROMOTION,
            "title": "API Decision",
            "description": "Created via API",
            "domain_id": "finance",
            "created_by": "da-001",
        }
        response = await client.post("/api/v1/decisions", json=payload, headers={"Authorization": "Bearer da-001"})
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "API Decision"
        assert data["status"] == DecisionStatus.PENDING

    async def test_list_decisions(self, client: AsyncClient, setup_raci: None) -> None:
        """Test listing decisions."""
        # Create one first
        await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.SCHEMA_CHANGE,
                "title": "List Test",
                "domain_id": "hr",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )

        response = await client.get(
            "/api/v1/decisions", params={"domain_id": "hr"}, headers={"Authorization": "Bearer da-001"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        assert data[0]["domain_id"] == "hr"

    async def test_get_decision(self, client: AsyncClient, setup_raci: None) -> None:
        """Test getting a single decision."""
        resp = await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.ACCESS_GRANT,
                "title": "Get Test",
                "domain_id": "finance",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )
        decision_id = resp.json()["id"]

        response = await client.get(f"/api/v1/decisions/{decision_id}", headers={"Authorization": "Bearer da-001"})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == decision_id

    async def test_get_nonexistent_decision(self, client: AsyncClient) -> None:
        """Test getting non-existent decision returns 404."""
        bad_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/decisions/{bad_id}", headers={"Authorization": "Bearer da-001"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_submit_decision(self, client: AsyncClient, setup_raci: None) -> None:
        """Test submitting a decision for approval."""
        resp = await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.SCHEMA_CHANGE,
                "title": "Submit Test",
                "domain_id": "finance",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )
        decision_id = resp.json()["id"]

        response = await client.post(
            f"/api/v1/decisions/{decision_id}/submit",
            json={"actor_id": "da-001"},
            headers={"Authorization": "Bearer da-001"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == DecisionStatus.AWAITING_APPROVAL

    async def test_submit_invalid_transition(self, client: AsyncClient, setup_raci: None) -> None:
        """Test submitting a decision in invalid state."""
        resp = await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.SCHEMA_CHANGE,
                "title": "Submit Fail Test",
                "domain_id": "finance",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )
        decision_id = resp.json()["id"]

        # Submit once
        await client.post(
            f"/api/v1/decisions/{decision_id}/submit",
            json={"actor_id": "da-001"},
            headers={"Authorization": "Bearer da-001"},
        )

        # Submit again should fail
        response = await client.post(
            f"/api/v1/decisions/{decision_id}/submit",
            json={"actor_id": "da-001"},
            headers={"Authorization": "Bearer da-001"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_approve_decision(self, client: AsyncClient, setup_raci: None) -> None:
        """Test approving a decision."""
        resp = await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.SCHEMA_CHANGE,
                "title": "Approve Test",
                "domain_id": "finance",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )
        decision_id = resp.json()["id"]
        await client.post(
            f"/api/v1/decisions/{decision_id}/submit",
            json={"actor_id": "da-001"},
            headers={"Authorization": "Bearer da-001"},
        )

        response = await client.post(
            f"/api/v1/decisions/{decision_id}/approve",
            json={
                "voter_id": "da-001",
                "vote": VoteValue.APPROVE,
                "comment": "Good change",
            },
            headers={"Authorization": "Bearer da-001"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["vote"] == VoteValue.APPROVE

    async def test_list_approvals(self, client: AsyncClient, setup_raci: None) -> None:
        """Test listing approvals for a decision."""
        resp = await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.SCHEMA_CHANGE,
                "title": "Approvals List Test",
                "domain_id": "finance",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )
        decision_id = resp.json()["id"]
        await client.post(
            f"/api/v1/decisions/{decision_id}/submit",
            json={"actor_id": "da-001"},
            headers={"Authorization": "Bearer da-001"},
        )
        await client.post(
            f"/api/v1/decisions/{decision_id}/approve",
            json={"voter_id": "da-001", "vote": VoteValue.APPROVE},
            headers={"Authorization": "Bearer da-001"},
        )

        response = await client.get(
            f"/api/v1/decisions/{decision_id}/approvals", headers={"Authorization": "Bearer da-001"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_veto_and_override_routes(self, client: AsyncClient, setup_raci: None) -> None:
        """Test veto and override cycle via API."""
        # 1. Create and submit
        resp = await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.DATA_PROMOTION,
                "title": "Veto Test",
                "domain_id": "finance",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )
        decision_id = resp.json()["id"]
        await client.post(
            f"/api/v1/decisions/{decision_id}/submit",
            json={"actor_id": "da-001"},
            headers={"Authorization": "Bearer da-001"},
        )

        # 2. Exercise veto (by a lower authority)
        veto_resp = await client.post(
            f"/api/v1/decisions/{decision_id}/veto",
            json={"vetoed_by": "steward-1", "reason": "Wait for check"},
            headers={"Authorization": "Bearer da-001"},
        )
        assert veto_resp.status_code == status.HTTP_201_CREATED
        veto_id = veto_resp.json()["id"]

        # 3. List vetoes
        list_resp = await client.get(
            f"/api/v1/decisions/{decision_id}/vetoes", headers={"Authorization": "Bearer da-001"}
        )
        assert list_resp.status_code == status.HTTP_200_OK
        assert len(list_resp.json()) == 1

        # 4. Override veto
        override_resp = await client.post(
            f"/api/v1/decisions/{decision_id}/vetoes/{veto_id}/override",
            json={"overridden_by": "da-001"},
            headers={"Authorization": "Bearer da-001"},
        )
        assert override_resp.status_code == status.HTTP_200_OK
        assert override_resp.json()["overridden_by"] == "da-001"

    async def test_approve_invalid_decision_error(self, client: AsyncClient, setup_raci: None) -> None:
        """Test that invalid approval (e.g. on pending decision) returns 400."""
        resp = await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.SCHEMA_CHANGE,
                "title": "Error Test",
                "domain_id": "finance",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )
        decision_id = resp.json()["id"]

        # Approve without submitting (still PENDING)
        response = await client.post(
            f"/api/v1/decisions/{decision_id}/approve",
            json={"voter_id": "da-001", "vote": VoteValue.APPROVE},
            headers={"Authorization": "Bearer da-001"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_veto_invalid_decision_error(self, client: AsyncClient, setup_raci: None) -> None:
        """Test that invalid veto returns 400."""
        resp = await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.SCHEMA_CHANGE,
                "title": "Veto Error Test",
                "domain_id": "finance",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )
        decision_id = resp.json()["id"]

        # Veto without submitting
        response = await client.post(
            f"/api/v1/decisions/{decision_id}/veto",
            json={"vetoed_by": "da-001", "reason": "test"},
            headers={"Authorization": "Bearer da-001"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_override_invalid_veto_error(self, client: AsyncClient, setup_raci: None) -> None:
        """Test that invalid override returns 400."""
        # 1. Create and submit
        resp = await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.DATA_PROMOTION,
                "title": "Override Error Test",
                "domain_id": "finance",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )
        decision_id = resp.json()["id"]
        await client.post(
            f"/api/v1/decisions/{decision_id}/submit",
            json={"actor_id": "da-001"},
            headers={"Authorization": "Bearer da-001"},
        )

        # 2. Exercise veto
        veto_resp = await client.post(
            f"/api/v1/decisions/{decision_id}/veto",
            json={"vetoed_by": "steward-1", "reason": "Wait for check"},
            headers={"Authorization": "Bearer da-001"},
        )
        veto_id = veto_resp.json()["id"]

        # 3. Use a user with lower level for override
        # Note: steward-1 has level 2, same as level 2 (RESPONSIBLE).
        # Wait, level 2 <= level 2 is true, so it should fail.
        response = await client.post(
            f"/api/v1/decisions/{decision_id}/vetoes/{veto_id}/override",
            json={"overridden_by": "steward-1"},
            headers={"Authorization": "Bearer da-001"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
