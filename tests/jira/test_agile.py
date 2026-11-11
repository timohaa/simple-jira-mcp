"""Tests for Agile board and sprint requests."""

import json

import httpx
import pytest


def _sprint(sprint_id, state="active"):
    return {
        "id": sprint_id,
        "name": f"Sprint {sprint_id}",
        "state": state,
        "startDate": "2026-10-01T08:00:00.000Z",
        "endDate": "2026-10-15T08:00:00.000Z",
        "originBoardId": 1,
    }


async def test_list_sprints_by_board(client, patch_async_client):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"values": [_sprint(5)], "isLast": True})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.list_sprints(
        project_key=None, board_id=3, states=["active", "future"]
    )

    assert len(requests) == 1
    assert requests[0].url.path == "/rest/agile/1.0/board/3/sprint"
    params = dict(requests[0].url.params)
    assert params["state"] == "active,future"
    assert params["startAt"] == "0"
    assert requests[0].headers["authorization"].startswith("Basic ")
    assert result == {
        "sprints": [
            {
                "id": 5,
                "name": "Sprint 5",
                "state": "active",
                "startDate": "2026-10-01T08:00:00.000Z",
                "endDate": "2026-10-15T08:00:00.000Z",
                "boardId": 3,
                "boardName": None,
            }
        ]
    }


async def test_list_sprints_by_project_paginates(client, patch_async_client):
    paths = []

    def handler(request):
        paths.append((request.url.path, request.url.params.get("startAt")))
        path = request.url.path
        start = request.url.params["startAt"]
        if path == "/rest/agile/1.0/board":
            assert request.url.params["projectKeyOrId"] == "ONE"
            if start == "0":
                return httpx.Response(
                    200,
                    json={"values": [{"id": 1, "name": "A"}], "isLast": False},
                )
            return httpx.Response(
                200, json={"values": [{"id": 2, "name": "B"}], "isLast": True}
            )
        if path == "/rest/agile/1.0/board/1/sprint":
            if start == "0":
                return httpx.Response(
                    200, json={"values": [_sprint(10)], "isLast": False}
                )
            return httpx.Response(
                200, json={"values": [_sprint(11, "future")], "isLast": True}
            )
        return httpx.Response(200, json={"values": [_sprint(20)], "isLast": True})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.list_sprints(
        project_key="ONE", board_id=None, states=["active"]
    )

    assert [(s["id"], s["boardId"], s["boardName"]) for s in result["sprints"]] == [
        (10, 1, "A"),
        (11, 1, "A"),
        (20, 2, "B"),
    ]
    assert ("/rest/agile/1.0/board", "1") in paths
    assert ("/rest/agile/1.0/board/1/sprint", "1") in paths


async def test_list_sprints_skips_boards_without_sprints(client, patch_async_client):
    def handler(request):
        path = request.url.path
        if path == "/rest/agile/1.0/board":
            return httpx.Response(
                200,
                json={
                    "values": [{"id": 1, "name": "Kanban"}, {"id": 2, "name": "Scrum"}],
                    "isLast": True,
                },
            )
        if path.endswith("/board/1/sprint"):
            return httpx.Response(
                400, json={"errorMessages": ["The board does not support sprints"]}
            )
        return httpx.Response(200, json={"values": [_sprint(7)], "isLast": True})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.list_sprints(
        project_key="ONE", board_id=None, states=["active"]
    )

    assert [s["id"] for s in result["sprints"]] == [7]


async def test_list_sprints_explicit_board_without_sprints_errors(
    client, patch_async_client
):
    patch_async_client(
        httpx.MockTransport(
            lambda request: httpx.Response(
                400, json={"errorMessages": ["The board does not support sprints"]}
            )
        )
    )
    result = await client.list_sprints(project_key=None, board_id=1, states=["active"])

    assert result["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "The board does not support sprints",
    }


async def test_list_sprints_no_boards(client, patch_async_client):
    patch_async_client(
        httpx.MockTransport(
            lambda request: httpx.Response(200, json={"values": [], "isLast": True})
        )
    )
    result = await client.list_sprints(
        project_key="ONE", board_id=None, states=["active"]
    )

    assert result == {"sprints": []}


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "AUTH_FAILED"),
        (404, "BOARD_NOT_FOUND"),
        (429, "RATE_LIMITED"),
        (500, "JIRA_ERROR"),
    ],
)
async def test_list_sprints_http_errors(client, patch_async_client, status, code):
    patch_async_client(
        httpx.MockTransport(lambda request: httpx.Response(status, json={}))
    )
    result = await client.list_sprints(project_key=None, board_id=9, states=["active"])

    assert result["error"]["code"] == code


async def test_list_sprints_page_error_after_first_page(client, patch_async_client):
    def handler(request):
        if request.url.params["startAt"] == "0":
            return httpx.Response(200, json={"values": [_sprint(1)], "isLast": False})
        return httpx.Response(429, json={})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.list_sprints(project_key=None, board_id=1, states=["active"])

    assert result["error"]["code"] == "RATE_LIMITED"


async def test_list_sprints_stops_on_empty_page(client, patch_async_client):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"values": [], "isLast": False})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.list_sprints(project_key=None, board_id=1, states=["active"])

    assert result == {"sprints": []}
    assert len(calls) == 1


async def test_list_sprints_connection_error(client, patch_async_client):
    def handler(request):
        raise httpx.ConnectError("boom")

    patch_async_client(httpx.MockTransport(handler))
    result = await client.list_sprints(project_key=None, board_id=1, states=["active"])

    assert result["error"]["code"] == "JIRA_ERROR"


async def test_move_issues_single_request(client, patch_async_client):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(204)

    patch_async_client(httpx.MockTransport(handler))
    result = await client.move_issues_to_sprint(12, ["ONE-1", "ONE-2"])

    assert result == {"sprint_id": 12, "moved": ["ONE-1", "ONE-2"]}
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/rest/agile/1.0/sprint/12/issue"
    assert requests[0].read() == b'{"issues":["ONE-1","ONE-2"]}'


async def test_move_issues_batches_of_50(client, patch_async_client):
    batches = []

    def handler(request):
        batches.append(json.loads(request.read())["issues"])
        return httpx.Response(204)

    keys = [f"ONE-{i}" for i in range(1, 121)]
    patch_async_client(httpx.MockTransport(handler))
    result = await client.move_issues_to_sprint(12, keys)

    assert [len(batch) for batch in batches] == [50, 50, 20]
    assert result == {"sprint_id": 12, "moved": keys}


async def test_move_issues_partial_failure_reports_moved(client, patch_async_client):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(204)
        return httpx.Response(400, json={"errorMessages": ["Sprint is closed"]})

    keys = [f"ONE-{i}" for i in range(1, 52)]
    patch_async_client(httpx.MockTransport(handler))
    result = await client.move_issues_to_sprint(12, keys)

    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert result["error"]["message"].startswith("Sprint is closed Already moved")
    assert "ONE-1," in result["error"]["message"]
    assert "ONE-51" not in result["error"]["message"]


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "VALIDATION_ERROR"),
        (401, "AUTH_FAILED"),
        (404, "SPRINT_NOT_FOUND"),
        (429, "RATE_LIMITED"),
        (500, "JIRA_ERROR"),
    ],
)
async def test_move_issues_http_errors(client, patch_async_client, status, code):
    patch_async_client(
        httpx.MockTransport(lambda request: httpx.Response(status, json={}))
    )
    result = await client.move_issues_to_sprint(12, ["ONE-1"])

    assert result["error"]["code"] == code
    assert "moved before" not in result["error"]["message"]


async def test_list_sprints_of_recorded_project(client, replay):
    jira = replay("list_sprints")

    result = await client.list_sprints(
        project_key="ONE", board_id=None, states=["active", "future"]
    )

    assert [str(request.url) for request in jira.requests] == [
        "https://example.atlassian.net/rest/agile/1.0/board"
        "?projectKeyOrId=ONE&startAt=0&maxResults=50",
        "https://example.atlassian.net/rest/agile/1.0/board/2/sprint"
        "?state=active%2Cfuture&startAt=0&maxResults=50",
    ]
    assert result == {
        "sprints": [
            {
                "id": 3,
                "name": "ONE Sprint 1",
                "state": "future",
                "startDate": None,
                "endDate": None,
                "boardId": 2,
                "boardName": "ONE board",
            }
        ]
    }


async def test_move_issue_to_recorded_sprint(client, replay):
    jira = replay("move_issues_to_sprint")

    result = await client.move_issues_to_sprint(3, ["ONE-1"])

    assert jira.sent(0) == {"issues": ["ONE-1"]}
    assert result == {"sprint_id": 3, "moved": ["ONE-1"]}


async def test_move_to_missing_sprint_is_not_found(client, replay):
    replay("move_issues_sprint_not_found")

    result = await client.move_issues_to_sprint(99999999, ["ONE-1"])

    assert result["error"] == {
        "code": "SPRINT_NOT_FOUND",
        "message": "Sprint 99999999 not found",
    }
