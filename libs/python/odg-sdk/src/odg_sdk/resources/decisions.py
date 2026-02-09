"""Decision resource API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from uuid import UUID

    from odg_sdk.client import OpenDataGovClient


class Decision(BaseModel):
    """Governance decision model."""

    id: UUID
    decision_type: str
    title: str
    description: str
    status: str
    domain_id: str
    created_by: str
    created_at: str
    updated_at: str | None = None
    metadata: dict[str, Any] | None = None


class DecisionApprover(BaseModel):
    """Decision approver model."""

    user_id: str
    role: str
    vote: str | None = None
    voted_at: str | None = None
    comment: str | None = None


class DecisionResource:
    """Decision resource manager.

    Provides methods to interact with governance decisions.
    """

    def __init__(self, client: OpenDataGovClient):
        self.client = client

    async def create(
        self,
        *,
        decision_type: str,
        title: str,
        description: str,
        domain_id: str,
        created_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> Decision:
        """Create a new governance decision.

        Args:
            decision_type: Type of decision (e.g., "data_promotion")
            title: Decision title
            description: Detailed description
            domain_id: Domain identifier
            created_by: User who created the decision
            metadata: Optional metadata dictionary

        Returns:
            Created decision

        Example:
            >>> decision = await client.decisions.create(
            ...     decision_type="data_promotion",
            ...     title="Promote sales to Gold",
            ...     description="Quality gates passed",
            ...     domain_id="finance",
            ...     created_by="user-1"
            ... )
        """
        data = await self.client.request(
            "POST",
            "/api/v1/decisions",
            json={
                "decision_type": decision_type,
                "title": title,
                "description": description,
                "domain_id": domain_id,
                "created_by": created_by,
                "metadata": metadata or {},
            },
        )
        return Decision.model_validate(data)

    async def get(self, decision_id: str | UUID) -> Decision:
        """Get a decision by ID.

        Args:
            decision_id: Decision UUID

        Returns:
            Decision object

        Example:
            >>> decision = await client.decisions.get("123e4567-e89b-12d3-a456-426614174000")
        """
        data = await self.client.request("GET", f"/api/v1/decisions/{decision_id}")
        return Decision.model_validate(data)

    async def list(
        self,
        *,
        domain_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Decision]:
        """List decisions with optional filters.

        Args:
            domain_id: Filter by domain
            status: Filter by status (pending, approved, rejected)
            limit: Maximum number of results
            offset: Result offset for pagination

        Returns:
            List of decisions

        Example:
            >>> decisions = await client.decisions.list(domain_id="finance", status="pending")
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if domain_id:
            params["domain_id"] = domain_id
        if status:
            params["status"] = status

        data = await self.client.request("GET", "/api/v1/decisions", params=params)
        return [Decision.model_validate(item) for item in data]

    async def submit(self, decision_id: str | UUID, actor_id: str) -> Decision:
        """Submit a decision for approval.

        Args:
            decision_id: Decision UUID
            actor_id: User submitting the decision

        Returns:
            Updated decision

        Example:
            >>> decision = await client.decisions.submit(decision_id, "user-1")
        """
        data = await self.client.request(
            "POST",
            f"/api/v1/decisions/{decision_id}/submit",
            json={"actor_id": actor_id},
        )
        return Decision.model_validate(data)

    async def approve(
        self,
        decision_id: str | UUID,
        voter_id: str,
        vote: str = "approve",
        comment: str | None = None,
    ) -> Decision:
        """Cast an approval vote on a decision.

        Args:
            decision_id: Decision UUID
            voter_id: User casting the vote
            vote: Vote type ("approve" or "reject")
            comment: Optional comment

        Returns:
            Updated decision

        Example:
            >>> decision = await client.decisions.approve(
            ...     decision_id,
            ...     voter_id="user-1",
            ...     vote="approve",
            ...     comment="Looks good"
            ... )
        """
        data = await self.client.request(
            "POST",
            f"/api/v1/decisions/{decision_id}/approve",
            json={
                "voter_id": voter_id,
                "vote": vote,
                "comment": comment,
            },
        )
        return Decision.model_validate(data)

    async def veto(self, decision_id: str | UUID, vetoer_id: str, reason: str) -> Decision:
        """Exercise veto power on a decision.

        Args:
            decision_id: Decision UUID
            vetoer_id: User exercising veto
            reason: Reason for veto

        Returns:
            Updated decision

        Example:
            >>> decision = await client.decisions.veto(
            ...     decision_id,
            ...     vetoer_id="admin",
            ...     reason="Security concerns"
            ... )
        """
        data = await self.client.request(
            "POST",
            f"/api/v1/decisions/{decision_id}/veto",
            json={
                "vetoer_id": vetoer_id,
                "reason": reason,
            },
        )
        return Decision.model_validate(data)
