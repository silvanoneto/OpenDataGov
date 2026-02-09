"""Tests for OpenDataGovClient."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odg_sdk import ODGAPIError, ODGAuthenticationError, ODGNotFoundError, ODGValidationError, OpenDataGovClient

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


@pytest.mark.asyncio
async def test_client_initialization():
    """Test client initialization."""
    client = OpenDataGovClient("http://localhost:8000")
    assert client.base_url == "http://localhost:8000"
    assert client.timeout == 30.0
    await client.close()


@pytest.mark.asyncio
async def test_client_with_api_key():
    """Test client initialization with API key."""
    client = OpenDataGovClient("http://localhost:8000", api_key="test_key")
    assert client.api_key == "test_key"
    assert "Authorization" in client._client.headers
    await client.close()


@pytest.mark.asyncio
async def test_client_context_manager():
    """Test client as async context manager."""
    async with OpenDataGovClient("http://localhost:8000") as client:
        assert client.base_url == "http://localhost:8000"


@pytest.mark.asyncio
async def test_request_success(httpx_mock: HTTPXMock):
    """Test successful API request."""
    httpx_mock.add_response(json={"id": "123", "title": "Test"})

    async with OpenDataGovClient("http://localhost:8000") as client:
        result = await client.request("GET", "/api/v1/decisions/123")
        assert result["id"] == "123"
        assert result["title"] == "Test"


@pytest.mark.asyncio
async def test_request_with_params(httpx_mock: HTTPXMock):
    """Test API request with query parameters."""
    httpx_mock.add_response(json=[{"id": "1"}, {"id": "2"}])

    async with OpenDataGovClient("http://localhost:8000") as client:
        result = await client.request(
            "GET",
            "/api/v1/decisions",
            params={"domain_id": "finance", "status": "pending"},
        )
        assert len(result) == 2


@pytest.mark.asyncio
async def test_request_with_json_body(httpx_mock: HTTPXMock):
    """Test API request with JSON body."""
    httpx_mock.add_response(json={"id": "123", "status": "created"})

    async with OpenDataGovClient("http://localhost:8000") as client:
        result = await client.request(
            "POST",
            "/api/v1/decisions",
            json={"title": "Test", "domain_id": "finance"},
        )
        assert result["id"] == "123"
        assert result["status"] == "created"


@pytest.mark.asyncio
async def test_request_401_error(httpx_mock: HTTPXMock):
    """Test 401 authentication error."""
    httpx_mock.add_response(status_code=401, json={"detail": "Unauthorized"})

    async with OpenDataGovClient("http://localhost:8000") as client:
        with pytest.raises(ODGAuthenticationError) as exc_info:
            await client.request("GET", "/api/v1/decisions")
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_request_404_error(httpx_mock: HTTPXMock):
    """Test 404 not found error."""
    httpx_mock.add_response(status_code=404, json={"detail": "Not found"})

    async with OpenDataGovClient("http://localhost:8000") as client:
        with pytest.raises(ODGNotFoundError) as exc_info:
            await client.request("GET", "/api/v1/decisions/invalid")
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_request_422_validation_error(httpx_mock: HTTPXMock):
    """Test 422 validation error."""
    httpx_mock.add_response(status_code=422, json={"detail": "Validation failed"})

    async with OpenDataGovClient("http://localhost:8000") as client:
        with pytest.raises(ODGValidationError) as exc_info:
            await client.request("POST", "/api/v1/decisions", json={"invalid": "data"})
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_request_500_server_error(httpx_mock: HTTPXMock):
    """Test 500 server error."""
    httpx_mock.add_response(status_code=500, json={"detail": "Internal server error"})

    async with OpenDataGovClient("http://localhost:8000") as client:
        with pytest.raises(ODGAPIError) as exc_info:
            await client.request("GET", "/api/v1/decisions")
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_graphql_success(httpx_mock: HTTPXMock):
    """Test successful GraphQL query."""
    httpx_mock.add_response(json={"data": {"decision": {"id": "123", "title": "Test Decision", "status": "pending"}}})

    async with OpenDataGovClient("http://localhost:8000") as client:
        result = await client.graphql("query { decision(id: $id) { id title status } }", {"id": "123"})
        assert result["decision"]["id"] == "123"
        assert result["decision"]["title"] == "Test Decision"


@pytest.mark.asyncio
async def test_graphql_error(httpx_mock: HTTPXMock):
    """Test GraphQL query with errors."""
    httpx_mock.add_response(json={"errors": [{"message": "Field 'invalid' not found"}], "data": None})

    async with OpenDataGovClient("http://localhost:8000") as client:
        with pytest.raises(ODGAPIError) as exc_info:
            await client.graphql("query { invalid }")
        assert "GraphQL errors" in str(exc_info.value)


@pytest.mark.asyncio
async def test_error_without_json_response(httpx_mock: HTTPXMock):
    """Test error handling when response is not JSON."""
    httpx_mock.add_response(status_code=500, text="Internal Server Error")

    async with OpenDataGovClient("http://localhost:8000") as client:
        with pytest.raises(ODGAPIError) as exc_info:
            await client.request("GET", "/api/v1/decisions")
        assert "API request failed" in str(exc_info.value)
