"""Polars integration for OpenDataGov.

Provides lazy plan versioning and lineage tracking for Polars transformations.
"""

from odg_core.polars.versioned_pipeline import (
    VersionedPolarsJob,
    create_versioned_pipeline,
)

__all__ = [
    "VersionedPolarsJob",
    "create_versioned_pipeline",
]
