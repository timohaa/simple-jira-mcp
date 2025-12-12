"""Tests for JiraClient create_issue operations."""

import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_create_issue_builds_payload(client, patch_async_client):
    """Test create_issue builds correct API payload."""
    recorded: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        recorded["json"] = json.loads(request.content.decode())
        return httpx.Response(
            201,
            json={"key": "ONE-200", "id": "200", "self": "https://example/api/issue"},
        )

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue(
        "ONE",
        "New issue",
        issue_type="Bug",
        description="Line 1\nLine 2",
        priority="High",
        labels=["backend"],
        assignee_account_id="abc",
    )

    payload = recorded["json"]["fields"]
    assert payload["project"]["key"] == "ONE"
    assert payload["issuetype"]["name"] == "Bug"
    assert payload["priority"]["name"] == "High"
    assert payload["labels"] == ["backend"]
    assert payload["assignee"]["accountId"] == "abc"
    description = payload["description"]
    assert description["type"] == "doc"
    assert len(description["content"]) == 1
    paragraph = description["content"][0]["content"]
    texts = [node for node in paragraph if node.get("type") == "text"]
    assert texts[0]["text"] == "Line 1"
    assert result["key"] == "ONE-200"


@pytest.mark.asyncio
async def test_create_issue_project_not_found_error(client, patch_async_client):
    """Test create_issue returns error when project not found."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue("MISSING", "Summary")

    assert result["isError"] is True
    assert result["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_issue_auth_failed_error(client, patch_async_client):
    """Test create_issue returns error on authentication failure."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue("ONE", "Summary")

    assert result["isError"] is True
    assert result["error"]["code"] == "AUTH_FAILED"


@pytest.mark.asyncio
async def test_create_issue_rate_limited_error(client, patch_async_client):
    """Test create_issue returns error when rate limited."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue("ONE", "Summary")

    assert result["isError"] is True
    assert result["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_create_issue_invalid_issue_type_error(client, patch_async_client):
    """Test create_issue maps invalid issue type errors."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errors": {"issuetype": "Invalid type"}})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue("ONE", "Summary")

    assert result["isError"] is True
    assert result["error"]["code"] == "INVALID_ISSUE_TYPE"


@pytest.mark.asyncio
async def test_create_issue_invalid_priority_error(client, patch_async_client):
    """Test create_issue maps invalid priority errors."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errors": {"priority": "Invalid priority"}})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue("ONE", "Summary", priority="Unknown")

    assert result["isError"] is True
    assert result["error"]["code"] == "INVALID_PRIORITY"


@pytest.mark.asyncio
async def test_create_issue_with_errors_field(client, patch_async_client):
    """Test create_issue handles errors field in response."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errors": {"summary": "Summary is required"}})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue("ONE", "Summary")

    assert result["isError"] is True
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_issue_with_error_messages(client, patch_async_client):
    """Test create_issue handles errorMessages in response."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errorMessages": ["Field error"]})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue("ONE", "Summary")

    assert result["isError"] is True
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_issue_with_empty_error_response(client, patch_async_client):
    """Test create_issue handles empty error response."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue("ONE", "Summary")

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"


@pytest.mark.asyncio
async def test_create_issue_non_json_error_response(client, patch_async_client):
    """Test create_issue handles non-JSON error response."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"Internal Server Error")

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue("ONE", "Summary")

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"


@pytest.mark.asyncio
async def test_create_issue_request_error(client, patch_async_client):
    """Test create_issue handles connection errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("Connection failed")

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue("ONE", "Summary")

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"
