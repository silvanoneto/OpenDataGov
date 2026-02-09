"""Example: Completeness check for data quality validation."""

from __future__ import annotations

from typing import Any

from odg_core.quality.base_check import BaseCheck, CheckResult, DAMADimension, Severity


class CompletenessCheck(BaseCheck):
    """Validates data completeness (non-null values).

    Checks that data has no missing/null values above the threshold.
    Follows DAMA Completeness dimension (ADR-050).
    """

    def __init__(self, threshold: float = 0.95) -> None:
        """Initialize completeness check.

        Args:
            threshold: Minimum completeness score required (default: 0.95)
        """
        self.threshold = threshold

    async def validate(self, data: Any) -> CheckResult:
        """Validate completeness of data.

        Args:
            data: pandas DataFrame to validate

        Returns:
            CheckResult with completeness score
        """
        try:
            import pandas as pd

            if not isinstance(data, pd.DataFrame):
                return CheckResult(
                    passed=False,
                    score=0.0,
                    failures=["Data must be a pandas DataFrame"],
                )

            total_cells = data.size
            if total_cells == 0:
                return CheckResult(
                    passed=True,
                    score=1.0,
                    failures=[],
                    row_count=0,
                    failure_count=0,
                )

            missing_cells = data.isnull().sum().sum()
            completeness_score = 1.0 - (missing_cells / total_cells)

            passed = completeness_score >= self.threshold
            failures = []
            if not passed:
                failures.append(f"Completeness score {completeness_score:.2%} below threshold {self.threshold:.2%}")
                # Add per-column breakdown
                missing_per_col = data.isnull().sum()
                for col, count in missing_per_col[missing_per_col > 0].items():
                    pct = (count / len(data)) * 100
                    failures.append(f"Column '{col}': {count} missing ({pct:.1f}%)")

            return CheckResult(
                passed=passed,
                score=completeness_score,
                failures=failures,
                metadata={
                    "threshold": self.threshold,
                    "total_cells": total_cells,
                    "missing_cells": int(missing_cells),
                },
                row_count=len(data),
                failure_count=int(missing_cells),
            )

        except ImportError:
            return CheckResult(
                passed=False,
                score=0.0,
                failures=["pandas is required for CompletenessCheck"],
            )
        except Exception as e:
            return CheckResult(
                passed=False,
                score=0.0,
                failures=[f"Validation error: {e}"],
            )

    def get_dimension(self) -> DAMADimension:
        """Return DAMA dimension."""
        return DAMADimension.COMPLETENESS

    def get_severity(self) -> Severity:
        """Return severity level."""
        return Severity.ERROR
