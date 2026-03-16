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
        target_dir = output_dir / issue_key
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / safe_filename
        logger.info(
            "Downloading attachment %s for issue %s to %s",
            attachment_id,
            issue_key,
            target_path,
        )

        try:
            async with self._create_client() as client:
                response = await client.get(
                    url,
                    auth=self._get_auth(),
                    follow_redirects=True,
                )

                if response.status_code == HTTP_UNAUTHORIZED:
                    return error_response(AUTH_FAILED, "Invalid credentials")
                if response.status_code == HTTP_NOT_FOUND:
                    return error_response(ATTACHMENT_NOT_FOUND, "Attachment not found")
                if response.status_code == HTTP_TOO_MANY_REQUESTS:
                    return error_response(RATE_LIMITED, "Too many requests")
                if response.status_code != HTTP_OK:
                    return error_response(
                        DOWNLOAD_FAILED, f"Download failed: {response.status_code}"
                    )

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
