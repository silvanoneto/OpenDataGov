"""Integration test: lakehouse promotion with quality gate check."""

from __future__ import annotations

from odg_core.enums import MedallionLayer
from odg_core.models import GovernanceDecision, QualityReport


class TestPromotionWithDQ:
    """Verify that promotion decisions include quality context."""

    def test_governance_decision_with_promotion_metadata(self) -> None:
        """A governance decision should carry promotion metadata."""
        decision = GovernanceDecision(
            title="Promote revenue dataset",
            description="Bronze to Silver promotion with DQ check",
            decision_type="data_promotion",
            domain_id="finance",
            created_by="data-team",
            source_layer=MedallionLayer.BRONZE,
            target_layer=MedallionLayer.SILVER,
        )

        assert decision.promotion is not None
        assert decision.promotion.source_layer == MedallionLayer.BRONZE
        assert decision.promotion.target_layer == MedallionLayer.SILVER

    def test_quality_report_with_dq_score(self) -> None:
        """QualityReport should carry DQ score and dimension scores."""
        report = QualityReport(
            dataset_id="revenue_daily",
            domain_id="finance",
            layer="silver",
            suite_name="default_silver",
            dq_score=0.92,
            dimension_scores={"completeness": 0.95, "accuracy": 0.90},
            expectations_passed=18,
            expectations_failed=2,
            expectations_total=20,
        )

        assert report.dq_score == 0.92
        assert report.dimension_scores["completeness"] == 0.95

    def test_promotion_dq_threshold_check(self) -> None:
        """Gold promotion should require high DQ score."""
        min_gold_score = 0.95

        report = QualityReport(
            dataset_id="revenue_daily",
            domain_id="finance",
            layer="gold",
            suite_name="default_gold",
            dq_score=0.93,
        )

        meets_threshold = report.dq_score >= min_gold_score
        assert meets_threshold is False

    def test_contract_breaking_change_triggers_governance(self) -> None:
        """Breaking changes in data contracts should require approval."""
        from odg_core.contracts.governance import evaluate_contract_change
        from odg_core.models import ColumnDefinition, DataContractSchema

        old = DataContractSchema(
            columns=[
                ColumnDefinition(name="id", data_type="integer", nullable=False),
                ColumnDefinition(name="amount", data_type="float", nullable=False),
            ]
        )
        new = DataContractSchema(
            columns=[
                ColumnDefinition(name="id", data_type="integer", nullable=False),
                # amount removed = breaking change
            ]
        )

        result = evaluate_contract_change(old, new)
        assert result["requires_approval"] is True
        assert result["governance_action"] == "veto_eligible"
