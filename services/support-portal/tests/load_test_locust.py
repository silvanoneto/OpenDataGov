"""Load testing with Locust - Phase 5.

Simulates 1000 concurrent users creating tickets, searching KB, submitting CSAT.

Usage:
    locust -f load_test_locust.py --host=http://localhost:8000 --users=1000 --spawn-rate=50
"""

import random
import string

from locust import between, events, task
from locust.contrib.fasthttp import FastHttpUser


# Test data generators
def random_email():
    """Generate random customer email."""
    domains = ["gmail.com", "outlook.com", "enterprise.com", "startup.io"]
    username = "".join(random.choices(string.ascii_lowercase, k=10))
    return f"{username}@{random.choice(domains)}"


def random_ticket_subject():
    """Generate realistic ticket subjects."""
    issues = [
        "Cannot access governance dashboard",
        "Data quality check failing",
        "Integration with DataHub not working",
        "Feature request: Add custom fields",
        "Bug: API rate limiting too aggressive",
        "Question about lineage tracking",
        "Performance issues with large datasets",
        "Authentication error with SSO",
        "Need help with policy configuration",
        "Catalog search returning no results",
    ]
    return random.choice(issues)


def random_description():
    """Generate ticket description."""
    templates = [
        "I'm experiencing issues with {feature}. Steps to reproduce:\n1. {step1}\n2. {step2}\n3. Error occurs",
        "We need help configuring {feature} for our {env} environment. Current setup: {setup}",
        "Bug report: {feature} is not working as expected. Expected: {expected}. Actual: {actual}",
        "Feature request: It would be great if {feature} could {action}. Use case: {usecase}",
        "Performance issue: {feature} is very slow when {condition}. Takes over {time} to complete.",
    ]

    return random.choice(templates).format(
        feature=random.choice(["data catalog", "governance engine", "quality checks", "lineage tracking"]),
        step1="Navigate to dashboard",
        step2="Click on configuration",
        env=random.choice(["production", "staging", "development"]),
        setup="5 node cluster, 100TB data",
        expected="Successful completion",
        actual="Timeout after 30s",
        action="support bulk operations",
        usecase="Processing 1M+ records",
        condition="handling large datasets",
        time="5 minutes",
    )


class SupportPortalUser(FastHttpUser):
    """Simulates customer using support portal."""

    wait_time = between(2, 5)  # Wait 2-5 seconds between tasks
    host = "http://localhost:8000"

    def on_start(self):
        """Initialize user session."""
        self.customer_email = random_email()
        self.customer_name = f"Test User {random.randint(1000, 9999)}"
        self.ticket_ids = []

    @task(10)
    def create_ticket(self):
        """Create new support ticket (most common action)."""
        priority = random.choices(
            ["P1_CRITICAL", "P2_HIGH", "P3_NORMAL", "P4_LOW"],
            weights=[5, 15, 60, 20],  # Realistic distribution
        )[0]

        payload = {
            "subject": random_ticket_subject(),
            "description": random_description(),
            "priority": priority,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "product_area": random.choice(["CATALOG", "GOVERNANCE", "QUALITY", "LINEAGE"]),
        }

        with self.client.post("/api/v1/tickets", json=payload, catch_response=True) as response:
            if response.status_code == 201:
                ticket_id = response.json().get("ticket_id")
                self.ticket_ids.append(ticket_id)
                response.success()
            else:
                response.failure(f"Failed to create ticket: {response.status_code}")

    @task(8)
    def search_knowledge_base(self):
        """Search KB for answers (common self-service action)."""
        queries = [
            "how to configure",
            "api error",
            "authentication",
            "data quality",
            "performance",
            "integration",
            "catalog",
            "governance",
            "lineage",
            "troubleshooting",
        ]

        query = random.choice(queries)

        with self.client.get(f"/api/v1/kb/search?q={query}", catch_response=True) as response:
            if response.status_code == 200:
                results = response.json().get("results", [])
                response.success()
                # Simulate reading article
                if results:
                    article_id = results[0]["article_id"]
                    self.view_article(article_id)
            else:
                response.failure(f"Search failed: {response.status_code}")

    def view_article(self, article_id):
        """View KB article."""
        self.client.get(f"/api/v1/kb/articles/{article_id}")

    @task(5)
    def view_my_tickets(self):
        """View customer's tickets."""
        with self.client.get(f"/api/v1/tickets?customer_email={self.customer_email}", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to list tickets: {response.status_code}")

    @task(3)
    def add_comment(self):
        """Add comment to ticket."""
        if not self.ticket_ids:
            return  # No tickets yet

        ticket_id = random.choice(self.ticket_ids)
        comment_text = random.choice(
            [
                "Any update on this?",
                "Still experiencing the issue",
                "This is now blocking our production deployment",
                "Thanks for the quick response!",
                "I tried the suggested solution but it didn't work",
                "Can we schedule a call to discuss this?",
            ]
        )

        payload = {"ticket_id": ticket_id, "author": self.customer_email, "content": comment_text, "is_internal": False}

        with self.client.post("/api/v1/comments", json=payload, catch_response=True) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(f"Failed to add comment: {response.status_code}")

    @task(2)
    def submit_csat(self):
        """Submit CSAT survey (after ticket resolution)."""
        if not self.ticket_ids:
            return

        ticket_id = random.choice(self.ticket_ids)
        rating = random.choices(
            [1, 2, 3, 4, 5],
            weights=[5, 10, 20, 40, 25],  # Realistic rating distribution
        )[0]

        feedback_templates = {
            1: ["Very disappointed", "Issue not resolved", "Poor support"],
            2: ["Slow response", "Took too long", "Confusing answer"],
            3: ["Average experience", "Got the answer eventually"],
            4: ["Good support", "Helpful response", "Quick resolution"],
            5: ["Excellent!", "Very helpful", "Outstanding support", "Resolved quickly"],
        }

        payload = {"ticket_id": ticket_id, "rating": rating, "feedback": random.choice(feedback_templates[rating])}

        with self.client.post("/api/v1/csat/submit", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to submit CSAT: {response.status_code}")


class AgentUser(FastHttpUser):
    """Simulates support agent handling tickets."""

    wait_time = between(5, 15)  # Agents take longer per action
    host = "http://localhost:8000"

    def on_start(self):
        """Initialize agent session."""
        self.agent_email = f"agent{random.randint(1, 20)}@opendatagov.io"
        self.agent_name = f"Agent {random.randint(1, 20)}"

    @task(10)
    def view_queue(self):
        """View open tickets queue."""
        with self.client.get("/api/v1/tickets?status=OPEN&status=NEW&limit=50", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to load queue: {response.status_code}")

    @task(8)
    def respond_to_ticket(self):
        """Respond to customer ticket."""
        # First get a ticket to respond to
        response = self.client.get("/api/v1/tickets?status=OPEN&limit=1")
        if response.status_code != 200 or not response.json().get("tickets"):
            return

        ticket = response.json()["tickets"][0]
        ticket_id = ticket["ticket_id"]

        # Add response comment
        response_templates = [
            "Thank you for contacting OpenDataGov support. I've reviewed your issue and...",
            "I understand you're experiencing issues with {feature}. Let me help you troubleshoot...",
            "This is a known issue that our engineering team is working on. ETA: {eta}",
            "I've escalated this to our L2 support team. They will follow up within {sla}",
            "Great news! We've identified the root cause. The fix will be deployed in version {version}",
        ]

        comment = random.choice(response_templates).format(
            feature="data catalog", eta="next week", sla="4 hours", version="v0.5.0"
        )

        payload = {"ticket_id": ticket_id, "author": self.agent_email, "content": comment, "is_internal": False}

        with self.client.post("/api/v1/comments", json=payload, catch_response=True) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(f"Failed to respond: {response.status_code}")

    @task(5)
    def update_ticket_status(self):
        """Update ticket status."""
        response = self.client.get("/api/v1/tickets?status=OPEN&limit=1")
        if response.status_code != 200 or not response.json().get("tickets"):
            return

        ticket = response.json()["tickets"][0]
        ticket_id = ticket["ticket_id"]

        new_status = random.choice(["IN_PROGRESS", "WAITING_ON_CUSTOMER", "SOLVED"])

        payload = {"status": new_status}

        with self.client.patch(f"/api/v1/tickets/{ticket_id}", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to update status: {response.status_code}")

    @task(3)
    def check_sla_compliance(self):
        """Check SLA compliance for tickets."""
        response = self.client.get("/api/v1/tickets?status=OPEN&limit=10")
        if response.status_code != 200:
            return

        tickets = response.json().get("tickets", [])
        for ticket in tickets[:3]:  # Check first 3
            ticket_id = ticket["ticket_id"]
            self.client.get(f"/api/v1/sla/compliance/{ticket_id}")

    @task(2)
    def search_kb_for_customer(self):
        """Search KB to find solution for customer."""
        queries = ["error", "how to", "configuration", "troubleshoot", "fix"]
        query = random.choice(queries)
        self.client.get(f"/api/v1/kb/search?q={query}")


# Custom events for metrics
@events.init_command_line_parser.add_listener
def _(parser):
    """Add custom command line args."""
    parser.add_argument("--customer-ratio", type=float, default=0.8, help="Ratio of customers to agents (default 0.8)")


# Metrics tracking
response_times = {"create_ticket": [], "search_kb": [], "view_queue": []}


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track response times for critical endpoints."""
    if exception:
        return

    if "/tickets" in name and request_type == "POST":
        response_times["create_ticket"].append(response_time)
    elif "/kb/search" in name:
        response_times["search_kb"].append(response_time)
    elif "/tickets" in name and "status=OPEN" in name:
        response_times["view_queue"].append(response_time)


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Print summary stats."""
    print("\n" + "=" * 60)
    print("LOAD TEST SUMMARY")
    print("=" * 60)

    for endpoint, times in response_times.items():
        if times:
            avg = sum(times) / len(times)
            p95 = sorted(times)[int(len(times) * 0.95)] if times else 0
            print(f"\n{endpoint}:")
            print(f"  Requests: {len(times)}")
            print(f"  Avg response time: {avg:.2f}ms")
            print(f"  P95 response time: {p95:.2f}ms")

    print("\n" + "=" * 60)
