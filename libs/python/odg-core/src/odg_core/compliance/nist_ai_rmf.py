"""NIST AI Risk Management Framework compliance checker (ADR-110)."""

from __future__ import annotations

from typing import Any

from odg_core.compliance.protocols import ComplianceFinding, ComplianceResult
from odg_core.enums import ComplianceFramework


class NISTAIRMFChecker:
    """Checks compliance with NIST AI RMF (AI 100-1)."""

    @property
    def framework(self) -> ComplianceFramework:
        return ComplianceFramework.NIST_AI_RMF

    def check(self, context: dict[str, Any]) -> ComplianceResult:
        findings: list[ComplianceFinding] = []

        # GOVERN function
        if not context.get("has_ai_governance_policy"):
            findings.append(
                ComplianceFinding(
                    rule_id="NIST-GOVERN-1",
                    severity="high",
                    description="No AI governance policies and procedures established",
                    recommendation="Define organizational AI risk management policies (GOVERN 1.1-1.7)",
                )
            )

        # MAP function
        if not context.get("has_ai_risk_mapping"):
            findings.append(
                ComplianceFinding(
                    rule_id="NIST-MAP-1",
                    severity="medium",
                    description="AI system context and risk not mapped",
                    recommendation="Map AI system context, stakeholders, and risk (MAP 1.1-1.6)",
                )
            )

        # MEASURE function
        if not context.get("has_ai_metrics"):
            findings.append(
                ComplianceFinding(
                    rule_id="NIST-MEASURE-1",
                    severity="medium",
                    description="No AI performance and risk metrics defined",
                    recommendation="Define quantitative metrics for AI trustworthiness (MEASURE 1.1-1.3)",
                )
            )

        # MANAGE function
        if not context.get("has_ai_incident_response"):
            findings.append(
                ComplianceFinding(
                    rule_id="NIST-MANAGE-1",
                    severity="high",
                    description="No AI incident response plan",
                    recommendation="Establish AI risk response and monitoring (MANAGE 1.1-1.4)",
                )
            )

        total_rules = 4
        passed_rules = total_rules - len(findings)
        score = passed_rules / total_rules if total_rules > 0 else 1.0

        return ComplianceResult(
            framework=ComplianceFramework.NIST_AI_RMF,
            passed=score >= 0.5,
            score=score,
            findings=findings,
        )
