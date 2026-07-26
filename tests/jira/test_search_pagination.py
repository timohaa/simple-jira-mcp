"""Tests for JiraClient search pagination state."""

import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_search_with_next_page_token(client, patch_async_client):
    """Test search handles pagination tokens."""
    recorded: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        recorded["json"] = json.loads(request.content.decode())
        response_body = {
            "isLast": False,
            "nextPageToken": "token_page_2",
            "issues": [],
        }
        return httpx.Response(200, json=response_body)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE", next_page_token="token_page_1")

    assert recorded["json"]["nextPageToken"] == "token_page_1"
    assert result["next_page_token"] == "token_page_2"
    assert result["is_last"] is False


@pytest.mark.asyncio
async def test_search_derives_is_last_from_token_when_absent(
    client, patch_async_client
):
    """Test a missing isLast does not mask a further page of results."""

    async def handler(_: httpx.Request) -> httpx.Response:
        body = {"nextPageToken": "token_page_2", "issues": []}
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE")

    assert result["is_last"] is False
    assert result["next_page_token"] == "token_page_2"


@pytest.mark.asyncio
async def test_search_is_last_when_no_token_and_no_flag(client, patch_async_client):
    """Test a response with neither isLast nor a token ends pagination."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"issues": []})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.search("project = ONE")

    assert result["is_last"] is True
    assert "next_page_token" not in result
