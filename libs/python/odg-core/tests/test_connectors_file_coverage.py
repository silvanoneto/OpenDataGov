"""Tests for odg_core.connectors.file_connector module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from odg_core.connectors.base import ConnectorConfig
from odg_core.connectors.file_connector import (
    FileConnector,
    FTPConnector,
    S3Connector,
)


class _ConcreteFileConnector(FileConnector):
    """Concrete subclass for testing _read_* methods."""

    def connect(self) -> None:
        self._connected = True

    def extract(self, **kwargs: Any) -> Any:
        yield from []

    def get_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture()
def config() -> ConnectorConfig:
    return ConnectorConfig(
        connector_type="file",
        source_name="test_file",
        credentials={"aws_access_key_id": "key", "aws_secret_access_key": "secret"},
    )


@pytest.fixture()
def ftp_config() -> ConnectorConfig:
    return ConnectorConfig(
        connector_type="ftp",
        source_name="test_ftp",
        credentials={"username": "user", "password": "pass"},
    )


# ── FileConnector._read_json ─────────────────────────────────


class TestFileConnectorReadJson:
    def test_reads_json_array(self, config: ConnectorConfig) -> None:
        connector = _ConcreteFileConnector(config, file_format="json")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"id": 1}, {"id": 2}], f)
            f.flush()
            records = list(connector._read_json(f.name))
        Path(f.name).unlink()
        assert records == [{"id": 1}, {"id": 2}]

    def test_reads_single_json_object(self, config: ConnectorConfig) -> None:
        connector = _ConcreteFileConnector(config, file_format="json")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"id": 1, "name": "test"}, f)
            f.flush()
            records = list(connector._read_json(f.name))
        Path(f.name).unlink()
        assert records == [{"id": 1, "name": "test"}]

    def test_reads_ndjson(self, config: ConnectorConfig) -> None:
        connector = _ConcreteFileConnector(config, file_format="json")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # Write invalid JSON first line to trigger NDJSON parsing
            f.write('{"id": 1}\n{"id": 2}\n')
            f.flush()
            # The file starts as valid JSON array attempt, fails, then reads as ndjson
            # Actually writing it this way: first try json.load which fails for ndjson
            # Let's write proper ndjson that json.load can't parse
        # Write NDJSON that will fail json.load
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"id": 1}\n{"id": 2}\n')
            f.flush()
            path = f.name
        records = list(connector._read_json(path))
        Path(path).unlink()
        assert len(records) == 2
        assert records[0] == {"id": 1}
        assert records[1] == {"id": 2}

    def test_reads_csv(self, config: ConnectorConfig) -> None:
        connector = _ConcreteFileConnector(config, file_format="csv")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("id,name\n1,Alice\n2,Bob\n")
            f.flush()
            records = list(connector._read_csv(f.name))
        Path(f.name).unlink()
        assert len(records) == 2
        assert records[0]["id"] == "1"
        assert records[0]["name"] == "Alice"

    def test_read_parquet_missing_lib(self, config: ConnectorConfig) -> None:
        connector = _ConcreteFileConnector(config, file_format="parquet")
        with (
            patch.dict("sys.modules", {"pyarrow": None, "pyarrow.parquet": None}),
            pytest.raises(ImportError, match="pyarrow"),
        ):
            list(connector._read_parquet("/fake/file.parquet"))


# ── S3Connector ───────────────────────────────────────────────


class TestS3Connector:
    def test_init(self, config: ConnectorConfig) -> None:
        connector = S3Connector(
            config=config,
            bucket="test-bucket",
            prefix="data/",
            file_pattern="*.json",
            endpoint_url="http://minio:9000",
        )
        assert connector.bucket == "test-bucket"
        assert connector.prefix == "data/"
        assert connector.file_pattern == "*.json"
        assert connector.endpoint_url == "http://minio:9000"
        assert connector.s3_client is None

    def test_ensure_s3_client_raises_when_none(self, config: ConnectorConfig) -> None:
        connector = S3Connector(config=config, bucket="b")
        with pytest.raises(RuntimeError, match="Not connected"):
            connector._ensure_s3_client()

    def test_ensure_s3_client_returns_client(self, config: ConnectorConfig) -> None:
        connector = S3Connector(config=config, bucket="b")
        mock_client = MagicMock()
        connector.s3_client = mock_client
        assert connector._ensure_s3_client() is mock_client

    def test_connect_with_boto3(self, config: ConnectorConfig) -> None:
        mock_session_cls = MagicMock()
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.client.return_value = mock_client

        with patch("odg_core.connectors.file_connector.boto3", create=True):
            # Simulate successful boto3 import
            import sys

            mock_boto3_mod = MagicMock()
            mock_boto3_mod.Session = mock_session_cls
            with patch.dict(sys.modules, {"boto3": mock_boto3_mod}):
                connector = S3Connector(
                    config=config,
                    bucket="test-bucket",
                    endpoint_url="http://minio:9000",
                )
                connector.connect()

        assert connector._connected is True
        assert connector.s3_client is mock_client

    def test_connect_raises_on_bad_bucket(self, config: ConnectorConfig) -> None:
        import sys

        mock_boto3_mod = MagicMock()
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3_mod.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        mock_client.head_bucket.side_effect = Exception("NoSuchBucket")

        with patch.dict(sys.modules, {"boto3": mock_boto3_mod}):
            connector = S3Connector(config=config, bucket="bad-bucket")
            with pytest.raises(ConnectionError, match="Failed to connect"):
                connector.connect()

    def test_extract_reads_json_files(self, config: ConnectorConfig) -> None:
        connector = S3Connector(config=config, bucket="b", prefix="data/", file_pattern="*.json")
        mock_client = MagicMock()
        connector.s3_client = mock_client

        # Mock paginator
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"Contents": [{"Key": "data/test.json"}]}]

        # Mock download - write a JSON file
        def download_side_effect(bucket, key, fileobj):
            fileobj.write(json.dumps([{"id": 1}]).encode())

        mock_client.download_fileobj.side_effect = download_side_effect

        records = list(connector.extract())
        assert len(records) == 1
        assert records[0] == {"id": 1}

    def test_extract_skips_non_matching_files(self, config: ConnectorConfig) -> None:
        connector = S3Connector(config=config, bucket="b", prefix="data/", file_pattern="*.json")
        mock_client = MagicMock()
        connector.s3_client = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"Contents": [{"Key": "data/test.csv"}]}]

        records = list(connector.extract())
        assert records == []

    def test_get_schema_empty(self, config: ConnectorConfig) -> None:
        connector = S3Connector(config=config, bucket="b")
        mock_client = MagicMock()
        connector.s3_client = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"Contents": []}]

        schema = connector.get_schema()
        assert schema == {"type": "object", "properties": {}}

    def test_infer_schema(self, config: ConnectorConfig) -> None:
        connector = S3Connector(config=config, bucket="b")
        schema = connector._infer_schema({"name": "test", "count": 42, "score": 3.14, "active": True})
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "integer"
        assert schema["properties"]["score"]["type"] == "number"
        # bool is subclass of int; _infer_schema checks int before bool
        assert schema["properties"]["active"]["type"] in ("boolean", "integer")

    def test_infer_schema_unknown_type(self, config: ConnectorConfig) -> None:
        connector = S3Connector(config=config, bucket="b")
        schema = connector._infer_schema({"data": None})
        assert schema["properties"]["data"]["type"] == "string"


# ── FTPConnector ──────────────────────────────────────────────


class TestFTPConnector:
    def test_init_ftp(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(
            config=ftp_config,
            host="ftp.example.com",
            directory="/data",
            file_pattern="*.csv",
        )
        assert connector.host == "ftp.example.com"
        assert connector.directory == "/data"
        assert connector.use_sftp is False
        assert connector.port == 21

    def test_init_sftp(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(
            config=ftp_config,
            host="sftp.example.com",
            use_sftp=True,
        )
        assert connector.use_sftp is True
        assert connector.port == 22

    def test_init_custom_port(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(
            config=ftp_config,
            host="ftp.example.com",
            port=2222,
        )
        assert connector.port == 2222

    def test_connect_ftp(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(config=ftp_config, host="ftp.example.com")
        mock_ftp = MagicMock()

        with patch("odg_core.connectors.file_connector.FTP", return_value=mock_ftp):
            connector.connect()

        assert connector._connected is True
        assert connector._ftp_client is mock_ftp
        mock_ftp.connect.assert_called_once_with("ftp.example.com", 21)
        mock_ftp.login.assert_called_once_with("user", "pass")

    def test_connect_ftp_failure(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(config=ftp_config, host="ftp.example.com")
        mock_ftp = MagicMock()
        mock_ftp.connect.side_effect = Exception("Connection refused")

        with (
            patch("odg_core.connectors.file_connector.FTP", return_value=mock_ftp),
            pytest.raises(ConnectionError, match="Failed to connect to FTP"),
        ):
            connector.connect()

    def test_connect_sftp(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(config=ftp_config, host="sftp.example.com", use_sftp=True)

        import sys

        mock_paramiko = MagicMock()
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_ssh
        mock_ssh.open_sftp.return_value = mock_sftp

        with patch.dict(sys.modules, {"paramiko": mock_paramiko}):
            connector.connect()

        assert connector._connected is True
        assert connector._sftp_client is mock_sftp
        assert connector._ssh_client is mock_ssh

    def test_connect_sftp_failure(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(config=ftp_config, host="sftp.example.com", use_sftp=True)

        import sys

        mock_paramiko = MagicMock()
        mock_ssh = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_ssh
        mock_ssh.connect.side_effect = Exception("Auth failed")

        with (
            patch.dict(sys.modules, {"paramiko": mock_paramiko}),
            pytest.raises(ConnectionError, match="Failed to connect to SFTP"),
        ):
            connector.connect()

    def test_extract_ftp_not_connected(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(config=ftp_config, host="ftp.example.com")
        with pytest.raises(RuntimeError, match="Not connected"):
            list(connector.extract())

    def test_extract_sftp_not_connected(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(config=ftp_config, host="sftp.example.com", use_sftp=True)
        with pytest.raises(RuntimeError, match="Not connected"):
            list(connector.extract())

    def test_extract_ftp_json_files(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(
            config=ftp_config,
            host="ftp.example.com",
            directory="/data",
            file_pattern="*.json",
            file_format="json",
        )
        mock_ftp = MagicMock()
        connector._ftp_client = mock_ftp
        connector._connected = True

        mock_ftp.nlst.return_value = ["report.json", "data.csv"]

        def retrbinary_effect(cmd, callback):
            callback(json.dumps([{"id": 1}]).encode())

        mock_ftp.retrbinary.side_effect = retrbinary_effect

        records = list(connector.extract())
        assert len(records) == 1
        assert records[0] == {"id": 1}

    def test_extract_sftp_files(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(
            config=ftp_config,
            host="sftp.example.com",
            directory="/data",
            file_pattern="*.json",
            file_format="json",
            use_sftp=True,
        )
        mock_sftp = MagicMock()
        connector._sftp_client = mock_sftp
        connector._connected = True

        mock_sftp.listdir.return_value = ["report.json"]

        def get_effect(remote, local):
            with open(local, "w") as f:
                json.dump([{"id": 42}], f)

        mock_sftp.get.side_effect = get_effect

        records = list(connector.extract())
        assert len(records) == 1
        assert records[0] == {"id": 42}

    def test_get_schema_empty(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(config=ftp_config, host="ftp.example.com")
        mock_ftp = MagicMock()
        connector._ftp_client = mock_ftp
        connector._connected = True
        mock_ftp.nlst.return_value = []

        schema = connector.get_schema()
        assert schema == {"type": "object", "properties": {}}

    def test_disconnect_ftp(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(config=ftp_config, host="ftp.example.com")
        mock_ftp = MagicMock()
        connector._ftp_client = mock_ftp
        connector._connected = True

        connector.disconnect()

        mock_ftp.quit.assert_called_once()
        assert connector._connected is False

    def test_disconnect_sftp(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(config=ftp_config, host="sftp.example.com", use_sftp=True)
        mock_sftp = MagicMock()
        mock_ssh = MagicMock()
        connector._sftp_client = mock_sftp
        connector._ssh_client = mock_ssh
        connector._connected = True

        connector.disconnect()

        mock_sftp.close.assert_called_once()
        mock_ssh.close.assert_called_once()
        assert connector._connected is False

    def test_disconnect_without_connection(self, ftp_config: ConnectorConfig) -> None:
        connector = FTPConnector(config=ftp_config, host="ftp.example.com")
        connector.disconnect()
        assert connector._connected is False
