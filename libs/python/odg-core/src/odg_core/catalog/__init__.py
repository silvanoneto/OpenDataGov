"""Data Catalog integration for OpenDataGov.

Provides DataHub client for:
- Dataset registration (medallion lakehouse)
- Lineage tracking (transformations, ML pipelines)
- Metadata management
- Data discovery
"""

from odg_core.catalog.datahub_client import DataHubClient

__all__ = ["DataHubClient"]
