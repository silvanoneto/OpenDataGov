"""Tests for odg_core.nosql.couchdb_client module."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Create a mock couchdb module so CouchDBClient can be imported
# without the actual couchdb-python package installed.
_mock_couchdb_module = MagicMock()


@pytest.fixture(autouse=True)
def mock_couchdb_import() -> Any:
    """Ensure the couchdb module is mocked for all tests."""
    from odg_core.nosql import couchdb_client

    with patch.dict(sys.modules, {"couchdb": _mock_couchdb_module}):
        original = couchdb_client._couchdb_module  # type: ignore[attr-defined]
        couchdb_client._couchdb_module = _mock_couchdb_module  # type: ignore[attr-defined]
        try:
            yield
        finally:
            couchdb_client._couchdb_module = original  # type: ignore[attr-defined]


def _make_client(
    url: str = "http://couchdb:5984",
    username: str = "admin",
    password: str = "changeme",
) -> Any:
    """Helper to create a CouchDBClient with mocked dependencies."""
    from odg_core.nosql.couchdb_client import CouchDBClient

    return CouchDBClient(url=url, username=username, password=password)


# ──── Initialization ─────────────────────────────────────────


class TestCouchDBClientInit:
    """Tests for CouchDBClient initialization."""

    def test_stores_configuration(self) -> None:
        client = _make_client(url="http://my-couch:5984", username="u", password="p")
        assert client.url == "http://my-couch:5984"
        assert client._username == "u"
        assert client._password == "p"
        assert client._connected is False

    def test_raises_import_error_when_module_missing(self) -> None:
        with patch.dict(sys.modules, {"couchdb": None}):
            # Force re-import to pick up None module

            from odg_core.nosql import couchdb_client

            original = couchdb_client._couchdb_module  # type: ignore[attr-defined]
            couchdb_client._couchdb_module = None  # type: ignore[attr-defined]
            try:
                with pytest.raises(ImportError, match="couchdb-python"):
                    couchdb_client.CouchDBClient()
            finally:
                couchdb_client._couchdb_module = original  # type: ignore[attr-defined]


# ──── connect ────────────────────────────────────────────────


class TestConnect:
    """Tests for CouchDBClient.connect."""

    def test_connect_sets_connected(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_server.version.return_value = "3.3.0"
        _mock_couchdb_module.Server.return_value = mock_server

        client.connect()

        assert client._connected is True

    def test_connect_raises_without_credentials(self) -> None:
        from odg_core.nosql.couchdb_client import CouchDBClient

        client = CouchDBClient(url="http://couch:5984", username=None, password=None)

        with pytest.raises(ValueError, match="credentials not provided"):
            client.connect()


# ──── _ensure_connected ──────────────────────────────────────


class TestEnsureConnected:
    """Tests for _ensure_connected helper."""

    def test_returns_server_when_connected(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        client._server = mock_server
        client._connected = True

        result = client._ensure_connected()
        assert result is mock_server

    def test_calls_connect_when_not_connected(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_server.version.return_value = "3.3.0"
        _mock_couchdb_module.Server.return_value = mock_server

        # Not connected yet
        assert client._connected is False
        client._ensure_connected()
        assert client._connected is True


# ──── create_database ────────────────────────────────────────


class TestCreateDatabase:
    """Tests for CouchDBClient.create_database."""

    def test_creates_new_database(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_server.__contains__ = MagicMock(return_value=False)
        client._server = mock_server
        client._connected = True

        result = client.create_database("test_db")

        assert result is True
        mock_server.create.assert_called_once_with("test_db")

    def test_returns_false_if_exists(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_server.__contains__ = MagicMock(return_value=True)
        client._server = mock_server
        client._connected = True

        result = client.create_database("existing_db")

        assert result is False
        mock_server.create.assert_not_called()


# ──── delete_database ────────────────────────────────────────


class TestDeleteDatabase:
    """Tests for CouchDBClient.delete_database."""

    def test_deletes_existing_database(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_server.__contains__ = MagicMock(return_value=True)
        client._server = mock_server
        client._connected = True

        result = client.delete_database("test_db")

        assert result is True
        mock_server.__delitem__.assert_called_once_with("test_db")

    def test_returns_false_if_not_exists(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_server.__contains__ = MagicMock(return_value=False)
        client._server = mock_server
        client._connected = True

        result = client.delete_database("missing_db")

        assert result is False


# ──── save_document ──────────────────────────────────────────


class TestSaveDocument:
    """Tests for CouchDBClient.save_document."""

    def test_saves_new_document(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_db = MagicMock()
        mock_db.__contains__ = MagicMock(return_value=False)
        mock_server.__contains__ = MagicMock(return_value=True)
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        client._server = mock_server
        client._connected = True

        result = client.save_document("test_db", "doc1", {"key": "value"})

        mock_db.save.assert_called_once()
        assert result["_id"] == "doc1"
        assert result["key"] == "value"
        assert "_created_at" in result

    def test_saves_document_with_auto_timestamp_disabled(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_db = MagicMock()
        mock_db.__contains__ = MagicMock(return_value=False)
        mock_server.__contains__ = MagicMock(return_value=True)
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        client._server = mock_server
        client._connected = True

        result = client.save_document("test_db", "doc1", {"key": "value"}, auto_timestamp=False)

        assert "_created_at" not in result


# ──── get_document ───────────────────────────────────────────


class TestGetDocument:
    """Tests for CouchDBClient.get_document."""

    def test_returns_document(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_db = MagicMock()
        mock_doc = {"_id": "doc1", "key": "value"}
        mock_db.__contains__ = MagicMock(return_value=True)
        mock_db.__getitem__ = MagicMock(return_value=mock_doc)
        mock_server.__contains__ = MagicMock(return_value=True)
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        client._server = mock_server
        client._connected = True

        result = client.get_document("test_db", "doc1")
        assert result is not None
        assert result["_id"] == "doc1"

    def test_returns_none_when_db_missing(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_server.__contains__ = MagicMock(return_value=False)
        client._server = mock_server
        client._connected = True

        result = client.get_document("missing_db", "doc1")
        assert result is None

    def test_returns_none_when_doc_missing(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_db = MagicMock()
        mock_db.__contains__ = MagicMock(return_value=False)
        mock_server.__contains__ = MagicMock(return_value=True)
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        client._server = mock_server
        client._connected = True

        result = client.get_document("test_db", "missing_doc")
        assert result is None


# ──── delete_document ────────────────────────────────────────


class TestDeleteDocument:
    """Tests for CouchDBClient.delete_document."""

    def test_deletes_existing_document(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_db = MagicMock()
        mock_doc = {"_id": "doc1", "_rev": "1-abc"}
        mock_db.__contains__ = MagicMock(return_value=True)
        mock_db.__getitem__ = MagicMock(return_value=mock_doc)
        mock_server.__contains__ = MagicMock(return_value=True)
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        client._server = mock_server
        client._connected = True

        result = client.delete_document("test_db", "doc1")

        assert result is True
        mock_db.delete.assert_called_once_with(mock_doc)

    def test_returns_false_when_doc_missing(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_db = MagicMock()
        mock_db.__contains__ = MagicMock(return_value=False)
        mock_server.__contains__ = MagicMock(return_value=True)
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        client._server = mock_server
        client._connected = True

        result = client.delete_document("test_db", "missing_doc")
        assert result is False


# ──── query_view ─────────────────────────────────────────────


class TestQueryView:
    """Tests for CouchDBClient.query_view."""

    def test_returns_results(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.id = "doc1"
        mock_row.key = "sklearn"
        mock_row.value = {"model": "churn"}
        mock_db.view.return_value = [mock_row]
        mock_server.__contains__ = MagicMock(return_value=True)
        mock_server.__getitem__ = MagicMock(return_value=mock_db)
        client._server = mock_server
        client._connected = True

        results = client.query_view("model_registry", "models", "by_framework", key="sklearn")

        assert len(results) == 1
        assert results[0]["id"] == "doc1"
        assert results[0]["key"] == "sklearn"

    def test_returns_empty_when_db_missing(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_server.__contains__ = MagicMock(return_value=False)
        client._server = mock_server
        client._connected = True

        results = client.query_view("missing_db", "design", "view")
        assert results == []


# ──── list_databases ─────────────────────────────────────────


class TestListDatabases:
    """Tests for CouchDBClient.list_databases."""

    def test_returns_database_names(self) -> None:
        client = _make_client()
        mock_server = MagicMock()
        mock_server.__iter__ = MagicMock(return_value=iter(["db1", "db2", "_replicator"]))
        client._server = mock_server
        client._connected = True

        result = client.list_databases()
        assert result == ["db1", "db2", "_replicator"]


# ──── find ───────────────────────────────────────────────────


class TestFind:
    """Tests for CouchDBClient.find (Mango query)."""

    @patch("requests.post")
    def test_find_returns_matching_docs(self, mock_post: MagicMock) -> None:
        client = _make_client()
        client._username = "admin"
        client._password = "changeme"
        client._url = "http://couchdb:5984"
        mock_server = MagicMock()
        client._server = mock_server
        client._connected = True

        mock_response = MagicMock()
        mock_response.json.return_value = {"docs": [{"_id": "doc1", "framework": "sklearn"}]}
        mock_post.return_value = mock_response

        results = client.find("model_registry", {"framework": {"$eq": "sklearn"}})

        assert len(results) == 1
        assert results[0]["_id"] == "doc1"
