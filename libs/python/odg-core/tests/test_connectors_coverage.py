"""Additional coverage tests for connectors (api_connector, base, web_scraper)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import Iterator

import pytest
import requests

from odg_core.connectors.base import BaseConnector, ConnectorConfig, ConnectorStatus

# ── Concrete subclass for ingest() testing ────────────────────


class _IngestableConnector(BaseConnector):
    """Connector that supports ingest() testing."""

    def __init__(
        self, config: ConnectorConfig, records: list[dict[str, Any]] | None = None, fail_connect: bool = False
    ):
        super().__init__(config)
        self._records = records or []
        self._fail_connect = fail_connect

    def connect(self) -> None:
        if self._fail_connect:
            raise ConnectionError("Connection failed")
        self._connected = True

    def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        yield from self._records

    def get_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}


# ── BaseConnector.ingest() ────────────────────────────────────


class TestBaseConnectorIngest:
    @pytest.fixture()
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(connector_type="test", source_name="test_source")

    @patch("odg_core.lineage.emitter.emit_lineage_event")
    def test_ingest_success(self, mock_lineage: MagicMock, config: ConnectorConfig) -> None:
        records = [{"id": 1}, {"id": 2}, {"id": 3}]
        connector = _IngestableConnector(config, records=records)

        # Mock _store_record to avoid CouchDB dependency
        cast("Any", connector)._store_record = MagicMock()

        result = connector.ingest()
        assert result.status == ConnectorStatus.SUCCESS
        assert result.records_ingested == 3
        assert result.records_failed == 0
        assert result.duration_seconds >= 0
        assert "run_id" in result.metadata

    @patch("odg_core.lineage.emitter.emit_lineage_event")
    def test_ingest_partial_with_invalid_records(self, mock_lineage: MagicMock, config: ConnectorConfig) -> None:
        records = [{"id": 1}, "not_a_dict", {"id": 3}]
        connector = _IngestableConnector(config, records=records)  # type: ignore[arg-type]
        cast("Any", connector)._store_record = MagicMock()

        # Override validate_record to reject non-dicts

        result = connector.ingest()
        assert result.status == ConnectorStatus.PARTIAL
        assert result.records_ingested == 2
        assert result.records_failed == 1
        assert len(result.errors) == 1

    @patch("odg_core.lineage.emitter.emit_lineage_event")
    def test_ingest_all_failed(self, mock_lineage: MagicMock, config: ConnectorConfig) -> None:
        records = ["bad1", "bad2"]
        connector = _IngestableConnector(config, records=records)  # type: ignore[arg-type]
        cast("Any", connector)._store_record = MagicMock()

        result = connector.ingest()
        assert result.status == ConnectorStatus.FAILED
        assert result.records_ingested == 0
        assert result.records_failed == 2

    def test_ingest_connect_failure(self, config: ConnectorConfig) -> None:
        connector = _IngestableConnector(config, fail_connect=True)
        result = connector.ingest()
        assert result.status == ConnectorStatus.FAILED
        assert result.error_message is not None
        assert "Connection failed" in result.error_message

    @patch("odg_core.lineage.emitter.emit_lineage_event")
    def test_ingest_disconnects_after(self, mock_lineage: MagicMock, config: ConnectorConfig) -> None:
        connector = _IngestableConnector(config, records=[{"id": 1}])
        cast("Any", connector)._store_record = MagicMock()
        connector.ingest()
        assert connector._connected is False

    @patch("odg_core.lineage.emitter.emit_lineage_event")
    def test_ingest_auto_connects(self, mock_lineage: MagicMock, config: ConnectorConfig) -> None:
        connector = _IngestableConnector(config, records=[{"id": 1}])
        cast("Any", connector)._store_record = MagicMock()
        assert connector._connected is False
        connector.ingest()
        # After ingest, disconnect is called in finally
        assert connector._connected is False

    def test_store_record_default_logs_warning(self, config: ConnectorConfig) -> None:
        connector = _IngestableConnector(config)
        # Default _store_record tries CouchDB which will fail
        # Should not raise
        connector._store_record({"id": 1})


# ── APIConnector.connect() ────────────────────────────────────


class TestAPIConnectorConnect:
    def test_connect_basic_auth(self) -> None:
        from odg_core.connectors.api_connector import APIConnector

        class _ConcreteAPI(APIConnector):
            def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
                yield from []

            def get_schema(self) -> dict[str, Any]:
                return {}

        config = ConnectorConfig(
            connector_type="rest_api",
            source_name="test",
            auth_type="basic",
            credentials={"username": "user", "password": "pass"},
        )
        connector = _ConcreteAPI(config, base_url="http://example.com")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(requests.Session, "get", return_value=mock_response):
            connector.connect()

        assert connector._connected is True
        assert connector.session is not None
        assert connector.session.auth == ("user", "pass")

    def test_connect_bearer_auth(self) -> None:
        from odg_core.connectors.api_connector import APIConnector

        class _ConcreteAPI(APIConnector):
            def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
                yield from []

            def get_schema(self) -> dict[str, Any]:
                return {}

        config = ConnectorConfig(
            connector_type="rest_api",
            source_name="test",
            auth_type="bearer",
            credentials={"token": "my-token"},
        )
        connector = _ConcreteAPI(config, base_url="http://example.com")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(requests.Session, "get", return_value=mock_response):
            connector.connect()

        assert connector._connected is True
        assert "Bearer my-token" in cast("Any", connector.session).headers.get("Authorization", "")

    def test_connect_api_key_auth(self) -> None:
        from odg_core.connectors.api_connector import APIConnector

        class _ConcreteAPI(APIConnector):
            def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
                yield from []

            def get_schema(self) -> dict[str, Any]:
                return {}

        config = ConnectorConfig(
            connector_type="rest_api",
            source_name="test",
            auth_type="api_key",
            credentials={"api_key": "secret-key", "header_name": "X-Custom-Key"},
        )
        connector = _ConcreteAPI(config, base_url="http://example.com")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(requests.Session, "get", return_value=mock_response):
            connector.connect()

        assert cast("Any", connector.session).headers.get("X-Custom-Key") == "secret-key"

    def test_connect_failure(self) -> None:
        from odg_core.connectors.api_connector import APIConnector

        class _ConcreteAPI(APIConnector):
            def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
                yield from []

            def get_schema(self) -> dict[str, Any]:
                return {}

        config = ConnectorConfig(connector_type="rest_api", source_name="test")
        connector = _ConcreteAPI(config, base_url="http://example.com")

        with (
            patch.object(requests.Session, "get", side_effect=Exception("Connection refused")),
            pytest.raises(ConnectionError, match="Failed to connect"),
        ):
            connector.connect()


# ── APIConnector.disconnect() ─────────────────────────────────


class TestAPIConnectorDisconnect:
    def test_disconnect_closes_session(self) -> None:
        from odg_core.connectors.api_connector import APIConnector

        class _ConcreteAPI(APIConnector):
            def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
                yield from []

            def get_schema(self) -> dict[str, Any]:
                return {}

        config = ConnectorConfig(connector_type="rest_api", source_name="test")
        connector = _ConcreteAPI(config, base_url="http://example.com")
        mock_session = MagicMock(spec=requests.Session)
        connector.session = mock_session
        connector._connected = True

        connector.disconnect()

        mock_session.close.assert_called_once()
        assert connector._connected is False

    def test_disconnect_without_session(self) -> None:
        from odg_core.connectors.api_connector import APIConnector

        class _ConcreteAPI(APIConnector):
            def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
                yield from []

            def get_schema(self) -> dict[str, Any]:
                return {}

        config = ConnectorConfig(connector_type="rest_api", source_name="test")
        connector = _ConcreteAPI(config, base_url="http://example.com")
        connector.disconnect()
        assert connector._connected is False


# ── RESTConnector.extract() ───────────────────────────────────


class TestRESTConnectorExtract:
    def test_extract_offset_pagination(self) -> None:
        from odg_core.connectors.api_connector import RESTConnector

        config = ConnectorConfig(connector_type="rest_api", source_name="test")
        connector = RESTConnector(
            config=config,
            base_url="http://example.com",
            endpoint="/api/data",
            pagination_type="offset",
            records_per_page=2,
        )

        mock_session = MagicMock(spec=requests.Session)
        connector.session = mock_session

        # First page returns 2 records, second returns 1 (less than page size, stops)
        resp1 = MagicMock()
        resp1.json.return_value = [{"id": 1}, {"id": 2}]
        resp1.raise_for_status = MagicMock()
        resp1.headers = {}

        resp2 = MagicMock()
        resp2.json.return_value = [{"id": 3}]
        resp2.raise_for_status = MagicMock()
        resp2.headers = {}

        mock_session.get.side_effect = [resp1, resp2]

        records = list(connector.extract())
        assert len(records) == 3

    def test_extract_with_limit(self) -> None:
        from odg_core.connectors.api_connector import RESTConnector

        config = ConnectorConfig(connector_type="rest_api", source_name="test")
        connector = RESTConnector(
            config=config,
            base_url="http://example.com",
            endpoint="/api/data",
            records_per_page=10,
        )

        mock_session = MagicMock(spec=requests.Session)
        connector.session = mock_session

        resp = MagicMock()
        resp.json.return_value = [{"id": i} for i in range(10)]
        resp.raise_for_status = MagicMock()
        resp.headers = {}
        mock_session.get.return_value = resp

        records = list(connector.extract(limit=3))
        assert len(records) == 3

    def test_extract_with_data_path(self) -> None:
        from odg_core.connectors.api_connector import RESTConnector

        config = ConnectorConfig(connector_type="rest_api", source_name="test")
        connector = RESTConnector(
            config=config,
            base_url="http://example.com",
            endpoint="/api/data",
            data_path="results.items",
            records_per_page=10,
        )

        mock_session = MagicMock(spec=requests.Session)
        connector.session = mock_session

        resp = MagicMock()
        resp.json.return_value = {"results": {"items": [{"id": 1}]}}
        resp.raise_for_status = MagicMock()
        resp.headers = {}
        mock_session.get.return_value = resp

        records = list(connector.extract())
        assert len(records) == 1
        assert records[0] == {"id": 1}

    def test_extract_fallback_data_keys(self) -> None:
        from odg_core.connectors.api_connector import RESTConnector

        config = ConnectorConfig(connector_type="rest_api", source_name="test")
        connector = RESTConnector(
            config=config,
            base_url="http://example.com",
            endpoint="/api/data",
            records_per_page=10,
        )

        mock_session = MagicMock(spec=requests.Session)
        connector.session = mock_session

        resp = MagicMock()
        resp.json.return_value = {"data": [{"id": 1}]}
        resp.raise_for_status = MagicMock()
        resp.headers = {}
        mock_session.get.return_value = resp

        records = list(connector.extract())
        assert records == [{"id": 1}]

    def test_extract_request_error_breaks(self) -> None:
        from odg_core.connectors.api_connector import RESTConnector

        config = ConnectorConfig(connector_type="rest_api", source_name="test")
        connector = RESTConnector(
            config=config,
            base_url="http://example.com",
            endpoint="/api/data",
        )

        mock_session = MagicMock(spec=requests.Session)
        mock_session.get.side_effect = requests.exceptions.ConnectionError("timeout")
        connector.session = mock_session

        records = list(connector.extract())
        assert records == []

    def test_extract_page_pagination(self) -> None:
        from odg_core.connectors.api_connector import RESTConnector

        config = ConnectorConfig(connector_type="rest_api", source_name="test")
        connector = RESTConnector(
            config=config,
            base_url="http://example.com",
            endpoint="/api/data",
            pagination_type="page",
            records_per_page=1,
        )

        mock_session = MagicMock(spec=requests.Session)
        connector.session = mock_session

        resp = MagicMock()
        resp.json.return_value = []
        resp.raise_for_status = MagicMock()
        resp.headers = {}
        mock_session.get.return_value = resp

        records = list(connector.extract())
        assert records == []

    def test_extract_link_header_pagination(self) -> None:
        from odg_core.connectors.api_connector import RESTConnector

        config = ConnectorConfig(connector_type="rest_api", source_name="test")
        connector = RESTConnector(
            config=config,
            base_url="http://example.com",
            endpoint="/api/data",
            pagination_type="link_header",
            records_per_page=1,
        )

        mock_session = MagicMock(spec=requests.Session)
        connector.session = mock_session

        resp1 = MagicMock()
        resp1.json.return_value = [{"id": 1}]
        resp1.raise_for_status = MagicMock()
        resp1.headers = {"Link": '<http://example.com/page2>; rel="next"'}

        resp2 = MagicMock()
        resp2.json.return_value = [{"id": 2}]
        resp2.raise_for_status = MagicMock()
        resp2.headers = {}

        mock_session.get.side_effect = [resp1, resp2]

        records = list(connector.extract())
        assert len(records) == 2


# ── GraphQLConnector.get_schema() ─────────────────────────────


class TestGraphQLConnectorGetSchema:
    def test_get_schema_success(self) -> None:
        from odg_core.connectors.api_connector import GraphQLConnector

        config = ConnectorConfig(connector_type="graphql", source_name="test")
        connector = GraphQLConnector(
            config=config,
            endpoint="http://example.com/graphql",
            query="query { items { id } }",
        )

        mock_session = MagicMock(spec=requests.Session)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"__schema": {"types": []}}}
        mock_resp.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_resp
        connector.session = mock_session

        schema = connector.get_schema()
        assert schema["type"] == "object"

    def test_get_schema_failure(self) -> None:
        from odg_core.connectors.api_connector import GraphQLConnector

        config = ConnectorConfig(connector_type="graphql", source_name="test")
        connector = GraphQLConnector(
            config=config,
            endpoint="http://example.com/graphql",
            query="query { items { id } }",
        )

        mock_session = MagicMock(spec=requests.Session)
        mock_session.post.side_effect = Exception("Network error")
        connector.session = mock_session

        schema = connector.get_schema()
        assert schema == {"type": "object", "properties": {}}


# ── WebScraperConnector.connect() / extract() ─────────────────


class TestWebScraperConnectorCoverage:
    @pytest.fixture(autouse=True)
    def _enable_scraping(self) -> Any:
        """Ensure WebScraperConnector can be instantiated without real bs4."""
        import odg_core.connectors.web_scraper as ws_mod

        orig = ws_mod._HAS_SCRAPING_DEPS
        ws_mod._HAS_SCRAPING_DEPS = True
        yield
        ws_mod._HAS_SCRAPING_DEPS = orig

    @pytest.fixture()
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(connector_type="web_scraper", source_name="test")

    @pytest.fixture()
    def selectors(self) -> dict[str, str]:
        return {"title": "h1", "desc": "p.desc"}

    def test_connect_success(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        from odg_core.connectors.web_scraper import WebScraperConnector

        connector = WebScraperConnector(config=config, base_url="http://example.com", selectors=selectors)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(requests.Session, "get", return_value=mock_response):
            connector.connect()

        assert connector._connected is True
        assert connector.session is not None
        assert connector.robot_parser is not None

    def test_connect_robots_disallows(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        from odg_core.connectors.web_scraper import WebScraperConnector

        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
            respect_robots_txt=True,
        )

        mock_parser = MagicMock()
        mock_parser.can_fetch.return_value = False

        with (
            patch.object(requests.Session, "get"),
            patch("odg_core.connectors.web_scraper.RobotFileParser", return_value=mock_parser),
            pytest.raises(ConnectionError, match=r"robots\.txt disallows"),
        ):
            connector.connect()

    def test_extract_not_connected(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        from odg_core.connectors.web_scraper import WebScraperConnector

        connector = WebScraperConnector(config=config, base_url="http://example.com", selectors=selectors)
        with pytest.raises(RuntimeError, match="Not connected"):
            list(connector.extract())

    def test_extract_basic(self, config: ConnectorConfig) -> None:
        import odg_core.connectors.web_scraper as ws_mod
        from odg_core.connectors.web_scraper import WebScraperConnector

        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors={"title": "h1"},
            rate_limit_seconds=0,
        )

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        connector.session = mock_session
        connector._connected = True

        # Mock BeautifulSoup to return a soup with the expected select() results.
        # _extract_records calls soup.select(first_selector) to find containers,
        # then container.select(selector) for each field.
        mock_element = MagicMock()
        mock_element.get_text.return_value = "Test Title"
        container = MagicMock()
        container.select.return_value = [mock_element]
        mock_soup = MagicMock()
        mock_soup.select.return_value = [container]

        orig_bs = getattr(cast("Any", ws_mod), "BeautifulSoup", None)
        cast("Any", ws_mod).BeautifulSoup = MagicMock(return_value=mock_soup)
        try:
            records = list(connector.extract())
        finally:
            if orig_bs is not None:
                cast("Any", ws_mod).BeautifulSoup = orig_bs
            else:
                delattr(cast("Any", ws_mod), "BeautifulSoup")

        assert len(records) == 1
        assert records[0]["title"] == "Test Title"
        assert records[0]["_url"] == "http://example.com"

    def test_extract_with_follow_links(self, config: ConnectorConfig) -> None:
        import odg_core.connectors.web_scraper as ws_mod
        from odg_core.connectors.web_scraper import WebScraperConnector

        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors={"title": "h1"},
            follow_links=True,
            link_selector="a.page-link",
            max_depth=1,
            rate_limit_seconds=0,
        )

        mock_session = MagicMock()
        resp1 = MagicMock()
        resp1.raise_for_status = MagicMock()
        resp2 = MagicMock()
        resp2.raise_for_status = MagicMock()
        mock_session.get.side_effect = [resp1, resp2]
        connector.session = mock_session
        connector._connected = True

        # Page 1 soup: has title + link to page2
        title1 = MagicMock()
        title1.get_text.return_value = "Page 1"
        link1 = MagicMock()
        link1.get.return_value = "/page2"

        soup1 = MagicMock()

        def soup1_select(sel: str) -> list[Any]:
            if sel == "h1":
                return [title1]
            if sel == "a.page-link":
                return [link1]
            return []

        soup1.select = soup1_select

        # Page 2 soup: has title, no links
        title2 = MagicMock()
        title2.get_text.return_value = "Page 2"
        soup2 = MagicMock()
        soup2.select.return_value = [title2]

        orig_bs = getattr(cast("Any", ws_mod), "BeautifulSoup", None)
        cast("Any", ws_mod).BeautifulSoup = MagicMock(side_effect=[soup1, soup2])
        try:
            records = list(connector.extract())
        finally:
            if orig_bs is not None:
                cast("Any", ws_mod).BeautifulSoup = orig_bs
            else:
                delattr(cast("Any", ws_mod), "BeautifulSoup")

        assert len(records) == 2

    def test_extract_skip_visited_url(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        from odg_core.connectors.web_scraper import WebScraperConnector

        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
            rate_limit_seconds=0,
        )
        connector.session = MagicMock()
        connector._connected = True
        connector._visited_urls.add("http://example.com")

        records = list(connector.extract())
        assert records == []

    def test_extract_records_no_containers(self, config: ConnectorConfig) -> None:
        from odg_core.connectors.web_scraper import WebScraperConnector

        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors={"title": "h1.missing", "desc": "p.desc"},
            rate_limit_seconds=0,
        )

        # Build a mock soup: h1.missing -> empty, p.desc -> one element
        mock_desc = MagicMock()
        mock_desc.get_text.return_value = "Hello"

        mock_soup = MagicMock()

        def mock_select(selector: str) -> list[Any]:
            if selector == "p.desc":
                return [mock_desc]
            return []

        mock_soup.select = mock_select

        records = list(connector._extract_records(mock_soup, "http://example.com"))
        assert len(records) == 1
        assert records[0]["_url"] == "http://example.com"

    def test_extract_records_with_containers(self, config: ConnectorConfig) -> None:
        from odg_core.connectors.web_scraper import WebScraperConnector

        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors={"title": "h3.title", "desc": "p.desc"},
            rate_limit_seconds=0,
        )

        # Build mock containers that each have title + desc
        title1 = MagicMock()
        title1.get_text.return_value = "Item 1"
        desc1 = MagicMock()
        desc1.get_text.return_value = "Desc 1"
        title2 = MagicMock()
        title2.get_text.return_value = "Item 2"
        desc2 = MagicMock()
        desc2.get_text.return_value = "Desc 2"

        container1 = MagicMock()
        container1.select = lambda sel: [title1] if sel == "h3.title" else ([desc1] if sel == "p.desc" else [])
        container2 = MagicMock()
        container2.select = lambda sel: [title2] if sel == "h3.title" else ([desc2] if sel == "p.desc" else [])

        mock_soup = MagicMock()

        def soup_select(selector: str) -> list[Any]:
            if selector == "h3.title":
                return [container1, container2]
            return []

        mock_soup.select = soup_select

        records = list(connector._extract_records(mock_soup, "http://example.com"))
        assert len(records) == 2

    def test_disconnect_closes_session(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        from odg_core.connectors.web_scraper import WebScraperConnector

        connector = WebScraperConnector(config=config, base_url="http://example.com", selectors=selectors)
        mock_session = MagicMock()
        connector.session = mock_session
        connector._connected = True

        connector.disconnect()

        mock_session.close.assert_called_once()
        assert connector._connected is False
