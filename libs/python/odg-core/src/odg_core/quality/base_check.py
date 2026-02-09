"""Base class for data quality checks (ADR-131).

All quality checks must extend BaseCheck and implement validate().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DAMADimension(StrEnum):
    """DAMA data quality dimensions (ADR-050)."""

    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    VALIDITY = "validity"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    UNIQUENESS = "uniqueness"


class Severity(StrEnum):
    """Severity level for check failures."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CheckResult(BaseModel):
    """Result of a data quality check."""

    passed: bool
    score: float = Field(ge=0.0, le=1.0, description="Quality score (0.0-1.0)")
    failures: list[str] = Field(default_factory=list, description="List of failure messages")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional check metadata")
    row_count: int | None = Field(default=None, description="Number of rows checked")
    failure_count: int | None = Field(default=None, description="Number of failures")


class BaseCheck(ABC):
    """Abstract base class for data quality checks.

    Implements the plugin pattern for extensible quality validation.
    All checks follow DAMA dimensions (ADR-050).

    Example:
        class CompletenessCheck(BaseCheck):
            async def validate(self, data: pd.DataFrame) -> CheckResult:
                missing = data.isnull().sum().sum()
                total = data.size
                score = 1.0 - (missing / total)
                return CheckResult(
                    passed=score >= 0.95,
                    score=score,
                    failures=[f"{missing} missing values"] if score < 0.95 else [],
                )

            def get_dimension(self) -> DAMADimension:
                return DAMADimension.COMPLETENESS

            def get_severity(self) -> Severity:
                return Severity.ERROR
    """

    @abstractmethod
    async def validate(self, data: Any) -> CheckResult:
        """Validate data and return check result.

        Args:
            data: Data to validate (DataFrame, dict, file path, etc.)

        Returns:
            CheckResult with pass/fail status and score

        Raises:
            Exception: If validation fails unexpectedly
        """
        ...

    @abstractmethod
    def get_dimension(self) -> DAMADimension:
        """Return the DAMA dimension this check validates."""
        ...

    @abstractmethod
    def get_severity(self) -> Severity:
        """Return the severity level for check failures."""
        ...

    def get_name(self) -> str:
        """Return human-readable check name (defaults to class name)."""
        return self.__class__.__name__

    def get_description(self) -> str:
        """Return check description (defaults to docstring)."""
        return (self.__class__.__doc__ or "").strip()

    async def initialize(self) -> None:  # noqa: B027
        """Initialize check (load config, connect to resources, etc.)."""

    async def shutdown(self) -> None:  # noqa: B027
        """Gracefully shutdown check."""
