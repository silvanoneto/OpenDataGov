"""GraphQL resolvers for data quality reports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from odg_core.db.tables import QualityReportRow
from odg_core.graphql.types.quality import QualityDimensionGQL, QualityReportGQL

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_quality_report(session: AsyncSession, dataset_id: str) -> QualityReportGQL | None:
    """Resolve latest quality report for a dataset."""
    # Get most recent report for dataset
    stmt = (
        select(QualityReportRow)
        .where(QualityReportRow.dataset_id == dataset_id)
        .order_by(QualityReportRow.created_at.desc())
        .limit(1)
    )

    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    # Convert dimension scores to QualityDimensionGQL list
    dimensions = []
    if row.dimension_scores:
        for dim_name, dim_data in row.dimension_scores.items():
            if isinstance(dim_data, dict):
                dimensions.append(
                    QualityDimensionGQL(
                        dimension=dim_name,
                        passed=dim_data.get("passed", False),
                        score=dim_data.get("score", 0.0),
                        message=dim_data.get("message"),
                    )
                )

    # Calculate overall passed status
    passed = row.expectations_failed == 0 if row.expectations_total > 0 else True

    return QualityReportGQL(
        id=row.id,
        dataset_id=row.dataset_id,
        overall_score=row.dq_score,
        passed=passed,
        dimensions=dimensions,
        created_at=row.created_at,
    )
