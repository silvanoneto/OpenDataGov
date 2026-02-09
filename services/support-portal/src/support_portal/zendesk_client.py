"""Zendesk API Integration.

Synchronizes tickets bidirectionally between OpenDataGov and Zendesk.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import select
from support_portal.models import (
    CommentRow,
    TicketPriority,
    TicketRow,
    TicketStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ZendeskClient:
    """Client for Zendesk Support API v2."""

    def __init__(
        self,
        subdomain: str,
        email: str,
        api_token: str,
    ):
        """Initialize Zendesk client.

        Args:
            subdomain: Zendesk subdomain (e.g., 'opendatagov')
            email: Admin email for authentication
            api_token: API token from Zendesk admin settings
        """
        self.subdomain = subdomain
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        self.auth = (f"{email}/token", api_token)
        self.client = httpx.AsyncClient(timeout=30.0)

    async def create_ticket(
        self,
        subject: str,
        description: str,
        requester_email: str,
        requester_name: str,
        priority: TicketPriority,
        tags: list[str] | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> str:
        """Create ticket in Zendesk.

        Args:
            subject: Ticket subject
            description: Ticket description
            requester_email: Customer email
            requester_name: Customer name
            priority: Ticket priority
            tags: Optional tags
            custom_fields: Optional custom fields (org_id, dataset_id, etc.)

        Returns:
            Zendesk ticket ID
        """
        # Map our priority to Zendesk priority
        zendesk_priority = self._map_priority_to_zendesk(priority)

        payload = {
            "ticket": {
                "subject": subject,
                "comment": {"body": description},
                "requester": {
                    "email": requester_email,
                    "name": requester_name,
                },
                "priority": zendesk_priority,
                "tags": tags or [],
                "custom_fields": self._format_custom_fields(custom_fields or {}),
            }
        }

        response = await self.client.post(
            f"{self.base_url}/tickets.json",
            json=payload,
            auth=self.auth,
        )

        response.raise_for_status()
        data = response.json()

        zendesk_ticket_id = str(data["ticket"]["id"])

        logger.info(f"Created Zendesk ticket: {zendesk_ticket_id}")

        return zendesk_ticket_id

    async def update_ticket(
        self,
        zendesk_ticket_id: str,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        comment: str | None = None,
        internal_note: bool = False,
    ) -> None:
        """Update Zendesk ticket.

        Args:
            zendesk_ticket_id: Zendesk ticket ID
            status: New status (optional)
            priority: New priority (optional)
            comment: Comment to add (optional)
            internal_note: If True, comment is internal staff note
        """
        payload: dict[str, Any] = {"ticket": {}}

        if status:
            payload["ticket"]["status"] = self._map_status_to_zendesk(status)

        if priority:
            payload["ticket"]["priority"] = self._map_priority_to_zendesk(priority)

        if comment:
            payload["ticket"]["comment"] = {
                "body": comment,
                "public": not internal_note,
            }

        if not payload["ticket"]:
            logger.warning("No fields to update in Zendesk ticket")
            return

        response = await self.client.put(
            f"{self.base_url}/tickets/{zendesk_ticket_id}.json",
            json=payload,
            auth=self.auth,
        )

        response.raise_for_status()

        logger.info(f"Updated Zendesk ticket: {zendesk_ticket_id}")

    async def get_ticket(self, zendesk_ticket_id: str) -> dict[str, Any]:
        """Get ticket details from Zendesk.

        Args:
            zendesk_ticket_id: Zendesk ticket ID

        Returns:
            Ticket data from Zendesk
        """
        response = await self.client.get(
            f"{self.base_url}/tickets/{zendesk_ticket_id}.json",
            auth=self.auth,
        )

        response.raise_for_status()
        data = response.json()

        return data["ticket"]

    async def get_ticket_comments(self, zendesk_ticket_id: str) -> list[dict[str, Any]]:
        """Get all comments for a Zendesk ticket.

        Args:
            zendesk_ticket_id: Zendesk ticket ID

        Returns:
            List of comment data
        """
        response = await self.client.get(
            f"{self.base_url}/tickets/{zendesk_ticket_id}/comments.json",
            auth=self.auth,
        )

        response.raise_for_status()
        data = response.json()

        return data["comments"]

    async def sync_ticket_to_zendesk(
        self,
        ticket: TicketRow,
        db: AsyncSession,
    ) -> str:
        """Create or update ticket in Zendesk from local ticket.

        Args:
            ticket: Local ticket row
            db: Database session

        Returns:
            Zendesk ticket ID
        """
        # Get user info
        from support_portal.models import UserRow

        user_result = await db.execute(select(UserRow).where(UserRow.user_id == ticket.user_id))
        user = user_result.scalars().first()

        if not user:
            raise ValueError(f"User {ticket.user_id} not found")

        # Get organization info
        from support_portal.models import OrganizationRow

        org_result = await db.execute(select(OrganizationRow).where(OrganizationRow.org_id == ticket.org_id))
        org = org_result.scalars().first()

        # Custom fields
        custom_fields = {
            "odg_ticket_id": ticket.ticket_id,
            "odg_org_id": ticket.org_id,
            "odg_org_name": org.name if org else "Unknown",
            "support_tier": org.support_tier if org else "community",
        }

        if ticket.zendesk_ticket_id:
            # Update existing ticket
            await self.update_ticket(
                zendesk_ticket_id=ticket.zendesk_ticket_id,
                status=TicketStatus(ticket.status),
                priority=TicketPriority(ticket.priority),
            )
            return ticket.zendesk_ticket_id
        else:
            # Create new ticket
            zendesk_id = await self.create_ticket(
                subject=ticket.subject,
                description=ticket.description,
                requester_email=user.email,
                requester_name=user.name,
                priority=TicketPriority(ticket.priority),
                tags=ticket.tags,
                custom_fields=custom_fields,
            )

            # Update local ticket with Zendesk ID
            ticket.zendesk_ticket_id = zendesk_id
            await db.commit()

            return zendesk_id

    async def sync_ticket_from_zendesk(
        self,
        zendesk_ticket_id: str,
        db: AsyncSession,
    ) -> TicketRow | None:
        """Update local ticket from Zendesk ticket.

        Args:
            zendesk_ticket_id: Zendesk ticket ID
            db: Database session

        Returns:
            Updated ticket row or None if not found
        """
        # Get Zendesk ticket
        zendesk_ticket = await self.get_ticket(zendesk_ticket_id)

        # Find local ticket
        result = await db.execute(select(TicketRow).where(TicketRow.zendesk_ticket_id == zendesk_ticket_id))
        ticket = result.scalars().first()

        if not ticket:
            logger.warning(f"No local ticket found for Zendesk ID {zendesk_ticket_id}")
            return None

        # Update local ticket
        ticket.status = self._map_status_from_zendesk(zendesk_ticket["status"])
        ticket.priority = self._map_priority_from_zendesk(zendesk_ticket["priority"])

        if zendesk_ticket.get("updated_at"):
            ticket.updated_at = datetime.fromisoformat(zendesk_ticket["updated_at"].replace("Z", "+00:00"))

        await db.commit()
        await db.refresh(ticket)

        logger.info(f"Synced ticket {ticket.ticket_id} from Zendesk")

        return ticket

    async def sync_comments_from_zendesk(
        self,
        zendesk_ticket_id: str,
        ticket_id: str,
        db: AsyncSession,
    ) -> int:
        """Sync comments from Zendesk to local database.

        Args:
            zendesk_ticket_id: Zendesk ticket ID
            ticket_id: Local ticket ID
            db: Database session

        Returns:
            Number of new comments synced
        """
        zendesk_comments = await self.get_ticket_comments(zendesk_ticket_id)

        # Get existing comments
        result = await db.execute(select(CommentRow).where(CommentRow.ticket_id == ticket_id))
        existing_comments = {c.zendesk_comment_id for c in result.scalars().all()}

        new_count = 0

        for zd_comment in zendesk_comments:
            zd_comment_id = str(zd_comment["id"])

            # Skip if already synced
            if zd_comment_id in existing_comments:
                continue

            # Create local comment
            comment = CommentRow(
                ticket_id=ticket_id,
                user_id=None,  # Zendesk comment - no local user
                body=zd_comment["body"],
                is_internal=not zd_comment.get("public", True),
                zendesk_comment_id=zd_comment_id,
                created_at=datetime.fromisoformat(zd_comment["created_at"].replace("Z", "+00:00")),
            )

            db.add(comment)
            new_count += 1

        await db.commit()

        logger.info(f"Synced {new_count} new comments from Zendesk")

        return new_count

    async def create_webhook(
        self,
        target_url: str,
        events: list[str] | None = None,
    ) -> str:
        """Create Zendesk webhook for ticket updates.

        Args:
            target_url: URL to send webhook events (e.g., https://api.opendatagov.io/webhooks/zendesk)
            events: List of event types to subscribe to

        Returns:
            Webhook ID
        """
        if events is None:
            events = [
                "ticket.created",
                "ticket.updated",
                "comment.created",
            ]

        payload = {
            "webhook": {
                "name": "OpenDataGov Sync",
                "endpoint": target_url,
                "http_method": "POST",
                "request_format": "json",
                "subscriptions": events,
                "status": "active",
            }
        }

        response = await self.client.post(
            f"{self.base_url}/webhooks.json",
            json=payload,
            auth=self.auth,
        )

        response.raise_for_status()
        data = response.json()

        webhook_id = str(data["webhook"]["id"])

        logger.info(f"Created Zendesk webhook: {webhook_id}")

        return webhook_id

    # Helper methods for status/priority mapping

    def _map_priority_to_zendesk(self, priority: TicketPriority) -> str:
        """Map our priority to Zendesk priority."""
        mapping = {
            TicketPriority.P1_CRITICAL: "urgent",
            TicketPriority.P2_HIGH: "high",
            TicketPriority.P3_NORMAL: "normal",
            TicketPriority.P4_LOW: "low",
            TicketPriority.URGENT: "urgent",
            TicketPriority.HIGH: "high",
            TicketPriority.NORMAL: "normal",
        }
        return mapping.get(priority, "normal")

    def _map_priority_from_zendesk(self, zendesk_priority: str) -> str:
        """Map Zendesk priority to our priority."""
        # Default to P3_NORMAL for enterprise tier
        mapping = {
            "urgent": TicketPriority.P1_CRITICAL.value,
            "high": TicketPriority.P2_HIGH.value,
            "normal": TicketPriority.P3_NORMAL.value,
            "low": TicketPriority.P4_LOW.value,
        }
        return mapping.get(zendesk_priority, TicketPriority.P3_NORMAL.value)

    def _map_status_to_zendesk(self, status: TicketStatus) -> str:
        """Map our status to Zendesk status."""
        mapping = {
            TicketStatus.NEW: "new",
            TicketStatus.OPEN: "open",
            TicketStatus.PENDING: "pending",
            TicketStatus.SOLVED: "solved",
            TicketStatus.CLOSED: "closed",
            TicketStatus.CANCELLED: "closed",
        }
        return mapping.get(status, "open")

    def _map_status_from_zendesk(self, zendesk_status: str) -> str:
        """Map Zendesk status to our status."""
        mapping = {
            "new": TicketStatus.NEW.value,
            "open": TicketStatus.OPEN.value,
            "pending": TicketStatus.PENDING.value,
            "solved": TicketStatus.SOLVED.value,
            "closed": TicketStatus.CLOSED.value,
        }
        return mapping.get(zendesk_status, TicketStatus.OPEN.value)

    def _format_custom_fields(self, fields: dict[str, Any]) -> list[dict[str, Any]]:
        """Format custom fields for Zendesk API.

        Zendesk expects: [{"id": 123, "value": "foo"}]
        """
        # Map field names to Zendesk custom field IDs
        # These IDs come from Zendesk admin > Ticket Fields
        field_id_mapping = {
            "odg_ticket_id": 360001234567,  # Custom field ID in Zendesk
            "odg_org_id": 360001234568,
            "odg_org_name": 360001234569,
            "support_tier": 360001234570,
        }

        return [
            {"id": field_id_mapping.get(name), "value": value}
            for name, value in fields.items()
            if name in field_id_mapping
        ]

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
