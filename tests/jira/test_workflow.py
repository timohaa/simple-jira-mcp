"""Tests for Jira workflow request payloads and transition selection."""

import json

import httpx
import pytest


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
        "fields": {"resolution": {"name": "Fixed"}, "customfield_10001": "Completed"},
        "update": {
            "comment": [
                {
                    "add": {
                        "body": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "Completed on 2026-09-30.",
                                        },
                                        {"type": "hardBreak"},
                                        {"type": "text", "text": "Verified today."},
                                    ],
                                },
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": "Ready for release."}
                                    ],
                                },
                            ],
                        }
                    }
                }
            ]
        },
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


async def test_transition_without_comment_field_posts_comment_separately(
    client, patch_async_client, workflow_transitions
):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/comment"):
            return httpx.Response(201, json={"id": "1", "created": "now"})
        if request.method == "POST":
            return httpx.Response(204)
        if request.url.path.endswith("/transitions"):
            return httpx.Response(200, json={"transitions": workflow_transitions})
        return httpx.Response(200, json={"fields": {"status": {"name": "In Progress"}}})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.transition_issue("ONE-123", "11", comment="Started")

    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/rest/api/3/issue/ONE-123/transitions"),
        ("POST", "/rest/api/3/issue/ONE-123/transitions"),
        ("POST", "/rest/api/3/issue/ONE-123/comment"),
        ("GET", "/rest/api/3/issue/ONE-123"),
    ]
    assert json.loads(requests[1].content) == {"transition": {"id": "11"}}
    assert json.loads(requests[2].content) == {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Started"}]}
            ],
        }
    }
    assert result["status"] == "In Progress"


async def test_separate_comment_failure_after_transition(
    client, patch_async_client, workflow_transitions
):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/comment"):
            return httpx.Response(403, json={"errorMessages": ["No permission"]})
        if request.method == "POST":
            return httpx.Response(204)
        return httpx.Response(200, json={"transitions": workflow_transitions})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.transition_issue("ONE-123", "11", comment="Started")

    assert len(requests) == 3
    assert result["error"] == {
        "code": "JIRA_ERROR",
        "message": "Transition succeeded, but adding the comment failed: No permission",
    }


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


RECORDED_TRANSITIONS = [
    {"id": "11", "name": "To Do", "status": "To Do", "fields": {}},
    {"id": "21", "name": "In Progress", "status": "In Progress", "fields": {}},
    {"id": "31", "name": "Done", "status": "Done", "fields": {}},
]


async def test_get_transitions_from_recorded_site(client, replay):
    jira = replay("get_transitions")

    result = await client.get_transitions("ONE-1")

    assert str(jira.requests[0].url) == (
        "https://example.atlassian.net/rest/api/3/issue/ONE-1/transitions"
        "?expand=transitions.fields"
    )
    assert result == {"transitions": RECORDED_TRANSITIONS}


async def test_transition_by_name_on_recorded_site(client, replay):
    jira = replay("transition_issue")

    result = await client.transition_issue("ONE-1", "to do")

    assert [request.method for request in jira.requests] == ["GET", "POST", "GET"]
    assert jira.sent(1) == {"transition": {"id": "11"}}
    assert result == {
        "key": "ONE-1",
        "status": "To Do",
        "resolution": None,
        "resolutiondate": None,
    }


async def test_transition_comment_is_posted_separately_on_recorded_site(client, replay):
    """The sandbox transitions have no screen, so the comment needs its own request."""
    jira = replay("transition_with_comment")

    result = await client.transition_issue("ONE-1", "Done", comment="Moved by recorder")

    assert [(r.method, r.url.path) for r in jira.requests] == [
        ("GET", "/rest/api/3/issue/ONE-1/transitions"),
        ("POST", "/rest/api/3/issue/ONE-1/transitions"),
        ("POST", "/rest/api/3/issue/ONE-1/comment"),
        ("GET", "/rest/api/3/issue/ONE-1"),
    ]
    assert jira.sent(1) == {"transition": {"id": "31"}}
    assert jira.sent(2) == {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Moved by recorder"}],
                }
            ],
        }
    }
    assert result == {
        "key": "ONE-1",
        "status": "Done",
        "resolution": "Done",
        "resolutiondate": "2026-11-11T12:22:12.835+0200",
    }


async def test_unknown_transition_lists_recorded_options(client, replay):
    jira = replay("transition_not_found")

    result = await client.transition_issue("ONE-1", "No such transition")

    assert len(jira.requests) == 1
    assert result["error"] == {
        "code": "VALIDATION_ERROR",
        "message": (
            "Transition 'No such transition' was not found. Valid options: "
            "11: To Do -> To Do; 21: In Progress -> In Progress; "
            "31: Done -> Done. Use a transition ID to disambiguate."
        ),
    }
