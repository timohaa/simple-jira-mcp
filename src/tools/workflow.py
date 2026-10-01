"""Issue workflow and comment tool implementations."""

from typing import Any

from src.config import get_config
from src.jira.client import JiraClient
from src.utils.errors import (
    CONFIG_NOT_FOUND,
    VALIDATION_ERROR,
    ErrorResponse,
    error_response,
)
from src.utils.validation import validate_issue_key


def _get_client(issue_key: str, config_id: str | None) -> JiraClient | ErrorResponse:
    """Validate a normalized issue key and resolve the selected configuration."""
    if not issue_key:
        return error_response(VALIDATION_ERROR, "Issue key is required")
    if not validate_issue_key(issue_key):
        return error_response(
            VALIDATION_ERROR,
            f"Invalid issue key format: '{issue_key}'. Expected format: PROJECT-123",
        )
    config = get_config(config_id)
    if not config:
        message = (
            f"Configuration '{config_id}' not found"
            if config_id
            else "No configuration available"
        )
        return error_response(CONFIG_NOT_FOUND, message)
    return JiraClient(config)


async def get_transitions(
    issue_key: str, config_id: str | None = None
) -> dict[str, Any]:
    """Get available issue transitions, target statuses, and screen field metadata."""
    issue_key = issue_key.strip().upper()
    client = _get_client(issue_key, config_id)
    if isinstance(client, dict):
        return client
    return await client.get_transitions(issue_key)


async def transition_issue(
    issue_key: str,
    transition: str,
    comment: str | None = None,
    resolution: str | None = None,
    fields: dict[str, Any] | None = None,
    config_id: str | None = None,
) -> dict[str, Any]:
    """Transition an issue by ID or case-insensitive transition/target-status name.

    Jira sets resolutiondate itself; the API cannot edit it. Record the actual
    completion date in the comment. Fields must be accepted by the transition screen.
    """
    issue_key = issue_key.strip().upper()
    client = _get_client(issue_key, config_id)
    if isinstance(client, dict):
        return client
    if not transition.strip():
        return error_response(VALIDATION_ERROR, "Transition is required")
    if comment is not None and not comment.strip():
        return error_response(VALIDATION_ERROR, "Comment must not be empty")
    if resolution is not None and not resolution.strip():
        return error_response(VALIDATION_ERROR, "Resolution must not be empty")
    return await client.transition_issue(
        issue_key, transition, comment=comment, resolution=resolution, fields=fields
    )


async def add_comment(
    issue_key: str, body: str, config_id: str | None = None
) -> dict[str, Any]:
    """Add a plain-text comment and return its ID and creation time."""
    issue_key = issue_key.strip().upper()
    client = _get_client(issue_key, config_id)
    if isinstance(client, dict):
        return client
    if not body.strip():
        return error_response(VALIDATION_ERROR, "Comment body is required")
    return await client.add_comment(issue_key, body)
