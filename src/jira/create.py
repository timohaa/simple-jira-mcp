"""Jira create issue operation implementation."""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from src.jira.adf import text_to_adf
from src.jira.base import (
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNAUTHORIZED,
    ISSUE_PATH,
    JiraClientBase,
)
from src.utils.errors import (
    AUTH_FAILED,
    INVALID_ISSUE_TYPE,
    INVALID_PRIORITY,
    JIRA_ERROR,
    PROJECT_NOT_FOUND,
    RATE_LIMITED,
    VALIDATION_ERROR,
    ErrorResponse,
    error_response,
)

logger = logging.getLogger(__name__)


@dataclass
class CreateIssueParams:
    """Parameters for creating a Jira issue."""

    project_key: str
    summary: str
    issue_type: str = "Task"
    description: str | None = None
    priority: str | None = None
    labels: list[str] | None = None
    assignee_account_id: str | None = None


class CreateOperation(JiraClientBase):
    """Handles Jira create issue operations."""

    async def create_issue(
        self, params: CreateIssueParams
    ) -> dict[str, Any] | ErrorResponse:
        """Create a new issue.

        Args:
            params: Issue creation parameters.

        Returns:
            Created issue info or error response.
        """
        url = f"{self.base_url}{ISSUE_PATH}"

        fields: dict[str, Any] = {
            "project": {"key": params.project_key},
            "summary": params.summary,
            "issuetype": {"name": params.issue_type},
        }

        if params.description:
            fields["description"] = text_to_adf(params.description)

        if params.priority:
            fields["priority"] = {"name": params.priority}

        if params.labels:
            fields["labels"] = params.labels

        if params.assignee_account_id:
            fields["assignee"] = {"accountId": params.assignee_account_id}

        payload = {"fields": fields}

        try:
            async with self._create_client() as client:
                response = await client.post(
                    url,
                    json=payload,
                    auth=self._get_auth(),
                )
                return self._handle_response(response)
        except httpx.RequestError as e:
            logger.exception("Request failed for create_issue")
            return error_response(JIRA_ERROR, f"Request failed: {e}")

    def _handle_response(
        self, response: httpx.Response
    ) -> dict[str, Any] | ErrorResponse:
        """Handle create_issue response."""
        status_error = self._get_status_error(response.status_code)
        if status_error:
            return status_error

        if response.status_code == HTTP_BAD_REQUEST:
            return self._handle_bad_request(response)

        if response.status_code not in (HTTP_OK, HTTP_CREATED):
            return self._handle_unexpected_status(response)

        data = response.json()
        key = data.get("key", "")
        return {
            "key": key,
            "id": data.get("id"),
            "url": f"{self.base_url}/browse/{key}",
        }

    def _get_status_error(self, status_code: int) -> ErrorResponse | None:
        """Return error response for known error status codes, or None."""
        status_errors = {
            HTTP_UNAUTHORIZED: (AUTH_FAILED, "Invalid credentials"),
            HTTP_NOT_FOUND: (PROJECT_NOT_FOUND, "Project not found"),
            HTTP_TOO_MANY_REQUESTS: (RATE_LIMITED, "Too many requests to Jira API"),
        }
        if status_code in status_errors:
            code, msg = status_errors[status_code]
            return error_response(code, msg)
        return None

    def _handle_bad_request(self, response: httpx.Response) -> ErrorResponse:
        """Handle 400 Bad Request response."""
        try:
            data = response.json()
        except Exception:
            return error_response(JIRA_ERROR, "Jira API error: 400")

        errors = data.get("errors", {}) if isinstance(data, dict) else {}
        messages = data.get("errorMessages", []) if isinstance(data, dict) else []

        if isinstance(errors, dict):
            if "issuetype" in errors:
                return error_response(INVALID_ISSUE_TYPE, str(errors["issuetype"]))
            if "priority" in errors:
                return error_response(INVALID_PRIORITY, str(errors["priority"]))
            if errors:
                msg = ", ".join(f"{k}: {v}" for k, v in errors.items())
                return error_response(VALIDATION_ERROR, msg)

        if isinstance(messages, list) and messages:
            return error_response(VALIDATION_ERROR, str(messages[0]))

        return error_response(JIRA_ERROR, "Jira API error: 400")

    def _handle_unexpected_status(self, response: httpx.Response) -> ErrorResponse:
        """Handle unexpected HTTP status codes."""
        try:
            data = response.json()
            errors = data.get("errors", {})
            if errors:
                msg = ", ".join(f"{k}: {v}" for k, v in errors.items())
            else:
                messages = data.get("errorMessages", [])
                msg = messages[0] if messages else f"Status {response.status_code}"
        except Exception:
            msg = f"Jira API error: {response.status_code}"
        return error_response(JIRA_ERROR, msg)
