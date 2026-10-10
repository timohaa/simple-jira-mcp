"""Download attachment tool implementation."""

from pathlib import Path

from simple_jira_mcp.jira.client import get_client
from simple_jira_mcp.utils.errors import (
    ATTACHMENT_NOT_FOUND,
    VALIDATION_ERROR,
    ErrorResponse,
    ToolResult,
    error_response,
    is_error,
)
from simple_jira_mcp.utils.validation import validate_attachment_id, validate_issue_key


def _validate_inputs(  # noqa: PLR0911
    issue_key: str,
    attachment_id: str,
    output_dir: str | None,
) -> tuple[str, str, Path] | ErrorResponse:
    """Validate and normalize all inputs.

    Returns:
        Tuple of (normalized_key, normalized_att_id, out_path) or ErrorResponse.
    """
    if not issue_key or not issue_key.strip():
        return error_response(VALIDATION_ERROR, "Issue key is required")
    normalized_key = issue_key.strip().upper()
    if not validate_issue_key(normalized_key):
        return error_response(
            VALIDATION_ERROR,
            f"Invalid issue key format: '{normalized_key}'. Expected: PROJECT-123",
        )

    if not attachment_id or not attachment_id.strip():
        return error_response(VALIDATION_ERROR, "Attachment ID is required")
    normalized_att_id = attachment_id.strip()
    if not validate_attachment_id(normalized_att_id):
        return error_response(
            VALIDATION_ERROR,
            f"Invalid attachment ID: '{normalized_att_id}'. Must be numeric.",
        )

    if not output_dir:
        out_path = Path.cwd()
    else:
        out_path = Path(output_dir)
        if not out_path.exists():
            return error_response(
                VALIDATION_ERROR,
                f"Output directory does not exist: '{output_dir}'",
            )
        if not out_path.is_dir():
            return error_response(
                VALIDATION_ERROR,
                f"Output path is not a directory: '{output_dir}'",
            )

    return (normalized_key, normalized_att_id, out_path)


async def download_attachment(
    issue_key: str,
    attachment_id: str,
    output_dir: str | None = None,
    config_id: str | None = None,
) -> ToolResult:
    """Download an attachment from a Jira issue.

    Args:
        issue_key: The Jira issue key (e.g., "ONE-123").
        attachment_id: The attachment ID from get_issue response.
        output_dir: Directory to save the file (default: current directory).
        config_id: Configuration ID to use.

    Returns:
        Download result or error response.
    """
    validation_result = _validate_inputs(issue_key, attachment_id, output_dir)
    if not isinstance(validation_result, tuple):
        return validation_result
    normalized_key, normalized_att_id, out_path = validation_result

    client = get_client(config_id)
    if is_error(client):
        return client

    # Fetch the issue first to resolve the attachment filename from its metadata
    issue_result = await client.get_issue(
        normalized_key, include_comments=False, include_attachments=True
    )

    if is_error(issue_result):
        return issue_result

    attachments = issue_result.get("attachments", [])
    attachment_info = next(
        (att for att in attachments if att.get("id") == normalized_att_id),
        None,
    )

    if not attachment_info:
        return error_response(
            ATTACHMENT_NOT_FOUND,
            f"Attachment '{normalized_att_id}' not found on issue '{normalized_key}'",
        )

    filename = attachment_info.get("filename") or "attachment"

    return await client.download_attachment(
        normalized_att_id,
        out_path,
        normalized_key,
        filename,
    )
