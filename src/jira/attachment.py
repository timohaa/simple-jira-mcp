"""Jira attachment download operation implementation."""

import logging
from pathlib import Path
from typing import Any

import httpx

from src.jira.base import (
    ATTACHMENT_PATH,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNAUTHORIZED,
    JiraClientBase,
)
from src.utils.errors import (
    ATTACHMENT_NOT_FOUND,
    AUTH_FAILED,
    DOWNLOAD_FAILED,
    RATE_LIMITED,
    ErrorResponse,
    error_response,
)
from src.utils.validation import sanitize_filename

logger = logging.getLogger(__name__)


class AttachmentOperation(JiraClientBase):
    """Handles Jira attachment download operations."""

    async def download_attachment(
        self,
        attachment_id: str,
        output_dir: Path,
        issue_key: str,
        filename: str,
    ) -> dict[str, Any] | ErrorResponse:
        """Download an attachment to a local file.

        Args:
            attachment_id: The attachment ID.
            output_dir: Directory to save the file.
            issue_key: The issue key (for subdirectory).
            filename: The original filename.

        Returns:
            Download result or error response.
        """
        url = f"{self.base_url}{ATTACHMENT_PATH}/{attachment_id}"

        safe_filename = sanitize_filename(filename)
        target_path = output_dir / issue_key / safe_filename
        logger.info(
            "Downloading attachment %s for issue %s to %s",
            attachment_id,
            issue_key,
            target_path,
        )

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            async with self._create_client() as client:
                response = await client.get(
                    url,
                    auth=self._get_auth(),
                    follow_redirects=True,
                )

                status_error = self._get_status_error(response.status_code)
                if status_error:
                    return status_error

                target_path.write_bytes(response.content)

                content_type = response.headers.get(
                    "content-type", "application/octet-stream"
                )
                size_kb = round(len(response.content) / 1024, 2)

                return {
                    "success": True,
                    "filename": safe_filename,
                    "path": str(target_path),
                    "size_kb": size_kb,
                    "mime_type": content_type,
                }

        except httpx.RequestError as e:
            logger.exception("Request failed for download_attachment")
            return error_response(DOWNLOAD_FAILED, f"Download failed: {e}")
        except OSError as e:
            logger.exception("File write failed for download_attachment")
            return error_response(DOWNLOAD_FAILED, f"File write failed: {e}")

    def _get_status_error(self, status_code: int) -> ErrorResponse | None:
        """Return error response for non-OK status codes, or None."""
        status_errors = {
            HTTP_UNAUTHORIZED: (AUTH_FAILED, "Invalid credentials"),
            HTTP_NOT_FOUND: (ATTACHMENT_NOT_FOUND, "Attachment not found"),
            HTTP_TOO_MANY_REQUESTS: (RATE_LIMITED, "Too many requests"),
        }
        if status_code in status_errors:
            code, msg = status_errors[status_code]
            return error_response(code, msg)
        if status_code != HTTP_OK:
            return error_response(DOWNLOAD_FAILED, f"Download failed: {status_code}")
        return None
