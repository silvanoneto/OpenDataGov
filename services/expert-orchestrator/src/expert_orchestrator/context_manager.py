"""Context Manager - Shares state between experts during workflow execution."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class SharedContext:
    """Thread-safe shared context for multi-expert workflows."""

    def __init__(self):
        """Initialize shared context."""
        self._store: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._metadata: dict[str, dict[str, Any]] = {}

    async def set(self, key: str, value: Any, metadata: dict[str, Any] | None = None) -> None:
        """Set a value in the shared context.

        Args:
            key: Context key
            value: Value to store
            metadata: Optional metadata (timestamp, source expert, etc.)

        Example:
            >>> context = SharedContext()
            >>> await context.set(
            ...     "schema_analysis",
            ...     {"columns": 15, "pii_fields": 3},
            ...     metadata={"source": "SchemaExpert", "confidence": 0.95}
            ... )
        """
        async with self._lock:
            self._store[key] = value

            if metadata is None:
                metadata = {}

            metadata["stored_at"] = datetime.utcnow().isoformat()
            self._metadata[key] = metadata

            logger.debug(f"Context SET: {key} = {type(value).__name__}")

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the shared context.

        Args:
            key: Context key
            default: Default value if key not found

        Returns:
            Stored value or default

        Example:
            >>> schema = await context.get("schema_analysis")
            >>> print(schema["columns"])
        """
        async with self._lock:
            value = self._store.get(key, default)
            logger.debug(f"Context GET: {key} = {type(value).__name__ if value else 'None'}")
            return value

    async def get_with_metadata(self, key: str) -> tuple[Any, dict[str, Any]] | None:
        """Get value and its metadata.

        Args:
            key: Context key

        Returns:
            Tuple of (value, metadata) or None if not found

        Example:
            >>> value, meta = await context.get_with_metadata("schema_analysis")
            >>> print(f"Created by: {meta['source']} at {meta['stored_at']}")
        """
        async with self._lock:
            if key not in self._store:
                return None
            return (self._store[key], self._metadata.get(key, {}))

    async def get_all(self) -> dict[str, Any]:
        """Get all values in the context.

        Returns:
            Copy of entire context store

        Example:
            >>> all_data = await context.get_all()
            >>> print(f"Context has {len(all_data)} entries")
        """
        async with self._lock:
            return self._store.copy()

    async def has(self, key: str) -> bool:
        """Check if key exists in context.

        Args:
            key: Context key

        Returns:
            True if key exists

        Example:
            >>> if await context.has("schema_analysis"):
            ...     schema = await context.get("schema_analysis")
        """
        async with self._lock:
            return key in self._store

    async def delete(self, key: str) -> bool:
        """Delete a key from context.

        Args:
            key: Context key to delete

        Returns:
            True if key was deleted, False if not found
        """
        async with self._lock:
            if key in self._store:
                del self._store[key]
                self._metadata.pop(key, None)
                logger.debug(f"Context DELETE: {key}")
                return True
            return False

    async def clear(self) -> None:
        """Clear entire context."""
        async with self._lock:
            self._store.clear()
            self._metadata.clear()
            logger.debug("Context CLEARED")

    async def keys(self) -> list[str]:
        """Get all keys in context.

        Returns:
            List of keys
        """
        async with self._lock:
            return list(self._store.keys())

    async def size(self) -> int:
        """Get number of entries in context.

        Returns:
            Number of stored entries
        """
        async with self._lock:
            return len(self._store)

    async def merge(self, other_context: dict[str, Any]) -> None:
        """Merge another dictionary into this context.

        Args:
            other_context: Dictionary to merge

        Example:
            >>> await context.merge({
            ...     "additional_data": {"foo": "bar"},
            ...     "settings": {"debug": True}
            ... })
        """
        async with self._lock:
            for key, value in other_context.items():
                self._store[key] = value
                self._metadata[key] = {"merged_at": datetime.utcnow().isoformat()}

    async def get_by_prefix(self, prefix: str) -> dict[str, Any]:
        """Get all entries with keys starting with prefix.

        Args:
            prefix: Key prefix to filter by

        Returns:
            Dict of matching entries

        Example:
            >>> # Get all task results
            >>> task_results = await context.get_by_prefix("task_")
        """
        async with self._lock:
            return {key: value for key, value in self._store.items() if key.startswith(prefix)}

    async def snapshot(self) -> dict[str, Any]:
        """Get complete snapshot of context including metadata.

        Returns:
            Dict with 'data' and 'metadata' keys

        Example:
            >>> snapshot = await context.snapshot()
            >>> print(json.dumps(snapshot, indent=2))
        """
        async with self._lock:
            return {
                "data": self._store.copy(),
                "metadata": self._metadata.copy(),
                "snapshot_at": datetime.utcnow().isoformat(),
                "size": len(self._store),
            }
