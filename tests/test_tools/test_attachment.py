"""Tests for download_attachment tool with mocked Jira API."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from simple_jira_mcp.tools.attachment import download_attachment


@pytest.fixture
def temp_dir(tmp_path):
    """Return pytest's temporary directory as the string the tool accepts."""
    return str(tmp_path)


class TestDownloadAttachmentValidation:
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

    async def test_nonexistent_output_dir_returns_error(self, mock_config):
        result = await download_attachment(
            "ONE-123", "12345", output_dir="/nonexistent/path"
        )

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "not exist" in result["error"]["message"].lower()

    async def test_output_dir_is_file_returns_error(self, mock_config, temp_dir):
        file_path = Path(temp_dir) / "not_a_dir.txt"
        file_path.write_text("test")

        result = await download_attachment(
            "ONE-123", "12345", output_dir=str(file_path)
        )

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "not a directory" in result["error"]["message"].lower()

    async def test_missing_config_returns_error(self, clean_config):
        result = await download_attachment("ONE-123", "12345")

        assert result["isError"] is True
        assert result["error"]["code"] == "CONFIG_NOT_FOUND"

    async def test_unknown_config_id_returns_error(self, mock_config):
        result = await download_attachment("ONE-123", "12345", config_id="unknown")

        assert result["isError"] is True
        assert result["error"]["code"] == "CONFIG_NOT_FOUND"


class TestDownloadAttachmentSuccess:
    @pytest.mark.parametrize(
        "issue_key,use_temp_dir,filename",
        [
            ("ONE-123", True, "screenshot.png"),
            ("one-123", True, "file.txt"),
            ("ONE-123", False, "file.txt"),
        ],
        ids=["explicit-dir", "lowercase-key", "default-cwd"],
    )
    async def test_download_success(
        self, mock_config, temp_dir, issue_key, use_temp_dir, filename
    ):
        issue_response = {
            "key": "ONE-123",
            "attachments": [{"id": "12345", "filename": filename}],
        }
        download_response = {"success": True, "filename": filename}

        with (
            patch(
                "simple_jira_mcp.jira.client.JiraClient.get_issue",
                new_callable=AsyncMock,
            ) as mock_get,
            patch(
                "simple_jira_mcp.jira.client.JiraClient.download_attachment",
                new_callable=AsyncMock,
            ) as mock_download,
        ):
            mock_get.return_value = issue_response
            mock_download.return_value = download_response
            out_dir = temp_dir if use_temp_dir else None
            result = await download_attachment(issue_key, "12345", output_dir=out_dir)

        assert result == download_response
        mock_get.assert_awaited_once_with(
            "ONE-123", include_comments=False, include_attachments=True
        )
        expected_dir = Path(temp_dir) if use_temp_dir else Path.cwd()
        mock_download.assert_awaited_once_with(
            "12345", expected_dir, "ONE-123", filename
        )

    async def test_none_filename_falls_back_to_default(self, mock_config, temp_dir):
        issue_response = {
            "key": "ONE-123",
            "attachments": [
                {"id": "12345", "filename": None},
            ],
        }

        with (
            patch(
                "simple_jira_mcp.jira.client.JiraClient.get_issue",
                new_callable=AsyncMock,
            ) as mock_get,
            patch(
                "simple_jira_mcp.jira.client.JiraClient.download_attachment",
                new_callable=AsyncMock,
            ) as mock_download,
        ):
            mock_get.return_value = issue_response
            mock_download.return_value = {"success": True, "filename": "attachment"}
            result = await download_attachment("ONE-123", "12345", output_dir=temp_dir)

        assert result["success"] is True
        assert mock_download.call_args.args[3] == "attachment"


class TestDownloadAttachmentApiErrors:
    @pytest.mark.parametrize(
        "issue_response,expected_code",
        [
            (
                {"isError": True, "error": {"code": "ISSUE_NOT_FOUND"}},
                "ISSUE_NOT_FOUND",
            ),
            ({"isError": True, "error": {"code": "AUTH_FAILED"}}, "AUTH_FAILED"),
            (
                {
                    "isError": True,
                    "error": {"code": "RATE_LIMITED", "message": "Too many requests"},
                },
                "RATE_LIMITED",
            ),
        ],
    )
    async def test_issue_fetch_errors(
        self, mock_config, temp_dir, issue_response, expected_code
    ):
        with patch(
            "simple_jira_mcp.jira.client.JiraClient.get_issue",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = issue_response
            result = await download_attachment("ONE-123", "12345", output_dir=temp_dir)

        assert result == issue_response
        assert result["error"]["code"] == expected_code

    async def test_attachment_not_found_on_issue(self, mock_config, temp_dir):
        issue_response = {
            "key": "ONE-123",
            "attachments": [
                {"id": "99999", "filename": "other.png"},
            ],
        }

        with patch(
            "simple_jira_mcp.jira.client.JiraClient.get_issue",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = issue_response
            result = await download_attachment("ONE-123", "12345", output_dir=temp_dir)

        assert result["isError"] is True
        assert result["error"]["code"] == "ATTACHMENT_NOT_FOUND"

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
                "simple_jira_mcp.jira.client.JiraClient.get_issue",
                new_callable=AsyncMock,
            ) as mock_get,
            patch(
                "simple_jira_mcp.jira.client.JiraClient.download_attachment",
                new_callable=AsyncMock,
            ) as mock_download,
        ):
            mock_get.return_value = issue_response
            mock_download.return_value = error_response
            result = await download_attachment("ONE-123", "12345", output_dir=temp_dir)

        assert result["isError"] is True
        assert result["error"]["code"] == "DOWNLOAD_FAILED"
