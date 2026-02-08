"""Quality gate API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from quality_gate.api.schemas import QualityReportResponse, ValidateRequest
from quality_gate.engine import QualityEngine

router = APIRouter(prefix="/api/v1/quality", tags=["quality"])

_engine = QualityEngine()


@router.post("/validate", status_code=201)
async def validate_dataset(body: ValidateRequest) -> QualityReportResponse:
    """Validate a dataset against quality expectations and return a DQ report."""
    report = _engine.validate(
        dataset_id=body.dataset_id,
        domain_id=body.domain_id,
        layer=body.layer,
        suite_name=body.suite_name,
        triggered_by=body.triggered_by,
    )
    return QualityReportResponse(
        id=report.id,
        dataset_id=report.dataset_id,
        domain_id=report.domain_id,
        layer=report.layer,
        suite_name=report.suite_name,
        dq_score=report.dq_score,
        dimension_scores=report.dimension_scores,
        expectations_passed=report.expectations_passed,
        expectations_failed=report.expectations_failed,
        expectations_total=report.expectations_total,
        created_at=report.created_at,
        triggered_by=report.triggered_by,
    )


@router.get("/reports/{report_id}", responses={404: {"description": "Report not found"}})
async def get_report(report_id: uuid.UUID) -> QualityReportResponse:
    """Get a quality report by ID."""
    report = _engine.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return QualityReportResponse(
        id=report.id,
        dataset_id=report.dataset_id,
        domain_id=report.domain_id,
        layer=report.layer,
        suite_name=report.suite_name,
        dq_score=report.dq_score,
        dimension_scores=report.dimension_scores,
        expectations_passed=report.expectations_passed,
        expectations_failed=report.expectations_failed,
        expectations_total=report.expectations_total,
        created_at=report.created_at,
        triggered_by=report.triggered_by,
    )
