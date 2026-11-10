"""Tests for search_issues tool with mocked Jira API."""

import json

import httpx
import pytest

from simple_jira_mcp.tools.search import search_issues


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
        # The message must name the accepted bounding clauses.
        message = result["error"]["message"]
        assert (
            "assignee, created, id, issuetype, key, priority, project, "
            "reporter, resolved, status, type, updated"
        ) in message

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
    async def test_search_integration_success(self, mock_config, patch_async_client):
        async def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content.decode())
            assert payload["jql"] == "project = ONE"
            assert payload["maxResults"] == 50
            return httpx.Response(
                200,
                json={
                    "isLast": False,
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
        patch_async_client(transport)

        result = await search_issues("project = ONE")

        assert result["is_last"] is False
        assert result["issues"][0]["key"] == "ONE-1"
        assert result["issues"][0]["status"] == "In Progress"
        assert result["next_page_token"] == "next"

    @pytest.mark.asyncio
    async def test_search_integration_with_custom_params(
        self, mock_config, patch_async_client
    ):
        async def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content.decode())
            assert payload["maxResults"] == 25
            assert payload["nextPageToken"] == "token"
            assert payload["fields"] == ["summary", "status"]
            response_data = {"isLast": True, "issues": []}
            return httpx.Response(200, json=response_data)

        transport = httpx.MockTransport(handler)
        patch_async_client(transport)

        result = await search_issues(
            "project = ONE",
            limit=25,
            next_page_token="token",
            fields=["summary", "status"],
        )

        assert result["is_last"] is True
        assert result["issues"] == []

    @pytest.mark.asyncio
    async def test_search_integration_auth_failed(
        self, mock_config, patch_async_client
    ):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(401)

        transport = httpx.MockTransport(handler)
        patch_async_client(transport)

        result = await search_issues("project = ONE")

        assert result["isError"] is True
        assert result["error"]["code"] == "AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_search_integration_invalid_jql(
        self, mock_config, patch_async_client
    ):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"errorMessages": ["Invalid query"]})

        transport = httpx.MockTransport(handler)
        patch_async_client(transport)

        result = await search_issues("project = ONE")

        assert result["isError"] is True
        assert result["error"]["code"] == "INVALID_JQL"

    @pytest.mark.asyncio
    async def test_search_integration_rate_limited(
        self, mock_config, patch_async_client
    ):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(429)

        transport = httpx.MockTransport(handler)
        patch_async_client(transport)

        result = await search_issues("project = ONE")

        assert result["isError"] is True
        assert result["error"]["code"] == "RATE_LIMITED"
