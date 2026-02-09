"""CouchDB client for document storage in OpenDataGov.

Provides high-level interface for storing and retrieving JSON documents
in Apache CouchDB with automatic versioning and change tracking.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

try:
    import couchdb as _couchdb_module
except ImportError:
    _couchdb_module = None


class CouchDBClient:
    """Client for Apache CouchDB document storage.

    Example:
        >>> from odg_core.nosql import CouchDBClient
        >>>
        >>> client = CouchDBClient(url="http://couchdb-svc:5984")
        >>> client.connect(username="admin", password="changeme")
        >>>
        >>> # Store model metadata
        >>> client.save_document(
        ...     db_name="model_registry",
        ...     doc_id="churn_predictor_v1",
        ...     document={
        ...         "model_name": "churn_predictor",
        ...         "version": 1,
        ...         "framework": "sklearn",
        ...         "metrics": {"accuracy": 0.95, "f1": 0.92}
        ...     }
        ... )
        >>>
        >>> # Retrieve document
        >>> doc = client.get_document("model_registry", "churn_predictor_v1")
    """

    def __init__(self, url: str | None = None, username: str | None = None, password: str | None = None):
        """Initialize CouchDB client.

        Args:
            url: CouchDB server URL (e.g., "http://couchdb-svc:5984")
            username: Admin username (optional if provided in connect())
            password: Admin password (optional if provided in connect())
        """
        if _couchdb_module is None:
            raise ImportError("couchdb-python not installed. Install with: pip install couchdb")

        self.url = url or os.getenv("COUCHDB_URL", "http://couchdb-svc:5984")
        self._username = username or os.getenv("COUCHDB_USERNAME")
        self._password = password or os.getenv("COUCHDB_PASSWORD")
        self._server: Any = None
        self._connected = False

    def connect(self, username: str | None = None, password: str | None = None) -> None:
        """Connect to CouchDB server.

        Args:
            username: Admin username (overrides constructor value)
            password: Admin password (overrides constructor value)

        Raises:
            Exception: If connection fails
        """
        username = username or self._username
        password = password or self._password

        if not username or not password:
            raise ValueError("CouchDB credentials not provided")

        try:
            self._server = _couchdb_module.Server(self.url)
            self._server.resource.credentials = (username, password)

            # Test connection
            _ = self._server.version()
            self._connected = True

        except Exception as e:
            raise Exception(f"Failed to connect to CouchDB at {self.url}: {e}") from e

    def _ensure_connected(self) -> Any:
        """Ensure server is connected and return the server instance.

        Returns:
            The CouchDB server instance.

        Raises:
            RuntimeError: If not connected and connect() fails.
        """
        if not self._connected:
            self.connect()
        if self._server is None:
            raise RuntimeError("CouchDB server not connected")
        return self._server

    def create_database(self, db_name: str) -> bool:
        """Create a new database if it doesn't exist.

        Args:
            db_name: Database name

        Returns:
            True if database was created, False if it already existed
        """
        server = self._ensure_connected()

        if db_name in server:
            return False

        server.create(db_name)
        return True

    def delete_database(self, db_name: str) -> bool:
        """Delete a database.

        Args:
            db_name: Database name

        Returns:
            True if database was deleted, False if it didn't exist

        Warning:
            This operation is irreversible!
        """
        server = self._ensure_connected()

        if db_name not in server:
            return False

        del server[db_name]
        return True

    def list_databases(self) -> list[str]:
        """List all databases.

        Returns:
            List of database names
        """
        server = self._ensure_connected()

        return list(server)

    def save_document(
        self, db_name: str, doc_id: str, document: dict[str, Any], auto_timestamp: bool = True
    ) -> dict[str, Any]:
        """Save or update a document.

        Args:
            db_name: Database name
            doc_id: Document ID
            document: Document data (will be JSON-serialized)
            auto_timestamp: Add _created_at/_updated_at timestamps

        Returns:
            Saved document with CouchDB metadata (_id, _rev)

        Example:
            >>> client.save_document(
            ...     db_name="governance_documents",
            ...     doc_id="decision_001",
            ...     document={"title": "Approve dataset", "status": "approved"}
            ... )
        """
        server = self._ensure_connected()

        # Ensure database exists
        if db_name not in server:
            self.create_database(db_name)

        db = server[db_name]

        # Check if document exists (for update)
        existing_doc = None
        if doc_id in db:
            existing_doc = db[doc_id]

        # Prepare document
        doc = {"_id": doc_id, **document}

        if auto_timestamp:
            if existing_doc:
                # Preserve creation time on update
                doc["_created_at"] = existing_doc.get("_created_at", datetime.now(UTC).isoformat())
                doc["_updated_at"] = datetime.now(UTC).isoformat()
            else:
                # Set creation time for new document
                doc["_created_at"] = datetime.now(UTC).isoformat()
                doc["_updated_at"] = datetime.now(UTC).isoformat()

        # Preserve _rev for updates
        if existing_doc:
            doc["_rev"] = existing_doc["_rev"]

        # Save document
        db.save(doc)

        return doc

    def get_document(self, db_name: str, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by ID.

        Args:
            db_name: Database name
            doc_id: Document ID

        Returns:
            Document data or None if not found
        """
        server = self._ensure_connected()

        if db_name not in server:
            return None

        db = server[db_name]

        if doc_id not in db:
            return None

        return dict(db[doc_id])

    def delete_document(self, db_name: str, doc_id: str) -> bool:
        """Delete a document.

        Args:
            db_name: Database name
            doc_id: Document ID

        Returns:
            True if document was deleted, False if not found
        """
        server = self._ensure_connected()

        if db_name not in server:
            return False

        db = server[db_name]

        if doc_id not in db:
            return False

        doc = db[doc_id]
        db.delete(doc)
        return True

    def query_view(self, db_name: str, design_doc: str, view_name: str, **params: Any) -> list[dict[str, Any]]:
        """Query a CouchDB view.

        Args:
            db_name: Database name
            design_doc: Design document name (without _design/ prefix)
            view_name: View name
            **params: View parameters (key, startkey, endkey, limit, etc.)

        Returns:
            List of documents matching the view query

        Example:
            >>> # Query models by framework
            >>> results = client.query_view(
            ...     db_name="model_registry",
            ...     design_doc="models",
            ...     view_name="by_framework",
            ...     key="sklearn"
            ... )
        """
        server = self._ensure_connected()

        if db_name not in server:
            return []

        db = server[db_name]

        view_path = f"_design/{design_doc}/_view/{view_name}"

        try:
            results = db.view(view_path, **params)
            return [{"id": row.id, "key": row.key, "value": row.value} for row in results]
        except Exception:
            return []

    def create_index(self, db_name: str, index_fields: list[str], index_name: str | None = None) -> dict[str, Any]:
        """Create a Mango query index.

        Args:
            db_name: Database name
            index_fields: List of fields to index
            index_name: Optional index name (auto-generated if not provided)

        Returns:
            Index creation result

        Example:
            >>> # Create index on model_name and version
            >>> client.create_index(
            ...     db_name="model_registry",
            ...     index_fields=["model_name", "version"],
            ...     index_name="model_version_idx"
            ... )
        """
        server = self._ensure_connected()

        server[db_name]

        index_def = {
            "index": {"fields": index_fields},
            "name": index_name or f"idx_{'_'.join(index_fields)}",
            "type": "json",
        }

        if not self._username or not self._password:
            raise ValueError("CouchDB credentials not available")

        # Use HTTP API for index creation (couchdb-python doesn't support Mango directly)
        import requests
        from requests.auth import HTTPBasicAuth

        response = requests.post(
            f"{self.url}/{db_name}/_index",
            json=index_def,
            auth=HTTPBasicAuth(self._username, self._password),
            headers={"Content-Type": "application/json"},
        )

        result: dict[str, Any] = response.json()
        return result

    def find(self, db_name: str, selector: dict[str, Any], limit: int = 25) -> list[dict[str, Any]]:
        """Query documents using Mango query selector.

        Args:
            db_name: Database name
            selector: Mango query selector
            limit: Maximum number of results

        Returns:
            List of matching documents

        Example:
            >>> # Find all sklearn models with accuracy > 0.9
            >>> results = client.find(
            ...     db_name="model_registry",
            ...     selector={
            ...         "framework": {"$eq": "sklearn"},
            ...         "metrics.accuracy": {"$gt": 0.9}
            ...     },
            ...     limit=10
            ... )
        """
        self._ensure_connected()

        if not self._username or not self._password:
            raise ValueError("CouchDB credentials not available")

        import requests
        from requests.auth import HTTPBasicAuth

        query = {"selector": selector, "limit": limit}

        response = requests.post(
            f"{self.url}/{db_name}/_find",
            json=query,
            auth=HTTPBasicAuth(self._username, self._password),
            headers={"Content-Type": "application/json"},
        )

        result = response.json()
        docs: list[dict[str, Any]] = result.get("docs", [])
        return docs

    def get_document_revisions(self, db_name: str, doc_id: str) -> list[str]:
        """Get all revision IDs for a document.

        Args:
            db_name: Database name
            doc_id: Document ID

        Returns:
            List of revision IDs (newest first)
        """
        server = self._ensure_connected()

        db = server[db_name]

        if doc_id not in db:
            return []

        # Get document with revs_info
        doc = db.get(doc_id, revs_info=True)
        revs_info = doc.get("_revs_info", [])

        return [rev["rev"] for rev in revs_info if rev["status"] == "available"]

    def get_document_revision(self, db_name: str, doc_id: str, rev: str) -> dict[str, Any] | None:
        """Get a specific revision of a document.

        Args:
            db_name: Database name
            doc_id: Document ID
            rev: Revision ID

        Returns:
            Document at the specified revision or None if not found
        """
        server = self._ensure_connected()

        db = server[db_name]

        try:
            doc = db.get(doc_id, rev=rev)
            return dict(doc)
        except Exception:
            return None
