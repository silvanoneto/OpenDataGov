# gRPC API Reference

## Overview

OpenDataGov provides gRPC APIs for high-performance inter-service communication and streaming use cases. gRPC uses Protocol Buffers for efficient serialization and supports bidirectional streaming.

## Why gRPC?

- **Performance**: Binary serialization (Protocol Buffers) is faster than JSON
- **Streaming**: Bidirectional streaming for real-time updates
- **Type Safety**: Strong typing with code generation
- **Inter-service**: Optimized for service-to-service communication
- **Language Support**: Generated clients in Python, Go, Java, etc.

## Service Endpoints

| Service               | Port     | Protocol Buffers Definition |
| --------------------- | -------- | --------------------------- |
| **GovernanceService** | `:50051` | `governance.proto`          |
| **CatalogService**    | `:50052` | `catalog.proto`             |
| **QualityService**    | `:50053` | `quality.proto`             |

## GovernanceService

**Endpoint**: `localhost:50051`

### Service Definition

```protobuf
service GovernanceService {
  rpc CreateDecision(CreateDecisionRequest) returns (GovernanceDecision);
  rpc GetDecision(GetDecisionRequest) returns (GovernanceDecision);
  rpc ListDecisions(ListDecisionsRequest) returns (ListDecisionsResponse);
  rpc CastVote(CastVoteRequest) returns (GovernanceDecision);
  rpc ExerciseVeto(ExerciseVetoRequest) returns (GovernanceDecision);
  rpc SubmitDecision(SubmitDecisionRequest) returns (GovernanceDecision);
  rpc StreamDecisions(StreamDecisionsRequest) returns (stream GovernanceDecision);
}
```

### Methods

#### CreateDecision

Create a new governance decision.

**Request**:

```protobuf
message CreateDecisionRequest {
  string decision_type = 1;
  string title = 2;
  string description = 3;
  string domain_id = 4;
  string created_by = 5;
  google.protobuf.Struct metadata = 6;
}
```

**Response**:

```protobuf
message GovernanceDecision {
  string id = 1;
  string decision_type = 2;
  string title = 3;
  string description = 4;
  string status = 5;
  string domain_id = 6;
  string created_by = 7;
  google.protobuf.Timestamp created_at = 8;
  google.protobuf.Timestamp updated_at = 9;
  google.protobuf.Struct metadata = 10;
  repeated DecisionApprover approvers = 11;
}
```

**Example (Python)**:

```python
import grpc
from odg_core.proto_gen import governance_pb2, governance_pb2_grpc
from google.protobuf.struct_pb2 import Struct

channel = grpc.insecure_channel('localhost:50051')
stub = governance_pb2_grpc.GovernanceServiceStub(channel)

metadata = Struct()
metadata.update({
    "source_layer": "silver",
    "target_layer": "gold",
    "reason": "Quality threshold met"
})

request = governance_pb2.CreateDecisionRequest(
    decision_type="data_promotion",
    title="Promote sales dataset to Gold",
    description="Sales data has passed all quality gates",
    domain_id="finance",
    created_by="user-123",
    metadata=metadata
)

response = stub.CreateDecision(request)
print(f"Decision created: {response.id}")
```

#### GetDecision

Retrieve a decision by ID.

**Request**:

```protobuf
message GetDecisionRequest {
  string decision_id = 1;
}
```

**Example (Python)**:

```python
request = governance_pb2.GetDecisionRequest(
    decision_id="123e4567-e89b-12d3-a456-426614174000"
)

response = stub.GetDecision(request)
print(f"Decision: {response.title}, Status: {response.status}")
```

#### ListDecisions

List decisions with optional filters.

**Request**:

```protobuf
message ListDecisionsRequest {
  string domain_id = 1;
  string status = 2;
  int32 limit = 3;
  int32 offset = 4;
}
```

**Response**:

```protobuf
message ListDecisionsResponse {
  repeated GovernanceDecision decisions = 1;
  int32 total_count = 2;
}
```

**Example (Python)**:

```python
request = governance_pb2.ListDecisionsRequest(
    domain_id="finance",
    status="pending",
    limit=10,
    offset=0
)

response = stub.ListDecisions(request)
for decision in response.decisions:
    print(f"- {decision.title} ({decision.status})")
```

#### StreamDecisions

Stream decision updates in real-time (server streaming).

**Example (Python)**:

```python
request = governance_pb2.StreamDecisionsRequest(
    domain_id="finance"
)

# Server streaming - receive updates as they happen
for decision in stub.StreamDecisions(request):
    print(f"Update: {decision.title} -> {decision.status}")
```

## CatalogService

**Endpoint**: `localhost:50052`

### Service Definition

```protobuf
service CatalogService {
  rpc GetDataset(GetDatasetRequest) returns (Dataset);
  rpc ListDatasets(ListDatasetsRequest) returns (ListDatasetsResponse);
  rpc GetLineage(GetLineageRequest) returns (LineageGraph);
  rpc RegisterDataset(RegisterDatasetRequest) returns (Dataset);
}
```

### Methods

#### GetDataset

Retrieve dataset metadata.

**Request**:

```protobuf
message GetDatasetRequest {
  string dataset_id = 1;
}
```

**Response**:

```protobuf
message Dataset {
  string id = 1;
  string name = 2;
  string description = 3;
  string classification = 4;
  string layer = 5;
  double quality_score = 6;
  string owner = 7;
  repeated string tags = 8;
  google.protobuf.Timestamp last_updated = 9;
}
```

**Example (Python)**:

```python
from odg_core.proto_gen import catalog_pb2, catalog_pb2_grpc

channel = grpc.insecure_channel('localhost:50052')
stub = catalog_pb2_grpc.CatalogServiceStub(channel)

request = catalog_pb2.GetDatasetRequest(dataset_id="gold.customers")
response = stub.GetDataset(request)
print(f"Dataset: {response.name}, Quality: {response.quality_score}")
```

#### GetLineage

Retrieve lineage graph for a dataset.

**Request**:

```protobuf
message GetLineageRequest {
  string dataset_id = 1;
  int32 depth = 2;  // How many levels to traverse
}
```

**Response**:

```protobuf
message LineageGraph {
  repeated LineageNode nodes = 1;
  repeated LineageEdge edges = 2;
}

message LineageNode {
  string id = 1;
  string name = 2;
  string type = 3;
  string layer = 4;
}

message LineageEdge {
  string from_id = 1;
  string to_id = 2;
  string label = 3;
}
```

**Example (Python)**:

```python
request = catalog_pb2.GetLineageRequest(
    dataset_id="gold.sales",
    depth=3
)

response = stub.GetLineage(request)
print(f"Nodes: {len(response.nodes)}, Edges: {len(response.edges)}")
for edge in response.edges:
    print(f"{edge.from_id} -> {edge.to_id} ({edge.label})")
```

## QualityService

**Endpoint**: `localhost:50053`

### Service Definition

```protobuf
service QualityService {
  rpc ValidateDataset(ValidationRequest) returns (ValidationReport);
  rpc GetQualityReport(GetQualityReportRequest) returns (QualityReport);
  rpc ListQualityReports(ListQualityReportsRequest) returns (ListQualityReportsResponse);
}
```

### Methods

#### ValidateDataset

Run quality validation on a dataset.

**Request**:

```protobuf
message ValidationRequest {
  string dataset_id = 1;
  string layer = 2;
  repeated string expectation_suite_names = 3;
}
```

**Response**:

```protobuf
message ValidationReport {
  string dataset_id = 1;
  bool success = 2;
  double overall_score = 3;
  repeated DimensionResult dimensions = 4;
  google.protobuf.Timestamp validated_at = 5;
}

message DimensionResult {
  string dimension_name = 1;
  double score = 2;
  string status = 3;
}
```

**Example (Python)**:

```python
from odg_core.proto_gen import quality_pb2, quality_pb2_grpc

channel = grpc.insecure_channel('localhost:50053')
stub = quality_pb2_grpc.QualityServiceStub(channel)

request = quality_pb2.ValidationRequest(
    dataset_id="gold.sales",
    layer="gold",
    expectation_suite_names=["gold_suite"]
)

response = stub.ValidateDataset(request)
print(f"Validation: {'PASSED' if response.success else 'FAILED'}")
print(f"Score: {response.overall_score}")
for dim in response.dimensions:
    print(f"  {dim.dimension_name}: {dim.score}")
```

## Authentication & Metadata

### JWT Authentication

Pass JWT token in gRPC metadata:

```python
import grpc

def auth_interceptor(token):
    def intercept(method, request, call_details):
        metadata = [('authorization', f'Bearer {token}')]
        return method(request, call_details._replace(metadata=metadata))
    return intercept

channel = grpc.insecure_channel('localhost:50051')
token = "your_jwt_token_here"

# Add interceptor to channel
intercepted_channel = grpc.intercept_channel(
    channel,
    grpc.UnaryUnaryClientInterceptor(auth_interceptor(token))
)

stub = governance_pb2_grpc.GovernanceServiceStub(intercepted_channel)
```

### OpenTelemetry Tracing

gRPC calls automatically propagate trace context:

```python
from opentelemetry import trace
from opentelemetry.instrumentation.grpc import GrpcInstrumentorClient

# Instrument gRPC client
GrpcInstrumentorClient().instrument()

# Traces are automatically propagated
with trace.get_tracer(__name__).start_as_current_span("create_decision"):
    response = stub.CreateDecision(request)
```

## Error Handling

gRPC uses status codes for errors:

```python
import grpc

try:
    response = stub.GetDecision(request)
except grpc.RpcError as e:
    print(f"Error: {e.code()}")
    print(f"Details: {e.details()}")

    if e.code() == grpc.StatusCode.NOT_FOUND:
        print("Decision not found")
    elif e.code() == grpc.StatusCode.PERMISSION_DENIED:
        print("Access denied")
    elif e.code() == grpc.StatusCode.INVALID_ARGUMENT:
        print("Invalid request")
```

### Common Status Codes

| Code                | Description         | Use Case                 |
| ------------------- | ------------------- | ------------------------ |
| `OK`                | Success             | Request completed        |
| `CANCELLED`         | Cancelled by client | Client timeout           |
| `INVALID_ARGUMENT`  | Invalid input       | Bad request data         |
| `NOT_FOUND`         | Resource not found  | Decision/dataset missing |
| `PERMISSION_DENIED` | Access denied       | Authorization failure    |
| `UNAVAILABLE`       | Service unavailable | Server down              |
| `INTERNAL`          | Internal error      | Server-side bug          |

## Performance Tuning

### Connection Pooling

Reuse gRPC channels:

```python
class GrpcClientPool:
    def __init__(self):
        self._channels = {}

    def get_channel(self, address):
        if address not in self._channels:
            self._channels[address] = grpc.insecure_channel(
                address,
                options=[
                    ('grpc.keepalive_time_ms', 10000),
                    ('grpc.keepalive_timeout_ms', 5000),
                    ('grpc.max_send_message_length', 10 * 1024 * 1024),
                    ('grpc.max_receive_message_length', 10 * 1024 * 1024),
                ]
            )
        return self._channels[address]

pool = GrpcClientPool()
channel = pool.get_channel('localhost:50051')
stub = governance_pb2_grpc.GovernanceServiceStub(channel)
```

### Streaming for Large Datasets

Use server streaming for large result sets:

```python
# Instead of returning all at once, stream results
request = governance_pb2.StreamDecisionsRequest(domain_id="finance")

count = 0
for decision in stub.StreamDecisions(request):
    process_decision(decision)
    count += 1
    if count % 100 == 0:
        print(f"Processed {count} decisions...")
```

## Client Code Generation

### Python

```bash
# Generate Python code from proto files
python -m grpc_tools.protoc \
  -I./libs/go/odg-proto/proto \
  --python_out=./libs/python/odg-core/src/odg_core/proto_gen \
  --grpc_python_out=./libs/python/odg-core/src/odg_core/proto_gen \
  ./libs/go/odg-proto/proto/*.proto
```

### Go

```bash
# Generate Go code
protoc \
  -I./libs/go/odg-proto/proto \
  --go_out=./libs/go/odg-proto/gen \
  --go-grpc_out=./libs/go/odg-proto/gen \
  ./libs/go/odg-proto/proto/*.proto
```

### JavaScript/TypeScript

```bash
# Generate JS/TS code
grpc_tools_node_protoc \
  --js_out=import_style=commonjs,binary:./client/src/proto \
  --grpc_out=grpc_js:./client/src/proto \
  --plugin=protoc-gen-grpc=$(which grpc_tools_node_protoc_plugin) \
  -I./libs/go/odg-proto/proto \
  ./libs/go/odg-proto/proto/*.proto
```

## Testing with grpcurl

### Install grpcurl

```bash
# macOS
brew install grpcurl

# Linux
go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest
```

### List Services

```bash
grpcurl -plaintext localhost:50051 list
```

Output:

```
governance.GovernanceService
grpc.reflection.v1alpha.ServerReflection
```

### Describe Service

```bash
grpcurl -plaintext localhost:50051 describe governance.GovernanceService
```

### Call Method

```bash
grpcurl -plaintext \
  -d '{
    "decision_type": "data_promotion",
    "title": "Test Decision",
    "description": "Test",
    "domain_id": "test",
    "created_by": "user-1"
  }' \
  localhost:50051 governance.GovernanceService/CreateDecision
```

## Comparison: gRPC vs REST

| Feature             | gRPC                        | REST                    |
| ------------------- | --------------------------- | ----------------------- |
| **Protocol**        | HTTP/2                      | HTTP/1.1                |
| **Payload**         | Protocol Buffers (binary)   | JSON (text)             |
| **Performance**     | ~5-10x faster               | Baseline                |
| **Streaming**       | Bidirectional               | Server-Sent Events only |
| **Browser Support** | Limited (requires grpc-web) | Full support            |
| **Tooling**         | grpcurl, BloomRPC           | curl, Postman           |
| **Use Case**        | Service-to-service          | Web clients, webhooks   |

## Security

### TLS/SSL

For production, use TLS:

```python
import grpc

# Read certificate
with open('server.crt', 'rb') as f:
    trusted_certs = f.read()

credentials = grpc.ssl_channel_credentials(root_certificates=trusted_certs)
channel = grpc.secure_channel('api.opendatagov.com:50051', credentials)
stub = governance_pb2_grpc.GovernanceServiceStub(channel)
```

### Mutual TLS (mTLS)

```python
# Client certificate authentication
with open('client.crt', 'rb') as f:
    client_cert = f.read()
with open('client.key', 'rb') as f:
    client_key = f.read()
with open('ca.crt', 'rb') as f:
    ca_cert = f.read()

credentials = grpc.ssl_channel_credentials(
    root_certificates=ca_cert,
    private_key=client_key,
    certificate_chain=client_cert
)

channel = grpc.secure_channel('api.opendatagov.com:50051', credentials)
```

## Further Reading

- [gRPC Documentation](https://grpc.io/docs/)
- [Protocol Buffers Guide](https://protobuf.dev/)
- [gRPC Python Quickstart](https://grpc.io/docs/languages/python/quickstart/)
- [Best Practices](https://grpc.io/docs/guides/performance/)
