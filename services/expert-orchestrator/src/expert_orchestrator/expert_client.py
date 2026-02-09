"""Expert Client - Invokes AI experts via HTTP."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ExpertClient:
    """Client for invoking AI experts."""

    def __init__(self, timeout_seconds: int = 300):
        """Initialize expert client.

        Args:
            timeout_seconds: Default timeout for expert requests
        """
        self.timeout_seconds = timeout_seconds
        self.client = httpx.AsyncClient(timeout=timeout_seconds)

    async def invoke_expert(self, expert_id: str, endpoint: str, action: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Invoke an expert to perform an action.

        Args:
            expert_id: Expert identifier
            endpoint: Expert HTTP endpoint
            action: Action to perform
            inputs: Input data for the action

        Returns:
            Expert response

        Example:
            >>> client = ExpertClient()
            >>> result = await client.invoke_expert(
            ...     expert_id="schema_expert_1",
            ...     endpoint="http://schema-expert:8000",
            ...     action="analyze_schema",
            ...     inputs={"file_path": "s3://data/customers.parquet"}
            ... )
        """
        logger.info(f"Invoking expert {expert_id}: {action}")

        try:
            response = await self.client.post(
                f"{endpoint}/api/v1/invoke", json={"expert_id": expert_id, "action": action, "inputs": inputs}
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"✓ Expert {expert_id} responded successfully")
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"Expert {expert_id} returned HTTP error: {e.response.status_code}")
            raise RuntimeError(f"Expert {expert_id} failed: {e.response.status_code} - {e.response.text}") from e

        except httpx.RequestError as e:
            logger.error(f"Failed to connect to expert {expert_id}: {e}")
            raise RuntimeError(f"Failed to connect to expert {expert_id}: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error invoking expert {expert_id}: {e}")
            raise

    async def health_check(self, endpoint: str) -> bool:
        """Check if an expert endpoint is healthy.

        Args:
            endpoint: Expert HTTP endpoint

        Returns:
            True if healthy

        Example:
            >>> is_healthy = await client.health_check("http://schema-expert:8000")
        """
        try:
            response = await self.client.get(f"{endpoint}/health", timeout=5.0)
            return response.status_code == 200

        except Exception as e:
            logger.warning(f"Health check failed for {endpoint}: {e}")
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
