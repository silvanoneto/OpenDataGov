"""Tests for DecisionResource."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odg_sdk import OpenDataGovClient

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


@pytest.mark.asyncio
async def test_create_decision(httpx_mock: HTTPXMock):
    """Test creating a decision."""
    httpx_mock.add_response(
        json={
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "decision_type": "data_promotion",
            "title": "Test Decision",
            "description": "Test description",
            "status": "pending",
            "domain_id": "finance",
            "created_by": "user-1",
            "created_at": "2024-02-08T10:00:00Z",
            "updated_at": None,
            "metadata": {},
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        decision = await client.decisions.create(
            decision_type="data_promotion",
            title="Test Decision",
            description="Test description",
            domain_id="finance",
            created_by="user-1",
        )

        assert decision.decision_type == "data_promotion"
        assert decision.title == "Test Decision"
        assert decision.status == "pending"


@pytest.mark.asyncio
async def test_get_decision(httpx_mock: HTTPXMock):
    """Test getting a decision by ID."""
    decision_id = "123e4567-e89b-12d3-a456-426614174000"

    httpx_mock.add_response(
        json={
            "id": decision_id,
            "decision_type": "data_promotion",
            "title": "Test Decision",
            "description": "Test",
            "status": "approved",
            "domain_id": "finance",
            "created_by": "user-1",
            "created_at": "2024-02-08T10:00:00Z",
            "updated_at": "2024-02-08T11:00:00Z",
            "metadata": {"key": "value"},
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        decision = await client.decisions.get(decision_id)

        assert str(decision.id) == decision_id
        assert decision.status == "approved"
        assert decision.metadata == {"key": "value"}


@pytest.mark.asyncio
async def test_list_decisions(httpx_mock: HTTPXMock):
    """Test listing decisions."""
    httpx_mock.add_response(
        json=[
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "decision_type": "data_promotion",
                "title": "Decision 1",
                "description": "Test 1",
                "status": "pending",
                "domain_id": "finance",
                "created_by": "user-1",
                "created_at": "2024-02-08T10:00:00Z",
                "updated_at": None,
                "metadata": None,
            },
            {
                "id": "234f5678-e89b-12d3-a456-426614174001",
                "decision_type": "schema_change",
                "title": "Decision 2",
                "description": "Test 2",
                "status": "approved",
                "domain_id": "crm",
                "created_by": "user-2",
                "created_at": "2024-02-08T11:00:00Z",
                "updated_at": "2024-02-08T12:00:00Z",
                "metadata": None,
            },
        ]
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        decisions = await client.decisions.list(domain_id="finance", status="pending", limit=10)

        assert len(decisions) == 2
        assert decisions[0].title == "Decision 1"
        assert decisions[1].title == "Decision 2"


@pytest.mark.asyncio
async def test_submit_decision(httpx_mock: HTTPXMock):
    """Test submitting a decision."""
    decision_id = "123e4567-e89b-12d3-a456-426614174000"

    httpx_mock.add_response(
        json={
            "id": decision_id,
            "decision_type": "data_promotion",
            "title": "Test Decision",
            "description": "Test",
            "status": "submitted",
            "domain_id": "finance",
            "created_by": "user-1",
            "created_at": "2024-02-08T10:00:00Z",
            "updated_at": "2024-02-08T10:05:00Z",
            "metadata": None,
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        decision = await client.decisions.submit(decision_id, "user-1")

        assert decision.status == "submitted"


@pytest.mark.asyncio
async def test_approve_decision(httpx_mock: HTTPXMock):
    """Test approving a decision."""
    decision_id = "123e4567-e89b-12d3-a456-426614174000"

    httpx_mock.add_response(
        json={
            "id": decision_id,
            "decision_type": "data_promotion",
            "title": "Test Decision",
            "description": "Test",
            "status": "approved",
            "domain_id": "finance",
            "created_by": "user-1",
            "created_at": "2024-02-08T10:00:00Z",
            "updated_at": "2024-02-08T10:10:00Z",
            "metadata": None,
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        decision = await client.decisions.approve(
            decision_id=decision_id, voter_id="data-owner-1", vote="approve", comment="Looks good"
        )

        assert decision.status == "approved"


@pytest.mark.asyncio
async def test_veto_decision(httpx_mock: HTTPXMock):
    """Test vetoing a decision."""
    decision_id = "123e4567-e89b-12d3-a456-426614174000"

    httpx_mock.add_response(
        json={
            "id": decision_id,
            "decision_type": "data_promotion",
            "title": "Test Decision",
            "description": "Test",
            "status": "vetoed",
            "domain_id": "finance",
            "created_by": "user-1",
            "created_at": "2024-02-08T10:00:00Z",
            "updated_at": "2024-02-08T10:15:00Z",
            "metadata": None,
        }
    )

    async with OpenDataGovClient("http://localhost:8000") as client:
        decision = await client.decisions.veto(decision_id=decision_id, vetoer_id="admin", reason="Security concerns")

        assert decision.status == "vetoed"
