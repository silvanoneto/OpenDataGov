"""SOX compliance checker (ADR-110)."""

from __future__ import annotations

from typing import Any

from odg_core.compliance.protocols import ComplianceFinding, ComplianceResult
from odg_core.enums import ComplianceFramework


class SOXChecker:
    """Checks compliance with Sarbanes-Oxley Act (financial data controls)."""

    @property
    def framework(self) -> ComplianceFramework:
        return ComplianceFramework.SOX

    def check(self, context: dict[str, Any]) -> ComplianceResult:
        findings: list[ComplianceFinding] = []

        if not context.get("has_audit_trail"):
            findings.append(
                ComplianceFinding(
                    rule_id="SOX-302",
                    severity="critical",
                    description="No immutable audit trail for financial data changes",
                    recommendation="Implement hash-chained audit log per SOX Section 302",
                )
            )

        if not context.get("has_access_controls"):
            findings.append(
                ComplianceFinding(
                    rule_id="SOX-404-ACCESS",
                    severity="critical",
                    description="Inadequate access controls for financial reporting data",
                    recommendation="Enforce RBAC and separation of duties per SOX Section 404",
                )
            )

        if not context.get("has_change_management"):
            findings.append(
                ComplianceFinding(
                    rule_id="SOX-404-CHANGE",
                    severity="high",
                    description="No formal change management process for financial data pipelines",
                    recommendation="Implement RACI-based approval for schema and pipeline changes",
                )
            )

        if not context.get("has_data_retention_policy"):
            findings.append(
                ComplianceFinding(
                    rule_id="SOX-802",
                    severity="high",
                    description="No data retention policy (SOX requires 7 years)",
                    recommendation="Configure retention policies: audit logs >= 7 years",
                )
            )

        total_rules = 4
        passed_rules = total_rules - len(findings)
        score = passed_rules / total_rules if total_rules > 0 else 1.0
        critical_count = sum(1 for f in findings if f.severity == "critical")

        return ComplianceResult(
            framework=ComplianceFramework.SOX,
            passed=critical_count == 0,
            score=score,
            findings=findings,
        )
