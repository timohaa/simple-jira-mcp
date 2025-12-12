"""Tests for search_issues tool with mocked Jira API."""

import json
import os
from functools import partial

import httpx
import pytest

import src.config
from src.config import reset_config_state
from src.tools.search import search_issues


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


class TestSearchValidation:
    @pytest.mark.asyncio
    async def test_empty_jql_returns_error(self, mock_config):
        result = await search_issues("")

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_whitespace_jql_returns_error(self, mock_config):
        result = await search_issues("   ")

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_unbounded_query_returns_error(self, mock_config):
        result = await search_issues('text ~ "keyword"')

        assert result["isError"] is True
        assert result["error"]["code"] == "UNBOUNDED_QUERY"

    @pytest.mark.asyncio
    async def test_jql_with_disallowed_characters_returns_error(self, mock_config):
        result = await search_issues('project = ONE; text ~ "keyword"')

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_invalid_limit_returns_error(self, mock_config):
        result = await search_issues("project = ONE", limit=0)

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_limit_over_100_returns_error(self, mock_config):
        result = await search_issues("project = ONE", limit=101)

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_negative_start_at_returns_error(self, mock_config):
        result = await search_issues("project = ONE", start_at=-1)

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_invalid_field_returns_error(self, mock_config):
        result = await search_issues("project = ONE", fields=["summary", "unknown"])

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_missing_config_returns_error(self, clean_config):
        result = await search_issues("project = ONE")

        assert result["isError"] is True
        assert result["error"]["code"] == "CONFIG_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_unknown_config_id_returns_error(self, mock_config):
        result = await search_issues("project = ONE", config_id="unknown")

        assert result["isError"] is True
        assert result["error"]["code"] == "CONFIG_NOT_FOUND"


class TestSearchIntegration:
    @pytest.mark.asyncio
    async def test_search_integration_success(self, mock_config, patch_httpx_client):
        async def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content.decode())
            assert payload["jql"] == "project = ONE"
            assert payload["maxResults"] == 50
            return httpx.Response(
                200,
                json={
                    "total": 1,
                    "maxResults": 50,
                    "nextPageToken": "next",
                    "issues": [
                        {
                            "key": "ONE-1",
                            "fields": {
                                "summary": "Issue title",
                                "status": {"name": "In Progress"},
                                "assignee": {"displayName": "Jane"},
                                "priority": {"name": "High"},
                                "issuetype": {"name": "Task"},
                                "labels": ["backend"],
                                "created": "2025-01-01",
                                "updated": "2025-01-02",
                            },
                        }
                    ],
                },
            )

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        result = await search_issues("project = ONE")

        assert result["total"] == 1
        assert result["issues"][0]["key"] == "ONE-1"
        assert result["issues"][0]["status"] == "In Progress"
        assert result["next_page_token"] == "next"

    @pytest.mark.asyncio
    async def test_search_integration_with_custom_params(
        self, mock_config, patch_httpx_client
    ):
        async def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content.decode())
            assert payload["maxResults"] == 25
            assert payload["nextPageToken"] == "token"
            assert payload["fields"] == ["summary", "status"]
            response_data = {"total": 0, "maxResults": 25, "issues": []}
            return httpx.Response(200, json=response_data)

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        result = await search_issues(
            "project = ONE",
            limit=25,
            next_page_token="token",
            fields=["summary", "status"],
        )

        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_search_integration_auth_failed(
        self, mock_config, patch_httpx_client
    ):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(401)

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        result = await search_issues("project = ONE")

        assert result["isError"] is True
        assert result["error"]["code"] == "AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_search_integration_invalid_jql(
        self, mock_config, patch_httpx_client
    ):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"errorMessages": ["Invalid query"]})

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        result = await search_issues("project = ONE")

        assert result["isError"] is True
        assert result["error"]["code"] == "INVALID_JQL"

    @pytest.mark.asyncio
    async def test_search_integration_rate_limited(
        self, mock_config, patch_httpx_client
    ):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(429)

        transport = httpx.MockTransport(handler)
        patch_httpx_client(transport)

        result = await search_issues("project = ONE")

        assert result["isError"] is True
        assert result["error"]["code"] == "RATE_LIMITED"
