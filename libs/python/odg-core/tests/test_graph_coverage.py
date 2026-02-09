"""Additional coverage tests for odg_core.graph.janusgraph_client module."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    import types

# Mock gremlin_python modules
_gremlin_mocks = {
    "gremlin_python": MagicMock(),
    "gremlin_python.driver": MagicMock(),
    "gremlin_python.driver.client": MagicMock(),
    "gremlin_python.driver.driver_remote_connection": MagicMock(),
    "gremlin_python.process": MagicMock(),
    "gremlin_python.process.anonymous_traversal": MagicMock(),
    "gremlin_python.process.graph_traversal": MagicMock(),
}


def _fresh_import() -> types.ModuleType:
    sys.modules.pop("odg_core.graph.janusgraph_client", None)
    import odg_core.graph.janusgraph_client as mod

    return mod


def _make_connected_client() -> tuple[Any, MagicMock]:
    with patch.dict(sys.modules, _gremlin_mocks):
        mod = _fresh_import()
        client = mod.JanusGraphClient(url="ws://fake:8182/gremlin")
        mock_gremlin = MagicMock()
        client._client = mock_gremlin
        client._connected = True
        return client, mock_gremlin


# ── connect / disconnect ─────────────────────────────────────


class TestJanusGraphConnect:
    def test_connect_success(self) -> None:
        with patch.dict(sys.modules, _gremlin_mocks):
            mod = _fresh_import()
            mock_client_cls = MagicMock()
            mock_client_instance = MagicMock()
            mock_client_cls.return_value = mock_client_instance
            mock_client_instance.submit.return_value.all.return_value.result.return_value = []

            mod.gremlin_client.Client = mock_client_cls
            cast("Any", mod).DriverRemoteConnection = MagicMock()
            mock_traversal = MagicMock()
            cast("Any", mod).traversal = MagicMock(return_value=mock_traversal)

            client = mod.JanusGraphClient(url="ws://fake:8182/gremlin")
            client.connect()

            assert client._connected is True

    def test_connect_failure(self) -> None:
        with patch.dict(sys.modules, _gremlin_mocks):
            mod = _fresh_import()
            mock_client_cls = MagicMock()
            mock_client_cls.return_value.submit.side_effect = Exception("Connection refused")
            mod.gremlin_client.Client = mock_client_cls

            client = mod.JanusGraphClient(url="ws://fake:8182/gremlin")
            with pytest.raises(ConnectionError, match="Failed to connect"):
                client.connect()

    def test_disconnect(self) -> None:
        client, mock_gremlin = _make_connected_client()
        client.disconnect()
        mock_gremlin.close.assert_called_once()
        assert client._connected is False

    def test_disconnect_without_client(self) -> None:
        with patch.dict(sys.modules, _gremlin_mocks):
            mod = _fresh_import()
            client = mod.JanusGraphClient(url="ws://fake:8182/gremlin")
            client.disconnect()
            assert client._connected is False


# ── Node Management ──────────────────────────────────────────


class TestAddNodes:
    def test_add_dataset(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_vertex = MagicMock()
        mock_vertex.id = 1
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_vertex]

        node = client.add_dataset("gold/customers", layer="gold", version="snap_1")
        assert node.label == "Dataset"
        assert node.properties["dataset_id"] == "gold/customers"
        assert node.properties["layer"] == "gold"

    def test_add_dataset_without_version(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_vertex = MagicMock()
        mock_vertex.id = 2
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_vertex]

        node = client.add_dataset("bronze/raw", layer="bronze")
        assert node.properties["version"] is None

    def test_add_dataset_with_extra_properties(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_vertex = MagicMock()
        mock_vertex.id = 3
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_vertex]

        node = client.add_dataset("gold/sales", layer="gold", format="parquet")
        assert node.properties["format"] == "parquet"

    def test_add_pipeline(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_vertex = MagicMock()
        mock_vertex.id = 10
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_vertex]

        node = client.add_pipeline("transform_sales", pipeline_version=5, pipeline_type="spark")
        assert node.label == "Pipeline"
        assert node.properties["pipeline_id"] == "transform_sales"

    def test_add_model(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_vertex = MagicMock()
        mock_vertex.id = 20
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_vertex]

        node = client.add_model("churn_predictor", model_version=3, framework="sklearn")
        assert node.label == "Model"
        assert node.properties["model_name"] == "churn_predictor"

    def test_add_feature(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_vertex = MagicMock()
        mock_vertex.id = 30
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_vertex]

        node = client.add_feature("customer_features", feature_names=["tenure", "spend"])
        assert node.label == "Feature"
        assert node.properties["feature_names"] == ["tenure", "spend"]


# ── Edge Management ──────────────────────────────────────────


class TestAddEdge:
    def test_add_edge(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_edge = MagicMock()
        mock_edge.id = "e1"
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_edge]

        edge = client.add_edge(
            source_label="Dataset",
            source_property="dataset_id",
            source_value="gold/customers",
            target_label="Dataset",
            target_property="dataset_id",
            target_value="silver/customers",
            edge_label="DERIVED_FROM",
        )
        assert edge.label == "DERIVED_FROM"
        assert edge.source_id == "gold/customers"
        assert edge.target_id == "silver/customers"

    def test_add_edge_no_result(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_gremlin.submit.return_value.all.return_value.result.return_value = []

        edge = client.add_edge(
            source_label="Model",
            source_property="model_name",
            source_value="model1",
            target_label="Dataset",
            target_property="dataset_id",
            target_value="ds1",
            edge_label="TRAINED_ON",
        )
        assert edge.id == ""


# ── High-level Lineage Operations ────────────────────────────


class TestHighLevelLineage:
    def test_add_pipeline_generates_dataset(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_vertex = MagicMock()
        mock_vertex.id = 1
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_vertex]

        client.add_pipeline_generates_dataset(
            pipeline_id="etl_job",
            pipeline_version=2,
            dataset_id="gold/sales",
            dataset_version="snap_1",
        )
        # Verify multiple submit calls (add_pipeline, add_dataset, edge)
        assert mock_gremlin.submit.call_count >= 3

    def test_add_model_trained_on_dataset(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_vertex = MagicMock()
        mock_vertex.id = 1
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_vertex]

        client.add_model_trained_on_dataset(
            model_name="churn_v2",
            model_version=2,
            dataset_id="gold/customers",
            dataset_version="snap_2",
        )
        assert mock_gremlin.submit.call_count >= 3

    def test_add_dataset_derived_from(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_vertex = MagicMock()
        mock_vertex.id = 1
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_vertex]

        client.add_dataset_derived_from(
            target_dataset_id="silver/customers",
            source_dataset_id="bronze/customers",
            transformation="clean_nulls",
        )
        assert mock_gremlin.submit.call_count >= 3

    def test_add_dataset_derived_from_no_transformation(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_vertex = MagicMock()
        mock_vertex.id = 1
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [mock_vertex]

        client.add_dataset_derived_from(
            target_dataset_id="silver/customers",
            source_dataset_id="bronze/customers",
        )
        # Should use "unknown" as default transformation
        assert mock_gremlin.submit.call_count >= 3


# ── Lineage Queries ──────────────────────────────────────────


class TestLineageQueries:
    def test_get_upstream_datasets(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [
            {"id": 1, "label": "Dataset", "dataset_id": ["bronze/sales"]},
        ]
        result = client.get_upstream_datasets("gold/sales")
        assert len(result) == 1
        assert result[0]["dataset_id"] == "bronze/sales"

    def test_get_upstream_datasets_empty(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_gremlin.submit.return_value.all.return_value.result.return_value = []
        result = client.get_upstream_datasets("gold/sales")
        assert result == []

    def test_get_downstream_datasets(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [
            {"id": 2, "label": "Dataset", "dataset_id": ["reports/summary"]},
        ]
        result = client.get_downstream_datasets("gold/sales")
        assert len(result) == 1

    def test_get_model_training_lineage(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [
            {
                "model": {"id": 1, "label": "Model", "model_name": ["churn"]},
                "training_datasets": [{"id": 2, "label": "Dataset", "dataset_id": ["gold/customers"]}],
                "upstream_pipelines": [{"id": 3, "label": "Pipeline", "pipeline_id": ["etl_job"]}],
            }
        ]
        result = client.get_model_training_lineage("churn", model_version=1)
        assert "model" in result
        assert len(result["training_datasets"]) == 1
        assert len(result["upstream_pipelines"]) == 1

    def test_get_model_training_lineage_empty(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_gremlin.submit.return_value.all.return_value.result.return_value = []
        result = client.get_model_training_lineage("unknown_model", model_version=1)
        assert result == {}

    def test_get_pipeline_outputs(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [
            {"id": 1, "label": "Dataset", "dataset_id": ["gold/sales"]},
            {"id": 2, "label": "Dataset", "dataset_id": ["gold/customers"]},
        ]
        result = client.get_pipeline_outputs("etl_job")
        assert len(result) == 2

    def test_get_dataset_consumers(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [
            {
                "models": [{"id": 1, "label": "Model", "model_name": ["churn"]}],
                "pipelines": [{"id": 2, "label": "Pipeline", "pipeline_id": ["etl"]}],
            }
        ]
        result = client.get_dataset_consumers("gold/customers")
        assert len(result["models"]) == 1
        assert len(result["pipelines"]) == 1

    def test_get_dataset_consumers_empty(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_gremlin.submit.return_value.all.return_value.result.return_value = []
        result = client.get_dataset_consumers("gold/orphan")
        assert result == {"models": [], "pipelines": []}

    def test_get_full_lineage_graph(self) -> None:
        client, mock_gremlin = _make_connected_client()
        # Simulate path results: [vertex, edge, vertex]
        path1 = [
            {"id": 1, "label": "Dataset", "dataset_id": ["gold/sales"]},
            {"id": "e1", "label": "DERIVED_FROM", "outV": "1", "inV": "2"},
            {"id": 2, "label": "Dataset", "dataset_id": ["silver/sales"]},
        ]
        mock_gremlin.submit.return_value.all.return_value.result.return_value = [path1]

        result = client.get_full_lineage_graph("gold/sales", "Dataset", depth=2)
        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    def test_get_full_lineage_graph_empty(self) -> None:
        client, mock_gremlin = _make_connected_client()
        mock_gremlin.submit.return_value.all.return_value.result.return_value = []

        result = client.get_full_lineage_graph("unknown", "Dataset")
        assert result == {"nodes": [], "edges": []}
