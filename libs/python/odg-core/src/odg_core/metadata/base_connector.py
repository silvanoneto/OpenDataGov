"""Base class for metadata catalog connectors (ADR-131).

All catalog connectors must extend BaseConnector and implement ETL pattern:
extract(), transform(), load().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class DatasetMetadata(BaseModel):
    """Standardized dataset metadata."""

    name: str
    description: str = ""
    layer: str  # bronze, silver, gold, platinum
    classification: str = "internal"  # public, internal, sensitive, confidential
    domain_id: str
    owner_id: str
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    source_system: str = ""
    datahub_urn: str | None = None


class LineageRelationship(BaseModel):
    """Lineage relationship between datasets."""

    from_dataset: str  # Source dataset name/URN
    to_dataset: str  # Target dataset name/URN
    relationship_type: str = "DEPENDS_ON"  # DEPENDS_ON, PRODUCES, DERIVES_FROM
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetadataExtract(BaseModel):
    """Raw extracted metadata from source system."""

    datasets: list[dict[str, Any]] = Field(default_factory=list)
    lineage: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional system metadata")


class BaseConnector(ABC):
    """Abstract base class for metadata catalog connectors.

    Implements ETL pattern for metadata ingestion:
    1. Extract: Pull raw metadata from source system
    2. Transform: Convert to standardized DatasetMetadata format
    3. Load: Push to OpenDataGov catalog (DataHub)

    Example:
        class PostgresConnector(BaseConnector):
            def __init__(self, connection_string: str):
                self.connection_string = connection_string

            async def extract(self) -> MetadataExtract:
                # Query pg_catalog for tables, columns, etc.
                return MetadataExtract(datasets=[...], lineage=[...])

            async def transform(self, raw: MetadataExtract) -> list[DatasetMetadata]:
                # Convert Postgres tables to DatasetMetadata
                return [DatasetMetadata(...) for table in raw.datasets]

            async def load(self, metadata: list[DatasetMetadata]) -> None:
                # Push to DataHub via REST API
                for dataset in metadata:
                    await datahub_client.emit_dataset(dataset)

            def get_source_type(self) -> str:
                return "postgresql"
    """

    @abstractmethod
    async def extract(self) -> MetadataExtract:
        """Extract raw metadata from source system.

        Returns:
            MetadataExtract with raw datasets and lineage

        Raises:
            Exception: If extraction fails
        """
        ...

    @abstractmethod
    async def transform(self, raw: MetadataExtract) -> list[DatasetMetadata]:
        """Transform raw metadata to standardized format.

        Args:
            raw: Raw extracted metadata

        Returns:
            List of standardized DatasetMetadata objects

        Raises:
            Exception: If transformation fails
        """
        ...

    @abstractmethod
    async def load(self, metadata: list[DatasetMetadata]) -> None:
        """Load metadata into OpenDataGov catalog.

        Args:
            metadata: List of DatasetMetadata to load

        Raises:
            Exception: If load fails
        """
        ...

    @abstractmethod
    def get_source_type(self) -> str:
        """Return the source system type (e.g., 'postgresql', 'snowflake', 's3')."""
        ...

    def get_name(self) -> str:
        """Return human-readable connector name (defaults to class name)."""
        return self.__class__.__name__

    def get_description(self) -> str:
        """Return connector description (defaults to docstring)."""
        return (self.__class__.__doc__ or "").strip()

    async def initialize(self) -> None:  # noqa: B027
        """Initialize connector (establish connections, auth, etc.)."""

    async def shutdown(self) -> None:  # noqa: B027
        """Gracefully shutdown connector."""

    async def run(self) -> int:
        """Run full ETL pipeline: extract → transform → load.

        Returns:
            Number of datasets loaded

        Raises:
            Exception: If any step fails
        """
        # Extract
        raw = await self.extract()

        # Transform
        datasets = await self.transform(raw)

        # Load
        await self.load(datasets)

        return len(datasets)
