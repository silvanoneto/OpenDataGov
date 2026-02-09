"""GraphQL types for data quality."""

import uuid
from datetime import datetime

import strawberry


@strawberry.type
class QualityDimensionGQL:
    """A single quality dimension result."""

    dimension: str
    passed: bool
    score: float
    message: str | None = None


@strawberry.type
class QualityReportGQL:
    """Data quality validation report."""

    id: uuid.UUID
    dataset_id: str
    overall_score: float
    passed: bool
    dimensions: list[QualityDimensionGQL]
    created_at: datetime
