"""Tests for OpenLineage lineage models, emitter, and consumer."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any
from unittest.mock import patch

from odg_core.lineage import emit_lineage_event
from odg_core.lineage.consumer import _dataset_to_urn, openlineage_to_datahub_mce
from odg_core.lineage.models import LineageDataset, LineageJob, LineageRunEvent

# ---------------------------------------------------------------------------
# Models — LineageDataset
# ---------------------------------------------------------------------------


class TestLineageDataset:
    def test_minimal_creation(self) -> None:
        ds = LineageDataset(namespace="ns", name="table_a")
        assert ds.namespace == "ns"
        assert ds.name == "table_a"
        assert ds.facets == {}

    def test_with_facets(self) -> None:
        facets: dict[str, Any] = {"schema": {"fields": [{"name": "id", "type": "int"}]}}
        ds = LineageDataset(namespace="s3", name="bucket/key", facets=facets)
        assert ds.facets == facets
        assert ds.facets["schema"]["fields"][0]["name"] == "id"

    def test_serialization_roundtrip(self) -> None:
        ds = LineageDataset(namespace="ns", name="t", facets={"k": "v"})
        data = ds.model_dump()
        restored = LineageDataset(**data)
        assert restored == ds


# ---------------------------------------------------------------------------
# Models — LineageJob
# ---------------------------------------------------------------------------


class TestLineageJob:
    def test_default_namespace(self) -> None:
        job = LineageJob(name="etl_job")
        assert job.namespace == "opendatagov"
        assert job.name == "etl_job"

    def test_custom_namespace(self) -> None:
        job = LineageJob(namespace="custom-ns", name="my_job")
        assert job.namespace == "custom-ns"

    def test_serialization_roundtrip(self) -> None:
        job = LineageJob(name="j")
        data = job.model_dump()
        restored = LineageJob(**data)
        assert restored == job


# ---------------------------------------------------------------------------
# Models — LineageRunEvent
# ---------------------------------------------------------------------------


class TestLineageRunEvent:
    def test_defaults(self) -> None:
        job = LineageJob(name="test_job")
        event = LineageRunEvent(job=job)

        assert event.event_type == "COMPLETE"
        assert isinstance(event.event_time, datetime)
        assert event.run == {}
        assert event.inputs == []
        assert event.outputs == []
        assert event.producer == "opendatagov"
        assert "OpenLineage" in event.schema_url

    def test_full_construction(self) -> None:
        run_id = str(uuid.uuid4())
        inp = LineageDataset(namespace="ns", name="input_table")
        out = LineageDataset(namespace="ns", name="output_table")
        job = LineageJob(name="transform_job")

        event = LineageRunEvent(
            event_type="START",
            run={"runId": run_id},
            job=job,
            inputs=[inp],
            outputs=[out],
        )

        assert event.event_type == "START"
        assert event.run["runId"] == run_id
        assert len(event.inputs) == 1
        assert len(event.outputs) == 1
        assert event.inputs[0].name == "input_table"
        assert event.outputs[0].name == "output_table"

    def test_serialization_roundtrip(self) -> None:
        job = LineageJob(name="j")
        event = LineageRunEvent(
            event_type="FAIL",
            job=job,
            inputs=[LineageDataset(namespace="n", name="i")],
            outputs=[LineageDataset(namespace="n", name="o")],
        )
        data = event.model_dump()
        restored = LineageRunEvent(**data)
        assert restored.event_type == event.event_type
        assert restored.job.name == event.job.name
        assert len(restored.inputs) == 1
        assert len(restored.outputs) == 1

    def test_all_event_types(self) -> None:
        """Ensure all OpenLineage event types can be assigned."""
        job = LineageJob(name="j")
        for et in ("START", "RUNNING", "COMPLETE", "FAIL", "ABORT"):
            event = LineageRunEvent(event_type=et, job=job)
            assert event.event_type == et


# ---------------------------------------------------------------------------
# Emitter — emit_lineage_event
# ---------------------------------------------------------------------------


class TestEmitLineageEvent:
    def test_returns_lineage_run_event(self) -> None:
        event = emit_lineage_event(
            job_name="promotion.bronze_to_silver",
            inputs=[{"namespace": "s3", "name": "raw/data"}],
            outputs=[{"namespace": "s3", "name": "silver/data"}],
        )

        assert isinstance(event, LineageRunEvent)
        assert event.event_type == "COMPLETE"
        assert event.job.name == "promotion.bronze_to_silver"
        assert event.job.namespace == "opendatagov"
        assert len(event.inputs) == 1
        assert len(event.outputs) == 1
        assert event.inputs[0].namespace == "s3"
        assert event.inputs[0].name == "raw/data"
        assert event.outputs[0].namespace == "s3"
        assert event.outputs[0].name == "silver/data"

    def test_custom_event_type(self) -> None:
        event = emit_lineage_event(
            job_name="j",
            inputs=[],
            outputs=[],
            event_type="FAIL",
        )
        assert event.event_type == "FAIL"

    def test_run_id_is_uuid(self) -> None:
        event = emit_lineage_event(
            job_name="j",
            inputs=[],
            outputs=[],
        )
        run_id = event.run.get("runId", "")
        # Should be a valid UUID4
        parsed = uuid.UUID(run_id)
        assert parsed.version == 4

    def test_empty_inputs_outputs(self) -> None:
        event = emit_lineage_event(
            job_name="no_io",
            inputs=[],
            outputs=[],
        )
        assert event.inputs == []
        assert event.outputs == []

    def test_multiple_inputs_outputs(self) -> None:
        event = emit_lineage_event(
            job_name="merge",
            inputs=[
                {"namespace": "ns", "name": "a"},
                {"namespace": "ns", "name": "b"},
                {"namespace": "ns", "name": "c"},
            ],
            outputs=[
                {"namespace": "ns", "name": "merged"},
                {"namespace": "ns", "name": "audit_log"},
            ],
        )
        assert len(event.inputs) == 3
        assert len(event.outputs) == 2

    def test_logs_event(self) -> None:
        """Verify that the emitter logs at INFO and DEBUG levels."""
        with patch("odg_core.lineage.emitter.logger") as mock_logger:
            emit_lineage_event(
                job_name="logged_job",
                inputs=[{"namespace": "n", "name": "i"}],
                outputs=[{"namespace": "n", "name": "o"}],
            )

            mock_logger.info.assert_called_once()
            info_args = mock_logger.info.call_args
            assert "COMPLETE" in info_args[0][0] or "COMPLETE" in str(info_args)

            mock_logger.debug.assert_called_once()

    def test_payload_is_json_serializable(self) -> None:
        event = emit_lineage_event(
            job_name="j",
            inputs=[{"namespace": "n", "name": "i"}],
            outputs=[{"namespace": "n", "name": "o"}],
        )
        # model_dump must be JSON-serializable (datetime needs default=str)
        payload = json.dumps(event.model_dump(), default=str)
        parsed = json.loads(payload)
        assert parsed["job"]["name"] == "j"

    def test_module_re_export(self) -> None:
        """emit_lineage_event is re-exported from lineage __init__."""
        from odg_core.lineage import emit_lineage_event as fn

        assert callable(fn)


# ---------------------------------------------------------------------------
# Consumer — _dataset_to_urn
# ---------------------------------------------------------------------------


class TestDatasetToUrn:
    def test_with_namespace_and_name(self) -> None:
        urn = _dataset_to_urn({"namespace": "s3", "name": "my_table"})
        assert urn == "urn:li:dataset:(urn:li:dataPlatform:s3,my_table,PROD)"

    def test_defaults_when_keys_missing(self) -> None:
        urn = _dataset_to_urn({})
        assert urn == "urn:li:dataset:(urn:li:dataPlatform:opendatagov,unknown,PROD)"

    def test_default_namespace_only(self) -> None:
        urn = _dataset_to_urn({"name": "x"})
        assert "opendatagov" in urn
        assert ",x," in urn

    def test_default_name_only(self) -> None:
        urn = _dataset_to_urn({"namespace": "custom"})
        assert "custom" in urn
        assert ",unknown," in urn


# ---------------------------------------------------------------------------
# Consumer — openlineage_to_datahub_mce
# ---------------------------------------------------------------------------


class TestOpenlineageToDatahubMce:
    def test_basic_conversion(self) -> None:
        event: dict[str, Any] = {
            "job": {"name": "etl_pipeline"},
            "inputs": [{"namespace": "s3", "name": "raw_table"}],
            "outputs": [{"namespace": "s3", "name": "clean_table"}],
        }

        mce = openlineage_to_datahub_mce(event)

        assert mce["entityType"] == "dataJob"
        assert "etl_pipeline" in mce["entityUrn"]
        assert mce["aspectName"] == "dataJobInputOutput"
        assert mce["changeType"] == "UPSERT"

        # Input/output datasets
        assert len(mce["aspect"]["inputDatasets"]) == 1
        assert len(mce["aspect"]["outputDatasets"]) == 1
        assert "raw_table" in mce["aspect"]["inputDatasets"][0]
        assert "clean_table" in mce["aspect"]["outputDatasets"][0]

        # Lineage edges
        assert len(mce["lineageEdges"]) == 1
        edge = mce["lineageEdges"][0]
        assert "raw_table" in edge["sourceUrn"]
        assert "clean_table" in edge["destinationUrn"]
        assert edge["type"] == "TRANSFORMED"

    def test_multiple_inputs_outputs(self) -> None:
        event: dict[str, Any] = {
            "job": {"name": "join_job"},
            "inputs": [
                {"namespace": "ns", "name": "a"},
                {"namespace": "ns", "name": "b"},
            ],
            "outputs": [
                {"namespace": "ns", "name": "x"},
                {"namespace": "ns", "name": "y"},
            ],
        }

        mce = openlineage_to_datahub_mce(event)

        # 2 inputs x 2 outputs = 4 edges
        assert len(mce["lineageEdges"]) == 4
        assert len(mce["aspect"]["inputDatasets"]) == 2
        assert len(mce["aspect"]["outputDatasets"]) == 2

    def test_empty_inputs_outputs(self) -> None:
        event: dict[str, Any] = {
            "job": {"name": "no_io_job"},
            "inputs": [],
            "outputs": [],
        }

        mce = openlineage_to_datahub_mce(event)

        assert mce["aspect"]["inputDatasets"] == []
        assert mce["aspect"]["outputDatasets"] == []
        assert mce["lineageEdges"] == []

    def test_missing_job_defaults_to_unknown(self) -> None:
        event: dict[str, Any] = {
            "inputs": [],
            "outputs": [],
        }

        mce = openlineage_to_datahub_mce(event)

        assert "unknown" in mce["entityUrn"]

    def test_missing_job_name_defaults_to_unknown(self) -> None:
        event: dict[str, Any] = {
            "job": {},
            "inputs": [],
            "outputs": [],
        }

        mce = openlineage_to_datahub_mce(event)

        assert "unknown" in mce["entityUrn"]

    def test_entity_urn_format(self) -> None:
        event: dict[str, Any] = {
            "job": {"name": "my_pipeline"},
            "inputs": [],
            "outputs": [],
        }

        mce = openlineage_to_datahub_mce(event)

        expected_prefix = "urn:li:dataJob:(urn:li:dataFlow:(opendatagov,my_pipeline,PROD),my_pipeline)"
        assert mce["entityUrn"] == expected_prefix

    def test_no_inputs_key(self) -> None:
        """When 'inputs' key is absent, should default to empty list."""
        event: dict[str, Any] = {
            "job": {"name": "j"},
            "outputs": [{"namespace": "n", "name": "o"}],
        }
        mce = openlineage_to_datahub_mce(event)
        assert mce["aspect"]["inputDatasets"] == []
        assert mce["lineageEdges"] == []

    def test_no_outputs_key(self) -> None:
        """When 'outputs' key is absent, should default to empty list."""
        event: dict[str, Any] = {
            "job": {"name": "j"},
            "inputs": [{"namespace": "n", "name": "i"}],
        }
        mce = openlineage_to_datahub_mce(event)
        assert mce["aspect"]["outputDatasets"] == []
        assert mce["lineageEdges"] == []
