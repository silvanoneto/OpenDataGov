"""Tests for CDC connector manager module."""

from __future__ import annotations

from unittest.mock import MagicMock, mock_open, patch

import pytest
import requests

from odg_core.cdc.connector_manager import ConnectorManager


@pytest.fixture
def mgr() -> ConnectorManager:
    return ConnectorManager("http://kafka-connect:8083")


class TestConnectorManagerInit:
    def test_default_url(self) -> None:
        m = ConnectorManager()
        assert m.connect_url == "http://localhost:8083"

    def test_custom_url(self, mgr: ConnectorManager) -> None:
        assert mgr.connect_url == "http://kafka-connect:8083"
        assert mgr.base_url == "http://kafka-connect:8083/connectors"

    def test_trailing_slash_stripped(self) -> None:
        m = ConnectorManager("http://host:8083/")
        assert m.connect_url == "http://host:8083"


class TestListConnectors:
    @patch("odg_core.cdc.connector_manager.requests.get")
    def test_list_success(self, mock_get: MagicMock, mgr: ConnectorManager) -> None:
        mock_get.return_value.json.return_value = ["conn-1", "conn-2"]
        mock_get.return_value.raise_for_status = MagicMock()
        result = mgr.list_connectors()
        assert result == ["conn-1", "conn-2"]

    @patch("odg_core.cdc.connector_manager.requests.get")
    def test_list_failure(self, mock_get: MagicMock, mgr: ConnectorManager) -> None:
        mock_get.side_effect = requests.RequestException("fail")
        result = mgr.list_connectors()
        assert result == []


class TestGetConnector:
    @patch("odg_core.cdc.connector_manager.requests.get")
    def test_get_success(self, mock_get: MagicMock, mgr: ConnectorManager) -> None:
        mock_get.return_value.json.return_value = {"name": "conn-1", "config": {}}
        mock_get.return_value.raise_for_status = MagicMock()
        result = mgr.get_connector("conn-1")
        assert result is not None
        assert result["name"] == "conn-1"

    @patch("odg_core.cdc.connector_manager.requests.get")
    def test_get_not_found(self, mock_get: MagicMock, mgr: ConnectorManager) -> None:
        mock_get.side_effect = requests.RequestException("404")
        result = mgr.get_connector("nonexistent")
        assert result is None


class TestGetConnectorStatus:
    @patch("odg_core.cdc.connector_manager.requests.get")
    def test_status_success(self, mock_get: MagicMock, mgr: ConnectorManager) -> None:
        mock_get.return_value.json.return_value = {
            "connector": {"state": "RUNNING"},
            "tasks": [{"state": "RUNNING"}],
        }
        mock_get.return_value.raise_for_status = MagicMock()
        result = mgr.get_connector_status("conn-1")
        assert result is not None
        assert result["connector"]["state"] == "RUNNING"

    @patch("odg_core.cdc.connector_manager.requests.get")
    def test_status_failure(self, mock_get: MagicMock, mgr: ConnectorManager) -> None:
        mock_get.side_effect = requests.RequestException("fail")
        result = mgr.get_connector_status("conn-1")
        assert result is None


class TestCreateConnector:
    @patch("builtins.open", mock_open(read_data='{"name": "test", "config": {}}'))
    @patch("odg_core.cdc.connector_manager.requests.post")
    def test_create_success(self, mock_post: MagicMock, mgr: ConnectorManager) -> None:
        mock_post.return_value.raise_for_status = MagicMock()
        result = mgr.create_connector("/path/to/config.json")
        assert result is True

    def test_create_file_not_found(self, mgr: ConnectorManager) -> None:
        result = mgr.create_connector("/nonexistent/config.json")
        assert result is False

    @patch("builtins.open", mock_open(read_data='{"name": "test", "config": {}}'))
    @patch("odg_core.cdc.connector_manager.requests.post")
    def test_create_request_failure(self, mock_post: MagicMock, mgr: ConnectorManager) -> None:
        mock_post.side_effect = requests.RequestException("fail")
        result = mgr.create_connector("/path/to/config.json")
        assert result is False


class TestUpdateConnector:
    @patch("odg_core.cdc.connector_manager.requests.put")
    def test_update_success(self, mock_put: MagicMock, mgr: ConnectorManager) -> None:
        mock_put.return_value.raise_for_status = MagicMock()
        result = mgr.update_connector("conn-1", {"key": "value"})
        assert result is True

    @patch("odg_core.cdc.connector_manager.requests.put")
    def test_update_failure(self, mock_put: MagicMock, mgr: ConnectorManager) -> None:
        mock_put.side_effect = requests.RequestException("fail")
        result = mgr.update_connector("conn-1", {"key": "value"})
        assert result is False


class TestDeleteConnector:
    @patch("odg_core.cdc.connector_manager.requests.delete")
    def test_delete_success(self, mock_del: MagicMock, mgr: ConnectorManager) -> None:
        mock_del.return_value.raise_for_status = MagicMock()
        result = mgr.delete_connector("conn-1")
        assert result is True

    @patch("odg_core.cdc.connector_manager.requests.delete")
    def test_delete_failure(self, mock_del: MagicMock, mgr: ConnectorManager) -> None:
        mock_del.side_effect = requests.RequestException("fail")
        result = mgr.delete_connector("conn-1")
        assert result is False


class TestPauseResumeRestart:
    @patch("odg_core.cdc.connector_manager.requests.put")
    def test_pause_success(self, mock_put: MagicMock, mgr: ConnectorManager) -> None:
        mock_put.return_value.raise_for_status = MagicMock()
        assert mgr.pause_connector("conn-1") is True

    @patch("odg_core.cdc.connector_manager.requests.put")
    def test_resume_success(self, mock_put: MagicMock, mgr: ConnectorManager) -> None:
        mock_put.return_value.raise_for_status = MagicMock()
        assert mgr.resume_connector("conn-1") is True

    @patch("odg_core.cdc.connector_manager.requests.post")
    def test_restart_success(self, mock_post: MagicMock, mgr: ConnectorManager) -> None:
        mock_post.return_value.raise_for_status = MagicMock()
        assert mgr.restart_connector("conn-1") is True

    @patch("odg_core.cdc.connector_manager.requests.put")
    def test_pause_failure(self, mock_put: MagicMock, mgr: ConnectorManager) -> None:
        mock_put.side_effect = requests.RequestException("fail")
        assert mgr.pause_connector("conn-1") is False

    @patch("odg_core.cdc.connector_manager.requests.put")
    def test_resume_failure(self, mock_put: MagicMock, mgr: ConnectorManager) -> None:
        mock_put.side_effect = requests.RequestException("fail")
        assert mgr.resume_connector("conn-1") is False

    @patch("odg_core.cdc.connector_manager.requests.post")
    def test_restart_failure(self, mock_post: MagicMock, mgr: ConnectorManager) -> None:
        mock_post.side_effect = requests.RequestException("fail")
        assert mgr.restart_connector("conn-1") is False


class TestGetConnectorTopics:
    @patch("odg_core.cdc.connector_manager.requests.get")
    def test_topics_success(self, mock_get: MagicMock, mgr: ConnectorManager) -> None:
        mock_get.return_value.json.return_value = {"conn-1": {"topics": ["topic-a", "topic-b"]}}
        mock_get.return_value.raise_for_status = MagicMock()
        result = mgr.get_connector_topics("conn-1")
        assert result == ["topic-a", "topic-b"]

    @patch("odg_core.cdc.connector_manager.requests.get")
    def test_topics_failure(self, mock_get: MagicMock, mgr: ConnectorManager) -> None:
        mock_get.side_effect = requests.RequestException("fail")
        result = mgr.get_connector_topics("conn-1")
        assert result == []


class TestHealthCheck:
    @patch("odg_core.cdc.connector_manager.requests.get")
    def test_healthy(self, mock_get: MagicMock, mgr: ConnectorManager) -> None:
        mock_get.return_value.raise_for_status = MagicMock()
        assert mgr.health_check() is True

    @patch("odg_core.cdc.connector_manager.requests.get")
    def test_unhealthy(self, mock_get: MagicMock, mgr: ConnectorManager) -> None:
        mock_get.side_effect = requests.RequestException("fail")
        assert mgr.health_check() is False
