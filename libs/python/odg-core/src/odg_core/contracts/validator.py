"""Validate data against a data contract schema (ADR-051)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from odg_core.models import ColumnDefinition, DataContract


def validate_data(
    contract: DataContract,
    actual_columns: list[dict[str, str]],
) -> dict[str, Any]:
    """Validate actual column metadata against a contract schema.

    Args:
        contract: The data contract to validate against.
        actual_columns: List of dicts with 'name' and 'data_type' keys.

    Returns:
        Dict with 'valid', 'missing_columns', 'type_mismatches', 'extra_columns'.
    """
    expected: dict[str, ColumnDefinition] = {col.name: col for col in contract.schema_definition.columns}
    actual_map: dict[str, str] = {col["name"]: col.get("data_type", "") for col in actual_columns}

    missing = [name for name in expected if name not in actual_map]
    extra = [name for name in actual_map if name not in expected]
    type_mismatches = []

    for name, col_def in expected.items():
        if name in actual_map and actual_map[name] != col_def.data_type:
            type_mismatches.append(
                {
                    "column": name,
                    "expected": col_def.data_type,
                    "actual": actual_map[name],
                }
            )

    valid = not missing and not type_mismatches

    return {
        "valid": valid,
        "missing_columns": missing,
        "type_mismatches": type_mismatches,
        "extra_columns": extra,
    }
