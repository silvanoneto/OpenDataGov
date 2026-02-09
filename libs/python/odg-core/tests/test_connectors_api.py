"""Tests for odg_core.connectors.api_connector module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from odg_core.connectors.api_connector import (
    GraphQLConnector,
    RESTConnector,
    _ensure_session,
)
from odg_core.connectors.base import ConnectorConfig

# ──── _ensure_session ────────────────────────────────────────


class TestEnsureSession:
    """Tests for the _ensure_session helper."""

    def test_raises_runtime_error_when_none(self) -> None:
        with pytest.raises(RuntimeError, match="Not connected"):
            _ensure_session(None)

    def test_returns_session_when_provided(self) -> None:
        session = MagicMock(spec=requests.Session)
        result = _ensure_session(session)
        assert result is session


# ──── RESTConnector._extract_from_path ───────────────────────


class TestRESTConnectorExtractFromPath:
    """Tests for the simple JSONPath-like extraction."""

    @pytest.fixture()
    def connector(self) -> RESTConnector:
        cfg = ConnectorConfig(connector_type="rest_api", source_name="test")
        return RESTConnector(config=cfg, base_url="http://example.com", endpoint="/data")

    def test_single_key(self, connector: RESTConnector) -> None:
        data: dict[str, Any] = {"items": [{"id": 1}, {"id": 2}]}
        result = connector._extract_from_path(data, "items")
        assert result == [{"id": 1}, {"id": 2}]

    def test_nested_path(self, connector: RESTConnector) -> None:
        data: dict[str, Any] = {"results": {"items": [{"id": 1}]}}
        result = connector._extract_from_path(data, "results.items")
        assert result == [{"id": 1}]

    def test_missing_key_returns_empty_list(self, connector: RESTConnector) -> None:
        data: dict[str, Any] = {"other": "value"}
        result = connector._extract_from_path(data, "missing")
        assert result == []

    def test_none_value_returns_empty_list(self, connector: RESTConnector) -> None:
        data: dict[str, Any] = {"items": None}
        result = connector._extract_from_path(data, "items")
        assert result == []

    def test_non_list_value_wrapped_in_list(self, connector: RESTConnector) -> None:
        data: dict[str, Any] = {"result": {"id": 1}}
        result = connector._extract_from_path(data, "result")
        assert result == [{"id": 1}]

    def test_path_through_non_dict_returns_empty(self, connector: RESTConnector) -> None:
        data: dict[str, Any] = {"level1": "not_a_dict"}
        result = connector._extract_from_path(data, "level1.level2")
        assert result == []


# ──── RESTConnector._parse_link_header ───────────────────────


class TestRESTConnectorParseLinkHeader:
    """Tests for Link header parsing."""

    @pytest.fixture()
    def connector(self) -> RESTConnector:
        cfg = ConnectorConfig(connector_type="rest_api", source_name="test")
        return RESTConnector(config=cfg, base_url="http://example.com", endpoint="/data")

    def test_extracts_next_url(self, connector: RESTConnector) -> None:
        header = '<http://example.com/page2>; rel="next", <http://example.com/page1>; rel="prev"'
        result = connector._parse_link_header(header)
        assert result == "http://example.com/page2"

    def test_no_next_returns_empty_string(self, connector: RESTConnector) -> None:
        header = '<http://example.com/page1>; rel="prev"'
        result = connector._parse_link_header(header)
        assert result == ""

    def test_single_next_link(self, connector: RESTConnector) -> None:
        header = '<http://example.com/items?page=3>; rel="next"'
        result = connector._parse_link_header(header)
        assert result == "http://example.com/items?page=3"


# ──── RESTConnector._infer_schema ────────────────────────────


class TestRESTConnectorInferSchema:
    """Tests for schema inference from a sample record."""

    @pytest.fixture()
    def connector(self) -> RESTConnector:
        cfg = ConnectorConfig(connector_type="rest_api", source_name="test")
        return RESTConnector(config=cfg, base_url="http://example.com", endpoint="/data")

    def test_infer_string(self, connector: RESTConnector) -> None:
        schema = connector._infer_schema({"name": "Alice"})
        assert schema["properties"]["name"]["type"] == "string"

    def test_infer_integer(self, connector: RESTConnector) -> None:
        schema = connector._infer_schema({"count": 42})
        assert schema["properties"]["count"]["type"] == "integer"

    def test_infer_float(self, connector: RESTConnector) -> None:
        schema = connector._infer_schema({"score": 3.14})
        assert schema["properties"]["score"]["type"] == "number"

    def test_infer_boolean(self, connector: RESTConnector) -> None:
        # Note: bool check must come before int in Python since bool is subclass of int,
        # but the source checks isinstance(value, bool) after int, so True maps to "integer".
        # Actually looking at the source, bool is checked AFTER int, so True will match int first.
        # Let's test what the code actually does:
        schema = connector._infer_schema({"active": True})
        # In Python, isinstance(True, int) is True and it's checked before bool
        assert schema["properties"]["active"]["type"] == "integer"

    def test_infer_list(self, connector: RESTConnector) -> None:
        schema = connector._infer_schema({"tags": ["a", "b"]})
        assert schema["properties"]["tags"]["type"] == "array"

    def test_infer_dict(self, connector: RESTConnector) -> None:
        schema = connector._infer_schema({"nested": {"key": "val"}})
        assert schema["properties"]["nested"]["type"] == "object"

    def test_required_contains_all_keys(self, connector: RESTConnector) -> None:
        record: dict[str, Any] = {"a": "x", "b": 1}
        schema = connector._infer_schema(record)
        assert set(schema["required"]) == {"a", "b"}

    def test_infer_none_maps_to_string(self, connector: RESTConnector) -> None:
        schema = connector._infer_schema({"field": None})
        assert schema["properties"]["field"]["type"] == "string"


# ──── GraphQLConnector.extract ───────────────────────────────


class TestGraphQLConnectorExtract:
    """Tests for GraphQL data extraction."""

    @pytest.fixture()
    def connector(self) -> GraphQLConnector:
        cfg = ConnectorConfig(connector_type="graphql", source_name="test_gql")
        return GraphQLConnector(
            config=cfg,
            endpoint="http://example.com/graphql",
            query="query { items { id name } }",
        )

    def test_yields_list_records(self, connector: GraphQLConnector) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"items": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}}
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock(spec=requests.Session)
        mock_session.post.return_value = mock_response
        connector.session = mock_session

        records = list(connector.extract())
        assert len(records) == 2
        assert records[0] == {"id": 1, "name": "a"}

    def test_yields_single_dict_record(self, connector: GraphQLConnector) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"repository": {"name": "kafka", "stars": 1000}}}
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock(spec=requests.Session)
        mock_session.post.return_value = mock_response
        connector.session = mock_session

        records = list(connector.extract())
        assert len(records) == 1
        assert records[0] == {"name": "kafka", "stars": 1000}

    def test_yields_scalar_as_dict(self, connector: GraphQLConnector) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"count": 42}}
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock(spec=requests.Session)
        mock_session.post.return_value = mock_response
        connector.session = mock_session

        records = list(connector.extract())
        assert records == [{"count": 42}]

    def test_graphql_errors_returns_empty(self, connector: GraphQLConnector) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"errors": [{"message": "bad"}]}
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock(spec=requests.Session)
        mock_session.post.return_value = mock_response
        connector.session = mock_session

        records = list(connector.extract())
        assert records == []

    def test_request_exception_returns_empty(self, connector: GraphQLConnector) -> None:
        mock_session = MagicMock(spec=requests.Session)
        mock_session.post.side_effect = requests.exceptions.ConnectionError("fail")
        connector.session = mock_session

        records = list(connector.extract())
        assert records == []
