"""OpenLineage event models (ADR-060)."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime by Pydantic
from typing import Any

from pydantic import BaseModel, Field

from odg_core.models import _utcnow


class LineageDataset(BaseModel):
    """OpenLineage dataset reference."""

    namespace: str
    name: str
    facets: dict[str, Any] = Field(default_factory=dict)


class LineageJob(BaseModel):
    """OpenLineage job reference."""

    namespace: str = "opendatagov"
    name: str


class LineageRunEvent(BaseModel):
    """OpenLineage RunEvent for lineage tracking."""

    event_type: str = "COMPLETE"  # START, RUNNING, COMPLETE, FAIL, ABORT
    event_time: datetime = Field(default_factory=_utcnow)
    run: dict[str, str] = Field(default_factory=dict)
    job: LineageJob
    inputs: list[LineageDataset] = Field(default_factory=list)
    outputs: list[LineageDataset] = Field(default_factory=list)
    producer: str = "opendatagov"
    schema_url: str = "https://openlineage.io/spec/1-0-5/OpenLineage.json#/definitions/RunEvent"
