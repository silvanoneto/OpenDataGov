"""Storage backends for OpenDataGov.

Provides integrations with different storage systems and table formats:
- Apache Iceberg for versioned lakehouse tables
- Delta Lake (future)
- Object storage (S3/MinIO)
"""

from odg_core.storage.iceberg_catalog import IcebergCatalog

__all__ = ["IcebergCatalog"]
