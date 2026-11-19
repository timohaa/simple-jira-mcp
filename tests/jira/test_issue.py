"""Tests for JiraClient get_issue operations."""

import httpx
import pytest


async def test_get_issue_transforms_data(client, replay):
    """Test get_issue transforms response data."""
    jira = replay("get_issue")

    result = await client.get_issue("ONE-1")

    assert len(jira.requests) == 1
    assert (
        jira.requests[0].url == "https://example.atlassian.net/rest/api/3/issue/ONE-1"
    )
    assert result == {
        "key": "ONE-1",
        "summary": "Recorded issue, updated",
        "description": "Line 1\nLine 2",
        "status": "Done",
        "assignee": None,
        "reporter": "User 1",
        "priority": "Medium",
        "issue_type": "Task",
        "labels": ["mcp-fixture"],
        "created": "2026-11-11T12:22:04.561+0200",
        "updated": "2026-11-11T12:22:14.763+0200",
        "resolved": "2026-11-11T12:22:12.835+0200",
        "duedate": None,
        "url": "https://example.atlassian.net/browse/ONE-1",
        "comments": [
            {
                "author": "User 1",
                "created": "2026-11-11T12:22:10.760+0200",
                "body": "First line\nSecond line",
            },
            {
                "author": "User 1",
                "created": "2026-11-11T12:22:13.343+0200",
                "body": "Moved by recorder",
            },
        ],
        "attachments": [
            {
                "id": "10007",
                "filename": "notes.txt",
                "size_kb": 0.02,
                "mime_type": "text/plain",
                "created": "2026-11-11T12:22:14.384+0200",
            }
        ],
    }


async def test_get_issue_missing_issue_is_not_found(client, replay):
    replay("get_issue_not_found")

    result = await client.get_issue("ONE-99999999")

    assert result == {
        "isError": True,
        "error": {"code": "ISSUE_NOT_FOUND", "message": "Issue not found"},
    }


async def test_get_issue_with_rejected_token_is_reported_as_not_found(client, replay):
    """Jira answers a bad API token with 404, so the cause cannot be told apart."""
    replay("auth_failed")

    result = await client.get_issue("ONE-1")

    assert result["error"]["code"] == "ISSUE_NOT_FOUND"


@pytest.mark.parametrize(
    "status,code,message",
    [
        (401, "AUTH_FAILED", "Invalid credentials"),
        (429, "RATE_LIMITED", "Too many requests to Jira API"),
        (500, "JIRA_ERROR", "Jira API error: 500"),
    ],
    ids=["401", "429", "500"],
)
async def test_get_issue_bare_status_errors(
    client, patch_async_client, status, code, message
):
    """Bare statuses a live site cannot be made to return on demand."""
    patch_async_client(httpx.MockTransport(lambda _: httpx.Response(status)))

    result = await client.get_issue("ONE-123")

    assert result == {"isError": True, "error": {"code": code, "message": message}}


async def test_get_issue_request_error(client, patch_async_client):
    """Test get_issue handles connection errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("Connection failed")

    patch_async_client(httpx.MockTransport(handler))

    result = await client.get_issue("ONE-123")

    assert result == {
        "isError": True,
        "error": {"code": "JIRA_ERROR", "message": "Request failed: Connection failed"},
    }
