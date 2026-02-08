"""Integration test: quality-gate validation end-to-end."""

from __future__ import annotations


class TestQualityGateIntegration:
    """Verify quality scoring and DAMA dimension mapping."""

    def test_dama_scorer_produces_all_dimensions(self) -> None:
        """DAMAScorer should produce scores for all 6 DAMA dimensions."""
        from odg_core.enums import DAMADimension
        from odg_core.quality.dimensions import DAMAScorer

        scorer = DAMAScorer()
        results = [
            {"expectation_type": "expect_column_values_to_not_be_null", "success": True},
            {"expectation_type": "expect_column_values_to_be_between", "success": True},
            {"expectation_type": "expect_column_values_to_match_regex", "success": False},
            {"expectation_type": "expect_column_values_to_be_unique", "success": True},
            {"expectation_type": "expect_column_pair_values_to_be_equal", "success": True},
            {"expectation_type": "expect_column_values_to_match_strftime_format", "success": True},
        ]
        scores = scorer.score(results)

        assert len(scores) == len(DAMADimension)
        for dim in DAMADimension:
            assert dim.value in scores
            assert 0.0 <= scores[dim.value] <= 1.0

    def test_overall_score_within_bounds(self) -> None:
        """Overall DQ score should be between 0 and 1."""
        from odg_core.quality.dimensions import DAMAScorer

        scorer = DAMAScorer()
        dim_scores = {"completeness": 0.9, "accuracy": 0.8, "validity": 0.7}
        overall = scorer.overall_score(dim_scores)
        assert 0.0 <= overall <= 1.0

    def test_sla_check_integration(self) -> None:
        """SLA threshold check should pass when scores meet thresholds."""
        from odg_core.quality.sla import check_sla, get_layer_thresholds

        thresholds = get_layer_thresholds("bronze")
        # Create scores that exceed all thresholds
        scores = {dim: thresh + 0.01 for dim, thresh in thresholds.items()}
        result = check_sla(scores, thresholds)
        assert all(result.values())

    def test_full_pipeline_score_to_sla(self) -> None:
        """Full pipeline: GE results -> DAMA scores -> SLA check."""
        from odg_core.quality.dimensions import DAMAScorer
        from odg_core.quality.sla import check_sla, get_layer_thresholds

        # Simulate Great Expectations results (all passing)
        ge_results = [
            {"expectation_type": "expect_column_values_to_not_be_null", "success": True},
            {"expectation_type": "expect_column_values_to_be_between", "success": True},
            {"expectation_type": "expect_column_values_to_match_regex", "success": True},
            {"expectation_type": "expect_column_values_to_be_unique", "success": True},
            {"expectation_type": "expect_column_pair_values_to_be_equal", "success": True},
            {"expectation_type": "expect_column_values_to_match_strftime_format", "success": True},
        ]

        # Score via DAMA dimensions
        scorer = DAMAScorer()
        dim_scores = scorer.score(ge_results)

        # Check SLA for bronze (lowest thresholds)
        thresholds = get_layer_thresholds("bronze")
        sla_result = check_sla(dim_scores, thresholds)

        # All expectations passed -> all SLA checks should pass
        assert all(sla_result.values())

        # Overall score should be 1.0 (all passed)
        overall = scorer.overall_score(dim_scores)
        assert abs(overall - 1.0) < 1e-9
