"""Tests for AccessRequestResource."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odg_sdk import OpenDataGovClient

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


@pytest.mark.asyncio
async def test_create_access_request(httpx_mock: HTTPXMock):
    """Test creating an access request."""
    httpx_mock.add_response(
        json={
            "request_id": "456f7890-ab12-cd34-ef56-789012345678",
            "dataset_id": "gold.customers",
            "requester_id": "analyst-1",
            "purpose": "Q1 2024 revenue analysis",
            "status": "pending",
            "created_at": "2024-02-08T14:00:00Z",
            "decision_id": "123e4567-e89b-12d3-a456-426614174000",
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        request = await client.access.create(
            dataset_id="gold.customers",
            requester_id="analyst-1",
            purpose="Q1 2024 revenue analysis",
            duration_days=30,
            justification="Need for quarterly report",
        )

        assert request.dataset_id == "gold.customers"
        assert request.requester_id == "analyst-1"
        assert request.status == "pending"
        assert request.decision_id is not None


@pytest.mark.asyncio
async def test_get_access_request(httpx_mock: HTTPXMock):
    """Test getting an access request."""
    request_id = "456f7890-ab12-cd34-ef56-789012345678"

    httpx_mock.add_response(
        json={
            "request_id": request_id,
            "dataset_id": "gold.sales",
            "requester_id": "analyst-2",
            "purpose": "Financial analysis",
            "status": "approved",
            "created_at": "2024-02-08T15:00:00Z",
            "decision_id": "234f5678-e89b-12d3-a456-426614174001",
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        request = await client.access.get(request_id)

        assert str(request.request_id) == request_id
        assert request.status == "approved"
        assert request.dataset_id == "gold.sales"
