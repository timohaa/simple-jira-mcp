"""Error handling utilities for Jira MCP Server."""

from typing import TYPE_CHECKING, Any, Literal, TypedDict

if TYPE_CHECKING:
    from typing_extensions import TypeIs


class ErrorDetail(TypedDict):
    """Error code and human-readable message."""

    code: str
    message: str


class ErrorResponse(TypedDict):
    """In-band error payload returned by tools and client operations."""

    isError: Literal[True]
    error: ErrorDetail


ToolResult = dict[str, Any] | ErrorResponse


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


def is_error(result: object) -> "TypeIs[ErrorResponse]":
    """Tell an error payload apart from a successful result or a client."""
    return isinstance(result, dict) and result.get("isError") is True


def error_response(code: str, message: str) -> ErrorResponse:
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
