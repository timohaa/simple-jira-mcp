"""Jira issue update and delete operations."""

from dataclasses import dataclass
from typing import Any

from simple_jira_mcp.jira.adf import text_to_adf
from simple_jira_mcp.jira.base import HTTP_NO_CONTENT, ISSUE_PATH, JiraClientBase
from simple_jira_mcp.utils.errors import (
    INVALID_PRIORITY,
    VALIDATION_ERROR,
    ErrorResponse,
    error_response,
    is_error,
)


@dataclass
class UpdateIssueParams:
    """Changes to apply to a Jira issue. None leaves a field unchanged."""

    summary: str | None = None
    description: str | None = None
    priority: str | None = None
    labels: list[str] | None = None
    assignee_account_id: str | None = None
    fields: dict[str, Any] | None = None


class EditOperation(JiraClientBase):
    """Handle issue updates and deletion."""

    async def update_issue(
        self, issue_key: str, params: UpdateIssueParams
    ) -> dict[str, Any] | ErrorResponse:
        """Set the given fields on an issue and report which ones were sent."""
        fields = self._build_fields(params)
        if is_error(fields):
            return fields
        result = await self._request(
            "PUT",
            f"{self.base_url}{ISSUE_PATH}/{issue_key}",
            payload={"fields": fields},
            success_status=HTTP_NO_CONTENT,
        )
        if is_error(result):
            rejected = "priority: " in result["error"]["message"]
            if params.priority is not None and rejected:
                return await self._invalid_priority(issue_key, params.priority)
            return result
        return {
            "key": issue_key,
            "url": f"{self.base_url}/browse/{issue_key}",
            "updated": sorted(fields),
        }

    async def _invalid_priority(self, issue_key: str, priority: str) -> ErrorResponse:
        """Name the rejected priority and list the ones the issue accepts."""
        message = f"Priority '{priority}' is not valid for {issue_key}."
        meta = await self._request(
            "GET", f"{self.base_url}{ISSUE_PATH}/{issue_key}/editmeta"
        )
        if is_error(meta):
            return error_response(INVALID_PRIORITY, message)
        allowed = meta.get("fields", {}).get("priority", {}).get("allowedValues", [])
        names = [item["name"] for item in allowed if item.get("name")]
        if names:
            message += f" Valid priorities: {', '.join(names)}."
        return error_response(INVALID_PRIORITY, message)

    async def delete_issue(
        self, issue_key: str, *, delete_subtasks: bool = False
    ) -> dict[str, Any] | ErrorResponse:
        """Delete an issue, and its subtasks when requested."""
        result = await self._request(
            "DELETE",
            f"{self.base_url}{ISSUE_PATH}/{issue_key}",
            params={"deleteSubtasks": "true" if delete_subtasks else "false"},
            success_status=HTTP_NO_CONTENT,
        )
        if is_error(result):
            return result
        return {"key": issue_key, "deleted": True}

    @staticmethod
    def _build_fields(params: UpdateIssueParams) -> dict[str, Any] | ErrorResponse:
        """Convert the named parameters to Jira REST fields and merge raw fields."""
        named: dict[str, Any] = {}
        if params.summary is not None:
            named["summary"] = params.summary
        if params.description is not None:
            named["description"] = text_to_adf(params.description)
        if params.priority is not None:
            named["priority"] = {"name": params.priority}
        if params.labels is not None:
            named["labels"] = params.labels
        if params.assignee_account_id is not None:
            named["assignee"] = {"accountId": params.assignee_account_id}

        raw = params.fields or {}
        duplicated = sorted(set(named) & set(raw))
        if duplicated:
            return error_response(
                VALIDATION_ERROR,
                f"Specify {', '.join(duplicated)} either directly or in fields",
            )
        if not named and not raw:
            return error_response(VALIDATION_ERROR, "No fields to update")
        return {**named, **raw}
