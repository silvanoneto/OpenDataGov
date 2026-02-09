# MLOps Implementation - Phase 1: MLflow Foundation

**Status**: ✅ Phase 1 Complete
**Date**: 2026-02-08
**Version**: 0.1.0

## Overview

The OpenDataGov MLOps implementation integrates experiment tracking and model registry capabilities while maintaining B-Swarm governance workflows. This ensures that all ML model lifecycles follow RACI-based approval processes and maintain audit trails.

### Architecture Principles

1. **B-Swarm Governance First**: MLflow operations integrate with existing governance workflows
1. **RACI Model**: Model promotions follow defined responsibility assignments
1. **EU AI Act Compliant**: Model Cards automatically track MLflow metadata
1. **Zero-Trust Security**: All MLflow operations authenticated via Keycloak, authorized via OPA
1. **Profile-Based Scaling**: From dev (no governance) to large (HA + full governance)

## Phase 1: MLflow Foundation

### Components Implemented

#### 1. MLflow Tracking Server

- **PostgreSQL Backend**: Experiment and run metadata storage
- **MinIO Artifact Store**: Model artifacts, datasets, plots storage
- **REST API + UI**: http://mlflow:5000
- **Profiles**:
  - `dev`: Single replica, no governance, ephemeral PostgreSQL
  - `medium`: 2-5 replicas (autoscaling), governance enabled, shared PostgreSQL
  - `large`: 3-10 replicas (autoscaling), HA mode, Vault secrets

#### 2. Governance Integration

- **Model Promotion API**: `/api/v1/mlops/model-promotion`
- **Retraining Requests**: `/api/v1/mlops/model-retraining`
- **Webhook Validation**: `/api/v1/mlops/webhook/mlflow-promotion`
- **RACI Workflow**:
  - **Responsible**: Data Scientist (initiates promotion)
  - **Accountable**: Data Architect (approves production deployment)
  - **Consulted**: Data Owner (reviews business impact)
  - **Informed**: Data Steward (notified of changes)

#### 3. Model Card Integration

Extended `ModelCard` class with MLflow fields:

```python
class ModelCard(BaseModel):
    # ... existing fields ...

    # MLflow integration
    mlflow_experiment_id: str | None = None
    mlflow_run_id: str | None = None
    mlflow_model_uri: str | None = None
    mlflow_version: int | None = None
    mlflow_stage: str | None = None  # None, Staging, Production, Archived
```

## Usage Guide

### 1. Logging Experiments

```python
import mlflow
from odg_sdk import OpenDataGovClient

# Configure MLflow tracking URI
mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("customer-churn")

# Log experiment
with mlflow.start_run() as run:
    # Log parameters
    mlflow.log_param("alpha", 0.5)
    mlflow.log_param("max_depth", 10)

    # Train model
    model = train_model(X_train, y_train, alpha=0.5, max_depth=10)

    # Log metrics
    mlflow.log_metric("accuracy", 0.95)
    mlflow.log_metric("precision", 0.93)
    mlflow.log_metric("recall", 0.96)

    # Log model
    mlflow.sklearn.log_model(model, "model")

    print(f"Run ID: {run.info.run_id}")
```

### 2. Registering Models

```python
# Register model from run
model_uri = f"runs:/{run.info.run_id}/model"
model_details = mlflow.register_model(model_uri, "customer-churn")

print(f"Model registered: {model_details.name} v{model_details.version}")
```

### 3. Requesting Production Promotion

**With Governance (medium/large profiles)**:

```python
from odg_sdk import OpenDataGovClient

# Initialize SDK
client = OpenDataGovClient(
    base_url="http://governance-engine:8000",
    auth_token=keycloak_token
)

# Request promotion via governance
decision = await client.mlops.request_promotion(
    model_name="customer-churn",
    source_stage="staging",
    target_stage="production",
    model_version=1,
    mlflow_run_id=run.info.run_id,
    mlflow_model_uri=model_uri,
    justification="Model achieves 95% accuracy, passes all validation tests",
    performance_metrics={
        "accuracy": 0.95,
        "precision": 0.93,
        "recall": 0.96
    }
)

print(f"Decision ID: {decision.decision_id}")
print(f"Status: {decision.status}")
print(f"Approval required: {decision.approval_required}")
```

**Without Governance (dev profile)**:

```python
from mlflow.tracking import MlflowClient

client = MlflowClient()

# Direct promotion (no approval needed)
client.transition_model_version_stage(
    name="customer-churn",
    version=1,
    stage="Production"
)
```

### 4. Approving Promotions (Data Architect)

```python
# Data Architect approves the decision
await client.decisions.approve(
    decision_id=decision.decision_id,
    approver_id="data-architect-1",
    comments="Model metrics meet production SLA requirements"
)

# MLflow stage transition happens automatically after approval
```

### 5. Checking Promotion Status

```python
status = await client.mlops.get_promotion_status(decision.decision_id)

print(f"Status: {status['status']}")
print(f"Approved by: {status.get('approved_by', 'Pending')}")
print(f"Metadata: {status['metadata']}")
```

## Deployment Profiles

### Development Profile (`values-dev.yaml`)

```yaml
mlflow:
  enabled: true
  replicaCount: 1
  resources:
    requests: {cpu: 100m, memory: 256Mi}
    limits: {cpu: 500m, memory: 512Mi}
  governance:
    enabled: false  # No approval workflow
```

**Use case**: Local development, experimentation
**Governance**: Disabled
**Promotions**: Direct (no approval required)

### Medium Profile (`values-medium.yaml`)

```yaml
mlflow:
  enabled: true
  replicaCount: 2
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 5
  resources:
    requests: {cpu: 2, memory: 4Gi}
    limits: {cpu: 4, memory: 8Gi}
  governance:
    enabled: true
    promotionRequiresApproval: true
```

**Use case**: Enterprise deployment, 1-10TB/day
**Governance**: Enabled
**Promotions**: Staging→Production requires Data Architect approval

### Large Profile (`values-large.yaml`)

```yaml
mlflow:
  enabled: true
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
  ha:
    enabled: true
    readReplicas: 2
  resources:
    requests: {cpu: 4, memory: 8Gi}
    limits: {cpu: 8, memory: 16Gi}
  governance:
    enabled: true
  vault:
    enabled: true  # Secrets from Vault
```

**Use case**: Large-scale, >10TB/day, Multi-AZ
**Governance**: Mandatory
**Promotions**: All stage transitions tracked and audited

## API Endpoints

### POST `/api/v1/mlops/model-promotion`

Request model promotion with governance approval.

**Request Body**:

```json
{
  "model_name": "customer-churn",
  "source_stage": "staging",
  "target_stage": "production",
  "model_version": 1,
  "mlflow_run_id": "abc123",
  "mlflow_model_uri": "s3://mlflow-artifacts/models/customer-churn/1",
  "justification": "Model achieves 95% accuracy",
  "performance_metrics": {
    "accuracy": 0.95,
    "precision": 0.93
  }
}
```

**Response**:

```json
{
  "decision_id": "dec-001",
  "status": "PENDING",
  "message": "Model promotion decision created. Awaiting approval from Data Architect.",
  "approval_required": true
}
```

**Valid Promotion Paths**:

- ✅ `None → Staging` (no approval)
- ✅ `Staging → Production` (requires approval)
- ✅ `Production → Archived` (requires approval)
- ❌ `None → Production` (invalid)

### POST `/api/v1/mlops/model-retraining`

Request approval for model retraining (typically triggered by drift detection).

**Request Body**:

```json
{
  "model_name": "customer-churn",
  "reason": "Data drift detected in feature distribution",
  "drift_score": 0.85,
  "drift_details": {
    "features_drifted": ["age", "income"],
    "drift_method": "KS-test"
  },
  "requester_id": "ds-001"
}
```

### GET `/api/v1/mlops/model-promotion/{decision_id}`

Get status of a model promotion decision.

**Response**:

```json
{
  "decision_id": "dec-001",
  "status": "APPROVED",
  "created_at": "2026-02-08T10:00:00Z",
  "approved_by": "data-architect-1",
  "metadata": {
    "model_name": "customer-churn",
    "model_version": 1,
    "source_stage": "staging",
    "target_stage": "production"
  }
}
```

## Security & Compliance

### Authentication

- **Keycloak OIDC**: All API calls require valid JWT token
- **Role-Based Access**:
  - `data_scientist`: Can log experiments, request promotions
  - `data_architect`: Can approve promotions, deploy to production
  - `data_owner`: Can review business impact
  - `data_steward`: Receives notifications

### Authorization (OPA)

```rego
# Example policy for model promotion
allow {
    input.action == "mlops:promote"
    input.target_stage == "production"
    input.user.role == "data_architect"
}

allow {
    input.action == "mlops:promote"
    input.target_stage == "staging"
    input.user.role == "data_scientist"
}
```

### Audit Trail

All MLflow operations generate audit events:

```json
{
  "event_type": "MODEL_PROMOTION_REQUESTED",
  "timestamp": "2026-02-08T10:00:00Z",
  "actor": "ds-001",
  "resource": "model/customer-churn/v1",
  "action": "promote:staging->production",
  "decision_id": "dec-001",
  "outcome": "PENDING_APPROVAL"
}
```

## Monitoring & Observability

### Metrics (Prometheus)

- `mlflow_experiments_total`: Total number of experiments
- `mlflow_runs_total`: Total number of runs
- `mlflow_models_registered_total`: Total registered models
- `mlflow_promotions_total{status}`: Promotions by status (approved, denied, pending)
- `mlflow_api_requests_total`: API request count
- `mlflow_api_latency_seconds`: API latency histogram

### Logs (Loki)

```
[2026-02-08 10:00:00] INFO governance_engine.api.routes_mlops - Model promotion requested
  decision_id=dec-001 model=customer-churn version=1
  path=staging→production user=ds-001
```

### Traces (Jaeger)

MLflow operations include OpenTelemetry traces linking:

- API request → Governance decision → Approval → MLflow promotion

## Troubleshooting

### Issue: Promotion fails with "Invalid promotion path"

**Cause**: Attempting direct promotion from None to Production
**Solution**: Promote to Staging first, then Staging to Production

### Issue: Promotion pending forever

**Cause**: Data Architect hasn't approved the decision
**Solution**:

1. Check decision status: `GET /api/v1/mlops/model-promotion/{decision_id}`
1. Notify Data Architect
1. Verify Data Architect has correct RACI role

### Issue: MLflow UI shows 500 error

**Cause**: PostgreSQL connection failure
**Solution**:

```bash
# Check PostgreSQL status
kubectl get pods -l app=postgresql

# Check MLflow logs
kubectl logs -l app=mlflow --tail=100

# Verify connection string
kubectl get configmap mlflow -o yaml | grep MLFLOW_BACKEND_STORE_URI
```

### Issue: Models not appearing in registry

**Cause**: MinIO artifact store not accessible
**Solution**:

```bash
# Check MinIO status
kubectl get pods -l app=minio

# Verify S3 credentials
kubectl get secret mlflow-s3 -o yaml

# Test MinIO access
mc alias set local http://minio:9000 $ACCESS_KEY $SECRET_KEY
mc ls local/mlflow-artifacts
```

## Next Steps: Phase 2 (Kubeflow Pipelines)

Phase 2 will add ML workflow orchestration:

- **Kubeflow Pipelines**: Training pipeline automation
- **Quality Gates**: DQ validation before training (Gold layer >= 0.95)
- **GPU Support**: Training with NVIDIA GPUs
- **Lakehouse Integration**: Automated data loading from medallion layers

**Estimated Timeline**: 4 weeks
**Status**: Planned

## References

- [MLOps Implementation Plan](/Users/silvis/.claude/plans/dynamic-cooking-popcorn.md)
- [ADR-030: Hybrid B-Swarm + MLOps Architecture](../docs/ARCHITECTURE_DECISIONS.md#adr-030)
- [ADR-111: AI Risk Classification (EU AI Act)](../docs/ARCHITECTURE_DECISIONS.md#adr-111)
- [Model Cards Documentation](../libs/python/odg-core/src/odg_core/compliance/model_card.py)
- [Security Implementation (ADR-072, ADR-073)](./SECURITY.md)

## Support

For issues or questions:

- GitHub Issues: https://github.com/silvanoneto/opendatagov/issues
- Documentation: https://opendatagov.readthedocs.io
- Community: https://discord.gg/opendatagov
