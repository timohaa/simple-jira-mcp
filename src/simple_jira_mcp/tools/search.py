"""Search issues tool implementation."""

from collections.abc import Sequence

from simple_jira_mcp.jira.client import get_client
from simple_jira_mcp.utils.errors import (
    UNBOUNDED_QUERY,
    VALIDATION_ERROR,
    ErrorResponse,
    ToolResult,
    error_response,
    is_error,
)
from simple_jira_mcp.utils.validation import (
    BOUNDING_KEYWORDS,
    has_disallowed_jql_chars,
    is_bounded_query,
    validate_limit,
    validate_search_fields,
)


def _validate_jql(jql: str) -> ErrorResponse | None:
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
            "JQL query must include at least one bounding clause: "
            f"{', '.join(sorted(BOUNDING_KEYWORDS))}. "
            "Scoping to a project is not required.",
        )

    return None


def _validate_search_params(
    jql: str,
    limit: int,
    fields: Sequence[str] | None,
) -> ErrorResponse | None:
    """Validate search parameters, returning error response or None if valid."""
    jql_error = _validate_jql(jql)
    if jql_error:
        return jql_error

    if not validate_limit(limit):
        return error_response(VALIDATION_ERROR, "Limit must be between 1 and 100")

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
    next_page_token: str | None = None,
    fields: Sequence[str] | None = None,
) -> ToolResult:
    """Search for Jira issues using JQL.

    Args:
        jql: JQL query string; must contain at least one bounding clause.
            Values that are JQL reserved words need quoting (project = "ON").
        config_id: Configuration ID to use.
        limit: Maximum results to return (1-100).
        next_page_token: Token for cursor-based pagination.
        fields: Specific fields to return.

    Returns:
        Search results or error response.
    """
    validation_error = _validate_search_params(jql, limit, fields)
    if validation_error:
        return validation_error

    client = get_client(config_id)
    if is_error(client):
        return client
    return await client.search(
        jql,
        max_results=limit,
        next_page_token=next_page_token,
        fields=None if fields is None else list(fields),
    )
