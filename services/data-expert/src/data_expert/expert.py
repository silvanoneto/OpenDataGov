"""Mock data expert implementation (ADR-034)."""

from __future__ import annotations

import random
from typing import ClassVar

from odg_core.enums import ExpertCapability
from odg_core.expert import BaseExpert, ExpertRequest, ExpertResponse


class MockDataExpert(BaseExpert):
    """Mock implementation of a data expert.

    Supports SQL generation, data analysis, data profiling, and schema
    inference.  All responses are synthetic -- suitable for development
    and integration testing.  Follows the "AI recommends, human decides"
    paradigm (ADR-011).
    """

    _CAPABILITIES: ClassVar[list[str]] = [
        ExpertCapability.SQL_GENERATION,
        ExpertCapability.DATA_ANALYSIS,
        ExpertCapability.DATA_PROFILING,
        ExpertCapability.SCHEMA_INFERENCE,
    ]

    # ------------------------------------------------------------------ #
    # BaseExpert interface
    # ------------------------------------------------------------------ #

    async def process(self, request: ExpertRequest) -> ExpertResponse:
        """Process a request and return a mock recommendation."""
        capability = request.parameters.get("capability", "")
        confidence = round(random.uniform(0.7, 0.95), 2)

        if capability == ExpertCapability.SQL_GENERATION:
            return self._sql_generation(request, confidence)
        if capability == ExpertCapability.DATA_ANALYSIS:
            return self._data_analysis(request, confidence)
        if capability == ExpertCapability.DATA_PROFILING:
            return self._data_profiling(request, confidence)
        if capability == ExpertCapability.SCHEMA_INFERENCE:
            return self._schema_inference(request, confidence)

        return ExpertResponse(
            recommendation=f"Processed query: {request.query}",
            confidence=confidence,
            reasoning="No specific capability matched; returning generic response.",
            metadata={"capability": capability},
            requires_approval=True,
        )

    def get_capabilities(self) -> list[str]:
        """Return the four supported capabilities."""
        return list(self._CAPABILITIES)

    async def health_check(self) -> bool:
        """Mock health check -- always healthy."""
        return True

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sql_generation(request: ExpertRequest, confidence: float) -> ExpertResponse:
        table = request.context.get("table", "my_table")
        sql = f"SELECT * FROM {table} WHERE 1=1 /* generated for: {request.query} */"
        return ExpertResponse(
            recommendation=sql,
            confidence=confidence,
            reasoning=f"Generated SQL query based on the request: '{request.query}'.",
            metadata={"capability": ExpertCapability.SQL_GENERATION, "table": table},
            requires_approval=True,
        )

    @staticmethod
    def _data_analysis(request: ExpertRequest, confidence: float) -> ExpertResponse:
        return ExpertResponse(
            recommendation=(
                f"Analysis summary for '{request.query}': "
                "The dataset contains 1 000 rows across 12 columns. "
                "Key observations: 3 columns have >5% null values, "
                "distribution is approximately normal for numeric fields."
            ),
            confidence=confidence,
            reasoning="Performed mock statistical analysis on the dataset.",
            metadata={
                "capability": ExpertCapability.DATA_ANALYSIS,
                "row_count": 1000,
                "column_count": 12,
                "null_columns": 3,
            },
            requires_approval=True,
        )

    @staticmethod
    def _data_profiling(request: ExpertRequest, confidence: float) -> ExpertResponse:
        return ExpertResponse(
            recommendation=(
                f"Profiling stats for '{request.query}': completeness=0.95, uniqueness=0.87, consistency=0.92."
            ),
            confidence=confidence,
            reasoning="Computed mock data-quality profiling metrics.",
            metadata={
                "capability": ExpertCapability.DATA_PROFILING,
                "completeness": 0.95,
                "uniqueness": 0.87,
                "consistency": 0.92,
            },
            requires_approval=True,
        )

    @staticmethod
    def _schema_inference(request: ExpertRequest, confidence: float) -> ExpertResponse:
        return ExpertResponse(
            recommendation=(
                f"Inferred schema for '{request.query}': "
                "id (INTEGER, PK), name (VARCHAR), created_at (TIMESTAMP), "
                "value (FLOAT), is_active (BOOLEAN)."
            ),
            confidence=confidence,
            reasoning="Inferred column types from mock sample data.",
            metadata={
                "capability": ExpertCapability.SCHEMA_INFERENCE,
                "columns": [
                    {"name": "id", "type": "INTEGER", "primary_key": True},
                    {"name": "name", "type": "VARCHAR", "primary_key": False},
                    {"name": "created_at", "type": "TIMESTAMP", "primary_key": False},
                    {"name": "value", "type": "FLOAT", "primary_key": False},
                    {"name": "is_active", "type": "BOOLEAN", "primary_key": False},
                ],
            },
            requires_approval=True,
        )
