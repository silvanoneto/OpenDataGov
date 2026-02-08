"""EU AI Act compliance checker (ADR-111)."""

from __future__ import annotations

from typing import Any

from odg_core.compliance.protocols import ComplianceFinding, ComplianceResult
from odg_core.enums import AIRiskLevel, ComplianceFramework


class EUAIActChecker:
    """Checks compliance with EU AI Act based on risk classification."""

    @property
    def framework(self) -> ComplianceFramework:
        return ComplianceFramework.EU_AI_ACT

    def check(self, context: dict[str, Any]) -> ComplianceResult:
        findings: list[ComplianceFinding] = []
        risk_level = AIRiskLevel(context.get("ai_risk_level", "minimal"))

        if risk_level == AIRiskLevel.HIGH:
            if not context.get("has_risk_management_system"):
                findings.append(
                    ComplianceFinding(
                        rule_id="AI-ACT-9",
                        severity="critical",
                        description="High-risk AI system lacks risk management system",
                        recommendation="Implement continuous risk management per Art. 9",
                    )
                )

            if not context.get("has_data_governance"):
                findings.append(
                    ComplianceFinding(
                        rule_id="AI-ACT-10",
                        severity="critical",
                        description="High-risk AI system lacks data governance measures",
                        recommendation="Establish data governance for training/validation data",
                    )
                )

            if not context.get("has_human_oversight"):
                findings.append(
                    ComplianceFinding(
                        rule_id="AI-ACT-14",
                        severity="high",
                        description="No human oversight mechanism for high-risk AI",
                        recommendation="Implement human-in-the-loop oversight mechanisms",
                    )
                )

        if risk_level in {AIRiskLevel.HIGH, AIRiskLevel.LIMITED} and not context.get("has_transparency_info"):
            findings.append(
                ComplianceFinding(
                    rule_id="AI-ACT-52",
                    severity="medium",
                    description="AI system transparency requirements not met",
                    recommendation="Provide clear information about AI system capabilities and limitations",
                )
            )

        total_rules = 4 if risk_level == AIRiskLevel.HIGH else 1
        passed_rules = total_rules - len(findings)
        score = passed_rules / total_rules if total_rules > 0 else 1.0
        critical_count = sum(1 for f in findings if f.severity == "critical")

        return ComplianceResult(
            framework=ComplianceFramework.EU_AI_ACT,
            passed=critical_count == 0,
            score=score,
            findings=findings,
            metadata={"risk_level": risk_level.value},
        )
