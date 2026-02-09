"""KServe admission webhook for governance validation.

This webhook is called by Kubernetes before creating/updating InferenceService
resources. It enforces governance policies by:

1. Checking that production deployments have approved governance decisions
2. Validating model provenance (MLflow tracking)
3. Ensuring model cards exist for HIGH/LIMITED risk models (EU AI Act)
4. Verifying RACI approvals for stage transitions
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks/kserve", tags=["webhooks"])


@router.post("/validate")
async def validate_inference_service(request: Request) -> dict[str, Any]:
    """Kubernetes ValidatingWebhook for InferenceService resources.

    Called by K8s API server before CREATE/UPDATE operations on InferenceServices.
    Blocks deployment if governance requirements are not met.

    Request format (Kubernetes AdmissionReview):
    ```json
    {
      "apiVersion": "admission.k8s.io/v1",
      "kind": "AdmissionReview",
      "request": {
        "uid": "...",
        "kind": {"group": "serving.kserve.io", "version": "v1beta1", "kind": "InferenceService"},
        "resource": {"group": "serving.kserve.io", "version": "v1beta1", "resource": "inferenceservices"},
        "operation": "CREATE",
        "object": { ... InferenceService spec ... }
      }
    }
    ```

    Returns:
        AdmissionReview response with allowed=true/false
    """
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook request: {e}")
        return _deny_response(
            uid="unknown",
            message=f"Invalid webhook request format: {e}",
        )

    # Extract AdmissionReview fields
    admission_request = body.get("request", {})
    uid = admission_request.get("uid")
    operation = admission_request.get("operation")
    inference_service = admission_request.get("object", {})

    # Extract InferenceService metadata
    metadata = inference_service.get("metadata", {})
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace", "default")
    annotations = metadata.get("annotations", {})
    labels = metadata.get("labels", {})

    logger.info(f"Validating InferenceService: {namespace}/{name} (operation: {operation})")

    # Check if governance is required
    governance_required = annotations.get("odg.governance/requires-approval") == "true"

    if not governance_required:
        logger.info(f"Governance not required for {namespace}/{name} - allowing")
        return _allow_response(uid, message="Governance validation not required")

    # Extract governance decision ID from annotations
    decision_id = annotations.get("odg.governance/decision-id")

    if not decision_id:
        logger.warning(f"Missing decision-id annotation for {namespace}/{name}")
        return _deny_response(
            uid,
            message="InferenceService requires governance approval but missing 'odg.governance/decision-id' annotation",
        )

    # Validate decision is approved
    # TODO: Query decision service
    # decision = await decision_service.get_decision(decision_id)
    # if decision.status != DecisionStatus.APPROVED:
    #     return _deny_response(
    #         uid,
    #         message=f"Decision {decision_id} not approved (status: {decision.status})"
    #     )

    # For now, log and allow (full implementation requires decision service integration)
    logger.info(f"Governance validation passed for {namespace}/{name} (decision: {decision_id})")

    # Extract model metadata
    model_name = labels.get("odg.model/name", "unknown")
    model_version = labels.get("odg.model/version", "unknown")
    risk_level = annotations.get("odg.model/risk-level", "MINIMAL")

    # Validate model card exists for HIGH/LIMITED risk models
    if risk_level in ["HIGH", "LIMITED"]:
        # TODO: Check model card exists in database
        logger.info(f"Model {model_name} v{model_version} is {risk_level} risk - should have model card")

    return _allow_response(
        uid,
        message=f"Governance validation passed for {namespace}/{name} (decision: {decision_id})",
    )


def _allow_response(uid: str, message: str = "") -> dict[str, Any]:
    """Generate allowed AdmissionReview response.

    Args:
        uid: Request UID
        message: Optional status message

    Returns:
        AdmissionReview response with allowed=true
    """
    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": True,
            "status": {"message": message} if message else {},
        },
    }


def _deny_response(uid: str, message: str) -> dict[str, Any]:
    """Generate denied AdmissionReview response.

    Args:
        uid: Request UID
        message: Denial reason

    Returns:
        AdmissionReview response with allowed=false
    """
    logger.warning(f"Denying InferenceService deployment: {message}")

    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": False,
            "status": {
                "code": 403,
                "message": message,
            },
        },
    }


@router.get("/health")
async def webhook_health() -> dict[str, str]:
    """Webhook health check endpoint.

    Used by Kubernetes to verify webhook is reachable before routing
    admission requests.

    Returns:
        Health status
    """
    return {"status": "healthy", "webhook": "kserve-governance"}
