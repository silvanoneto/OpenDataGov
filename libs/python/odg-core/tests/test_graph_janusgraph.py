"""Tests for odg_core.graph.janusgraph_client module."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    import types

# Mock gremlin_python modules so JanusGraphClient can be imported
# without the actual gremlinpython package installed.
_gremlin_mocks = {
    "gremlin_python": MagicMock(),
    "gremlin_python.driver": MagicMock(),
    "gremlin_python.driver.client": MagicMock(),
    "gremlin_python.driver.driver_remote_connection": MagicMock(),
    "gremlin_python.process": MagicMock(),
    "gremlin_python.process.anonymous_traversal": MagicMock(),
    "gremlin_python.process.graph_traversal": MagicMock(),
}

_MOD_KEY = "odg_core.graph.janusgraph_client"


def _fresh_import() -> types.ModuleType:
    """Force re-import of janusgraph_client with gremlin mocked."""
    sys.modules.pop(_MOD_KEY, None)
    import odg_core.graph.janusgraph_client as mod

    return mod


def _make_client() -> Any:
    """Create a JanusGraphClient with gremlin mocked."""
    with patch.dict(sys.modules, _gremlin_mocks):
        mod = _fresh_import()
        return mod.JanusGraphClient(url="ws://fake:8182/gremlin")


# ──── Dataclasses (no gremlin dependency) ────────────────────


class TestLineageNode:
    """Tests for LineageNode dataclass properties."""

    def test_node_type_returns_label(self) -> None:
        from odg_core.graph.janusgraph_client import LineageNode

        node = LineageNode(id="1", label="Dataset", properties={"name": "customers"})
        assert node.node_type == "Dataset"

    def test_name_returns_properties_name(self) -> None:
        from odg_core.graph.janusgraph_client import LineageNode

        node = LineageNode(id="2", label="Model", properties={"name": "churn_v1"})
        assert node.name == "churn_v1"

    def test_name_returns_empty_string_when_missing(self) -> None:
        from odg_core.graph.janusgraph_client import LineageNode

        node = LineageNode(id="3", label="Pipeline", properties={})
        assert node.name == ""


class TestLineageEdge:
    """Tests for LineageEdge dataclass properties."""

    def test_edge_type_returns_label(self) -> None:
        from odg_core.graph.janusgraph_client import LineageEdge

        edge = LineageEdge(
            id="e1",
            label="DERIVED_FROM",
            source_id="v1",
            target_id="v2",
            properties={},
        )
        assert edge.edge_type == "DERIVED_FROM"

    def test_edge_properties(self) -> None:
        from odg_core.graph.janusgraph_client import LineageEdge

        edge = LineageEdge(
            id="e2",
            label="TRAINED_ON",
            source_id="model1",
            target_id="dataset1",
            properties={"confidence": 0.95},
        )
        assert edge.source_id == "model1"
        assert edge.target_id == "dataset1"
        assert edge.properties["confidence"] == 0.95


# ──── JanusGraphClient internal methods ──────────────────────


class TestJanusGraphClientVertexToDict:
    """Tests for JanusGraphClient._vertex_to_dict."""

    @pytest.fixture()
    def client(self) -> Any:
        return _make_client()

    def test_empty_vertex_returns_empty_dict(self, client: Any) -> None:
        assert client._vertex_to_dict({}) == {}

    def test_none_vertex_returns_empty_dict(self, client: Any) -> None:
        assert client._vertex_to_dict(None) == {}

    def test_vertex_with_id_and_label(self, client: Any) -> None:
        vertex: dict[str, Any] = {"id": 123, "label": "Dataset", "name": ["customers"]}
        result = client._vertex_to_dict(vertex)
        assert result["id"] == "123"
        assert result["label"] == "Dataset"
        assert result["name"] == "customers"

    def test_single_element_list_unwrapped(self, client: Any) -> None:
        vertex: dict[str, Any] = {"id": 1, "label": "Model", "version": [3]}
        result = client._vertex_to_dict(vertex)
        assert result["version"] == 3

    def test_multi_element_list_kept_as_list(self, client: Any) -> None:
        vertex: dict[str, Any] = {"id": 1, "label": "Feature", "names": ["f1", "f2"]}
        result = client._vertex_to_dict(vertex)
        assert result["names"] == ["f1", "f2"]

    def test_non_list_value_kept_as_is(self, client: Any) -> None:
        vertex: dict[str, Any] = {"id": 1, "label": "Pipeline", "status": "running"}
        result = client._vertex_to_dict(vertex)
        assert result["status"] == "running"


class TestJanusGraphClientEdgeToDict:
    """Tests for JanusGraphClient._edge_to_dict."""

    @pytest.fixture()
    def client(self) -> Any:
        return _make_client()

    def test_empty_edge_returns_empty_dict(self, client: Any) -> None:
        assert client._edge_to_dict({}) == {}

    def test_none_edge_returns_empty_dict(self, client: Any) -> None:
        assert client._edge_to_dict(None) == {}

    def test_edge_with_source_and_target(self, client: Any) -> None:
        edge: dict[str, Any] = {
            "id": "e1",
            "label": "DERIVED_FROM",
            "outV": "v1",
            "inV": "v2",
            "weight": 1.0,
        }
        result = client._edge_to_dict(edge)
        assert result["id"] == "e1"
        assert result["label"] == "DERIVED_FROM"
        assert result["source"] == "v1"
        assert result["target"] == "v2"
        assert result["weight"] == 1.0

    def test_edge_excludes_standard_keys_from_extras(self, client: Any) -> None:
        edge: dict[str, Any] = {"id": "e2", "label": "TRAINED_ON", "outV": "m", "inV": "d"}
        result = client._edge_to_dict(edge)
        # Only id, label, source, target should be present
        assert set(result.keys()) == {"id", "label", "source", "target"}


class TestJanusGraphClientDeduplicateNodes:
    """Tests for JanusGraphClient._deduplicate_nodes."""

    @pytest.fixture()
    def client(self) -> Any:
        return _make_client()

    def test_deduplicates_by_id(self, client: Any) -> None:
        nodes = [
            {"id": "1", "label": "Dataset"},
            {"id": "1", "label": "Dataset"},
            {"id": "2", "label": "Model"},
        ]
        result = client._deduplicate_nodes(nodes)
        assert len(result) == 2
        ids = [n["id"] for n in result]
        assert ids == ["1", "2"]

    def test_empty_list_returns_empty(self, client: Any) -> None:
        assert client._deduplicate_nodes([]) == []

    def test_nodes_without_id_are_skipped(self, client: Any) -> None:
        nodes = [{"label": "Unknown"}, {"id": "1", "label": "Dataset"}]
        result = client._deduplicate_nodes(nodes)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_preserves_order(self, client: Any) -> None:
        nodes = [
            {"id": "3", "label": "C"},
            {"id": "1", "label": "A"},
            {"id": "2", "label": "B"},
        ]
        result = client._deduplicate_nodes(nodes)
        assert [n["id"] for n in result] == ["3", "1", "2"]


class TestJanusGraphClientGetClient:
    """Tests for JanusGraphClient._get_client."""

    def test_raises_connection_error_when_not_connected(self) -> None:
        client = _make_client()
        # _client is None by default
        with pytest.raises(ConnectionError, match="Not connected"):
            client._get_client()

    def test_returns_client_when_connected(self) -> None:
        client = _make_client()
        mock_client = MagicMock()
        client._client = mock_client

        result = client._get_client()
        assert result is mock_client
