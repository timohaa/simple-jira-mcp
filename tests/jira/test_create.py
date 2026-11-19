"""Tests for JiraClient create_issue operations."""

from dataclasses import replace

import httpx
import pytest

from simple_jira_mcp.jira.create import CreateIssueParams

PARAMS = CreateIssueParams(project_key="ONE", summary="Summary")


async def test_create_issue_builds_payload(client, replay):
    """Test create_issue builds correct API payload."""
    jira = replay("create_issue")

    result = await client.create_issue(
        CreateIssueParams(
            project_key="ONE",
            summary="Recorded issue",
            description="Line 1\nLine 2",
            labels=["mcp-fixture"],
        )
    )

    assert jira.requests[0].method == "POST"
    assert jira.requests[0].url == "https://example.atlassian.net/rest/api/3/issue"
    assert jira.sent(0) == {
        "fields": {
            "project": {"key": "ONE"},
            "summary": "Recorded issue",
            "issuetype": {"name": "Task"},
            "labels": ["mcp-fixture"],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Line 1"},
                            {"type": "hardBreak"},
                            {"type": "text", "text": "Line 2"},
                        ],
                    }
                ],
            },
        }
    }
    assert result == {
        "key": "ONE-1",
        "id": "10025",
        "url": "https://example.atlassian.net/browse/ONE-1",
    }


async def test_create_issue_sends_optional_fields(client, replay):
    jira = replay("create_issue")

    await client.create_issue(
        replace(PARAMS, issue_type="Bug", priority="High", assignee_account_id="abc")
    )

    assert jira.sent(0) == {
        "fields": {
            "project": {"key": "ONE"},
            "summary": "Summary",
            "issuetype": {"name": "Bug"},
            "priority": {"name": "High"},
            "assignee": {"accountId": "abc"},
        }
    }


async def test_create_issue_unknown_project_is_validation_error(client, replay):
    """Jira rejects an unknown project with 400, not 404."""
    replay("create_project_not_found")

    result = await client.create_issue(replace(PARAMS, project_key="ZZNOPROJECT"))

    assert result["error"] == {
        "code": "VALIDATION_ERROR",
        "message": (
            "project: The target project doesn't exist or you don't have "
            "permission to create issues in it."
        ),
    }


async def test_create_issue_invalid_issue_type_error(client, replay):
    """Test create_issue maps invalid issue type errors."""
    replay("create_invalid_issue_type")

    result = await client.create_issue(replace(PARAMS, issue_type="NoSuchType"))

    assert result["error"] == {
        "code": "INVALID_ISSUE_TYPE",
        "message": "Specify a valid issue type",
    }


TYPES_URL = (
    "https://example.atlassian.net/rest/api/3/issue/createmeta/ONE/issuetypes"
    "?maxResults=200"
)
TYPE_FIELDS_URL = (
    "https://example.atlassian.net/rest/api/3/issue/createmeta/ONE/issuetypes/10010"
    "?maxResults=200"
)


INVALID = "Priority 'NoSuchPriority' is not valid for Task issues in ONE."


@pytest.mark.parametrize(
    "faults,lookups,message",
    [
        (
            {},
            [TYPES_URL, TYPE_FIELDS_URL],
            f"{INVALID} Valid priorities: Highest, High, Medium, Low, Lowest.",
        ),
        ({2: httpx.Response(500)}, [TYPES_URL, TYPE_FIELDS_URL], INVALID),
        ({1: httpx.Response(403)}, [TYPES_URL], INVALID),
    ],
)
async def test_create_issue_unknown_priority_lists_valid_priorities(
    client, replay, faults, lookups, message
):
    """Test create_issue names the priority and lists the allowed ones."""
    jira = replay("create_invalid_priority", faults)

    result = await client.create_issue(replace(PARAMS, priority="NoSuchPriority"))

    assert [str(request.url) for request in jira.requests[1:]] == lookups
    assert result["error"] == {"code": "INVALID_PRIORITY", "message": message}


async def test_create_issue_unknown_priority_for_type_without_priority(client, replay):
    """The sandbox Bug type has no priority field, so none can be listed."""
    jira = replay("create_invalid_priority_type_without_priority")

    result = await client.create_issue(
        replace(PARAMS, issue_type="Bug", priority="NoSuchPriority")
    )

    assert len(jira.requests) == 3
    assert result["error"] == {
        "code": "INVALID_PRIORITY",
        "message": "Priority 'NoSuchPriority' is not valid for Bug issues in ONE.",
    }


async def test_create_issue_priority_error_without_priority(client, patch_async_client):
    """Test create_issue keeps Jira's message when no priority was sent."""
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        errors = {"priority": "Priority is required"}
        return httpx.Response(400, json={"errors": errors})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.create_issue(PARAMS)

    assert len(requests) == 1
    assert result["error"] == {
        "code": "INVALID_PRIORITY",
        "message": "Priority is required",
    }


@pytest.mark.parametrize(
    "response,code,message",
    [
        (httpx.Response(401), "AUTH_FAILED", "Invalid credentials"),
        (httpx.Response(404), "PROJECT_NOT_FOUND", "Project not found"),
        (httpx.Response(429), "RATE_LIMITED", "Too many requests to Jira API"),
        (
            httpx.Response(400, json={"errors": {"summary": "Summary is required"}}),
            "VALIDATION_ERROR",
            "summary: Summary is required",
        ),
        (
            httpx.Response(400, json={"errorMessages": ["Field error"]}),
            "VALIDATION_ERROR",
            "Field error",
        ),
        (httpx.Response(400, json={}), "JIRA_ERROR", "Jira API error: 400"),
        (
            httpx.Response(500, content=b"Internal Server Error"),
            "JIRA_ERROR",
            "Jira API error: 500",
        ),
    ],
    ids=[
        "401",
        "404",
        "429",
        "400-field-errors",
        "400-error-messages",
        "400-empty-body",
        "500-not-json",
    ],
)
async def test_create_issue_fault_responses(
    client, patch_async_client, response, code, message
):
    """Statuses and bodies a live site cannot be made to return on demand."""
    patch_async_client(httpx.MockTransport(lambda _: response))

    result = await client.create_issue(PARAMS)

    assert result == {"isError": True, "error": {"code": code, "message": message}}


async def test_create_issue_request_error(client, patch_async_client):
    """Test create_issue handles connection errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("Connection failed")

    patch_async_client(httpx.MockTransport(handler))

    result = await client.create_issue(PARAMS)

    assert result == {
        "isError": True,
        "error": {"code": "JIRA_ERROR", "message": "Request failed: Connection failed"},
    }
