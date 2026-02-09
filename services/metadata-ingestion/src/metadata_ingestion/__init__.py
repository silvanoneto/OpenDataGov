"""Metadata Ingestion Service for DataHub.

Automatically ingests metadata from:
- Lakehouse layer promotions
- MLflow model registrations
- Feast feature materializations
- Kubeflow pipeline executions
"""

from metadata_ingestion.ingestion_service import MetadataIngestionService

__all__ = ["MetadataIngestionService"]
__version__ = "0.1.0"
