"""Protocol interfaces for metadata catalog operations (ADR-041)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from odg_core.metadata.odg_schema import ODGDatasetMetadata


class MetadataCatalog(Protocol):
    """Abstract interface for metadata catalog backends."""

    async def register(self, metadata: ODGDatasetMetadata) -> None:
        """Register or update dataset metadata in the catalog."""
        ...

    async def get(self, dataset_id: str) -> ODGDatasetMetadata | None:
        """Retrieve dataset metadata by ID."""
        ...

    async def search(self, query: str, limit: int = 20) -> list[ODGDatasetMetadata]:
        """Search datasets by keyword."""
        ...
