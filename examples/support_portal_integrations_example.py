"""Support Portal Integrations Example - Phase 4.

Demonstrates PagerDuty, Jira, DataHub, and Webhook integrations.
"""

import asyncio

from odg_core.db.session import get_async_session
from support_portal.jira_client import JiraClient
from support_portal.pagerduty_client import PagerDutyClient
from support_portal.webhook_manager import WebhookEvents, WebhookManager


async def example_1_pagerduty_incident():
    """Example 1: Create PagerDuty incident for P1 ticket."""
    print("\n=== Example 1: PagerDuty Integration ===\n")

    pagerduty = PagerDutyClient()

    # Create critical incident
    incident = await pagerduty.create_incident(
        ticket_id="tkt_12345678",
        ticket_subject="Production Database Connection Failure",
        priority="P1_CRITICAL",
        customer_name="ACME Corporation",
        description="""
Database connection pool exhausted in production environment.
All API requests failing with 500 errors.

Error: "Connection timeout after 30s"
Affected: 100% of users
Started: 10 minutes ago
        """,
        urgency="high",
    )

    if incident:
        print("✅ PagerDuty incident created:")
        print(f"   Dedup Key: {incident['dedup_key']}")
        print(f"   Status: {incident['status']}")

        # Get on-call engineer
        oncall = await pagerduty.get_on_call_user()
        if oncall:
            print(f"\n📟 On-Call Engineer: {oncall['name']} ({oncall['email']})")

        # Simulate agent starting work (acknowledge)
        print("\n📌 Agent acknowledged incident...")
        await pagerduty.acknowledge_incident("tkt_12345678")

        # Add progress note
        await pagerduty.add_incident_note(
            ticket_id="tkt_12345678",
            note="Identified root cause: database connection leak. Restarting service.",
        )

        # Resolve incident when ticket is solved
        print("✅ Issue resolved, closing PagerDuty incident...")
        await pagerduty.resolve_incident("tkt_12345678")

    await pagerduty.close()


async def example_2_jira_bug_tracking():
    """Example 2: Create Jira bug from support ticket."""
    print("\n=== Example 2: Jira Integration ===\n")

    jira = JiraClient()

    # Create bug ticket
    issue = await jira.create_issue(
        ticket_id="tkt_87654321",
        ticket_subject="Data Quality Check Failing for CSV Files",
        description="""
**Bug Report from Customer Support**

Customer is experiencing failures in data quality validation for CSV uploads.

**Steps to Reproduce:**
1. Upload CSV file with 1M+ rows
2. Run quality checks
3. Check fails with "Memory allocation error"

**Expected:** Quality check should complete successfully
**Actual:** Process crashes after ~500K rows

**Environment:**
- Version: v0.4.0
- Dataset size: 1.2M rows
- Memory limit: 4GB
        """,
        issue_type="Bug",
        priority="High",
        labels=["support-ticket", "data-quality", "csv", "memory"],
    )

    if issue:
        print(f"✅ Jira issue created: {issue['key']}")
        print(f"   URL: {issue['url']}")

        # Link issue to support ticket
        await jira.link_issue_to_ticket(
            issue_key=issue["key"],
            ticket_id="tkt_87654321",
        )

        # Add comment with additional info
        await jira.add_comment(
            issue_key=issue["key"],
            comment="Customer reports this started after upgrading to v0.4.0. May be related to Polars upgrade.",
        )

        # Update status when work starts
        print("\n🔧 Moving to In Progress...")
        await jira.update_status(issue["key"], "In Progress")

        # Search for all issues related to this ticket
        print("\n🔍 Searching for related Jira issues...")
        related_issues = await jira.search_issues_by_ticket("tkt_87654321")
        for related in related_issues:
            print(f"   - {related['key']}: {related['summary']} ({related['status']})")

    await jira.close()


async def example_3_webhook_events():
    """Example 3: Send webhook events to external systems."""
    print("\n=== Example 3: Webhook Integration ===\n")

    async with get_async_session() as db:
        webhook_manager = WebhookManager(db)
        webhook_events = WebhookEvents(webhook_manager)

        # Example: Ticket created
        await webhook_events.ticket_created(
            ticket={
                "ticket_id": "tkt_99887766",
                "subject": "Unable to Access Governance Dashboard",
                "priority": "P2_HIGH",
                "status": "NEW",
                "customer_name": "John Doe",
                "customer_email": "john@example.com",
                "created_at": "2026-02-08T15:30:00Z",
            }
        )
        print("✅ Sent webhook: ticket.created")

        # Example: Ticket updated
        await webhook_events.ticket_updated(
            ticket={
                "ticket_id": "tkt_99887766",
                "status": "OPEN",
                "priority": "P2_HIGH",
                "assigned_to": "agent@opendatagov.io",
                "updated_at": "2026-02-08T15:35:00Z",
            },
            changes={
                "status": {"from": "NEW", "to": "OPEN"},
                "assigned_to": {"from": None, "to": "agent@opendatagov.io"},
            },
        )
        print("✅ Sent webhook: ticket.updated")

        # Example: Comment created
        await webhook_events.comment_created(
            ticket_id="tkt_99887766",
            comment={
                "comment_id": "cmt_11223344",
                "author": "agent@opendatagov.io",
                "is_internal": False,
                "created_at": "2026-02-08T15:40:00Z",
            },
        )
        print("✅ Sent webhook: comment.created")

        # Example: CSAT submitted
        await webhook_events.csat_submitted(
            ticket_id="tkt_99887766",
            rating=5,
            feedback="Excellent support! Very responsive and helpful.",
        )
        print("✅ Sent webhook: csat.submitted")

        # Example: SLA breached
        await webhook_events.sla_breached(
            ticket_id="tkt_99887766",
            sla_type="response",
            elapsed_pct=105.0,
        )
        print("✅ Sent webhook: sla.breached")

        await webhook_manager.close()


async def example_4_full_workflow():
    """Example 4: Complete workflow with all integrations."""
    print("\n=== Example 4: Complete Integration Workflow ===\n")

    # Step 1: Critical ticket created
    print("1️⃣  Customer creates critical P1 ticket...")
    ticket = {
        "ticket_id": "tkt_critical_001",
        "subject": "Production Outage - Cannot Access Data Catalog",
        "priority": "P1_CRITICAL",
        "status": "NEW",
        "customer_name": "Enterprise Customer",
        "customer_email": "ops@enterprise.com",
        "description": "All catalog queries failing with 503 errors",
    }

    # Step 2: Send webhook notification
    async with get_async_session() as db:
        webhook_manager = WebhookManager(db)
        webhook_events = WebhookEvents(webhook_manager)
        await webhook_events.ticket_created(ticket)
        print("   ✅ Webhook sent to monitoring systems")

    # Step 3: Create PagerDuty incident (critical priority)
    pagerduty = PagerDutyClient()
    pd_incident = await pagerduty.create_incident(
        ticket_id=ticket["ticket_id"],
        ticket_subject=ticket["subject"],
        priority=ticket["priority"],
        customer_name=ticket["customer_name"],
        description=ticket["description"],
    )
    print(f"   ✅ PagerDuty incident created: {pd_incident['dedup_key']}")

    # Step 4: Get on-call engineer
    oncall = await pagerduty.get_on_call_user()
    print(f"   📟 Paged on-call engineer: {oncall['name']}")

    # Step 5: Engineer acknowledges
    print("\n2️⃣  Engineer acknowledges incident...")
    await pagerduty.acknowledge_incident(ticket["ticket_id"])
    print("   ✅ Incident acknowledged")

    # Step 6: Investigation reveals bug - create Jira ticket
    print("\n3️⃣  Bug identified, creating Jira ticket...")
    jira = JiraClient()
    jira_issue = await jira.create_issue(
        ticket_id=ticket["ticket_id"],
        ticket_subject="Critical: Catalog Service Connection Pool Exhaustion",
        description="Root cause: Connection pool leak in catalog-agent service",
        issue_type="Bug",
        priority="Highest",
    )
    print(f"   ✅ Jira issue created: {jira_issue['key']}")

    # Step 7: Update Jira to In Progress
    await jira.update_status(jira_issue["key"], "In Progress")

    # Step 8: Add progress notes
    await pagerduty.add_incident_note(
        ticket["ticket_id"],
        "Root cause identified. Deploying fix.",
    )
    await jira.add_comment(
        jira_issue["key"],
        "Deploying hotfix to restart service with increased connection pool size.",
    )

    # Step 9: Issue resolved
    print("\n4️⃣  Issue resolved...")
    await pagerduty.resolve_incident(ticket["ticket_id"])
    await jira.update_status(jira_issue["key"], "Done")
    print("   ✅ PagerDuty incident resolved")
    print("   ✅ Jira issue closed")

    # Step 10: Send resolution webhook
    async with get_async_session() as db:
        webhook_manager = WebhookManager(db)
        webhook_events = WebhookEvents(webhook_manager)
        await webhook_events.ticket_solved(
            {
                "ticket_id": ticket["ticket_id"],
                "subject": ticket["subject"],
                "assigned_to": oncall["email"],
                "resolution_time_seconds": 3600,  # 1 hour
                "sla_breached": False,
                "resolved_at": "2026-02-08T16:30:00Z",
            }
        )
        print("   ✅ Resolution webhook sent")

    await pagerduty.close()
    await jira.close()

    print("\n✅ Complete workflow finished!")
    print("\nTimeline:")
    print("  15:30 - Ticket created, webhooks sent")
    print("  15:31 - PagerDuty incident created, engineer paged")
    print("  15:35 - Engineer acknowledged")
    print("  15:40 - Root cause found, Jira ticket created")
    print("  16:15 - Fix deployed")
    print("  16:30 - Incident resolved, within SLA ✅")


async def main():
    """Run all integration examples."""
    print("=" * 60)
    print("Support Portal - Phase 4 Integrations Examples")
    print("=" * 60)

    await example_1_pagerduty_incident()
    await example_2_jira_bug_tracking()
    await example_3_webhook_events()
    await example_4_full_workflow()

    print("\n" + "=" * 60)
    print("✅ All integration examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
