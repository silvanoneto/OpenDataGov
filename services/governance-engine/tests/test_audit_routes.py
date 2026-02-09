"""Tests for audit API routes."""

from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuditRoutes:
    """Tests for /api/v1/audit endpoints."""

    async def test_list_events(self, client: AsyncClient) -> None:
        """Test listing audit events."""
        response = await client.get("/api/v1/audit", headers={"Authorization": "Bearer da-001"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    async def test_get_events_for_entity(self, client: AsyncClient) -> None:
        """Test getting events for a specific entity."""
        response = await client.get("/api/v1/audit/entity/some-id", headers={"Authorization": "Bearer da-001"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    async def test_verify_audit_integrity(self, client: AsyncClient) -> None:
        """Test verifying audit trail integrity."""
        response = await client.get("/api/v1/audit/verify", headers={"Authorization": "Bearer da-001"})
        assert response.status_code == status.HTTP_200_OK
        assert "is_valid" in response.json()
