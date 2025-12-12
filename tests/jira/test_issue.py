"""Tests for JiraClient get_issue operations."""

import httpx
import pytest


@pytest.mark.asyncio
async def test_get_issue_transforms_data_and_uses_expand(client, patch_async_client):
    """Test get_issue transforms response and uses expand parameter."""
    recorded: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        recorded["url"] = str(request.url)
        body = {
            "key": "ONE-123",
            "fields": {
                "summary": "Issue summary",
                "description": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Description text"}],
                        }
                    ],
                },
                "status": {"name": "Done"},
                "assignee": {"displayName": "Assignee"},
                "reporter": {"displayName": "Reporter"},
                "priority": {"name": "Medium"},
                "issuetype": {"name": "Task"},
                "labels": ["backend"],
                "created": "2025-01-01",
                "updated": "2025-01-02",
                "resolutiondate": None,
                "comment": {
                    "comments": [
                        {
                            "author": {"displayName": "Commenter"},
                            "created": "2025-01-03",
                            "body": {
                                "type": "doc",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "Hi"}],
                                    }
                                ],
                            },
                        }
                    ]
                },
                "attachment": [
                    {
                        "id": "123",
                        "filename": "file.txt",
                        "size": 2048,
                        "mimeType": "text/plain",
                        "created": "2025-01-04",
                    }
                ],
            },
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.get_issue("ONE-123")

    assert "expand=renderedFields" in recorded["url"]
    assert result["description"] == "Description text"
    assert result["comments"][0]["body"] == "Hi"
    attachment = result["attachments"][0]
    assert attachment["filename"] == "file.txt"
    assert attachment["size_kb"] == 2.0
    assert result["url"].endswith("/browse/ONE-123")


@pytest.mark.asyncio
async def test_get_issue_rate_limited_error(client, patch_async_client):
    """Test get_issue returns error when rate limited."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.get_issue("ONE-123")

    assert result["isError"] is True
    assert result["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_get_issue_auth_failed_error(client, patch_async_client):
    """Test get_issue returns error on authentication failure."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.get_issue("ONE-123")

    assert result["isError"] is True
    assert result["error"]["code"] == "AUTH_FAILED"


@pytest.mark.asyncio
async def test_get_issue_not_found_error(client, patch_async_client):
    """Test get_issue returns error when issue not found."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.get_issue("ONE-123")

    assert result["isError"] is True
    assert result["error"]["code"] == "ISSUE_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_issue_other_status_error(client, patch_async_client):
    """Test get_issue returns error for server errors."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.get_issue("ONE-123")

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"
    assert "500" in result["error"]["message"]


@pytest.mark.asyncio
async def test_get_issue_request_error(client, patch_async_client):
    """Test get_issue handles connection errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("Connection failed")

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.get_issue("ONE-123")

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"
    assert "Request failed" in result["error"]["message"]
