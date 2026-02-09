"""Feast Feature Store integration with versioning and lineage tracking.

Provides automatic tracking of feature materialization jobs with lineage
to source datasets and transformation pipelines.
"""

from odg_core.feast.materialization_tracker import (
    MaterializationTracker,
    track_feast_materialization,
)

__all__ = [
    "MaterializationTracker",
    "track_feast_materialization",
]
