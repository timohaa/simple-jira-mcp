"""Jira get issue operation implementation."""

import logging
from typing import Any

import httpx

from src.jira.adf import adf_to_text
from src.jira.base import (
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNAUTHORIZED,
    ISSUE_PATH,
    JiraClientBase,
)
from src.utils.errors import (
    AUTH_FAILED,
    ISSUE_NOT_FOUND,
    JIRA_ERROR,
    RATE_LIMITED,
    ErrorResponse,
    error_response,
)

logger = logging.getLogger(__name__)


class IssueOperation(JiraClientBase):
    """Handles Jira get issue operations."""

    async def get_issue(
        self,
        issue_key: str,
        *,
        include_comments: bool = True,
        include_attachments: bool = True,
    ) -> dict[str, Any] | ErrorResponse:
        """Get detailed information for a single issue.

        Args:
            issue_key: The Jira issue key (e.g., "ONE-123").
            include_comments: Whether to include comments.
            include_attachments: Whether to include attachment metadata.

        Returns:
            Issue details or error response.
        """
        expand = []
        if include_comments:
            expand.append("renderedFields")

        url = f"{self.base_url}{ISSUE_PATH}/{issue_key}"
        params: dict[str, str] = {}
        if expand:
            params["expand"] = ",".join(expand)

        try:
            async with self._create_client() as client:
                response = await client.get(
                    url,
                    params=params,
                    auth=self._get_auth(),
                )
                return self._handle_response(
                    response, include_comments, include_attachments
                )
        except httpx.RequestError as e:
            logger.exception("Request failed for get_issue")
            return error_response(JIRA_ERROR, f"Request failed: {e}")

    def _handle_response(
        self,
        response: httpx.Response,
        include_comments: bool,
        include_attachments: bool,
    ) -> dict[str, Any] | ErrorResponse:
        """Handle get_issue response."""
        if response.status_code == HTTP_UNAUTHORIZED:
            return error_response(AUTH_FAILED, "Invalid credentials")
        if response.status_code == HTTP_NOT_FOUND:
            return error_response(ISSUE_NOT_FOUND, "Issue not found")
        if response.status_code == HTTP_TOO_MANY_REQUESTS:
            return error_response(RATE_LIMITED, "Too many requests to Jira API")
        if response.status_code != HTTP_OK:
            return error_response(JIRA_ERROR, f"Jira API error: {response.status_code}")

        data = response.json()
        return self._transform_issue(data, include_comments, include_attachments)

    def _transform_issue(
        self,
        data: dict[str, Any],
        include_comments: bool,
        include_attachments: bool,
    ) -> dict[str, Any]:
        """Transform raw Jira issue to clean format."""
        fields = data.get("fields", {})
        key = data.get("key", "")

        result: dict[str, Any] = {
            "key": key,
            "summary": fields.get("summary"),
            "description": adf_to_text(fields.get("description")),
            "status": self._extract_name(fields.get("status")),
            "assignee": self._extract_display_name(fields.get("assignee")),
            "reporter": self._extract_display_name(fields.get("reporter")),
            "priority": self._extract_name(fields.get("priority")),
            "issue_type": self._extract_name(fields.get("issuetype")),
            "labels": fields.get("labels", []),
            "created": self._format_date(fields.get("created")),
            "updated": self._format_date(fields.get("updated")),
            "resolved": self._format_date(fields.get("resolutiondate")),
            "url": f"{self.base_url}/browse/{key}",
        }

        if include_comments:
            result["comments"] = self._extract_comments(fields.get("comment", {}))

        if include_attachments:
            result["attachments"] = self._extract_attachments(
                fields.get("attachment", [])
            )

        return result

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
