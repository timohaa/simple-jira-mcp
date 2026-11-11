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


@pytest.mark.asyncio
async def test_create_issue_project_not_found_error(client, patch_async_client):
    """Test create_issue returns error when project not found."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue(replace(PARAMS, project_key="MISSING"))

    assert result["isError"] is True
    assert result["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_issue_auth_failed_error(client, patch_async_client):
    """Test create_issue returns error on authentication failure."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue(PARAMS)

    assert result["isError"] is True
    assert result["error"]["code"] == "AUTH_FAILED"


@pytest.mark.asyncio
async def test_create_issue_rate_limited_error(client, patch_async_client):
    """Test create_issue returns error when rate limited."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue(PARAMS)

    assert result["isError"] is True
    assert result["error"]["code"] == "RATE_LIMITED"


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


@pytest.mark.asyncio
async def test_create_issue_with_errors_field(client, patch_async_client):
    """Test create_issue handles errors field in response."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errors": {"summary": "Summary is required"}})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue(PARAMS)

    assert result["isError"] is True
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_issue_with_error_messages(client, patch_async_client):
    """Test create_issue handles errorMessages in response."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errorMessages": ["Field error"]})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue(PARAMS)

    assert result["isError"] is True
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_issue_with_empty_error_response(client, patch_async_client):
    """Test create_issue handles empty error response."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={})

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue(PARAMS)

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"


@pytest.mark.asyncio
async def test_create_issue_non_json_error_response(client, patch_async_client):
    """Test create_issue handles non-JSON error response."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"Internal Server Error")

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue(PARAMS)

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"


@pytest.mark.asyncio
async def test_create_issue_request_error(client, patch_async_client):
    """Test create_issue handles connection errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("Connection failed")

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    result = await client.create_issue(PARAMS)

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"
