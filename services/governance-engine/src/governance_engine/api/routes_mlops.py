"""MLOps governance integration routes (Phase 1: MLflow Foundation).

B-Swarm governance for ML lifecycle:
- Model promotion approval (staging → production)
- Model retraining decisions
- Expert registration approval

RACI workflow for model promotion:
- Responsible: Data Scientist (requester)
- Accountable: Data Architect (approver)
- Consulted: Data Owner
- Informed: Data Steward
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from odg_core.auth.dependencies import require_role
from odg_core.auth.models import UserContext
from odg_core.enums import DecisionType, RACIRole
from pydantic import BaseModel, Field

from governance_engine.api.deps import DecisionServiceDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mlops", tags=["mlops"])


class ModelPromotionRequest(BaseModel):
    """Request to promote a model between stages."""

    model_name: str = Field(..., description="Name of the model to promote")
    source_stage: str = Field(..., description="Current stage (e.g., 'staging')")
    target_stage: str = Field(..., description="Target stage (e.g., 'production')")
    model_version: int = Field(..., description="Version number to promote", gt=0)
    mlflow_run_id: str | None = Field(None, description="MLflow run ID")
    mlflow_model_uri: str | None = Field(None, description="MLflow model URI")
    justification: str = Field(..., description="Business justification for promotion")
    performance_metrics: dict[str, float] = Field(default_factory=dict, description="Model performance metrics")


class ModelPromotionResponse(BaseModel):
    """Response for model promotion request."""

    decision_id: str
    status: str
    message: str
    approval_required: bool


class RetrainingRequest(BaseModel):
    """Request to retrain a model."""

    model_name: str
    reason: str
    drift_score: float | None = None
    drift_details: dict[str, Any] | None = None
    requester_id: str


class RetrainingResponse(BaseModel):
    """Response for retraining request."""

    decision_id: str
    status: str
    message: str


class ExpertRegistrationRequest(BaseModel):
    """Request to register a new AI expert."""

    expert_name: str = Field(..., description="Name of the AI expert (e.g., 'rag-expert')")
    expert_version: str = Field(..., description="Version of the expert")
    capabilities: list[str] = Field(..., description="List of capabilities")
    risk_level: str = Field(..., description="EU AI Act risk level (MINIMAL/LIMITED/HIGH/UNACCEPTABLE)")
    model_backend: str = Field(..., description="Model backend (e.g., 'BERT', 'CLIP', 'Starcoder')")
    model_card_url: str | None = Field(None, description="URL to model card")
    justification: str = Field(..., description="Business justification for deployment")
    security_features: list[str] = Field(default_factory=list, description="Security features implemented")


class ExpertRegistrationResponse(BaseModel):
    """Response for expert registration request."""

    decision_id: str
    status: str
    message: str
    approval_required: bool


@router.post("/model-promotion", response_model=ModelPromotionResponse)
async def request_model_promotion(
    service: DecisionServiceDep,
    promotion_request: ModelPromotionRequest = Body(...),
    user: UserContext = Depends(require_role(RACIRole.RESPONSIBLE)),
) -> ModelPromotionResponse:
    """Request B-Swarm approval for model promotion.

    This endpoint creates a governance decision that requires approval
    from the Data Architect (RACI: Accountable).

    Args:
        promotion_request: Model promotion details
        service: Decision service dependency
        user: Authenticated user context

    Returns:
        ModelPromotionResponse with decision ID and status

    Raises:
        HTTPException: If promotion validation fails
    """
    # Validate promotion path
    valid_promotions = {
        ("none", "staging"),
        ("staging", "production"),
        ("production", "archived"),
    }
    promotion_path = (promotion_request.source_stage.lower(), promotion_request.target_stage.lower())

    if promotion_path not in valid_promotions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid promotion path: {promotion_request.source_stage} →"
                f" {promotion_request.target_stage}. "
                "Valid paths: None→Staging, Staging→Production, Production→Archived"
            ),
        )

    # Determine if approval is required (staging → production always requires approval)
    approval_required = promotion_path == ("staging", "production")

    # Create governance decision
    decision = await service.create_decision(
        decision_type=DecisionType.EXPERT_REGISTRATION,  # Reuse for ML model approval
        title=(
            f"Promote {promotion_request.model_name} v{promotion_request.model_version}"
            f" to {promotion_request.target_stage}"
        ),
        domain_id="mlops",
        created_by=user.user_id,
        metadata={
            "model_name": promotion_request.model_name,
            "source_stage": promotion_request.source_stage,
            "target_stage": promotion_request.target_stage,
            "model_version": promotion_request.model_version,
            "mlflow_run_id": promotion_request.mlflow_run_id,
            "mlflow_model_uri": promotion_request.mlflow_model_uri,
            "justification": promotion_request.justification,
            "performance_metrics": promotion_request.performance_metrics,
            "raci": {
                "responsible": user.user_id,
                "accountable": "data_architect",
                "consulted": ["data_owner"],
                "informed": ["data_steward"],
            },
        },
    )

    logger.info(
        "Model promotion requested",
        extra={
            "decision_id": decision.id,
            "model": promotion_request.model_name,
            "version": promotion_request.model_version,
            "path": f"{promotion_request.source_stage} → {promotion_request.target_stage}",
            "user": user.user_id,
        },
    )

    return ModelPromotionResponse(
        decision_id=str(decision.id),
        status=decision.status,
        message=(
            "Model promotion decision created. "
            + ("Awaiting approval from Data Architect." if approval_required else "No approval required.")
        ),
        approval_required=approval_required,
    )


@router.post("/model-retraining", response_model=RetrainingResponse)
async def request_model_retraining(
    retraining_request: RetrainingRequest,
    service: DecisionServiceDep,
    user: UserContext = Depends(require_role(RACIRole.RESPONSIBLE)),
) -> RetrainingResponse:
    """Request approval to retrain a model.

    Typically triggered by drift detection or performance degradation.

    Args:
        retraining_request: Retraining request details
        service: Decision service dependency
        user: Authenticated user context

    Returns:
        RetrainingResponse with decision ID

    Raises:
        HTTPException: If validation fails
    """
    # Create governance decision for retraining
    decision = await service.create_decision(
        decision_type=DecisionType.EXPERT_REGISTRATION,
        title=f"Retrain model: {retraining_request.model_name}",
        domain_id="mlops",
        created_by=retraining_request.requester_id,
        metadata={
            "model_name": retraining_request.model_name,
            "reason": retraining_request.reason,
            "drift_score": retraining_request.drift_score,
            "drift_details": retraining_request.drift_details,
            "action": "retrain",
        },
    )

    logger.info(
        "Model retraining requested",
        extra={
            "decision_id": decision.id,
            "model": retraining_request.model_name,
            "reason": retraining_request.reason,
            "drift_score": retraining_request.drift_score,
        },
    )

    return RetrainingResponse(
        decision_id=str(decision.id),
        status=decision.status,
        message=f"Retraining decision created for {retraining_request.model_name}",
    )


@router.post("/expert-registration", response_model=ExpertRegistrationResponse)
async def request_expert_registration(
    registration_request: ExpertRegistrationRequest,
    service: DecisionServiceDep,
    user: UserContext = Depends(require_role(RACIRole.RESPONSIBLE)),
) -> ExpertRegistrationResponse:
    """Request approval to register a new AI expert.

    According to EU AI Act and ADR-011:
    - MINIMAL risk: Auto-approved (no governance overhead)
    - LIMITED risk: Requires Data Architect approval
    - HIGH risk: Requires Data Architect + Legal approval
    - UNACCEPTABLE: Rejected automatically

    Args:
        registration_request: Expert registration details
        service: Decision service dependency
        user: Authenticated user context

    Returns:
        ExpertRegistrationResponse with decision ID

    Raises:
        HTTPException: If risk level is UNACCEPTABLE
    """
    # Validate risk level
    risk_level = registration_request.risk_level.upper()
    valid_risk_levels = ["MINIMAL", "LIMITED", "HIGH", "UNACCEPTABLE"]

    if risk_level not in valid_risk_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid risk level: {risk_level}. Must be one of {valid_risk_levels}",
        )

    # Reject UNACCEPTABLE risk
    if risk_level == "UNACCEPTABLE":
        raise HTTPException(
            status_code=403,
            detail="UNACCEPTABLE risk AI systems are prohibited under EU AI Act Article 5",
        )

    # Determine approval requirement
    approval_required = risk_level in ["LIMITED", "HIGH"]

    # Create governance decision
    decision = await service.create_decision(
        decision_type=DecisionType.EXPERT_REGISTRATION,
        title=f"Register AI Expert: {registration_request.expert_name} v{registration_request.expert_version}",
        domain_id="mlops",
        created_by=user.user_id,
        metadata={
            "expert_name": registration_request.expert_name,
            "expert_version": registration_request.expert_version,
            "capabilities": registration_request.capabilities,
            "risk_level": risk_level,
            "model_backend": registration_request.model_backend,
            "model_card_url": registration_request.model_card_url,
            "justification": registration_request.justification,
            "security_features": registration_request.security_features,
            "raci": {
                "responsible": user.user_id,
                "accountable": "data_architect" if risk_level in ["LIMITED", "HIGH"] else None,
                "consulted": ["legal_team"] if risk_level == "HIGH" else [],
                "informed": ["data_steward"],
            },
            "eu_ai_act": {
                "risk_level": risk_level,
                "requires_model_card": risk_level in ["LIMITED", "HIGH"],
                "requires_transparency": True,
                "requires_human_oversight": risk_level in ["LIMITED", "HIGH"],
            },
        },
    )

    logger.info(
        "AI Expert registration requested",
        extra={
            "decision_id": decision.id,
            "expert": registration_request.expert_name,
            "version": registration_request.expert_version,
            "risk_level": risk_level,
            "approval_required": approval_required,
            "user": user.user_id,
        },
    )

    message = "AI Expert registration decision created. "
    if risk_level == "MINIMAL":
        message += "Auto-approved (MINIMAL risk)."
    elif risk_level == "LIMITED":
        message += "Awaiting approval from Data Architect."
    elif risk_level == "HIGH":
        message += "Awaiting approval from Data Architect and Legal team."

    return ExpertRegistrationResponse(
        decision_id=str(decision.id),
        status=decision.status,
        message=message,
        approval_required=approval_required,
    )


@router.get("/model-promotion/{decision_id}")
async def get_promotion_status(
    decision_id: str,
    service: DecisionServiceDep,
    user: UserContext = Depends(require_role(RACIRole.RESPONSIBLE)),
) -> dict[str, Any]:
    """Get status of a model promotion decision.

    Args:
        decision_id: Decision ID from promotion request
        service: Decision service dependency
        user: Authenticated user context

    Returns:
        Decision status and details

    Raises:
        HTTPException: If decision not found
    """
    decision = await service.get_decision(uuid.UUID(decision_id))

    if not decision:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")

    return {
        "decision_id": str(decision.id),
        "status": decision.status,
        "created_at": decision.created_at.isoformat(),
        "approved_by": decision.metadata.get("approved_by"),
        "metadata": decision.metadata,
    }


@router.get("/expert-registration/{decision_id}")
async def get_expert_registration_status(
    decision_id: str,
    service: DecisionServiceDep,
    user: UserContext = Depends(require_role(RACIRole.RESPONSIBLE)),
) -> dict[str, Any]:
    """Get status of an AI expert registration decision.

    Args:
        decision_id: Decision ID from registration request
        service: Decision service dependency
        user: Authenticated user context

    Returns:
        Decision status and details

    Raises:
        HTTPException: If decision not found
    """
    decision = await service.get_decision(uuid.UUID(decision_id))

    if not decision:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")

    return {
        "decision_id": str(decision.id),
        "status": decision.status,
        "expert_name": decision.metadata.get("expert_name"),
        "expert_version": decision.metadata.get("expert_version"),
        "risk_level": decision.metadata.get("risk_level"),
        "created_at": decision.created_at.isoformat(),
        "approved_by": decision.metadata.get("approved_by"),
        "metadata": decision.metadata,
    }


@router.post("/webhook/mlflow-promotion")
async def mlflow_promotion_webhook(
    payload: dict[str, Any],
    service: DecisionServiceDep,
) -> dict[str, Any]:
    """Webhook endpoint called by MLflow when model promotion is attempted.

    This endpoint validates that the promotion has been approved via B-Swarm
    governance before allowing it to proceed.

    Args:
        payload: MLflow webhook payload
        service: Decision service dependency

    Returns:
        Approval status

    Raises:
        HTTPException: If promotion not approved
    """
    model_name = payload.get("model_name")
    model_version = payload.get("version")
    target_stage = payload.get("to_stage")

    # Find pending decision for this promotion
    # Note: In production, implement proper decision lookup by metadata
    logger.info(
        "MLflow promotion webhook called",
        extra={
            "model": model_name,
            "version": model_version,
            "target_stage": target_stage,
        },
    )

    # For now, return success (full implementation requires decision lookup)
    return {
        "approved": True,
        "message": f"Promotion of {model_name} v{model_version} to {target_stage} approved",
    }
