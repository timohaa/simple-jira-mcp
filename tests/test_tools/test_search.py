"""Tests for search_issues tool with mocked Jira API."""

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


JQL = 'project = "ONE" AND labels = mcp-fixture ORDER BY key ASC'


class TestSearchIntegration:
    async def test_search_integration_success(self, mock_config, replay):
        jira = replay("search")

        result = await search_issues(JQL)

        assert jira.requests[0].url.host == "test.atlassian.net"
        assert jira.sent(0)["jql"] == JQL
        assert jira.sent(0)["maxResults"] == 50
        assert result["is_last"] is True
        assert [issue["key"] for issue in result["issues"]] == [
            "ONE-1",
            "ONE-2",
            "ONE-3",
        ]
        assert result["issues"][0]["status"] == "Done"
        assert result["issues"][0]["url"] == "https://test.atlassian.net/browse/ONE-1"

    async def test_search_integration_with_custom_params(self, mock_config, replay):
        jira = replay("search_two_pages")

        first = await search_issues(JQL, limit=1)
        second = await search_issues(
            JQL, limit=1, next_page_token=first["next_page_token"]
        )

        assert jira.sent(0)["maxResults"] == 1
        assert jira.sent(1)["nextPageToken"] == first["next_page_token"]
        assert [issue["key"] for issue in first["issues"]] == ["ONE-1"]
        assert [issue["key"] for issue in second["issues"]] == ["ONE-2"]

    async def test_search_integration_forwards_fields(self, mock_config, replay):
        fields = [
            "summary",
            "description",
            "reporter",
            "resolution",
            "project",
            "comment",
            "attachment",
        ]
        jira = replay("search_all_fields")

        result = await search_issues(JQL, fields=fields)

        assert jira.sent(0)["fields"] == fields
        assert result["issues"][0]["reporter"] == "User 1"

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

    async def test_search_integration_invalid_jql(self, mock_config, replay):
        replay("search_invalid_jql")

        result = await search_issues('project = "ONE" AND (')

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
