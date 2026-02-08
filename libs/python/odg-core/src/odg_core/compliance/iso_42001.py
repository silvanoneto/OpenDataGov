"""ISO 42001 (AI Management System) compliance checker (ADR-110)."""

from __future__ import annotations

from typing import Any

from odg_core.compliance.protocols import ComplianceFinding, ComplianceResult
from odg_core.enums import ComplianceFramework


class ISO42001Checker:
    """Checks compliance with ISO/IEC 42001:2023 AI Management System."""

    @property
    def framework(self) -> ComplianceFramework:
        return ComplianceFramework.ISO_42001

    def check(self, context: dict[str, Any]) -> ComplianceResult:
        findings: list[ComplianceFinding] = []

        # Clause 4: Context of the organization
        if not context.get("has_ai_scope_definition"):
            findings.append(
                ComplianceFinding(
                    rule_id="ISO42001-4",
                    severity="medium",
                    description="AI management system scope not defined",
                    recommendation="Define scope, interested parties, and AIMS boundaries (Clause 4)",
                )
            )

        # Clause 5: Leadership
        if not context.get("has_ai_leadership_commitment"):
            findings.append(
                ComplianceFinding(
                    rule_id="ISO42001-5",
                    severity="medium",
                    description="No leadership commitment to AI management",
                    recommendation="Establish AI policy and management responsibility (Clause 5)",
                )
            )

        # Clause 6: Planning — risk assessment
        if not context.get("has_ai_risk_assessment"):
            findings.append(
                ComplianceFinding(
                    rule_id="ISO42001-6",
                    severity="high",
                    description="No AI risk assessment process",
                    recommendation="Implement AI risk assessment and treatment (Clause 6)",
                )
            )

        # Clause 8: Operation — AI lifecycle
        if not context.get("has_ai_lifecycle_management"):
            findings.append(
                ComplianceFinding(
                    rule_id="ISO42001-8",
                    severity="high",
                    description="No AI system lifecycle management",
                    recommendation="Implement operational planning and control for AI systems (Clause 8)",
                )
            )

        # Clause 9: Performance evaluation
        if not context.get("has_ai_monitoring"):
            findings.append(
                ComplianceFinding(
                    rule_id="ISO42001-9",
                    severity="medium",
                    description="No AI performance monitoring and evaluation",
                    recommendation="Establish monitoring, measurement, and internal audit (Clause 9)",
                )
            )

        total_rules = 5
        passed_rules = total_rules - len(findings)
        score = passed_rules / total_rules if total_rules > 0 else 1.0

        return ComplianceResult(
            framework=ComplianceFramework.ISO_42001,
            passed=score >= 0.6,
            score=score,
            findings=findings,
        )
