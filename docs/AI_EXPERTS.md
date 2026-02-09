# AI Experts - OpenDataGov

OpenDataGov includes **4 specialized AI experts** for intelligent data governance operations. All experts comply with **EU AI Act** requirements and follow the **"AI recommends, human decides"** principle (ADR-011).

## Table of Contents

- [Overview](#overview)
- [Expert Services](#expert-services)
  - [RAG Expert](#rag-expert)
  - [Code Expert](#code-expert)
  - [Vision Expert](#vision-expert)
  - [NLP Expert](#nlp-expert)
- [EU AI Act Compliance](#eu-ai-act-compliance)
- [Deployment](#deployment)
- [API Reference](#api-reference)
- [Governance Integration](#governance-integration)
- [Examples](#examples)

______________________________________________________________________

## Overview

### Architecture

```
┌─────────────────┐
│  User Request   │
└────────┬────────┘
         │
    ┌────▼─────────────────────────────────────┐
    │   Governance Engine (B-Swarm)            │
    │   - RACI workflow                        │
    │   - Approval decisions                   │
    │   - Audit trail (Kafka)                  │
    └────┬─────────────────────────────────────┘
         │
    ┌────▼─────────────────────────────────────┐
    │   AI Experts                             │
    │   ┌──────────┬─────────┬────────┬─────┐  │
    │   │ RAG      │ Code    │ Vision │ NLP │  │
    │   │ Expert   │ Expert  │ Expert │ Exp │  │
    │   └──────────┴─────────┴────────┴─────┘  │
    └────┬─────────────────────────────────────┘
         │
    ┌────▼─────────────────────────────────────┐
    │   Infrastructure                         │
    │   - Qdrant (vector store)                │
    │   - GPU nodes (optional)                 │
    │   - OpenTelemetry (observability)        │
    └──────────────────────────────────────────┘
```

### Key Features

✅ **EU AI Act Compliant**: All experts classified as LIMITED risk with Model Cards
✅ **B-Swarm Governance**: RACI approval workflows for all critical operations
✅ **Human Oversight**: `requires_approval` flag for all recommendations
✅ **Audit Trail**: All requests logged to Kafka for compliance
✅ **Privacy-First**: PII detection (NLP Expert) for GDPR/LGPD
✅ **Security**: Vulnerability scanning (Code Expert), network policies
✅ **Observability**: OpenTelemetry traces, Prometheus metrics, Grafana dashboards

______________________________________________________________________

## Expert Services

### RAG Expert

**Retrieval-Augmented Generation** for governance Q&A.

#### Capabilities

| Capability         | Description                               | Requires Approval |
| ------------------ | ----------------------------------------- | ----------------- |
| `document_search`  | Semantic search over governance documents | ❌ No             |
| `qa_generation`    | Answer questions with retrieved context   | ✅ Yes            |
| `summarization`    | Summarize policies and regulations        | ✅ Yes            |
| `compliance_check` | Check compliance against regulations      | ✅ Yes            |

#### Model Details

- **Embedding**: SentenceTransformer (all-mpnet-base-v2)
- **LLM**: Mistral-7B-Instruct-v0.2 (vLLM)
- **Vector Store**: Qdrant
- **Risk Level**: LIMITED (EU AI Act Article 52)

#### Example

```bash
curl -X POST http://rag-expert:8002/api/v1/expert/process \
  -H "Content-Type: application/json" \
  -d '{
    "capability": "qa_generation",
    "query": "What is our data retention policy for PII?",
    "context": {"domain": "privacy"}
  }'
```

**Response:**

```json
{
  "recommendation": "Based on the retrieved documents, I found relevant information. However, this requires human review...",
  "confidence": 0.75,
  "reasoning": "Retrieved 3 relevant documents and generated answer",
  "metadata": {
    "sources": [
      {"id": "policy-001", "score": 0.92, "text": "..."},
      {"id": "policy-042", "score": 0.87, "text": "..."}
    ]
  },
  "requires_approval": true
}
```

______________________________________________________________________

### Code Expert

**Code generation and security analysis** with syntax validation.

#### Capabilities

| Capability        | Description                         | Requires Approval |
| ----------------- | ----------------------------------- | ----------------- |
| `code_generation` | Generate code from natural language | ✅ Yes            |
| `code_review`     | Review code for security issues     | ❌ No             |
| `refactoring`     | Suggest refactoring improvements    | ❌ No             |
| `bug_fix`         | Suggest bug fixes                   | ✅ Yes            |

#### Model Details

- **Code Generation**: Starcoder (7B parameters)
- **Syntax Validation**: Python AST + TreeSitter
- **Security Scanning**: Pattern-based (Semgrep in production)
- **Risk Level**: LIMITED (EU AI Act Article 52)

#### Security Features

- ✅ Syntax validation (AST parsing, 99%+ accuracy)
- ✅ Security pattern detection (eval, exec, os.system, etc.)
- ✅ Mandatory code review before deployment
- ✅ Audit logs for all generated code

#### Example

```bash
curl -X POST http://code-expert:8004/api/v1/expert/process \
  -H "Content-Type: application/json" \
  -d '{
    "capability": "code_generation",
    "query": "Write a function to validate email addresses",
    "context": {"language": "python"}
  }'
```

**Response:**

```json
{
  "recommendation": "import re\n\ndef validate_email(email: str) -> bool:\n    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'\n    return bool(re.match(pattern, email))",
  "confidence": 0.85,
  "reasoning": "Code passed syntax and security validation. Manual review recommended.",
  "metadata": {
    "language": "python",
    "vulnerabilities": [],
    "validation_status": "passed",
    "security_status": "clean"
  },
  "requires_approval": true
}
```

______________________________________________________________________

### Vision Expert

**Image analysis and classification** with CLIP.

#### Capabilities

| Capability              | Description                       | Requires Approval |
| ----------------------- | --------------------------------- | ----------------- |
| `image_classification`  | Classify images into categories   | ⚠️ If conf < 0.8  |
| `image_text_similarity` | Match images to text descriptions | ❌ No             |
| `visual_qa`             | Answer questions about images     | ✅ Yes            |
| `object_detection`      | Detect objects in images          | ✅ Yes            |

#### Model Details

- **Vision Model**: OpenAI CLIP (ViT-B/32)
- **Embedding Dimension**: 512
- **Architecture**: Vision Transformer
- **Risk Level**: LIMITED (EU AI Act Article 52)

#### ⚠️ Prohibited Uses (EU AI Act Article 5)

❌ **UNACCEPTABLE** - Do NOT use for:

- Biometric identification
- Emotion recognition in workplace/education
- Social scoring
- Real-time surveillance

#### Example

```bash
curl -X POST http://vision-expert:8005/api/v1/expert/process \
  -H "Content-Type: application/json" \
  -d '{
    "capability": "image_classification",
    "query": "Classify this image",
    "context": {
      "image_url": "https://example.com/dataset.jpg",
      "labels": ["chart", "table", "text", "diagram"]
    }
  }'
```

______________________________________________________________________

### NLP Expert

**Natural language processing** with BERT and **PII detection**.

#### Capabilities

| Capability                 | Description                      | Requires Approval   |
| -------------------------- | -------------------------------- | ------------------- |
| `text_classification`      | Classify text into categories    | ⚠️ If PII detected  |
| `named_entity_recognition` | Extract entities + PII detection | ✅ Always (GDPR)    |
| `sentiment_analysis`       | Analyze sentiment                | ❌ No               |
| `text_summarization`       | Summarize documents              | ⚠️ If PII in source |
| `question_answering`       | Answer questions from context    | ✅ Yes              |

#### Model Details

- **Base Model**: BERT (bert-base-uncased)
- **Parameters**: 110M
- **PII Detection**: Regex-based (email, phone, SSN, credit card, IP)
- **Risk Level**: LIMITED (EU AI Act Article 52)

#### Privacy Features (GDPR/LGPD)

- ✅ Automatic PII detection (5 patterns)
- ✅ Mandatory approval for PII-containing text
- ✅ Audit logs for all PII detections
- ✅ Data Protection Officer oversight

#### Example

```bash
curl -X POST http://nlp-expert:8006/api/v1/expert/process \
  -H "Content-Type: application/json" \
  -d '{
    "capability": "named_entity_recognition",
    "query": "John Doe works at Acme Corp. Contact: john@example.com",
    "context": {}
  }'
```

**Response:**

```json
{
  "recommendation": "Extracted 3 entities (1 PII)",
  "confidence": 0.85,
  "reasoning": "Named entity recognition completed. ⚠️ 1 PII entities detected (GDPR/LGPD compliance required)",
  "metadata": {
    "entities": [
      {"type": "PERSON_OR_ORG", "text": "John", "start": 0, "end": 4},
      {"type": "PERSON_OR_ORG", "text": "Doe", "start": 5, "end": 8},
      {"type": "PERSON_OR_ORG", "text": "Acme", "start": 18, "end": 22},
      {"type": "PII_EMAIL", "text": "john@example.com", "start": 37, "end": 53}
    ],
    "pii_count": 1,
    "privacy_warning": true
  },
  "requires_approval": true
}
```

______________________________________________________________________

## EU AI Act Compliance

All AI Experts are classified as **LIMITED risk** under **EU AI Act Article 52** (Transparency obligations).

### Requirements

| Requirement         | Implementation                                    |
| ------------------- | ------------------------------------------------- |
| **Model Card**      | YAML files in `/modelcards/` for each expert      |
| **Transparency**    | Confidence scores + source documents              |
| **Human Oversight** | `requires_approval: true` for critical operations |
| **Audit Trail**     | All requests logged to Kafka                      |
| **Risk Assessment** | Annual review (every 6 months)                    |

### Model Cards

Each expert has a comprehensive Model Card:

- [rag-expert.yaml](../modelcards/rag-expert.yaml)
- [code-expert.yaml](../modelcards/code-expert.yaml)
- [vision-expert.yaml](../modelcards/vision-expert.yaml)
- [nlp-expert.yaml](../modelcards/nlp-expert.yaml)

### Approval Workflow

```
┌─────────────────────────────────────────────┐
│  1. Expert Registration Request             │
│     POST /api/v1/mlops/expert-registration  │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  2. B-Swarm Governance Decision             │
│     - MINIMAL: Auto-approved                │
│     - LIMITED: Data Architect approval      │
│     - HIGH: Data Architect + Legal          │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  3. Expert Deployment                       │
│     kubectl apply -f ai-experts/            │
└─────────────────────────────────────────────┘
```

______________________________________________________________________

## Deployment

### Prerequisites

- Kubernetes cluster (1.25+)
- Helm 3.10+
- Optional: GPU nodes for Vision/NLP experts

### Quick Start

```bash
# Add Helm repository
helm repo add opendatagov https://charts.opendatagov.org
helm repo update

# Install AI Experts (dev profile)
helm install ai-experts opendatagov/ai-experts \
  -f values-dev.yaml \
  --namespace odg \
  --create-namespace

# Verify deployment
kubectl get pods -n odg -l app.kubernetes.io/name=ai-experts
```

### Deployment Profiles

| Profile    | Use Case    | Resources | GPU         | HA         |
| ---------- | ----------- | --------- | ----------- | ---------- |
| **dev**    | Development | Minimal   | ❌ No       | ❌ No      |
| **small**  | Small teams | Low       | ❌ No       | ❌ No      |
| **medium** | Production  | Medium    | ✅ Optional | ⚠️ Partial |
| **large**  | Enterprise  | High      | ✅ Yes      | ✅ Full    |

### Profile Selection

```bash
# Dev profile (minimal resources)
helm install ai-experts opendatagov/ai-experts -f values-dev.yaml

# Medium profile (production-ready, GPU)
helm install ai-experts opendatagov/ai-experts -f values-medium.yaml

# Large profile (HA, multi-GPU)
helm install ai-experts opendatagov/ai-experts -f values-large.yaml
```

### Configuration

**Enable/disable specific experts:**

```yaml
# values-custom.yaml
ragExpert:
  enabled: true  # Enable RAG Expert
codeExpert:
  enabled: false  # Disable Code Expert
visionExpert:
  enabled: true
nlpExpert:
  enabled: true
```

**GPU configuration (Vision/NLP):**

```yaml
visionExpert:
  gpu:
    enabled: true
    count: 2  # Multi-GPU
  env:
    - name: DEVICE
      value: cuda
```

______________________________________________________________________

## API Reference

### Common Endpoints (All Experts)

#### Health Check

```
GET /health
```

**Response:**

```json
{"status": "ok"}
```

#### Capabilities

```
GET /capabilities
```

**Response:**

```json
{
  "expert_name": "rag-expert",
  "capabilities": [...],
  "risk_level": "LIMITED",
  "requires_model_card": true
}
```

#### Process Request

```
POST /api/v1/expert/process
```

**Request Body:**

```json
{
  "capability": "qa_generation",
  "query": "Your query here",
  "context": {}
}
```

**Response:**

```json
{
  "recommendation": "...",
  "confidence": 0.85,
  "reasoning": "...",
  "metadata": {},
  "requires_approval": true
}
```

______________________________________________________________________

## Governance Integration

### Expert Registration

Register a new AI expert with governance approval:

```bash
curl -X POST http://governance-engine:8000/api/v1/mlops/expert-registration \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "expert_name": "rag-expert",
    "expert_version": "0.1.0",
    "capabilities": ["document_search", "qa_generation"],
    "risk_level": "LIMITED",
    "model_backend": "SentenceTransformer + Mistral-7B",
    "model_card_url": "https://modelcards.opendatagov.org/rag-expert.yaml",
    "justification": "Needed for governance Q&A automation",
    "security_features": ["Human oversight", "Audit trail", "Source transparency"]
  }'
```

**Response:**

```json
{
  "decision_id": "dec_123",
  "status": "PENDING",
  "message": "AI Expert registration decision created. Awaiting approval from Data Architect.",
  "approval_required": true
}
```

### Check Registration Status

```bash
curl http://governance-engine:8000/api/v1/mlops/expert-registration/dec_123
```

### RACI Workflow

| Role               | Responsibility | Action                   |
| ------------------ | -------------- | ------------------------ |
| **Data Scientist** | Responsible    | Request registration     |
| **Data Architect** | Accountable    | Approve/reject (LIMITED) |
| **Legal Team**     | Consulted      | Review (HIGH risk only)  |
| **Data Steward**   | Informed       | Monitor usage            |

______________________________________________________________________

## Examples

### Example 1: Governance Q&A with RAG Expert

```python
import httpx

# Query governance documents
response = httpx.post(
    "http://rag-expert:8002/api/v1/expert/process",
    json={
        "capability": "qa_generation",
        "query": "What are the requirements for GDPR Article 17 (right to erasure)?",
        "context": {"regulation": "GDPR"}
    }
)

result = response.json()
print(f"Answer: {result['recommendation']}")
print(f"Confidence: {result['confidence']}")
print(f"Requires Approval: {result['requires_approval']}")

# Show source documents
for doc in result['metadata']['sources']:
    print(f"- {doc['id']} (score: {doc['score']:.2f})")
```

### Example 2: Code Security Review

```python
import httpx

# Review code for security issues
code_to_review = """
import os

def run_command(cmd):
    os.system(cmd)  # Security issue!
"""

response = httpx.post(
    "http://code-expert:8004/api/v1/expert/process",
    json={
        "capability": "code_review",
        "query": code_to_review,
        "context": {"language": "python"}
    }
)

result = response.json()
if result['metadata']['vulnerabilities']:
    print("⚠️ Security issues found:")
    for vuln in result['metadata']['vulnerabilities']:
        print(f"- {vuln['severity']}: {vuln['message']}")
```

### Example 3: PII Detection with NLP Expert

```python
import httpx

# Detect PII in text
text = "Contact John Smith at john.smith@example.com or 555-123-4567"

response = httpx.post(
    "http://nlp-expert:8006/api/v1/expert/process",
    json={
        "capability": "named_entity_recognition",
        "query": text,
        "context": {}
    }
)

result = response.json()
if result['metadata']['privacy_warning']:
    print(f"⚠️ GDPR WARNING: {result['metadata']['pii_count']} PII entities detected")
    for entity in result['metadata']['entities']:
        if entity['type'].startswith('PII_'):
            print(f"- {entity['type']}: {entity['text']}")
```

______________________________________________________________________

## Monitoring

### Prometheus Metrics

All experts expose metrics at `/metrics`:

- `http_requests_total` - Total requests
- `http_request_duration_seconds` - Request latency
- `expert_confidence_score` - Confidence score distribution
- `expert_approval_required_total` - Requests requiring approval

### Grafana Dashboards

Import dashboards from `/deploy/grafana-dashboards/`:

- `ai-experts-overview.json` - All experts overview
- `ai-experts-performance.json` - Latency and throughput
- `ai-experts-governance.json` - Approval rates, PII detection

### Audit Trail

All expert requests are logged to Kafka topic `odg.ai.experts`:

```json
{
  "expert": "rag-expert",
  "capability": "qa_generation",
  "query": "...",
  "response": {...},
  "requires_approval": true,
  "user_id": "user_123",
  "timestamp": "2026-02-08T10:30:00Z",
  "trace_id": "abc123..."
}
```

______________________________________________________________________

## Troubleshooting

### Common Issues

**1. Expert pod not starting**

```bash
kubectl logs -n odg <pod-name>
kubectl describe pod -n odg <pod-name>
```

**2. Qdrant connection failed (RAG Expert)**

```bash
# Check Qdrant is running
kubectl get pods -n odg -l app=qdrant

# Test connectivity
kubectl exec -n odg <rag-expert-pod> -- curl http://qdrant:6333/health
```

**3. GPU not available (Vision/NLP)**

```bash
# Check GPU node labels
kubectl get nodes -l gpu=true

# Verify NVIDIA device plugin
kubectl get pods -n kube-system -l name=nvidia-device-plugin-ds
```

**4. Low confidence scores**

- Check model loading in logs
- Verify input quality
- Review model card limitations

______________________________________________________________________

## Next Steps

- Read [Model Cards](../modelcards/) for detailed AI compliance
- Review [Governance Integration](GOVERNANCE.md) for approval workflows
- Check [Deployment Profiles](DEPLOYMENT_PROFILES.md) for scaling
- See [API Reference](API_GRAPHQL.md) for GraphQL integration

______________________________________________________________________

**Version**: 0.1.0
**Last Updated**: 2026-02-08
**Compliance**: EU AI Act Article 52 (LIMITED risk)
