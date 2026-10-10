"""Tests for JiraClientBase helper methods."""

import httpx
import pytest

from simple_jira_mcp.config import DEFAULT_TIMEOUT, JiraConfig
from simple_jira_mcp.jira.base import JiraClientBase
from simple_jira_mcp.jira.client import CreateIssueParams


def _config(**overrides) -> JiraConfig:
    """Build a JiraConfig with test defaults."""
    values = {
        "id": "test",
        "url": "https://example.atlassian.net",
        "email": "user@example.com",
        "token": "token",
    }
    values.update(overrides)
    return JiraConfig(**values)  # type: ignore[arg-type]


def test_http_client_uses_default_timeout():
    """Test the HTTP client falls back to the 30s default."""
    client = JiraClientBase(_config())._http

    assert client.timeout.connect == DEFAULT_TIMEOUT
    assert client.timeout.read == DEFAULT_TIMEOUT


def test_http_client_uses_config_timeout():
    """Test the HTTP client honours a per-config timeout."""
    client = JiraClientBase(_config(timeout=5.0))._http

    assert client.timeout.connect == 5.0
    assert client.timeout.read == 5.0
    assert client.timeout.write == 5.0
    assert client.timeout.pool == 5.0


def test_extract_name_with_none():
    """Test _extract_name returns None for None input."""
    assert JiraClientBase._extract_name(None) is None


def test_extract_name_with_non_dict():
    """Test _extract_name returns None for non-dict input."""
    assert JiraClientBase._extract_name("string") is None  # type: ignore[arg-type]


def test_extract_name_with_dict():
    """Test _extract_name extracts name from dict."""
    assert JiraClientBase._extract_name({"name": "Test"}) == "Test"


def test_extract_display_name_with_none():
    """Test _extract_display_name returns None for None input."""
    assert JiraClientBase._extract_display_name(None) is None


def test_extract_display_name_with_non_dict():
    """Test _extract_display_name returns None for non-dict input."""
    assert JiraClientBase._extract_display_name("string") is None  # type: ignore[arg-type]


def test_extract_display_name_with_dict():
    """Test _extract_display_name extracts displayName from dict."""
    assert JiraClientBase._extract_display_name({"displayName": "User"}) == "User"


@pytest.mark.parametrize("body", ["not json", "[]", '"text"', ""])
@pytest.mark.parametrize("operation", ["search", "get_issue", "create_issue"])
async def test_non_object_success_body_is_jira_error(
    client, patch_async_client, operation, body
):
    """A 200/201 whose body is not a JSON object must not raise."""
    patch_async_client(httpx.MockTransport(lambda _: httpx.Response(200, content=body)))

    if operation == "search":
        result = await client.search("project = ONE")
    elif operation == "get_issue":
        result = await client.get_issue("ONE-1")
    else:
        result = await client.create_issue(
            CreateIssueParams(project_key="ONE", summary="Title")
        )

    assert result["isError"] is True
    assert result["error"] == {
        "code": "JIRA_ERROR",
        "message": "Invalid JSON response from Jira API",
    }


async def test_transitions_missing_id_or_name_do_not_raise(client, patch_async_client):
    body = {"transitions": [{"to": {"name": "Done"}}, {"id": 7, "name": None}]}
    patch_async_client(httpx.MockTransport(lambda _: httpx.Response(200, json=body)))

    result = await client.get_transitions("ONE-1")

    assert [(t["id"], t["name"]) for t in result["transitions"]] == [
        ("", ""),
        ("7", ""),
    ]

    patch_async_client(httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    result = await client.transition_issue("ONE-1", "nope")
    assert result["error"]["code"] == "VALIDATION_ERROR"
