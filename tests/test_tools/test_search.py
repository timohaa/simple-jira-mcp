"""Tests for search_issues tool with mocked Jira API."""

import httpx
import pytest

from simple_jira_mcp.tools.search import search_issues


class TestSearchValidation:
    @pytest.mark.parametrize(
        "jql,kwargs",
        [
            ("", {}),
            ("   ", {}),
            ('project = ONE; text ~ "keyword"', {}),
            ("project = ONE", {"limit": 0}),
            ("project = ONE", {"limit": 101}),
            ("project = ONE", {"fields": ["summary", "unknown"]}),
        ],
        ids=[
            "empty",
            "whitespace",
            "disallowed-char",
            "limit-0",
            "limit-101",
            "unknown-field",
        ],
    )
    async def test_invalid_input_returns_validation_error(
        self, mock_config, jql, kwargs
    ):
        result = await search_issues(jql, **kwargs)

        assert result["isError"] is True
        assert result["error"]["code"] == "VALIDATION_ERROR"

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

    @pytest.mark.parametrize(
        "config_id,fixture_name",
        [(None, "clean_config"), ("unknown", "mock_config")],
        ids=["no-configs", "unknown-id"],
    )
    async def test_config_errors(self, request, config_id, fixture_name):
        request.getfixturevalue(fixture_name)

        result = await search_issues("project = ONE", config_id=config_id)

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

    async def test_search_integration_invalid_jql(self, mock_config, replay):
        replay("search_invalid_jql")

        result = await search_issues('project = "ONE" AND (')

        assert result["isError"] is True
        assert result["error"]["code"] == "INVALID_JQL"

    @pytest.mark.parametrize(
        "status,code", [(401, "AUTH_FAILED"), (429, "RATE_LIMITED")], ids=["401", "429"]
    )
    async def test_search_integration_bare_status_errors(
        self, mock_config, patch_async_client, status, code
    ):
        """Bare statuses a live site cannot be made to return on demand."""
        patch_async_client(httpx.MockTransport(lambda _: httpx.Response(status)))

        result = await search_issues("project = ONE")

        assert result["isError"] is True
        assert result["error"]["code"] == code
