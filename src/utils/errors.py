"""Error handling utilities for Jira MCP Server."""

from typing import Any

# Type alias for error responses (matches TypedDict structure but is dict[str, Any])
ErrorResponse = dict[str, Any]


# Centralized error codes used across tools
AUTH_FAILED = "AUTH_FAILED"
CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
ISSUE_NOT_FOUND = "ISSUE_NOT_FOUND"
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
ATTACHMENT_NOT_FOUND = "ATTACHMENT_NOT_FOUND"
INVALID_JQL = "INVALID_JQL"
UNBOUNDED_QUERY = "UNBOUNDED_QUERY"
INVALID_ISSUE_TYPE = "INVALID_ISSUE_TYPE"
INVALID_PRIORITY = "INVALID_PRIORITY"
VALIDATION_ERROR = "VALIDATION_ERROR"
DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
RATE_LIMITED = "RATE_LIMITED"
JIRA_ERROR = "JIRA_ERROR"


def error_response(code: str, message: str) -> dict[str, Any]:
    """Create a standardized error response.

    Args:
        code: Error code (e.g., ISSUE_NOT_FOUND).
        message: Human-readable error message.

    Returns:
        Structured error response dict.
    """
    return {
        "isError": True,
        "error": {
            "code": code,
            "message": message,
        },
    }
