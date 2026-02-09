"""Webhook manager for external integrations.

Allows external systems to receive real-time events from the support portal.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

import httpx

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Webhook subscription model (add to models.py later)
class WebhookSubscription:
    """Webhook subscription configuration."""

    def __init__(
        self,
        webhook_id: str,
        url: str,
        events: list[str],
        secret: str | None = None,
        active: bool = True,
    ):
        self.webhook_id = webhook_id
        self.url = url
        self.events = events  # e.g., ["ticket.created", "ticket.updated", "comment.created"]
        self.secret = secret  # For HMAC signature verification
        self.active = active


class WebhookManager:
    """Manages webhook subscriptions and event delivery."""

    # Supported event types
    SUPPORTED_EVENTS: ClassVar[list[str]] = [
        "ticket.created",
        "ticket.updated",
        "ticket.solved",
        "ticket.closed",
        "comment.created",
        "csat.submitted",
        "sla.breached",
    ]

    def __init__(self, db: AsyncSession):
        """Initialize webhook manager.

        Args:
            db: Database session
        """
        self.db = db
        self.client = httpx.AsyncClient(timeout=10.0)

    async def send_event(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Send event to all subscribed webhooks.

        Args:
            event_type: Event type (e.g., "ticket.created")
            payload: Event payload data
        """
        if event_type not in self.SUPPORTED_EVENTS:
            logger.warning(f"Unknown event type: {event_type}")
            return

        # Get active subscriptions for this event type
        subscriptions = await self._get_subscriptions(event_type)

        if not subscriptions:
            logger.debug(f"No webhooks subscribed to {event_type}")
            return

        # Send to each webhook
        for subscription in subscriptions:
            await self._deliver_webhook(
                subscription=subscription,
                event_type=event_type,
                payload=payload,
            )

    async def _get_subscriptions(self, event_type: str) -> list[WebhookSubscription]:
        """Get active webhook subscriptions for event type.

        Args:
            event_type: Event type to filter by

        Returns:
            List of subscriptions
        """
        # TODO: Query from database
        # For now, return empty list (would normally query webhook_subscriptions table)
        return []

    async def _deliver_webhook(
        self,
        subscription: WebhookSubscription,
        event_type: str,
        payload: dict[str, Any],
    ) -> bool:
        """Deliver webhook event to subscriber.

        Args:
            subscription: Webhook subscription
            event_type: Event type
            payload: Event payload

        Returns:
            True if delivered successfully
        """
        # Build webhook payload
        webhook_payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
        }

        # Generate HMAC signature if secret is configured
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type,
            "X-Webhook-Timestamp": webhook_payload["timestamp"],
        }

        if subscription.secret:
            signature = self._generate_signature(
                payload=webhook_payload,
                secret=subscription.secret,
            )
            headers["X-Webhook-Signature"] = signature

        try:
            response = await self.client.post(
                subscription.url,
                json=webhook_payload,
                headers=headers,
            )

            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"✅ Delivered webhook {event_type} to {subscription.url} (status: {response.status_code})")
                return True
            else:
                logger.warning(f"⚠️  Webhook delivery failed: {subscription.url} (status: {response.status_code})")
                return False

        except httpx.TimeoutException:
            logger.error(f"Webhook timeout: {subscription.url}")
            return False
        except Exception as e:
            logger.error(f"Webhook delivery error: {subscription.url} - {e}")
            return False

    def _generate_signature(self, payload: dict[str, Any], secret: str) -> str:
        """Generate HMAC-SHA256 signature for webhook payload.

        Args:
            payload: Webhook payload
            secret: Secret key

        Returns:
            Hex-encoded signature
        """
        import json

        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return f"sha256={signature}"

    @staticmethod
    def verify_signature(
        payload: dict[str, Any],
        signature: str,
        secret: str,
    ) -> bool:
        """Verify webhook signature.

        Args:
            payload: Received payload
            signature: Received signature (format: "sha256=...")
            secret: Secret key

        Returns:
            True if signature is valid
        """
        import json

        if not signature.startswith("sha256="):
            return False

        expected_signature = signature[7:]  # Remove "sha256=" prefix

        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        computed_signature = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed_signature, expected_signature)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Event helpers for common webhook triggers
class WebhookEvents:
    """Helper methods to send common webhook events."""

    def __init__(self, webhook_manager: WebhookManager):
        self.manager = webhook_manager

    async def ticket_created(self, ticket: dict[str, Any]) -> None:
        """Send ticket.created event.

        Args:
            ticket: Ticket data
        """
        await self.manager.send_event(
            event_type="ticket.created",
            payload={
                "ticket_id": ticket["ticket_id"],
                "subject": ticket["subject"],
                "priority": ticket["priority"],
                "status": ticket["status"],
                "customer": {
                    "name": ticket.get("customer_name"),
                    "email": ticket.get("customer_email"),
                },
                "created_at": ticket["created_at"],
                "url": f"https://support.opendatagov.io/tickets/{ticket['ticket_id']}",
            },
        )

    async def ticket_updated(
        self,
        ticket: dict[str, Any],
        changes: dict[str, Any],
    ) -> None:
        """Send ticket.updated event.

        Args:
            ticket: Updated ticket data
            changes: Changed fields
        """
        await self.manager.send_event(
            event_type="ticket.updated",
            payload={
                "ticket_id": ticket["ticket_id"],
                "changes": changes,
                "current_state": {
                    "status": ticket["status"],
                    "priority": ticket["priority"],
                    "assigned_to": ticket.get("assigned_to"),
                },
                "updated_at": ticket["updated_at"],
            },
        )

    async def ticket_solved(self, ticket: dict[str, Any]) -> None:
        """Send ticket.solved event.

        Args:
            ticket: Solved ticket data
        """
        await self.manager.send_event(
            event_type="ticket.solved",
            payload={
                "ticket_id": ticket["ticket_id"],
                "subject": ticket["subject"],
                "resolved_by": ticket.get("assigned_to"),
                "resolution_time_seconds": ticket.get("resolution_time_seconds"),
                "sla_met": not ticket.get("sla_breached", False),
                "resolved_at": ticket["resolved_at"],
            },
        )

    async def comment_created(
        self,
        ticket_id: str,
        comment: dict[str, Any],
    ) -> None:
        """Send comment.created event.

        Args:
            ticket_id: Ticket ID
            comment: Comment data
        """
        await self.manager.send_event(
            event_type="comment.created",
            payload={
                "ticket_id": ticket_id,
                "comment_id": comment["comment_id"],
                "author": comment.get("author"),
                "is_internal": comment.get("is_internal", False),
                "created_at": comment["created_at"],
            },
        )

    async def csat_submitted(
        self,
        ticket_id: str,
        rating: int,
        feedback: str | None,
    ) -> None:
        """Send csat.submitted event.

        Args:
            ticket_id: Ticket ID
            rating: CSAT rating (1-5)
            feedback: Optional feedback text
        """
        await self.manager.send_event(
            event_type="csat.submitted",
            payload={
                "ticket_id": ticket_id,
                "rating": rating,
                "feedback": feedback,
                "submitted_at": datetime.utcnow().isoformat(),
            },
        )

    async def sla_breached(
        self,
        ticket_id: str,
        sla_type: str,
        elapsed_pct: float,
    ) -> None:
        """Send sla.breached event.

        Args:
            ticket_id: Ticket ID
            sla_type: SLA type (response, resolution)
            elapsed_pct: SLA percentage elapsed
        """
        await self.manager.send_event(
            event_type="sla.breached",
            payload={
                "ticket_id": ticket_id,
                "sla_type": sla_type,
                "elapsed_pct": elapsed_pct,
                "breached_at": datetime.utcnow().isoformat(),
            },
        )
