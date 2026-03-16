"""Get issue tool implementation."""

from typing import Any

from src.config import get_config
from src.jira.client import JiraClient
from src.utils.errors import CONFIG_NOT_FOUND, VALIDATION_ERROR, error_response
from src.utils.validation import validate_issue_key


async def get_issue(
    issue_key: str,
    config_id: str | None = None,
    include_comments: bool = True,
    include_attachments: bool = True,
) -> dict[str, Any]:
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

    config = get_config(config_id)
    if not config:
        msg = f"Configuration '{config_id}' not found"
        if not config_id:
            msg = "No configuration available"
        return error_response(CONFIG_NOT_FOUND, msg)

    client = JiraClient(config)
    return await client.get_issue(
        issue_key,
        include_comments=include_comments,
        include_attachments=include_attachments,
    )
