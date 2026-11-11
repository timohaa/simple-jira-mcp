"""Tests for JiraClient search pagination state."""

import httpx
import pytest


async def test_search_follows_next_page_token(client, replay):
    """Test the token from one page fetches the next page."""
    jql = 'project = "ONE" AND labels = mcp-fixture ORDER BY key ASC'
    jira = replay("search_two_pages")

    first = await client.search(jql, max_results=1)
    second = await client.search(
        jql, max_results=1, next_page_token=first["next_page_token"]
    )

    assert first["is_last"] is False
    assert [issue["key"] for issue in first["issues"]] == ["ONE-1"]
    assert "nextPageToken" not in jira.sent(0)
    assert jira.sent(1)["nextPageToken"] == first["next_page_token"]
    assert first["next_page_token"].startswith("EAEY")
    assert [issue["key"] for issue in second["issues"]] == ["ONE-2"]
    assert second["is_last"] is False


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
