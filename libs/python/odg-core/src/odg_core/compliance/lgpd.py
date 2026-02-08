"""LGPD compliance checker (ADR-110)."""

from __future__ import annotations

from typing import Any

from odg_core.compliance.protocols import ComplianceFinding, ComplianceResult
from odg_core.enums import ComplianceFramework


class LGPDChecker:
    """Checks compliance with Brazilian LGPD."""

    @property
    def framework(self) -> ComplianceFramework:
        return ComplianceFramework.LGPD

    def check(self, context: dict[str, Any]) -> ComplianceResult:
        findings: list[ComplianceFinding] = []

        if not context.get("has_legal_basis"):
            findings.append(
                ComplianceFinding(
                    rule_id="LGPD-7",
                    severity="critical",
                    description="No legal basis for data processing",
                    recommendation="Document legal basis under LGPD Art. 7",
                )
            )

        if not context.get("supports_data_subject_rights"):
            findings.append(
                ComplianceFinding(
                    rule_id="LGPD-18",
                    severity="high",
                    description="Data subject rights not implemented",
                    recommendation="Implement access, correction, deletion, portability per Art. 18",
                )
            )

        if not context.get("has_dpo"):
            findings.append(
                ComplianceFinding(
                    rule_id="LGPD-41",
                    severity="medium",
                    description="No Data Protection Officer (DPO/Encarregado) designated",
                    recommendation="Designate an Encarregado per Art. 41",
                )
            )

        if not context.get("has_security_measures"):
            findings.append(
                ComplianceFinding(
                    rule_id="LGPD-46",
                    severity="high",
                    description="Security measures not documented",
                    recommendation="Implement and document security measures per Art. 46",
                )
            )

        total_rules = 4
        passed_rules = total_rules - len(findings)
        score = passed_rules / total_rules if total_rules > 0 else 1.0
        critical_count = sum(1 for f in findings if f.severity == "critical")

        return ComplianceResult(
            framework=ComplianceFramework.LGPD,
            passed=critical_count == 0,
            score=score,
            findings=findings,
        )
