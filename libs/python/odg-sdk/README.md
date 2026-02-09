# OpenDataGov Python SDK

Official Python client for OpenDataGov REST and GraphQL APIs.

## Installation

```bash
pip install odg-sdk
```

## Quick Start

```python
from odg_sdk import OpenDataGovClient

# Initialize client
client = OpenDataGovClient("http://localhost:8000")

# Create a governance decision
decision = await client.decisions.create(
    decision_type="data_promotion",
    title="Promote sales dataset to Gold",
    description="Quality gates passed",
    domain_id="finance",
    created_by="user-1"
)

print(f"Decision created: {decision.id}")

# List decisions
decisions = await client.decisions.list(domain_id="finance", status="pending")
for d in decisions:
    print(f"- {d.title} ({d.status})")

# Search datasets
datasets = await client.datasets.search("customer", domain="crm")
for ds in datasets:
    print(f"- {ds['name']} ({ds['layer']})")

# Request dataset access
access_request = await client.access.create(
    dataset_id="gold.customers",
    requester_id="analyst-1",
    purpose="Q1 revenue analysis",
    duration_days=30
)

# Close client when done
await client.close()
```

## Using Context Manager

```python
async with OpenDataGovClient("http://localhost:8000") as client:
    decision = await client.decisions.get("123e4567-e89b-12d3-a456-426614174000")
    print(decision.title)
```

## Authentication

```python
# With API key
client = OpenDataGovClient(
    "https://api.opendatagov.com",
    api_key="sk_your_api_key_here"
)
```

## GraphQL Queries

```python
# Execute custom GraphQL queries
result = await client.graphql("""
    query GetDatasetWithLineage($id: ID!) {
        dataset(id: $id) {
            name
            qualityScore
            upstreamLineage {
                name
            }
        }
    }
""", {"id": "gold.sales"})

print(result["dataset"]["name"])
```

## API Resources

### Decisions

```python
# Create decision
decision = await client.decisions.create(
    decision_type="data_promotion",
    title="Promote to Gold",
    description="Quality checks passed",
    domain_id="finance",
    created_by="user-1"
)

# Get decision
decision = await client.decisions.get(decision_id)

# List decisions
decisions = await client.decisions.list(
    domain_id="finance",
    status="pending",
    limit=10
)

# Submit for approval
decision = await client.decisions.submit(decision_id, actor_id="user-1")

# Approve decision
decision = await client.decisions.approve(
    decision_id,
    voter_id="user-1",
    vote="approve",
    comment="Looks good"
)

# Exercise veto
decision = await client.decisions.veto(
    decision_id,
    vetoer_id="admin",
    reason="Security concerns"
)
```

### Datasets

```python
# Get dataset
dataset = await client.datasets.get("gold.customers")

# Get dataset with lineage
dataset = await client.datasets.get("gold.customers", include_lineage=True)

# List datasets
datasets = await client.datasets.list(
    layer="gold",
    classification="sensitive",
    limit=50
)

# Get lineage graph
lineage = await client.datasets.get_lineage("gold.sales", depth=5)
print(f"Nodes: {len(lineage['nodes'])}, Edges: {len(lineage['edges'])}")

# Search datasets
results = await client.datasets.search(
    "customer",
    domain="crm",
    layer="gold"
)
```

### Quality

```python
# Validate dataset
report = await client.quality.validate(
    dataset_id="gold.sales",
    layer="gold",
    expectation_suite_names=["gold_suite"]
)

# Get quality report
report = await client.quality.get_report("gold.customers")
print(f"Overall score: {report['overallScore']}")
```

### Access Requests

```python
# Request access
request = await client.access.create(
    dataset_id="gold.customers",
    requester_id="analyst-1",
    purpose="Revenue analysis for Q1 2024",
    duration_days=30,
    justification="Need to generate quarterly report"
)

# Get access request status
request = await client.access.get(request_id)
print(f"Status: {request.status}")
```

## Error Handling

```python
from odg_sdk import (
    ODGAPIError,
    ODGAuthenticationError,
    ODGNotFoundError,
    ODGValidationError,
)

try:
    decision = await client.decisions.get("invalid-id")
except ODGNotFoundError as e:
    print(f"Decision not found: {e}")
except ODGAuthenticationError as e:
    print(f"Authentication failed: {e}")
except ODGValidationError as e:
    print(f"Validation error: {e}")
except ODGAPIError as e:
    print(f"API error: {e} (status: {e.status_code})")
```

## Configuration

```python
client = OpenDataGovClient(
    base_url="http://localhost:8000",
    api_key="sk_your_key",  # Optional
    timeout=30.0,  # Request timeout in seconds
)
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=odg_sdk --cov-report=term-missing

# Lint code
ruff check src/

# Type checking
mypy src/
```

## License

Apache-2.0
