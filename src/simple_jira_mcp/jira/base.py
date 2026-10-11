"""Base Jira client with shared utilities and constants."""

import logging
from typing import Any

import httpx

from simple_jira_mcp.config import JiraConfig
from simple_jira_mcp.jira.adf import adf_to_text
from simple_jira_mcp.utils.errors import (
    AUTH_FAILED,
    INVALID_PRIORITY,
    ISSUE_NOT_FOUND,
    JIRA_ERROR,
    RATE_LIMITED,
    VALIDATION_ERROR,
    ErrorResponse,
    error_response,
)

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

    Create the client on first use to bind it to the requesting event loop.
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

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        success_status: int = HTTP_OK,
    ) -> dict[str, Any] | ErrorResponse:
        """Send an issue request and map the response to a result or error."""
        try:
            response = await self._http.request(
                method, url, params=params, json=payload
            )
        except httpx.RequestError as e:
            logger.exception("Request failed for %s %s", method, url)
            return error_response(JIRA_ERROR, f"Request failed: {e}")

        status_errors = {
            HTTP_UNAUTHORIZED: (AUTH_FAILED, "Invalid credentials"),
            HTTP_NOT_FOUND: (ISSUE_NOT_FOUND, "Issue not found"),
            HTTP_TOO_MANY_REQUESTS: (RATE_LIMITED, "Too many requests to Jira API"),
        }
        if response.status_code in status_errors:
            code, message = status_errors[response.status_code]
            return error_response(code, message)
        if response.status_code == success_status:
            if success_status == HTTP_NO_CONTENT:
                return {}
            return self._json_object(response)

        message = f"Jira API error: {response.status_code}"
        try:
            data = response.json()
            errors = data.get("errors", {})
            messages = data.get("errorMessages", [])
            if errors:
                message = ", ".join(f"{key}: {value}" for key, value in errors.items())
            elif messages:
                message = str(messages[0])
        except (ValueError, AttributeError, TypeError):
            pass
        code = (
            VALIDATION_ERROR if response.status_code == HTTP_BAD_REQUEST else JIRA_ERROR
        )
        return error_response(code, message)

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
    def _priority_error(message: str, allowed: list[dict[str, Any]]) -> ErrorResponse:
        """Build INVALID_PRIORITY, appending the allowed names when known."""
        names = [item["name"] for item in allowed if item.get("name")]
        if names:
            message += f" Valid priorities: {', '.join(names)}."
        return error_response(INVALID_PRIORITY, message)

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
