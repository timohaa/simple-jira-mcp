"""Tests for Jira issue update and delete requests."""

import json

import httpx
import pytest

from simple_jira_mcp.jira.client import UpdateIssueParams


@pytest.fixture
def requests(patch_async_client):
    """Record requests and answer each with 204 No Content."""
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(204)

    patch_async_client(httpx.MockTransport(handler))
    return seen


async def test_update_issue_payload_and_result(client, requests):
    params = UpdateIssueParams(
        summary="New title",
        description="First.\n\nSecond.",
        priority="High",
        labels=[],
        assignee_account_id="acc-1",
        fields={"duedate": None, "customfield_10001": "x"},
    )
    result = await client.update_issue("ONE-123", params)

    assert len(requests) == 1
    assert requests[0].method == "PUT"
    assert requests[0].url.path == "/rest/api/3/issue/ONE-123"
    assert requests[0].headers["authorization"].startswith("Basic ")
    assert json.loads(requests[0].content) == {
        "fields": {
            "summary": "New title",
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "First."}],
                    },
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Second."}],
                    },
                ],
            },
            "priority": {"name": "High"},
            "labels": [],
            "assignee": {"accountId": "acc-1"},
            "duedate": None,
            "customfield_10001": "x",
        }
    }
    assert result == {
        "key": "ONE-123",
        "url": "https://example.atlassian.net/browse/ONE-123",
        "updated": [
            "assignee",
            "customfield_10001",
            "description",
            "duedate",
            "labels",
            "priority",
            "summary",
        ],
    }


async def test_update_issue_sends_only_given_fields(client, requests):
    result = await client.update_issue("ONE-123", UpdateIssueParams(summary="Title"))

    assert json.loads(requests[0].content) == {"fields": {"summary": "Title"}}
    assert result["updated"] == ["summary"]


async def test_update_issue_clears_field_with_null(client, requests):
    params = UpdateIssueParams(fields={"assignee": None})
    result = await client.update_issue("ONE-123", params)

    assert json.loads(requests[0].content) == {"fields": {"assignee": None}}
    assert result["updated"] == ["assignee"]


@pytest.mark.parametrize(
    "params,message",
    [
        (UpdateIssueParams(), "No fields to update"),
        (UpdateIssueParams(fields={}), "No fields to update"),
        (
            UpdateIssueParams(summary="A", labels=["x"], fields={"summary": "B"}),
            "Specify summary either directly or in fields",
        ),
        (
            UpdateIssueParams(assignee_account_id="a", fields={"assignee": None}),
            "Specify assignee either directly or in fields",
        ),
    ],
)
async def test_update_issue_rejects_without_request(client, requests, params, message):
    result = await client.update_issue("ONE-123", params)

    assert result["error"] == {"code": "VALIDATION_ERROR", "message": message}
    assert requests == []


PRIORITY_REJECTED = httpx.Response(
    400,
    json={"errors": {"priority": "Specify the Priority (name) in the string format"}},
)


EDITMETA_URL = "https://example.atlassian.net/rest/api/3/issue/ONE-1/editmeta"


INVALID = "Priority 'NoSuchPriority' is not valid for ONE-1."


@pytest.mark.parametrize(
    "faults,message",
    [
        ({}, f"{INVALID} Valid priorities: Highest, High, Medium, Low, Lowest."),
        ({1: httpx.Response(200, json={"fields": {}})}, INVALID),
        ({1: httpx.Response(500)}, INVALID),
    ],
)
async def test_update_issue_unknown_priority(client, replay, faults, message):
    jira = replay("update_invalid_priority", faults)

    result = await client.update_issue(
        "ONE-1", UpdateIssueParams(priority="NoSuchPriority")
    )

    assert [(r.method, str(r.url)) for r in jira.requests] == [
        ("PUT", "https://example.atlassian.net/rest/api/3/issue/ONE-1"),
        ("GET", EDITMETA_URL),
    ]
    assert result["error"] == {"code": "INVALID_PRIORITY", "message": message}


async def test_update_issue_raw_priority_error_passes_through(
    client, patch_async_client
):
    patch_async_client(httpx.MockTransport(lambda _: PRIORITY_REJECTED))
    params = UpdateIssueParams(fields={"priority": {"id": "99"}})
    result = await client.update_issue("ONE-123", params)

    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert result["error"]["message"].startswith("priority: ")


@pytest.mark.parametrize("delete_subtasks,expected", [(False, "false"), (True, "true")])
async def test_delete_issue_request_and_result(
    client, requests, delete_subtasks, expected
):
    result = await client.delete_issue("ONE-123", delete_subtasks=delete_subtasks)

    assert len(requests) == 1
    assert requests[0].method == "DELETE"
    assert requests[0].url.path == "/rest/api/3/issue/ONE-123"
    assert dict(requests[0].url.params) == {"deleteSubtasks": expected}
    assert result == {"key": "ONE-123", "deleted": True}


ERROR_RESPONSES = [
    (httpx.Response(401), "AUTH_FAILED", "Invalid credentials"),
    (httpx.Response(404), "ISSUE_NOT_FOUND", "Issue not found"),
    (httpx.Response(429), "RATE_LIMITED", "Too many requests to Jira API"),
    (
        httpx.Response(400, json={"errors": {"summary": "Too long"}}),
        "VALIDATION_ERROR",
        "summary: Too long",
    ),
    (
        httpx.Response(403, json={"errorMessages": ["No permission"]}),
        "JIRA_ERROR",
        "No permission",
    ),
    (httpx.Response(500, text="oops"), "JIRA_ERROR", "Jira API error: 500"),
]


@pytest.mark.parametrize("operation", ["update", "delete"])
@pytest.mark.parametrize("response,code,message", ERROR_RESPONSES)
async def test_error_responses(
    client, patch_async_client, operation, response, code, message
):
    patch_async_client(httpx.MockTransport(lambda _: response))

    if operation == "update":
        result = await client.update_issue("ONE-123", UpdateIssueParams(summary="T"))
    else:
        result = await client.delete_issue("ONE-123")

    assert result == {"isError": True, "error": {"code": code, "message": message}}


@pytest.mark.parametrize("operation", ["update", "delete"])
async def test_request_failure(client, patch_async_client, operation):
    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    patch_async_client(httpx.MockTransport(handler))

    if operation == "update":
        result = await client.update_issue("ONE-123", UpdateIssueParams(summary="T"))
    else:
        result = await client.delete_issue("ONE-123")

    assert result["error"]["code"] == "JIRA_ERROR"
    assert "Request failed" in result["error"]["message"]


async def test_update_issue_on_recorded_site(client, replay):
    jira = replay("update_issue")

    result = await client.update_issue(
        "ONE-1",
        UpdateIssueParams(summary="Recorded issue, updated", labels=["mcp-fixture"]),
    )

    assert jira.requests[0].method == "PUT"
    assert jira.sent(0) == {
        "fields": {"summary": "Recorded issue, updated", "labels": ["mcp-fixture"]}
    }
    assert result == {
        "key": "ONE-1",
        "url": "https://example.atlassian.net/browse/ONE-1",
        "updated": ["labels", "summary"],
    }


async def test_delete_issue_on_recorded_site(client, replay):
    jira = replay("delete_issue")

    result = await client.delete_issue("ONE-3")

    assert jira.requests[0].method == "DELETE"
    assert result == {"key": "ONE-3", "deleted": True}


async def test_delete_missing_issue_is_not_found(client, replay):
    replay("delete_issue_not_found")

    result = await client.delete_issue("ONE-99999999")

    assert result["error"] == {"code": "ISSUE_NOT_FOUND", "message": "Issue not found"}
