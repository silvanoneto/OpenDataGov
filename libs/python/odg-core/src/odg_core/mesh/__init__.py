"""Data Mesh architecture for OpenDataGov.

Implements Data Mesh principles:
1. Domain-oriented decentralized data ownership
2. Data as a product
3. Self-serve data infrastructure as a platform
4. Federated computational governance

Key concepts:
- Domain: Business domain owning data (Finance, Sales, HR, etc.)
- Data Product: Dataset published by a domain with SLAs
- Contract: Agreement between data product provider and consumer
- Federated Policy: Domain-specific governance rules
"""

from odg_core.mesh.contract import ContractStatus, DataContract
from odg_core.mesh.data_product import DataProduct, DataProductSpec
from odg_core.mesh.domain import Domain, DomainRegistry

__all__ = [
    "ContractStatus",
    "DataContract",
    "DataProduct",
    "DataProductSpec",
    "Domain",
    "DomainRegistry",
]
