"""Search issues tool implementation."""

from typing import Any

from src.config import get_config
from src.jira.client import JiraClient
from src.utils.errors import (
    CONFIG_NOT_FOUND,
    UNBOUNDED_QUERY,
    VALIDATION_ERROR,
    error_response,
)
from src.utils.validation import (
    has_disallowed_jql_chars,
    is_bounded_query,
    validate_limit,
    validate_search_fields,
    validate_start_at,
)


def _validate_jql(jql: str) -> dict[str, Any] | None:
    """Validate JQL query, returning error response or None if valid."""
    if not jql or not jql.strip():
        return error_response(VALIDATION_ERROR, "JQL query is required")

    if has_disallowed_jql_chars(jql):
        return error_response(
            VALIDATION_ERROR,
            "JQL query contains disallowed characters (semicolon or newlines)",
        )

    if not is_bounded_query(jql):
        return error_response(
            UNBOUNDED_QUERY,
            "JQL query must include at least one filter "
            "(project, date range, assignee, etc.)",
        )

    return None


def _validate_search_params(
    jql: str,
    limit: int,
    start_at: int,
    fields: list[str] | None,
) -> dict[str, Any] | None:
    """Validate search parameters, returning error response or None if valid."""
    jql_error = _validate_jql(jql)
    if jql_error:
        return jql_error

    if not validate_limit(limit):
        return error_response(VALIDATION_ERROR, "Limit must be between 1 and 100")

    if not validate_start_at(start_at):
        return error_response(VALIDATION_ERROR, "start_at must be >= 0")

    if fields is not None:
        is_valid, invalid_field = validate_search_fields(fields)
        if not is_valid:
            return error_response(
                VALIDATION_ERROR,
                f"Invalid field requested: '{invalid_field}'. Use allowed fields only.",
            )

    return None


async def search_issues(
    jql: str,
    config_id: str | None = None,
    limit: int = 50,
    start_at: int = 0,
    next_page_token: str | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Search for Jira issues using JQL.

    Args:
        jql: JQL query string (must be bounded).
        config_id: Configuration ID to use.
        limit: Maximum results to return (1-100).
        start_at: Deprecated - ignored by Jira API v3.
        next_page_token: Token for cursor-based pagination.
        fields: Specific fields to return.

    Returns:
        Search results or error response.
    """
    # Validate inputs
    validation_error = _validate_search_params(jql, limit, start_at, fields)
    if validation_error:
        return validation_error

    # Get configuration
    config = get_config(config_id)
    if not config:
        if config_id:
            msg = f"Configuration '{config_id}' not found"
        else:
            msg = "No configuration available"
        return error_response(CONFIG_NOT_FOUND, msg)

    # Execute search
    client = JiraClient(config)
    return await client.search(
        jql,
        max_results=limit,
        start_at=start_at,
        next_page_token=next_page_token,
        fields=fields,
    )
