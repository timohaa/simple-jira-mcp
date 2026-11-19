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


@pytest.mark.parametrize(
    "response,code,message",
    [
        (httpx.Response(401), "AUTH_FAILED", "Invalid credentials"),
        (httpx.Response(429), "RATE_LIMITED", "Too many requests to Jira API"),
        (httpx.Response(500), "JIRA_ERROR", "Jira API error: 500"),
        (httpx.Response(400, content=b"Not JSON"), "INVALID_JQL", "Invalid JQL query"),
        (
            httpx.Response(400, json={"errorMessages": []}),
            "INVALID_JQL",
            "Invalid JQL query",
        ),
    ],
    ids=["401", "429", "500", "400-not-json", "400-no-messages"],
)
async def test_search_fault_responses(
    client, patch_async_client, response, code, message
):
    """Statuses and bodies a live site cannot be made to return on demand."""
    patch_async_client(httpx.MockTransport(lambda _: response))

    result = await client.search("project = ONE")

    assert result == {"isError": True, "error": {"code": code, "message": message}}


async def test_search_request_error(client, patch_async_client):
    """Test search handles connection errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("Connection failed")

    patch_async_client(httpx.MockTransport(handler))

    result = await client.search("project = ONE")

    assert result["isError"] is True
    assert result["error"] == {
        "code": "JIRA_ERROR",
        "message": "Request failed: Connection failed",
    }
