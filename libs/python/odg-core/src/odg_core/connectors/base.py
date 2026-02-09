"""Base connector interface for data ingestion sources.

All data source connectors must inherit from BaseConnector and implement
the required methods for authentication, data extraction, and schema detection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


class ConnectorStatus(StrEnum):
    """Connector execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Some records failed


@dataclass
class ConnectorConfig:
    """Base configuration for data source connectors."""

    connector_type: str  # e.g., "rest_api", "web_scraper", "s3"
    source_name: str  # User-friendly name
    schedule: str | None = None  # Cron expression for scheduled ingestion
    enabled: bool = True

    # Authentication
    auth_type: str | None = None  # "basic", "bearer", "oauth2", "api_key", "none"
    credentials: dict[str, str] = field(default_factory=dict)

    # Target storage
    target_database: str | None = "bronze"  # PostgreSQL/CouchDB database
    target_table: str | None = None  # Table/collection name
    target_layer: str = "bronze"  # Medallion layer

    # Data processing
    extract_schema: bool = True  # Auto-detect schema
    validate_data: bool = True  # Validate against schema
    batch_size: int = 1000  # Records per batch

    # Metadata
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionResult:
    """Result of a data ingestion run."""

    status: ConnectorStatus
    records_ingested: int
    records_failed: int
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    error_message: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.records_ingested + self.records_failed
        if total == 0:
            return 0.0
        return self.records_ingested / total


class BaseConnector(ABC):
    """Abstract base class for all data source connectors.

    Subclasses must implement:
    - connect(): Establish connection to source
    - extract(): Extract data from source
    - get_schema(): Detect data schema
    """

    def __init__(self, config: ConnectorConfig):
        """Initialize connector with configuration.

        Args:
            config: Connector configuration
        """
        self.config = config
        self._connected = False

    @abstractmethod
    def connect(self) -> None:
        """Connect to the data source.

        Raises:
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Extract data from the source.

        Yields:
            Records as dictionaries

        Example:
            >>> connector = MyConnector(config)
            >>> connector.connect()
            >>> for record in connector.extract(limit=100):
            ...     print(record)
        """
        pass

    @abstractmethod
    def get_schema(self) -> dict[str, Any]:
        """Detect or retrieve schema from source.

        Returns:
            Schema definition (JSON Schema format)
        """
        pass

    def disconnect(self) -> None:
        """Disconnect from the data source.

        Override this method if cleanup is needed.
        """
        self._connected = False

    def validate_record(self, record: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate a record against the source schema.

        Args:
            record: Record to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation - subclasses can override
        if not isinstance(record, dict):
            return False, "Record must be a dictionary"

        return True, None

    def ingest(self, **kwargs: Any) -> IngestionResult:
        """Run complete ingestion process.

        Args:
            **kwargs: Additional parameters for extract()

        Returns:
            Ingestion result with statistics

        Example:
            >>> result = connector.ingest(limit=1000)
            >>> print(f"Ingested {result.records_ingested} records")
        """
        import uuid

        from odg_core.lineage.emitter import emit_lineage_event

        start_time = datetime.now(UTC)
        run_id = str(uuid.uuid4())

        records_ingested = 0
        records_failed = 0
        errors = []

        try:
            # Connect to source
            if not self._connected:
                self.connect()

            # Extract and validate data
            for record in self.extract(**kwargs):
                is_valid, error_msg = self.validate_record(record)

                if is_valid:
                    # Store record (implement in subclass or use separate writer)
                    self._store_record(record)
                    records_ingested += 1
                else:
                    records_failed += 1
                    errors.append({"record": record, "error": error_msg, "timestamp": datetime.now(UTC).isoformat()})

            end_time = datetime.now(UTC)
            duration = (end_time - start_time).total_seconds()

            # Determine final status
            if records_failed == 0:
                status = ConnectorStatus.SUCCESS
            elif records_ingested > 0:
                status = ConnectorStatus.PARTIAL
            else:
                status = ConnectorStatus.FAILED

            # Emit lineage event
            emit_lineage_event(
                job_name=f"ingest_{self.config.source_name}",
                job_namespace="connectors",
                inputs=[
                    {
                        "namespace": self.config.connector_type,
                        "name": self.config.source_name,
                        "facets": {"connector_config": self.config.__dict__},
                    }
                ],
                outputs=[
                    {
                        "namespace": self.config.target_layer,
                        "name": self.config.target_table or self.config.source_name,
                        "facets": {"records_ingested": records_ingested, "records_failed": records_failed},
                    }
                ],
                event_type="COMPLETE",
                run_id=run_id,
            )

            return IngestionResult(
                status=status,
                records_ingested=records_ingested,
                records_failed=records_failed,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                errors=errors[:100],  # Limit error list
                metadata={
                    "run_id": run_id,
                    "connector_type": self.config.connector_type,
                    "source_name": self.config.source_name,
                },
            )

        except Exception as e:
            end_time = datetime.now(UTC)
            duration = (end_time - start_time).total_seconds()

            return IngestionResult(
                status=ConnectorStatus.FAILED,
                records_ingested=records_ingested,
                records_failed=records_failed,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error_message=str(e),
                metadata={"run_id": run_id, "connector_type": self.config.connector_type},
            )

        finally:
            self.disconnect()

    def _store_record(self, record: dict[str, Any]) -> None:
        """Store a validated record to target storage.

        Args:
            record: Record to store

        Note:
            Override this method or use a separate DataWriter class.
        """
        # Default implementation: write to CouchDB bronze layer
        try:
            import uuid

            from odg_core.nosql import CouchDBClient

            client = CouchDBClient()
            client.connect()

            db_name = self.config.target_database or "bronze"
            doc_id = record.get("id") or str(uuid.uuid4())

            # Add metadata
            record["_source"] = self.config.source_name
            record["_ingested_at"] = datetime.now(UTC).isoformat()
            record["_connector_type"] = self.config.connector_type

            client.save_document(db_name, doc_id, record)

        except Exception as e:
            print(f"Warning: Failed to store record: {e}")
