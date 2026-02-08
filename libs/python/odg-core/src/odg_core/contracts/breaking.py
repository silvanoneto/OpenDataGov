"""Breaking vs non-breaking change detection for data contracts (ADR-051)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from odg_core.models import ColumnDefinition, DataContractSchema


def _classify_new_column(
    name: str,
    new_col: ColumnDefinition,
    breaking: list[dict[str, str]],
    non_breaking: list[dict[str, str]],
) -> None:
    """Classify a column that exists only in the new schema."""
    if not new_col.nullable:
        breaking.append({"type": "non_nullable_column_added", "column": name})
    else:
        non_breaking.append({"type": "nullable_column_added", "column": name})


def _classify_modified_column(
    name: str,
    old_col: ColumnDefinition,
    new_col: ColumnDefinition,
    breaking: list[dict[str, str]],
) -> None:
    """Classify changes for a column that exists in both schemas."""
    if old_col.data_type != new_col.data_type:
        breaking.append(
            {
                "type": "type_changed",
                "column": name,
                "old_type": old_col.data_type,
                "new_type": new_col.data_type,
            }
        )
    if old_col.nullable and not new_col.nullable:
        breaking.append({"type": "nullable_to_non_nullable", "column": name})


def detect_breaking_changes(
    old_schema: DataContractSchema,
    new_schema: DataContractSchema,
) -> dict[str, Any]:
    """Compare two contract schema versions and classify changes.

    Breaking changes:
      - Column removed
      - Column type changed
      - Non-nullable column added (without default)

    Non-breaking changes:
      - Nullable column added
      - Column description changed

    Returns:
        Dict with 'has_breaking', 'breaking_changes', 'non_breaking_changes'.
    """
    old_cols = {col.name: col for col in old_schema.columns}
    new_cols = {col.name: col for col in new_schema.columns}

    breaking: list[dict[str, str]] = []
    non_breaking: list[dict[str, str]] = []

    # Removed columns are breaking
    for name in old_cols:
        if name not in new_cols:
            breaking.append({"type": "column_removed", "column": name})

    for name, new_col in new_cols.items():
        if name not in old_cols:
            _classify_new_column(name, new_col, breaking, non_breaking)
        else:
            _classify_modified_column(name, old_cols[name], new_col, breaking)

    return {
        "has_breaking": len(breaking) > 0,
        "breaking_changes": breaking,
        "non_breaking_changes": non_breaking,
    }
