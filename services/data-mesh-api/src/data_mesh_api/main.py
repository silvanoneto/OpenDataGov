"""Data Mesh Self-Serve API.

Self-serve platform for:
- Domain registration
- Data product publishing
- Contract management
- SLA monitoring
- Federated governance

Follows Data Mesh principles:
1. Domain-oriented: Each domain manages their own data products
2. Data as a Product: Publish with SLAs and quality guarantees
3. Self-serve Platform: Easy APIs for autonomy
4. Federated Governance: Domain-specific policies
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from odg_core.mesh import (
    DataContract,
    DataProduct,
    DataProductSpec,
    Domain,
    get_contract_manager,
    get_domain_registry,
    get_product_catalog,
)
from odg_core.mesh.contract import ContractStatus
from odg_core.mesh.data_product import DataProductTier
from odg_core.mesh.domain import DomainStatus
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle."""
    logger.info("Starting Data Mesh API...")

    # Initialize registries
    get_domain_registry()
    get_product_catalog()
    get_contract_manager()

    logger.info("✓ Data Mesh API initialized")

    yield

    logger.info("Shutting down Data Mesh API...")


app = FastAPI(
    title="OpenDataGov Data Mesh API",
    version="0.1.0",
    description="Self-serve platform for Data Mesh: domains, data products, contracts",
    lifespan=lifespan,
)


# ============================================================================
# Domain Management
# ============================================================================


@app.post("/api/v1/domains", response_model=Domain, tags=["domains"])
async def register_domain(domain: Domain) -> Domain:
    """Register a new data domain.

    Example:
        ```bash
        curl -X POST http://data-mesh-api:8007/api/v1/domains \\
          -H "Content-Type: application/json" \\
          -d '{
            "domain_id": "finance",
            "name": "Finance Domain",
            "description": "Financial data products",
            "owner_team": "finance-data-team",
            "owner_email": "finance@company.com",
            "min_dq_score": 0.95,
            "sla_freshness_hours": 12
          }'
        ```
    """
    registry = get_domain_registry()

    try:
        registered = registry.register_domain(domain)
        logger.info(f"Registered domain: {domain.domain_id}")
        return registered
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/v1/domains/{domain_id}", response_model=Domain, tags=["domains"])
async def get_domain(domain_id: str) -> Domain:
    """Get domain by ID."""
    registry = get_domain_registry()
    domain = registry.get_domain(domain_id)

    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain {domain_id} not found")

    return domain


@app.get("/api/v1/domains", response_model=list[Domain], tags=["domains"])
async def list_domains(
    status: DomainStatus | None = None,
) -> list[Domain]:
    """List all domains."""
    registry = get_domain_registry()
    return registry.list_domains(status=status)


# ============================================================================
# Data Product Management
# ============================================================================


class PublishProductRequest(BaseModel):
    """Request to publish a data product."""

    spec: DataProductSpec
    storage_location: str
    current_dq_score: float


@app.post("/api/v1/products", response_model=DataProduct, tags=["products"])
async def publish_data_product(request: PublishProductRequest) -> DataProduct:
    """Publish a new data product.

    Example:
        ```bash
        curl -X POST http://data-mesh-api:8007/api/v1/products \\
          -H "Content-Type: application/json" \\
          -d '{
            "spec": {
              "product_id": "finance.revenue",
              "name": "Revenue Data Product",
              "description": "Daily revenue metrics",
              "domain_id": "finance",
              "schema": [
                {"name": "date", "type": "DATE", "description": "Revenue date"},
                {"name": "amount", "type": "DECIMAL", "description": "Revenue amount"}
              ],
              "tier": "gold",
              "sla": {
                "freshness_hours": 12,
                "availability": 0.99,
                "completeness": 0.95,
                "accuracy": 0.95
              }
            },
            "storage_location": "s3://odg-gold/finance/revenue",
            "current_dq_score": 0.97
          }'
        ```
    """
    catalog = get_product_catalog()
    domain_registry = get_domain_registry()

    # Verify domain exists
    domain = domain_registry.get_domain(request.spec.domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain {request.spec.domain_id} not found")

    # Create data product from spec
    product = DataProduct(
        product_id=request.spec.product_id,
        name=request.spec.name,
        description=request.spec.description,
        domain_id=request.spec.domain_id,
        owner_email=domain.owner_email,
        storage_location=request.storage_location,
        schema=request.spec.schema,
        tier=request.spec.tier,
        current_dq_score=request.current_dq_score,
        sla=request.spec.sla,
        public=request.spec.public,
        allowed_consumers=request.spec.allowed_consumers,
        tags=request.spec.tags,
        documentation_url=request.spec.documentation_url,
    )

    try:
        published = catalog.publish_product(product)

        # Add to domain's product list
        domain_registry.add_data_product(request.spec.domain_id, request.spec.product_id)

        logger.info(f"Published data product: {product.product_id}")
        return published
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/v1/products/{product_id}", response_model=DataProduct, tags=["products"])
async def get_data_product(product_id: str) -> DataProduct:
    """Get data product by ID."""
    catalog = get_product_catalog()
    product = catalog.get_product(product_id)

    if not product:
        raise HTTPException(status_code=404, detail=f"Data product {product_id} not found")

    return product


@app.get("/api/v1/products", response_model=list[DataProduct], tags=["products"])
async def list_data_products(
    domain_id: str | None = None,
    tier: DataProductTier | None = None,
    public: bool | None = None,
) -> list[DataProduct]:
    """List data products with filters.

    Example:
        ```bash
        # List all Gold products
        curl http://data-mesh-api:8007/api/v1/products?tier=gold

        # List Finance domain products
        curl http://data-mesh-api:8007/api/v1/products?domain_id=finance

        # List public products
        curl http://data-mesh-api:8007/api/v1/products?public=true
        ```
    """
    catalog = get_product_catalog()
    return catalog.list_products(domain_id=domain_id, tier=tier, public=public)


@app.delete("/api/v1/products/{product_id}", tags=["products"])
async def deprecate_data_product(product_id: str, reason: str) -> DataProduct:
    """Deprecate a data product."""
    catalog = get_product_catalog()

    try:
        deprecated = catalog.deprecate_product(product_id, reason)
        logger.info(f"Deprecated data product: {product_id} (reason: {reason})")
        return deprecated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ============================================================================
# Contract Management
# ============================================================================


@app.post("/api/v1/contracts", response_model=DataContract, tags=["contracts"])
async def create_contract(contract: DataContract) -> DataContract:
    """Create a data contract between provider and consumer.

    Example:
        ```bash
        curl -X POST http://data-mesh-api:8007/api/v1/contracts \\
          -H "Content-Type: application/json" \\
          -d '{
            "contract_id": "contract_finance_sales_revenue",
            "provider_domain": "finance",
            "consumer_domain": "sales",
            "data_product_id": "finance.revenue",
            "sla_freshness_hours": 12,
            "sla_availability": 0.99,
            "sla_quality_score": 0.95,
            "schema_version": "1.0.0",
            "monthly_query_limit": 10000,
            "alert_email": "sales@company.com"
          }'
        ```
    """
    manager = get_contract_manager()
    catalog = get_product_catalog()

    # Verify data product exists
    product = catalog.get_product(contract.data_product_id)
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Data product {contract.data_product_id} not found",
        )

    try:
        created = manager.create_contract(contract)
        logger.info(
            f"Created contract: {contract.contract_id} ({contract.provider_domain} → {contract.consumer_domain})"
        )
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/v1/contracts/{contract_id}/activate", response_model=DataContract, tags=["contracts"])
async def activate_contract(contract_id: str) -> DataContract:
    """Activate a contract (both parties agreed)."""
    manager = get_contract_manager()

    try:
        activated = manager.activate_contract(contract_id)
        logger.info(f"Activated contract: {contract_id}")
        return activated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/v1/contracts/{contract_id}", response_model=DataContract, tags=["contracts"])
async def get_contract(contract_id: str) -> DataContract:
    """Get contract by ID."""
    manager = get_contract_manager()
    contract = manager.get_contract(contract_id)

    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")

    return contract


@app.get("/api/v1/contracts", response_model=list[DataContract], tags=["contracts"])
async def list_contracts(
    provider_domain: str | None = None,
    consumer_domain: str | None = None,
    status: ContractStatus | None = None,
) -> list[DataContract]:
    """List contracts with filters."""
    manager = get_contract_manager()
    return manager.list_contracts(
        provider_domain=provider_domain,
        consumer_domain=consumer_domain,
        status=status,
    )


@app.delete("/api/v1/contracts/{contract_id}", response_model=DataContract, tags=["contracts"])
async def terminate_contract(contract_id: str, reason: str) -> DataContract:
    """Terminate a contract."""
    manager = get_contract_manager()

    try:
        terminated = manager.terminate_contract(contract_id, reason)
        logger.info(f"Terminated contract: {contract_id} (reason: {reason})")
        return terminated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ============================================================================
# Health & Discovery
# ============================================================================


@app.get("/health")
async def health() -> dict:
    """Health check."""
    return {"status": "ok"}


@app.get("/api/v1/mesh/stats")
async def get_mesh_stats() -> dict:
    """Get Data Mesh statistics."""
    domain_registry = get_domain_registry()
    product_catalog = get_product_catalog()
    contract_manager = get_contract_manager()

    domains = domain_registry.list_domains()
    products = product_catalog.list_products()
    contracts = contract_manager.list_contracts()

    active_contracts = [c for c in contracts if c.status == ContractStatus.ACTIVE]

    return {
        "total_domains": len(domains),
        "total_products": len(products),
        "total_contracts": len(contracts),
        "active_contracts": len(active_contracts),
        "products_by_tier": {
            "bronze": len([p for p in products if p.tier == DataProductTier.BRONZE]),
            "silver": len([p for p in products if p.tier == DataProductTier.SILVER]),
            "gold": len([p for p in products if p.tier == DataProductTier.GOLD]),
            "platinum": len([p for p in products if p.tier == DataProductTier.PLATINUM]),
        },
    }
