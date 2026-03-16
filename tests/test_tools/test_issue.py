"""Tests for get_issue tool with mocked Jira API."""

import json
import os
from unittest.mock import AsyncMock, patch

import pytest

import src.config
from src.config import reset_config_state
from src.tools.issue import get_issue


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


class TestGetIssueValidation:
    @pytest.mark.asyncio
    async def test_empty_issue_key_returns_error(self, mock_config):
        result = await get_issue("")

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "required" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_whitespace_issue_key_returns_error(self, mock_config):
        result = await get_issue("   ")

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_invalid_issue_key_format_returns_error(self, mock_config):
        result = await get_issue("invalid")

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "format" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_lowercase_issue_key_normalized(self, mock_config):
        mock_response = {
            "key": "ONE-123",
            "summary": "Test",
            "status": "Done",
        }

        with patch(
            "src.tools.issue.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response
            await get_issue("one-123")

        mock_get.assert_called_once()
        assert mock_get.call_args.args[0] == "ONE-123"

    @pytest.mark.asyncio
    async def test_missing_config_returns_error(self, clean_config):
        result = await get_issue("ONE-123")

        assert result["isError"] is True
        assert result["error"]["code"] == "CONFIG_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_unknown_config_id_returns_error(self, mock_config):
        result = await get_issue("ONE-123", config_id="unknown")

        assert result["isError"] is True
        assert result["error"]["code"] == "CONFIG_NOT_FOUND"


class TestGetIssueSuccess:
    @pytest.mark.asyncio
    async def test_successful_get_issue(self, mock_config):
        mock_response = {
            "key": "ONE-123",
            "summary": "Test issue",
            "description": "This is a test",
            "status": "Done",
            "assignee": "John Doe",
            "reporter": "Jane Smith",
            "priority": "High",
            "issue_type": "Task",
            "labels": ["backend"],
            "created": "2025-01-15",
            "updated": "2025-01-20",
            "resolved": None,
            "url": "https://test.atlassian.net/browse/ONE-123",
            "comments": [],
            "attachments": [],
        }

        with patch(
            "src.tools.issue.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response
            result = await get_issue("ONE-123")

        assert result["key"] == "ONE-123"
        assert result["summary"] == "Test issue"
        assert result["status"] == "Done"

    @pytest.mark.asyncio
    async def test_get_issue_with_comments(self, mock_config):
        mock_response = {
            "key": "ONE-123",
            "summary": "Test",
            "comments": [
                {"author": "John", "created": "2025-01-16", "body": "A comment"}
            ],
            "attachments": [],
        }

        with patch(
            "src.tools.issue.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response
            result = await get_issue("ONE-123", include_comments=True)

        assert len(result["comments"]) == 1
        assert result["comments"][0]["author"] == "John"

    @pytest.mark.asyncio
    async def test_get_issue_with_attachments(self, mock_config):
        mock_response = {
            "key": "ONE-123",
            "summary": "Test",
            "comments": [],
            "attachments": [
                {
                    "id": "12345",
                    "filename": "screenshot.png",
                    "size_kb": 145.2,
                    "mime_type": "image/png",
                    "created": "2025-01-16",
                }
            ],
        }

        with patch(
            "src.tools.issue.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response
            result = await get_issue("ONE-123", include_attachments=True)

        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["id"] == "12345"

    @pytest.mark.asyncio
    async def test_get_issue_exclude_comments(self, mock_config):
        mock_response = {"key": "ONE-123", "summary": "Test", "attachments": []}

        with patch(
            "src.tools.issue.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response
            await get_issue("ONE-123", include_comments=False)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["include_comments"] is False

    @pytest.mark.asyncio
    async def test_get_issue_exclude_attachments(self, mock_config):
        mock_response = {"key": "ONE-123", "summary": "Test", "comments": []}

        with patch(
            "src.tools.issue.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response
            await get_issue("ONE-123", include_attachments=False)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["include_attachments"] is False


class TestGetIssueApiErrors:
    @pytest.mark.asyncio
    async def test_issue_not_found_error(self, mock_config):
        error_response = {
            "isError": True,
            "error": {"code": "ISSUE_NOT_FOUND", "message": "Issue not found"},
        }

        with patch(
            "src.tools.issue.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = error_response
            result = await get_issue("ONE-999")

        assert result["isError"] is True
        assert result["error"]["code"] == "ISSUE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_auth_failed_error(self, mock_config):
        error_response = {
            "isError": True,
            "error": {"code": "AUTH_FAILED", "message": "Invalid credentials"},
        }

        with patch(
            "src.tools.issue.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = error_response
            result = await get_issue("ONE-123")

        assert result["isError"] is True
        assert result["error"]["code"] == "AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_rate_limited_error(self, mock_config):
        error_response = {
            "isError": True,
            "error": {"code": "RATE_LIMITED", "message": "Too many requests"},
        }

        with patch(
            "src.tools.issue.JiraClient.get_issue", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = error_response
            result = await get_issue("ONE-123")

        assert result["isError"] is True
        assert result["error"]["code"] == "RATE_LIMITED"
