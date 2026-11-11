"""Tests for create_issue tool with mocked Jira API."""

import httpx
import pytest

from simple_jira_mcp.tools.create import create_issue


class TestCreateIssueValidation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "project_key,msg_snippet",
        [
            ("", "project key"),
            ("   ", "project key"),
            ("123invalid", "format"),
        ],
    )
    async def test_project_key_validation_errors(
        self, mock_config, project_key, msg_snippet
    ):
        result = await create_issue(project_key, "Test summary")

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert msg_snippet in result["error"]["message"].lower()

    async def test_lowercase_project_key_normalized(self, mock_config, replay):
        jira = replay("create_issue")

        await create_issue("one", "Test summary")

        assert jira.sent(0)["fields"]["project"] == {"key": "ONE"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("summary", ["", "   "])
    async def test_summary_required(self, mock_config, summary):
        result = await create_issue("ONE", summary)

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_summary_too_long_returns_error(self, mock_config):
        long_summary = "x" * 256
        result = await create_issue("ONE", long_summary)

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "255" in result["error"]["message"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "config_id,fixture_name",
        [
            (None, "clean_config"),
            ("unknown", "mock_config"),
        ],
    )
    async def test_config_errors(self, request, config_id, fixture_name):
        request.getfixturevalue(fixture_name)
        result = await create_issue("ONE", "Test summary", config_id=config_id)

        assert result["isError"] is True
        assert result["error"]["code"] == "CONFIG_NOT_FOUND"


class TestCreateIssueIntegration:
    async def test_create_issue_integration_success(self, mock_config, replay):
        jira = replay("create_issue")

        result = await create_issue(
            "ONE",
            "New issue",
            issue_type="Bug",
            priority="High",
            labels=["backend"],
            assignee_account_id="abc",
            description="Details here",
        )

        assert jira.requests[0].url == "https://test.atlassian.net/rest/api/3/issue"
        assert result == {
            "key": "ONE-1",
            "id": "10025",
            "url": "https://test.atlassian.net/browse/ONE-1",
        }
        assert jira.sent(0) == {
            "fields": {
                "project": {"key": "ONE"},
                "summary": "New issue",
                "issuetype": {"name": "Bug"},
                "priority": {"name": "High"},
                "labels": ["backend"],
                "assignee": {"accountId": "abc"},
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Details here"}],
                        }
                    ],
                },
            }
        }

    async def test_create_issue_integration_default_issue_type(
        self, mock_config, replay
    ):
        jira = replay("create_issue")

        result = await create_issue("ONE", "New issue")

        assert result["key"] == "ONE-1"
        assert jira.sent(0)["fields"]["issuetype"] == {"name": "Task"}


class TestCreateIssueApiErrors:
    async def test_create_issue_integration_invalid_issue_type(
        self, mock_config, replay
    ):
        replay("create_invalid_issue_type")

        result = await create_issue("ONE", "Summary", issue_type="NoSuchType")

        assert result["isError"] is True
        assert result["error"]["code"] == "INVALID_ISSUE_TYPE"

    async def test_create_issue_integration_invalid_priority(self, mock_config, replay):
        replay("create_invalid_priority")

        result = await create_issue("ONE", "Summary", priority="NoSuchPriority")

        assert result["isError"] is True
        assert result["error"]["code"] == "INVALID_PRIORITY"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status,expected_code",
        [
            (404, "PROJECT_NOT_FOUND"),
            (401, "AUTH_FAILED"),
            (429, "RATE_LIMITED"),
            (500, "JIRA_ERROR"),
        ],
    )
    async def test_create_issue_integration_http_errors(
        self, mock_config, patch_async_client, status, expected_code
    ):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json={"errors": {"summary": "Error"}})

        transport = httpx.MockTransport(handler)
        patch_async_client(transport)

        result = await create_issue("ONE", "Test summary")

        assert result["isError"] is True
        assert result["error"]["code"] == expected_code
