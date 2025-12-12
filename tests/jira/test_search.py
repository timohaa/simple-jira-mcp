"""Tests for JiraClient search operations."""

import json
import logging

import httpx
import pytest


@pytest.mark.asyncio
async def test_search_sends_payload_and_transforms(client, patch_async_client):
    """Test search sends correct payload and transforms response."""
    recorded: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        recorded["method"] = request.method
        recorded["url"] = str(request.url)
        recorded["json"] = json.loads(request.content.decode())
        response_body = {
            "total": 1,
            "maxResults": 50,
            "issues": [
                {
                    "key": "ONE-123",
                    "fields": {
                        "summary": "Search result",
                        "status": {"name": "Done"},
                        "assignee": {"displayName": "Jane"},
                        "priority": {"name": "High"},
                        "issuetype": {"name": "Task"},
                        "labels": ["backend"],
                        "created": "2025-01-01",
                        "updated": "2025-01-02",
                    },
                }
            ],
        }
        return httpx.Response(200, json=response_body)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE")

    assert recorded["method"] == "POST"
    assert recorded["url"].endswith("/rest/api/3/search/jql")
    assert recorded["json"]["maxResults"] == 50
    assert "startAt" not in recorded["json"]
    assert recorded["json"]["fields"] == [
        "summary",
        "status",
        "assignee",
        "priority",
        "updated",
        "created",
        "labels",
        "issuetype",
    ]
    issue = result["issues"][0]
    assert issue["key"] == "ONE-123"
    assert issue["summary"] == "Search result"
    assert issue["assignee"] == "Jane"


@pytest.mark.asyncio
async def test_search_with_next_page_token(client, patch_async_client):
    """Test search handles pagination tokens."""
    recorded: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        recorded["json"] = json.loads(request.content.decode())
        response_body = {
            "total": 100,
            "maxResults": 50,
            "nextPageToken": "token_page_2",
            "issues": [],
        }
        return httpx.Response(200, json=response_body)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE", next_page_token="token_page_1")

    assert recorded["json"]["nextPageToken"] == "token_page_1"
    assert result["next_page_token"] == "token_page_2"


@pytest.mark.asyncio
async def test_search_returns_invalid_jql_error(client, patch_async_client):
    """Test search returns error for invalid JQL."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errorMessages": ["Bad JQL"]})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search('text ~ "oops"')

    assert result["isError"] is True
    assert result["error"]["code"] == "INVALID_JQL"
    assert "Bad JQL" in result["error"]["message"]


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
async def test_search_with_start_at_logs_warning(client, patch_async_client, caplog):
    """Test search logs warning when using deprecated start_at."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total": 0, "maxResults": 50, "issues": []})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    with caplog.at_level(logging.WARNING):
        await client.search("project = ONE", start_at=10)

    assert "start_at parameter is deprecated" in caplog.text


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
