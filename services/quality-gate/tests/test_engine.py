"""Tests for the quality validation engine."""

from quality_gate.engine import QualityEngine


class TestQualityEngine:
    def test_validate_returns_report(self) -> None:
        engine = QualityEngine()
        report = engine.validate(
            dataset_id="test/dataset",
            domain_id="test",
            layer="bronze",
        )
        assert report.dataset_id == "test/dataset"
        assert report.domain_id == "test"
        assert report.layer == "bronze"
        assert 0.0 <= report.dq_score <= 1.0
        assert report.expectations_passed >= 0
        assert report.expectations_total >= 0
        assert report.expectations_passed + report.expectations_failed == report.expectations_total

    def test_validate_with_custom_suite(self) -> None:
        engine = QualityEngine()
        report = engine.validate(
            dataset_id="finance/revenue",
            domain_id="finance",
            layer="silver",
            suite_name="default",
        )
        assert report.dq_score >= 0.0
        assert isinstance(report.dimension_scores, dict)

    def test_get_report_returns_cached(self) -> None:
        engine = QualityEngine()
        report = engine.validate(
            dataset_id="test/dataset",
            domain_id="test",
            layer="bronze",
        )
        cached = engine.get_report(report.id)
        assert cached is not None
        assert cached.id == report.id

    def test_get_report_missing_returns_none(self) -> None:
        import uuid

        engine = QualityEngine()
        assert engine.get_report(uuid.uuid4()) is None

    def test_dimension_scores_present(self) -> None:
        engine = QualityEngine()
        report = engine.validate(
            dataset_id="test/dataset",
            domain_id="test",
            layer="bronze",
        )
        # All 6 DAMA dimensions should have scores
        expected_dims = {"completeness", "accuracy", "consistency", "timeliness", "uniqueness", "validity"}
        assert set(report.dimension_scores.keys()) == expected_dims
