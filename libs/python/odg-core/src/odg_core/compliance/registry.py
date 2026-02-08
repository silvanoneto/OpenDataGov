"""Compliance checker registry (ADR-110).

Central registry for pluggable compliance framework checkers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from odg_core.compliance.protocols import ComplianceChecker, ComplianceResult
    from odg_core.enums import ComplianceFramework


class ComplianceRegistry:
    """Registry for compliance framework checkers."""

    def __init__(self) -> None:
        self._checkers: dict[ComplianceFramework, ComplianceChecker] = {}

    def register(self, checker: ComplianceChecker) -> None:
        """Register a compliance checker."""
        self._checkers[checker.framework] = checker

    def check(self, framework: ComplianceFramework, context: dict[str, Any]) -> ComplianceResult:
        """Run a compliance check for a specific framework."""
        checker = self._checkers.get(framework)
        if checker is None:
            msg = f"No checker registered for {framework}"
            raise ValueError(msg)
        return checker.check(context)

    def check_all(self, context: dict[str, Any]) -> dict[ComplianceFramework, ComplianceResult]:
        """Run all registered compliance checks."""
        return {fw: checker.check(context) for fw, checker in self._checkers.items()}

    @property
    def registered_frameworks(self) -> list[ComplianceFramework]:
        """List all registered frameworks."""
        return list(self._checkers.keys())


def create_default_registry() -> ComplianceRegistry:
    """Create a registry with all built-in compliance checkers."""
    from odg_core.compliance.dama import DAMAChecker
    from odg_core.compliance.eu_ai_act import EUAIActChecker
    from odg_core.compliance.gdpr import GDPRChecker
    from odg_core.compliance.iso_42001 import ISO42001Checker
    from odg_core.compliance.lgpd import LGPDChecker
    from odg_core.compliance.nist_ai_rmf import NISTAIRMFChecker
    from odg_core.compliance.sox import SOXChecker

    registry = ComplianceRegistry()
    registry.register(LGPDChecker())
    registry.register(GDPRChecker())
    registry.register(EUAIActChecker())
    registry.register(NISTAIRMFChecker())
    registry.register(ISO42001Checker())
    registry.register(SOXChecker())
    registry.register(DAMAChecker())
    return registry
