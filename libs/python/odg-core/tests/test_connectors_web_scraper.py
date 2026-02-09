"""Tests for odg_core.connectors.web_scraper module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# Ensure the web_scraper module accepts init even without real bs4/requests.
import odg_core.connectors.web_scraper as _ws_mod
from odg_core.connectors.base import ConnectorConfig

_ws_mod._HAS_SCRAPING_DEPS = True
from odg_core.connectors.web_scraper import WebScraperConnector  # noqa: E402


@pytest.fixture()
def config() -> ConnectorConfig:
    return ConnectorConfig(connector_type="web_scraper", source_name="test_scraper")


@pytest.fixture()
def selectors() -> dict[str, str]:
    return {"title": "h1.title", "description": "p.desc"}


# ──── get_schema ─────────────────────────────────────────────


class TestWebScraperGetSchema:
    """Tests for schema inference from CSS selectors."""

    def test_schema_includes_url_property(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
        )
        schema = connector.get_schema()
        assert "_url" in schema["properties"]
        assert schema["properties"]["_url"]["type"] == "string"

    def test_schema_includes_selector_fields(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
        )
        schema = connector.get_schema()
        assert "title" in schema["properties"]
        assert "description" in schema["properties"]
        assert schema["properties"]["title"]["type"] == "string"
        assert schema["properties"]["description"]["type"] == "string"

    def test_schema_required_contains_url(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
        )
        schema = connector.get_schema()
        assert "_url" in schema["required"]


# ──── _can_fetch ─────────────────────────────────────────────


class TestWebScraperCanFetch:
    """Tests for robots.txt checking."""

    def test_returns_true_when_robots_not_enabled(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
            respect_robots_txt=False,
        )
        assert connector._can_fetch("http://example.com/page") is True

    def test_returns_true_when_robot_parser_is_none(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
            respect_robots_txt=True,
        )
        # robot_parser is None by default before connect()
        assert connector.robot_parser is None
        assert connector._can_fetch("http://example.com/page") is True

    def test_returns_true_when_session_is_none(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
            respect_robots_txt=True,
        )
        connector.robot_parser = MagicMock()
        # session is None before connect()
        assert connector.session is None
        assert connector._can_fetch("http://example.com/page") is True

    def test_delegates_to_robot_parser(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
            respect_robots_txt=True,
        )
        mock_parser = MagicMock()
        mock_parser.can_fetch.return_value = False
        connector.robot_parser = mock_parser

        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": "TestBot/1.0"}
        connector.session = mock_session

        assert connector._can_fetch("http://example.com/secret") is False
        mock_parser.can_fetch.assert_called_once()


# ──── disconnect ─────────────────────────────────────────────


class TestWebScraperDisconnect:
    """Tests for disconnect behaviour."""

    def test_disconnect_closes_session(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
        )
        mock_session = MagicMock()
        connector.session = mock_session
        connector._connected = True

        connector.disconnect()

        mock_session.close.assert_called_once()
        assert connector._connected is False

    def test_disconnect_without_session(self, config: ConnectorConfig, selectors: dict[str, str]) -> None:
        connector = WebScraperConnector(
            config=config,
            base_url="http://example.com",
            selectors=selectors,
        )
        # Should not raise even without a session
        connector.disconnect()
        assert connector._connected is False
