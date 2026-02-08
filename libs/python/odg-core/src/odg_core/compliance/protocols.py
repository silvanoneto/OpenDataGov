"""Compliance protocols and shared models (ADR-110)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from odg_core.enums import ComplianceFramework  # noqa: TC001 — needed at runtime by Pydantic


class ComplianceFinding(BaseModel):
    """Single compliance finding."""

    rule_id: str
    severity: str  # critical, high, medium, low
    description: str
    recommendation: str


class ComplianceResult(BaseModel):
    """Result of a compliance check against a framework."""

    framework: ComplianceFramework
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    findings: list[ComplianceFinding] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class ComplianceChecker(Protocol):
    """Protocol for pluggable compliance checkers."""

    @property
    def framework(self) -> ComplianceFramework: ...

    def check(self, context: dict[str, Any]) -> ComplianceResult: ...
