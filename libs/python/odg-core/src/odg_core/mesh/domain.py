"""Domain model for Data Mesh.

A Domain represents a business capability with:
- Ownership: Team responsible for domain data
- Data Products: Datasets published by the domain
- Quality Standards: Domain-specific DQ requirements
- Governance Policies: Domain-specific rules
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DomainStatus(StrEnum):
    """Domain status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class Domain(BaseModel):
    """Data Mesh domain.

    Represents a business domain that owns and publishes data products.

    Examples:
    - Finance domain: revenue, transactions, budgets
    - Sales domain: opportunities, customers, contracts
    - HR domain: employees, payroll, performance
    """

    domain_id: str = Field(..., description="Unique domain identifier (e.g., 'finance')")
    name: str = Field(..., description="Human-readable domain name")
    description: str = Field(..., description="Domain description")
    owner_team: str = Field(..., description="Team owning this domain")
    owner_email: str = Field(..., description="Domain owner email")

    # Data product management
    data_products: list[str] = Field(default_factory=list, description="List of data product IDs")

    # Quality standards
    min_dq_score: float = Field(default=0.90, ge=0.0, le=1.0, description="Minimum DQ score for domain")
    required_dimensions: list[str] = Field(
        default_factory=lambda: ["completeness", "accuracy", "timeliness"],
        description="Required DAMA dimensions",
    )

    # Governance
    governance_policies: list[str] = Field(default_factory=list, description="Domain-specific governance policy IDs")
    tags: list[str] = Field(default_factory=list, description="Domain tags (e.g., 'pii', 'gdpr')")

    # SLA commitments
    sla_freshness_hours: int = Field(default=24, description="Max data freshness in hours")
    sla_availability: float = Field(default=0.99, ge=0.0, le=1.0, description="Availability SLA (e.g., 99%)")

    # Metadata
    status: DomainStatus = Field(default=DomainStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "domain_id": "finance",
                "name": "Finance Domain",
                "description": "Financial data products: revenue, transactions, budgets",
                "owner_team": "finance-data-team",
                "owner_email": "finance-data@company.com",
                "data_products": ["finance.revenue", "finance.transactions"],
                "min_dq_score": 0.95,
                "sla_freshness_hours": 12,
                "sla_availability": 0.99,
                "tags": ["gdpr", "sox_compliant"],
            }
        }
    )


class DomainRegistry:
    """Registry of all data mesh domains.

    Central registry for domain discovery and management.
    """

    def __init__(self) -> None:
        """Initialize domain registry."""
        self.domains: dict[str, Domain] = {}

    def register_domain(self, domain: Domain) -> Domain:
        """Register a new domain.

        Args:
            domain: Domain to register

        Returns:
            Registered domain

        Raises:
            ValueError: If domain already exists
        """
        if domain.domain_id in self.domains:
            raise ValueError(f"Domain {domain.domain_id} already exists")

        self.domains[domain.domain_id] = domain
        return domain

    def get_domain(self, domain_id: str) -> Domain | None:
        """Get domain by ID.

        Args:
            domain_id: Domain identifier

        Returns:
            Domain or None if not found
        """
        return self.domains.get(domain_id)

    def list_domains(
        self,
        status: DomainStatus | None = None,
        tags: list[str] | None = None,
    ) -> list[Domain]:
        """List domains with optional filters.

        Args:
            status: Filter by status
            tags: Filter by tags (domain must have all tags)

        Returns:
            List of domains
        """
        domains = list(self.domains.values())

        if status:
            domains = [d for d in domains if d.status == status]

        if tags:
            domains = [d for d in domains if all(tag in d.tags for tag in tags)]

        return domains

    def update_domain(self, domain_id: str, updates: dict[str, Any]) -> Domain:
        """Update domain.

        Args:
            domain_id: Domain identifier
            updates: Fields to update

        Returns:
            Updated domain

        Raises:
            ValueError: If domain not found
        """
        domain = self.get_domain(domain_id)
        if not domain:
            raise ValueError(f"Domain {domain_id} not found")

        for key, value in updates.items():
            if hasattr(domain, key):
                setattr(domain, key, value)

        domain.updated_at = datetime.now()
        return domain

    def add_data_product(self, domain_id: str, data_product_id: str) -> Domain:
        """Add data product to domain.

        Args:
            domain_id: Domain identifier
            data_product_id: Data product identifier

        Returns:
            Updated domain

        Raises:
            ValueError: If domain not found
        """
        domain = self.get_domain(domain_id)
        if not domain:
            raise ValueError(f"Domain {domain_id} not found")

        if data_product_id not in domain.data_products:
            domain.data_products.append(data_product_id)
            domain.updated_at = datetime.now()

        return domain

    def remove_data_product(self, domain_id: str, data_product_id: str) -> Domain:
        """Remove data product from domain.

        Args:
            domain_id: Domain identifier
            data_product_id: Data product identifier

        Returns:
            Updated domain

        Raises:
            ValueError: If domain not found
        """
        domain = self.get_domain(domain_id)
        if not domain:
            raise ValueError(f"Domain {domain_id} not found")

        if data_product_id in domain.data_products:
            domain.data_products.remove(data_product_id)
            domain.updated_at = datetime.now()

        return domain


# Global registry instance
_registry: DomainRegistry | None = None


def get_domain_registry() -> DomainRegistry:
    """Get or create global domain registry.

    Returns:
        DomainRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = DomainRegistry()
    return _registry
