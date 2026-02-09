"""Tests for quality checks module."""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from odg_core.quality.base_check import (
    BaseCheck,
    CheckResult,
    DAMADimension,
    Severity,
)
from odg_core.quality.checks.completeness_check import CompletenessCheck

# ── Fake pandas for tests (no real pandas needed) ─────────────
# We create a lightweight fake pandas module so CompletenessCheck
# can do `import pandas as pd` and `isinstance(data, pd.DataFrame)`.


class _FakeDataFrame:
    """Minimal DataFrame stand-in for CompletenessCheck tests."""

    def __init__(self, data: dict[str, list[Any]] | None = None) -> None:
        self._data = data or {}
        cols = list(self._data.keys())
        self._ncols = len(cols)
        self._nrows = len(next(iter(self._data.values()))) if self._data else 0

    @property
    def size(self) -> int:
        return self._nrows * self._ncols

    def __len__(self) -> int:
        return self._nrows

    def isnull(self) -> _FakeNullFrame:
        return _FakeNullFrame(self._data)


class _FakeNullSeries:
    """Per-column null counts with .items() support."""

    def __init__(self, col_counts: dict[str, int]) -> None:
        self._counts = col_counts

    def sum(self) -> int:
        return sum(self._counts.values())

    def __getitem__(self, mask: _FakeNullSeries) -> _FakeNullSeries:
        # mask[mask > 0] — filter to non-zero columns
        return _FakeNullSeries({k: v for k, v in self._counts.items() if v > 0})

    def __gt__(self, other: int) -> _FakeNullSeries:
        return self  # used as mask in __getitem__

    def items(self) -> list[tuple[str, int]]:
        return list(self._counts.items())


class _FakeNullFrame:
    """Result of df.isnull()."""

    def __init__(self, data: dict[str, list[Any]]) -> None:
        self._data = data

    def sum(self) -> _FakeNullSeries:
        counts = {}
        for col, values in self._data.items():
            counts[col] = sum(1 for v in values if v is None)
        return _FakeNullSeries(counts)


_fake_pd_module = types.ModuleType("pandas")
_fake_pd_module.DataFrame = _FakeDataFrame  # type: ignore[attr-defined]

# ── DAMADimension enum tests ────────────────────────────────────


class TestDAMADimension:
    def test_all_dimensions(self) -> None:
        assert DAMADimension.COMPLETENESS.value == "completeness"
        assert DAMADimension.ACCURACY.value == "accuracy"
        assert DAMADimension.VALIDITY.value == "validity"
        assert DAMADimension.CONSISTENCY.value == "consistency"
        assert DAMADimension.TIMELINESS.value == "timeliness"
        assert DAMADimension.UNIQUENESS.value == "uniqueness"

    def test_dimension_count(self) -> None:
        assert len(DAMADimension) == 6


# ── Severity enum tests ────────────────────────────────────────


class TestSeverity:
    def test_all_severities(self) -> None:
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"
        assert Severity.CRITICAL.value == "critical"


# ── CheckResult model tests ────────────────────────────────────


class TestCheckResult:
    def test_create_passing_result(self) -> None:
        r = CheckResult(passed=True, score=0.98)
        assert r.passed is True
        assert r.score == 0.98
        assert r.failures == []
        assert r.metadata == {}

    def test_create_failing_result(self) -> None:
        r = CheckResult(
            passed=False,
            score=0.50,
            failures=["Too many nulls"],
            row_count=100,
            failure_count=50,
        )
        assert r.passed is False
        assert len(r.failures) == 1
        assert r.row_count == 100

    def test_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            CheckResult(passed=True, score=1.5)
        with pytest.raises(ValidationError):
            CheckResult(passed=True, score=-0.1)


# ── BaseCheck abstract tests ───────────────────────────────────


class _DummyCheck(BaseCheck):
    """A dummy check for testing."""

    async def validate(self, data: Any) -> CheckResult:
        return CheckResult(passed=True, score=1.0)

    def get_dimension(self) -> DAMADimension:
        return DAMADimension.COMPLETENESS

    def get_severity(self) -> Severity:
        return Severity.ERROR


class TestBaseCheck:
    def test_get_name_default(self) -> None:
        check = _DummyCheck()
        assert check.get_name() == "_DummyCheck"

    def test_get_description_from_docstring(self) -> None:
        check = _DummyCheck()
        assert "dummy check" in check.get_description().lower()

    @pytest.mark.asyncio
    async def test_validate(self) -> None:
        check = _DummyCheck()
        result = await check.validate(None)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_initialize_no_op(self) -> None:
        check = _DummyCheck()
        await check.initialize()

    @pytest.mark.asyncio
    async def test_shutdown_no_op(self) -> None:
        check = _DummyCheck()
        await check.shutdown()


# ── CompletenessCheck tests ─────────────────────────────────────


class TestCompletenessCheck:
    def test_default_threshold(self) -> None:
        check = CompletenessCheck()
        assert check.threshold == 0.95

    def test_custom_threshold(self) -> None:
        check = CompletenessCheck(threshold=0.80)
        assert check.threshold == 0.80

    def test_get_dimension(self) -> None:
        check = CompletenessCheck()
        assert check.get_dimension() == DAMADimension.COMPLETENESS

    def test_get_severity(self) -> None:
        check = CompletenessCheck()
        assert check.get_severity() == Severity.ERROR

    @pytest.mark.asyncio
    async def test_validate_complete_data(self) -> None:
        df = _FakeDataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        check = CompletenessCheck()
        with patch.dict(sys.modules, {"pandas": _fake_pd_module}):
            result = await check.validate(df)
        assert result.passed is True
        assert result.score == 1.0
        assert result.failures == []
        assert result.row_count == 3
        assert result.failure_count == 0

    @pytest.mark.asyncio
    async def test_validate_incomplete_data(self) -> None:
        # Use None to represent NaN (our _FakeNullFrame counts None)
        df = _FakeDataFrame({"a": [1, None, 3], "b": [None, None, 6]})
        check = CompletenessCheck(threshold=0.95)
        with patch.dict(sys.modules, {"pandas": _fake_pd_module}):
            result = await check.validate(df)
        assert result.passed is False
        assert result.score < 0.95
        assert len(result.failures) > 0

    @pytest.mark.asyncio
    async def test_validate_empty_dataframe(self) -> None:
        df = _FakeDataFrame()
        check = CompletenessCheck()
        with patch.dict(sys.modules, {"pandas": _fake_pd_module}):
            result = await check.validate(df)
        assert result.passed is True
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_validate_non_dataframe(self) -> None:
        check = CompletenessCheck()
        with patch.dict(sys.modules, {"pandas": _fake_pd_module}):
            result = await check.validate({"a": 1})
        assert result.passed is False
        assert result.score == 0.0
        assert len(result.failures) == 1

    @pytest.mark.asyncio
    async def test_validate_with_low_threshold(self) -> None:
        df = _FakeDataFrame({"a": [1, None, 3], "b": [4, 5, 6]})
        check = CompletenessCheck(threshold=0.50)
        with patch.dict(sys.modules, {"pandas": _fake_pd_module}):
            result = await check.validate(df)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_metadata(self) -> None:
        df = _FakeDataFrame({"a": [1, 2], "b": [3, 4]})
        check = CompletenessCheck()
        with patch.dict(sys.modules, {"pandas": _fake_pd_module}):
            result = await check.validate(df)
        assert "threshold" in result.metadata
        assert "total_cells" in result.metadata
        assert result.metadata["total_cells"] == 4

    @pytest.mark.asyncio
    async def test_validate_import_error(self) -> None:
        """Cover the ImportError path (line 80-85)."""
        check = CompletenessCheck()
        with patch.dict(sys.modules, {"pandas": None}):
            result = await check.validate({"a": 1})
        assert result.passed is False
        assert "pandas is required" in result.failures[0]

    @pytest.mark.asyncio
    async def test_validate_generic_exception(self) -> None:
        """Cover the generic Exception path (line 86-91)."""
        check = CompletenessCheck()
        df = _FakeDataFrame({"a": [1, 2]})
        exploding_pd = types.ModuleType("pandas")
        exploding_pd.DataFrame = _FakeDataFrame  # type: ignore[attr-defined]

        def _exploding_size(self: Any) -> int:
            raise RuntimeError("boom")

        with patch.dict(sys.modules, {"pandas": exploding_pd}):
            original_size = _FakeDataFrame.size
            _FakeDataFrame.size = property(_exploding_size)  # type: ignore[assignment]
            try:
                result = await check.validate(df)
            finally:
                _FakeDataFrame.size = original_size  # type: ignore[method-assign]
        assert result.passed is False
        assert "Validation error" in result.failures[0]
