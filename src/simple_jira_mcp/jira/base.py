"""Base Jira client with shared utilities and constants."""

import logging
from typing import Any

import httpx

from simple_jira_mcp.config import JiraConfig
from simple_jira_mcp.jira.adf import adf_to_text
from simple_jira_mcp.utils.errors import JIRA_ERROR, ErrorResponse, error_response

logger = logging.getLogger(__name__)

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429

API_BASE = "/rest/api/3"
SEARCH_PATH = f"{API_BASE}/search/jql"
ISSUE_PATH = f"{API_BASE}/issue"
ATTACHMENT_PATH = f"{API_BASE}/attachment/content"


class HttpSession:
    """One pooled, authenticated HTTP client for a Jira instance.

    The client is created on first use so that it binds to the event loop
    that issues the requests.
    """

    def __init__(self, config: JiraConfig) -> None:
        """Initialize the session.

        Args:
            config: Jira configuration with credentials and timeout.
        """
        self._config = config
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Return the shared client, creating it on first use."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=(self._config.email, self._config.token),
                timeout=self._config.timeout,
            )
        return self._client

    async def aclose(self) -> None:
        """Close the client if one was created."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class JiraClientBase:
    """Base class for Jira API operations with shared utilities."""

    def __init__(self, config: JiraConfig, session: HttpSession | None = None) -> None:
        """Initialize the Jira client base.

        Args:
            config: Jira configuration with URL and credentials.
            session: HTTP session to share with other operations. A private
                one is created when omitted.
        """
        self.config = config
        self.base_url = config.url
        self._session = session or HttpSession(config)

    @property
    def _http(self) -> httpx.AsyncClient:
        """The session's HTTP client."""
        return self._session.client

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any] | ErrorResponse:
        """Decode a success response body, which must be a JSON object."""
        try:
            data = response.json()
        except ValueError:
            data = None
        if isinstance(data, dict):
            return data
        return error_response(JIRA_ERROR, "Invalid JSON response from Jira API")

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
                    "created": att.get("created"),
                }
            )
        return attachments
