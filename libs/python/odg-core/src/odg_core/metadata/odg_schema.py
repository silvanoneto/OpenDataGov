"""ODG enriched dataset metadata schema (ADR-041).

Extends basic dataset metadata with governance, quality, and privacy information.
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003 — needed at runtime by Pydantic

from pydantic import BaseModel, Field

from odg_core.enums import DataClassification, MedallionLayer


class ODGDatasetMetadata(BaseModel):
    """Enriched dataset metadata for the ODG catalog."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    dataset_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="")
    domain_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=200)
    layer: MedallionLayer = MedallionLayer.BRONZE
    classification: DataClassification = DataClassification.INTERNAL
    tags: list[str] = Field(default_factory=list)
    schema_fields: list[DatasetField] = Field(default_factory=list)
    quality_score: float | None = None
    contract_id: uuid.UUID | None = None
    jurisdiction: str | None = None
    pii_columns: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DatasetField(BaseModel):
    """Individual field within a dataset schema."""

    name: str
    data_type: str
    description: str = ""
    is_pii: bool = False
    is_nullable: bool = True
