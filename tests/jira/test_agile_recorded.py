"""Tests for Agile sprint requests replayed from recorded Jira exchanges."""


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
