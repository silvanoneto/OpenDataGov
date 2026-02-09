"""Email client for CSAT surveys and notifications.

Uses SendGrid for transactional emails.
"""

from __future__ import annotations

import logging
import os

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, To

logger = logging.getLogger(__name__)


class EmailClient:
    """SendGrid email client for support portal."""

    def __init__(self, api_key: str | None = None):
        """Initialize SendGrid client.

        Args:
            api_key: SendGrid API key (defaults to SENDGRID_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("SENDGRID_API_KEY")
        if not self.api_key:
            logger.warning("SendGrid API key not configured")
            self.client = None
        else:
            self.client = SendGridAPIClient(self.api_key)

        self.from_email = os.getenv("FROM_EMAIL", "support@opendatagov.io")

    async def send_csat_survey(
        self,
        ticket_id: str,
        ticket_subject: str,
        customer_email: str,
        customer_name: str,
        survey_link: str,
    ) -> bool:
        """Send CSAT survey email to customer.

        Args:
            ticket_id: Ticket ID
            ticket_subject: Ticket subject for context
            customer_email: Customer email
            customer_name: Customer name
            survey_link: Link to CSAT survey (with token)

        Returns:
            True if sent successfully
        """
        if not self.client:
            logger.error("SendGrid client not configured")
            return False

        # Email template
        subject = f"How was your support experience? (Ticket #{ticket_id[:8]})"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .rating-buttons {{ text-align: center; margin: 30px 0; }}
        .rating-button {{
            display: inline-block;
            width: 50px;
            height: 50px;
            margin: 0 5px;
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            text-decoration: none;
            color: #6b7280;
            font-size: 24px;
            line-height: 46px;
            transition: all 0.2s;
        }}
        .rating-button:hover {{ background: #4F46E5; color: white; border-color: #4F46E5; transform: scale(1.1); }}
        .footer {{ text-align: center; margin-top: 20px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📝 How was your support experience?</h1>
        </div>
        <div class="content">
            <p>Hi {customer_name},</p>

            <p>Your support ticket has been resolved:</p>

            <div style="background: white; padding: 15px; border-left: 4px solid #4F46E5; margin: 20px 0;">
                <strong>Ticket #{ticket_id[:8]}</strong><br>
                {ticket_subject}
            </div>

            <p>We'd love to hear about your experience! Please rate our support:</p>

            <div class="rating-buttons">
                <a href="{survey_link}?rating=1" class="rating-button">😞</a>
                <a href="{survey_link}?rating=2" class="rating-button">😕</a>
                <a href="{survey_link}?rating=3" class="rating-button">😐</a>
                <a href="{survey_link}?rating=4" class="rating-button">🙂</a>
                <a href="{survey_link}?rating=5" class="rating-button">😄</a>
            </div>

            <p style="text-align: center; color: #6b7280; font-size: 14px;">
                1 = Very Poor | 5 = Excellent
            </p>

            <p>Your feedback helps us improve our service!</p>

            <p>Best regards,<br>
            <strong>OpenDataGov Support Team</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply directly to this email.</p>
            <p>© 2026 OpenDataGov. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        try:
            message = Mail(
                from_email=Email(self.from_email, "OpenDataGov Support"),
                to_emails=To(customer_email, customer_name),
                subject=subject,
                html_content=Content("text/html", html_content),
            )

            # Add custom args for tracking
            message.custom_arg = [
                {"ticket_id": ticket_id},
                {"email_type": "csat_survey"},
            ]

            response = self.client.send(message)

            if response.status_code == 202:
                logger.info(f"✅ Sent CSAT survey to {customer_email} for ticket {ticket_id}")
                return True
            else:
                logger.error(f"Failed to send CSAT email: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending CSAT email: {e}")
            return False

    async def send_ticket_notification(
        self,
        ticket_id: str,
        ticket_subject: str,
        customer_email: str,
        customer_name: str,
        status: str,
        message: str,
    ) -> bool:
        """Send ticket status notification to customer.

        Args:
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            customer_email: Customer email
            customer_name: Customer name
            status: New ticket status
            message: Status update message

        Returns:
            True if sent successfully
        """
        if not self.client:
            logger.error("SendGrid client not configured")
            return False

        status_emoji = {
            "new": "🆕",
            "open": "🔵",
            "pending": "⏸️",
            "solved": "✅",
            "closed": "🔒",
        }.get(status.lower(), "[i]")

        subject = f"{status_emoji} Ticket Update: {ticket_subject[:50]}..."

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .status-badge {{
            display: inline-block;
            padding: 5px 15px;
            background: #10b981;
            color: white;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 12px;
        }}
        .ticket-box {{ background: white; padding: 15px; border-left: 4px solid #4F46E5; margin: 20px 0; }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background: #4F46E5;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
        }}
        .footer {{ text-align: center; margin-top: 20px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{status_emoji} Ticket Update</h1>
        </div>
        <div class="content">
            <p>Hi {customer_name},</p>

            <p>Your support ticket has been updated:</p>

            <div class="ticket-box">
                <strong>Ticket #{ticket_id[:8]}</strong><br>
                {ticket_subject}<br><br>
                <span class="status-badge">{status}</span>
            </div>

            <p><strong>Update:</strong></p>
            <p>{message}</p>

            <p style="text-align: center; margin: 30px 0;">
                <a href="https://support.opendatagov.io/tickets/{ticket_id}" class="button">
                    View Ticket
                </a>
            </p>

            <p>If you have any questions, simply reply to your ticket.</p>

            <p>Best regards,<br>
            <strong>OpenDataGov Support Team</strong></p>
        </div>
        <div class="footer">
            <p>© 2026 OpenDataGov. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        try:
            message = Mail(
                from_email=Email(self.from_email, "OpenDataGov Support"),
                to_emails=To(customer_email, customer_name),
                subject=subject,
                html_content=Content("text/html", html_content),
            )

            message.custom_arg = [
                {"ticket_id": ticket_id},
                {"email_type": "status_update"},
            ]

            response = self.client.send(message)

            if response.status_code == 202:
                logger.info(f"✅ Sent ticket notification to {customer_email}")
                return True
            else:
                logger.error(f"Failed to send notification: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False

    async def send_sla_breach_alert(
        self,
        ticket_id: str,
        ticket_subject: str,
        priority: str,
        sla_elapsed_pct: float,
        assigned_to: str | None,
        escalation_level: str,
    ) -> bool:
        """Send SLA breach alert to internal team.

        Args:
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            priority: Ticket priority
            sla_elapsed_pct: SLA percentage elapsed
            assigned_to: Agent assigned (if any)
            escalation_level: Escalation level (manager, director, vp)

        Returns:
            True if sent successfully
        """
        if not self.client:
            logger.error("SendGrid client not configured")
            return False

        # Determine recipient based on escalation level
        recipient_map = {
            "notify_manager": "manager@opendatagov.io",
            "escalate_to_director": "director@opendatagov.io",
            "escalate_to_vp_engineering": "vp-eng@opendatagov.io",
            "page_on_call": "oncall@opendatagov.io",
        }

        recipient = recipient_map.get(escalation_level, "manager@opendatagov.io")

        subject = f"🚨 SLA BREACH ALERT: {priority} Ticket #{ticket_id[:8]}"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #dc2626; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #fef2f2; padding: 30px; border-radius: 0 0 8px 8px; border: 2px solid #dc2626; }}
        .alert-box {{ background: #fee2e2; padding: 20px; border-left: 4px solid #dc2626; margin: 20px 0; }}
        .metric {{ font-size: 48px; font-weight: bold; color: #dc2626; text-align: center; }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background: #dc2626;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 SLA BREACH ALERT</h1>
        </div>
        <div class="content">
            <div class="alert-box">
                <strong>Ticket #{ticket_id[:8]}</strong><br>
                {ticket_subject}<br><br>
                <strong>Priority:</strong> {priority}<br>
                <strong>Assigned To:</strong> {assigned_to or "Unassigned"}<br>
                <strong>Escalation:</strong> {escalation_level.replace("_", " ").title()}
            </div>

            <div class="metric">
                {sla_elapsed_pct:.0f}%
            </div>
            <p style="text-align: center; color: #991b1b; font-weight: bold;">
                SLA ELAPSED
            </p>

            <p style="text-align: center; margin: 30px 0;">
                <a href="https://support.opendatagov.io/admin/tickets/{ticket_id}" class="button">
                    VIEW TICKET NOW
                </a>
            </p>

            <p><strong>Immediate Action Required:</strong></p>
            <ul>
                <li>Prioritize this ticket immediately</li>
                <li>Contact customer if not already done</li>
                <li>Escalate to senior engineer if needed</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

        try:
            message = Mail(
                from_email=Email(self.from_email, "OpenDataGov Support Alerts"),
                to_emails=To(recipient),
                subject=subject,
                html_content=Content("text/html", html_content),
            )

            message.custom_arg = [
                {"ticket_id": ticket_id},
                {"email_type": "sla_breach_alert"},
                {"escalation_level": escalation_level},
            ]

            response = self.client.send(message)

            if response.status_code == 202:
                logger.info(f"✅ Sent SLA breach alert to {recipient}")
                return True
            else:
                logger.error(f"Failed to send SLA alert: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending SLA alert: {e}")
            return False
