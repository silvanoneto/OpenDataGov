"""Access request resource API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from uuid import UUID

    from odg_sdk.client import OpenDataGovClient


class AccessRequest(BaseModel):
    """Access request model."""

    request_id: UUID
    dataset_id: str
    requester_id: str
    purpose: str
    status: str
    created_at: str
    decision_id: UUID | None = None


class AccessRequestResource:
    """Access request resource manager.

    Provides methods to request and manage dataset access.
    """

    def __init__(self, client: OpenDataGovClient):
        self.client = client

    async def create(
        self,
        *,
        dataset_id: str,
        requester_id: str,
        purpose: str,
        duration_days: int = 30,
        justification: str = "",
    ) -> AccessRequest:
        """Create an access request for a dataset.

        Args:
            dataset_id: Dataset identifier
            requester_id: User requesting access
            purpose: Purpose of access (min 10 chars)
            duration_days: Access duration in days (1-365)
            justification: Optional justification

        Returns:
            Created access request

        Example:
            >>> request = await client.access.create(
            ...     dataset_id="gold.customers",
            ...     requester_id="analyst-1",
            ...     purpose="Q1 2024 revenue analysis",
            ...     duration_days=30
            ... )
        """
        data = await self.client.request(
            "POST",
            "/api/v1/self-service/access-requests",
            json={
                "dataset_id": dataset_id,
                "requester_id": requester_id,
                "purpose": purpose,
                "duration_days": duration_days,
                "justification": justification,
            },
        )
        return AccessRequest.model_validate(data)

    async def get(self, request_id: str | UUID) -> AccessRequest:
        """Get access request by ID.

        Args:
            request_id: Access request UUID

        Returns:
            Access request

        Example:
            >>> request = await client.access.get("123e4567-e89b-12d3-a456-426614174000")
        """
        data = await self.client.request(
            "GET",
            f"/api/v1/self-service/access-requests/{request_id}",
        )
        return AccessRequest.model_validate(data)
