"""API connectors for REST and GraphQL endpoints.

Provides connectors for extracting data from HTTP APIs with support for
authentication, pagination, rate limiting, and error handling.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import requests

from odg_core.connectors.base import BaseConnector, ConnectorConfig

if TYPE_CHECKING:
    from collections.abc import Iterator


def _ensure_session(session: requests.Session | None) -> requests.Session:
    """Validate that a session has been initialized via connect().

    Args:
        session: The session to validate

    Returns:
        The validated session

    Raises:
        RuntimeError: If session is None (connect() not called)
    """
    if session is None:
        raise RuntimeError("Not connected. Call connect() before using the connector.")
    return session


class APIConnector(BaseConnector):
    """Base connector for HTTP APIs."""

    def __init__(self, config: ConnectorConfig, base_url: str):
        """Initialize API connector.

        Args:
            config: Connector configuration
            base_url: Base URL for the API
        """
        super().__init__(config)
        self.base_url = base_url
        self.session: requests.Session | None = None

    def connect(self) -> None:
        """Establish HTTP session with authentication."""
        session = requests.Session()

        # Configure authentication
        if self.config.auth_type == "basic":
            username = str(self.config.credentials.get("username", ""))
            password = str(self.config.credentials.get("password", ""))
            session.auth = (username, password)

        elif self.config.auth_type == "bearer":
            token = self.config.credentials.get("token")
            session.headers["Authorization"] = f"Bearer {token}"

        elif self.config.auth_type == "api_key":
            api_key = self.config.credentials.get("api_key")
            header_name = str(self.config.credentials.get("header_name", "X-API-Key"))
            session.headers[header_name] = str(api_key or "")

        # Test connection
        try:
            response = session.get(self.base_url, timeout=10)
            response.raise_for_status()
            self._connected = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to API: {e}") from e

        self.session = session

    def disconnect(self) -> None:
        """Close HTTP session."""
        if self.session:
            self.session.close()
        super().disconnect()


class RESTConnector(APIConnector):
    """Connector for REST APIs with pagination support.

    Example:
        >>> config = ConnectorConfig(
        ...     connector_type="rest_api",
        ...     source_name="github_repos",
        ...     auth_type="bearer",
        ...     credentials={"token": "ghp_xxx"},
        ...     target_table="github_repositories"
        ... )
        >>>
        >>> connector = RESTConnector(
        ...     config=config,
        ...     base_url="https://api.github.com",
        ...     endpoint="/orgs/apache/repos",
        ...     pagination_type="link_header"
        ... )
        >>>
        >>> result = connector.ingest(limit=100)
    """

    def __init__(
        self,
        config: ConnectorConfig,
        base_url: str,
        endpoint: str,
        pagination_type: str = "offset",  # "offset", "page", "cursor", "link_header"
        records_per_page: int = 100,
        data_path: str | None = None,  # JSONPath to data array
    ):
        """Initialize REST API connector.

        Args:
            config: Connector configuration
            base_url: Base URL for the API
            endpoint: API endpoint path
            pagination_type: Pagination strategy
            records_per_page: Records per page
            data_path: JSONPath to extract data array from response
        """
        super().__init__(config, base_url)
        self.endpoint = endpoint
        self.pagination_type = pagination_type
        self.records_per_page = records_per_page
        self.data_path = data_path

    def extract(self, limit: int | None = None, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Extract data from REST API with pagination.

        Args:
            limit: Maximum number of records to extract
            **kwargs: Additional query parameters

        Yields:
            Records from the API
        """
        session = _ensure_session(self.session)
        url = urljoin(self.base_url, self.endpoint)
        params: dict[str, Any] = {**kwargs, "per_page": self.records_per_page}

        records_extracted = 0
        page = 1

        while True:
            # Add pagination parameter
            if self.pagination_type == "offset":
                params["offset"] = (page - 1) * self.records_per_page
                params["limit"] = self.records_per_page
            elif self.pagination_type == "page":
                params["page"] = page

            # Make request
            try:
                response = session.get(url, params=params, timeout=30)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"API request failed: {e}")
                break

            # Parse response
            data = response.json()

            # Extract records from response
            if self.data_path:
                # Use JSONPath if specified
                records = self._extract_from_path(data, self.data_path)
            elif isinstance(data, list):
                records = data
            else:
                # Assume data is at root level or has common keys
                records = data.get("data") or data.get("results") or data.get("items") or [data]

            # Yield records
            for record in records:
                yield record
                records_extracted += 1

                if limit and records_extracted >= limit:
                    return

            # Check for more pages
            if not records or len(records) < self.records_per_page:
                break

            # Handle link header pagination
            if self.pagination_type == "link_header":
                link_header = response.headers.get("Link")
                if not link_header or 'rel="next"' not in link_header:
                    break
                # Extract next URL from link header
                url = self._parse_link_header(link_header)

            page += 1

            # Rate limiting (respect API limits)
            time.sleep(0.1)

    def _extract_from_path(self, data: dict[str, Any], path: str) -> list[dict[str, Any]]:
        """Extract data using simple JSONPath-like syntax.

        Args:
            data: Response data
            path: Path to data array (e.g., "results.items")

        Returns:
            Extracted records
        """
        keys = path.split(".")
        current: Any = data

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return []

        if current is None:
            return []

        return current if isinstance(current, list) else [current]

    def _parse_link_header(self, link_header: str) -> str:
        """Parse Link header for next page URL.

        Args:
            link_header: Link header value

        Returns:
            Next page URL
        """
        links = link_header.split(",")
        for link in links:
            if 'rel="next"' in link:
                url = link.split(";")[0].strip("<>")
                return url
        return ""

    def get_schema(self) -> dict[str, Any]:
        """Infer schema from first API response.

        Returns:
            JSON Schema definition
        """
        # Extract one record to infer schema
        for record in self.extract(limit=1):
            return self._infer_schema(record)

        return {"type": "object", "properties": {}}

    def _infer_schema(self, record: dict[str, Any]) -> dict[str, Any]:
        """Infer JSON Schema from a sample record.

        Args:
            record: Sample record

        Returns:
            JSON Schema definition
        """
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
            elif isinstance(value, list):
                properties[key] = {"type": "array"}
            elif isinstance(value, dict):
                properties[key] = {"type": "object"}
            else:
                properties[key] = {"type": "string"}

        return {"type": "object", "properties": properties, "required": list(record.keys())}


class GraphQLConnector(APIConnector):
    """Connector for GraphQL APIs.

    Example:
        >>> config = ConnectorConfig(
        ...     connector_type="graphql",
        ...     source_name="github_graphql",
        ...     auth_type="bearer",
        ...     credentials={"token": "ghp_xxx"}
        ... )
        >>>
        >>> query = '''
        ... query {
        ...   repository(owner: "apache", name: "kafka") {
        ...     name
        ...     stargazerCount
        ...     forkCount
        ...   }
        ... }
        ... '''
        >>>
        >>> connector = GraphQLConnector(
        ...     config=config,
        ...     endpoint="https://api.github.com/graphql",
        ...     query=query
        ... )
        >>>
        >>> result = connector.ingest()
    """

    def __init__(
        self,
        config: ConnectorConfig,
        endpoint: str,
        query: str,
        variables: dict[str, Any] | None = None,
    ):
        """Initialize GraphQL connector.

        Args:
            config: Connector configuration
            endpoint: GraphQL endpoint URL
            query: GraphQL query string
            variables: Query variables
        """
        super().__init__(config, endpoint)
        self.query = query
        self.variables = variables or {}

    def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Execute GraphQL query and extract data.

        Yields:
            Records from GraphQL response
        """
        session = _ensure_session(self.session)
        payload: dict[str, Any] = {"query": self.query, "variables": {**self.variables, **kwargs}}

        try:
            response = session.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"GraphQL request failed: {e}")
            return

        data = response.json()

        # Check for GraphQL errors
        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}")
            return

        # Extract data (usually nested under "data" key)
        result = data.get("data", {})

        # Flatten and yield records
        for key, value in result.items():
            if isinstance(value, list):
                yield from value
            elif isinstance(value, dict):
                yield value
            else:
                yield {key: value}

    def get_schema(self) -> dict[str, Any]:
        """GraphQL introspection to get schema.

        Returns:
            JSON Schema definition
        """
        # Simplified - full introspection query would be much longer
        introspection_query = """
        query IntrospectionQuery {
          __schema {
            types {
              name
              fields {
                name
                type {
                  name
                  kind
                }
              }
            }
          }
        }
        """

        session = _ensure_session(self.session)
        payload = {"query": introspection_query}

        try:
            response = session.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status()
            response.json()

            # Convert GraphQL schema to JSON Schema (simplified)
            return {"type": "object", "description": "GraphQL schema", "properties": {}}

        except Exception:
            return {"type": "object", "properties": {}}
