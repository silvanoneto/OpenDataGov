"""PagerDuty integration for P1 critical incident escalation.

Creates PagerDuty incidents for critical support tickets and syncs status.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PagerDutyClient:
    """PagerDuty API client for incident management."""

    def __init__(self, api_token: str | None = None, integration_key: str | None = None):
        """Initialize PagerDuty client.

        Args:
            api_token: PagerDuty API token (defaults to PAGERDUTY_API_TOKEN env var)
            integration_key: Events API v2 integration key (defaults to PAGERDUTY_INTEGRATION_KEY)
        """
        self.api_token = api_token or os.getenv("PAGERDUTY_API_TOKEN")
        self.integration_key = integration_key or os.getenv("PAGERDUTY_INTEGRATION_KEY")

        if not self.api_token or not self.integration_key:
            logger.warning("PagerDuty credentials not configured")
            self.enabled = False
        else:
            self.enabled = True

        self.api_url = "https://api.pagerduty.com"
        self.events_url = "https://events.pagerduty.com/v2"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def create_incident(
        self,
        ticket_id: str,
        ticket_subject: str,
        priority: str,
        customer_name: str,
        description: str,
        urgency: str = "high",
    ) -> dict[str, Any] | None:
        """Create PagerDuty incident for critical ticket.

        Args:
            ticket_id: Support ticket ID
            ticket_subject: Ticket subject
            priority: Ticket priority
            customer_name: Customer name
            description: Incident description
            urgency: Incident urgency (high, low)

        Returns:
            Incident data or None if failed
        """
        if not self.enabled:
            logger.error("PagerDuty not configured")
            return None

        # Map priority to PagerDuty severity
        severity_map = {
            "p1_critical": "critical",
            "p2_high": "error",
            "p3_normal": "warning",
            "p4_low": "info",
        }
        severity = severity_map.get(priority.lower(), "error")

        # Create incident via Events API v2
        payload = {
            "routing_key": self.integration_key,
            "event_action": "trigger",
            "dedup_key": f"support-ticket-{ticket_id}",
            "payload": {
                "summary": f"{priority.upper()}: {ticket_subject}",
                "source": "OpenDataGov Support Portal",
                "severity": severity,
                "timestamp": datetime.utcnow().isoformat(),
                "component": "support",
                "group": "customer-support",
                "class": "support-ticket",
                "custom_details": {
                    "ticket_id": ticket_id,
                    "customer": customer_name,
                    "priority": priority,
                    "description": description[:500],  # Limit to 500 chars
                    "ticket_url": f"https://support.opendatagov.io/tickets/{ticket_id}",
                },
            },
            "links": [
                {
                    "href": f"https://support.opendatagov.io/tickets/{ticket_id}",
                    "text": "View Support Ticket",
                }
            ],
        }

        try:
            response = await self.client.post(
                f"{self.events_url}/enqueue",
                json=payload,
            )

            response.raise_for_status()
            data = response.json()

            logger.info(f"✅ Created PagerDuty incident for ticket {ticket_id}: {data.get('dedup_key')}")

            return {
                "dedup_key": data.get("dedup_key"),
                "status": data.get("status"),
                "message": data.get("message"),
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"PagerDuty API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error creating PagerDuty incident: {e}")
            return None

    async def acknowledge_incident(self, ticket_id: str) -> bool:
        """Acknowledge PagerDuty incident (when agent starts working on ticket).

        Args:
            ticket_id: Support ticket ID

        Returns:
            True if acknowledged successfully
        """
        if not self.enabled:
            return False

        dedup_key = f"support-ticket-{ticket_id}"

        payload = {
            "routing_key": self.integration_key,
            "event_action": "acknowledge",
            "dedup_key": dedup_key,
        }

        try:
            response = await self.client.post(
                f"{self.events_url}/enqueue",
                json=payload,
            )

            response.raise_for_status()

            logger.info(f"✅ Acknowledged PagerDuty incident for ticket {ticket_id}")
            return True

        except Exception as e:
            logger.error(f"Error acknowledging PagerDuty incident: {e}")
            return False

    async def resolve_incident(self, ticket_id: str) -> bool:
        """Resolve PagerDuty incident (when ticket is resolved).

        Args:
            ticket_id: Support ticket ID

        Returns:
            True if resolved successfully
        """
        if not self.enabled:
            return False

        dedup_key = f"support-ticket-{ticket_id}"

        payload = {
            "routing_key": self.integration_key,
            "event_action": "resolve",
            "dedup_key": dedup_key,
        }

        try:
            response = await self.client.post(
                f"{self.events_url}/enqueue",
                json=payload,
            )

            response.raise_for_status()

            logger.info(f"✅ Resolved PagerDuty incident for ticket {ticket_id}")
            return True

        except Exception as e:
            logger.error(f"Error resolving PagerDuty incident: {e}")
            return False

    async def add_incident_note(self, ticket_id: str, note: str) -> bool:
        """Add note to PagerDuty incident.

        Args:
            ticket_id: Support ticket ID
            note: Note to add

        Returns:
            True if added successfully
        """
        if not self.enabled:
            return False

        # Note: This requires REST API v2 (not Events API)
        # First, get incident ID by dedup_key
        dedup_key = f"support-ticket-{ticket_id}"

        # Query incidents
        headers = {
            "Authorization": f"Token token={self.api_token}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json",
        }

        try:
            # Find incident by dedup_key
            response = await self.client.get(
                f"{self.api_url}/incidents",
                headers=headers,
                params={
                    "incident_key": dedup_key,
                    "limit": 1,
                },
            )

            response.raise_for_status()
            data = response.json()

            if not data.get("incidents"):
                logger.warning(f"No PagerDuty incident found for ticket {ticket_id}")
                return False

            incident_id = data["incidents"][0]["id"]

            # Add note
            note_payload = {
                "note": {
                    "content": note,
                }
            }

            note_response = await self.client.post(
                f"{self.api_url}/incidents/{incident_id}/notes",
                headers=headers,
                json=note_payload,
            )

            note_response.raise_for_status()

            logger.info(f"✅ Added note to PagerDuty incident for ticket {ticket_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding PagerDuty note: {e}")
            return False

    async def get_on_call_user(self, escalation_policy_id: str | None = None) -> dict[str, Any] | None:
        """Get current on-call engineer.

        Args:
            escalation_policy_id: Escalation policy ID (defaults to env var)

        Returns:
            On-call user info or None
        """
        if not self.enabled:
            return None

        policy_id = escalation_policy_id or os.getenv("PAGERDUTY_ESCALATION_POLICY_ID")

        if not policy_id:
            logger.error("Escalation policy ID not configured")
            return None

        headers = {
            "Authorization": f"Token token={self.api_token}",
            "Accept": "application/vnd.pagerduty+json;version=2",
        }

        try:
            response = await self.client.get(
                f"{self.api_url}/oncalls",
                headers=headers,
                params={
                    "escalation_policy_ids[]": policy_id,
                    "include[]": "users",
                },
            )

            response.raise_for_status()
            data = response.json()

            if not data.get("oncalls"):
                logger.warning("No on-call user found")
                return None

            oncall = data["oncalls"][0]
            user = oncall.get("user", {})

            return {
                "id": user.get("id"),
                "name": user.get("summary"),
                "email": user.get("email"),
                "escalation_level": oncall.get("escalation_level"),
            }

        except Exception as e:
            logger.error(f"Error getting on-call user: {e}")
            return None

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
