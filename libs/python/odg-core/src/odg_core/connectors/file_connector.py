"""File-based connectors for S3, FTP, HTTP downloads, and local files.

Supports various file formats: CSV, JSON, Parquet, Excel, etc.
"""

from __future__ import annotations

import csv
import json
from ftplib import FTP
from pathlib import Path
from typing import TYPE_CHECKING, Any

from odg_core.connectors.base import BaseConnector, ConnectorConfig

if TYPE_CHECKING:
    from collections.abc import Iterator


class FileConnector(BaseConnector):
    """Base connector for file-based sources."""

    def __init__(
        self,
        config: ConnectorConfig,
        file_format: str = "json",  # json, csv, parquet, excel
        encoding: str = "utf-8",
    ):
        """Initialize file connector.

        Args:
            config: Connector configuration
            file_format: File format (json, csv, parquet, excel)
            encoding: File encoding
        """
        super().__init__(config)
        self.file_format = file_format
        self.encoding = encoding

    def _read_json(self, file_path: str) -> Iterator[dict[str, Any]]:
        """Read JSON file (supports both array and newline-delimited JSON).

        Args:
            file_path: Path to JSON file

        Yields:
            Records from JSON file
        """
        with open(file_path, encoding=self.encoding) as f:
            try:
                # Try parsing as JSON array
                data = json.load(f)
                if isinstance(data, list):
                    yield from data
                else:
                    yield data
            except json.JSONDecodeError:
                # Try newline-delimited JSON
                f.seek(0)
                for line in f:
                    if line.strip():
                        yield json.loads(line)

    def _read_csv(self, file_path: str) -> Iterator[dict[str, Any]]:
        """Read CSV file.

        Args:
            file_path: Path to CSV file

        Yields:
            Records from CSV file
        """
        with open(file_path, encoding=self.encoding) as f:
            reader = csv.DictReader(f)
            yield from reader

    def _read_parquet(self, file_path: str) -> Iterator[dict[str, Any]]:
        """Read Parquet file.

        Args:
            file_path: Path to Parquet file

        Yields:
            Records from Parquet file
        """
        try:
            import pyarrow.parquet as pq
        except ImportError:
            raise ImportError("pyarrow required for Parquet. Install with: pip install pyarrow") from None

        table = pq.read_table(file_path)
        df = table.to_pandas()

        for _, row in df.iterrows():
            yield {str(k): v for k, v in row.to_dict().items()}


class S3Connector(FileConnector):
    """Connector for files stored in Amazon S3 or MinIO.

    Example:
        >>> config = ConnectorConfig(
        ...     connector_type="s3",
        ...     source_name="s3_data_lake",
        ...     credentials={
        ...         "aws_access_key_id": "minioadmin",
        ...         "aws_secret_access_key": "minioadmin"
        ...     },
        ...     target_table="external_data"
        ... )
        >>>
        >>> connector = S3Connector(
        ...     config=config,
        ...     bucket="raw-data",
        ...     prefix="external/",
        ...     file_pattern="*.json",
        ...     endpoint_url="http://minio:9000"
        ... )
        >>>
        >>> result = connector.ingest()
    """

    def __init__(
        self,
        config: ConnectorConfig,
        bucket: str,
        prefix: str = "",
        file_pattern: str = "*",
        endpoint_url: str | None = None,
        file_format: str = "json",
    ):
        """Initialize S3 connector.

        Args:
            config: Connector configuration
            bucket: S3 bucket name
            prefix: Key prefix (folder path)
            file_pattern: File pattern (e.g., "*.json")
            endpoint_url: S3-compatible endpoint (for MinIO)
            file_format: File format
        """
        super().__init__(config, file_format=file_format)
        self.bucket = bucket
        self.prefix = prefix
        self.file_pattern = file_pattern
        self.endpoint_url = endpoint_url
        self.s3_client: Any = None

    def connect(self) -> None:
        """Connect to S3."""
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 required for S3. Install with: pip install boto3") from None

        session = boto3.Session(
            aws_access_key_id=self.config.credentials.get("aws_access_key_id"),
            aws_secret_access_key=self.config.credentials.get("aws_secret_access_key"),
            region_name=self.config.credentials.get("region", "us-east-1"),
        )

        s3_client = session.client("s3", endpoint_url=self.endpoint_url)

        # Test connection
        try:
            s3_client.head_bucket(Bucket=self.bucket)
            self._connected = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to S3 bucket {self.bucket}: {e}") from e

        self.s3_client = s3_client

    def _ensure_s3_client(self) -> Any:
        """Validate that the S3 client has been initialized via connect().

        Returns:
            The validated S3 client

        Raises:
            RuntimeError: If client is None (connect() not called)
        """
        if self.s3_client is None:
            raise RuntimeError("Not connected. Call connect() before using the connector.")
        return self.s3_client

    def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Extract data from S3 files.

        Yields:
            Records from S3 files
        """
        s3_client = self._ensure_s3_client()
        # List objects in bucket
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self.bucket, Prefix=self.prefix)

        import fnmatch
        import tempfile

        for page in pages:
            for obj in page.get("Contents", []):
                key = obj["Key"]

                # Filter by file pattern
                if not fnmatch.fnmatch(key, f"{self.prefix}{self.file_pattern}"):
                    continue

                # Download file to temp location
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{self.file_format}") as tmp_file:
                    s3_client.download_fileobj(self.bucket, key, tmp_file)
                    tmp_path = tmp_file.name

                # Read file based on format
                try:
                    if self.file_format == "json":
                        yield from self._read_json(tmp_path)
                    elif self.file_format == "csv":
                        yield from self._read_csv(tmp_path)
                    elif self.file_format == "parquet":
                        yield from self._read_parquet(tmp_path)
                finally:
                    # Cleanup temp file
                    Path(tmp_path).unlink(missing_ok=True)

    def get_schema(self) -> dict[str, Any]:
        """Infer schema from first file.

        Returns:
            JSON Schema definition
        """
        for record in self.extract():
            return self._infer_schema(record)

        return {"type": "object", "properties": {}}

    def _infer_schema(self, record: dict[str, Any]) -> dict[str, Any]:
        """Infer schema from sample record."""
        properties = {}

        for key, value in record.items():
            if isinstance(value, str):
                properties[key] = {"type": "string"}
            elif isinstance(value, int):
                properties[key] = {"type": "integer"}
            elif isinstance(value, float):
                properties[key] = {"type": "number"}
            elif isinstance(value, bool):
                properties[key] = {"type": "boolean"}
            else:
                properties[key] = {"type": "string"}

        return {"type": "object", "properties": properties}


class FTPConnector(FileConnector):
    """Connector for FTP/SFTP file servers.

    Example:
        >>> config = ConnectorConfig(
        ...     connector_type="ftp",
        ...     source_name="partner_ftp",
        ...     credentials={
        ...         "username": "ftpuser",
        ...         "password": "ftppass"
        ...     }
        ... )
        >>>
        >>> connector = FTPConnector(
        ...     config=config,
        ...     host="ftp.partner.com",
        ...     directory="/data/exports",
        ...     file_pattern="*.csv",
        ...     use_sftp=True
        ... )
        >>>
        >>> result = connector.ingest()
    """

    def __init__(
        self,
        config: ConnectorConfig,
        host: str,
        directory: str = "/",
        file_pattern: str = "*",
        use_sftp: bool = False,
        port: int | None = None,
        file_format: str = "csv",
    ):
        """Initialize FTP connector.

        Args:
            config: Connector configuration
            host: FTP server hostname
            directory: Remote directory
            file_pattern: File pattern
            use_sftp: Use SFTP instead of FTP
            port: Server port
            file_format: File format
        """
        super().__init__(config, file_format=file_format)
        self.host = host
        self.directory = directory
        self.file_pattern = file_pattern
        self.use_sftp = use_sftp
        self.port = port or (22 if use_sftp else 21)
        self._ssh_client: Any = None
        self._sftp_client: Any = None
        self._ftp_client: FTP | None = None

    def connect(self) -> None:
        """Connect to FTP/SFTP server."""
        username = self.config.credentials.get("username", "")
        password = self.config.credentials.get("password", "")

        if self.use_sftp:
            try:
                import paramiko  # type: ignore[import-untyped]
            except ImportError:
                raise ImportError("paramiko required for SFTP. Install with: pip install paramiko") from None

            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                ssh_client.connect(self.host, port=self.port, username=username, password=password)
                self._sftp_client = ssh_client.open_sftp()
                self._ssh_client = ssh_client
                self._connected = True
            except Exception as e:
                raise ConnectionError(f"Failed to connect to SFTP server: {e}") from e
        else:
            ftp_client = FTP()

            try:
                ftp_client.connect(self.host, self.port)
                ftp_client.login(username, password)
                self._ftp_client = ftp_client
                self._connected = True
            except Exception as e:
                raise ConnectionError(f"Failed to connect to FTP server: {e}") from e

    def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Extract data from FTP files.

        Yields:
            Records from FTP files
        """
        import fnmatch
        import tempfile

        # List files
        if self.use_sftp:
            if self._sftp_client is None:
                raise RuntimeError("Not connected. Call connect() before using the connector.")
            files: list[str] = self._sftp_client.listdir(self.directory)
        else:
            if self._ftp_client is None:
                raise RuntimeError("Not connected. Call connect() before using the connector.")
            files = self._ftp_client.nlst(self.directory)

        for filename in files:
            # Filter by pattern
            if not fnmatch.fnmatch(filename, self.file_pattern):
                continue

            remote_path = f"{self.directory}/{filename}"

            # Download to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{self.file_format}") as tmp_file:
                if self.use_sftp:
                    self._sftp_client.get(remote_path, tmp_file.name)
                else:
                    if self._ftp_client is None:
                        raise RuntimeError("Not connected. Call connect() before using the connector.")
                    with open(tmp_file.name, "wb") as f:
                        self._ftp_client.retrbinary(f"RETR {remote_path}", f.write)

                # Read file
                try:
                    if self.file_format == "json":
                        yield from self._read_json(tmp_file.name)
                    elif self.file_format == "csv":
                        yield from self._read_csv(tmp_file.name)
                    elif self.file_format == "parquet":
                        yield from self._read_parquet(tmp_file.name)
                finally:
                    Path(tmp_file.name).unlink(missing_ok=True)

    def get_schema(self) -> dict[str, Any]:
        """Infer schema from first file."""
        for record in self.extract():
            # Same as S3Connector
            properties = {}
            for key, value in record.items():
                properties[key] = {"type": type(value).__name__}
            return {"type": "object", "properties": properties}

        return {"type": "object", "properties": {}}

    def disconnect(self) -> None:
        """Close FTP/SFTP connection."""
        if self.use_sftp:
            if self._sftp_client is not None:
                self._sftp_client.close()
            if self._ssh_client is not None:
                self._ssh_client.close()
        else:
            if self._ftp_client is not None:
                self._ftp_client.quit()
        super().disconnect()
