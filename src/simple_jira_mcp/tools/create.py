"""Create issue tool implementation."""

from simple_jira_mcp.jira.client import get_client
from simple_jira_mcp.jira.create import CreateIssueParams
from simple_jira_mcp.utils.errors import (
    VALIDATION_ERROR,
    ToolResult,
    error_response,
    is_error,
)
from simple_jira_mcp.utils.validation import validate_project_key

MAX_SUMMARY_LENGTH = 255


async def create_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    assignee_account_id: str | None = None,
    config_id: str | None = None,
) -> ToolResult:
    """Create a new Jira issue.

    Args:
        project_key: The project key (e.g., "ONE").
        summary: The issue title/summary (max 255 chars).
        issue_type: The issue type (default: "Task").
        description: Optional description (plain text).
        priority: Optional priority level.
        labels: Optional list of labels.
        assignee_account_id: Optional assignee account ID.
        config_id: Configuration ID to use.

    Returns:
        Created issue info or error response.
    """
    if not project_key or not project_key.strip():
        return error_response(VALIDATION_ERROR, "Project key is required")

    project_key = project_key.strip().upper()

    if not validate_project_key(project_key):
        return error_response(
            VALIDATION_ERROR,
            f"Invalid project key format: '{project_key}'. "
            "Expected format: PROJECT (uppercase letters and numbers)",
        )

    if not summary or not summary.strip():
        return error_response(VALIDATION_ERROR, "Summary is required")

    summary = summary.strip()

    if len(summary) > MAX_SUMMARY_LENGTH:
        return error_response(
            VALIDATION_ERROR,
            f"Summary exceeds maximum length of {MAX_SUMMARY_LENGTH} characters",
        )

    if not issue_type or not issue_type.strip():
        issue_type = "Task"

    client = get_client(config_id)
    if is_error(client):
        return client
    params = CreateIssueParams(
        project_key=project_key,
        summary=summary,
        issue_type=issue_type,
        description=description,
        priority=priority,
        labels=labels,
        assignee_account_id=assignee_account_id,
    )
    return await client.create_issue(params)
