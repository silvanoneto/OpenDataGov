# GraphQL API Reference

## Overview

OpenDataGov provides a GraphQL API for efficient metadata queries, lineage traversal, and complex filtering. The GraphQL endpoint reduces overfetching and allows clients to request exactly the data they need in a single query.

## Endpoint

- **URL**: `/api/v1/graphql`
- **Method**: `POST` (queries and mutations)
- **Playground**: Interactive GraphiQL interface available at `/api/v1/graphql` in development

## Authentication

GraphQL requests use the same authentication as REST APIs:

```bash
curl -X POST http://localhost:8000/api/v1/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"query": "{ __schema { types { name } } }"}'
```

## Schema Exploration

### Introspection Query

Get the full schema:

```graphql
query IntrospectionQuery {
  __schema {
    types {
      name
      kind
      description
    }
  }
}
```

## Core Queries

### 1. Decision Queries

#### Get Single Decision

```graphql
query GetDecision($id: UUID!) {
  decision(id: $id) {
    id
    decisionType
    title
    description
    status
    domainId
    createdBy
    createdAt
    metadata {
      sourceLayer
      targetLayer
      reason
    }
    approvers {
      userId
      role
      vote
      votedAt
      comment
    }
  }
}
```

**Variables**:

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000"
}
```

#### List Decisions with Filters

```graphql
query ListDecisions($domain: String, $status: String, $limit: Int) {
  decisions(domainId: $domain, status: $status, limit: $limit) {
    id
    title
    status
    decisionType
    domainId
    createdBy
    createdAt
  }
}
```

**Variables**:

```json
{
  "domain": "finance",
  "status": "pending",
  "limit": 10
}
```

### 2. Dataset Queries

#### Get Dataset with Lineage

```graphql
query GetDatasetWithLineage($id: ID!) {
  dataset(id: $id) {
    id
    name
    description
    classification
    layer
    qualityScore
    upstreamLineage {
      id
      name
      layer
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
      decisionType
      createdAt
    }
  }
}
```

**Variables**:

```json
{
  "id": "gold.customers"
}
```

#### List Datasets

```graphql
query ListDatasets($domain: String, $layer: String, $limit: Int) {
  datasets(domainId: $domain, layer: $layer, limit: $limit) {
    id
    name
    description
    classification
    layer
    qualityScore
    owner
    tags
    lastUpdated
  }
}
```

### 3. Lineage Graph

#### Get Complete Lineage Graph

```graphql
query GetLineageGraph($datasetId: ID!, $depth: Int = 3) {
  lineage(datasetId: $datasetId, depth: $depth) {
    nodes {
      id
      name
      type
      layer
      classification
    }
    edges {
      from
      to
      label
      transformationType
    }
  }
}
```

**Variables**:

```json
{
  "datasetId": "gold.sales",
  "depth": 5
}
```

### 4. Quality Report Queries

#### Get Quality Report

```graphql
query GetQualityReport($datasetId: ID!) {
  qualityReport(datasetId: $datasetId) {
    datasetId
    overallScore
    dimensions {
      name
      score
      status
      details
    }
    validatedAt
    validatedBy
    expectationResults {
      expectationType
      success
      observedValue
      details
    }
  }
}
```

## Advanced Queries

### Combined Query Example

Fetch decision with related dataset and quality information:

```graphql
query DecisionWithContext($decisionId: UUID!) {
  decision(id: $decisionId) {
    id
    title
    status
    metadata {
      targetDataset
    }
  }

  # Note: This requires the target dataset ID from the decision
  dataset(id: "gold.customers") {
    name
    qualityScore
    upstreamLineage {
      name
    }
  }
}
```

### Filtering and Pagination

```graphql
query PaginatedDecisions($offset: Int = 0, $limit: Int = 20, $status: String) {
  decisions(offset: $offset, limit: $limit, status: $status) {
    id
    title
    status
    createdAt
  }
}
```

## Mutations

(Future implementation - currently read-only)

Planned mutations:

```graphql
mutation CreateDecision($input: CreateDecisionInput!) {
  createDecision(input: $input) {
    id
    status
    createdAt
  }
}

mutation ApproveDecision($id: UUID!, $vote: VoteInput!) {
  approveDecision(id: $id, vote: $vote) {
    id
    status
    approvers {
      userId
      vote
    }
  }
}
```

## Error Handling

GraphQL returns errors in a structured format:

```json
{
  "errors": [
    {
      "message": "Decision not found",
      "locations": [{"line": 2, "column": 3}],
      "path": ["decision"],
      "extensions": {
        "code": "NOT_FOUND",
        "decisionId": "123e4567-e89b-12d3-a456-426614174000"
      }
    }
  ],
  "data": {
    "decision": null
  }
}
```

## Performance Best Practices

### 1. Request Only Needed Fields

❌ **Bad**: Request all fields

```graphql
query {
  decisions {
    id
    decisionType
    title
    description
    status
    domainId
    createdBy
    createdAt
    metadata { ... }
    approvers { ... }
    # ... many more fields
  }
}
```

✅ **Good**: Request only what you need

```graphql
query {
  decisions {
    id
    title
    status
    createdAt
  }
}
```

### 2. Use Fragments for Reusability

```graphql
fragment DecisionSummary on GovernanceDecisionGQL {
  id
  title
  status
  decisionType
  createdAt
}

query GetMultipleDecisions {
  pending: decisions(status: "pending") {
    ...DecisionSummary
  }
  approved: decisions(status: "approved") {
    ...DecisionSummary
  }
}
```

### 3. Limit Depth for Lineage Queries

```graphql
# Limit depth to avoid expensive recursive queries
query {
  lineage(datasetId: "gold.sales", depth: 3) {
    nodes { id name }
    edges { from to }
  }
}
```

## Client Examples

### Python (using `gql`)

```python
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

transport = RequestsHTTPTransport(
    url="http://localhost:8000/api/v1/graphql",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
)

client = Client(transport=transport, fetch_schema_from_transport=True)

query = gql("""
    query GetDecision($id: UUID!) {
        decision(id: $id) {
            id
            title
            status
        }
    }
""")

result = client.execute(query, variable_values={"id": "123e4567-e89b-12d3-a456-426614174000"})
print(result)
```

### JavaScript (using `graphql-request`)

```javascript
import { GraphQLClient, gql } from 'graphql-request'

const client = new GraphQLClient('http://localhost:8000/api/v1/graphql', {
  headers: {
    Authorization: 'Bearer YOUR_TOKEN',
  },
})

const query = gql`
  query GetDataset($id: ID!) {
    dataset(id: $id) {
      name
      qualityScore
      upstreamLineage {
        name
      }
    }
  }
`

const data = await client.request(query, { id: 'gold.customers' })
console.log(data)
```

### cURL

```bash
curl -X POST http://localhost:8000/api/v1/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "query GetDecision($id: UUID!) { decision(id: $id) { id title status } }",
    "variables": { "id": "123e4567-e89b-12d3-a456-426614174000" }
  }'
```

## Schema Types Reference

### GovernanceDecisionGQL

```graphql
type GovernanceDecisionGQL {
  id: UUID!
  decisionType: String!
  title: String!
  description: String!
  status: String!
  domainId: String!
  createdBy: String!
  createdAt: DateTime!
  updatedAt: DateTime
  metadata: PromotionMetadataGQL
  approvers: [DecisionApproverGQL!]!
}
```

### DatasetGQL

```graphql
type DatasetGQL {
  id: ID!
  name: String!
  description: String
  classification: String
  layer: String
  qualityScore: Float
  owner: String
  tags: [String!]
  lastUpdated: DateTime
  upstreamLineage: [DatasetGQL!]
  downstreamLineage: [DatasetGQL!]
  decisions: [GovernanceDecisionGQL!]
}
```

### QualityReportGQL

```graphql
type QualityReportGQL {
  datasetId: String!
  overallScore: Float!
  dimensions: [QualityDimensionGQL!]!
  validatedAt: DateTime!
  validatedBy: String
  expectationResults: [ExpectationResultGQL!]
}
```

## Comparison: GraphQL vs REST

| Feature            | GraphQL                           | REST                            |
| ------------------ | --------------------------------- | ------------------------------- |
| **Data Fetching**  | Single request for nested data    | Multiple requests (N+1 problem) |
| **Over-fetching**  | Request exact fields needed       | Often returns unnecessary data  |
| **Under-fetching** | Get all related data in one query | Need multiple endpoints         |
| **Versioning**     | No versioning needed (additive)   | Requires version management     |
| **Learning Curve** | Steeper (new paradigm)            | Familiar to most developers     |
| **Tooling**        | Excellent (GraphiQL, Apollo)      | Mature (Swagger, Postman)       |
| **Use Case**       | Complex queries, mobile apps      | Simple CRUD, webhooks           |

## Troubleshooting

### Query Timeout

If queries are timing out, reduce the depth or add pagination:

```graphql
query {
  decisions(limit: 10, offset: 0) {
    id
    title
  }
}
```

### N+1 Query Problem

GraphQL resolvers use DataLoader pattern to batch database queries and avoid N+1 issues. This is handled automatically by the implementation.

### Cache Headers

GraphQL responses include standard HTTP cache headers:

```
Cache-Control: public, max-age=300
ETag: "abc123"
```

## Further Reading

- [GraphQL Official Documentation](https://graphql.org/learn/)
- [Strawberry Documentation](https://strawberry.rocks/) (our GraphQL framework)
- [Best Practices](https://graphql.org/learn/best-practices/)
