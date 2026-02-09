"""Tests for self-service API routes."""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSelfServiceRoutes:
    """Tests for /api/v1/self-service endpoints."""

    async def test_create_access_request(self, client: AsyncClient) -> None:
        """Test creating an access request."""
        payload = {
            "dataset_id": "gold.customers",
            "requester_id": "ds-001",
            "purpose": "Marketing analytics campaign",
            "duration_days": 90,
            "justification": "Need to analyze customer churn",
        }
        response = await client.post(
            "/api/v1/self-service/access-requests", json=payload, headers={"Authorization": "Bearer ds-001"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["dataset_id"] == "gold.customers"
        assert data["status"] == "pending"

    async def test_get_access_request_not_implemented(self, client: AsyncClient) -> None:
        """Test getting access request status (currently not implemented)."""
        response = await client.get(
            f"/api/v1/self-service/access-requests/{uuid.uuid4()}", headers={"Authorization": "Bearer ds-001"}
        )
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED

    async def test_search_datasets(self, client: AsyncClient) -> None:
        """Test searching datasets with various filters."""
        response = await client.get(
            "/api/v1/self-service/datasets/search",
            params={
                "query": "customer",
                "domain": "crm",
                "layer": "gold",
                "classification": "sensitive",
            },
            headers={"Authorization": "Bearer ds-001"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        assert "gold" in data[0]["layer"]
        assert "sensitive" in data[0]["classification"]

    async def test_dataset_preview(self, client: AsyncClient) -> None:
        """Test dataset preview."""
        payload = {
            "dataset_id": "gold.customers",
            "limit": 10,
            "apply_privacy": True,
        }
        response = await client.post(
            "/api/v1/self-service/datasets/preview", json=payload, headers={"Authorization": "Bearer ds-001"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["privacy_applied"] is True
        assert len(data["sample_data"]) > 0

    async def test_create_pipeline(self, client: AsyncClient) -> None:
        """Test creating a data pipeline."""
        payload = {
            "name": "Customer Aggregation",
            "description": "Weekly customer aggregation",
            "source_datasets": ["gold.customers", "gold.transactions"],
            "target_dataset": "platinum.customer_metrics",
            "schedule": "@weekly",
            "owner_id": "eng-001",
        }
        response = await client.post(
            "/api/v1/self-service/pipelines", json=payload, headers={"Authorization": "Bearer ds-001"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "pending_approval"

    async def test_self_service_health(self, client: AsyncClient) -> None:
        """Test self-service health check."""
        response = await client.get("/api/v1/self-service/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "ok"
