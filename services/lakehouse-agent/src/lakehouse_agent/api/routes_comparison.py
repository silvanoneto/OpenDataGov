"""Version comparison API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from odg_core.storage.iceberg_catalog import IcebergCatalog
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/compare", tags=["comparison"])


class SchemaComparisonResult(BaseModel):
    """Schema comparison result between two versions."""

    from_version: str
    to_version: str
    added_columns: list[str]
    removed_columns: list[str]
    common_columns: list[str]
    type_changes: dict[str, dict[str, str]]


class DataComparisonResult(BaseModel):
    """Data comparison result between two versions."""

    from_version: str
    to_version: str
    rows_from: int
    rows_to: int
    rows_added: int
    rows_removed: int
    sample_diff: dict[str, Any]


class ModelComparisonResult(BaseModel):
    """Model performance comparison between versions."""

    model_name: str
    from_version: int
    to_version: int
    metrics_diff: dict[str, dict[str, float]]
    training_data_changed: bool
    feature_importance_diff: dict[str, float] | None = None


@router.get("/datasets/{namespace}/{table}/schema", response_model=SchemaComparisonResult)
async def compare_dataset_schema(
    namespace: str, table: str, from_version: str, to_version: str
) -> SchemaComparisonResult:
    """Compare schemas between two dataset versions.

    Args:
        namespace: Dataset namespace (e.g., 'gold', 'silver')
        table: Table name
        from_version: Source snapshot ID
        to_version: Target snapshot ID

    Returns:
        Schema comparison showing added/removed columns and type changes
    """
    try:
        iceberg = IcebergCatalog()
        table_obj = iceberg.catalog.load_table(f"{namespace}.{table}")

        # Get schemas from both snapshots
        snapshot_from = table_obj.snapshot(int(from_version))
        snapshot_to = table_obj.snapshot(int(to_version))

        if not snapshot_from:
            raise HTTPException(404, f"Snapshot {from_version} not found")
        if not snapshot_to:
            raise HTTPException(404, f"Snapshot {to_version} not found")

        schema_from = {field.name: str(field.field_type) for field in snapshot_from.schema().fields}
        schema_to = {field.name: str(field.field_type) for field in snapshot_to.schema().fields}

        added_columns = list(set(schema_to.keys()) - set(schema_from.keys()))
        removed_columns = list(set(schema_from.keys()) - set(schema_to.keys()))
        common_columns = list(set(schema_from.keys()) & set(schema_to.keys()))

        # Detect type changes in common columns
        type_changes = {
            col: {"from": schema_from[col], "to": schema_to[col]}
            for col in common_columns
            if schema_from[col] != schema_to[col]
        }

        return SchemaComparisonResult(
            from_version=from_version,
            to_version=to_version,
            added_columns=added_columns,
            removed_columns=removed_columns,
            common_columns=common_columns,
            type_changes=type_changes,
        )

    except ValueError as e:
        raise HTTPException(400, f"Invalid snapshot ID: {e}") from e
    except Exception as e:
        raise HTTPException(500, f"Error comparing schemas: {e}") from e


@router.get("/datasets/{namespace}/{table}/data", response_model=DataComparisonResult)
async def compare_dataset_data(
    namespace: str, table: str, from_version: str, to_version: str, sample_size: int = 5
) -> DataComparisonResult:
    """Compare data between two dataset versions.

    Args:
        namespace: Dataset namespace
        table: Table name
        from_version: Source snapshot ID
        to_version: Target snapshot ID
        sample_size: Number of sample rows to include in diff

    Returns:
        Data comparison showing row count changes and sample differences
    """
    try:
        iceberg = IcebergCatalog()

        # Time-travel to both versions
        df_from = iceberg.time_travel(namespace, table, from_version)
        df_to = iceberg.time_travel(namespace, table, to_version)

        rows_from = len(df_from)
        rows_to = len(df_to)

        return DataComparisonResult(
            from_version=from_version,
            to_version=to_version,
            rows_from=rows_from,
            rows_to=rows_to,
            rows_added=max(0, rows_to - rows_from),
            rows_removed=max(0, rows_from - rows_to),
            sample_diff={
                "from_sample": df_from.head(sample_size).to_dict(orient="records"),
                "to_sample": df_to.head(sample_size).to_dict(orient="records"),
            },
        )

    except Exception as e:
        raise HTTPException(500, f"Error comparing data: {e}") from e


@router.get("/models/{model_name}/performance", response_model=ModelComparisonResult)
async def compare_model_performance(model_name: str, from_version: int, to_version: int) -> ModelComparisonResult:
    """Compare performance metrics between model versions.

    Args:
        model_name: Name of the model
        from_version: Source model version
        to_version: Target model version

    Returns:
        Metrics comparison and training data change detection
    """
    try:
        from odg_core.compliance.model_card import ModelCard

        async def _get_model_card(name: str, version: int) -> ModelCard | None:
            """Retrieve a model card by name and version from MLflow/storage."""
            # TODO: implement actual retrieval from MLflow or database
            return None

        # Get model cards for both versions
        card_from = await _get_model_card(model_name, from_version)
        card_to = await _get_model_card(model_name, to_version)

        if not card_from:
            raise HTTPException(404, f"Model {model_name} version {from_version} not found")
        if not card_to:
            raise HTTPException(404, f"Model {model_name} version {to_version} not found")

        # Compare metrics (metrics is list[ModelCardMetrics] with metric_name/value)
        from_metrics = {m.metric_name: m.value for m in card_from.metrics}
        to_metrics = {m.metric_name: m.value for m in card_to.metrics}
        all_metrics = set(from_metrics.keys()) | set(to_metrics.keys())
        metrics_diff: dict[str, dict[str, float]] = {}

        for metric in all_metrics:
            val_from = from_metrics.get(metric, 0.0)
            val_to = to_metrics.get(metric, 0.0)
            metrics_diff[metric] = {
                "from": val_from,
                "to": val_to,
                "delta": val_to - val_from,
                "percent_change": ((val_to - val_from) / val_from * 100) if val_from != 0 else 0.0,
            }

        feature_importance_diff = None

        return ModelComparisonResult(
            model_name=model_name,
            from_version=from_version,
            to_version=to_version,
            metrics_diff=metrics_diff,
            training_data_changed=(card_from.training_dataset_version != card_to.training_dataset_version),
            feature_importance_diff=feature_importance_diff,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error comparing models: {e}") from e


@router.get("/pipelines/{pipeline_id}/versions")
async def compare_pipeline_versions(pipeline_id: str, from_version: int, to_version: int) -> dict[str, Any]:
    """Compare two versions of a pipeline.

    Args:
        pipeline_id: Pipeline identifier
        from_version: Source pipeline version
        to_version: Target pipeline version

    Returns:
        Comparison of DAG structure, code, and execution metrics
    """
    try:
        from odg_core.db.tables import PipelineVersionRow
        from sqlalchemy import select

        from lakehouse_agent.api.dependencies import get_db

        # This is a simplified version - in production, inject db session properly
        async with get_db() as db:
            result_from = await db.execute(
                select(PipelineVersionRow).where(
                    PipelineVersionRow.pipeline_id == pipeline_id, PipelineVersionRow.version == from_version
                )
            )
            version_from = result_from.scalar_one_or_none()

            result_to = await db.execute(
                select(PipelineVersionRow).where(
                    PipelineVersionRow.pipeline_id == pipeline_id, PipelineVersionRow.version == to_version
                )
            )
            version_to = result_to.scalar_one_or_none()

            if not version_from or not version_to:
                raise HTTPException(404, "Pipeline version not found")

            return {
                "pipeline_id": pipeline_id,
                "from_version": from_version,
                "to_version": to_version,
                "dag_changed": version_from.dag_hash != version_to.dag_hash,
                "code_changed": (
                    version_from.transformation_hash != version_to.transformation_hash
                    if version_from.transformation_hash and version_to.transformation_hash
                    else None
                ),
                "git_commits": {"from": version_from.git_commit, "to": version_to.git_commit},
                "created_at": {"from": version_from.created_at.isoformat(), "to": version_to.created_at.isoformat()},
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error comparing pipeline versions: {e}") from e
