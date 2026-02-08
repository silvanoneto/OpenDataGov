"""Pydantic request/response schemas for quality-gate API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ValidateRequest(BaseModel):
    """Request to validate a dataset against a quality suite."""

    dataset_id: str = Field(min_length=1, max_length=200)
    domain_id: str = Field(min_length=1, max_length=100)
    layer: str = Field(min_length=1, max_length=20)
    suite_name: str = Field(default="default", max_length=200)
    triggered_by: uuid.UUID | None = None


class QualityReportResponse(BaseModel):
    """Response containing a quality evaluation report."""

    id: uuid.UUID
    dataset_id: str
    domain_id: str
    layer: str
    suite_name: str
    dq_score: float
    dimension_scores: dict[str, float]
    expectations_passed: int
    expectations_failed: int
    expectations_total: int
    created_at: datetime
    triggered_by: uuid.UUID | None = None
