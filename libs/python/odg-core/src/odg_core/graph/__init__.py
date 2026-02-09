"""Graph database integration for data lineage.

Provides JanusGraph client for querying and managing lineage graphs.
"""

from odg_core.graph.janusgraph_client import JanusGraphClient, LineageEdge, LineageNode

__all__ = [
    "JanusGraphClient",
    "LineageEdge",
    "LineageNode",
]
