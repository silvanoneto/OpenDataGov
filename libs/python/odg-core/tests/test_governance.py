"""Tests for contracts/governance.py — governance integration for data contracts."""

from __future__ import annotations

from odg_core.contracts.governance import evaluate_contract_change
from odg_core.models import ColumnDefinition, DataContractSchema


def _schema(*columns: tuple[str, str, bool]) -> DataContractSchema:
    """Helper to build a DataContractSchema from (name, type, nullable) tuples."""
    return DataContractSchema(
        columns=[ColumnDefinition(name=n, data_type=t, nullable=nl) for n, t, nl in columns],
    )


class TestEvaluateContractChangeNoChange:
    def test_identical_schemas(self) -> None:
        """Identical schemas should produce no_change governance action."""
        schema = _schema(("id", "string", False))
        result = evaluate_contract_change(schema, schema)

        assert result["requires_approval"] is False
        assert result["governance_action"] == "no_change"
        assert result["change_analysis"]["has_breaking"] is False
        assert result["change_analysis"]["non_breaking_changes"] == []

    def test_empty_schemas(self) -> None:
        """Two empty schemas should produce no_change."""
        empty = DataContractSchema(columns=[])
        result = evaluate_contract_change(empty, empty)

        assert result["requires_approval"] is False
        assert result["governance_action"] == "no_change"


class TestEvaluateContractChangeAutoApprove:
    def test_nullable_column_added(self) -> None:
        """Adding a nullable column is non-breaking and auto-approved."""
        old = _schema(("id", "string", False))
        new = _schema(("id", "string", False), ("notes", "string", True))

        result = evaluate_contract_change(old, new)

        assert result["requires_approval"] is False
        assert result["governance_action"] == "auto_approve"
        assert result["change_analysis"]["has_breaking"] is False
        assert len(result["change_analysis"]["non_breaking_changes"]) == 1


class TestEvaluateContractChangeRACIApproval:
    def test_type_change_requires_raci(self) -> None:
        """Changing a column type is breaking and requires RACI approval."""
        old = _schema(("id", "string", False))
        new = _schema(("id", "integer", False))

        result = evaluate_contract_change(old, new)

        assert result["requires_approval"] is True
        assert result["governance_action"] == "raci_approval"
        assert result["breaking_change_count"] >= 1

    def test_nullable_to_non_nullable_requires_raci(self) -> None:
        """Changing nullable to non-nullable is breaking and requires RACI."""
        old = _schema(("id", "string", False), ("name", "string", True))
        new = _schema(("id", "string", False), ("name", "string", False))

        result = evaluate_contract_change(old, new)

        assert result["requires_approval"] is True
        assert result["governance_action"] == "raci_approval"

    def test_non_nullable_column_added_requires_raci(self) -> None:
        """Adding a non-nullable column is breaking and requires RACI."""
        old = _schema(("id", "string", False))
        new = _schema(("id", "string", False), ("required_col", "string", False))

        result = evaluate_contract_change(old, new)

        assert result["requires_approval"] is True
        assert result["governance_action"] == "raci_approval"


class TestEvaluateContractChangeVetoEligible:
    def test_column_removal_is_veto_eligible(self) -> None:
        """Removing a column is breaking and veto-eligible."""
        old = _schema(("id", "string", False), ("name", "string", True))
        new = _schema(("id", "string", False))

        result = evaluate_contract_change(old, new)

        assert result["requires_approval"] is True
        assert result["governance_action"] == "veto_eligible"
        assert result["breaking_change_count"] >= 1

    def test_column_removal_with_type_change(self) -> None:
        """Column removal + type change should still be veto_eligible."""
        old = _schema(
            ("id", "string", False),
            ("name", "string", True),
            ("age", "integer", True),
        )
        new = _schema(
            ("id", "integer", False),  # type change
            # name removed
            ("age", "integer", True),
        )

        result = evaluate_contract_change(old, new)

        assert result["requires_approval"] is True
        assert result["governance_action"] == "veto_eligible"
        # Both column_removed and type_changed should be present
        breaking_types = {c["type"] for c in result["change_analysis"]["breaking_changes"]}
        assert "column_removed" in breaking_types
        assert "type_changed" in breaking_types


class TestEvaluateContractChangeAnalysisPassthrough:
    def test_change_analysis_present(self) -> None:
        """Result should always contain full change_analysis from breaking detection."""
        old = _schema(("id", "string", False))
        new = _schema(("id", "integer", False))

        result = evaluate_contract_change(old, new)

        analysis = result["change_analysis"]
        assert "has_breaking" in analysis
        assert "breaking_changes" in analysis
        assert "non_breaking_changes" in analysis
