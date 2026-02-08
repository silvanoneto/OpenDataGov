"""DAMA DMBOK compliance coverage checker (ADR-113)."""

from __future__ import annotations

from typing import Any

from odg_core.compliance.protocols import ComplianceFinding, ComplianceResult
from odg_core.enums import ComplianceFramework, DAMADimension

# DAMA DMBOK Knowledge Areas mapped to ODG capabilities
DAMA_KNOWLEDGE_AREAS: dict[str, str] = {
    "data_governance": "Governance Engine (RACI, approvals, audit)",
    "data_quality": "Quality Gate (6 DAMA dimensions, SLAs)",
    "metadata_management": "DataHub + Metadata Adapter",
    "data_architecture": "Medallion Architecture (Bronze/Silver/Gold/Platinum)",
    "data_modeling": "Data Contracts + Schema validation",
    "data_storage": "MinIO + PostgreSQL (cloud-agnostic)",
    "data_security": "Keycloak + OPA + Vault + PII masking",
    "data_integration": "NATS JetStream + Kafka + OpenLineage",
    "reference_data": "DataHub catalog + enriched metadata",
    "data_warehousing": "Lakehouse Agent (promotion pipeline)",
    "document_management": "Not yet implemented",
}


class DAMAChecker:
    """Checks DAMA DMBOK compliance coverage."""

    @property
    def framework(self) -> ComplianceFramework:
        return ComplianceFramework.DAMA_DMBOK

    def check(self, context: dict[str, Any]) -> ComplianceResult:
        findings: list[ComplianceFinding] = []
        implemented = context.get("implemented_areas", [])

        for area, description in DAMA_KNOWLEDGE_AREAS.items():
            if area not in implemented:
                severity = "high" if area in {"data_governance", "data_quality", "data_security"} else "medium"
                findings.append(
                    ComplianceFinding(
                        rule_id=f"DAMA-{area.upper()}",
                        severity=severity,
                        description=f"DAMA knowledge area not implemented: {area}",
                        recommendation=f"Implement: {description}",
                    )
                )

        # Check quality dimensions coverage
        quality_dimensions = context.get("quality_dimensions", [])
        for dim in DAMADimension:
            if dim.value not in quality_dimensions:
                findings.append(
                    ComplianceFinding(
                        rule_id=f"DAMA-DQ-{dim.value.upper()}",
                        severity="medium",
                        description=f"Quality dimension not measured: {dim.value}",
                        recommendation=f"Add {dim.value} quality checks to expectation suites",
                    )
                )

        total = len(DAMA_KNOWLEDGE_AREAS) + len(DAMADimension)
        passed = total - len(findings)
        score = passed / total if total > 0 else 0.0

        return ComplianceResult(
            framework=ComplianceFramework.DAMA_DMBOK,
            passed=score >= 0.7,
            score=score,
            findings=findings,
        )
