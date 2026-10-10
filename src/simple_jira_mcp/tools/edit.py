"""Issue update and delete tool implementations."""

from typing import Any

from simple_jira_mcp.jira.edit import UpdateIssueParams
from simple_jira_mcp.tools.create import MAX_SUMMARY_LENGTH
from simple_jira_mcp.tools.workflow import client_for_issue
from simple_jira_mcp.utils.errors import (
    VALIDATION_ERROR,
    ToolResult,
    error_response,
    is_error,
)


async def update_issue(
    issue_key: str,
    summary: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    assignee_account_id: str | None = None,
    fields: dict[str, Any] | None = None,
    config_id: str | None = None,
) -> ToolResult:
    """Update fields on an issue. Omitted parameters leave their field unchanged.

    Labels replace the current set. Other fields, and null values that clear a
    field, go in `fields` in Jira REST format.
    """
    issue_key = issue_key.strip().upper()
    client = client_for_issue(issue_key, config_id)
    if is_error(client):
        return client
    if summary is not None:
        summary = summary.strip()
        if not summary:
            return error_response(VALIDATION_ERROR, "Summary must not be empty")
        if len(summary) > MAX_SUMMARY_LENGTH:
            return error_response(
                VALIDATION_ERROR,
                f"Summary exceeds maximum length of {MAX_SUMMARY_LENGTH} characters",
            )
    if priority is not None and not priority.strip():
        return error_response(VALIDATION_ERROR, "Priority must not be empty")
    if assignee_account_id is not None and not assignee_account_id.strip():
        return error_response(
            VALIDATION_ERROR,
            "Assignee account ID must not be empty. To unassign, pass "
            'fields={"assignee": null}',
        )
    params = UpdateIssueParams(
        summary=summary,
        description=description,
        priority=priority,
        labels=labels,
        assignee_account_id=assignee_account_id,
        fields=fields,
    )
    return await client.update_issue(issue_key, params)


async def delete_issue(
    issue_key: str, delete_subtasks: bool = False, config_id: str | None = None
) -> ToolResult:
    """Permanently delete an issue. Jira cannot restore deleted issues."""
    issue_key = issue_key.strip().upper()
    client = client_for_issue(issue_key, config_id)
    if is_error(client):
        return client
    return await client.delete_issue(issue_key, delete_subtasks=delete_subtasks)
