"""Tests for sprint tool validation and config selection."""

from unittest.mock import AsyncMock

import pytest

from simple_jira_mcp.jira.client import JiraClient
from simple_jira_mcp.tools import sprint

pytestmark = pytest.mark.usefixtures("clean_config")


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"project_key": "  "},
        {"project_key": "bad key"},
        {"project_key": "1"},
        {"board_id": 0},
        {"board_id": -4},
        {"project_key": "ONE", "state": ""},
        {"project_key": "ONE", "state": "active,done"},
    ],
)
async def test_list_sprints_validation(two_configs, kwargs):
    result = await sprint.list_sprints(**kwargs)

    assert result["isError"] is True
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "sprint_id,issue_keys",
    [
        (0, ["ONE-1"]),
        (-1, ["ONE-1"]),
        (5, []),
        (5, ["invalid"]),
        (5, ["ONE-1", "ONE-2/x"]),
        (5, [""]),
    ],
)
async def test_move_validation(two_configs, sprint_id, issue_keys):
    result = await sprint.move_issues_to_sprint(sprint_id, issue_keys)

    assert result["error"]["code"] == "VALIDATION_ERROR"


async def test_missing_config():
    list_result = await sprint.list_sprints(project_key="ONE")
    move_result = await sprint.move_issues_to_sprint(5, ["ONE-1"])

    assert list_result["error"]["code"] == "CONFIG_NOT_FOUND"
    assert move_result["error"]["code"] == "CONFIG_NOT_FOUND"


async def test_unknown_config(two_configs):
    list_result = await sprint.list_sprints(board_id=1, config_id="unknown")
    move_result = await sprint.move_issues_to_sprint(5, ["ONE-1"], config_id="unknown")

    assert list_result["error"]["code"] == "CONFIG_NOT_FOUND"
    assert move_result["error"]["code"] == "CONFIG_NOT_FOUND"


@pytest.mark.parametrize(
    "config_id,used_config", [(None, "default"), ("second", "second")]
)
async def test_list_sprints_normalizes_and_forwards(
    two_configs, monkeypatch, config_id, used_config
):
    calls = []

    async def list_sprints(self, **kwargs):
        calls.append((self.config.id, kwargs))
        return {"sprints": []}

    monkeypatch.setattr(JiraClient, "list_sprints", list_sprints)

    result = await sprint.list_sprints(
        project_key=" one ", state="Active, future,active", config_id=config_id
    )

    assert result == {"sprints": []}
    assert calls == [
        (
            used_config,
            {"project_key": "ONE", "board_id": None, "states": ["active", "future"]},
        )
    ]


async def test_list_sprints_board_id_wins_over_project(two_configs, monkeypatch):
    method = AsyncMock(return_value={"sprints": []})
    monkeypatch.setattr(JiraClient, "list_sprints", method)

    await sprint.list_sprints(project_key="not a key", board_id=4)

    method.assert_awaited_once_with(
        project_key=None, board_id=4, states=["active", "future"]
    )


async def test_move_normalizes_and_dedupes(two_configs, monkeypatch):
    calls = []

    async def move_issues_to_sprint(self, sprint_id, issue_keys):
        calls.append((self.config.id, sprint_id, issue_keys))
        return {"sprint_id": sprint_id, "moved": issue_keys}

    monkeypatch.setattr(JiraClient, "move_issues_to_sprint", move_issues_to_sprint)

    result = await sprint.move_issues_to_sprint(
        5, [" one-1", "ONE-2", "ONE-1"], config_id="second"
    )

    assert calls == [("second", 5, ["ONE-1", "ONE-2"])]
    assert result == {"sprint_id": 5, "moved": ["ONE-1", "ONE-2"]}
