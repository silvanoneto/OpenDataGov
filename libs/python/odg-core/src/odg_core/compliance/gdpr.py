"""GDPR compliance checker (ADR-110)."""

from __future__ import annotations

from typing import Any

from odg_core.compliance.protocols import ComplianceFinding, ComplianceResult
from odg_core.enums import ComplianceFramework


class GDPRChecker:
    """Checks compliance with EU GDPR."""

    @property
    def framework(self) -> ComplianceFramework:
        return ComplianceFramework.GDPR

    def check(self, context: dict[str, Any]) -> ComplianceResult:
        findings: list[ComplianceFinding] = []

        if not context.get("has_lawful_basis"):
            findings.append(
                ComplianceFinding(
                    rule_id="GDPR-6",
                    severity="critical",
                    description="No lawful basis for data processing",
                    recommendation="Document lawful basis under GDPR Art. 6",
                )
            )

        if not context.get("supports_data_portability"):
            findings.append(
                ComplianceFinding(
                    rule_id="GDPR-20",
                    severity="high",
                    description="Data portability not supported",
                    recommendation="Implement data export in machine-readable format",
                )
            )

        if not context.get("has_dpia"):
            findings.append(
                ComplianceFinding(
                    rule_id="GDPR-35",
                    severity="medium",
                    description="No Data Protection Impact Assessment conducted",
                    recommendation="Conduct DPIA for high-risk processing activities",
                )
            )

        if context.get("transfers_outside_eu") and not context.get("has_adequacy_decision"):
            findings.append(
                ComplianceFinding(
                    rule_id="GDPR-45",
                    severity="critical",
                    description="Cross-border transfer without adequacy decision",
                    recommendation="Ensure adequate safeguards for international data transfers",
                )
            )

        total_rules = 4
        passed_rules = total_rules - len(findings)
        score = passed_rules / total_rules if total_rules > 0 else 1.0
        critical_count = sum(1 for f in findings if f.severity == "critical")

        return ComplianceResult(
            framework=ComplianceFramework.GDPR,
            passed=critical_count == 0,
            score=score,
            findings=findings,
        )
