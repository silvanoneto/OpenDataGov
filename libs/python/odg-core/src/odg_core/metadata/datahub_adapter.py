"""Bidirectional adapter: ODG metadata <-> DataHub MCE (ADR-041).

Converts between ODGDatasetMetadata and DataHub Metadata Change Events.
Requires `acryl-datahub` when actually pushing to DataHub.
"""

from __future__ import annotations

import logging
from typing import Any

from odg_core.metadata.odg_schema import DatasetField, ODGDatasetMetadata

logger = logging.getLogger(__name__)


def odg_to_datahub_mce(metadata: ODGDatasetMetadata) -> dict[str, Any]:
    """Convert ODG dataset metadata to a DataHub-compatible MCE dict.

    This produces a simplified MCE structure. Production usage should
    use the `datahub` SDK's MetadataChangeEvent classes directly.
    """
    fields = [
        {
            "fieldPath": f.name,
            "nativeDataType": f.data_type,
            "type": {"type": {"com.linkedin.schema.StringType": {}}},
            "description": f.description,
            "nullable": f.is_nullable,
            "globalTags": {"tags": [{"tag": "urn:li:tag:PII"}]} if f.is_pii else {"tags": []},
        }
        for f in metadata.schema_fields
    ]

    return {
        "entityType": "dataset",
        "entityUrn": f"urn:li:dataset:(urn:li:dataPlatform:opendatagov,{metadata.dataset_id},PROD)",
        "aspectName": "schemaMetadata",
        "aspect": {
            "schemaName": metadata.name,
            "platform": "urn:li:dataPlatform:opendatagov",
            "fields": fields,
            "primaryKeys": [],
        },
        "changeType": "UPSERT",
    }


def datahub_to_odg(mce: dict[str, Any]) -> ODGDatasetMetadata:
    """Convert a DataHub MCE dict to ODG dataset metadata.

    Extracts basic information from the MCE structure.
    """
    aspect = mce.get("aspect", {})
    urn = mce.get("entityUrn", "")

    # Parse dataset_id from URN: urn:li:dataset:(platform,id,env)
    dataset_id = urn.split(",")[1] if "," in urn else urn

    fields_raw = aspect.get("fields", [])
    fields = [
        DatasetField(
            name=f.get("fieldPath", ""),
            data_type=f.get("nativeDataType", "string"),
            description=f.get("description", ""),
            is_nullable=f.get("nullable", True),
            is_pii=bool(f.get("globalTags", {}).get("tags", [])),
        )
        for f in fields_raw
    ]

    return ODGDatasetMetadata(
        dataset_id=dataset_id,
        name=aspect.get("schemaName", dataset_id),
        domain_id="unknown",
        owner_id="unknown",
        schema_fields=fields,
    )
