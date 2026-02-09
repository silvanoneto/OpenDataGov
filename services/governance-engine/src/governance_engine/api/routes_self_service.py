"""Self-Service Portal API endpoints (ADR-102).

Provides backend APIs for self-service capabilities:
- Access request workflow
- Dataset discovery and preview
- Pipeline creation (Airflow DAG generation)
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from odg_core.auth.dependencies import get_current_user, require_role
from odg_core.auth.models import UserContext
from odg_core.enums import RACIRole
from pydantic import BaseModel, Field

from governance_engine.api.deps import DecisionServiceDep

router = APIRouter(prefix="/api/v1/self-service", tags=["self-service"])


# ──── Request/Response Models ─────────────────────────────────────


class AccessRequestCreate(BaseModel):
    """Request to access a dataset."""

    dataset_id: str
    requester_id: str
    purpose: str = Field(min_length=10, description="Purpose of access (min 10 chars)")
    duration_days: int = Field(default=30, ge=1, le=365, description="Access duration in days")
    justification: str = ""


class AccessRequestResponse(BaseModel):
    """Access request with approval status."""

    request_id: uuid.UUID
    dataset_id: str
    requester_id: str
    purpose: str
    status: str  # pending, approved, rejected
    created_at: str
    decision_id: uuid.UUID | None = None


class DatasetSearchResult(BaseModel):
    """Dataset search result for discovery."""

    dataset_id: str
    name: str
    description: str
    layer: str  # bronze, silver, gold, platinum
    classification: str  # public, internal, sensitive, confidential
    domain_id: str
    owner_id: str
    quality_score: float | None = None
    tags: list[str] = Field(default_factory=list)
    last_updated: str | None = None


class DatasetPreviewRequest(BaseModel):
    """Request to preview dataset data."""

    dataset_id: str
    limit: int = Field(default=100, le=1000, description="Max rows to preview")
    apply_privacy: bool = Field(default=True, description="Apply privacy controls")


class DatasetPreviewResponse(BaseModel):
    """Dataset preview with privacy controls applied."""

    dataset_id: str
    columns: list[str]
    sample_data: list[dict[str, Any]]
    row_count: int
    privacy_applied: bool
    notice: str = ""


class PipelineCreate(BaseModel):
    """Request to create a data pipeline."""

    name: str
    description: str
    source_datasets: list[str]
    target_dataset: str
    transformations: list[dict[str, Any]] = Field(default_factory=list)
    schedule: str = Field(default="@daily", description="Cron or preset schedule")
    owner_id: str


class PipelineResponse(BaseModel):
    """Created pipeline information."""

    pipeline_id: uuid.UUID
    name: str
    status: str  # draft, pending_approval, active
    airflow_dag_id: str | None = None
    decision_id: uuid.UUID | None = None


# ──── Endpoints ───────────────────────────────────────────────────


@router.post("/access-requests")
async def create_access_request(
    request: AccessRequestCreate,
    service: DecisionServiceDep,
    user: UserContext = Depends(get_current_user),
) -> AccessRequestResponse:
    """Create an access request for a dataset.

    Triggers governance approval workflow via decision engine.
    """
    from odg_core.enums import DecisionType

    # Create governance decision for access request
    decision = await service.create_decision(
        decision_type=DecisionType.ACCESS_GRANT,
        title=f"Access request for {request.dataset_id}",
        description=f"Purpose: {request.purpose}\nRequester: {request.requester_id}",
        domain_id="data-access",  # TODO: Derive from dataset
        created_by=request.requester_id,
        metadata={
            "dataset_id": request.dataset_id,
            "purpose": request.purpose,
            "duration_days": request.duration_days,
            "justification": request.justification,
        },
    )

    return AccessRequestResponse(
        request_id=uuid.uuid4(),  # TODO: Create actual access_requests table
        dataset_id=request.dataset_id,
        requester_id=request.requester_id,
        purpose=request.purpose,
        status="pending",
        created_at=decision.created_at.isoformat(),
        decision_id=decision.id,
    )


@router.get("/access-requests/{request_id}")
async def get_access_request(
    request_id: uuid.UUID,
    service: DecisionServiceDep,
    user: UserContext = Depends(get_current_user),
) -> AccessRequestResponse:
    """Get access request status."""
    # TODO: Query from access_requests table
    # For now, return mock response
    raise HTTPException(status_code=501, detail="Not implemented - access_requests table needed")


@router.get("/datasets/search")
async def search_datasets(
    user: UserContext = Depends(get_current_user),
    query: str = Query(default="", description="Search query"),
    domain: str | None = None,
    layer: str | None = None,
    classification: str | None = None,
    limit: int = Query(default=50, le=200),
) -> list[DatasetSearchResult]:
    """Search datasets for discovery.

    Supports filtering by domain, layer, classification, and text search.
    """
    # TODO: Implement actual search against DataHub or catalog
    # For now, return mock results
    mock_results = [
        DatasetSearchResult(
            dataset_id="gold.customers",
            name="customers",
            description="Customer master data with PII",
            layer="gold",
            classification="sensitive",
            domain_id="crm",
            owner_id="data-team",
            quality_score=0.95,
            tags=["pii", "crm", "master-data"],
            last_updated="2024-02-08T10:00:00Z",
        ),
        DatasetSearchResult(
            dataset_id="gold.transactions",
            name="transactions",
            description="Transaction fact table",
            layer="gold",
            classification="internal",
            domain_id="finance",
            owner_id="finance-team",
            quality_score=0.98,
            tags=["finance", "transactions"],
            last_updated="2024-02-08T09:30:00Z",
        ),
    ]

    # Apply filters
    results = mock_results
    if domain:
        results = [r for r in results if r.domain_id == domain]
    if layer:
        results = [r for r in results if r.layer == layer]
    if classification:
        results = [r for r in results if r.classification == classification]
    if query:
        results = [r for r in results if query.lower() in r.name.lower() or query.lower() in r.description.lower()]

    return results[:limit]


@router.post("/datasets/preview")
async def preview_dataset(
    request: DatasetPreviewRequest,
    user: UserContext = Depends(get_current_user),
) -> DatasetPreviewResponse:
    """Preview dataset data with privacy controls.

    Applies masking/anonymization based on classification.
    """
    # TODO: Implement actual data preview with privacy controls
    # For now, return mock preview

    return DatasetPreviewResponse(
        dataset_id=request.dataset_id,
        columns=["id", "name", "email", "age"],
        sample_data=[
            {"id": "****", "name": "John ****", "email": "j***@example.com", "age": 25},
            {"id": "****", "name": "Jane ****", "email": "j***@example.com", "age": 30},
        ],
        row_count=2,
        privacy_applied=request.apply_privacy,
        notice="PII fields masked due to SENSITIVE classification" if request.apply_privacy else "",
    )


@router.post("/pipelines")
async def create_pipeline(
    request: PipelineCreate,
    service: DecisionServiceDep,
    user: UserContext = Depends(require_role(RACIRole.ACCOUNTABLE)),
) -> PipelineResponse:
    """Create a data pipeline (generates Airflow DAG).

    Triggers approval workflow for pipeline creation.
    """
    from odg_core.enums import DecisionType

    # Create governance decision for pipeline creation
    decision = await service.create_decision(
        decision_type=DecisionType.SCHEMA_CHANGE,  # Or new PIPELINE_CREATE type
        title=f"Create pipeline: {request.name}",
        description=request.description,
        domain_id="data-engineering",
        created_by=request.owner_id,
        metadata={
            "pipeline_name": request.name,
            "source_datasets": request.source_datasets,
            "target_dataset": request.target_dataset,
            "schedule": request.schedule,
            "transformations": request.transformations,
        },
    )

    pipeline_id = uuid.uuid4()

    return PipelineResponse(
        pipeline_id=pipeline_id,
        name=request.name,
        status="pending_approval",
        airflow_dag_id=None,  # Generated after approval
        decision_id=decision.id,
    )


@router.get("/health")
async def self_service_health() -> dict[str, str]:
    """Health check for self-service APIs."""
    return {"status": "ok", "service": "self-service"}
