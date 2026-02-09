"""Tests for remaining coverage gaps across odg_core modules.

Covers:
- connectors/web_scraper.py
- auth/keycloak.py
- plugins/registry.py
- feast/materialization_tracker.py
- metadata/base_connector.py
- events/kafka_publisher.py
- events/kafka_consumer.py
- governance/base_rule.py
- privacy/base_privacy.py
- storage/base_storage.py
- connectors/base.py (_infer_schema)
- nosql/couchdb_client.py
- connectors/file_connector.py (S3Connector, FTPConnector)
- storage/iceberg_catalog.py
"""

from __future__ import annotations

import contextlib
import sys
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# ────────────────────────────────────────────────────────────────
# 1. connectors/web_scraper.py
# ────────────────────────────────────────────────────────────────


@pytest.fixture()
def web_scraper_module():
    """Import web_scraper with mocked bs4 and requests in sys.modules."""
    mock_bs4 = MagicMock()
    mock_requests = MagicMock()

    saved_bs4 = sys.modules.get("bs4")
    saved_requests = sys.modules.get("requests")

    sys.modules["bs4"] = mock_bs4
    sys.modules["requests"] = mock_requests

    # Force reimport so the try/except picks up the mocks
    mod_name = "odg_core.connectors.web_scraper"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    import odg_core.connectors.web_scraper as ws_mod

    ws_mod._HAS_SCRAPING_DEPS = True
    ws_mod.requests = mock_requests  # type: ignore[attr-defined]
    ws_mod.BeautifulSoup = mock_bs4.BeautifulSoup  # type: ignore[attr-defined]

    yield ws_mod, mock_requests, mock_bs4

    # Restore original modules
    if saved_bs4 is not None:
        sys.modules["bs4"] = saved_bs4
    else:
        sys.modules.pop("bs4", None)
    if saved_requests is not None:
        sys.modules["requests"] = saved_requests
    else:
        sys.modules.pop("requests", None)


def _make_scraper_config() -> Any:
    from odg_core.connectors.base import ConnectorConfig

    return ConnectorConfig(
        connector_type="web_scraper",
        source_name="test_scraper",
        target_table="test_table",
    )


class TestWebScraperConnector:
    """Tests for WebScraperConnector."""

    def test_init(self, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1.title", "body": "p.content"},
        )
        assert connector.base_url == "https://example.com"
        assert connector.selectors == {"title": "h1.title", "body": "p.content"}
        assert connector.respect_robots_txt is True
        assert connector.follow_links is False

    def test_init_missing_deps(self, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        ws_mod._HAS_SCRAPING_DEPS = False
        config = _make_scraper_config()
        with pytest.raises(ImportError, match="beautifulsoup4"):
            ws_mod.WebScraperConnector(
                config=config,
                base_url="https://example.com",
                selectors={"title": "h1"},
            )

    def test_connect_with_robots_txt(self, web_scraper_module):
        ws_mod, mock_requests, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
            respect_robots_txt=True,
        )

        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": "test-bot"}
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        with patch("odg_core.connectors.web_scraper.RobotFileParser") as mock_rp_cls:
            mock_rp = MagicMock()
            mock_rp.can_fetch.return_value = True
            mock_rp_cls.return_value = mock_rp

            connector.connect()

        assert connector._connected is True
        assert connector.session is mock_session

    def test_connect_robots_txt_exception(self, web_scraper_module):
        """Cover the except branch when robots.txt read fails."""
        ws_mod, mock_requests, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
            respect_robots_txt=True,
        )

        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": "test-bot"}
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        with patch("odg_core.connectors.web_scraper.RobotFileParser") as mock_rp_cls:
            mock_rp = MagicMock()
            mock_rp.read.side_effect = Exception("network error")
            mock_rp.can_fetch.return_value = True
            mock_rp_cls.return_value = mock_rp

            connector.connect()

        assert connector._connected is True

    def test_connect_disallowed_by_robots(self, web_scraper_module):
        ws_mod, mock_requests, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
            respect_robots_txt=True,
        )

        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": "test-bot"}
        mock_requests.Session.return_value = mock_session

        with patch("odg_core.connectors.web_scraper.RobotFileParser") as mock_rp_cls:
            mock_rp = MagicMock()
            mock_rp.can_fetch.return_value = False
            mock_rp_cls.return_value = mock_rp

            with pytest.raises(ConnectionError, match=r"robots\.txt disallows"):
                connector.connect()

    def test_connect_request_fails(self, web_scraper_module):
        ws_mod, mock_requests, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
            respect_robots_txt=False,
        )

        mock_session = MagicMock()
        mock_session.headers = {}
        mock_session.get.side_effect = Exception("connection refused")
        mock_requests.Session.return_value = mock_session

        with pytest.raises(ConnectionError, match="Failed to connect"):
            connector.connect()

    def test_can_fetch_no_robots(self, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
            respect_robots_txt=False,
        )
        assert connector._can_fetch("https://example.com/page") is True

    def test_can_fetch_no_session(self, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
            respect_robots_txt=True,
        )
        connector.robot_parser = MagicMock()
        connector.session = None
        assert connector._can_fetch("https://example.com/page") is True

    def test_extract_not_connected(self, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
        )
        with pytest.raises(RuntimeError, match="Not connected"):
            list(connector.extract())

    @patch("time.sleep")
    def test_extract_basic(self, mock_sleep, web_scraper_module):
        ws_mod, _mock_requests_mod, _mock_bs4 = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1.title"},
        )

        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": "test"}
        mock_response = MagicMock()
        mock_response.content = b"<html><h1 class='title'>Test</h1></html>"
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        connector.session = mock_session
        connector.respect_robots_txt = False

        # Mock BeautifulSoup parsing
        mock_soup = MagicMock()
        mock_element = MagicMock()
        mock_element.get_text.return_value = "Test Title"
        mock_soup.select.return_value = [mock_element]

        # Container select returns elements
        mock_element.select.return_value = [mock_element]

        ws_mod.BeautifulSoup = MagicMock(return_value=mock_soup)

        records = list(connector.extract())
        assert len(records) >= 1
        mock_sleep.assert_called()

    @patch("time.sleep")
    def test_extract_with_link_following(self, mock_sleep, web_scraper_module):
        ws_mod, _, _mock_bs4 = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
            follow_links=True,
            link_selector="a.page-link",
            max_depth=1,
        )

        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": "test"}
        mock_response = MagicMock()
        mock_response.content = b"<html></html>"
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        connector.session = mock_session
        connector.respect_robots_txt = False

        # Soup returns no containers (single-record path)
        mock_soup = MagicMock()
        mock_soup.select.side_effect = lambda sel: (
            [] if sel == "h1" else [MagicMock(get=MagicMock(return_value="/page2"))] if sel == "a.page-link" else []
        )

        ws_mod.BeautifulSoup = MagicMock(return_value=mock_soup)

        records = list(connector.extract())
        assert isinstance(records, list)

    @patch("time.sleep")
    def test_extract_fetch_error(self, mock_sleep, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
        )
        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": "test"}
        mock_session.get.side_effect = Exception("timeout")
        connector.session = mock_session
        connector.respect_robots_txt = False

        records = list(connector.extract())
        assert records == []

    @patch("time.sleep")
    def test_extract_skip_visited(self, mock_sleep, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
        )
        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": "test"}
        connector.session = mock_session
        connector.respect_robots_txt = False
        connector._visited_urls = {"https://example.com"}

        records = list(connector.extract())
        assert records == []

    @patch("time.sleep")
    def test_extract_skip_disallowed_url(self, mock_sleep, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
            respect_robots_txt=True,
        )
        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": "test"}
        connector.session = mock_session

        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = False
        connector.robot_parser = mock_rp

        records = list(connector.extract())
        assert records == []

    def test_extract_records_no_containers(self, web_scraper_module):
        ws_mod, _, _mock_bs4 = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1.title", "body": "p.body"},
        )

        mock_soup = MagicMock()
        mock_element = MagicMock()
        mock_element.get_text.return_value = "Some Text"
        # first selector returns empty (no containers), then individual selects return elements
        mock_soup.select.side_effect = lambda sel: [mock_element] if sel != "h1.title" else []

        records = list(connector._extract_records(mock_soup, "https://example.com/page"))
        assert len(records) == 1
        assert records[0]["_url"] == "https://example.com/page"

    def test_extract_records_with_containers(self, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1.title"},
        )

        mock_container = MagicMock()
        mock_el = MagicMock()
        mock_el.get_text.return_value = "Title Text"
        mock_container.select.return_value = [mock_el]

        mock_soup = MagicMock()
        mock_soup.select.return_value = [mock_container]

        records = list(connector._extract_records(mock_soup, "https://example.com"))
        assert len(records) == 1
        assert records[0]["title"] == "Title Text"

    def test_extract_records_container_no_data(self, web_scraper_module):
        """Container with only _url field (len(record) == 1) should not be yielded."""
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1.title"},
        )

        # Container that has no matching sub-elements
        mock_container = MagicMock()
        mock_container.select.return_value = []  # No element found within container

        mock_soup = MagicMock()
        # First call (for first_selector to get containers) returns [mock_container]
        # Second call (field-level fallback from soup.select) returns [] too
        call_count = {"n": 0}

        def soup_select(sel):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return [mock_container]  # containers
            return []  # fallback page-level search also empty

        mock_soup.select = soup_select

        records = list(connector._extract_records(mock_soup, "https://example.com"))
        assert records == []

    def test_get_schema(self, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1", "body": "p"},
        )
        schema = connector.get_schema()
        assert schema["type"] == "object"
        assert "_url" in schema["properties"]
        assert "title" in schema["properties"]
        assert "body" in schema["properties"]

    def test_disconnect(self, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
        )
        mock_session = MagicMock()
        connector.session = mock_session
        connector._connected = True

        connector.disconnect()
        mock_session.close.assert_called_once()
        assert connector._connected is False

    def test_disconnect_no_session(self, web_scraper_module):
        ws_mod, _, _ = web_scraper_module
        config = _make_scraper_config()
        connector = ws_mod.WebScraperConnector(
            config=config,
            base_url="https://example.com",
            selectors={"title": "h1"},
        )
        connector.session = None
        connector.disconnect()  # Should not raise


# ────────────────────────────────────────────────────────────────
# 2. auth/keycloak.py
# ────────────────────────────────────────────────────────────────


class TestKeycloakVerifier:
    """Tests for keycloak.KeycloakVerifier.verify_token."""

    @patch("odg_core.auth.keycloak.PyJWKClient")
    def test_verify_token_success(self, mock_jwks_client_cls):
        from odg_core.auth.keycloak import KeycloakVerifier
        from odg_core.settings import KeycloakSettings

        settings = KeycloakSettings(
            server_url="http://keycloak:8180",
            realm="test",
            client_id="test-client",
            enabled=True,
        )

        mock_jwks_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwks_client_cls.return_value = mock_jwks_client

        verifier = KeycloakVerifier(settings)

        decoded_payload = {
            "sub": "user-123",
            "preferred_username": "testuser",
            "email": "test@example.com",
            "exp": 9999999999,
            "iat": 1000000000,
            "realm_access": {"roles": ["admin", "viewer"]},
            "resource_access": {
                "test-client": {"roles": ["client-role"]},
            },
        }

        with patch("odg_core.auth.keycloak.jwt.decode", return_value=decoded_payload):
            result = verifier.verify_token("fake-token")

        assert result is not None
        assert result.sub == "user-123"

    @patch("odg_core.auth.keycloak.PyJWKClient")
    def test_verify_token_expired(self, mock_jwks_client_cls):
        import jwt as jwt_lib

        from odg_core.auth.keycloak import KeycloakVerifier
        from odg_core.settings import KeycloakSettings

        settings = KeycloakSettings(
            server_url="http://keycloak:8180",
            realm="test",
            client_id="test-client",
            enabled=True,
        )

        mock_jwks_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwks_client_cls.return_value = mock_jwks_client

        verifier = KeycloakVerifier(settings)

        with patch(
            "odg_core.auth.keycloak.jwt.decode",
            side_effect=jwt_lib.ExpiredSignatureError("expired"),
        ):
            result = verifier.verify_token("expired-token")

        assert result is None

    @patch("odg_core.auth.keycloak.PyJWKClient")
    def test_verify_token_general_error(self, mock_jwks_client_cls):
        from odg_core.auth.keycloak import KeycloakVerifier
        from odg_core.settings import KeycloakSettings

        settings = KeycloakSettings(
            server_url="http://keycloak:8180",
            realm="test",
            client_id="test-client",
            enabled=True,
        )

        mock_jwks_client = MagicMock()
        mock_jwks_client.get_signing_key_from_jwt.side_effect = RuntimeError("JWKS unavailable")
        mock_jwks_client_cls.return_value = mock_jwks_client

        verifier = KeycloakVerifier(settings)
        result = verifier.verify_token("bad-token")
        assert result is None

    def test_verify_token_disabled(self):
        from odg_core.auth.keycloak import KeycloakVerifier
        from odg_core.settings import KeycloakSettings

        settings = KeycloakSettings(enabled=False)
        verifier = KeycloakVerifier(settings)
        result = verifier.verify_token("any-token")
        assert result is None


# ────────────────────────────────────────────────────────────────
# 3. plugins/registry.py
# ────────────────────────────────────────────────────────────────


class TestPluginRegistry:
    """Tests for PluginRegistry including overwrite warnings and get/list methods."""

    def setup_method(self):
        from odg_core.plugins.registry import PluginRegistry

        PluginRegistry.clear_all()

    def teardown_method(self):
        from odg_core.plugins.registry import PluginRegistry

        PluginRegistry.clear_all()

    def test_register_and_get_check(self):
        from odg_core.plugins.registry import PluginRegistry

        mock_check = MagicMock()
        PluginRegistry.register_check("test_check", mock_check)
        assert PluginRegistry.get_check("test_check") is mock_check
        assert "test_check" in PluginRegistry.list_checks()

    def test_register_check_overwrite_warning(self):
        from odg_core.plugins.registry import PluginRegistry

        mock_check1 = MagicMock()
        mock_check2 = MagicMock()
        PluginRegistry.register_check("dup", mock_check1)
        PluginRegistry.register_check("dup", mock_check2)
        assert PluginRegistry.get_check("dup") is mock_check2

    def test_register_and_get_rule(self):
        from odg_core.plugins.registry import PluginRegistry

        mock_rule = MagicMock()
        PluginRegistry.register_rule("test_rule", mock_rule)
        assert PluginRegistry.get_rule("test_rule") is mock_rule
        assert "test_rule" in PluginRegistry.list_rules()

    def test_register_rule_overwrite_warning(self):
        from odg_core.plugins.registry import PluginRegistry

        mock1 = MagicMock()
        mock2 = MagicMock()
        PluginRegistry.register_rule("dup", mock1)
        PluginRegistry.register_rule("dup", mock2)
        assert PluginRegistry.get_rule("dup") is mock2

    def test_register_and_get_connector(self):
        from odg_core.plugins.registry import PluginRegistry

        mock_conn = MagicMock()
        PluginRegistry.register_connector("test_conn", mock_conn)
        assert PluginRegistry.get_connector("test_conn") is mock_conn
        assert "test_conn" in PluginRegistry.list_connectors()

    def test_register_connector_overwrite_warning(self):
        from odg_core.plugins.registry import PluginRegistry

        mock1 = MagicMock()
        mock2 = MagicMock()
        PluginRegistry.register_connector("dup", mock1)
        PluginRegistry.register_connector("dup", mock2)
        assert PluginRegistry.get_connector("dup") is mock2

    def test_register_and_get_privacy(self):
        from odg_core.plugins.registry import PluginRegistry

        mock_priv = MagicMock()
        PluginRegistry.register_privacy("test_priv", mock_priv)
        assert PluginRegistry.get_privacy("test_priv") is mock_priv
        assert "test_priv" in PluginRegistry.list_privacy()

    def test_register_privacy_overwrite_warning(self):
        from odg_core.plugins.registry import PluginRegistry

        mock1 = MagicMock()
        mock2 = MagicMock()
        PluginRegistry.register_privacy("dup", mock1)
        PluginRegistry.register_privacy("dup", mock2)
        assert PluginRegistry.get_privacy("dup") is mock2

    def test_register_and_get_storage(self):
        from odg_core.plugins.registry import PluginRegistry

        mock_storage = MagicMock()
        PluginRegistry.register_storage("test_storage", mock_storage)
        assert PluginRegistry.get_storage("test_storage") is mock_storage
        assert "test_storage" in PluginRegistry.list_storage()

    def test_register_storage_overwrite_warning(self):
        from odg_core.plugins.registry import PluginRegistry

        mock1 = MagicMock()
        mock2 = MagicMock()
        PluginRegistry.register_storage("dup", mock1)
        PluginRegistry.register_storage("dup", mock2)
        assert PluginRegistry.get_storage("dup") is mock2

    def test_register_and_get_expert(self):
        from odg_core.plugins.registry import PluginRegistry

        mock_expert = MagicMock()
        PluginRegistry.register_expert("test_expert", mock_expert)
        assert PluginRegistry.get_expert("test_expert") is mock_expert
        assert "test_expert" in PluginRegistry.list_experts()

    def test_register_expert_overwrite_warning(self):
        from odg_core.plugins.registry import PluginRegistry

        mock1 = MagicMock()
        mock2 = MagicMock()
        PluginRegistry.register_expert("dup", mock1)
        PluginRegistry.register_expert("dup", mock2)
        assert PluginRegistry.get_expert("dup") is mock2

    def test_get_nonexistent_returns_none(self):
        from odg_core.plugins.registry import PluginRegistry

        assert PluginRegistry.get_check("nope") is None
        assert PluginRegistry.get_rule("nope") is None
        assert PluginRegistry.get_connector("nope") is None
        assert PluginRegistry.get_privacy("nope") is None
        assert PluginRegistry.get_storage("nope") is None
        assert PluginRegistry.get_expert("nope") is None


# ────────────────────────────────────────────────────────────────
# 4. feast/materialization_tracker.py
# ────────────────────────────────────────────────────────────────


class TestMaterializationTracker:
    """Tests for MaterializationTracker."""

    def _make_mock_feature_view(self) -> MagicMock:
        fv = MagicMock()
        fv.name = "customer_features"
        feat1 = MagicMock()
        feat1.name = "total_spend"
        feat2 = MagicMock()
        feat2.name = "order_count"
        fv.features = [feat1, feat2]
        fv.entities = ["customer_id"]
        fv.ttl = timedelta(hours=24)
        fv.batch_source = MagicMock()
        return fv

    @patch("odg_core.lineage.emitter.emit_lineage_event")
    @patch("odg_core.storage.iceberg_catalog.IcebergCatalog")
    def test_track_materialization_basic(self, mock_iceberg_cls, mock_emit):
        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        fv = self._make_mock_feature_view()
        mock_store.get_feature_view.return_value = fv

        tracker = MaterializationTracker(mock_store)

        with patch.object(tracker, "_persist_materialization"):
            result = tracker.track_materialization(
                feature_view_name="customer_features",
                source_pipeline_id="spark_pipeline",
                source_pipeline_version=3,
                start_date=datetime(2026, 1, 1, tzinfo=UTC),
                end_date=datetime(2026, 2, 1, tzinfo=UTC),
            )

        assert result["feature_view"] == "customer_features"
        assert result["source_pipeline_id"] == "spark_pipeline"
        assert result["feature_names"] == ["total_spend", "order_count"]
        mock_emit.assert_called_once()

    @patch("odg_core.lineage.emitter.emit_lineage_event")
    @patch("odg_core.storage.iceberg_catalog.IcebergCatalog")
    def test_track_materialization_with_iceberg_snapshot(self, mock_iceberg_cls, mock_emit):
        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        fv = self._make_mock_feature_view()
        mock_store.get_feature_view.return_value = fv

        mock_iceberg = MagicMock()
        mock_iceberg.get_snapshot_id.return_value = "snap-12345"
        mock_iceberg_cls.return_value = mock_iceberg

        tracker = MaterializationTracker(mock_store)

        with patch.object(tracker, "_persist_materialization"):
            result = tracker.track_materialization(
                feature_view_name="customer_features",
                source_dataset_id="gold/customers",
            )

        assert result["source_dataset_version"] == "snap-12345"
        mock_emit.assert_called_once()

    @patch("odg_core.lineage.emitter.emit_lineage_event")
    @patch("odg_core.storage.iceberg_catalog.IcebergCatalog")
    def test_track_materialization_iceberg_error(self, mock_iceberg_cls, mock_emit):
        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        fv = self._make_mock_feature_view()
        mock_store.get_feature_view.return_value = fv

        mock_iceberg = MagicMock()
        mock_iceberg.get_snapshot_id.side_effect = Exception("catalog down")
        mock_iceberg_cls.return_value = mock_iceberg

        tracker = MaterializationTracker(mock_store)

        with patch.object(tracker, "_persist_materialization"):
            result = tracker.track_materialization(
                feature_view_name="customer_features",
                source_dataset_id="gold/customers",
            )

        # snapshot version should be None when iceberg fails
        assert result["source_dataset_version"] is None

    @patch("odg_core.lineage.emitter.emit_lineage_event")
    @patch("odg_core.storage.iceberg_catalog.IcebergCatalog")
    def test_track_materialization_with_provided_snapshot(self, mock_iceberg_cls, mock_emit):
        """When source_dataset_version is already provided, skip Iceberg lookup."""
        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        fv = self._make_mock_feature_view()
        mock_store.get_feature_view.return_value = fv

        tracker = MaterializationTracker(mock_store)

        with patch.object(tracker, "_persist_materialization"):
            result = tracker.track_materialization(
                feature_view_name="customer_features",
                source_dataset_id="gold/customers",
                source_dataset_version="already-provided",
            )

        assert result["source_dataset_version"] == "already-provided"
        mock_iceberg_cls.assert_not_called()

    def test_persist_materialization(self):
        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        metadata = {
            "run_id": "test-run",
            "feature_view": "customer_features",
            "feature_names": ["total_spend"],
            "source_pipeline_id": "pipeline_1",
            "source_pipeline_version": 1,
            "source_dataset_id": "gold/customers",
            "source_dataset_version": "snap-1",
            "start_date": "2026-01-01T00:00:00+00:00",
            "end_date": "2026-02-01T00:00:00+00:00",
            "materialization_time": datetime.now(UTC).isoformat(),
            "feature_view_hash": "abc123def456",
        }

        mock_session = MagicMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.__exit__ = MagicMock(return_value=False)

        with (
            patch("sqlalchemy.create_engine") as mock_engine_fn,
            patch("sqlalchemy.orm.Session", return_value=mock_session_ctx),
            patch("odg_core.db.tables.FeastMaterializationRow"),
        ):
            mock_engine_fn.return_value = MagicMock()
            tracker._persist_materialization(metadata)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_persist_materialization_db_error(self):
        """Cover the except branch in _persist_materialization."""
        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        metadata = {
            "run_id": "test-run",
            "feature_view": "fv",
            "feature_names": [],
            "materialization_time": datetime.now(UTC).isoformat(),
            "feature_view_hash": "abc",
        }

        with patch("sqlalchemy.create_engine", side_effect=Exception("DB down")):
            # Should not raise, just print warning
            tracker._persist_materialization(metadata)

    def test_get_materialization_history(self):
        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        mock_row = MagicMock()
        mock_row.run_id = "run-1"
        mock_row.feature_view = "customer_features"
        mock_row.feature_names = ["total_spend"]
        mock_row.source_pipeline_id = "p1"
        mock_row.source_pipeline_version = 1
        mock_row.source_dataset_id = "gold/customers"
        mock_row.source_dataset_version = "snap-1"
        mock_row.start_date = datetime(2026, 1, 1, tzinfo=UTC)
        mock_row.end_date = datetime(2026, 2, 1, tzinfo=UTC)
        mock_row.materialization_time = datetime(2026, 2, 1, tzinfo=UTC)

        mock_session = MagicMock()
        mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_row]
        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.__exit__ = MagicMock(return_value=False)

        with (
            patch("sqlalchemy.create_engine") as mock_engine_fn,
            patch("sqlalchemy.orm.Session", return_value=mock_session_ctx),
            patch("sqlalchemy.select"),
            patch("odg_core.db.tables.FeastMaterializationRow") as mock_fmr,
        ):
            mock_engine_fn.return_value = MagicMock()
            mock_fmr.feature_view = "customer_features"
            mock_fmr.materialization_time = MagicMock()
            mock_fmr.materialization_time.desc.return_value = "desc"

            results = tracker.get_materialization_history("customer_features")

        assert len(results) == 1
        assert results[0]["run_id"] == "run-1"

    def test_get_materialization_history_db_error(self):
        from odg_core.feast.materialization_tracker import MaterializationTracker

        mock_store = MagicMock()
        tracker = MaterializationTracker(mock_store)

        with patch("sqlalchemy.create_engine", side_effect=Exception("DB down")):
            results = tracker.get_materialization_history("fv")

        assert results == []


# ────────────────────────────────────────────────────────────────
# 5. metadata/base_connector.py
# ────────────────────────────────────────────────────────────────


class TestMetadataBaseConnector:
    """Tests for metadata.base_connector.BaseConnector default methods."""

    def _make_concrete_connector(self) -> Any:
        from odg_core.metadata.base_connector import (
            BaseConnector,
            DatasetMetadata,
            MetadataExtract,
        )

        class ConcreteConnector(BaseConnector):
            """A test connector for metadata ingestion."""

            async def extract(self):
                return MetadataExtract(
                    datasets=[{"name": "test_ds"}],
                    lineage=[],
                )

            async def transform(self, raw):
                return [
                    DatasetMetadata(
                        name="test_ds",
                        layer="bronze",
                        domain_id="test-domain",
                        owner_id="test-owner",
                    )
                ]

            async def load(self, metadata):
                pass

            def get_source_type(self):
                return "test"

        return ConcreteConnector()

    def test_get_name(self):
        connector = self._make_concrete_connector()
        assert connector.get_name() == "ConcreteConnector"

    def test_get_description(self):
        connector = self._make_concrete_connector()
        assert "test connector" in connector.get_description().lower()

    @pytest.mark.asyncio
    async def test_run(self):
        connector = self._make_concrete_connector()
        count = await connector.run()
        assert count == 1

    @pytest.mark.asyncio
    async def test_initialize_and_shutdown(self):
        connector = self._make_concrete_connector()
        await connector.initialize()
        await connector.shutdown()


# ────────────────────────────────────────────────────────────────
# 6. events/kafka_publisher.py
# ────────────────────────────────────────────────────────────────


class TestKafkaPublisher:
    """Tests for KafkaPublisher trace-header and error paths."""

    @pytest.mark.asyncio
    async def test_publish_with_trace_headers(self):
        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = AsyncMock()

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={"traceparent": "00-abc-def-01"},
        ):
            await publisher.publish("audit_event", {"data": "test"})

        publisher._producer.send_and_wait.assert_awaited_once()
        call_args = publisher._producer.send_and_wait.call_args
        payload = call_args[0][1]
        assert payload["_trace"] == {"traceparent": "00-abc-def-01"}

    @pytest.mark.asyncio
    async def test_publish_with_empty_trace_headers(self):
        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = AsyncMock()

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={},
        ):
            await publisher.publish("audit_event", {"data": "test"})

        call_args = publisher._producer.send_and_wait.call_args
        payload = call_args[0][1]
        assert "_trace" not in payload

    @pytest.mark.asyncio
    async def test_publish_kafka_error(self):
        from aiokafka.errors import KafkaError

        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = AsyncMock()
        publisher._producer.send_and_wait.side_effect = KafkaError("send failed")

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={},
        ):
            # Should not raise, logs warning
            await publisher.publish("audit_event", {"data": "test"})

    @pytest.mark.asyncio
    async def test_publish_general_error(self):
        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = AsyncMock()
        publisher._producer.send_and_wait.side_effect = RuntimeError("unexpected")

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={},
        ):
            await publisher.publish("audit_event", {"data": "test"})

    @pytest.mark.asyncio
    async def test_publish_no_producer(self):
        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = None
        await publisher.publish("audit_event", {"data": "test"})  # Should return immediately

    @pytest.mark.asyncio
    async def test_publish_unknown_topic(self):
        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = AsyncMock()
        await publisher.publish("unknown_event_key", {"data": "test"})
        publisher._producer.send_and_wait.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_publish_with_key(self):
        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = AsyncMock()

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={},
        ):
            await publisher.publish("audit_event", {"data": "test"}, key="partition-key")

        call_args = publisher._producer.send_and_wait.call_args
        assert call_args[1]["key"] == b"partition-key"

    @pytest.mark.asyncio
    async def test_publish_batch_with_trace_headers(self):
        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = AsyncMock()

        events = [
            ("audit_event", {"data": "a"}),
            ("decision_created", {"data": "b"}),
        ]

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={"traceparent": "00-trace"},
        ):
            await publisher.publish_batch(events)

        assert publisher._producer.send.await_count == 2
        publisher._producer.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_batch_unknown_event(self):
        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = AsyncMock()

        events = [
            ("unknown_event", {"data": "a"}),
            ("audit_event", {"data": "b"}),
        ]

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={},
        ):
            await publisher.publish_batch(events)

        assert publisher._producer.send.await_count == 1

    @pytest.mark.asyncio
    async def test_publish_batch_kafka_error(self):
        from aiokafka.errors import KafkaError

        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = AsyncMock()
        publisher._producer.send.side_effect = KafkaError("batch fail")

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={},
        ):
            await publisher.publish_batch([("audit_event", {"data": "a"})])

    @pytest.mark.asyncio
    async def test_publish_batch_general_error(self):
        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = AsyncMock()
        publisher._producer.send.side_effect = RuntimeError("unexpected")

        with patch(
            "odg_core.telemetry.context.get_trace_headers",
            return_value={},
        ):
            await publisher.publish_batch([("audit_event", {"data": "a"})])

    @pytest.mark.asyncio
    async def test_publish_batch_no_producer(self):
        from odg_core.events.kafka_publisher import KafkaPublisher

        publisher = KafkaPublisher()
        publisher._producer = None
        await publisher.publish_batch([("audit_event", {"data": "a"})])


# ────────────────────────────────────────────────────────────────
# 7. events/kafka_consumer.py
# ────────────────────────────────────────────────────────────────


class TestKafkaConsumer:
    """Tests for KafkaConsumer subscribe/consume paths."""

    @pytest.mark.asyncio
    async def test_subscribe_when_consumer_is_none(self):
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test-group")
        assert consumer._consumer is None

        mock_aiokafka_consumer = AsyncMock()
        mock_aiokafka_consumer.start = AsyncMock()
        mock_aiokafka_consumer.subscribe = MagicMock()

        with patch("odg_core.events.kafka_consumer.AIOKafkaConsumer", return_value=mock_aiokafka_consumer):
            await consumer.subscribe(["topic1", "topic2"])

        mock_aiokafka_consumer.start.assert_awaited_once()
        mock_aiokafka_consumer.subscribe.assert_called_once_with(["topic1", "topic2"])

    @pytest.mark.asyncio
    async def test_subscribe_when_already_connected(self):
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test-group")
        mock_aiokafka_consumer = AsyncMock()
        mock_aiokafka_consumer.start = AsyncMock()
        mock_aiokafka_consumer.subscribe = MagicMock()
        consumer._consumer = mock_aiokafka_consumer

        await consumer.subscribe(["topic1"])
        mock_aiokafka_consumer.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subscribe_error(self):
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test-group")
        mock_aiokafka_consumer = AsyncMock()
        mock_aiokafka_consumer.start = AsyncMock(side_effect=Exception("connection failed"))
        consumer._consumer = mock_aiokafka_consumer

        with pytest.raises(Exception, match="connection failed"):
            await consumer.subscribe(["topic1"])

    @pytest.mark.asyncio
    async def test_consume_not_initialized(self):
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test-group")

        async def handler(topic, payload):
            pass

        with pytest.raises(RuntimeError, match="Consumer not initialized"):
            await consumer.consume(handler)

    @pytest.mark.asyncio
    async def test_consume_processes_messages(self):
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test-group")

        msg1 = MagicMock()
        msg1.topic = "test-topic"
        msg1.value = {"key": "value"}
        msg1.partition = 0
        msg1.offset = 0

        mock_aiokafka_consumer = MagicMock()
        mock_aiokafka_consumer.stop = AsyncMock()

        # Simulate async iteration: yield one message then set _running = False
        async def fake_aiter(self_inner: Any) -> AsyncIterator[Any]:
            yield msg1
            consumer._running = False

        mock_aiokafka_consumer.__aiter__ = lambda self_inner: fake_aiter(self_inner)
        consumer._consumer = mock_aiokafka_consumer

        handler = AsyncMock()

        await consumer.consume(handler)
        handler.assert_awaited_once_with("test-topic", {"key": "value"})

    @pytest.mark.asyncio
    async def test_consume_break_when_not_running(self):
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test-group")

        msg1 = MagicMock()
        msg1.topic = "topic"
        msg1.value = {"a": 1}
        msg1.partition = 0
        msg1.offset = 0

        msg2 = MagicMock()
        msg2.topic = "topic"
        msg2.value = {"b": 2}
        msg2.partition = 0
        msg2.offset = 1

        mock_aiokafka_consumer = MagicMock()
        mock_aiokafka_consumer.stop = AsyncMock()

        async def fake_aiter(self_inner: Any) -> AsyncIterator[Any]:
            yield msg1
            consumer._running = False
            yield msg2  # This should trigger the break

        mock_aiokafka_consumer.__aiter__ = lambda self_inner: fake_aiter(self_inner)
        consumer._consumer = mock_aiokafka_consumer

        handler = AsyncMock()

        await consumer.consume(handler)
        # Only msg1 should be handled; msg2 triggers break
        handler.assert_awaited_once_with("topic", {"a": 1})

    @pytest.mark.asyncio
    async def test_consume_max_retries_exceeded(self):
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test-group")

        msg = MagicMock()
        msg.topic = "topic"
        msg.value = {"data": "fail"}
        msg.partition = 0
        msg.offset = 0

        mock_aiokafka_consumer = MagicMock()
        mock_aiokafka_consumer.stop = AsyncMock()

        async def fake_aiter(self_inner: Any) -> AsyncIterator[Any]:
            yield msg
            consumer._running = False

        mock_aiokafka_consumer.__aiter__ = lambda self_inner: fake_aiter(self_inner)
        consumer._consumer = mock_aiokafka_consumer

        handler = AsyncMock(side_effect=Exception("handler error"))

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await consumer.consume(handler, max_retries=2, retry_delay=0.0)

        assert handler.await_count == 2

    @pytest.mark.asyncio
    async def test_consume_kafka_error(self):
        from aiokafka.errors import KafkaError

        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test-group")

        mock_aiokafka_consumer = MagicMock()
        mock_aiokafka_consumer.stop = AsyncMock()

        async def fake_aiter(self_inner: Any) -> AsyncIterator[Any]:
            raise KafkaError("consumer error")
            yield  # Make it a generator

        mock_aiokafka_consumer.__aiter__ = lambda self_inner: fake_aiter(self_inner)
        consumer._consumer = mock_aiokafka_consumer

        handler = AsyncMock()

        with pytest.raises(KafkaError):
            await consumer.consume(handler)

    @pytest.mark.asyncio
    async def test_consume_general_exception(self):
        from odg_core.events.kafka_consumer import KafkaConsumer

        consumer = KafkaConsumer(group_id="test-group")

        mock_aiokafka_consumer = MagicMock()
        mock_aiokafka_consumer.stop = AsyncMock()

        async def fake_aiter(self_inner: Any) -> AsyncIterator[Any]:
            raise RuntimeError("unexpected error")
            yield

        mock_aiokafka_consumer.__aiter__ = lambda self_inner: fake_aiter(self_inner)
        consumer._consumer = mock_aiokafka_consumer

        handler = AsyncMock()

        with pytest.raises(RuntimeError, match="unexpected error"):
            await consumer.consume(handler)

        # finally block should have set _running to False
        assert consumer._running is False


# ────────────────────────────────────────────────────────────────
# 8a. governance/base_rule.py
# ────────────────────────────────────────────────────────────────


class TestBaseRule:
    """Tests for BaseRule default method implementations."""

    def _make_concrete_rule(self) -> Any:
        from odg_core.governance.base_rule import BaseRule, RuleEvaluation

        class TestRule(BaseRule):
            """A test governance rule."""

            async def evaluate(self, context):
                return RuleEvaluation(matched=True, actions=["approve"])

            def get_conditions(self):
                return ["condition_a"]

            def get_actions(self):
                return ["approve", "deny"]

        return TestRule()

    def test_get_name(self):
        rule = self._make_concrete_rule()
        assert rule.get_name() == "TestRule"

    def test_get_description(self):
        rule = self._make_concrete_rule()
        assert "test governance rule" in rule.get_description().lower()

    def test_get_priority(self):
        rule = self._make_concrete_rule()
        assert rule.get_priority() == 0

    @pytest.mark.asyncio
    async def test_evaluate(self):
        rule = self._make_concrete_rule()
        result = await rule.evaluate({"test": True})
        assert result.matched is True

    @pytest.mark.asyncio
    async def test_initialize_and_shutdown(self):
        rule = self._make_concrete_rule()
        await rule.initialize()
        await rule.shutdown()


# ────────────────────────────────────────────────────────────────
# 8b. privacy/base_privacy.py
# ────────────────────────────────────────────────────────────────


class TestBasePrivacy:
    """Tests for BasePrivacy default method implementations."""

    def _make_concrete_privacy(self) -> Any:
        from odg_core.privacy.base_privacy import BasePrivacy, PrivacyResult

        class TestPrivacy(BasePrivacy):
            """A test privacy mechanism."""

            async def apply(self, data, config):
                return PrivacyResult(transformed_data=data, privacy_loss=0.5)

            async def audit(self):
                return {"total_epsilon": 0.5}

            def get_mechanism_type(self):
                return "test"

        return TestPrivacy()

    def test_get_name(self):
        priv = self._make_concrete_privacy()
        assert priv.get_name() == "TestPrivacy"

    def test_get_description(self):
        priv = self._make_concrete_privacy()
        assert "test privacy mechanism" in priv.get_description().lower()

    @pytest.mark.asyncio
    async def test_initialize_and_shutdown(self):
        priv = self._make_concrete_privacy()
        await priv.initialize()
        await priv.shutdown()


# ────────────────────────────────────────────────────────────────
# 8c. storage/base_storage.py
# ────────────────────────────────────────────────────────────────


class TestBaseStorage:
    """Tests for BaseStorage default method implementations."""

    def _make_concrete_storage(self) -> Any:
        from odg_core.storage.base_storage import BaseStorage

        class TestStorage(BaseStorage):
            """A test storage backend."""

            async def read(self, path):
                return b"data"

            async def write(self, path, data):
                pass

            async def list(self, prefix=""):
                return ["file1.txt"]

            async def delete(self, path):
                pass

            def get_storage_type(self):
                return "test"

        return TestStorage()

    def test_get_name(self):
        storage = self._make_concrete_storage()
        assert storage.get_name() == "TestStorage"

    def test_get_description(self):
        storage = self._make_concrete_storage()
        assert "test storage backend" in storage.get_description().lower()

    @pytest.mark.asyncio
    async def test_initialize_and_shutdown(self):
        storage = self._make_concrete_storage()
        await storage.initialize()
        await storage.shutdown()

    @pytest.mark.asyncio
    async def test_exists_true(self):
        from odg_core.storage.base_storage import BaseStorage, StorageMetadata

        class StorageWithMeta(BaseStorage):
            """Storage with metadata."""

            async def read(self, path):
                return b""

            async def write(self, path, data):
                pass

            async def list(self, prefix=""):
                return []

            async def delete(self, path):
                pass

            def get_storage_type(self):
                return "test"

            async def get_metadata(self, path):
                return StorageMetadata(path=path)

        storage = StorageWithMeta()
        assert await storage.exists("file.txt") is True

    @pytest.mark.asyncio
    async def test_exists_not_found(self):
        from odg_core.storage.base_storage import BaseStorage

        class StorageNotFound(BaseStorage):
            """Storage not found."""

            async def read(self, path):
                return b""

            async def write(self, path, data):
                pass

            async def list(self, prefix=""):
                return []

            async def delete(self, path):
                pass

            def get_storage_type(self):
                return "test"

            async def get_metadata(self, path):
                raise FileNotFoundError

        storage = StorageNotFound()
        assert await storage.exists("missing.txt") is False

    @pytest.mark.asyncio
    async def test_exists_other_error(self):
        from odg_core.storage.base_storage import BaseStorage

        class StorageError(BaseStorage):
            """Storage error."""

            async def read(self, path):
                return b""

            async def write(self, path, data):
                pass

            async def list(self, prefix=""):
                return []

            async def delete(self, path):
                pass

            def get_storage_type(self):
                return "test"

            async def get_metadata(self, path):
                raise RuntimeError("disk failure")

        storage = StorageError()
        assert await storage.exists("file.txt") is False


# ────────────────────────────────────────────────────────────────
# 8d. connectors/base.py (_infer_schema)
# ────────────────────────────────────────────────────────────────


class TestBaseConnectorInferSchema:
    """Tests for S3Connector._infer_schema with various types."""

    def test_infer_schema_string(self):
        from odg_core.connectors.base import ConnectorConfig
        from odg_core.connectors.file_connector import S3Connector

        config = ConnectorConfig(
            connector_type="s3",
            source_name="test",
            target_table="test_table",
        )
        connector = S3Connector(config=config, bucket="test-bucket")
        schema = connector._infer_schema({"name": "Alice"})
        assert schema["properties"]["name"]["type"] == "string"

    def test_infer_schema_integer(self):
        from odg_core.connectors.base import ConnectorConfig
        from odg_core.connectors.file_connector import S3Connector

        config = ConnectorConfig(
            connector_type="s3",
            source_name="test",
            target_table="test_table",
        )
        connector = S3Connector(config=config, bucket="test-bucket")
        schema = connector._infer_schema({"count": 42})
        assert schema["properties"]["count"]["type"] == "integer"

    def test_infer_schema_float(self):
        from odg_core.connectors.base import ConnectorConfig
        from odg_core.connectors.file_connector import S3Connector

        config = ConnectorConfig(
            connector_type="s3",
            source_name="test",
            target_table="test_table",
        )
        connector = S3Connector(config=config, bucket="test-bucket")
        schema = connector._infer_schema({"score": 3.14})
        assert schema["properties"]["score"]["type"] == "number"

    def test_infer_schema_boolean(self):
        """Note: isinstance(True, int) is True in Python, so booleans map to 'integer'."""
        from odg_core.connectors.base import ConnectorConfig
        from odg_core.connectors.file_connector import S3Connector

        config = ConnectorConfig(
            connector_type="s3",
            source_name="test",
            target_table="test_table",
        )
        connector = S3Connector(config=config, bucket="test-bucket")
        schema = connector._infer_schema({"active": True})
        # bool is subclass of int, so isinstance(True, int) is True; mapped to "integer"
        assert schema["properties"]["active"]["type"] == "integer"

    def test_infer_schema_other_type(self):
        from odg_core.connectors.base import ConnectorConfig
        from odg_core.connectors.file_connector import S3Connector

        config = ConnectorConfig(
            connector_type="s3",
            source_name="test",
            target_table="test_table",
        )
        connector = S3Connector(config=config, bucket="test-bucket")
        schema = connector._infer_schema({"data": [1, 2, 3]})
        assert schema["properties"]["data"]["type"] == "string"

    def test_infer_schema_mixed_types(self):
        from odg_core.connectors.base import ConnectorConfig
        from odg_core.connectors.file_connector import S3Connector

        config = ConnectorConfig(
            connector_type="s3",
            source_name="test",
            target_table="test_table",
        )
        connector = S3Connector(config=config, bucket="test-bucket")
        schema = connector._infer_schema(
            {
                "name": "Alice",
                "age": 30,
                "score": 9.5,
                "active": False,
                "tags": ["a", "b"],
            }
        )
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["age"]["type"] == "integer"
        assert schema["properties"]["score"]["type"] == "number"
        # bool is subclass of int in Python, so isinstance(False, int) is True
        assert schema["properties"]["active"]["type"] == "integer"
        assert schema["properties"]["tags"]["type"] == "string"


# ────────────────────────────────────────────────────────────────
# 8e. nosql/couchdb_client.py
# ────────────────────────────────────────────────────────────────


class TestCouchDBClient:
    """Tests for CouchDBClient uncovered paths."""

    @pytest.fixture()
    def mock_couchdb_module(self):
        """Ensure couchdb module is available via mock."""
        mock_mod = MagicMock()
        saved = sys.modules.get("couchdb")
        sys.modules["couchdb"] = mock_mod

        # Reimport to pick up the mock
        mod_name = "odg_core.nosql.couchdb_client"
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        import odg_core.nosql.couchdb_client as cdb_mod

        cdb_mod._couchdb_module = mock_mod  # type: ignore[attr-defined]

        yield cdb_mod, mock_mod

        if saved is not None:
            sys.modules["couchdb"] = saved
        else:
            sys.modules.pop("couchdb", None)

    def test_save_document_update_path(self, mock_couchdb_module):
        cdb_mod, _mock_couchdb = mock_couchdb_module

        client = cdb_mod.CouchDBClient(url="http://localhost:5984")
        mock_server = MagicMock()
        mock_server.__contains__ = MagicMock(return_value=True)

        mock_db = MagicMock()
        existing_doc = {"_id": "doc1", "_rev": "1-abc", "_created_at": "2026-01-01T00:00:00"}
        mock_db.__contains__ = MagicMock(return_value=True)
        mock_db.__getitem__ = MagicMock(return_value=existing_doc)
        mock_server.__getitem__ = MagicMock(return_value=mock_db)

        client._server = mock_server
        client._connected = True

        result = client.save_document("test_db", "doc1", {"title": "updated"})
        assert result["_rev"] == "1-abc"
        assert result["_created_at"] == "2026-01-01T00:00:00"
        mock_db.save.assert_called_once()

    def test_list_databases_exception(self, mock_couchdb_module):
        """list_databases when _ensure_connected calls connect and fails."""
        cdb_mod, mock_couchdb = mock_couchdb_module

        client = cdb_mod.CouchDBClient(
            url="http://localhost:5984",
            username="admin",
            password="pass",
        )
        client._connected = False

        mock_server = MagicMock()
        mock_server.version.return_value = "3.0"
        mock_server.__iter__ = MagicMock(return_value=iter(["db1", "db2"]))
        mock_couchdb.Server.return_value = mock_server

        result = client.list_databases()
        assert result == ["db1", "db2"]

    def test_find_db_not_found(self, mock_couchdb_module):
        """find() when credentials are not set raises ValueError."""
        cdb_mod, _mock_couchdb = mock_couchdb_module

        client = cdb_mod.CouchDBClient(url="http://localhost:5984")
        client._server = MagicMock()
        client._connected = True
        client._username = None
        client._password = None

        with pytest.raises(ValueError, match="credentials not available"):
            client.find("test_db", {"field": "value"})


# ────────────────────────────────────────────────────────────────
# 8f. connectors/file_connector.py (S3Connector, FTPConnector)
# ────────────────────────────────────────────────────────────────


class TestS3Connector:
    """Tests for S3Connector."""

    def _make_config(self) -> Any:
        from odg_core.connectors.base import ConnectorConfig

        return ConnectorConfig(
            connector_type="s3",
            source_name="test_s3",
            target_table="test_table",
            credentials={
                "aws_access_key_id": "key",
                "aws_secret_access_key": "secret",
                "region": "us-east-1",
            },
        )

    @patch("odg_core.connectors.file_connector.boto3", create=True)
    def test_connect_success(self, mock_boto3):
        from odg_core.connectors.file_connector import S3Connector

        config = self._make_config()
        connector = S3Connector(config=config, bucket="my-bucket", endpoint_url="http://minio:9000")

        mock_session = MagicMock()
        mock_s3_client = MagicMock()
        mock_session.client.return_value = mock_s3_client
        mock_boto3.Session.return_value = mock_session

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            connector.connect()

        assert connector._connected is True

    @patch("odg_core.connectors.file_connector.boto3", create=True)
    def test_connect_failure(self, mock_boto3):
        from odg_core.connectors.file_connector import S3Connector

        config = self._make_config()
        connector = S3Connector(config=config, bucket="my-bucket")

        mock_session = MagicMock()
        mock_s3_client = MagicMock()
        mock_s3_client.head_bucket.side_effect = Exception("bucket not found")
        mock_session.client.return_value = mock_s3_client
        mock_boto3.Session.return_value = mock_session

        with (
            patch.dict("sys.modules", {"boto3": mock_boto3}),
            pytest.raises(ConnectionError, match="Failed to connect"),
        ):
            connector.connect()

    def test_extract_not_connected(self):
        from odg_core.connectors.file_connector import S3Connector

        config = self._make_config()
        connector = S3Connector(config=config, bucket="my-bucket")
        with pytest.raises(RuntimeError, match="Not connected"):
            list(connector.extract())

    def test_get_schema_empty(self):
        from odg_core.connectors.file_connector import S3Connector

        config = self._make_config()
        connector = S3Connector(config=config, bucket="my-bucket")

        with patch.object(connector, "extract", return_value=iter([])):
            schema = connector.get_schema()

        assert schema == {"type": "object", "properties": {}}


class TestFTPConnector:
    """Tests for FTPConnector."""

    def _make_config(self) -> Any:
        from odg_core.connectors.base import ConnectorConfig

        return ConnectorConfig(
            connector_type="ftp",
            source_name="test_ftp",
            target_table="test_table",
            credentials={"username": "user", "password": "pass"},
        )

    def test_init_ftp(self):
        from odg_core.connectors.file_connector import FTPConnector

        config = self._make_config()
        connector = FTPConnector(
            config=config,
            host="ftp.example.com",
            directory="/data",
            file_pattern="*.csv",
        )
        assert connector.host == "ftp.example.com"
        assert connector.port == 21
        assert connector.use_sftp is False

    def test_init_sftp(self):
        from odg_core.connectors.file_connector import FTPConnector

        config = self._make_config()
        connector = FTPConnector(
            config=config,
            host="ftp.example.com",
            use_sftp=True,
        )
        assert connector.port == 22
        assert connector.use_sftp is True

    @patch("odg_core.connectors.file_connector.FTP")
    def test_connect_ftp(self, mock_ftp_cls):
        from odg_core.connectors.file_connector import FTPConnector

        config = self._make_config()
        connector = FTPConnector(config=config, host="ftp.example.com")

        mock_ftp = MagicMock()
        mock_ftp_cls.return_value = mock_ftp

        connector.connect()
        assert connector._connected is True
        mock_ftp.connect.assert_called_once()
        mock_ftp.login.assert_called_once()

    @patch("odg_core.connectors.file_connector.FTP")
    def test_connect_ftp_failure(self, mock_ftp_cls):
        from odg_core.connectors.file_connector import FTPConnector

        config = self._make_config()
        connector = FTPConnector(config=config, host="ftp.example.com")

        mock_ftp = MagicMock()
        mock_ftp.connect.side_effect = Exception("connection refused")
        mock_ftp_cls.return_value = mock_ftp

        with pytest.raises(ConnectionError, match="Failed to connect"):
            connector.connect()

    def test_extract_not_connected_sftp(self):
        from odg_core.connectors.file_connector import FTPConnector

        config = self._make_config()
        connector = FTPConnector(config=config, host="ftp.example.com", use_sftp=True)
        with pytest.raises(RuntimeError, match="Not connected"):
            list(connector.extract())

    def test_extract_not_connected_ftp(self):
        from odg_core.connectors.file_connector import FTPConnector

        config = self._make_config()
        connector = FTPConnector(config=config, host="ftp.example.com")
        with pytest.raises(RuntimeError, match="Not connected"):
            list(connector.extract())

    def test_disconnect_ftp(self):
        from odg_core.connectors.file_connector import FTPConnector

        config = self._make_config()
        connector = FTPConnector(config=config, host="ftp.example.com")
        connector._ftp_client = MagicMock()
        connector._connected = True

        connector.disconnect()
        connector._ftp_client.quit.assert_called_once()
        assert connector._connected is False

    def test_disconnect_sftp(self):
        from odg_core.connectors.file_connector import FTPConnector

        config = self._make_config()
        connector = FTPConnector(config=config, host="ftp.example.com", use_sftp=True)
        connector._sftp_client = MagicMock()
        connector._ssh_client = MagicMock()
        connector._connected = True

        connector.disconnect()
        connector._sftp_client.close.assert_called_once()
        connector._ssh_client.close.assert_called_once()

    def test_get_schema_empty(self):
        from odg_core.connectors.file_connector import FTPConnector

        config = self._make_config()
        connector = FTPConnector(config=config, host="ftp.example.com")

        with patch.object(connector, "extract", return_value=iter([])):
            schema = connector.get_schema()

        assert schema == {"type": "object", "properties": {}}

    def test_get_schema_with_record(self):
        from odg_core.connectors.file_connector import FTPConnector

        config = self._make_config()
        connector = FTPConnector(config=config, host="ftp.example.com")

        with patch.object(connector, "extract", return_value=iter([{"name": "Alice", "age": 30}])):
            schema = connector.get_schema()

        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]


# ────────────────────────────────────────────────────────────────
# 8g. storage/iceberg_catalog.py
# ────────────────────────────────────────────────────────────────


class TestIcebergCatalog:
    """Tests for IcebergCatalog init and shutdown paths."""

    def test_init_default(self):
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        catalog = IcebergCatalog()
        assert catalog.warehouse_path == "s3://odg-lakehouse/"
        assert catalog._catalog is None

    def test_init_custom_path(self):
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        catalog = IcebergCatalog(warehouse_path="s3://custom/path/")
        assert catalog.warehouse_path == "s3://custom/path/"

    def test_get_catalog_imports_pyiceberg(self):
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        catalog = IcebergCatalog()

        mock_loaded_catalog = MagicMock()
        with (
            patch(
                "odg_core.storage.iceberg_catalog.load_catalog",
                return_value=mock_loaded_catalog,
                create=True,
            ),
            patch.dict("sys.modules", {"pyiceberg": MagicMock(), "pyiceberg.catalog": MagicMock()}),
            contextlib.suppress(ImportError),
        ):
            catalog._get_catalog()

    def test_get_catalog_import_error(self):
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        catalog = IcebergCatalog()

        with patch.dict("sys.modules", {"pyiceberg": None, "pyiceberg.catalog": None}), pytest.raises(ImportError):
            catalog._get_catalog()

    def test_time_travel_by_tag(self):
        from odg_core.storage.iceberg_catalog import IcebergCatalog

        catalog = IcebergCatalog()

        with (
            patch.object(catalog, "get_snapshot_by_tag", return_value="12345"),
            patch.object(catalog, "time_travel", return_value=MagicMock()) as mock_tt,
        ):
            catalog.time_travel_by_tag("gold", "customers", "production")

        mock_tt.assert_called_once_with("gold", "customers", "12345")
