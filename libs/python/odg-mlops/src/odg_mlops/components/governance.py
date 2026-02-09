"""Governance integration components for Kubeflow Pipelines."""

from __future__ import annotations

from kfp import dsl


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["httpx>=0.25.0"],
)
def request_governance_approval(
    model_name: str,
    model_version: int,
    mlflow_run_id: str,
    mlflow_model_uri: str,
    source_stage: str = "staging",
    target_stage: str = "production",
    justification: str = "",
    performance_metrics: dict | None = None,
    governance_engine_url: str = "http://governance-engine:8000",
    auth_token: str | None = None,
) -> tuple[str, bool, str]:
    """Request B-Swarm governance approval for model promotion.

    This component creates a RACI-based governance decision that requires
    approval from the Data Architect before the model can be promoted to
    production.

    Args:
        model_name: Model name
        model_version: Model version number
        mlflow_run_id: MLflow run ID
        mlflow_model_uri: MLflow model URI
        source_stage: Current stage (e.g., "staging")
        target_stage: Target stage (e.g., "production")
        justification: Business justification for promotion
        performance_metrics: Model performance metrics
        governance_engine_url: Governance Engine URL
        auth_token: Optional Keycloak auth token

    Returns:
        tuple containing:
        - decision_id (str): Governance decision ID
        - approval_required (bool): Whether approval is required
        - status (str): Decision status

    Example:
        >>> # Request approval for high-performing model
        >>> with dsl.Condition(train_task.outputs['f1_score'] > 0.8):
        ...     approval_task = request_governance_approval(
        ...         model_name="customer-churn",
        ...         model_version=register_task.outputs['version'],
        ...         mlflow_run_id=log_task.outputs['run_id'],
        ...         mlflow_model_uri=log_task.outputs['model_uri'],
        ...         justification="Model achieves F1 > 0.8",
        ...         performance_metrics=train_task.outputs['metrics']
        ...     )
    """
    import httpx

    if performance_metrics is None:
        performance_metrics = {}

    # Prepare request payload
    payload = {
        "model_name": model_name,
        "source_stage": source_stage,
        "target_stage": target_stage,
        "model_version": model_version,
        "mlflow_run_id": mlflow_run_id,
        "mlflow_model_uri": mlflow_model_uri,
        "justification": justification
        or f"Automated promotion request for {model_name} v{model_version}",
        "performance_metrics": performance_metrics,
    }

    print(f"Requesting governance approval for {model_name} v{model_version}")
    print(f"Promotion: {source_stage} → {target_stage}")
    print(f"Governance Engine: {governance_engine_url}")

    # Send request to Governance Engine
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{governance_engine_url}/api/v1/mlops/model-promotion",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to request governance approval: {e}") from e

    decision_id = result["decision_id"]
    approval_required = result["approval_required"]
    status = result["status"]

    print("\n✓ Governance decision created:")
    print(f"  Decision ID: {decision_id}")
    print(f"  Status: {status}")
    print(f"  Approval Required: {approval_required}")

    if approval_required:
        print("\n⚠ Awaiting approval from Data Architect")
        print(f"  Track decision: {governance_engine_url}/decisions/{decision_id}")
    else:
        print("\n✓ No approval required for this promotion path")

    return decision_id, approval_required, status


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["httpx>=0.25.0"],
)
def check_approval_status(
    decision_id: str,
    governance_engine_url: str = "http://governance-engine:8000",
    auth_token: str | None = None,
) -> tuple[str, bool]:
    """Check status of a governance approval decision.

    Args:
        decision_id: Decision ID from request_governance_approval
        governance_engine_url: Governance Engine URL
        auth_token: Optional Keycloak auth token

    Returns:
        tuple containing:
        - status (str): Decision status (PENDING, APPROVED, DENIED)
        - approved (bool): Whether decision was approved

    Example:
        >>> status_task = check_approval_status(
        ...     decision_id=approval_task.outputs['decision_id']
        ... )
    """
    import httpx

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{governance_engine_url}/api/v1/mlops/model-promotion/{decision_id}",
                headers=headers,
            )
            response.raise_for_status()
            decision = response.json()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to check approval status: {e}") from e

    status = decision["status"]
    approved = status == "APPROVED"

    print(f"Decision ID: {decision_id}")
    print(f"Status: {status}")
    print(f"Approved: {approved}")

    if approved:
        print(f"✓ Decision approved by: {decision.get('approved_by', 'N/A')}")
    elif status == "PENDING":
        print("⏳ Decision pending approval")
    elif status == "DENIED":
        print("❌ Decision denied")

    return status, approved
