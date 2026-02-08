"""Tests for DAMA quality dimensions and SLA modules."""

from datetime import UTC, datetime, timedelta

from odg_core.models import QualitySLA
from odg_core.quality.dimensions import DAMAScorer
from odg_core.quality.reviewer import filter_due_for_review, needs_review
from odg_core.quality.sla import check_sla, get_layer_thresholds


class TestDAMAScorer:
    def test_score_all_pass(self) -> None:
        scorer = DAMAScorer()
        results = [
            {"expectation_type": "expect_column_values_to_not_be_null", "success": True},
            {"expectation_type": "expect_column_values_to_be_unique", "success": True},
            {"expectation_type": "expect_column_values_to_match_regex", "success": True},
        ]
        scores = scorer.score(results)
        assert scores["completeness"] == 1.0
        assert scores["uniqueness"] == 1.0
        assert scores["validity"] == 1.0

    def test_score_with_failures(self) -> None:
        scorer = DAMAScorer()
        results = [
            {"expectation_type": "expect_column_values_to_not_be_null", "success": True},
            {"expectation_type": "expect_table_row_count_to_be_between", "success": False},
        ]
        scores = scorer.score(results)
        assert scores["completeness"] == 0.5

    def test_score_with_unknown_expectation_type(self) -> None:
        scorer = DAMAScorer()
        results = [
            {"expectation_type": "unknown_type", "success": True},
            {"expectation_type": "expect_column_values_to_not_be_null", "success": True},
        ]
        scores = scorer.score(results)
        assert scores["completeness"] == 1.0

    def test_overall_score(self) -> None:
        scorer = DAMAScorer()
        scores = {
            "completeness": 1.0,
            "accuracy": 0.8,
            "consistency": 0.6,
            "timeliness": 1.0,
            "uniqueness": 1.0,
            "validity": 0.6,
        }
        overall = scorer.overall_score(scores)
        assert 0.8 <= overall <= 0.84

    def test_overall_score_empty(self) -> None:
        scorer = DAMAScorer()
        assert scorer.overall_score({}) < 0.01


class TestSLA:
    def test_default_thresholds(self) -> None:
        bronze = get_layer_thresholds("bronze")
        silver = get_layer_thresholds("silver")
        gold = get_layer_thresholds("gold")
        assert bronze["completeness"] == 0.70
        assert silver["completeness"] == 0.85
        assert gold["completeness"] == 0.95

    def test_check_sla_passes(self) -> None:
        thresholds = {"completeness": 0.70, "accuracy": 0.70}
        scores = {"completeness": 0.80, "accuracy": 0.90}
        result = check_sla(scores, thresholds)
        assert result["completeness"] is True
        assert result["accuracy"] is True

    def test_check_sla_fails(self) -> None:
        thresholds = {"completeness": 0.90}
        scores = {"completeness": 0.50}
        result = check_sla(scores, thresholds)
        assert result["completeness"] is False


class TestReviewer:
    def test_needs_review_never_reviewed(self) -> None:
        sla = QualitySLA(
            dataset_id="d",
            domain_id="d",
            dimension="completeness",
            threshold=0.9,
            owner_id="o",
            last_reviewed_at=None,
        )
        assert needs_review(sla) is True

    def test_needs_review_overdue(self) -> None:
        sla = QualitySLA(
            dataset_id="d",
            domain_id="d",
            dimension="completeness",
            threshold=0.9,
            owner_id="o",
            review_interval_days=90,
            last_reviewed_at=datetime.now(UTC) - timedelta(days=100),
        )
        assert needs_review(sla) is True

    def test_does_not_need_review(self) -> None:
        sla = QualitySLA(
            dataset_id="d",
            domain_id="d",
            dimension="completeness",
            threshold=0.9,
            owner_id="o",
            review_interval_days=90,
            last_reviewed_at=datetime.now(UTC) - timedelta(days=10),
        )
        assert needs_review(sla) is False

    def test_filter_due_for_review(self) -> None:
        overdue = QualitySLA(
            dataset_id="d1",
            domain_id="d",
            dimension="completeness",
            threshold=0.9,
            owner_id="o",
            last_reviewed_at=datetime.now(UTC) - timedelta(days=100),
        )
        recent = QualitySLA(
            dataset_id="d2",
            domain_id="d",
            dimension="accuracy",
            threshold=0.9,
            owner_id="o",
            last_reviewed_at=datetime.now(UTC) - timedelta(days=10),
        )
        result = filter_due_for_review([overdue, recent])
        assert len(result) == 1
        assert result[0].dataset_id == "d1"
