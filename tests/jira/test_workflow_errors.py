"""Tests for workflow field validation and runtime failures."""

import httpx
import pytest


@pytest.mark.parametrize(
    "transition,kwargs,message",
    [
        ("11", {"resolution": "Fixed"}, "resolution"),
        ("11", {"fields": {"summary": "Changed"}}, "summary"),
        ("31", {"fields": {"unknown": "value"}}, "unknown"),
        ("31", {"fields": {"resolutiondate": "2026-09-30"}}, "cannot be edited"),
        (
            "31",
            {"resolution": "Fixed", "fields": {"resolution": {"id": "1"}}},
            "either directly or in fields",
        ),
    ],
)
async def test_rejects_unsupported_fields(
    client, patch_async_client, workflow_transitions, transition, kwargs, message
):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"transitions": workflow_transitions})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.transition_issue("ONE-123", transition, **kwargs)

    assert len(requests) == 1
    assert result["isError"] is True
    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert message in result["error"]["message"]


async def test_rejects_field_without_set_operation(
    client, patch_async_client, workflow_transitions
):
    workflow_transitions[1]["fields"]["customfield_10001"]["operations"] = ["add"]

    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json={"transitions": workflow_transitions})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.transition_issue(
        "ONE-123", "31", fields={"customfield_10001": "Completed"}
    )

    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert "customfield_10001" in result["error"]["message"]


@pytest.mark.parametrize(
    "operation", ["get_transitions", "transition_issue", "add_comment"]
)
@pytest.mark.parametrize(
    "status,expected_code",
    [
        (401, "AUTH_FAILED"),
        (404, "ISSUE_NOT_FOUND"),
        (429, "RATE_LIMITED"),
        (400, "VALIDATION_ERROR"),
        (403, "JIRA_ERROR"),
        (500, "JIRA_ERROR"),
    ],
)
async def test_initial_http_errors(
    client, patch_async_client, operation, status, expected_code
):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"errorMessages": ["Denied"]})

    patch_async_client(httpx.MockTransport(handler))
    args = ("ONE-123",) if operation == "get_transitions" else ("ONE-123", "Done")
    result = await getattr(client, operation)(*args)

    assert len(requests) == 1
    assert result["isError"] is True
    assert result["error"]["code"] == expected_code


@pytest.mark.parametrize(
    "status,body,expected_message",
    [
        (
            400,
            {"errors": {"customfield_10001": "Required"}},
            "customfield_10001: Required",
        ),
        (
            400,
            {"errorMessages": ["Workflow validator failed"]},
            "Workflow validator failed",
        ),
        (400, {}, "Jira API error: 400"),
        (400, ["Unexpected"], "Jira API error: 400"),
        (401, {}, "Invalid credentials"),
        (404, {}, "Issue not found"),
        (429, {}, "Too many requests"),
        (500, {"errors": {"workflow": "Failed"}}, "workflow: Failed"),
    ],
)
async def test_transition_post_errors(
    client, patch_async_client, workflow_transitions, status, body, expected_message
):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"transitions": workflow_transitions})
        return httpx.Response(status, json=body)

    patch_async_client(httpx.MockTransport(handler))
    result = await client.transition_issue("ONE-123", "31")

    assert len(requests) == 2
    assert result["isError"] is True
    assert expected_message in result["error"]["message"]


@pytest.mark.parametrize("stage", ["lookup", "post", "readback", "comment"])
async def test_transport_errors(
    client, patch_async_client, workflow_transitions, stage, caplog, capsys
):
    requests = []

    def handler(request):
        requests.append(request)
        fails = (
            stage in ("lookup", "comment")
            or (stage == "post" and request.method == "POST")
            or (stage == "readback" and not request.url.path.endswith("/transitions"))
        )
        if fails:
            raise httpx.ReadTimeout("Timed out", request=request)
        if request.method == "POST":
            return httpx.Response(204)
        return httpx.Response(200, json={"transitions": workflow_transitions})

    client.config.token = "unique-secret-api-token"
    client.config.timeout = 7.5
    patch_async_client(httpx.MockTransport(handler))
    if stage == "comment":
        result = await client.add_comment("ONE-123", "Comment")
    else:
        result = await client.transition_issue("ONE-123", "31")

    assert result["isError"] is True
    assert result["error"]["code"] == "JIRA_ERROR"
    assert "Timed out" in result["error"]["message"]
    if stage == "readback":
        assert "Transition succeeded" in result["error"]["message"]
    assert all(request.extensions["timeout"]["read"] == 7.5 for request in requests)
    assert "unique-secret-api-token" not in caplog.text
    assert "unique-secret-api-token" not in str(result)
    assert capsys.readouterr().out == ""


async def test_readback_http_error_after_success(
    client, patch_async_client, workflow_transitions
):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(204)
        if request.url.path.endswith("/transitions"):
            return httpx.Response(200, json={"transitions": workflow_transitions})
        return httpx.Response(429)

    patch_async_client(httpx.MockTransport(handler))
    result = await client.transition_issue("ONE-123", "31")

    assert result["error"]["code"] == "RATE_LIMITED"
    assert "Transition succeeded" in result["error"]["message"]


@pytest.mark.parametrize(
    "status,body,code",
    [
        (200, "invalid json", "JIRA_ERROR"),
        (200, "[]", "JIRA_ERROR"),
        (500, "", "JIRA_ERROR"),
    ],
)
async def test_malformed_responses(client, patch_async_client, status, body, code):
    patch_async_client(
        httpx.MockTransport(lambda _: httpx.Response(status, content=body))
    )
    result = await client.get_transitions("ONE-123")

    assert result["isError"] is True
    assert result["error"]["code"] == code
