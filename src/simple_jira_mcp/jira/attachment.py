"""Jira attachment download operation implementation."""

import logging
from pathlib import Path
from typing import Any

import anyio
import httpx

from simple_jira_mcp.jira.base import (
    ATTACHMENT_PATH,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNAUTHORIZED,
    JiraClientBase,
)
from simple_jira_mcp.utils.errors import (
    ATTACHMENT_NOT_FOUND,
    AUTH_FAILED,
    DOWNLOAD_FAILED,
    RATE_LIMITED,
    ErrorResponse,
    error_response,
)
from simple_jira_mcp.utils.validation import sanitize_filename

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

        The file is saved as `<output_dir>/<issue_key>/<filename>`. If that
        path is taken, the attachment ID is appended to the stem so that
        same-named attachments on one issue do not overwrite each other.

        Args:
            attachment_id: The attachment ID.
            output_dir: Directory to save the file.
            issue_key: The issue key (for subdirectory).
            filename: The original filename.

        Returns:
            Download result or error response.
        """
        url = f"{self.base_url}{ATTACHMENT_PATH}/{attachment_id}"
        target = anyio.Path(output_dir / issue_key / sanitize_filename(filename))

        try:
            async with self._http.stream("GET", url, follow_redirects=True) as response:
                status_error = self._get_status_error(response.status_code)
                if status_error:
                    return status_error

                await target.parent.mkdir(parents=True, exist_ok=True)
                if await target.exists():
                    target = target.with_name(
                        f"{target.stem}-{attachment_id}{target.suffix}"
                    )
                logger.info(
                    "Downloading attachment %s for issue %s to %s",
                    attachment_id,
                    issue_key,
                    target,
                )
                size_bytes = await self._write_stream(response, target)
                content_type = response.headers.get(
                    "content-type", "application/octet-stream"
                )
        except httpx.RequestError as e:
            logger.exception("Request failed for download_attachment")
            return error_response(DOWNLOAD_FAILED, f"Download failed: {e}")
        except OSError as e:
            logger.exception("File write failed for download_attachment")
            return error_response(DOWNLOAD_FAILED, f"File write failed: {e}")

        return {
            "success": True,
            "filename": target.name,
            "path": str(target),
            "size_kb": round(size_bytes / 1024, 2),
            "mime_type": content_type,
        }

    @staticmethod
    async def _write_stream(response: httpx.Response, target: anyio.Path) -> int:
        """Write the response body to target in chunks; return the byte count."""
        size_bytes = 0
        try:
            async with await target.open("wb") as file:
                async for chunk in response.aiter_bytes():
                    await file.write(chunk)
                    size_bytes += len(chunk)
        except (httpx.RequestError, OSError):
            # Don't leave a truncated file that looks like a finished download.
            await target.unlink(missing_ok=True)
            raise
        return size_bytes

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
