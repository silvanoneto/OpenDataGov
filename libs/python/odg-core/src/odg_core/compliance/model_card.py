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

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    last_reviewed_at: datetime | None = None
    approved_by: str = ""
