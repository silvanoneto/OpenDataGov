"""Spark integration for OpenDataGov.

Provides job versioning and execution tracking capabilities for Spark jobs.
"""

from odg_core.spark.job_versioning import ODGSparkListener, VersionedSparkJob

__all__ = [
    "ODGSparkListener",
    "VersionedSparkJob",
]
