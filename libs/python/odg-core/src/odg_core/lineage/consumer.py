"""OpenLineage event consumer: Kafka -> DataHub ingestion (ADR-060).

Consumes OpenLineage events from Kafka and converts them to DataHub MCEs.
This module is started as a background task during application startup.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def openlineage_to_datahub_mce(event: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenLineage RunEvent to a DataHub MCE.

    Maps OpenLineage datasets to DataHub dataset URNs and creates
    lineage edges between inputs and outputs.
    """
    job = event.get("job", {})
    inputs = event.get("inputs", [])
    outputs = event.get("outputs", [])

    edges = []
    for output in outputs:
        output_urn = _dataset_to_urn(output)
        for inp in inputs:
            input_urn = _dataset_to_urn(inp)
            edges.append(
                {
                    "sourceUrn": input_urn,
                    "destinationUrn": output_urn,
                    "type": "TRANSFORMED",
                }
            )

    return {
        "entityType": "dataJob",
        "entityUrn": (
            f"urn:li:dataJob:(urn:li:dataFlow:"
            f"(opendatagov,{job.get('name', 'unknown')},PROD),{job.get('name', 'unknown')})"
        ),
        "aspectName": "dataJobInputOutput",
        "aspect": {
            "inputDatasets": [_dataset_to_urn(d) for d in inputs],
            "outputDatasets": [_dataset_to_urn(d) for d in outputs],
        },
        "changeType": "UPSERT",
        "lineageEdges": edges,
    }


def _dataset_to_urn(dataset: dict[str, Any]) -> str:
    """Convert an OpenLineage dataset to a DataHub dataset URN."""
    namespace = dataset.get("namespace", "opendatagov")
    name = dataset.get("name", "unknown")
    return f"urn:li:dataset:(urn:li:dataPlatform:{namespace},{name},PROD)"
