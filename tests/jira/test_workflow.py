"""Tests for Jira workflow request payloads and transition selection."""

import json

import httpx
import pytest

from src.jira.adf import adf_to_text, text_to_adf


async def test_get_transitions(client, patch_async_client, workflow_transitions):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"transitions": workflow_transitions})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.get_transitions("ONE-123")

    assert requests[0].method == "GET"
    assert requests[0].url.path == "/rest/api/3/issue/ONE-123/transitions"
    assert dict(requests[0].url.params) == {"expand": "transitions.fields"}
    assert requests[0].headers["authorization"].startswith("Basic ")
    assert result == {
        "transitions": [
            {"id": "11", "name": "Start work", "status": "In Progress", "fields": {}},
            {
                "id": "31",
                "name": "Finish work",
                "status": "Done",
                "fields": workflow_transitions[1]["fields"],
            },
        ]
    }
    assert result["transitions"][1]["fields"]["customfield_10001"]["required"] is True


@pytest.mark.parametrize("transition", ["31", "finish WORK", "dOnE", " Done "])
async def test_transition_payload_and_result(
    client, patch_async_client, workflow_transitions, transition
):
    requests = []
    completion = "2026-10-01T12:34:56.000+0000"

    def handler(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(204)
        if request.url.path.endswith("/transitions"):
            return httpx.Response(200, json={"transitions": workflow_transitions})
        assert dict(request.url.params) == {
            "fields": "status,resolution,resolutiondate"
        }
        return httpx.Response(
            200,
            json={
                "fields": {
                    "status": {"name": "Done"},
                    "resolution": {"name": "Fixed"},
                    "resolutiondate": completion,
                }
            },
        )

    patch_async_client(httpx.MockTransport(handler))
    fields = {"customfield_10001": "Completed"}
    comment = "Completed on 2026-09-30.\nVerified today.\n\nReady for release."
    result = await client.transition_issue(
        "ONE-123", transition, comment=comment, resolution="Fixed", fields=fields
    )

    assert [request.method for request in requests] == ["GET", "POST", "GET"]
    assert requests[1].url.path == "/rest/api/3/issue/ONE-123/transitions"
    assert all(request.headers.get("authorization") for request in requests)
    assert json.loads(requests[1].content) == {
        "transition": {"id": "31"},
        "fields": {"resolution": {"name": "Fixed"}, **fields},
        "update": {"comment": [{"add": {"body": text_to_adf(comment)}}]},
    }
    assert fields == {"customfield_10001": "Completed"}
    assert result == {
        "key": "ONE-123",
        "status": "Done",
        "resolution": "Fixed",
        "resolutiondate": completion,
    }


async def test_transition_without_optional_fields(client, patch_async_client):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(204)
        if request.url.path.endswith("/transitions"):
            return httpx.Response(
                200,
                json={
                    "transitions": [
                        {
                            "id": "11",
                            "name": "Start work",
                            "to": {"name": "In Progress"},
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"fields": {"status": {"name": "In Progress"}}})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.transition_issue("ONE-123", "11")

    assert json.loads(requests[1].content) == {"transition": {"id": "11"}}
    assert result["status"] == "In Progress"
    assert result["resolution"] is None
    assert result["resolutiondate"] is None


async def test_transition_id_takes_precedence(client, patch_async_client):
    posted = []

    def handler(request):
        if request.method == "POST":
            posted.append(json.loads(request.content))
            return httpx.Response(204)
        if request.url.path.endswith("/transitions"):
            return httpx.Response(
                200,
                json={
                    "transitions": [
                        {"id": "11", "name": "Start", "to": {"name": "In Progress"}},
                        {"id": "31", "name": "11", "to": {"name": "Done"}},
                    ]
                },
            )
        return httpx.Response(200, json={"fields": {}})

    patch_async_client(httpx.MockTransport(handler))
    await client.transition_issue("ONE-123", "11")

    assert posted == [{"transition": {"id": "11"}}]


@pytest.mark.parametrize(
    "options,transition,reason",
    [
        ([], "Done", "not found"),
        ([("11", "Start", "In Progress")], "Unknown", "not found"),
        ([("11", "Finish", "Done"), ("31", "Close", "Done")], "done", "ambiguous"),
        ([("11", "Finish", "Done"), ("31", "Finish", "Closed")], "finish", "ambiguous"),
        ([("11", "Done", "Closed"), ("31", "Close", "Done")], "done", "ambiguous"),
    ],
)
async def test_transition_selection_errors(
    client, patch_async_client, options, transition, reason
):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "transitions": [
                    {"id": key, "name": name, "to": {"name": status}}
                    for key, name, status in options
                ]
            },
        )

    patch_async_client(httpx.MockTransport(handler))
    result = await client.transition_issue("ONE-123", transition)

    assert len(requests) == 1
    assert result["isError"] is True
    assert result["error"]["code"] == "VALIDATION_ERROR"
    message = result["error"]["message"]
    assert reason in message
    assert "Valid options:" in message
    for key, name, status in options:
        assert f"{key}: {name} -> {status}" in message
    if not options:
        assert "none" in message


async def test_add_comment(client, patch_async_client):
    requests = []
    created = "2026-10-01T12:34:56.000+0000"
    body = "First line\nSecond line\n\nAnother paragraph"

    def handler(request):
        requests.append(request)
        return httpx.Response(201, json={"id": "10001", "created": created})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.add_comment("ONE-123", body)

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/rest/api/3/issue/ONE-123/comment"
    assert requests[0].headers["authorization"].startswith("Basic ")
    payload = json.loads(requests[0].content)
    assert payload == {"body": text_to_adf(body)}
    assert adf_to_text(payload["body"]) == body
    assert result == {"id": "10001", "created": created}
