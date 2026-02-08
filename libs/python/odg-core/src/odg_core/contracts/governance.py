"""Governance integration for data contracts (ADR-051).

Triggers RACI approval workflow when breaking changes are detected
in data contract schemas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from odg_core.contracts.breaking import detect_breaking_changes

if TYPE_CHECKING:
    from odg_core.models import DataContractSchema


def evaluate_contract_change(
    old_schema: DataContractSchema,
    new_schema: DataContractSchema,
) -> dict[str, Any]:
    """Evaluate a contract schema change and determine governance action.

    Returns:
        Dict with:
          - requires_approval: bool
          - change_analysis: breaking change detection result
          - governance_action: "auto_approve" | "raci_approval" | "veto_eligible"
    """
    analysis = detect_breaking_changes(old_schema, new_schema)

    if not analysis["has_breaking"] and not analysis["non_breaking_changes"]:
        return {
            "requires_approval": False,
            "change_analysis": analysis,
            "governance_action": "no_change",
        }

    if not analysis["has_breaking"]:
        return {
            "requires_approval": False,
            "change_analysis": analysis,
            "governance_action": "auto_approve",
        }

    # Breaking changes require RACI approval
    breaking_count = len(analysis["breaking_changes"])
    has_column_removal = any(c["type"] == "column_removed" for c in analysis["breaking_changes"])

    return {
        "requires_approval": True,
        "change_analysis": analysis,
        "governance_action": "veto_eligible" if has_column_removal else "raci_approval",
        "breaking_change_count": breaking_count,
    }
