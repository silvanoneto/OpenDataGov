"""Web scraping connector for extracting data from public websites.

Respects robots.txt and implements rate limiting to be a good web citizen.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

try:
    import requests
    from bs4 import BeautifulSoup

    _HAS_SCRAPING_DEPS = True
except ImportError:
    _HAS_SCRAPING_DEPS = False

from odg_core.connectors.base import BaseConnector, ConnectorConfig

if TYPE_CHECKING:
    from collections.abc import Iterator


class WebScraperConnector(BaseConnector):
    """Connector for scraping data from public websites.

    Example:
        >>> config = ConnectorConfig(
        ...     connector_type="web_scraper",
        ...     source_name="apache_projects",
        ...     target_table="apache_project_list"
        ... )
        >>>
        >>> connector = WebScraperConnector(
        ...     config=config,
        ...     base_url="https://projects.apache.org",
        ...     selectors={
        ...         "project_name": "h3.project-title",
        ...         "description": "p.project-description"
        ...     }
        ... )
        >>>
        >>> result = connector.ingest()
    """

    def __init__(
        self,
        config: ConnectorConfig,
        base_url: str,
        selectors: dict[str, str],  # CSS selectors for data extraction
        follow_links: bool = False,
        link_selector: str | None = None,
        max_depth: int = 1,
        rate_limit_seconds: float = 1.0,
        respect_robots_txt: bool = True,
    ):
        """Initialize web scraper connector.

        Args:
            config: Connector configuration
            base_url: Base URL to scrape
            selectors: CSS selectors for data extraction {field_name: selector}
            follow_links: Follow links to scrape multiple pages
            link_selector: CSS selector for links to follow
            max_depth: Maximum depth for link following
            rate_limit_seconds: Seconds to wait between requests
            respect_robots_txt: Check robots.txt before scraping
        """
        if not _HAS_SCRAPING_DEPS:
            raise ImportError(
                "beautifulsoup4 and requests are required for web scraping. "
                "Install with: pip install beautifulsoup4 requests"
            )

        super().__init__(config)
        self.base_url = base_url
        self.selectors = selectors
        self.follow_links = follow_links
        self.link_selector = link_selector
        self.max_depth = max_depth
        self.rate_limit_seconds = rate_limit_seconds
        self.respect_robots_txt = respect_robots_txt

        self.session: requests.Session | None = None
        self.robot_parser: RobotFileParser | None = None
        self._visited_urls: set[str] = set()

    def connect(self) -> None:
        """Initialize HTTP session and check robots.txt."""
        session = requests.Session()
        session.headers["User-Agent"] = "OpenDataGov-Bot/1.0 (Educational/Research; https://github.com/opendatagov)"
        self.session = session

        # Check robots.txt
        if self.respect_robots_txt:
            robot_parser = RobotFileParser()
            robots_url = urljoin(self.base_url, "/robots.txt")

            try:
                robot_parser.set_url(robots_url)
                robot_parser.read()
            except Exception as e:
                print(f"Warning: Could not read robots.txt: {e}")

            self.robot_parser = robot_parser

        # Test connection
        if self._can_fetch(self.base_url):
            try:
                response = session.get(self.base_url, timeout=10)
                response.raise_for_status()
                self._connected = True
            except Exception as e:
                raise ConnectionError(f"Failed to connect to website: {e}") from e
        else:
            raise ConnectionError(f"robots.txt disallows scraping {self.base_url}")

    def _can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt.

        Args:
            url: URL to check

        Returns:
            True if URL can be fetched
        """
        if not self.respect_robots_txt or not self.robot_parser:
            return True

        if self.session is None:
            return True

        user_agent: str = str(self.session.headers.get("User-Agent", "*"))
        return self.robot_parser.can_fetch(user_agent, url)

    def extract(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Extract data from website using CSS selectors.

        Yields:
            Records extracted from web pages
        """
        if self.session is None:
            raise RuntimeError("Not connected. Call connect() before using the connector.")
        session = self.session

        urls_to_scrape = [self.base_url]
        current_depth = 0

        while urls_to_scrape and current_depth <= self.max_depth:
            next_urls: list[str] = []

            for url in urls_to_scrape:
                # Skip if already visited
                if url in self._visited_urls:
                    continue

                # Check robots.txt
                if not self._can_fetch(url):
                    print(f"Skipping {url} (disallowed by robots.txt)")
                    continue

                # Fetch page
                try:
                    response = session.get(url, timeout=30)
                    response.raise_for_status()
                except Exception as e:
                    print(f"Failed to fetch {url}: {e}")
                    continue

                self._visited_urls.add(url)

                # Parse HTML
                soup = BeautifulSoup(response.content, "html.parser")

                # Extract data using selectors
                records = self._extract_records(soup, url)
                yield from records

                # Follow links if enabled
                if self.follow_links and self.link_selector and current_depth < self.max_depth:
                    links = soup.select(self.link_selector)
                    for link in links:
                        href = link.get("href")
                        if href:
                            # Ensure url and href are not sequences (mypy sanity check)
                            u = str(url)
                            h = str(href)
                            absolute_url = urljoin(u, h)
                            # Only follow links on same domain
                            if urlparse(absolute_url).netloc == urlparse(str(self.base_url)).netloc:
                                next_urls.append(absolute_url)

                # Rate limiting
                time.sleep(self.rate_limit_seconds)

            urls_to_scrape = next_urls
            current_depth += 1

    def _extract_records(self, soup: BeautifulSoup, url: str) -> Iterator[dict[str, Any]]:
        """Extract records from parsed HTML.

        Args:
            soup: BeautifulSoup object
            url: Page URL

        Yields:
            Extracted records
        """
        # Find all elements matching the first selector (assumes it's the container)
        first_selector = next(iter(self.selectors.values()))
        containers = soup.select(first_selector)

        if not containers:
            # If no containers found, extract single record from page
            record = {"_url": url}
            for field, selector in self.selectors.items():
                elements = soup.select(selector)
                if elements:
                    record[field] = elements[0].get_text(strip=True)
            yield record
            return

        # Extract record for each container
        for container in containers:
            record = {"_url": url}

            for field, selector in self.selectors.items():
                # Try to find element within container first
                elements = container.select(selector)
                if not elements:
                    # Fallback to page-level search
                    elements = soup.select(selector)

                if elements:
                    record[field] = elements[0].get_text(strip=True)

            # Only yield if record has some data
            if len(record) > 1:  # More than just _url
                yield record

    def get_schema(self) -> dict[str, Any]:
        """Infer schema from selectors.

        Returns:
            JSON Schema definition
        """
        properties = {"_url": {"type": "string", "description": "Source URL"}}

        for field_name in self.selectors:
            properties[field_name] = {"type": "string"}

        return {"type": "object", "properties": properties, "required": ["_url"]}

    def disconnect(self) -> None:
        """Close HTTP session."""
        if self.session:
            self.session.close()
        super().disconnect()
