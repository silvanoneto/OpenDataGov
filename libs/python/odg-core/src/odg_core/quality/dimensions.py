"""DAMA DMBOK dimension scoring (ADR-052).

Maps Great Expectations results to the 6 DAMA quality dimensions:
completeness, accuracy, consistency, timeliness, uniqueness, validity.
"""

from __future__ import annotations

from typing import Any

from odg_core.enums import DAMADimension

# Mapping: GE expectation type prefix → DAMA dimension
_EXPECTATION_DIMENSION_MAP: dict[str, DAMADimension] = {
    "expect_column_values_to_not_be_null": DAMADimension.COMPLETENESS,
    "expect_table_row_count_to_be_between": DAMADimension.COMPLETENESS,
    "expect_column_values_to_be_between": DAMADimension.ACCURACY,
    "expect_column_mean_to_be_between": DAMADimension.ACCURACY,
    "expect_column_values_to_match_regex": DAMADimension.VALIDITY,
    "expect_column_values_to_be_in_set": DAMADimension.VALIDITY,
    "expect_column_values_to_be_of_type": DAMADimension.VALIDITY,
    "expect_column_values_to_be_unique": DAMADimension.UNIQUENESS,
    "expect_compound_columns_to_be_unique": DAMADimension.UNIQUENESS,
    "expect_column_pair_values_to_be_equal": DAMADimension.CONSISTENCY,
    "expect_column_values_to_match_strftime_format": DAMADimension.TIMELINESS,
}


class DAMAScorer:
    """Compute per-dimension scores from Great Expectations validation results."""

    def __init__(self, dimension_map: dict[str, DAMADimension] | None = None) -> None:
        self._map = dimension_map or _EXPECTATION_DIMENSION_MAP

    def score(self, results: list[dict[str, Any]]) -> dict[str, float]:
        """Score each DAMA dimension from a list of expectation results.

        Each result dict must have:
          - expectation_type: str
          - success: bool

        Returns a dict of dimension → score (0.0 to 1.0).
        """
        dimension_pass: dict[str, int] = {}
        dimension_total: dict[str, int] = {}

        for result in results:
            exp_type = result.get("expectation_type", "")
            dimension = self._map.get(exp_type)
            if dimension is None:
                continue

            dim_key = dimension.value
            dimension_total[dim_key] = dimension_total.get(dim_key, 0) + 1
            if result.get("success", False):
                dimension_pass[dim_key] = dimension_pass.get(dim_key, 0) + 1

        scores: dict[str, float] = {}
        for dim in DAMADimension:
            total = dimension_total.get(dim.value, 0)
            if total == 0:
                scores[dim.value] = 1.0  # No expectations = assumed passing
            else:
                scores[dim.value] = dimension_pass.get(dim.value, 0) / total

        return scores

    def overall_score(self, dimension_scores: dict[str, float]) -> float:
        """Compute overall DQ score as mean of all dimension scores."""
        if not dimension_scores:
            return 0.0
        return sum(dimension_scores.values()) / len(dimension_scores)
