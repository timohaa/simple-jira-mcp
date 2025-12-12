"""Jira search operation implementation."""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.jira.base import (
    HTTP_BAD_REQUEST,
    HTTP_OK,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNAUTHORIZED,
    SEARCH_PATH,
    JiraClientBase,
)
from src.utils.errors import (
    AUTH_FAILED,
    INVALID_JQL,
    JIRA_ERROR,
    RATE_LIMITED,
    ErrorResponse,
    error_response,
)

logger = logging.getLogger(__name__)

# Default fields to return from search
DEFAULT_SEARCH_FIELDS = [
    "summary",
    "status",
    "assignee",
    "priority",
    "updated",
    "created",
    "labels",
    "issuetype",
]


@dataclass
class SearchParams:
    """Parameters for Jira issue search."""

    jql: str
    max_results: int = 50
    start_at: int = 0
    next_page_token: str | None = None
    fields: list[str] = field(default_factory=lambda: DEFAULT_SEARCH_FIELDS.copy())


class SearchOperation(JiraClientBase):
    """Handles Jira search operations."""

    async def search(self, params: SearchParams) -> dict[str, Any] | ErrorResponse:
        """Search for issues using JQL.

        Args:
            params: Search parameters.

        Returns:
            Search results or error response.
        """
        logger.info(
            "Executing JQL search (config_id=%s): %s",
            getattr(self.config, "id", None),
            params.jql,
        )
        # Log deprecation warning if start_at is used
        if params.start_at != 0:
            logger.warning(
                "start_at parameter is deprecated and ignored by Jira API v3. "
                "Use next_page_token for pagination."
            )

        url = f"{self.base_url}{SEARCH_PATH}"
        payload: dict[str, Any] = {
            "jql": params.jql,
            "maxResults": params.max_results,
            "fields": params.fields,
        }

        # Use cursor-based pagination (nextPageToken) instead of startAt
        if params.next_page_token:
            payload["nextPageToken"] = params.next_page_token

        try:
            async with self._create_client() as client:
                response = await client.post(
                    url,
                    json=payload,
                    auth=self._get_auth(),
                )
                return self._handle_response(response)
        except httpx.RequestError as e:
            logger.exception("Request failed for JQL search")
            return error_response(JIRA_ERROR, f"Request failed: {e}")

    def _handle_response(
        self, response: httpx.Response
    ) -> dict[str, Any] | ErrorResponse:
        """Handle search response and transform to clean format."""
        if response.status_code == HTTP_UNAUTHORIZED:
            return error_response(AUTH_FAILED, "Invalid credentials")
        if response.status_code == HTTP_TOO_MANY_REQUESTS:
            return error_response(RATE_LIMITED, "Too many requests to Jira API")
        if response.status_code == HTTP_BAD_REQUEST:
            try:
                data = response.json()
                messages = data.get("errorMessages", [])
                msg = messages[0] if messages else "Invalid JQL query"
            except Exception:
                msg = "Invalid JQL query"
            return error_response(INVALID_JQL, msg)

        if response.status_code != HTTP_OK:
            return error_response(JIRA_ERROR, f"Jira API error: {response.status_code}")

        data = response.json()
        return self._transform_results(data)

    def _transform_results(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform raw Jira search results to clean format."""
        issues = []
        for issue in data.get("issues", []):
            fields = issue.get("fields", {})
            issues.append(
                {
                    "key": issue.get("key"),
                    "summary": fields.get("summary"),
                    "status": self._extract_name(fields.get("status")),
                    "assignee": self._extract_display_name(fields.get("assignee")),
                    "priority": self._extract_name(fields.get("priority")),
                    "issue_type": self._extract_name(fields.get("issuetype")),
                    "labels": fields.get("labels", []),
                    "created": self._format_date(fields.get("created")),
                    "updated": self._format_date(fields.get("updated")),
                    "url": f"{self.base_url}/browse/{issue.get('key')}",
                }
            )

        result: dict[str, Any] = {
            "total": data.get("total", 0),
            "max_results": data.get("maxResults", 50),
            "issues": issues,
        }

        # Include nextPageToken for cursor-based pagination if present
        next_token = data.get("nextPageToken")
        if next_token:
            result["next_page_token"] = next_token

        return result
