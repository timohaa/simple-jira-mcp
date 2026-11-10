"""Sprint listing and issue move tool implementations."""

from simple_jira_mcp.jira.client import get_client
from simple_jira_mcp.utils.errors import (
    VALIDATION_ERROR,
    ToolResult,
    error_response,
    is_error,
)
from simple_jira_mcp.utils.validation import (
    parse_sprint_states,
    validate_issue_key,
    validate_project_key,
)


def _sprint_scope_error(
    project_key: str | None, board_id: int | None
) -> ToolResult | None:
    """Return a validation error for the project/board selector, if invalid."""
    if board_id is not None:
        if board_id < 1:
            return error_response(
                VALIDATION_ERROR, "board_id must be a positive integer"
            )
        return None
    if not (project_key and project_key.strip()):
        return error_response(
            VALIDATION_ERROR, "Either project_key or board_id is required"
        )
    key = project_key.strip().upper()
    if not validate_project_key(key):
        return error_response(
            VALIDATION_ERROR,
            f"Invalid project key format: '{key}'. Expected format: PROJECT",
        )
    return None


async def list_sprints(
    project_key: str | None = None,
    board_id: int | None = None,
    state: str = "active,future",
    config_id: str | None = None,
) -> ToolResult:
    """List sprints of a board, or of every board in a project."""
    scope_error = _sprint_scope_error(project_key, board_id)
    if scope_error is not None:
        return scope_error
    states = parse_sprint_states(state)
    if states is None:
        return error_response(
            VALIDATION_ERROR,
            f"Invalid state: '{state}'. Use a comma-separated list of "
            "active, future, closed",
        )
    client = get_client(config_id)
    if is_error(client):
        return client
    key = project_key.strip().upper() if project_key and board_id is None else None
    return await client.list_sprints(project_key=key, board_id=board_id, states=states)


async def move_issues_to_sprint(
    sprint_id: int, issue_keys: list[str], config_id: str | None = None
) -> ToolResult:
    """Move issues into a sprint and return the moved keys."""
    if sprint_id < 1:
        return error_response(VALIDATION_ERROR, "sprint_id must be a positive integer")
    keys = list(dict.fromkeys(key.strip().upper() for key in issue_keys))
    if not keys:
        return error_response(VALIDATION_ERROR, "At least one issue key is required")
    for key in keys:
        if not validate_issue_key(key):
            return error_response(
                VALIDATION_ERROR,
                f"Invalid issue key format: '{key}'. Expected format: PROJECT-123",
            )
    client = get_client(config_id)
    if is_error(client):
        return client
    return await client.move_issues_to_sprint(sprint_id, keys)
