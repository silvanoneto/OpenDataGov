"""AI model card template (ADR-111).

Structured documentation for AI/ML models used in the platform,
following the Model Cards for Model Reporting framework.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from odg_core.enums import AIRiskLevel


class ModelCardMetrics(BaseModel):
    """Performance metrics for a model card."""

    metric_name: str
    value: float
    dataset: str = ""
    description: str = ""


class ModelCardEthics(BaseModel):
    """Ethical considerations for a model card."""

    intended_use: str = ""
    out_of_scope_use: str = ""
    known_biases: list[str] = Field(default_factory=list)
    mitigation_strategies: list[str] = Field(default_factory=list)


class PerformanceSnapshot(BaseModel):
    """Performance metrics snapshot for model history tracking."""

    timestamp: datetime
    dataset_id: str  # Dataset used for validation/evaluation
    metrics: dict[str, float]  # e.g., {accuracy: 0.95, f1: 0.92, ...}
    drift_score: float | None = None


class ModelCard(BaseModel):
    """Structured AI model documentation (Model Cards for Model Reporting).

    Fields align with EU AI Act transparency and NIST AI RMF documentation
    requirements.
    """

    model_name: str
    model_version: str
    owner: str
    description: str = ""

    # Classification
    risk_level: AIRiskLevel = AIRiskLevel.MINIMAL
    expert_capability: str = ""

    # Technical details
    model_type: str = ""
    training_data_description: str = ""
    evaluation_data_description: str = ""
    metrics: list[ModelCardMetrics] = Field(default_factory=list)

    # Ethical and governance
    ethics: ModelCardEthics = Field(default_factory=ModelCardEthics)
    limitations: list[str] = Field(default_factory=list)
    regulatory_requirements: list[str] = Field(default_factory=list)

    # MLflow integration (Phase 1: MLOps Foundation)
    mlflow_experiment_id: str | None = None
    mlflow_run_id: str | None = None
    mlflow_model_uri: str | None = None
    mlflow_version: int | None = None
    mlflow_stage: str | None = None  # None, Staging, Production, Archived

    # Training data lineage (versioning)
    training_dataset_id: str | None = Field(None, description="Dataset ID used for training (e.g., 'gold/customers')")
    training_dataset_version: str | None = Field(
        None, description="Snapshot/version of the training dataset (e.g., Iceberg snapshot ID)"
    )
    training_timestamp: datetime | None = Field(None, description="Timestamp when the model was trained")

    # Model ancestry (for retraining lineage)
    parent_model_version: str | None = Field(None, description="Previous model version if this is a retrained model")
    is_retrained: bool = Field(default=False, description="Whether this model is a result of retraining")

    # Training environment tracking
    training_environment: dict[str, str] | None = Field(
        None,
        description="Training environment details (Python, libraries, CUDA versions, Docker image)",
        examples=[
            {
                "python_version": "3.13",
                "sklearn_version": "1.3.0",
                "cuda_version": "12.0",
                "docker_image": "sha256:abc123...",
            }
        ],
    )

    # Performance history tracking
    performance_history: list[PerformanceSnapshot] | None = Field(
        None, description="Historical performance metrics and drift scores over time"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    last_reviewed_at: datetime | None = None
    approved_by: str = ""
