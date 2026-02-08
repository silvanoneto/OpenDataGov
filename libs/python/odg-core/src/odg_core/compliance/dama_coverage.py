"""DAMA DMBOK coverage report (ADR-113).

Maps the 11 DAMA knowledge areas to ODG components and tracks
implementation coverage.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeAreaCoverage(BaseModel):
    """Coverage details for a single DAMA knowledge area."""

    area: str
    description: str
    components: list[str] = Field(default_factory=list)
    adrs: list[str] = Field(default_factory=list)
    coverage_level: str = "none"  # none, partial, full


class DAMACoverageReport(BaseModel):
    """Full DAMA DMBOK coverage report."""

    areas: list[KnowledgeAreaCoverage] = Field(default_factory=list)
    overall_coverage: float = 0.0

    def compute_coverage(self) -> float:
        """Compute overall coverage percentage."""
        if not self.areas:
            return 0.0
        weights = {"none": 0.0, "partial": 0.5, "full": 1.0}
        total = sum(weights.get(a.coverage_level, 0.0) for a in self.areas)
        self.overall_coverage = total / len(self.areas)
        return self.overall_coverage


def build_default_coverage() -> DAMACoverageReport:
    """Build the default ODG DAMA coverage report."""
    areas = [
        KnowledgeAreaCoverage(
            area="Data Governance",
            description="Planning, oversight, and control of data management",
            components=["governance-engine", "RACI workflow", "audit trail"],
            adrs=["ADR-010", "ADR-011", "ADR-013", "ADR-014"],
            coverage_level="full",
        ),
        KnowledgeAreaCoverage(
            area="Data Quality",
            description="Ensuring data fitness for use",
            components=["quality-gate", "Great Expectations", "DAMA 6 dimensions", "SLAs"],
            adrs=["ADR-050", "ADR-051", "ADR-052"],
            coverage_level="full",
        ),
        KnowledgeAreaCoverage(
            area="Metadata Management",
            description="Managing data about data",
            components=["DataHub", "metadata adapter", "active metadata"],
            adrs=["ADR-040", "ADR-041", "ADR-042"],
            coverage_level="full",
        ),
        KnowledgeAreaCoverage(
            area="Data Architecture",
            description="Data structures and integration blueprint",
            components=["Medallion Architecture", "data contracts"],
            adrs=["ADR-024", "ADR-051"],
            coverage_level="full",
        ),
        KnowledgeAreaCoverage(
            area="Data Modeling & Design",
            description="Discovering, analyzing, and representing data requirements",
            components=["data contracts", "schema validation", "breaking change detection"],
            adrs=["ADR-051"],
            coverage_level="full",
        ),
        KnowledgeAreaCoverage(
            area="Data Storage & Operations",
            description="Managing data storage and data throughout lifecycle",
            components=["MinIO (S3)", "PostgreSQL", "Redis"],
            adrs=["ADR-024"],
            coverage_level="full",
        ),
        KnowledgeAreaCoverage(
            area="Data Security",
            description="Ensuring data privacy, confidentiality, and access",
            components=["Keycloak", "OPA", "Vault", "PII masking", "classification"],
            adrs=["ADR-070", "ADR-071", "ADR-072", "ADR-073", "ADR-074"],
            coverage_level="full",
        ),
        KnowledgeAreaCoverage(
            area="Data Integration & Interoperability",
            description="Managing data movement and consolidation",
            components=["NATS JetStream", "Kafka", "OpenLineage", "OTel"],
            adrs=["ADR-060", "ADR-061", "ADR-062"],
            coverage_level="full",
        ),
        KnowledgeAreaCoverage(
            area="Reference & Master Data",
            description="Managing shared data to reduce redundancy",
            components=["DataHub catalog", "enriched metadata"],
            adrs=["ADR-040"],
            coverage_level="partial",
        ),
        KnowledgeAreaCoverage(
            area="Data Warehousing & BI",
            description="Managing analytical data processing",
            components=["lakehouse-agent", "promotion pipeline"],
            adrs=["ADR-024"],
            coverage_level="full",
        ),
        KnowledgeAreaCoverage(
            area="Document & Content Management",
            description="Managing unstructured data and documents",
            components=[],
            adrs=[],
            coverage_level="none",
        ),
    ]

    report = DAMACoverageReport(areas=areas)
    report.compute_coverage()
    return report
