"""OpenDataGov client."""

from __future__ import annotations

from typing import Any

import httpx

from odg_sdk.exceptions import (
    ODGAPIError,
    ODGAuthenticationError,
    ODGConnectionError,
    ODGNotFoundError,
    ODGValidationError,
)
from odg_sdk.resources.access import AccessRequestResource
from odg_sdk.resources.datasets import DatasetResource
from odg_sdk.resources.decisions import DecisionResource
from odg_sdk.resources.quality import QualityResource


class OpenDataGovClient:
    """OpenDataGov API client.

    Provides access to all OpenDataGov REST and GraphQL APIs.

    Example:
        >>> client = OpenDataGovClient("http://localhost:8000")
        >>> decision = client.decisions.create(
        ...     decision_type="data_promotion",
        ...     title="Promote sales to Gold",
        ...     domain_id="finance"
        ... )
        >>> print(decision.id)

    Args:
        base_url: OpenDataGov API base URL
        api_key: Optional API key for authentication
        timeout: Request timeout in seconds (default: 30)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        # Configure HTTP client
        headers = {
            "User-Agent": "odg-sdk/0.1.0",
            "Accept": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
        )

        # Initialize resource managers
        self.decisions = DecisionResource(self)
        self.datasets = DatasetResource(self)
        self.quality = QualityResource(self)
        self.access = AccessRequestResource(self)

    async def __aenter__(self) -> OpenDataGovClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the OpenDataGov API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., "/api/v1/decisions")
            params: Query parameters
            json: JSON request body

        Returns:
            Response JSON data

        Raises:
            ODGAuthenticationError: If authentication fails (401)
            ODGNotFoundError: If resource not found (404)
            ODGValidationError: If request validation fails (422)
            ODGAPIError: For other API errors
            ODGConnectionError: If connection fails
        """
        try:
            response = await self._client.request(
                method=method,
                url=path,
                params=params,
                json=json,
            )

            # Check for HTTP errors
            if response.status_code >= 400:
                self._handle_error_response(response)

            return response.json()

        except httpx.HTTPError as e:
            raise ODGConnectionError(f"Failed to connect to OpenDataGov API: {e}") from e

    def _handle_error_response(self, response: httpx.Response) -> None:
        """Handle error responses from the API."""
        try:
            error_data = response.json()
            message = error_data.get("detail", "API request failed")
        except Exception:
            message = f"API request failed with status {response.status_code}"
            error_data = None

        if response.status_code == 401:
            raise ODGAuthenticationError(message, response.status_code, error_data)
        elif response.status_code == 404:
            raise ODGNotFoundError(message, response.status_code, error_data)
        elif response.status_code == 422:
            raise ODGValidationError(message, response.status_code, error_data)
        else:
            raise ODGAPIError(message, response.status_code, error_data)

    async def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            GraphQL response data

        Example:
            >>> result = await client.graphql('''
            ...     query GetDecision($id: UUID!) {
            ...         decision(id: $id) { id title status }
            ...     }
            ... ''', {"id": "123e4567-e89b-12d3-a456-426614174000"})
        """
        response = await self.request(
            "POST",
            "/api/v1/graphql",
            json={"query": query, "variables": variables or {}},
        )

        # Check for GraphQL errors
        if "errors" in response:
            errors = response["errors"]
            error_messages = [e.get("message", "Unknown error") for e in errors]
            raise ODGAPIError(f"GraphQL errors: {', '.join(error_messages)}", response_data=response)

        return response.get("data", {})
