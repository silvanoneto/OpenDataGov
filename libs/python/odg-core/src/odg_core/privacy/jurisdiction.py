"""Jurisdiction-based data residency rules (ADR-074)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from odg_core.enums import ComplianceFramework, Jurisdiction

# Mapping: jurisdiction -> applicable compliance frameworks
JURISDICTION_FRAMEWORKS: dict[Jurisdiction, list[ComplianceFramework]] = {
    Jurisdiction.BR: [ComplianceFramework.LGPD, ComplianceFramework.DAMA_DMBOK],
    Jurisdiction.EU: [ComplianceFramework.GDPR, ComplianceFramework.EU_AI_ACT, ComplianceFramework.DAMA_DMBOK],
    Jurisdiction.US: [ComplianceFramework.SOX, ComplianceFramework.NIST_AI_RMF, ComplianceFramework.DAMA_DMBOK],
    Jurisdiction.GLOBAL: [ComplianceFramework.ISO_42001, ComplianceFramework.DAMA_DMBOK],
}


class JurisdictionPolicy(BaseModel):
    """Data residency and jurisdiction policy."""

    jurisdiction: Jurisdiction
    allowed_regions: list[str] = Field(default_factory=list)
    data_transfer_restricted: bool = Field(default=False)
    applicable_frameworks: list[ComplianceFramework] = Field(default_factory=list)


def get_jurisdiction_policy(jurisdiction: Jurisdiction) -> JurisdictionPolicy:
    """Get the default policy for a jurisdiction."""
    frameworks = JURISDICTION_FRAMEWORKS.get(jurisdiction, [])
    return JurisdictionPolicy(
        jurisdiction=jurisdiction,
        applicable_frameworks=frameworks,
        data_transfer_restricted=jurisdiction in {Jurisdiction.EU, Jurisdiction.BR},
    )
