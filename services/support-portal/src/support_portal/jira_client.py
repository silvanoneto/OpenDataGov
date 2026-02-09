"""Jira integration for creating engineering tasks from support tickets.

Syncs critical bugs and feature requests from support to Jira.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from httpx import BasicAuth

logger = logging.getLogger(__name__)


class JiraClient:
    """Jira API client for issue management."""

    def __init__(
        self,
        jira_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ):
        """Initialize Jira client.

        Args:
            jira_url: Jira instance URL (defaults to JIRA_URL env var)
            email: Jira account email (defaults to JIRA_EMAIL)
            api_token: Jira API token (defaults to JIRA_API_TOKEN)
        """
        self.jira_url = (jira_url or os.getenv("JIRA_URL", "")).rstrip("/")
        self.email = email or os.getenv("JIRA_EMAIL")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN")

        if not all([self.jira_url, self.email, self.api_token]):
            logger.warning("Jira credentials not configured")
            self.enabled = False
        else:
            self.enabled = True
            self.auth = BasicAuth(self.email, self.api_token)

        self.client = httpx.AsyncClient(timeout=30.0)

        # Project keys
        self.project_keys = {
            "bug": os.getenv("JIRA_BUG_PROJECT", "SUP"),
            "feature": os.getenv("JIRA_FEATURE_PROJECT", "FEAT"),
        }

    async def create_issue(
        self,
        ticket_id: str,
        ticket_subject: str,
        description: str,
        issue_type: str = "Bug",
        priority: str = "High",
        labels: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Create Jira issue from support ticket.

        Args:
            ticket_id: Support ticket ID
            ticket_subject: Ticket subject
            description: Issue description
            issue_type: Jira issue type (Bug, Task, Story)
            priority: Issue priority (Highest, High, Medium, Low)
            labels: Optional labels

        Returns:
            Created issue data or None if failed
        """
        if not self.enabled:
            logger.error("Jira not configured")
            return None

        # Determine project key
        project_key = self.project_keys.get("bug" if issue_type == "Bug" else "feature", self.project_keys["bug"])

        # Build issue payload
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": ticket_subject,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": description,
                                }
                            ],
                        },
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "\n\nSupport Ticket: ",
                                },
                                {
                                    "type": "text",
                                    "text": f"#{ticket_id}",
                                    "marks": [{"type": "strong"}],
                                },
                            ],
                        },
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "View ticket: ",
                                },
                                {
                                    "type": "text",
                                    "text": f"https://support.opendatagov.io/tickets/{ticket_id}",
                                    "marks": [
                                        {
                                            "type": "link",
                                            "attrs": {"href": f"https://support.opendatagov.io/tickets/{ticket_id}"},
                                        }
                                    ],
                                },
                            ],
                        },
                    ],
                },
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
                "labels": labels or ["support-ticket", f"ticket-{ticket_id[:8]}"],
            }
        }

        try:
            response = await self.client.post(
                f"{self.jira_url}/rest/api/3/issue",
                json=payload,
                auth=self.auth,
            )

            response.raise_for_status()
            data = response.json()

            issue_key = data.get("key")
            issue_url = f"{self.jira_url}/browse/{issue_key}"

            logger.info(f"✅ Created Jira issue {issue_key} for ticket {ticket_id}")

            return {
                "key": issue_key,
                "id": data.get("id"),
                "url": issue_url,
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Jira API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error creating Jira issue: {e}")
            return None

    async def add_comment(
        self,
        issue_key: str,
        comment: str,
    ) -> bool:
        """Add comment to Jira issue.

        Args:
            issue_key: Jira issue key (e.g., SUP-123)
            comment: Comment text

        Returns:
            True if added successfully
        """
        if not self.enabled:
            return False

        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": comment,
                            }
                        ],
                    }
                ],
            }
        }

        try:
            response = await self.client.post(
                f"{self.jira_url}/rest/api/3/issue/{issue_key}/comment",
                json=payload,
                auth=self.auth,
            )

            response.raise_for_status()

            logger.info(f"✅ Added comment to Jira issue {issue_key}")
            return True

        except Exception as e:
            logger.error(f"Error adding Jira comment: {e}")
            return False

    async def update_status(
        self,
        issue_key: str,
        status: str,
    ) -> bool:
        """Update Jira issue status.

        Args:
            issue_key: Jira issue key
            status: New status (e.g., "In Progress", "Done")

        Returns:
            True if updated successfully
        """
        if not self.enabled:
            return False

        # Get available transitions
        try:
            transitions_response = await self.client.get(
                f"{self.jira_url}/rest/api/3/issue/{issue_key}/transitions",
                auth=self.auth,
            )

            transitions_response.raise_for_status()
            transitions = transitions_response.json().get("transitions", [])

            # Find transition ID by name
            transition_id = None
            for transition in transitions:
                if transition["name"].lower() == status.lower():
                    transition_id = transition["id"]
                    break

            if not transition_id:
                logger.error(f"No transition found for status '{status}'")
                return False

            # Execute transition
            payload = {"transition": {"id": transition_id}}

            response = await self.client.post(
                f"{self.jira_url}/rest/api/3/issue/{issue_key}/transitions",
                json=payload,
                auth=self.auth,
            )

            response.raise_for_status()

            logger.info(f"✅ Updated Jira issue {issue_key} to status '{status}'")
            return True

        except Exception as e:
            logger.error(f"Error updating Jira status: {e}")
            return False

    async def link_issue_to_ticket(
        self,
        issue_key: str,
        ticket_id: str,
    ) -> bool:
        """Add web link from Jira issue to support ticket.

        Args:
            issue_key: Jira issue key
            ticket_id: Support ticket ID

        Returns:
            True if linked successfully
        """
        if not self.enabled:
            return False

        payload = {
            "object": {
                "url": f"https://support.opendatagov.io/tickets/{ticket_id}",
                "title": f"Support Ticket #{ticket_id[:8]}",
            }
        }

        try:
            response = await self.client.post(
                f"{self.jira_url}/rest/api/3/issue/{issue_key}/remotelink",
                json=payload,
                auth=self.auth,
            )

            response.raise_for_status()

            logger.info(f"✅ Linked Jira issue {issue_key} to ticket {ticket_id}")
            return True

        except Exception as e:
            logger.error(f"Error linking Jira issue: {e}")
            return False

    async def get_issue(self, issue_key: str) -> dict[str, Any] | None:
        """Get Jira issue details.

        Args:
            issue_key: Jira issue key

        Returns:
            Issue data or None
        """
        if not self.enabled:
            return None

        try:
            response = await self.client.get(
                f"{self.jira_url}/rest/api/3/issue/{issue_key}",
                auth=self.auth,
            )

            response.raise_for_status()
            data = response.json()

            fields = data.get("fields", {})

            return {
                "key": data.get("key"),
                "id": data.get("id"),
                "summary": fields.get("summary"),
                "status": fields.get("status", {}).get("name"),
                "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
                "priority": fields.get("priority", {}).get("name"),
                "created": fields.get("created"),
                "updated": fields.get("updated"),
                "url": f"{self.jira_url}/browse/{data.get('key')}",
            }

        except Exception as e:
            logger.error(f"Error getting Jira issue: {e}")
            return None

    async def search_issues_by_ticket(self, ticket_id: str) -> list[dict[str, Any]]:
        """Search Jira issues linked to support ticket.

        Args:
            ticket_id: Support ticket ID

        Returns:
            List of linked issues
        """
        if not self.enabled:
            return []

        # JQL query to find issues with ticket label
        jql = f'labels = "ticket-{ticket_id[:8]}"'

        try:
            response = await self.client.get(
                f"{self.jira_url}/rest/api/3/search",
                params={
                    "jql": jql,
                    "fields": "summary,status,assignee,priority,created",
                },
                auth=self.auth,
            )

            response.raise_for_status()
            data = response.json()

            issues = []
            for issue in data.get("issues", []):
                fields = issue.get("fields", {})
                issues.append(
                    {
                        "key": issue.get("key"),
                        "summary": fields.get("summary"),
                        "status": fields.get("status", {}).get("name"),
                        "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
                        "priority": fields.get("priority", {}).get("name"),
                        "created": fields.get("created"),
                        "url": f"{self.jira_url}/browse/{issue.get('key')}",
                    }
                )

            return issues

        except Exception as e:
            logger.error(f"Error searching Jira issues: {e}")
            return []

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
