"""Data Product model for Data Mesh.

A Data Product is a dataset published by a domain with:
- Clear ownership
- Quality guarantees (SLAs)
- Discoverability (metadata, documentation)
- Understandability (schema, samples)
- Trustworthiness (DQ scores, lineage)
- Addressability (stable URIs)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DataProductTier(StrEnum):
    """Data product tier based on quality and criticality."""

    BRONZE = "bronze"  # Raw, experimental
    SILVER = "silver"  # Validated, production-ready
    GOLD = "gold"  # High-quality, certified
    PLATINUM = "platinum"  # Mission-critical, premium SLA


class DataProductStatus(StrEnum):
    """Data product lifecycle status."""

    DRAFT = "draft"  # Being developed
    PUBLISHED = "published"  # Available for consumption
    DEPRECATED = "deprecated"  # Planned for retirement
    RETIRED = "retired"  # No longer available


class DataProductSLA(BaseModel):
    """Service Level Agreement for data product."""

    freshness_hours: int = Field(..., description="Max age of data in hours")
    availability: float = Field(..., ge=0.0, le=1.0, description="Availability % (e.g., 0.99 = 99%)")
    completeness: float = Field(..., ge=0.0, le=1.0, description="Min completeness score")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Min accuracy score")
    response_time_ms: int = Field(default=1000, description="Max response time in ms")


class DataProductSpec(BaseModel):
    """Data Product specification (blueprint).

    Defines the contract for a data product before it's created.
    """

    product_id: str = Field(..., description="Unique product ID (e.g., 'finance.revenue')")
    name: str = Field(..., description="Human-readable product name")
    description: str = Field(..., description="Product description")
    domain_id: str = Field(..., description="Owning domain")

    # Schema definition
    data_schema: list[dict[str, str]] = Field(..., description="Schema: [{'name', 'type', 'description'}]")

    # Quality requirements
    tier: DataProductTier = Field(default=DataProductTier.SILVER)
    sla: DataProductSLA = Field(..., description="SLA commitments")

    # Access control
    public: bool = Field(default=False, description="Publicly accessible")
    allowed_consumers: list[str] = Field(default_factory=list, description="Allowed consumer domain IDs")

    # Metadata
    tags: list[str] = Field(default_factory=list)
    documentation_url: str | None = Field(None, description="Link to documentation")


class DataProduct(BaseModel):
    """Data Product (deployed instance).

    Represents a published data product with:
    - Metadata
    - SLA commitments
    - Quality metrics
    - Access control
    - Usage statistics
    """

    product_id: str = Field(..., description="Unique product ID")
    name: str = Field(..., description="Product name")
    description: str = Field(..., description="Product description")
    domain_id: str = Field(..., description="Owning domain")
    owner_email: str = Field(..., description="Product owner email")

    # Location
    storage_location: str = Field(..., description="S3/Iceberg location")
    catalog_urn: str | None = Field(None, description="DataHub URN")

    # Schema
    data_schema: list[dict[str, str]] = Field(..., description="Dataset schema")
    sample_data_url: str | None = Field(None, description="Link to sample data")

    # Quality
    tier: DataProductTier = Field(default=DataProductTier.SILVER)
    current_dq_score: float = Field(..., ge=0.0, le=1.0, description="Current DQ score")
    sla: DataProductSLA = Field(..., description="SLA commitments")

    # Access control
    public: bool = Field(default=False)
    allowed_consumers: list[str] = Field(default_factory=list)
    active_contracts: list[str] = Field(default_factory=list, description="Active contract IDs")

    # Metadata
    tags: list[str] = Field(default_factory=list)
    documentation_url: str | None = None
    lineage_upstream: list[str] = Field(default_factory=list, description="Upstream data product IDs")
    lineage_downstream: list[str] = Field(default_factory=list, description="Downstream data product IDs")

    # Metrics
    total_consumers: int = Field(default=0, description="Number of active consumers")
    monthly_queries: int = Field(default=0, description="Queries in last 30 days")
    last_updated: datetime = Field(default_factory=datetime.now)

    # Status
    status: DataProductStatus = Field(default=DataProductStatus.PUBLISHED)
    created_at: datetime = Field(default_factory=datetime.now)
    version: str = Field(default="1.0.0", description="Semantic version")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "finance.revenue",
                "name": "Revenue Data Product",
                "description": "Daily revenue metrics by customer and product",
                "domain_id": "finance",
                "owner_email": "finance-data@company.com",
                "storage_location": "s3://odg-gold/finance/revenue",
                "tier": "gold",
                "current_dq_score": 0.97,
                "sla": {
                    "freshness_hours": 12,
                    "availability": 0.99,
                    "completeness": 0.95,
                    "accuracy": 0.95,
                },
                "public": False,
                "allowed_consumers": ["sales", "analytics"],
                "tags": ["revenue", "financial", "gdpr"],
            }
        }
    )


class DataProductCatalog:
    """Catalog of all data products."""

    def __init__(self) -> None:
        """Initialize data product catalog."""
        self.products: dict[str, DataProduct] = {}

    def publish_product(self, product: DataProduct) -> DataProduct:
        """Publish a data product.

        Args:
            product: Data product to publish

        Returns:
            Published product

        Raises:
            ValueError: If product already exists
        """
        if product.product_id in self.products:
            raise ValueError(f"Data product {product.product_id} already exists")

        product.status = DataProductStatus.PUBLISHED
        product.created_at = datetime.now()
        self.products[product.product_id] = product

        return product

    def get_product(self, product_id: str) -> DataProduct | None:
        """Get data product by ID.

        Args:
            product_id: Product identifier

        Returns:
            Data product or None
        """
        return self.products.get(product_id)

    def list_products(
        self,
        domain_id: str | None = None,
        tier: DataProductTier | None = None,
        public: bool | None = None,
        tags: list[str] | None = None,
    ) -> list[DataProduct]:
        """List data products with filters.

        Args:
            domain_id: Filter by domain
            tier: Filter by tier
            public: Filter by public flag
            tags: Filter by tags (must have all tags)

        Returns:
            List of data products
        """
        products = list(self.products.values())

        if domain_id:
            products = [p for p in products if p.domain_id == domain_id]

        if tier:
            products = [p for p in products if p.tier == tier]

        if public is not None:
            products = [p for p in products if p.public == public]

        if tags:
            products = [p for p in products if all(tag in p.tags for tag in tags)]

        return products

    def update_product(self, product_id: str, updates: dict[str, Any]) -> DataProduct:
        """Update data product.

        Args:
            product_id: Product identifier
            updates: Fields to update

        Returns:
            Updated product

        Raises:
            ValueError: If product not found
        """
        product = self.get_product(product_id)
        if not product:
            raise ValueError(f"Data product {product_id} not found")

        for key, value in updates.items():
            if hasattr(product, key):
                setattr(product, key, value)

        product.last_updated = datetime.now()
        return product

    def deprecate_product(self, product_id: str, reason: str) -> DataProduct:
        """Deprecate a data product.

        Args:
            product_id: Product identifier
            reason: Deprecation reason

        Returns:
            Deprecated product

        Raises:
            ValueError: If product not found
        """
        product = self.get_product(product_id)
        if not product:
            raise ValueError(f"Data product {product_id} not found")

        product.status = DataProductStatus.DEPRECATED
        product.last_updated = datetime.now()

        return product


# Global catalog instance
_catalog: DataProductCatalog | None = None


def get_product_catalog() -> DataProductCatalog:
    """Get or create global data product catalog.

    Returns:
        DataProductCatalog instance
    """
    global _catalog
    if _catalog is None:
        _catalog = DataProductCatalog()
    return _catalog
