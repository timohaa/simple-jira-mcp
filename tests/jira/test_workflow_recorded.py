"""Tests for workflow transitions replayed from recorded Jira exchanges."""

import pytest

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


@pytest.mark.parametrize("transition", ["to do", "11"], ids=["by-name", "by-id"])
async def test_transition_on_recorded_site(client, replay, transition):
    jira = replay("transition_issue")

    result = await client.transition_issue("ONE-1", transition)

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
