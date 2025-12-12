"""Tests for download_attachment tool with mocked Jira API."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import src.config
from src.config import reset_config_state
from src.tools.attachment import download_attachment


@pytest.fixture
def clean_config():
    """Reset config state before and after each test."""
    original = os.environ.get("JIRA_CONFIG_JSON")

    reset_config_state()

    yield

    if original:
        os.environ["JIRA_CONFIG_JSON"] = original
    elif "JIRA_CONFIG_JSON" in os.environ:
        del os.environ["JIRA_CONFIG_JSON"]

    reset_config_state()


@pytest.fixture
def mock_config(clean_config):
    """Set up a test config."""
    config_data = [
        {
            "id": "test",
            "url": "https://test.atlassian.net",
            "email": "test@example.com",
            "token": "test-token",
        }
    ]
    os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
    src.config.load_configs()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for downloads."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestDownloadAttachmentValidation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "issue_key,attachment_id,msg_snippet",
        [
            ("", "12345", "issue key"),
            ("   ", "12345", "issue key"),
            ("invalid", "12345", "format"),
        ],
    )
    async def test_issue_key_validation_errors(
        self, mock_config, issue_key, attachment_id, msg_snippet
    ):
        result = await download_attachment(issue_key, attachment_id)

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert msg_snippet in result["error"]["message"].lower()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "attachment_id,msg_snippet",
        [
            ("", "attachment id"),
            ("abc", "numeric"),
        ],
    )
    async def test_attachment_id_validation_errors(
        self, mock_config, attachment_id, msg_snippet
    ):
        result = await download_attachment("ONE-123", attachment_id)

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert msg_snippet in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_nonexistent_output_dir_returns_error(self, mock_config):
        result = await download_attachment(
            "ONE-123", "12345", output_dir="/nonexistent/path"
        )

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "not exist" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_output_dir_is_file_returns_error(self, mock_config, temp_dir):
        file_path = Path(temp_dir) / "not_a_dir.txt"
        file_path.write_text("test")

        result = await download_attachment(
            "ONE-123", "12345", output_dir=str(file_path)
        )

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "not a directory" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_missing_config_returns_error(self, clean_config):
        result = await download_attachment("ONE-123", "12345")

        assert result["isError"] is True
        assert result["error"]["code"] == "CONFIG_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_unknown_config_id_returns_error(self, mock_config):
        result = await download_attachment("ONE-123", "12345", config_id="unknown")

        assert result["isError"] is True
        assert result["error"]["code"] == "CONFIG_NOT_FOUND"


class TestDownloadAttachmentSuccess:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "issue_key,output_dir_key,filename",
        [
            ("ONE-123", "temp_dir", "screenshot.png"),
            ("one-123", "temp_dir", "file.txt"),
            ("ONE-123", None, "file.txt"),
        ],
    )
    async def test_download_success(
        self, mock_config, temp_dir, issue_key, output_dir_key, filename
    ):
        issue_response = {
            "key": "ONE-123",
            "attachments": [
                {"id": "12345", "filename": filename},
            ],
        }
        base_dir = temp_dir if output_dir_key == "temp_dir" else Path.cwd()
        download_response = {
            "success": True,
            "filename": filename,
            "path": f"{base_dir}/ONE-123/{filename}",
            "size_kb": 1.0,
            "mime_type": "text/plain",
        }

        with (
            patch(
                "src.tools.attachment.JiraClient.get_issue", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.tools.attachment.JiraClient.download_attachment",
                new_callable=AsyncMock,
            ) as mock_download,
        ):
            mock_get.return_value = issue_response
            mock_download.return_value = download_response
            out_dir = None if output_dir_key is None else temp_dir
            result = await download_attachment(issue_key, "12345", output_dir=out_dir)

        assert result["success"] is True
        assert result["filename"] == filename
        mock_get.assert_called_once()
        assert mock_get.call_args.args[0] == "ONE-123"


class TestDownloadAttachmentApiErrors:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "issue_response,expected_code",
        [
            (
                {"isError": True, "error": {"code": "ISSUE_NOT_FOUND"}},
                "ISSUE_NOT_FOUND",
            ),
            ({"isError": True, "error": {"code": "AUTH_FAILED"}}, "AUTH_FAILED"),
        ],
    )
    async def test_issue_fetch_errors(
        self, mock_config, temp_dir, issue_response, expected_code
    ):
        with patch(
            "src.tools.attachment.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = issue_response
            result = await download_attachment("ONE-123", "12345", output_dir=temp_dir)

        assert result["isError"] is True
        assert result["error"]["code"] == expected_code

    @pytest.mark.asyncio
    async def test_attachment_not_found_on_issue(self, mock_config, temp_dir):
        issue_response = {
            "key": "ONE-123",
            "attachments": [
                {"id": "99999", "filename": "other.png"},
            ],
        }

        with patch(
            "src.tools.attachment.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = issue_response
            result = await download_attachment("ONE-123", "12345", output_dir=temp_dir)

        assert result["isError"] is True
        assert result["error"]["code"] == "ATTACHMENT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_download_failed_error(self, mock_config, temp_dir):
        issue_response = {
            "key": "ONE-123",
            "attachments": [
                {"id": "12345", "filename": "file.txt"},
            ],
        }
        error_response = {
            "isError": True,
            "error": {"code": "DOWNLOAD_FAILED", "message": "Network error"},
        }

        with (
            patch(
                "src.tools.attachment.JiraClient.get_issue", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.tools.attachment.JiraClient.download_attachment",
                new_callable=AsyncMock,
            ) as mock_download,
        ):
            mock_get.return_value = issue_response
            mock_download.return_value = error_response
            result = await download_attachment("ONE-123", "12345", output_dir=temp_dir)

        assert result["isError"] is True
        assert result["error"]["code"] == "DOWNLOAD_FAILED"

    @pytest.mark.asyncio
    async def test_rate_limited_error(self, mock_config, temp_dir):
        error_response = {
            "isError": True,
            "error": {"code": "RATE_LIMITED", "message": "Too many requests"},
        }

        with patch(
            "src.tools.attachment.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = error_response
            result = await download_attachment("ONE-123", "12345", output_dir=temp_dir)

        assert result["isError"] is True
        assert result["error"]["code"] == "RATE_LIMITED"
