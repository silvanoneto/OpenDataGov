"""DuckDB integration for OpenDataGov.

Provides SQL transformation versioning and lineage tracking for DuckDB queries.
"""

from odg_core.duckdb.versioned_query import VersionedDuckDBJob, create_versioned_query

__all__ = [
    "VersionedDuckDBJob",
    "create_versioned_query",
]
