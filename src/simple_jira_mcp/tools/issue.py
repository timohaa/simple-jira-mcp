"""Get issue tool implementation."""

from simple_jira_mcp.jira.client import get_client
from simple_jira_mcp.utils.errors import (
    VALIDATION_ERROR,
    ToolResult,
    error_response,
    is_error,
)
from simple_jira_mcp.utils.validation import validate_issue_key


async def get_issue(
    issue_key: str,
    config_id: str | None = None,
    include_comments: bool = True,
    include_attachments: bool = True,
) -> ToolResult:
    """Fetch complete details for a single Jira issue.

    Args:
        issue_key: The Jira issue key (e.g., "ONE-123").
        config_id: Configuration ID to use.
        include_comments: Whether to include comments.
        include_attachments: Whether to include attachment metadata.

    Returns:
        Issue details or error response.
    """
    if not issue_key or not issue_key.strip():
        return error_response(VALIDATION_ERROR, "Issue key is required")

    issue_key = issue_key.strip().upper()

    if not validate_issue_key(issue_key):
        return error_response(
            VALIDATION_ERROR,
            f"Invalid issue key format: '{issue_key}'. Expected format: PROJECT-123",
        )

    client = get_client(config_id)
    if is_error(client):
        return client
    return await client.get_issue(
        issue_key,
        include_comments=include_comments,
        include_attachments=include_attachments,
    )
