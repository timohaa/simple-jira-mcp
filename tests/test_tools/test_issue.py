"""Tests for get_issue tool validation, config selection and forwarding."""

from unittest.mock import AsyncMock, patch

import pytest

from simple_jira_mcp.tools.issue import get_issue


@pytest.fixture
def client_get_issue():
    """Replace JiraClient.get_issue with a mock."""
    with patch(
        "simple_jira_mcp.jira.client.JiraClient.get_issue", new_callable=AsyncMock
    ) as method:
        method.return_value = {"key": "ONE-123"}
        yield method


class TestGetIssueValidation:
    @pytest.mark.parametrize(
        "issue_key,message",
        [
            ("", "Issue key is required"),
            ("   ", "Issue key is required"),
            (
                "invalid",
                "Invalid issue key format: 'INVALID'. Expected format: PROJECT-123",
            ),
        ],
        ids=["empty", "whitespace", "bad-format"],
    )
    async def test_invalid_issue_key_returns_error(
        self, mock_config, client_get_issue, issue_key, message
    ):
        result = await get_issue(issue_key)

        assert result == {
            "isError": True,
            "error": {"code": "VALIDATION_ERROR", "message": message},
        }
        client_get_issue.assert_not_awaited()

    @pytest.mark.parametrize(
        "config_id,fixture_name",
        [(None, "clean_config"), ("unknown", "mock_config")],
        ids=["no-configs", "unknown-id"],
    )
    async def test_config_errors(self, request, config_id, fixture_name):
        request.getfixturevalue(fixture_name)

        result = await get_issue("ONE-123", config_id=config_id)

        assert result["isError"] is True
        assert result["error"]["code"] == "CONFIG_NOT_FOUND"


class TestGetIssueForwarding:
    @pytest.mark.parametrize(
        "kwargs,comments,attachments",
        [
            ({}, True, True),
            ({"include_comments": False}, False, True),
            ({"include_attachments": False}, True, False),
        ],
        ids=["defaults", "no-comments", "no-attachments"],
    )
    async def test_forwards_normalized_key_and_flags(
        self, mock_config, client_get_issue, kwargs, comments, attachments
    ):
        result = await get_issue(" one-123 ", **kwargs)

        assert result == {"key": "ONE-123"}
        client_get_issue.assert_awaited_once_with(
            "ONE-123", include_comments=comments, include_attachments=attachments
        )

    @pytest.mark.parametrize(
        "code,message",
        [
            ("ISSUE_NOT_FOUND", "Issue not found"),
            ("AUTH_FAILED", "Invalid credentials"),
            ("RATE_LIMITED", "Too many requests"),
        ],
    )
    async def test_client_errors_returned_unchanged(
        self, mock_config, client_get_issue, code, message
    ):
        error = {"isError": True, "error": {"code": code, "message": message}}
        client_get_issue.return_value = error

        assert await get_issue("ONE-123") == error
