"""Base Jira client with shared utilities and constants."""

import logging
from typing import Any

import httpx

from src.config import JiraConfig

logger = logging.getLogger(__name__)

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429

API_BASE = "/rest/api/3"
SEARCH_PATH = f"{API_BASE}/search/jql"
ISSUE_PATH = f"{API_BASE}/issue"
ATTACHMENT_PATH = f"{API_BASE}/attachment/content"

DEFAULT_TIMEOUT = 30.0


class JiraClientBase:
    """Base class for Jira API operations with shared utilities."""

    def __init__(self, config: JiraConfig) -> None:
        """Initialize the Jira client base.

        Args:
            config: Jira configuration with URL and credentials.
        """
        self.config = config
        self.base_url = config.url

    def _get_auth(self) -> tuple[str, str]:
        """Get basic auth credentials."""
        return (self.config.email, self.config.token)

    def _create_client(self) -> httpx.AsyncClient:
        """Create an async HTTP client with default timeout."""
        return httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)

    @staticmethod
    def _extract_name(obj: dict[str, Any] | None) -> str | None:
        """Extract 'name' field from a Jira object."""
        if obj and isinstance(obj, dict):
            return obj.get("name")
        return None

    @staticmethod
    def _extract_display_name(obj: dict[str, Any] | None) -> str | None:
        """Extract 'displayName' field from a Jira user object."""
        if obj and isinstance(obj, dict):
            return obj.get("displayName")
        return None

    @staticmethod
    def _format_date(date_str: str | None) -> str | None:
        """Return a Jira date string, or None if absent."""
        if not date_str:
            return None
        return date_str
