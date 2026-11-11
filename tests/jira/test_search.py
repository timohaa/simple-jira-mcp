"""Tests for JiraClient search operations."""

import httpx
import pytest

JQL = 'project = "ONE" AND labels = mcp-fixture ORDER BY key ASC'


async def test_search_sends_payload_and_transforms(client, replay):
    """Test search sends correct payload and transforms response."""
    jira = replay("search")

    result = await client.search(JQL)

    assert len(jira.requests) == 1
    assert jira.requests[0].method == "POST"
    assert jira.requests[0].url == "https://example.atlassian.net/rest/api/3/search/jql"
    assert jira.sent(0) == {
        "jql": JQL,
        "maxResults": 50,
        "fields": [
            "summary",
            "status",
            "assignee",
            "priority",
            "updated",
            "created",
            "labels",
            "issuetype",
        ],
    }
    assert result["is_last"] is True
    assert "next_page_token" not in result
    assert "total" not in result
    assert [issue["key"] for issue in result["issues"]] == ["ONE-1", "ONE-2", "ONE-3"]
    issue = result["issues"][0]
    assert issue["summary"] == "Recorded issue, updated"
    assert issue["status"] == "Done"
    assert issue["assignee"] is None
    assert issue["priority"] == "Medium"
    assert issue["labels"] == ["mcp-fixture"]
    assert issue["issue_type"] == "Task"
    assert issue["url"] == "https://example.atlassian.net/browse/ONE-1"


async def test_search_returns_requested_fields(client, replay):
    """Test search output includes non-default requested fields."""
    requested = [
        "summary",
        "description",
        "reporter",
        "resolution",
        "project",
        "comment",
        "attachment",
    ]
    jira = replay("search_all_fields")

    result = await client.search(JQL, fields=requested)

    assert jira.sent(0)["fields"] == requested
    issue = result["issues"][0]
    assert issue["description"] == "Line 1\nLine 2"
    assert issue["reporter"] == "User 1"
    assert issue["resolution"] == "Done"
    assert issue["project"] == "ONE"
    assert [comment["body"] for comment in issue["comments"]] == [
        "First line\nSecond line",
        "Moved by recorder",
    ]
    assert [(a["filename"], a["size_kb"]) for a in issue["attachments"]] == [
        ("notes.txt", 0.02)
    ]
    # Fields that were not requested must not appear
    assert "status" not in issue
    assert "labels" not in issue
    assert result["issues"][1]["description"] == ""
    assert result["issues"][1]["resolution"] is None


async def test_search_returns_invalid_jql_error(client, replay):
    """Test search returns Jira's own message for a JQL syntax error."""
    replay("search_invalid_jql")

    result = await client.search('project = "ONE" AND (')

    assert result == {
        "isError": True,
        "error": {
            "code": "INVALID_JQL",
            "message": (
                "Error in the JQL Query: Expecting a field name at the end of "
                "the query."
            ),
        },
    }


@pytest.mark.asyncio
async def test_search_auth_failed_error(client, patch_async_client):
    """Test search returns error on authentication failure."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE")

    assert result["isError"] is True
    assert result["error"]["code"] == "AUTH_FAILED"


@pytest.mark.asyncio
async def test_search_rate_limited_error(client, patch_async_client):
    """Test search returns error when rate limited."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE")

    assert result["isError"] is True
    assert result["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_search_other_status_error(client, patch_async_client):
    """Test search returns error for server errors."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE")

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"
    assert "500" in result["error"]["message"]


@pytest.mark.asyncio
async def test_search_bad_request_non_json_response(client, patch_async_client):
    """Test search handles non-JSON error responses."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, content=b"Not JSON")

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE")

    assert result["isError"] is True
    assert result["error"]["code"] == "INVALID_JQL"
    assert result["error"]["message"] == "Invalid JQL query"


@pytest.mark.asyncio
async def test_search_bad_request_empty_error_messages(client, patch_async_client):
    """Test search handles empty error messages."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errorMessages": []})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE")

    assert result["isError"] is True
    assert result["error"]["code"] == "INVALID_JQL"
    assert result["error"]["message"] == "Invalid JQL query"


@pytest.mark.asyncio
async def test_search_request_error(client, patch_async_client):
    """Test search handles connection errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("Connection failed")

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE")

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"
    assert "Request failed" in result["error"]["message"]
