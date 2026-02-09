"""Data source connectors for ingesting data from various sources.

Provides pluggable connectors for:
- REST APIs
- GraphQL APIs
- Web scraping (public sites)
- File sources (S3, FTP, HTTP)
- SaaS platforms (Salesforce, Google Analytics, etc.)
"""

from odg_core.connectors.api_connector import APIConnector, GraphQLConnector, RESTConnector
from odg_core.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
    IngestionResult,
)
from odg_core.connectors.file_connector import FileConnector, FTPConnector, S3Connector
from odg_core.connectors.web_scraper import WebScraperConnector

__all__ = [
    # API connectors
    "APIConnector",
    # Base classes
    "BaseConnector",
    "ConnectorConfig",
    "ConnectorStatus",
    "FTPConnector",
    # File sources
    "FileConnector",
    "GraphQLConnector",
    "IngestionResult",
    "RESTConnector",
    "S3Connector",
    # Web scraping
    "WebScraperConnector",
]
