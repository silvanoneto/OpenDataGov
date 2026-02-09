"""Support Portal Example - Creating and Managing Support Tickets.

This example demonstrates:
1. Creating support tickets
2. Adding comments
3. Tracking SLA compliance
4. Searching knowledge base
5. Submitting CSAT surveys
"""

import asyncio
from datetime import datetime

from odg_core.db.session import get_async_session
from support_portal.models import (
    CreateTicketRequest,
    OrganizationRow,
    ProductArea,
    SupportTier,
    UserRow,
)
from support_portal.sla_manager import SLAManager
from support_portal.zendesk_client import ZendeskClient


async def create_sample_organization(db):
    """Create sample organization for demo."""
    org = OrganizationRow(
        org_id="org_enterprise_acme",
        name="ACME Corporation",
        support_tier=SupportTier.ENTERPRISE.value,
        max_tickets_per_month=None,  # Unlimited
    )

    db.add(org)
    await db.commit()

    print(f"✅ Created organization: {org.name} (Tier: {org.support_tier})")

    return org


async def create_sample_user(db, org_id: str):
    """Create sample user."""
    user = UserRow(
        user_id="user_john_doe",
        org_id=org_id,
        email="john.doe@acme.com",
        name="John Doe",
        role="customer",
    )

    db.add(user)
    await db.commit()

    print(f"✅ Created user: {user.name} ({user.email})")

    return user


async def example_1_create_critical_ticket():
    """Example 1: Create critical P1 ticket for production outage."""
    print("\n=== Example 1: Creating Critical P1 Ticket ===\n")

    async with get_async_session() as db:
        # Create org and user
        org = await create_sample_organization(db)
        await create_sample_user(db, org.org_id)

        # Import after session is ready
        from fastapi.testclient import TestClient
        from support_portal.main import app

        client = TestClient(app)

        # Create critical ticket
        request = CreateTicketRequest(
            subject="Production Data Pipeline Down - Cannot Access Datasets",
            description="""
Our production data pipeline has been down for the last 30 minutes.

**Impact:**
- Cannot access any datasets in the catalog
- ML models failing to fetch training data
- Dashboards showing stale data

**Error Message:**
```
ConnectionError: Failed to connect to lakehouse-agent:8000
Timeout after 30s
```

**Environment:**
- Deployment: Production (AWS us-east-1)
- Version: v0.4.0
- Last working: 2026-02-08 14:30 UTC

**Steps Attempted:**
1. Restarted lakehouse-agent pods
2. Checked PostgreSQL connectivity - OK
3. Checked MinIO connectivity - OK
4. Verified network policies - OK

Please help urgently as this is blocking our entire ML pipeline!
            """,
            product_area=ProductArea.CATALOG,
            severity="blocking",
            tags=["production", "outage", "urgent", "data-pipeline"],
        )

        response = client.post(
            "/api/v1/tickets",
            json=request.model_dump(),
            headers={"Authorization": "Bearer fake_token"},
        )

        if response.status_code == 201:
            ticket = response.json()
            print(f"✅ Created ticket: {ticket['ticket_id']}")
            print(f"   Subject: {ticket['subject']}")
            print(f"   Priority: {ticket['priority']}")
            print(f"   SLA Response Target: {ticket['sla_response_target']}")
            print(f"   SLA Resolution Target: {ticket['sla_resolution_target']}")

            # Calculate time until SLA breach
            response_target = datetime.fromisoformat(ticket["sla_response_target"].replace("Z", "+00:00"))
            time_until_breach = (response_target - datetime.now(response_target.tzinfo)).total_seconds() / 3600

            print(f"\n⏰ Time until SLA breach: {time_until_breach:.1f} hours")

            return ticket["ticket_id"]
        else:
            print(f"❌ Failed to create ticket: {response.text}")


async def example_2_add_comments_and_track_sla():
    """Example 2: Add comments and track SLA compliance."""
    print("\n=== Example 2: Adding Comments and Tracking SLA ===\n")

    ticket_id = await example_1_create_critical_ticket()

    if not ticket_id:
        print("⚠️  No ticket created, skipping example 2")
        return

    async with get_async_session() as db:
        sla_manager = SLAManager(db)

        # Simulate first response from support team (within SLA)
        print("📝 Support team responding to ticket...")

        # Record first response
        await sla_manager.record_first_response(ticket_id)

        # Check SLA compliance
        compliance = await sla_manager.check_sla_compliance(ticket_id)

        print("\n📊 SLA Compliance Status:")
        print(f"   First Response: {'✅ Within SLA' if compliance['first_response_compliant'] else '❌ BREACHED'}")
        print(f"   Response SLA Elapsed: {compliance['response_sla_elapsed_pct']:.1f}%")
        print(f"   SLA Breached: {compliance['sla_breached']}")

        # Check escalation
        escalations = await sla_manager.check_escalation(ticket_id)

        if escalations:
            print("\n🚨 Escalation Actions Triggered:")
            for action in escalations:
                print(f"   - {action}")


async def example_3_search_knowledge_base():
    """Example 3: Search knowledge base for common issues."""
    print("\n=== Example 3: Searching Knowledge Base ===\n")

    async with get_async_session() as db:
        from support_portal.models import KnowledgeBaseArticleRow

        # Create sample KB articles
        articles = [
            KnowledgeBaseArticleRow(
                article_id="kb_001",
                title="How to Troubleshoot Data Pipeline Connection Issues",
                slug="troubleshoot-data-pipeline",
                category="troubleshooting",
                content="""
# Troubleshooting Data Pipeline Connection Issues

If you're experiencing connection issues with the data pipeline, follow these steps:

## 1. Check Service Health

```bash
kubectl get pods -n opendatagov
```

Ensure all pods are in `Running` state.

## 2. Verify Database Connectivity

```bash
kubectl exec -it lakehouse-agent-0 -- pg_isready -h postgresql
```

## 3. Check MinIO/S3 Access

```bash
kubectl exec -it lakehouse-agent-0 -- aws s3 ls s3://odg-lakehouse/
```

## 4. Review Logs

```bash
kubectl logs -n opendatagov deployment/lakehouse-agent --tail=100
```

## Common Issues

- **Connection timeout**: Check network policies and security groups
- **Authentication error**: Verify AWS credentials or MinIO access keys
- **Permission denied**: Check IAM roles and S3 bucket policies

## Still Need Help?

If these steps don't resolve your issue, [create a support ticket](/tickets/new).
                """,
                tags=["troubleshooting", "data-pipeline", "connectivity"],
                author="support@opendatagov.io",
                published=True,
                view_count=245,
                helpful_votes=32,
                unhelpful_votes=3,
            ),
            KnowledgeBaseArticleRow(
                article_id="kb_002",
                title="Understanding Support Tiers and SLA",
                slug="support-tiers-sla",
                category="general",
                content="""
# Support Tiers and SLA

OpenDataGov offers three support tiers:

## Community (Free)
- Access to community forums
- Documentation and self-service resources
- Best-effort support
- No SLA guarantees

## Professional ($499/mo)
- Business hours support (9 AM - 5 PM ET)
- **SLA: 2 business days first response**
- Email support
- Monthly support review

## Enterprise ($2,999/mo)
- 24/7 priority support
- **SLA: 4 hours (P1), 8 hours (P2), 24 hours (P3)**
- Dedicated account manager
- Quarterly business reviews
- Custom integrations support

[Upgrade your plan](/billing/upgrade)
                """,
                tags=["sla", "support", "tiers", "pricing"],
                author="support@opendatagov.io",
                published=True,
                view_count=1523,
                helpful_votes=187,
                unhelpful_votes=12,
            ),
        ]

        for article in articles:
            db.add(article)

        await db.commit()

        print("✅ Created sample KB articles")

        # Search KB
        from fastapi.testclient import TestClient
        from support_portal.main import app

        client = TestClient(app)

        search_query = "connection pipeline"
        response = client.get(f"/api/v1/kb/search?query={search_query}")

        if response.status_code == 200:
            results = response.json()
            print(f"\n🔍 Search results for '{search_query}':")

            for article in results:
                print(f"\n   📄 {article['title']}")
                print(f"      Category: {article['category']}")
                print(f"      Views: {article['views']}")
                print(f"      Helpful: {article['helpful_votes']}")
                print(f"      Excerpt: {article['excerpt'][:100]}...")
        else:
            print(f"❌ Search failed: {response.text}")


async def example_4_submit_csat_survey():
    """Example 4: Submit CSAT survey after ticket resolution."""
    print("\n=== Example 4: Submitting CSAT Survey ===\n")

    ticket_id = await example_1_create_critical_ticket()

    if not ticket_id:
        print("⚠️  No ticket created, skipping example 4")
        return

    async with get_async_session() as db:
        sla_manager = SLAManager(db)

        # Mark ticket as resolved
        print("✅ Resolving ticket...")
        await sla_manager.record_resolution(ticket_id)

        # Submit CSAT survey
        from fastapi.testclient import TestClient
        from support_portal.main import app

        client = TestClient(app)

        rating = 5
        feedback = (
            "Excellent support! Team responded quickly and resolved"
            " the issue in under 2 hours. Very impressed with the expertise."
        )

        response = client.post(
            f"/api/v1/tickets/{ticket_id}/csat",
            params={"rating": rating, "feedback": feedback},
            headers={"Authorization": "Bearer fake_token"},
        )

        if response.status_code == 201:
            print(f"⭐ Submitted CSAT: {rating}/5")
            print(f"💬 Feedback: {feedback}")

            # Get overall CSAT metrics
            metrics_response = client.get("/api/v1/csat/metrics?days=30")
            if metrics_response.status_code == 200:
                metrics = metrics_response.json()
                print("\n📊 Overall CSAT Metrics (Last 30 days):")
                print(f"   Average Rating: {metrics['average_rating']}/5")
                print(f"   CSAT Score: {metrics['csat_score']}%")
                print(f"   Total Responses: {metrics['total_responses']}")


async def example_5_zendesk_integration():
    """Example 5: Sync tickets with Zendesk."""
    print("\n=== Example 5: Zendesk Integration ===\n")

    # Initialize Zendesk client
    zendesk = ZendeskClient(
        subdomain="opendatagov",
        email="support@opendatagov.io",
        api_token="your_zendesk_api_token",
    )

    ticket_id = await example_1_create_critical_ticket()

    if not ticket_id:
        print("⚠️  No ticket created, skipping example 5")
        return

    async with get_async_session() as db:
        from sqlalchemy import select
        from support_portal.models import TicketRow

        result = await db.execute(select(TicketRow).where(TicketRow.ticket_id == ticket_id))
        ticket = result.scalars().first()

        if not ticket:
            print("❌ Ticket not found")
            return

        # Sync to Zendesk
        print("🔄 Syncing ticket to Zendesk...")

        try:
            zendesk_id = await zendesk.sync_ticket_to_zendesk(ticket, db)
            print(f"✅ Ticket synced to Zendesk: {zendesk_id}")

            # Sync back from Zendesk
            print("🔄 Syncing updates from Zendesk...")
            updated_ticket = await zendesk.sync_ticket_from_zendesk(zendesk_id, db)

            if updated_ticket:
                print("✅ Ticket updated from Zendesk")
                print(f"   Status: {updated_ticket.status}")
                print(f"   Priority: {updated_ticket.priority}")

        except Exception as e:
            print(f"⚠️  Zendesk sync skipped (demo mode): {e}")


async def example_6_sla_monitoring():
    """Example 6: Monitor tickets approaching SLA breach."""
    print("\n=== Example 6: SLA Breach Monitoring ===\n")

    async with get_async_session() as db:
        sla_manager = SLAManager(db)

        # Get tickets at risk
        at_risk_tickets = await sla_manager.monitor_sla_breaches()

        print(f"🚨 Tickets Approaching SLA Breach: {len(at_risk_tickets)}\n")

        for ticket_info in at_risk_tickets:
            print(f"   Ticket: {ticket_info['ticket_id']}")
            print(f"   Subject: {ticket_info['subject']}")
            print(f"   Priority: {ticket_info['priority']}")
            print(f"   SLA Elapsed: {ticket_info['sla_elapsed_pct']:.1f}%")
            print(f"   Response Due: {ticket_info['response_target']}")

            if ticket_info["escalation_actions"]:
                print("   🚨 Escalations:")
                for action in ticket_info["escalation_actions"]:
                    print(f"      - {action}")

            print()


async def main():
    """Run all examples."""
    print("=" * 60)
    print("OpenDataGov Support Portal - Examples")
    print("=" * 60)

    await example_1_create_critical_ticket()
    await example_2_add_comments_and_track_sla()
    await example_3_search_knowledge_base()
    await example_4_submit_csat_survey()
    await example_5_zendesk_integration()
    await example_6_sla_monitoring()

    print("\n" + "=" * 60)
    print("✅ All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
