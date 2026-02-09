"""Base class for governance rules (ADR-131).

All governance rules must extend BaseRule and implement evaluate().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class RuleEvaluation(BaseModel):
    """Result of evaluating a governance rule."""

    matched: bool = Field(description="Whether the rule conditions were matched")
    actions: list[str] = Field(default_factory=list, description="Actions to execute if matched")
    conditions_met: dict[str, bool] = Field(
        default_factory=dict,
        description="Which conditions were met",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional evaluation metadata")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in evaluation")


class BaseRule(ABC):
    """Abstract base class for governance rules.

    Implements the plugin pattern for extensible governance policies.
    Rules evaluate conditions and recommend actions (ADR-011).

    Example:
        class DataClassificationRule(BaseRule):
            async def evaluate(self, context: dict) -> RuleEvaluation:
                dataset_name = context.get("dataset_name", "")
                contains_pii = context.get("contains_pii", False)

                if contains_pii:
                    return RuleEvaluation(
                        matched=True,
                        actions=["classify_as_sensitive", "require_approval"],
                        conditions_met={"contains_pii": True},
                    )

                return RuleEvaluation(matched=False)

            def get_conditions(self) -> list[str]:
                return ["contains_pii"]

            def get_actions(self) -> list[str]:
                return ["classify_as_sensitive", "require_approval"]
    """

    @abstractmethod
    async def evaluate(self, context: dict[str, Any]) -> RuleEvaluation:
        """Evaluate the rule against the given context.

        Args:
            context: Context dictionary with variables for evaluation

        Returns:
            RuleEvaluation with matched status and recommended actions

        Raises:
            Exception: If evaluation fails unexpectedly
        """
        ...

    @abstractmethod
    def get_conditions(self) -> list[str]:
        """Return the list of condition keys this rule evaluates."""
        ...

    @abstractmethod
    def get_actions(self) -> list[str]:
        """Return the list of possible actions this rule can recommend."""
        ...

    def get_name(self) -> str:
        """Return human-readable rule name (defaults to class name)."""
        return self.__class__.__name__

    def get_description(self) -> str:
        """Return rule description (defaults to docstring)."""
        return (self.__class__.__doc__ or "").strip()

    def get_priority(self) -> int:
        """Return rule priority (higher = evaluated first, default: 0)."""
        return 0

    async def initialize(self) -> None:  # noqa: B027
        """Initialize rule (load config, etc.)."""

    async def shutdown(self) -> None:  # noqa: B027
        """Gracefully shutdown rule."""
