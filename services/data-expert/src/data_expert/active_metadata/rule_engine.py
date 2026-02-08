"""Rule engine for active metadata automation (ADR-042)."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data_expert.active_metadata.rules import MetadataRule

logger = logging.getLogger(__name__)


class RuleEngine:
    """Executes metadata rules against column metadata."""

    def __init__(self, rules: list[MetadataRule]) -> None:
        self._rules = rules

    def evaluate(self, columns: list[dict[str, str]]) -> list[dict[str, str]]:
        """Evaluate all rules against a list of column metadata dicts.

        Each column dict should have at least a 'name' key.
        Returns a list of action results.
        """
        actions: list[dict[str, str]] = []

        for rule in self._rules:
            for col in columns:
                if self._matches_condition(rule.condition, col):
                    action_result = {
                        "rule": rule.name,
                        "column": col.get("name", ""),
                        "action": rule.action,
                        "auto_approve": str(rule.auto_approve),
                    }
                    actions.append(action_result)
                    logger.info(
                        "Rule '%s' matched column '%s': %s",
                        rule.name,
                        col.get("name"),
                        rule.action,
                    )

        return actions

    def _matches_condition(self, condition: str, column: dict[str, str]) -> bool:
        """Check if a column matches a rule condition.

        Supports: "column matches <regex>"
        """
        if condition.startswith("column matches "):
            pattern = condition.removeprefix("column matches ")
            col_name = column.get("name", "")
            return bool(re.search(pattern, col_name, re.IGNORECASE))
        return False
