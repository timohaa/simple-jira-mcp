"""Jira search operation implementation."""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.jira.adf import adf_to_text
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
                return self._handle_response(response, params.fields)
        except httpx.RequestError as e:
            logger.exception("Request failed for JQL search")
            return error_response(JIRA_ERROR, f"Request failed: {e}")

    def _handle_response(
        self, response: httpx.Response, requested_fields: list[str]
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
        return self._transform_results(data, requested_fields)

    def _transform_results(
        self, data: dict[str, Any], requested_fields: list[str]
    ) -> dict[str, Any]:
        """Transform raw Jira search results to clean format.

        The /search/jql endpoint has no total count; pagination state comes
        from isLast and nextPageToken only.
        """
        issues = [
            self._transform_issue(issue, requested_fields)
            for issue in data.get("issues", [])
        ]

        result: dict[str, Any] = {
            "issues": issues,
            "is_last": data.get("isLast", True),
        }

        next_token = data.get("nextPageToken")
        if next_token:
            result["next_page_token"] = next_token

        return result

    def _transform_issue(
        self, issue: dict[str, Any], requested_fields: list[str]
    ) -> dict[str, Any]:
        """Transform one raw issue, emitting only the requested fields."""
        fields = issue.get("fields", {})
        extractors: dict[str, tuple[str, Any]] = {
            "summary": ("summary", fields.get("summary")),
            "status": ("status", self._extract_name(fields.get("status"))),
            "assignee": (
                "assignee",
                self._extract_display_name(fields.get("assignee")),
            ),
            "reporter": (
                "reporter",
                self._extract_display_name(fields.get("reporter")),
            ),
            "priority": ("priority", self._extract_name(fields.get("priority"))),
            "resolution": ("resolution", self._extract_name(fields.get("resolution"))),
            "issuetype": ("issue_type", self._extract_name(fields.get("issuetype"))),
            "labels": ("labels", fields.get("labels", [])),
            "created": ("created", self._format_date(fields.get("created"))),
            "updated": ("updated", self._format_date(fields.get("updated"))),
            "description": ("description", adf_to_text(fields.get("description"))),
            "comment": ("comments", self._extract_comments(fields.get("comment", {}))),
            "attachment": (
                "attachments",
                self._extract_attachments(fields.get("attachment", [])),
            ),
            "project": ("project", self._extract_key(fields.get("project"))),
        }

        result: dict[str, Any] = {"key": issue.get("key")}
        for name in requested_fields:
            if name in extractors:
                output_key, value = extractors[name]
                result[output_key] = value
        result["url"] = f"{self.base_url}/browse/{issue.get('key')}"
        return result
