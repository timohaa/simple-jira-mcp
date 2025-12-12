"""Tests for create_issue tool with mocked Jira API."""

import json
import os
from functools import partial

import httpx
import pytest

import src.config
from src.config import reset_config_state
from src.tools.create import create_issue
from src.utils.errors import INVALID_ISSUE_TYPE, INVALID_PRIORITY


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
def patch_httpx_client(monkeypatch):
    """Patch httpx.AsyncClient in Jira modules to use a mock transport."""

    def _apply(transport: httpx.MockTransport) -> None:
        async_client = partial(httpx.AsyncClient, transport=transport)
        monkeypatch.setattr("src.jira.search.httpx.AsyncClient", async_client)
        monkeypatch.setattr("src.jira.issue.httpx.AsyncClient", async_client)
        monkeypatch.setattr("src.jira.create.httpx.AsyncClient", async_client)
        monkeypatch.setattr("src.jira.attachment.httpx.AsyncClient", async_client)

    return _apply


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

    @pytest.mark.asyncio
    async def test_lowercase_project_key_normalized(
        self, mock_config, patch_httpx_client
    ):
        recorded: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            recorded["json"] = json.loads(request.content.decode())
            return httpx.Response(201, json={"key": "ONE-1", "id": "1"})

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        await create_issue("one", "Test summary")

        assert recorded["json"]["fields"]["project"]["key"] == "ONE"

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
    @pytest.mark.asyncio
    async def test_create_issue_integration_success(
        self, mock_config, patch_httpx_client
    ):
        recorded: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            recorded["json"] = json.loads(request.content.decode())
            return httpx.Response(
                201,
                json={"key": "ONE-123", "id": "123"},
            )

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        result = await create_issue(
            "ONE",
            "New issue",
            issue_type="Bug",
            priority="High",
            labels=["backend"],
            assignee_account_id="abc",
            description="Details here",
        )

        assert result["key"] == "ONE-123"
        payload = recorded["json"]["fields"]
        assert payload["issuetype"]["name"] == "Bug"
        assert payload["priority"]["name"] == "High"
        assert payload["labels"] == ["backend"]
        assert payload["assignee"]["accountId"] == "abc"
        assert payload["project"]["key"] == "ONE"
        assert payload["summary"] == "New issue"
        assert payload["description"]["type"] == "doc"

    @pytest.mark.asyncio
    async def test_create_issue_integration_default_issue_type(
        self, mock_config, patch_httpx_client
    ):
        recorded: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            recorded["json"] = json.loads(request.content.decode())
            return httpx.Response(201, json={"key": "ONE-456", "id": "456"})

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        result = await create_issue("ONE", "New issue")

        assert result["key"] == "ONE-456"
        assert recorded["json"]["fields"]["issuetype"]["name"] == "Task"


class TestCreateIssueApiErrors:
    @pytest.mark.asyncio
    async def test_create_issue_integration_invalid_issue_type(
        self, mock_config, patch_httpx_client
    ):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"errors": {"issuetype": "Invalid type"}})

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        result = await create_issue("ONE", "Summary", issue_type="Invalid")

        assert result["isError"] is True
        assert result["error"]["code"] == INVALID_ISSUE_TYPE

    @pytest.mark.asyncio
    async def test_create_issue_integration_invalid_priority(
        self, mock_config, patch_httpx_client
    ):
        async def handler(_: httpx.Request) -> httpx.Response:
            error_json = {"errors": {"priority": "Invalid priority"}}
            return httpx.Response(400, json=error_json)

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        result = await create_issue("ONE", "Summary", priority="Unknown")

        assert result["isError"] is True
        assert result["error"]["code"] == INVALID_PRIORITY

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
        self, mock_config, patch_httpx_client, status, expected_code
    ):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json={"errors": {"summary": "Error"}})

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        result = await create_issue("ONE", "Test summary")

        assert result["isError"] is True
        assert result["error"]["code"] == expected_code
