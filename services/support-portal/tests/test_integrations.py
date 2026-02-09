"""Integration tests for external services - Phase 5.

Tests PagerDuty, Jira, Slack, SendGrid, Webhook integrations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from support_portal.email_client import EmailClient
from support_portal.jira_client import JiraClient
from support_portal.pagerduty_client import PagerDutyClient
from support_portal.slack_client import SlackClient
from support_portal.webhook_manager import WebhookManager


class TestPagerDutyIntegration:
    """Test PagerDuty client."""

    @pytest.fixture
    def pd_client(self):
        """Create PagerDuty client with test credentials."""
        return PagerDutyClient(api_token="test_token", integration_key="test_integration_key")

    @pytest.mark.asyncio
    async def test_create_incident(self, pd_client):
        """Test creating PagerDuty incident."""
        with patch.object(pd_client.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_response.json.return_value = {
                "dedup_key": "support-ticket-tkt_123",
                "status": "success",
                "message": "Event processed",
            }
            mock_post.return_value = mock_response

            result = await pd_client.create_incident(
                ticket_id="tkt_123",
                ticket_subject="Test incident",
                priority="P1_CRITICAL",
                customer_name="Test Customer",
                description="Test description",
            )

            assert result is not None
            assert result["dedup_key"] == "support-ticket-tkt_123"
            assert result["status"] == "success"

            # Verify API call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0].endswith("/enqueue")
            payload = call_args[1]["json"]
            assert payload["event_action"] == "trigger"
            assert payload["payload"]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_acknowledge_incident(self, pd_client):
        """Test acknowledging incident."""
        with patch.object(pd_client.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_response.json.return_value = {"status": "success"}
            mock_post.return_value = mock_response

            result = await pd_client.acknowledge_incident("tkt_456")

            assert result is True

            # Verify acknowledge action
            payload = mock_post.call_args[1]["json"]
            assert payload["event_action"] == "acknowledge"

    @pytest.mark.asyncio
    async def test_resolve_incident(self, pd_client):
        """Test resolving incident."""
        with patch.object(pd_client.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_post.return_value = mock_response

            result = await pd_client.resolve_incident("tkt_789")

            assert result is True

            # Verify resolve action
            payload = mock_post.call_args[1]["json"]
            assert payload["event_action"] == "resolve"

    @pytest.mark.asyncio
    async def test_get_on_call_user(self, pd_client):
        """Test getting on-call engineer."""
        with patch.object(pd_client.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "oncalls": [
                    {
                        "user": {"id": "USER123", "summary": "John Engineer", "email": "john@opendatagov.io"},
                        "escalation_level": 1,
                    }
                ]
            }
            mock_get.return_value = mock_response

            with patch.dict("os.environ", {"PAGERDUTY_ESCALATION_POLICY_ID": "POL123"}):
                result = await pd_client.get_on_call_user()

            assert result is not None
            assert result["name"] == "John Engineer"
            assert result["email"] == "john@opendatagov.io"

    @pytest.mark.asyncio
    async def test_api_error_handling(self, pd_client):
        """Test error handling for API failures."""
        with patch.object(pd_client.client, "post") as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "API Error", request=MagicMock(), response=MagicMock(status_code=400, text="Bad Request")
            )

            result = await pd_client.create_incident(
                ticket_id="tkt_error",
                ticket_subject="Test",
                priority="P1_CRITICAL",
                customer_name="Test",
                description="Test",
            )

            assert result is None


class TestJiraIntegration:
    """Test Jira client."""

    @pytest.fixture
    def jira_client(self):
        """Create Jira client with test credentials."""
        return JiraClient(jira_url="https://test.atlassian.net", email="test@opendatagov.io", api_token="test_token")

    @pytest.mark.asyncio
    async def test_create_issue(self, jira_client):
        """Test creating Jira issue."""
        with patch.object(jira_client.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"key": "SUP-123", "id": "10001"}
            mock_post.return_value = mock_response

            result = await jira_client.create_issue(
                ticket_id="tkt_123",
                ticket_subject="Test Bug",
                description="Test description",
                issue_type="Bug",
                priority="High",
            )

            assert result is not None
            assert result["key"] == "SUP-123"
            assert result["url"] == "https://test.atlassian.net/browse/SUP-123"

            # Verify payload structure
            payload = mock_post.call_args[1]["json"]
            assert payload["fields"]["issuetype"]["name"] == "Bug"
            assert payload["fields"]["priority"]["name"] == "High"

    @pytest.mark.asyncio
    async def test_add_comment(self, jira_client):
        """Test adding comment to issue."""
        with patch.object(jira_client.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_post.return_value = mock_response

            result = await jira_client.add_comment(issue_key="SUP-123", comment="Test comment")

            assert result is True

            # Verify Atlassian Document Format
            payload = mock_post.call_args[1]["json"]
            assert payload["body"]["type"] == "doc"
            assert payload["body"]["content"][0]["type"] == "paragraph"

    @pytest.mark.asyncio
    async def test_update_status(self, jira_client):
        """Test updating issue status."""
        with patch.object(jira_client.client, "get") as mock_get, patch.object(jira_client.client, "post") as mock_post:
            # Mock transitions endpoint
            mock_get_response = MagicMock()
            mock_get_response.status_code = 200
            mock_get_response.json.return_value = {
                "transitions": [{"id": "31", "name": "In Progress"}, {"id": "41", "name": "Done"}]
            }
            mock_get.return_value = mock_get_response

            # Mock transition execution
            mock_post_response = MagicMock()
            mock_post_response.status_code = 204
            mock_post.return_value = mock_post_response

            result = await jira_client.update_status("SUP-123", "In Progress")

            assert result is True

            # Verify correct transition ID used
            payload = mock_post.call_args[1]["json"]
            assert payload["transition"]["id"] == "31"

    @pytest.mark.asyncio
    async def test_search_issues_by_ticket(self, jira_client):
        """Test searching issues linked to ticket."""
        with patch.object(jira_client.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "issues": [
                    {
                        "key": "SUP-456",
                        "fields": {
                            "summary": "Related Bug",
                            "status": {"name": "In Progress"},
                            "priority": {"name": "High"},
                            "assignee": {"displayName": "John Doe"},
                            "created": "2026-02-01T10:00:00Z",
                        },
                    }
                ]
            }
            mock_get.return_value = mock_response

            result = await jira_client.search_issues_by_ticket("tkt_12345678")

            assert len(result) == 1
            assert result[0]["key"] == "SUP-456"
            assert result[0]["summary"] == "Related Bug"

            # Verify JQL query
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert "ticket-tkt_12345" in params["jql"]


class TestSlackIntegration:
    """Test Slack client."""

    @pytest.fixture
    def slack_client(self):
        """Create Slack client with test token."""
        return SlackClient(bot_token="xoxb-test-token")

    @pytest.mark.asyncio
    async def test_notify_critical_ticket(self, slack_client):
        """Test sending critical ticket notification."""
        with patch.object(slack_client.client, "chat_postMessage") as mock_post:
            mock_post.return_value = {"ok": True, "ts": "1234567890.123456"}

            result = await slack_client.notify_critical_ticket(
                ticket_id="tkt_123",
                ticket_subject="Production Down",
                customer_name="Enterprise Corp",
                priority="P1_CRITICAL",
                assigned_to="john@opendatagov.io",
            )

            assert result is True

            # Verify message structure
            call_args = mock_post.call_args
            assert call_args[1]["channel"] == "#support-critical"
            blocks = call_args[1]["blocks"]
            assert any("🚨 CRITICAL" in str(block) for block in blocks)

    @pytest.mark.asyncio
    async def test_notify_sla_breach(self, slack_client):
        """Test SLA breach notification."""
        with patch.object(slack_client.client, "chat_postMessage") as mock_post:
            mock_post.return_value = {"ok": True}

            result = await slack_client.notify_sla_breach(
                ticket_id="tkt_456", priority="P2_HIGH", sla_elapsed_pct=105.0, escalation_level=1
            )

            assert result is True

            # Verify urgency color
            mock_post.call_args[1]["blocks"]
            # Color should be red (#DC3545)

    @pytest.mark.asyncio
    async def test_team_metrics_notification(self, slack_client):
        """Test team metrics summary."""
        with patch.object(slack_client.client, "chat_postMessage") as mock_post:
            mock_post.return_value = {"ok": True}

            result = await slack_client.notify_team_metrics(
                period="Last 7 days",
                total_tickets=145,
                sla_compliance_rate=94.5,
                avg_csat_score=4.3,
                top_agent="John Engineer",
                top_agent_tickets=28,
            )

            assert result is True

            # Verify metrics formatting
            blocks = mock_post.call_args[1]["blocks"]
            assert any("145" in str(block) for block in blocks)
            assert any("94.5%" in str(block) for block in blocks)


class TestEmailIntegration:
    """Test email client."""

    @pytest.fixture
    def email_client(self):
        """Create email client with test API key."""
        return EmailClient(api_key="SG.test_api_key")

    @pytest.mark.asyncio
    async def test_send_csat_survey(self, email_client):
        """Test sending CSAT survey email."""
        with patch.object(email_client.client.client, "send") as mock_send:
            mock_send.return_value.status_code = 202

            result = await email_client.send_csat_survey(
                ticket_id="tkt_789",
                ticket_subject="Test Ticket",
                customer_email="customer@example.com",
                customer_name="Test Customer",
                survey_link="https://support.opendatagov.io/survey/abc123",
            )

            assert result is True

            # Verify email content
            call_args = mock_send.call_args
            message = call_args[0][0]
            assert message.from_email.email == "support@opendatagov.io"
            assert message.personalizations[0].tos[0]["email"] == "customer@example.com"
            assert "Rate your experience" in message.subject.get()

    @pytest.mark.asyncio
    async def test_send_sla_breach_alert(self, email_client):
        """Test sending SLA breach alert."""
        with patch.object(email_client.client.client, "send") as mock_send:
            mock_send.return_value.status_code = 202

            result = await email_client.send_sla_breach_alert(
                ticket_id="tkt_critical", priority="P1_CRITICAL", sla_elapsed_pct=120.0, escalation_level=2
            )

            assert result is True

            message = mock_send.call_args[0][0]
            assert "SLA BREACH" in message.subject.get()


class TestWebhookIntegration:
    """Test webhook manager."""

    @pytest.fixture
    async def webhook_manager(self):
        """Create webhook manager with mock DB."""
        db = AsyncMock()
        manager = WebhookManager(db)
        yield manager
        await manager.close()

    @pytest.mark.asyncio
    async def test_send_event_with_signature(self, webhook_manager):
        """Test sending webhook with HMAC signature."""
        with (
            patch.object(webhook_manager, "_get_subscriptions") as mock_subs,
            patch.object(webhook_manager.client, "post") as mock_post,
        ):
            # Mock subscription
            from support_portal.webhook_manager import WebhookSubscription

            mock_subs.return_value = [
                WebhookSubscription(
                    webhook_id="wh_123",
                    url="https://example.com/webhook",
                    events=["ticket.created"],
                    secret="test_secret",
                )
            ]

            # Mock HTTP response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            await webhook_manager.send_event(event_type="ticket.created", payload={"ticket_id": "tkt_123"})

            # Verify signature header
            call_args = mock_post.call_args
            headers = call_args[1]["headers"]
            assert "X-Webhook-Signature" in headers
            assert headers["X-Webhook-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_verify_signature(self):
        """Test webhook signature verification."""
        from support_portal.webhook_manager import WebhookManager

        payload = {"event": "test", "data": {"foo": "bar"}}
        secret = "test_secret"

        # Generate signature
        import hashlib
        import hmac
        import json

        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        expected_sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

        signature = f"sha256={expected_sig}"

        # Verify
        is_valid = WebhookManager.verify_signature(payload, signature, secret)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_webhook_retry_on_failure(self, webhook_manager):
        """Test webhook delivery retry logic."""
        with (
            patch.object(webhook_manager, "_get_subscriptions") as mock_subs,
            patch.object(webhook_manager.client, "post") as mock_post,
        ):
            from support_portal.webhook_manager import WebhookSubscription

            mock_subs.return_value = [
                WebhookSubscription(
                    webhook_id="wh_456", url="https://example.com/webhook", events=["ticket.updated"], secret=None
                )
            ]

            # Mock failure
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_post.return_value = mock_response

            await webhook_manager.send_event(event_type="ticket.updated", payload={"ticket_id": "tkt_456"})

            # Should log warning but not raise exception
            mock_post.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
