"""Integration test: metadata sync with DataHub."""

from __future__ import annotations


class TestMetadataModels:
    """Verify metadata models and adapters (works without DataHub)."""

    def test_odg_dataset_metadata_creation(self) -> None:
        """ODGDatasetMetadata should be creatable with required fields."""
        from odg_core.metadata.odg_schema import ODGDatasetMetadata

        metadata = ODGDatasetMetadata(
            dataset_id="revenue_daily",
            name="Revenue Daily",
            domain_id="finance",
            owner_id="data-team",
        )

        assert metadata.dataset_id == "revenue_daily"
        assert metadata.name == "Revenue Daily"
        assert metadata.id is not None

    def test_odg_to_openlineage_conversion(self) -> None:
        """ODG metadata should convert to OpenLineage format."""
        from odg_core.metadata.odg_schema import DatasetField, ODGDatasetMetadata
        from odg_core.metadata.openlineage_adapter import odg_to_openlineage_dataset

        metadata = ODGDatasetMetadata(
            dataset_id="revenue_daily",
            name="Revenue Daily",
            domain_id="finance",
            owner_id="data-team",
            schema_fields=[
                DatasetField(name="id", data_type="integer"),
                DatasetField(name="amount", data_type="float"),
            ],
        )

        ol_dataset = odg_to_openlineage_dataset(metadata)

        assert ol_dataset["namespace"] == "opendatagov://finance"
        assert ol_dataset["name"] == "revenue_daily"
        assert "schema" in ol_dataset["facets"]
        assert len(ol_dataset["facets"]["schema"]["fields"]) == 2

    def test_lineage_run_event_creation(self) -> None:
        """LineageRunEvent should be creatable with job and datasets."""
        from odg_core.lineage.models import LineageDataset, LineageJob, LineageRunEvent

        event = LineageRunEvent(
            job=LineageJob(name="promote-revenue"),
            inputs=[LineageDataset(namespace="opendatagov", name="bronze.revenue")],
            outputs=[LineageDataset(namespace="opendatagov", name="silver.revenue")],
        )

        assert event.job.name == "promote-revenue"
        assert len(event.inputs) == 1
        assert len(event.outputs) == 1
        assert event.event_type == "COMPLETE"


class TestDataHubSync:
    """Verify DataHub MCE conversion (works without DataHub)."""

    def test_openlineage_to_datahub_mce(self) -> None:
        """OpenLineage events should convert to DataHub MCEs."""
        from odg_core.lineage.consumer import openlineage_to_datahub_mce

        event = {
            "job": {"name": "promote-revenue", "namespace": "opendatagov"},
            "inputs": [{"namespace": "opendatagov", "name": "bronze.revenue"}],
            "outputs": [{"namespace": "opendatagov", "name": "silver.revenue"}],
        }

        mce = openlineage_to_datahub_mce(event)
        assert mce["entityType"] == "dataJob"
        assert "lineageEdges" in mce
        assert len(mce["lineageEdges"]) == 1

    def test_mce_contains_input_output_datasets(self) -> None:
        """MCE should list input and output dataset URNs."""
        from odg_core.lineage.consumer import openlineage_to_datahub_mce

        event = {
            "job": {"name": "enrich-users", "namespace": "opendatagov"},
            "inputs": [
                {"namespace": "opendatagov", "name": "silver.users"},
                {"namespace": "opendatagov", "name": "silver.orders"},
            ],
            "outputs": [{"namespace": "opendatagov", "name": "gold.user_metrics"}],
        }

        mce = openlineage_to_datahub_mce(event)

        assert len(mce["aspect"]["inputDatasets"]) == 2
        assert len(mce["aspect"]["outputDatasets"]) == 1
        assert "silver.users" in mce["aspect"]["inputDatasets"][0]
        assert "gold.user_metrics" in mce["aspect"]["outputDatasets"][0]
        # 1 output x 2 inputs = 2 lineage edges
        assert len(mce["lineageEdges"]) == 2

    def test_mce_entity_urn_format(self) -> None:
        """MCE entity URN should follow DataHub format."""
        from odg_core.lineage.consumer import openlineage_to_datahub_mce

        event = {
            "job": {"name": "my-job", "namespace": "opendatagov"},
            "inputs": [],
            "outputs": [],
        }

        mce = openlineage_to_datahub_mce(event)
        assert mce["entityUrn"].startswith("urn:li:dataJob:")
        assert "my-job" in mce["entityUrn"]
        assert mce["changeType"] == "UPSERT"
