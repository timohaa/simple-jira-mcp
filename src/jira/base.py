"""Base Jira client with shared utilities and constants."""

import logging
from typing import Any

import httpx

from src.config import JiraConfig
from src.jira.adf import adf_to_text

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
        """Create an async HTTP client using the config's timeout."""
        return httpx.AsyncClient(timeout=self.config.timeout)

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
    def _extract_key(obj: dict[str, Any] | None) -> str | None:
        """Extract 'key' field from a Jira object."""
        if obj and isinstance(obj, dict):
            return obj.get("key")
        return None

    @staticmethod
    def _format_date(date_str: str | None) -> str | None:
        """Return a Jira date string, or None if absent."""
        if not date_str:
            return None
        return date_str

    def _extract_comments(self, comment_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract comments from issue data."""
        comments = []
        for comment in comment_data.get("comments", []):
            comments.append(
                {
                    "author": self._extract_display_name(comment.get("author")),
                    "created": comment.get("created"),
                    "body": adf_to_text(comment.get("body")),
                }
            )
        return comments

    def _extract_attachments(
        self, attachment_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Extract attachment metadata from issue data."""
        attachments = []
        for att in attachment_data:
            size_bytes = att.get("size", 0)
            attachments.append(
                {
                    "id": str(att.get("id")),
                    "filename": att.get("filename"),
                    "size_kb": round(size_bytes / 1024, 2),
                    "mime_type": att.get("mimeType"),
                    "created": self._format_date(att.get("created")),
                }
            )
        return attachments
