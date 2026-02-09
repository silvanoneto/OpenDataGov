"""Deep tests for GraphQL lineage resolvers, lineage types, dataset types, and schema methods.

Covers:
    - graphql/resolvers/lineage.py  (all resolver functions)
    - graphql/types/lineage.py      (computed @strawberry.field properties)
    - graphql/types/dataset.py      (VersionedDatasetGQL.versions / get_version_data)
    - graphql/schema.py             (Query / Mutation delegation to resolvers)
"""

from __future__ import annotations

import uuid
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-under-test imports
# ---------------------------------------------------------------------------
from odg_core.graphql.resolvers.lineage import (
    _edge_dict_to_gql,
    _node_dict_to_gql,
    resolve_dataset_lineage,
    resolve_impact_analysis,
    resolve_lineage_graph,
    resolve_model_lineage,
    resolve_pipeline_lineage,
    resolve_record_dataset_promotion,
    resolve_record_model_training,
    resolve_record_pipeline_execution,
)
from odg_core.graphql.types.dataset import VersionedDatasetGQL
from odg_core.graphql.types.lineage import (
    DatasetLineageGQL,
    DetailedLineageGraphGQL,
    ImpactAnalysisGQL,
    LineageEdgeGQL,
    LineageNodeGQL,
    ModelLineageGQL,
)

# The path where JanusGraphClient is looked up inside the resolver module.
_JANUS_PATCH = "odg_core.graphql.resolvers.lineage.JanusGraphClient"

# The path where IcebergCatalog is imported locally inside dataset type methods.
# Because the import is local (from odg_core.storage.iceberg_catalog import IcebergCatalog),
# we must patch it at its origin so the local import picks up the mock.
_ICEBERG_PATCH = "odg_core.storage.iceberg_catalog.IcebergCatalog"


# ===================================================================
# Helpers
# ===================================================================


def _make_node(
    node_id: str = "n1",
    label: str = "Dataset",
    extra: dict[str, Any] | None = None,
) -> LineageNodeGQL:
    props: dict[str, Any] = {"dataset_id": node_id}
    if extra:
        props.update(extra)
    return LineageNodeGQL(id=node_id, label=label, properties=cast("Any", props))


def _make_edge(
    edge_id: str = "e1",
    label: str = "DERIVED_FROM",
    source: str = "n1",
    target: str = "n2",
) -> LineageEdgeGQL:
    return LineageEdgeGQL(id=edge_id, label=label, source=source, target=target, properties=None)


# ===================================================================
# 1. graphql/resolvers/lineage.py
# ===================================================================


class TestNodeDictToGQL:
    """Tests for _node_dict_to_gql helper."""

    def test_converts_full_dict(self) -> None:
        node = _node_dict_to_gql({"id": "abc", "label": "Dataset", "dataset_id": "gold/sales"})
        assert node.id == "abc"
        assert node.label == "Dataset"
        assert cast("dict[str, Any]", node.properties)["dataset_id"] == "gold/sales"

    def test_defaults_on_missing_keys(self) -> None:
        node = _node_dict_to_gql({})
        assert node.id == ""
        assert node.label == ""

    def test_preserves_extra_properties(self) -> None:
        node = _node_dict_to_gql({"id": "x", "label": "Model", "framework": "pytorch"})
        assert cast("dict[str, Any]", node.properties)["framework"] == "pytorch"


class TestEdgeDictToGQL:
    """Tests for _edge_dict_to_gql helper."""

    def test_converts_full_dict(self) -> None:
        edge = _edge_dict_to_gql({"id": "e1", "label": "DERIVED_FROM", "source": "n1", "target": "n2"})
        assert edge.id == "e1"
        assert edge.label == "DERIVED_FROM"
        assert edge.source == "n1"
        assert edge.target == "n2"

    def test_defaults_on_missing_keys(self) -> None:
        edge = _edge_dict_to_gql({})
        assert edge.id == ""
        assert edge.label == ""
        assert edge.source == ""
        assert edge.target == ""

    def test_source_target_coerced_to_str(self) -> None:
        edge = _edge_dict_to_gql({"id": "e", "label": "L", "source": 123, "target": 456})
        assert edge.source == "123"
        assert edge.target == "456"


class TestResolveDatasetLineage:
    """Tests for resolve_dataset_lineage."""

    @patch(_JANUS_PATCH)
    def test_returns_dataset_lineage(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_upstream_datasets.return_value = [
            {"id": "u1", "label": "Dataset"},
        ]
        client.get_downstream_datasets.return_value = [
            {"id": "d1", "label": "Dataset"},
        ]
        client.get_dataset_consumers.return_value = {
            "pipelines": [{"id": "p1", "label": "Pipeline"}],
            "models": [{"id": "m1", "label": "Model"}],
        }

        result = resolve_dataset_lineage("gold/customers", depth=3)

        assert result is not None
        assert result.dataset_id == "gold/customers"
        assert result.layer == "gold"
        assert len(result.upstream_datasets) == 1
        assert len(result.downstream_datasets) == 1
        assert len(result.generating_pipelines) == 1
        assert len(result.consuming_models) == 1

        client.connect.assert_called_once()
        client.disconnect.assert_called_once()
        client.get_upstream_datasets.assert_called_once_with("gold/customers", max_depth=3)
        client.get_downstream_datasets.assert_called_once_with("gold/customers", max_depth=3)
        client.get_dataset_consumers.assert_called_once_with("gold/customers")

    @patch(_JANUS_PATCH)
    def test_layer_is_unknown_when_no_slash(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_upstream_datasets.return_value = []
        client.get_downstream_datasets.return_value = []
        client.get_dataset_consumers.return_value = {"pipelines": [], "models": []}

        result = resolve_dataset_lineage("customers")
        assert result is not None
        assert result.layer == "unknown"
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_disconnect_called_on_exception(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_upstream_datasets.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            resolve_dataset_lineage("gold/x")

        client.disconnect.assert_called_once()


class TestResolveModelLineage:
    """Tests for resolve_model_lineage."""

    @patch(_JANUS_PATCH)
    def test_returns_model_lineage(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_model_training_lineage.return_value = {
            "model": {"framework": "sklearn"},
            "training_datasets": [
                {"id": "d1", "label": "Dataset", "version": "snap_1"},
                {"id": "d2", "label": "Dataset"},
            ],
            "upstream_pipelines": [{"id": "p1", "label": "Pipeline"}],
        }

        result = resolve_model_lineage("churn_predictor", 5)

        assert result is not None
        assert result.model_name == "churn_predictor"
        assert result.model_version == 5
        assert result.framework == "sklearn"
        assert len(result.training_datasets) == 2
        assert len(result.upstream_pipelines) == 1
        assert result.dataset_snapshots == ["snap_1"]

        client.connect.assert_called_once()
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_returns_none_when_no_lineage(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_model_training_lineage.return_value = None

        result = resolve_model_lineage("missing", 1)
        assert result is None
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_returns_none_when_lineage_empty_dict(self, mock_janus: MagicMock) -> None:
        """An empty dict is falsy in Python, so `not lineage` is True -> returns None."""
        client = mock_janus.return_value
        client.get_model_training_lineage.return_value = {}

        result = resolve_model_lineage("empty", 1)
        assert result is None
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_disconnect_called_on_exception(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_model_training_lineage.side_effect = RuntimeError("fail")

        with pytest.raises(RuntimeError, match="fail"):
            resolve_model_lineage("model", 1)

        client.disconnect.assert_called_once()


class TestResolvePipelineLineage:
    """Tests for resolve_pipeline_lineage."""

    @patch(_JANUS_PATCH)
    def test_returns_pipeline_lineage(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_pipeline_outputs.return_value = [
            {"id": "o1", "label": "Dataset"},
            {"id": "o2", "label": "Dataset"},
        ]

        result = resolve_pipeline_lineage("spark_agg", pipeline_version=3)

        assert result is not None
        assert result.pipeline_id == "spark_agg"
        assert result.pipeline_version == 3
        assert result.pipeline_type == "unknown"
        assert result.input_datasets == []
        assert len(result.output_datasets) == 2
        assert result.downstream_models == []

        client.connect.assert_called_once()
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_version_defaults_to_zero_when_none(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_pipeline_outputs.return_value = []

        result = resolve_pipeline_lineage("p1", pipeline_version=None)
        assert result is not None
        assert result.pipeline_version == 0

    @patch(_JANUS_PATCH)
    def test_disconnect_called_on_exception(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_pipeline_outputs.side_effect = ValueError("bad")

        with pytest.raises(ValueError, match="bad"):
            resolve_pipeline_lineage("p1")

        client.disconnect.assert_called_once()


class TestResolveLineageGraph:
    """Tests for resolve_lineage_graph."""

    @patch(_JANUS_PATCH)
    def test_returns_graph_with_nodes_and_edges(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_full_lineage_graph.return_value = {
            "nodes": [
                {"id": "n1", "label": "Dataset"},
                {"id": "n2", "label": "Model"},
            ],
            "edges": [
                {"id": "e1", "label": "TRAINED_ON", "source": "n2", "target": "n1"},
            ],
        }

        result = resolve_lineage_graph("n1", "Dataset", depth=4)

        assert len(result.nodes) == 2
        assert len(result.edges) == 1
        assert result.edges[0].label == "TRAINED_ON"

        client.connect.assert_called_once()
        client.get_full_lineage_graph.assert_called_once_with("n1", "Dataset", 4)
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_empty_graph(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_full_lineage_graph.return_value = {}

        result = resolve_lineage_graph("x", "Dataset")
        assert result.nodes == []
        assert result.edges == []

    @patch(_JANUS_PATCH)
    def test_disconnect_called_on_exception(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_full_lineage_graph.side_effect = RuntimeError("err")

        with pytest.raises(RuntimeError):
            resolve_lineage_graph("x", "Dataset")

        client.disconnect.assert_called_once()


class TestResolveImpactAnalysis:
    """Tests for resolve_impact_analysis."""

    @patch(_JANUS_PATCH)
    def test_returns_impact_analysis(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_downstream_datasets.return_value = [
            {"id": "d1", "label": "Dataset"},
        ]
        client.get_dataset_consumers.return_value = {
            "models": [{"id": "m1", "label": "Model"}],
            "pipelines": [{"id": "p1", "label": "Pipeline"}],
        }

        result = resolve_impact_analysis("silver/customers", change_type="schema")

        assert result.target_node.id == "silver/customers"
        assert result.target_node.label == "Dataset"
        assert len(result.affected_datasets) == 1
        assert len(result.affected_models) == 1
        assert len(result.affected_pipelines) == 1

        client.connect.assert_called_once()
        client.get_downstream_datasets.assert_called_once_with("silver/customers", max_depth=10)
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_disconnect_called_on_exception(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.get_downstream_datasets.side_effect = RuntimeError("err")

        with pytest.raises(RuntimeError):
            resolve_impact_analysis("x")

        client.disconnect.assert_called_once()


class TestResolveRecordPipelineExecution:
    """Tests for resolve_record_pipeline_execution."""

    @patch(_JANUS_PATCH)
    def test_records_successfully(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value

        result = resolve_record_pipeline_execution(
            pipeline_id="pipe1",
            pipeline_version=2,
            input_datasets=["bronze/in1"],
            output_datasets=["silver/out1", "silver/out2"],
        )

        assert result is True
        client.connect.assert_called_once()
        client.add_pipeline.assert_called_once_with("pipe1", 2)
        assert client.add_pipeline_generates_dataset.call_count == 2
        client.add_pipeline_generates_dataset.assert_any_call(
            pipeline_id="pipe1", pipeline_version=2, dataset_id="silver/out1"
        )
        client.add_pipeline_generates_dataset.assert_any_call(
            pipeline_id="pipe1", pipeline_version=2, dataset_id="silver/out2"
        )
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_returns_false_on_error(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.add_pipeline.side_effect = RuntimeError("DB error")

        result = resolve_record_pipeline_execution("pipe1", 1, [], [])
        assert result is False
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_empty_output_datasets(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value

        result = resolve_record_pipeline_execution("pipe1", 1, [], [])
        assert result is True
        client.add_pipeline.assert_called_once()
        client.add_pipeline_generates_dataset.assert_not_called()
        client.disconnect.assert_called_once()


class TestResolveRecordModelTraining:
    """Tests for resolve_record_model_training."""

    @patch(_JANUS_PATCH)
    def test_records_with_dataset_versions(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value

        result = resolve_record_model_training(
            model_name="churn",
            model_version=3,
            training_datasets=["gold/cust", "gold/tx"],
            dataset_versions=["snap_a", "snap_b"],
        )

        assert result is True
        client.connect.assert_called_once()
        client.add_model.assert_called_once_with("churn", 3)
        assert client.add_model_trained_on_dataset.call_count == 2
        client.add_model_trained_on_dataset.assert_any_call(
            model_name="churn",
            model_version=3,
            dataset_id="gold/cust",
            dataset_version="snap_a",
        )
        client.add_model_trained_on_dataset.assert_any_call(
            model_name="churn",
            model_version=3,
            dataset_id="gold/tx",
            dataset_version="snap_b",
        )
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_records_without_dataset_versions(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value

        result = resolve_record_model_training(
            model_name="churn",
            model_version=1,
            training_datasets=["gold/cust"],
            dataset_versions=None,
        )

        assert result is True
        client.add_model_trained_on_dataset.assert_called_once_with(
            model_name="churn",
            model_version=1,
            dataset_id="gold/cust",
            dataset_version="",
        )

    @patch(_JANUS_PATCH)
    def test_fewer_versions_than_datasets(self, mock_janus: MagicMock) -> None:
        """When dataset_versions is shorter than training_datasets, extra datasets get empty version."""
        client = mock_janus.return_value

        result = resolve_record_model_training(
            model_name="m",
            model_version=1,
            training_datasets=["d1", "d2", "d3"],
            dataset_versions=["v1"],
        )

        assert result is True
        assert client.add_model_trained_on_dataset.call_count == 3
        # d2 and d3 should get empty string version
        client.add_model_trained_on_dataset.assert_any_call(
            model_name="m", model_version=1, dataset_id="d2", dataset_version=""
        )
        client.add_model_trained_on_dataset.assert_any_call(
            model_name="m", model_version=1, dataset_id="d3", dataset_version=""
        )

    @patch(_JANUS_PATCH)
    def test_returns_false_on_error(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.add_model.side_effect = RuntimeError("DB error")

        result = resolve_record_model_training("m", 1, ["d1"])
        assert result is False
        client.disconnect.assert_called_once()


class TestResolveRecordDatasetPromotion:
    """Tests for resolve_record_dataset_promotion."""

    @patch(_JANUS_PATCH)
    def test_records_with_transformation(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value

        result = resolve_record_dataset_promotion(
            source_dataset="bronze/customers",
            target_dataset="silver/customers",
            transformation="dedup + validate",
        )

        assert result is True
        client.connect.assert_called_once()
        client.add_dataset_derived_from.assert_called_once_with(
            target_dataset_id="silver/customers",
            source_dataset_id="bronze/customers",
            transformation="dedup + validate",
        )
        client.disconnect.assert_called_once()

    @patch(_JANUS_PATCH)
    def test_records_without_transformation(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value

        result = resolve_record_dataset_promotion("bronze/x", "silver/x")
        assert result is True
        client.add_dataset_derived_from.assert_called_once_with(
            target_dataset_id="silver/x",
            source_dataset_id="bronze/x",
            transformation=None,
        )

    @patch(_JANUS_PATCH)
    def test_returns_false_on_error(self, mock_janus: MagicMock) -> None:
        client = mock_janus.return_value
        client.add_dataset_derived_from.side_effect = RuntimeError("fail")

        result = resolve_record_dataset_promotion("bronze/x", "silver/x")
        assert result is False
        client.disconnect.assert_called_once()


# ===================================================================
# 2. graphql/types/lineage.py  -- computed properties
# ===================================================================


class TestLineageNodeGQLProperties:
    """Tests for LineageNodeGQL computed fields."""

    def test_node_type_returns_label(self) -> None:
        node = LineageNodeGQL(id="n1", label="Dataset", properties=cast("Any", {}))
        assert cast("Any", node).node_type() == "Dataset"

    def test_name_returns_dataset_id(self) -> None:
        node = LineageNodeGQL(id="n1", label="Dataset", properties=cast("Any", {"dataset_id": "gold/sales"}))
        assert cast("Any", node).name() == "gold/sales"

    def test_name_returns_model_name(self) -> None:
        node = LineageNodeGQL(id="n1", label="Model", properties=cast("Any", {"model_name": "churn"}))
        assert cast("Any", node).name() == "churn"

    def test_name_returns_pipeline_id(self) -> None:
        node = LineageNodeGQL(id="n1", label="Pipeline", properties=cast("Any", {"pipeline_id": "etl_job"}))
        assert cast("Any", node).name() == "etl_job"

    def test_name_returns_feature_view(self) -> None:
        node = LineageNodeGQL(id="n1", label="Feature", properties=cast("Any", {"feature_view": "customer_features"}))
        assert cast("Any", node).name() == "customer_features"

    def test_name_returns_empty_when_no_known_key(self) -> None:
        node = LineageNodeGQL(id="n1", label="Other", properties=cast("Any", {"foo": "bar"}))
        assert cast("Any", node).name() == ""

    def test_name_returns_empty_when_properties_not_dict(self) -> None:
        node = LineageNodeGQL(id="n1", label="X", properties=cast("Any", "not_a_dict"))
        assert cast("Any", node).name() == ""

    def test_name_priority_dataset_id_over_model_name(self) -> None:
        """dataset_id is checked first in the or-chain."""
        node = LineageNodeGQL(
            id="n1",
            label="Mixed",
            properties=cast("Any", {"dataset_id": "gold/x", "model_name": "my_model"}),
        )
        assert cast("Any", node).name() == "gold/x"


class TestLineageEdgeGQLProperties:
    """Tests for LineageEdgeGQL computed fields."""

    def test_edge_type_returns_label(self) -> None:
        edge = LineageEdgeGQL(id="e1", label="DERIVED_FROM", source="n1", target="n2", properties=None)
        assert cast("Any", edge).edge_type() == "DERIVED_FROM"


class TestDetailedLineageGraphGQLProperties:
    """Tests for DetailedLineageGraphGQL computed fields."""

    def test_node_count(self) -> None:
        graph = DetailedLineageGraphGQL(
            nodes=[_make_node("n1"), _make_node("n2"), _make_node("n3")],
            edges=[],
        )
        assert cast("Any", graph).node_count() == 3

    def test_edge_count(self) -> None:
        graph = DetailedLineageGraphGQL(
            nodes=[],
            edges=[_make_edge("e1"), _make_edge("e2")],
        )
        assert cast("Any", graph).edge_count() == 2

    def test_empty_graph_counts(self) -> None:
        graph = DetailedLineageGraphGQL(nodes=[], edges=[])
        assert cast("Any", graph).node_count() == 0
        assert cast("Any", graph).edge_count() == 0


class TestDatasetLineageGQLProperties:
    """Tests for DatasetLineageGQL computed fields."""

    def test_upstream_count(self) -> None:
        lineage = DatasetLineageGQL(
            dataset_id="gold/x",
            layer="gold",
            upstream_datasets=[_make_node("u1"), _make_node("u2")],
            downstream_datasets=[],
            generating_pipelines=[],
            consuming_models=[],
        )
        assert cast("Any", lineage).upstream_count() == 2

    def test_downstream_count(self) -> None:
        lineage = DatasetLineageGQL(
            dataset_id="gold/x",
            layer="gold",
            upstream_datasets=[],
            downstream_datasets=[_make_node("d1")],
            generating_pipelines=[],
            consuming_models=[],
        )
        assert cast("Any", lineage).downstream_count() == 1

    def test_zero_counts(self) -> None:
        lineage = DatasetLineageGQL(
            dataset_id="x",
            layer="bronze",
            upstream_datasets=[],
            downstream_datasets=[],
            generating_pipelines=[],
            consuming_models=[],
        )
        assert cast("Any", lineage).upstream_count() == 0
        assert cast("Any", lineage).downstream_count() == 0


class TestModelLineageGQLProperties:
    """Tests for ModelLineageGQL computed fields."""

    def test_is_reproducible_true(self) -> None:
        ml = ModelLineageGQL(
            model_name="m",
            model_version=1,
            training_datasets=[],
            upstream_pipelines=[],
            dataset_snapshots=["snap_1"],
        )
        assert cast("Any", ml).is_reproducible() is True

    def test_is_reproducible_false(self) -> None:
        ml = ModelLineageGQL(
            model_name="m",
            model_version=1,
            training_datasets=[],
            upstream_pipelines=[],
            dataset_snapshots=[],
        )
        assert cast("Any", ml).is_reproducible() is False


class TestImpactAnalysisGQLProperties:
    """Tests for ImpactAnalysisGQL computed fields."""

    def _make_impact(self, n_datasets: int, n_models: int, n_pipelines: int) -> ImpactAnalysisGQL:
        return ImpactAnalysisGQL(
            target_node=_make_node("target"),
            affected_datasets=[_make_node(f"d{i}") for i in range(n_datasets)],
            affected_models=[_make_node(f"m{i}") for i in range(n_models)],
            affected_pipelines=[_make_node(f"p{i}") for i in range(n_pipelines)],
        )

    def test_total_affected(self) -> None:
        impact = self._make_impact(2, 3, 1)
        assert cast("Any", impact).total_affected() == 6

    def test_severity_none(self) -> None:
        impact = self._make_impact(0, 0, 0)
        assert cast("Any", impact).severity() == "NONE"
        assert cast("Any", impact).total_affected() == 0

    def test_severity_low(self) -> None:
        impact = self._make_impact(1, 1, 1)  # 3 total
        assert cast("Any", impact).severity() == "LOW"

    def test_severity_low_boundary(self) -> None:
        impact = self._make_impact(5, 0, 0)  # exactly 5
        assert cast("Any", impact).severity() == "LOW"

    def test_severity_medium(self) -> None:
        impact = self._make_impact(3, 2, 1)  # 6 total
        assert cast("Any", impact).severity() == "MEDIUM"

    def test_severity_medium_boundary(self) -> None:
        impact = self._make_impact(20, 0, 0)  # exactly 20
        assert cast("Any", impact).severity() == "MEDIUM"

    def test_severity_high(self) -> None:
        impact = self._make_impact(10, 8, 4)  # 22 total
        assert cast("Any", impact).severity() == "HIGH"

    def test_severity_high_large(self) -> None:
        impact = self._make_impact(50, 50, 50)  # 150 total
        assert cast("Any", impact).severity() == "HIGH"


# ===================================================================
# 3. graphql/types/dataset.py  -- VersionedDatasetGQL
# ===================================================================


def _make_versioned_dataset(**overrides: Any) -> VersionedDatasetGQL:
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "customers",
        "namespace": "gold",
        "description": "Customer data",
        "layer": "gold",
        "classification": None,
        "quality_score": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-06-01T00:00:00Z",
        "current_version": "snap_latest",
        "total_versions": 5,
    }
    defaults.update(overrides)
    return VersionedDatasetGQL(**defaults)


class TestVersionedDatasetGQLVersions:
    """Tests for VersionedDatasetGQL.versions() method."""

    @patch(_ICEBERG_PATCH)
    def test_returns_versions_list(self, mock_iceberg: MagicMock) -> None:
        iceberg_instance = mock_iceberg.return_value
        iceberg_instance.list_snapshots.return_value = [
            {
                "snapshot_id": "snap_1",
                "timestamp": "2024-01-01T00:00:00Z",
                "timestamp_ms": 1704067200000,
                "operation": "APPEND",
                "summary": {"added-data-files": "2"},
            },
            {
                "snapshot_id": "snap_2",
                "timestamp": "2024-02-01T00:00:00Z",
                "timestamp_ms": 1706745600000,
                "operation": "OVERWRITE",
                "summary": None,
            },
        ]

        ds = _make_versioned_dataset()
        versions = cast("Any", ds).versions()

        assert len(versions) == 2
        assert versions[0].snapshot_id == "snap_1"
        assert versions[0].timestamp == "2024-01-01T00:00:00Z"
        assert versions[0].timestamp_ms == 1704067200000
        assert versions[0].operation == "APPEND"
        assert versions[0].summary == {"added-data-files": "2"}

        assert versions[1].snapshot_id == "snap_2"
        assert versions[1].operation == "OVERWRITE"
        assert versions[1].summary is None

        mock_iceberg.assert_called_once()
        iceberg_instance.list_snapshots.assert_called_once_with("gold", "customers")

    @patch(_ICEBERG_PATCH)
    def test_returns_empty_on_exception(self, mock_iceberg: MagicMock) -> None:
        mock_iceberg.return_value.list_snapshots.side_effect = RuntimeError("no catalog")

        ds = _make_versioned_dataset()
        versions = cast("Any", ds).versions()

        assert versions == []

    @patch(_ICEBERG_PATCH)
    def test_returns_empty_when_no_snapshots(self, mock_iceberg: MagicMock) -> None:
        mock_iceberg.return_value.list_snapshots.return_value = []

        ds = _make_versioned_dataset()
        versions = cast("Any", ds).versions()

        assert versions == []


class TestVersionedDatasetGQLGetVersionData:
    """Tests for VersionedDatasetGQL.get_version_data() method."""

    @patch(_ICEBERG_PATCH)
    def test_returns_data_dict(self, mock_iceberg: MagicMock) -> None:
        mock_df = MagicMock()
        mock_df.__len__ = MagicMock(return_value=100)
        mock_df.columns = ["id", "name", "email"]
        mock_df.head.return_value.to_dict.return_value = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
        ]
        mock_iceberg.return_value.time_travel.return_value = mock_df

        ds = _make_versioned_dataset()
        result = cast("Any", ds).get_version_data(snapshot_id="snap_1", limit=10)

        assert result["snapshot_id"] == "snap_1"
        assert result["row_count"] == 100
        assert result["schema"] == ["id", "name", "email"]
        assert len(result["sample"]) == 1
        mock_df.head.assert_called_once_with(10)
        mock_iceberg.return_value.time_travel.assert_called_once_with("gold", "customers", "snap_1")

    @patch(_ICEBERG_PATCH)
    def test_returns_error_dict_on_exception(self, mock_iceberg: MagicMock) -> None:
        mock_iceberg.return_value.time_travel.side_effect = ValueError("snapshot not found")

        ds = _make_versioned_dataset()
        result = cast("Any", ds).get_version_data(snapshot_id="bad_snap")

        assert "error" in result
        assert "snapshot not found" in result["error"]
        assert result["snapshot_id"] == "bad_snap"

    @patch(_ICEBERG_PATCH)
    def test_custom_limit_passed_to_head(self, mock_iceberg: MagicMock) -> None:
        mock_df = MagicMock()
        mock_df.__len__ = MagicMock(return_value=5)
        mock_df.columns = ["col_a"]
        mock_df.head.return_value.to_dict.return_value = []
        mock_iceberg.return_value.time_travel.return_value = mock_df

        ds = _make_versioned_dataset()
        cast("Any", ds).get_version_data(snapshot_id="snap_x", limit=3)

        mock_df.head.assert_called_once_with(3)


# ===================================================================
# 4. graphql/schema.py  -- Query / Mutation delegation
# ===================================================================

_RESOLVER_MOD = "odg_core.graphql.schema"


class TestSchemaQueryDelegation:
    """Verify that Query methods delegate to the correct resolver functions."""

    @patch(f"{_RESOLVER_MOD}.resolve_dataset_lineage")
    def test_dataset_lineage_delegates(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Query

        sentinel = MagicMock()
        mock_resolver.return_value = sentinel

        q = Query()
        result = cast("Any", q).dataset_lineage(dataset_id="gold/customers", depth=5)

        mock_resolver.assert_called_once_with("gold/customers", 5)
        assert result is sentinel

    @patch(f"{_RESOLVER_MOD}.resolve_model_lineage")
    def test_model_lineage_delegates(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Query

        sentinel = MagicMock()
        mock_resolver.return_value = sentinel

        q = Query()
        result = cast("Any", q).model_lineage(model_name="churn", model_version=3)

        mock_resolver.assert_called_once_with("churn", 3)
        assert result is sentinel

    @patch(f"{_RESOLVER_MOD}.resolve_pipeline_lineage")
    def test_pipeline_lineage_delegates(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Query

        sentinel = MagicMock()
        mock_resolver.return_value = sentinel

        q = Query()
        result = cast("Any", q).pipeline_lineage(pipeline_id="etl", pipeline_version=2)

        mock_resolver.assert_called_once_with("etl", 2)
        assert result is sentinel

    @patch(f"{_RESOLVER_MOD}.resolve_pipeline_lineage")
    def test_pipeline_lineage_delegates_none_version(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Query

        q = Query()
        cast("Any", q).pipeline_lineage(pipeline_id="etl", pipeline_version=None)

        mock_resolver.assert_called_once_with("etl", None)

    @patch(f"{_RESOLVER_MOD}.resolve_lineage_graph")
    def test_lineage_graph_delegates(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Query

        sentinel = MagicMock()
        mock_resolver.return_value = sentinel

        q = Query()
        result = cast("Any", q).lineage_graph(node_id="n1", node_type="Dataset", depth=4)

        mock_resolver.assert_called_once_with("n1", "Dataset", 4)
        assert result is sentinel

    @patch(f"{_RESOLVER_MOD}.resolve_impact_analysis")
    def test_impact_analysis_delegates(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Query

        sentinel = MagicMock()
        mock_resolver.return_value = sentinel

        q = Query()
        result = cast("Any", q).impact_analysis(dataset_id="silver/customers", change_type="schema")

        mock_resolver.assert_called_once_with("silver/customers", "schema")
        assert result is sentinel


class TestSchemaMutationDelegation:
    """Verify that Mutation methods delegate to the correct resolver functions."""

    @patch(f"{_RESOLVER_MOD}.resolve_record_pipeline_execution")
    def test_record_pipeline_execution_delegates(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Mutation

        mock_resolver.return_value = True

        m = Mutation()
        result = cast("Any", m).record_pipeline_execution(
            pipeline_id="pipe1",
            pipeline_version=2,
            input_datasets=["in1"],
            output_datasets=["out1"],
        )

        mock_resolver.assert_called_once_with("pipe1", 2, ["in1"], ["out1"])
        assert result is True

    @patch(f"{_RESOLVER_MOD}.resolve_record_model_training")
    def test_record_model_training_delegates(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Mutation

        mock_resolver.return_value = True

        m = Mutation()
        result = cast("Any", m).record_model_training(
            model_name="churn",
            model_version=5,
            training_datasets=["gold/cust"],
            dataset_versions=["snap_a"],
        )

        mock_resolver.assert_called_once_with("churn", 5, ["gold/cust"], ["snap_a"])
        assert result is True

    @patch(f"{_RESOLVER_MOD}.resolve_record_model_training")
    def test_record_model_training_delegates_no_versions(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Mutation

        mock_resolver.return_value = True

        m = Mutation()
        cast("Any", m).record_model_training(
            model_name="m",
            model_version=1,
            training_datasets=["d1"],
            dataset_versions=None,
        )

        mock_resolver.assert_called_once_with("m", 1, ["d1"], None)

    @patch(f"{_RESOLVER_MOD}.resolve_record_dataset_promotion")
    def test_record_dataset_promotion_delegates(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Mutation

        mock_resolver.return_value = True

        m = Mutation()
        result = cast("Any", m).record_dataset_promotion(
            source_dataset="bronze/x",
            target_dataset="silver/x",
            transformation="dedup",
        )

        mock_resolver.assert_called_once_with("bronze/x", "silver/x", "dedup")
        assert result is True

    @patch(f"{_RESOLVER_MOD}.resolve_record_dataset_promotion")
    def test_record_dataset_promotion_no_transformation(self, mock_resolver: MagicMock) -> None:
        from odg_core.graphql.schema import Mutation

        mock_resolver.return_value = True

        m = Mutation()
        cast("Any", m).record_dataset_promotion(
            source_dataset="bronze/x",
            target_dataset="silver/x",
            transformation=None,
        )

        mock_resolver.assert_called_once_with("bronze/x", "silver/x", None)
