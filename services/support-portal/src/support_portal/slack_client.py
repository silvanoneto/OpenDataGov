"""Slack client for internal team notifications.

Sends alerts for critical tickets, SLA breaches, and team updates.
"""

from __future__ import annotations

import logging
import os

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Slack notification client for support team."""

    def __init__(self, token: str | None = None):
        """Initialize Slack client.

        Args:
            token: Slack bot token (defaults to SLACK_BOT_TOKEN env var)
        """
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        if not self.token:
            logger.warning("Slack bot token not configured")
            self.client = None
        else:
            self.client = AsyncWebClient(token=self.token)

        # Slack channel IDs
        self.channels = {
            "support_alerts": os.getenv("SLACK_SUPPORT_ALERTS_CHANNEL", "C1234567890"),
            "sla_breaches": os.getenv("SLACK_SLA_BREACHES_CHANNEL", "C0987654321"),
            "general_support": os.getenv("SLACK_GENERAL_SUPPORT_CHANNEL", "C1122334455"),
        }

    async def notify_critical_ticket(
        self,
        ticket_id: str,
        ticket_subject: str,
        customer_name: str,
        priority: str,
        assigned_to: str | None,
    ) -> bool:
        """Notify team about new critical (P1) ticket.

        Args:
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            customer_name: Customer name
            priority: Ticket priority
            assigned_to: Assigned agent (if any)

        Returns:
            True if sent successfully
        """
        if not self.client:
            logger.error("Slack client not configured")
            return False

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "🚨 NEW CRITICAL TICKET", "emoji": True}},
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Ticket:*\n<https://support.opendatagov.io/tickets/{ticket_id}|#{ticket_id[:8]}>",
                    },
                    {"type": "mrkdwn", "text": f"*Priority:*\n{priority}"},
                    {"type": "mrkdwn", "text": f"*Customer:*\n{customer_name}"},
                    {"type": "mrkdwn", "text": f"*Assigned:*\n{assigned_to or 'Unassigned'}"},
                ],
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Subject:*\n{ticket_subject}"}},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Ticket", "emoji": True},
                        "url": f"https://support.opendatagov.io/tickets/{ticket_id}",
                        "style": "danger",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Assign to Me", "emoji": True},
                        "value": ticket_id,
                        "action_id": "assign_ticket",
                    },
                ],
            },
        ]

        try:
            await self.client.chat_postMessage(
                channel=self.channels["support_alerts"],
                blocks=blocks,
                text=f"🚨 NEW CRITICAL TICKET: {ticket_subject}",  # Fallback text
            )

            logger.info(f"✅ Posted critical ticket alert to Slack: {ticket_id}")
            return True

        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return False

    async def notify_sla_breach(
        self,
        ticket_id: str,
        ticket_subject: str,
        priority: str,
        sla_elapsed_pct: float,
        assigned_to: str | None,
        escalation_level: str,
    ) -> bool:
        """Notify team about SLA breach or approaching breach.

        Args:
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            priority: Ticket priority
            sla_elapsed_pct: SLA percentage elapsed
            assigned_to: Assigned agent
            escalation_level: Escalation level

        Returns:
            True if sent successfully
        """
        if not self.client:
            logger.error("Slack client not configured")
            return False

        # Color coding based on severity
        if sla_elapsed_pct >= 100:
            emoji = "🔴"
            status = "BREACHED"
        elif sla_elapsed_pct >= 80:
            emoji = "⚠️"
            status = "WARNING"
        else:
            emoji = "🟢"
            status = "OK"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} SLA {status}: {sla_elapsed_pct:.0f}% ELAPSED",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Ticket:*\n<https://support.opendatagov.io/tickets/{ticket_id}|#{ticket_id[:8]}>",
                    },
                    {"type": "mrkdwn", "text": f"*Priority:*\n{priority}"},
                    {"type": "mrkdwn", "text": f"*Assigned:*\n{assigned_to or 'Unassigned'}"},
                    {"type": "mrkdwn", "text": f"*Escalation:*\n{escalation_level.replace('_', ' ').title()}"},
                ],
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Subject:*\n{ticket_subject}"}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"⏰ SLA: *{sla_elapsed_pct:.0f}%* elapsed"}]},
        ]

        # Add action buttons for breached SLAs
        if sla_elapsed_pct >= 80:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Ticket", "emoji": True},
                            "url": f"https://support.opendatagov.io/tickets/{ticket_id}",
                            "style": "danger",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Escalate", "emoji": True},
                            "value": ticket_id,
                            "action_id": "escalate_ticket",
                        },
                    ],
                }
            )

        try:
            await self.client.chat_postMessage(
                channel=self.channels["sla_breaches"],
                blocks=blocks,
                text=f"{emoji} SLA {status}: {ticket_subject}",
            )

            logger.info(f"✅ Posted SLA alert to Slack: {ticket_id}")
            return True

        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return False

    async def notify_ticket_resolved(
        self,
        ticket_id: str,
        ticket_subject: str,
        customer_name: str,
        assigned_to: str,
        resolution_time_hours: float,
        sla_met: bool,
    ) -> bool:
        """Notify team about resolved ticket.

        Args:
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            customer_name: Customer name
            assigned_to: Agent who resolved
            resolution_time_hours: Time to resolution in hours
            sla_met: Whether SLA was met

        Returns:
            True if sent successfully
        """
        if not self.client:
            logger.error("Slack client not configured")
            return False

        emoji = "✅" if sla_met else "⚠️"
        sla_status = "Within SLA" if sla_met else "SLA Breached"

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *Ticket Resolved*: <https://support.opendatagov.io/tickets/{ticket_id}|#{ticket_id[:8]}>",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Customer:*\n{customer_name}"},
                    {"type": "mrkdwn", "text": f"*Resolved By:*\n{assigned_to}"},
                    {"type": "mrkdwn", "text": f"*Resolution Time:*\n{resolution_time_hours:.1f}h"},
                    {"type": "mrkdwn", "text": f"*SLA:*\n{sla_status}"},
                ],
            },
        ]

        try:
            await self.client.chat_postMessage(
                channel=self.channels["general_support"],
                blocks=blocks,
                text=f"{emoji} Ticket Resolved: {ticket_subject}",
            )

            logger.info(f"✅ Posted resolution notification to Slack: {ticket_id}")
            return True

        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return False

    async def notify_team_metrics(
        self,
        period: str,
        total_tickets: int,
        resolved_tickets: int,
        sla_compliance_rate: float,
        avg_csat_score: float,
    ) -> bool:
        """Send daily/weekly team metrics summary.

        Args:
            period: Period (e.g., "Daily", "Weekly")
            total_tickets: Total tickets in period
            resolved_tickets: Resolved tickets
            sla_compliance_rate: SLA compliance percentage
            avg_csat_score: Average CSAT rating

        Returns:
            True if sent successfully
        """
        if not self.client:
            logger.error("Slack client not configured")
            return False

        # Emoji indicators
        sla_emoji = "✅" if sla_compliance_rate >= 95 else "⚠️" if sla_compliance_rate >= 90 else "🔴"
        csat_emoji = "😄" if avg_csat_score >= 4.5 else "🙂" if avg_csat_score >= 4.0 else "😐"

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"📊 {period} Support Metrics", "emoji": True}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total Tickets:*\n{total_tickets}"},
                    {"type": "mrkdwn", "text": f"*Resolved:*\n{resolved_tickets}"},
                    {"type": "mrkdwn", "text": f"*SLA Compliance:*\n{sla_emoji} {sla_compliance_rate:.1f}%"},
                    {"type": "mrkdwn", "text": f"*Avg CSAT:*\n{csat_emoji} {avg_csat_score:.1f}/5"},
                ],
            },
            {"type": "context", "elements": [{"type": "mrkdwn", "text": "🎯 Target: 95% SLA compliance, 4.5+ CSAT"}]},
        ]

        try:
            await self.client.chat_postMessage(
                channel=self.channels["general_support"],
                blocks=blocks,
                text=f"📊 {period} Support Metrics",
            )

            logger.info("✅ Posted team metrics to Slack")
            return True

        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return False

    async def send_custom_alert(
        self,
        channel: str,
        title: str,
        message: str,
        color: str = "#4F46E5",
        url: str | None = None,
    ) -> bool:
        """Send custom alert message.

        Args:
            channel: Channel ID or name
            title: Alert title
            message: Alert message
            color: Color for alert (hex code)
            url: Optional URL for action button

        Returns:
            True if sent successfully
        """
        if not self.client:
            logger.error("Slack client not configured")
            return False

        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}*\n{message}"}}]

        if url:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Details", "emoji": True},
                            "url": url,
                        }
                    ],
                }
            )

        try:
            await self.client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=title,
            )

            logger.info("✅ Posted custom alert to Slack")
            return True

        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return False
