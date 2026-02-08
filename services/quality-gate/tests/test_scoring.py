"""Tests for DAMA dimension scoring."""

from odg_core.quality.dimensions import DAMAScorer


class TestDAMAScorer:
    def test_all_pass(self) -> None:
        scorer = DAMAScorer()
        results = [
            {"expectation_type": "expect_column_values_to_not_be_null", "success": True},
            {"expectation_type": "expect_column_values_to_be_unique", "success": True},
        ]
        scores = scorer.score(results)
        assert scores["completeness"] == 1.0
        assert scores["uniqueness"] == 1.0

    def test_partial_failure(self) -> None:
        scorer = DAMAScorer()
        results = [
            {"expectation_type": "expect_column_values_to_not_be_null", "success": True},
            {"expectation_type": "expect_table_row_count_to_be_between", "success": False},
        ]
        scores = scorer.score(results)
        assert scores["completeness"] == 0.5

    def test_unknown_expectation_ignored(self) -> None:
        scorer = DAMAScorer()
        results = [
            {"expectation_type": "expect_unknown_custom_thing", "success": False},
        ]
        scores = scorer.score(results)
        # All dimensions should be 1.0 (no mapped expectations)
        for score in scores.values():
            assert score == 1.0

    def test_overall_score(self) -> None:
        scorer = DAMAScorer()
        dimension_scores = {
            "completeness": 1.0,
            "accuracy": 0.5,
            "consistency": 1.0,
            "timeliness": 1.0,
            "uniqueness": 1.0,
            "validity": 0.0,
        }
        overall = scorer.overall_score(dimension_scores)
        assert abs(overall - 0.75) < 0.01

    def test_empty_scores(self) -> None:
        scorer = DAMAScorer()
        assert scorer.overall_score({}) == 0.0
