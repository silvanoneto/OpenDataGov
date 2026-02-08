"""ODG metadata <-> OpenLineage schema adapter (ADR-041, ADR-060)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from odg_core.metadata.odg_schema import ODGDatasetMetadata


def odg_to_openlineage_dataset(metadata: ODGDatasetMetadata) -> dict[str, Any]:
    """Convert ODG dataset metadata to an OpenLineage dataset facet."""
    return {
        "namespace": f"opendatagov://{metadata.domain_id}",
        "name": metadata.dataset_id,
        "facets": {
            "schema": {
                "_producer": "opendatagov",
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SchemaDatasetFacet.json",
                "fields": [
                    {"name": f.name, "type": f.data_type, "description": f.description} for f in metadata.schema_fields
                ],
            },
            "dataQualityMetrics": {
                "_producer": "opendatagov",
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsInputDatasetFacet.json",
                "qualityScore": metadata.quality_score,
            },
            "ownership": {
                "_producer": "opendatagov",
                "owners": [{"name": metadata.owner_id, "type": "DATAOWNER"}],
            },
        },
    }
