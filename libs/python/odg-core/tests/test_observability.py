"""Tests for data observability modules."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from odg_core.observability.distribution import detect_distribution_drift
from odg_core.observability.freshness import record_freshness
from odg_core.observability.schema_drift import detect_schema_drift
from odg_core.observability.volume import record_row_count


class TestFreshness:
    def test_record_freshness_does_not_raise(self) -> None:
        """record_freshness should execute without errors."""
        record_freshness(
            dataset="revenue",
            domain="finance",
            layer="silver",
            seconds_since_update=3600.0,
        )


class TestVolume:
    def test_record_row_count_does_not_raise(self) -> None:
        """record_row_count should execute without errors."""
        record_row_count(
            dataset="revenue",
            domain="finance",
            layer="bronze",
            rows=10_000,
        )


class TestSchemaDrift:
    def test_no_drift(self) -> None:
        expected = ["id", "name", "email"]
        actual = ["id", "name", "email"]
        result = detect_schema_drift("users", "identity", expected, actual)
        assert result["has_drift"] is False
        assert result["added"] == []
        assert result["removed"] == []

    def test_added_columns(self) -> None:
        expected = ["id", "name"]
        actual = ["id", "name", "age"]
        result = detect_schema_drift("users", "identity", expected, actual)
        assert result["has_drift"] is True
        assert result["added"] == ["age"]
        assert result["removed"] == []

    def test_removed_columns(self) -> None:
        expected = ["id", "name", "email"]
        actual = ["id", "name"]
        result = detect_schema_drift("users", "identity", expected, actual)
        assert result["has_drift"] is True
        assert result["added"] == []
        assert result["removed"] == ["email"]

    def test_both_added_and_removed(self) -> None:
        expected = ["id", "name", "email"]
        actual = ["id", "name", "phone"]
        result = detect_schema_drift("users", "identity", expected, actual)
        assert result["has_drift"] is True
        assert result["added"] == ["phone"]
        assert result["removed"] == ["email"]


def _mock_ks_2samp(reference: list[float], current: list[float]) -> tuple[float, float]:
    """Fake KS test: returns (1.0, 0.0) when data differs, (0.0, 1.0) when identical."""
    if reference == current:
        return 0.0, 1.0
    return 1.0, 0.001


def _make_scipy_stats_module() -> MagicMock:
    """Create a mock scipy.stats module with a working ks_2samp."""
    mock_module = MagicMock()
    mock_module.ks_2samp = _mock_ks_2samp
    return mock_module


class TestDistributionDrift:
    def test_no_drift_identical_distributions(self) -> None:
        """Identical distributions should report no drift."""
        mock_stats = _make_scipy_stats_module()

        with patch.dict("sys.modules", {"scipy": MagicMock(), "scipy.stats": mock_stats}):
            reference = [1.0, 2.0, 3.0, 4.0, 5.0] * 20
            current = list(reference)

            result = detect_distribution_drift(
                dataset="revenue",
                column="amount",
                reference=reference,
                current=current,
            )

            assert result["has_drift"] is False
            p_value = result["p_value"]
            assert isinstance(p_value, float)
            assert p_value >= 0.05
            assert isinstance(result["statistic"], float)

    def test_drift_detected_different_distributions(self) -> None:
        """Completely different distributions should report drift."""
        mock_stats = _make_scipy_stats_module()

        with patch.dict("sys.modules", {"scipy": MagicMock(), "scipy.stats": mock_stats}):
            reference = [1.0, 1.1, 1.2, 1.3, 1.4] * 20
            current = [100.0, 200.0, 300.0, 400.0, 500.0] * 20

            result = detect_distribution_drift(
                dataset="revenue",
                column="amount",
                reference=reference,
                current=current,
            )

            assert result["has_drift"] is True
            p_value = result["p_value"]
            assert isinstance(p_value, float)
            assert p_value < 0.05
            statistic = result["statistic"]
            assert isinstance(statistic, float)
            assert statistic > 0.0

    def test_custom_threshold_no_drift(self) -> None:
        """With a very low threshold, borderline drift is not flagged."""
        mock_stats = MagicMock()
        # Return a p_value of 0.04 which is below default 0.05 but above 0.01
        mock_stats.ks_2samp.return_value = (0.3, 0.04)

        with patch.dict("sys.modules", {"scipy": MagicMock(), "scipy.stats": mock_stats}):
            result = detect_distribution_drift(
                dataset="test",
                column="col",
                reference=[1.0, 2.0],
                current=[3.0, 4.0],
                threshold=0.01,
            )
            # p=0.04 >= threshold=0.01 => no drift
            assert result["has_drift"] is False

    def test_custom_threshold_drift(self) -> None:
        """With a high threshold, even borderline differences are flagged."""
        mock_stats = MagicMock()
        mock_stats.ks_2samp.return_value = (0.3, 0.04)

        with patch.dict("sys.modules", {"scipy": MagicMock(), "scipy.stats": mock_stats}):
            result = detect_distribution_drift(
                dataset="test",
                column="col",
                reference=[1.0, 2.0],
                current=[3.0, 4.0],
                threshold=0.05,
            )
            # p=0.04 < threshold=0.05 => drift
            assert result["has_drift"] is True

    def test_drift_adds_otel_span_event(self) -> None:
        """When drift is detected, an OTel span event should be added."""
        mock_span = MagicMock()
        mock_stats = _make_scipy_stats_module()

        with (
            patch("odg_core.observability.distribution.trace") as mock_trace,
            patch.dict("sys.modules", {"scipy": MagicMock(), "scipy.stats": mock_stats}),
        ):
            mock_trace.get_current_span.return_value = mock_span

            reference = [1.0] * 50
            current = [100.0] * 50

            result = detect_distribution_drift(
                dataset="orders",
                column="total",
                reference=reference,
                current=current,
            )

            assert result["has_drift"] is True
            mock_span.add_event.assert_called_once()

            call_args = mock_span.add_event.call_args
            assert call_args[0][0] == "distribution_drift_detected"
            attrs = call_args[1]["attributes"]
            assert attrs["dataset"] == "orders"
            assert attrs["column"] == "total"
            assert "ks_statistic" in attrs
            assert "p_value" in attrs
            assert "threshold" in attrs

    def test_no_drift_does_not_add_span_event(self) -> None:
        """When no drift is detected, no OTel span event should be added."""
        mock_span = MagicMock()
        mock_stats = _make_scipy_stats_module()

        with (
            patch("odg_core.observability.distribution.trace") as mock_trace,
            patch.dict("sys.modules", {"scipy": MagicMock(), "scipy.stats": mock_stats}),
        ):
            mock_trace.get_current_span.return_value = mock_span

            data = [1.0, 2.0, 3.0, 4.0, 5.0] * 20

            result = detect_distribution_drift(
                dataset="orders",
                column="total",
                reference=data,
                current=list(data),
            )

            assert result["has_drift"] is False
            mock_span.add_event.assert_not_called()

    def test_scipy_import_error_fallback(self) -> None:
        """When scipy is unavailable, should return has_drift=False."""
        with patch.dict("sys.modules", {"scipy": None, "scipy.stats": None}):
            # Patch at the point of import inside the function
            with patch("builtins.__import__", side_effect=ImportError("no scipy")):
                result = detect_distribution_drift(
                    dataset="test",
                    column="col",
                    reference=[1.0, 2.0],
                    current=[3.0, 4.0],
                )

            assert result["has_drift"] is False
            assert result["statistic"] == pytest.approx(0.0)
            assert result["p_value"] == pytest.approx(1.0)

    def test_drift_logging(self) -> None:
        """When drift is detected, a warning should be logged."""
        mock_stats = _make_scipy_stats_module()

        with (
            patch("odg_core.observability.distribution.logger") as mock_logger,
            patch.dict("sys.modules", {"scipy": MagicMock(), "scipy.stats": mock_stats}),
        ):
            reference = [1.0] * 50
            current = [100.0] * 50

            detect_distribution_drift(
                dataset="sales",
                column="revenue",
                reference=reference,
                current=current,
            )

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            assert "Distribution drift" in call_args[0]
            assert "sales" in call_args[1:]
            assert "revenue" in call_args[1:]

    def test_no_drift_no_logging(self) -> None:
        """When no drift is detected, no warning should be logged."""
        mock_stats = _make_scipy_stats_module()

        with (
            patch("odg_core.observability.distribution.logger") as mock_logger,
            patch.dict("sys.modules", {"scipy": MagicMock(), "scipy.stats": mock_stats}),
        ):
            data = [1.0, 2.0, 3.0] * 20

            detect_distribution_drift(
                dataset="test",
                column="col",
                reference=data,
                current=list(data),
            )

            mock_logger.warning.assert_not_called()

    def test_return_types(self) -> None:
        """Result dict should contain correct types."""
        mock_stats = _make_scipy_stats_module()

        with patch.dict("sys.modules", {"scipy": MagicMock(), "scipy.stats": mock_stats}):
            data = [1.0, 2.0, 3.0] * 20
            result = detect_distribution_drift(
                dataset="test",
                column="col",
                reference=data,
                current=list(data),
            )

            assert isinstance(result["statistic"], float)
            assert isinstance(result["p_value"], float)
            assert isinstance(result["has_drift"], bool)
