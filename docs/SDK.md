# Python SDK Guide

## Overview

The OpenDataGov Python SDK (`odg-sdk`) provides a Pythonic interface to all OpenDataGov REST and GraphQL APIs. It handles authentication, error handling, and provides type-safe models for all API resources.

## Installation

```bash
pip install odg-sdk
```

## Quick Start

```python
from odg_sdk import OpenDataGovClient

# Initialize client
async with OpenDataGovClient("http://localhost:8000") as client:
    # Create a governance decision
    decision = await client.decisions.create(
        decision_type="data_promotion",
        title="Promote sales to Gold",
        description="Quality gates passed",
        domain_id="finance",
        created_by="user-1"
    )

    print(f"Decision created: {decision.id}")
    print(f"Status: {decision.status}")
```

## Client Initialization

### Basic Usage

```python
from odg_sdk import OpenDataGovClient

client = OpenDataGovClient("http://localhost:8000")

# ... use client ...

# Close when done
await client.close()
```

### With Authentication

```python
client = OpenDataGovClient(
    base_url="https://api.opendatagov.com",
    api_key="sk_your_api_key_here",
    timeout=30.0  # Request timeout in seconds
)
```

### As Context Manager (Recommended)

```python
async with OpenDataGovClient("http://localhost:8000", api_key="sk_key") as client:
    # Client automatically closes on exit
    decision = await client.decisions.get(decision_id)
```

## API Resources

The SDK organizes APIs into resource managers accessible via the client:

| Resource  | Access             | Purpose                            |
| --------- | ------------------ | ---------------------------------- |
| Decisions | `client.decisions` | Governance decisions and approvals |
| Datasets  | `client.datasets`  | Dataset metadata and lineage       |
| Quality   | `client.quality`   | Data quality validation            |
| Access    | `client.access`    | Access request management          |

## Decisions Resource

### Create Decision

```python
decision = await client.decisions.create(
    decision_type="data_promotion",
    title="Promote sales dataset to Gold",
    description="All quality gates passed with score 0.98",
    domain_id="finance",
    created_by="engineer-1",
    metadata={
        "source_layer": "silver",
        "target_layer": "gold",
        "quality_score": 0.98
    }
)

print(decision.id)  # UUID
print(decision.status)  # "pending"
```

### Get Decision

```python
decision = await client.decisions.get("123e4567-e89b-12d3-a456-426614174000")

print(f"Title: {decision.title}")
print(f"Status: {decision.status}")
print(f"Domain: {decision.domain_id}")
```

### List Decisions

```python
# List all decisions
decisions = await client.decisions.list()

# Filter by domain and status
decisions = await client.decisions.list(
    domain_id="finance",
    status="pending",
    limit=10,
    offset=0
)

for decision in decisions:
    print(f"- {decision.title} ({decision.status})")
```

### Submit Decision for Approval

```python
decision = await client.decisions.submit(
    decision_id="123e4567...",
    actor_id="engineer-1"
)

print(f"Submitted, status: {decision.status}")
```

### Approve/Reject Decision

```python
# Approve
decision = await client.decisions.approve(
    decision_id="123e4567...",
    voter_id="data-owner-1",
    vote="approve",
    comment="Quality metrics look excellent"
)

# Reject
decision = await client.decisions.approve(
    decision_id="123e4567...",
    voter_id="compliance-officer",
    vote="reject",
    comment="Missing compliance documentation"
)
```

### Exercise Veto

```python
decision = await client.decisions.veto(
    decision_id="123e4567...",
    vetoer_id="security-admin",
    reason="Security vulnerability detected in dataset"
)

print(f"Vetoed, status: {decision.status}")
```

## Datasets Resource

### Get Dataset

```python
# Basic dataset info
dataset = await client.datasets.get("gold.customers")

# With lineage
dataset = await client.datasets.get("gold.customers", include_lineage=True)

print(f"Name: {dataset['name']}")
print(f"Quality Score: {dataset['qualityScore']}")
print(f"Upstream: {len(dataset.get('upstreamLineage', []))} datasets")
```

### List Datasets

```python
datasets = await client.datasets.list(
    domain_id="finance",
    layer="gold",
    classification="sensitive",
    limit=50
)

for ds in datasets:
    print(f"- {ds['name']} ({ds['layer']}) - Quality: {ds.get('qualityScore', 'N/A')}")
```

### Get Lineage Graph

```python
lineage = await client.datasets.get_lineage(
    dataset_id="gold.sales",
    depth=5  # How many levels to traverse
)

print(f"Nodes: {len(lineage['nodes'])}")
print(f"Edges: {len(lineage['edges'])}")

# Process nodes
for node in lineage['nodes']:
    print(f"  {node['id']} ({node['layer']})")

# Process edges
for edge in lineage['edges']:
    print(f"  {edge['from']} -> {edge['to']}")
```

### Search Datasets

```python
results = await client.datasets.search(
    query="customer",
    domain="crm",
    layer="gold",
    classification="sensitive",
    limit=20
)

for r in results:
    print(f"- {r['dataset_id']}: {r['name']}")
```

## Quality Resource

### Validate Dataset

```python
report = await client.quality.validate(
    dataset_id="gold.sales",
    layer="gold",
    expectation_suite_names=["gold_suite", "pii_checks"]
)

print(f"Validation: {'PASSED' if report['success'] else 'FAILED'}")
print(f"Overall Score: {report['overall_score']}")

for dim in report.get('dimensions', []):
    print(f"  {dim['dimension_name']}: {dim['score']}")
```

### Get Quality Report

```python
report = await client.quality.get_report("gold.customers")

print(f"Overall Score: {report['overallScore']}")
print(f"Validated At: {report['validatedAt']}")

# Check dimensions
for dim in report['dimensions']:
    print(f"  {dim['name']}: {dim['score']} ({dim['status']})")

# Check expectation results
for result in report['expectationResults']:
    if not result['success']:
        print(f"  FAILED: {result['expectationType']}")
```

## Access Request Resource

### Create Access Request

```python
request = await client.access.create(
    dataset_id="gold.customers",
    requester_id="analyst-1",
    purpose="Q1 2024 revenue analysis for board presentation",
    duration_days=30,
    justification="Need customer data to generate quarterly revenue report"
)

print(f"Request ID: {request.request_id}")
print(f"Status: {request.status}")

if request.decision_id:
    print(f"Decision ID: {request.decision_id}")
```

### Get Access Request

```python
request = await client.access.get("123e4567-e89b-12d3-a456-426614174000")

print(f"Dataset: {request.dataset_id}")
print(f"Requester: {request.requester_id}")
print(f"Status: {request.status}")
print(f"Purpose: {request.purpose}")
```

## GraphQL Queries

Execute custom GraphQL queries for complex data needs:

### Basic Query

```python
result = await client.graphql("""
    query GetDecision($id: UUID!) {
        decision(id: $id) {
            id
            title
            status
            approvers {
                userId
                vote
                comment
            }
        }
    }
""", {"id": "123e4567-e89b-12d3-a456-426614174000"})

decision = result["decision"]
print(f"Title: {decision['title']}")

for approver in decision['approvers']:
    print(f"  {approver['userId']}: {approver['vote']}")
```

### Complex Lineage Query

```python
result = await client.graphql("""
    query GetCompleteContext($datasetId: ID!) {
        dataset(id: $datasetId) {
            name
            qualityScore
            upstreamLineage {
                id
                name
                layer
                qualityScore
            }
            downstreamLineage {
                id
                name
                layer
            }
            decisions {
                id
                title
                status
                createdAt
            }
        }
    }
""", {"datasetId": "gold.sales"})

dataset = result["dataset"]
print(f"Dataset: {dataset['name']}")
print(f"Upstream: {len(dataset['upstreamLineage'])} datasets")
print(f"Downstream: {len(dataset['downstreamLineage'])} datasets")
print(f"Related Decisions: {len(dataset['decisions'])}")
```

## Error Handling

The SDK provides specific exception types for different error scenarios:

```python
from odg_sdk import (
    ODGError,
    ODGAPIError,
    ODGAuthenticationError,
    ODGNotFoundError,
    ODGValidationError,
    ODGConnectionError,
)

try:
    decision = await client.decisions.get("invalid-uuid")

except ODGNotFoundError as e:
    print(f"Decision not found: {e}")
    print(f"Status code: {e.status_code}")

except ODGAuthenticationError as e:
    print(f"Authentication failed: {e}")
    print("Check your API key")

except ODGValidationError as e:
    print(f"Validation error: {e}")
    if e.response_data:
        print(f"Details: {e.response_data}")

except ODGConnectionError as e:
    print(f"Connection failed: {e}")
    print("Check if OpenDataGov is running")

except ODGAPIError as e:
    print(f"API error: {e}")
    print(f"Status: {e.status_code}")

except ODGError as e:
    print(f"OpenDataGov error: {e}")
```

## Complete Examples

### Promote Dataset Through Governance

```python
from odg_sdk import OpenDataGovClient

async def promote_dataset_to_gold(dataset_id: str, created_by: str):
    """Complete workflow to promote a dataset to Gold layer."""

    async with OpenDataGovClient("http://localhost:8000") as client:
        # 1. Validate quality
        print("Validating quality...")
        report = await client.quality.validate(
            dataset_id=dataset_id,
            layer="silver",
            expectation_suite_names=["silver_to_gold_suite"]
        )

        if not report["success"]:
            print(f"Quality validation failed: {report['overall_score']}")
            return

        print(f"Quality validation passed: {report['overall_score']}")

        # 2. Create promotion decision
        print("Creating governance decision...")
        decision = await client.decisions.create(
            decision_type="data_promotion",
            title=f"Promote {dataset_id} to Gold",
            description=f"Quality score: {report['overall_score']}",
            domain_id="finance",
            created_by=created_by,
            metadata={
                "source_layer": "silver",
                "target_layer": "gold",
                "quality_score": report["overall_score"]
            }
        )

        print(f"Decision created: {decision.id}")

        # 3. Submit for approval
        print("Submitting for approval...")
        decision = await client.decisions.submit(decision.id, created_by)

        print(f"Decision status: {decision.status}")
        return decision.id

# Run
import asyncio
decision_id = asyncio.run(promote_dataset_to_gold("silver.sales", "engineer-1"))
```

### Request and Track Dataset Access

```python
async def request_dataset_access(
    dataset_id: str,
    requester_id: str,
    purpose: str
):
    """Request access and monitor approval status."""

    async with OpenDataGovClient("http://localhost:8000") as client:
        # Create access request
        request = await client.access.create(
            dataset_id=dataset_id,
            requester_id=requester_id,
            purpose=purpose,
            duration_days=30
        )

        print(f"Access request created: {request.request_id}")

        if not request.decision_id:
            print("No approval required - access granted immediately")
            return

        # Check decision status
        decision = await client.decisions.get(request.decision_id)

        print(f"Approval status: {decision.status}")
        print(f"Approvers:")

        # This would be empty initially - need to poll or use webhooks
        for approver in getattr(decision, 'approvers', []):
            print(f"  {approver.user_id} ({approver.role}): {approver.vote}")

# Run
asyncio.run(request_dataset_access(
    "gold.customers",
    "analyst-1",
    "Q1 2024 revenue analysis"
))
```

## Best Practices

### 1. Use Context Managers

Always use `async with` to ensure proper cleanup:

```python
# Good
async with OpenDataGovClient(url) as client:
    await client.decisions.list()

# Not recommended
client = OpenDataGovClient(url)
await client.decisions.list()
await client.close()  # Easy to forget!
```

### 2. Handle Errors Appropriately

```python
from odg_sdk import ODGNotFoundError, ODGValidationError

try:
    decision = await client.decisions.get(decision_id)
except ODGNotFoundError:
    # Decision doesn't exist - maybe create it?
    decision = await client.decisions.create(...)
except ODGValidationError as e:
    # Invalid data - log and alert
    logger.error(f"Validation failed: {e.response_data}")
    raise
```

### 3. Batch Operations

```python
# Get multiple decisions in parallel
import asyncio

decision_ids = ["id1", "id2", "id3"]

async with OpenDataGovClient(url) as client:
    tasks = [client.decisions.get(id) for id in decision_ids]
    decisions = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(decisions):
        if isinstance(result, Exception):
            print(f"Failed to get {decision_ids[i]}: {result}")
        else:
            print(f"Got decision: {result.title}")
```

### 4. Use GraphQL for Complex Queries

When you need nested data, use GraphQL to avoid multiple round trips:

```python
# Instead of this (N+1 queries)
dataset = await client.datasets.get(dataset_id)
lineage = await client.datasets.get_lineage(dataset_id)
report = await client.quality.get_report(dataset_id)

# Do this (single query)
result = await client.graphql("""
    query GetAll($id: ID!) {
        dataset(id: $id) {
            name
            upstreamLineage { id name }
            downstreamLineage { id name }
        }
        qualityReport(datasetId: $id) {
            overallScore
            dimensions { name score }
        }
    }
""", {"id": dataset_id})
```

## Configuration

### Environment Variables

The SDK respects these environment variables:

```bash
export ODG_API_URL=http://localhost:8000
export ODG_API_KEY=sk_your_key_here
export ODG_TIMEOUT=30
```

### Timeouts

Customize request timeouts:

```python
# Global timeout
client = OpenDataGovClient(url, timeout=60.0)

# Per-request timeout (not currently supported, use global)
```

## Testing

Mock the SDK in your tests:

```python
from unittest.mock import AsyncMock, MagicMock
from odg_sdk import OpenDataGovClient

def test_my_function():
    client = MagicMock(spec=OpenDataGovClient)
    client.decisions.create = AsyncMock(return_value=Mock(
        id="123",
        status="pending"
    ))

    # Test your code that uses the client
    result = await my_function(client)

    assert client.decisions.create.called
```

## Troubleshooting

### Import Errors

```python
# If you see "No module named 'odg_sdk'"
pip install --upgrade odg-sdk
```

### Connection Refused

```python
# Verify OpenDataGov is running
import httpx
response = httpx.get("http://localhost:8000/health")
print(response.json())  # Should be {"status": "ok"}
```

### GraphQL Errors

```python
# GraphQL errors are raised as ODGAPIError
try:
    result = await client.graphql("query { invalid }")
except ODGAPIError as e:
    print(f"GraphQL error: {e}")
    if e.response_data and "errors" in e.response_data:
        for error in e.response_data["errors"]:
            print(f"  - {error['message']}")
```

## API Reference

Full API documentation available at:

- [GraphQL API Guide](API_GRAPHQL.md)
- [gRPC API Guide](API_GRPC.md)
- [REST API Docs](http://localhost:8000/docs) (when running locally)

## Source Code

GitHub: https://github.com/opendatagov/opendatagov/tree/main/libs/python/odg-sdk
