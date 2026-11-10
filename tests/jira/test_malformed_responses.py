"""Tests for tolerating malformed or unexpected Jira response bodies."""

import httpx
import pytest

from simple_jira_mcp.jira.base import JiraClientBase
from simple_jira_mcp.jira.client import CreateIssueParams

NOT_AN_OBJECT = [(None, None), ("string", None), ({}, None)]


@pytest.mark.parametrize(
    "value,name", [*NOT_AN_OBJECT, ({"name": "Test"}, "Test"), ({"id": "1"}, None)]
)
def test_extract_name_tolerates_non_objects(value, name):
    assert JiraClientBase._extract_name(value) == name


@pytest.mark.parametrize(
    "value,name",
    [*NOT_AN_OBJECT, ({"displayName": "User"}, "User"), ({"accountId": "1"}, None)],
)
def test_extract_display_name_tolerates_non_objects(value, name):
    assert JiraClientBase._extract_display_name(value) == name


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
