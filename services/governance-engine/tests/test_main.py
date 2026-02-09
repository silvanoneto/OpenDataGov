"""Tests for main FastAPI application."""

from __future__ import annotations

import pytest
from fastapi import status
from governance_engine.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    """Test the main health endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_endpoint() -> None:
    """Test the main ready endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ready"}
