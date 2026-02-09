"""Tests for dashboard API routes."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from odg_core.enums import DecisionType, RACIRole


@pytest.fixture
async def setup_dashboard_data(client: AsyncClient, role_service: Any) -> None:
    """Setup data for dashboard testing."""
    # Ensure user has role
    await role_service.assign_role(
        user_id="da-001",
        domain_id="finance",
        role=RACIRole.ACCOUNTABLE,
        assigned_by="admin",
    )

    # Create some decisions to have history
    for i in range(3):
        await client.post(
            "/api/v1/decisions",
            json={
                "decision_type": DecisionType.DATA_PROMOTION,
                "title": f"Dashboard Decision {i}",
                "domain_id": "finance",
                "created_by": "da-001",
            },
            headers={"Authorization": "Bearer da-001"},
        )


@pytest.mark.asyncio
class TestDashboardRoutes:
    """Tests for /api/v1/dashboard endpoints."""

    async def test_get_decision_history(self, client: AsyncClient, setup_dashboard_data: None) -> None:
        """Test getting decision history."""
        response = await client.get("/api/v1/dashboard/decision-history", headers={"Authorization": "Bearer da-001"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 3
        assert "timeline" in data[0]
        assert data[0]["timeline"][0]["event_type"] == "created"

    async def test_get_raci_patterns(self, client: AsyncClient, setup_dashboard_data: None) -> None:
        """Test getting RACI pattern analytics."""
        response = await client.get(
            "/api/v1/dashboard/raci-patterns",
            params={"domain_id": "finance"},
            headers={"Authorization": "Bearer da-001"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_decisions"] >= 3
        assert "finance" in data["decisions_by_domain"]

    async def test_get_privacy_budget(self, client: AsyncClient) -> None:
        """Test getting privacy budget status."""
        response = await client.get("/api/v1/dashboard/privacy-budget", headers={"Authorization": "Bearer da-001"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_epsilon_consumed" in data
        assert len(data["alerts"]) > 0

    async def test_get_audit_stats(self, client: AsyncClient, setup_dashboard_data: None) -> None:
        """Test getting audit statistics."""
        response = await client.get("/api/v1/dashboard/audit-stats", headers={"Authorization": "Bearer da-001"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_events"] > 0
        assert data["chain_integrity"] is True

    async def test_dashboard_health(self, client: AsyncClient) -> None:
        """Test dashboard health check."""
        response = await client.get("/api/v1/dashboard/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "ok"
