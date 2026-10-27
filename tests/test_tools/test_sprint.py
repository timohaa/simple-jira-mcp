"""Tests for sprint tool validation and config selection."""

import json
from unittest.mock import AsyncMock

import pytest

from simple_jira_mcp.config import load_configs, reset_config_state
from simple_jira_mcp.jira import client as jira_client
from simple_jira_mcp.jira.client import JiraClient
from simple_jira_mcp.tools import sprint


@pytest.fixture(autouse=True)
def clean_config():
    reset_config_state()
    yield
    reset_config_state()


@pytest.fixture
def mock_config(monkeypatch):
    monkeypatch.setenv(
        "JIRA_CONFIG_JSON",
        json.dumps(
            [
                {
                    "id": config_id,
                    "url": f"https://{config_id}.atlassian.net",
                    "email": "user@example.com",
                    "token": "test-token",
                }
                for config_id in ("default", "second")
            ]
        ),
    )
    return load_configs()


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
async def test_list_sprints_validation(mock_config, kwargs):
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
async def test_move_validation(mock_config, sprint_id, issue_keys):
    result = await sprint.move_issues_to_sprint(sprint_id, issue_keys)

    assert result["error"]["code"] == "VALIDATION_ERROR"


async def test_missing_config():
    list_result = await sprint.list_sprints(project_key="ONE")
    move_result = await sprint.move_issues_to_sprint(5, ["ONE-1"])

    assert list_result["error"]["code"] == "CONFIG_NOT_FOUND"
    assert move_result["error"]["code"] == "CONFIG_NOT_FOUND"


async def test_unknown_config(mock_config):
    list_result = await sprint.list_sprints(board_id=1, config_id="unknown")
    move_result = await sprint.move_issues_to_sprint(5, ["ONE-1"], config_id="unknown")

    assert list_result["error"]["code"] == "CONFIG_NOT_FOUND"
    assert move_result["error"]["code"] == "CONFIG_NOT_FOUND"


@pytest.mark.parametrize("config_id", [None, "second"])
async def test_list_sprints_normalizes_and_forwards(
    mock_config, monkeypatch, config_id
):
    method = AsyncMock(return_value={"sprints": []})
    monkeypatch.setattr(JiraClient, "list_sprints", method)

    result = await sprint.list_sprints(
        project_key=" one ", state="Active, future,active", config_id=config_id
    )

    assert result == {"sprints": []}
    method.assert_awaited_once_with(
        project_key="ONE", board_id=None, states=["active", "future"]
    )
    expected = jira_client.get_client(config_id)
    assert expected.config.id == (config_id or "default")


async def test_list_sprints_board_id_wins_over_project(mock_config, monkeypatch):
    method = AsyncMock(return_value={"sprints": []})
    monkeypatch.setattr(JiraClient, "list_sprints", method)

    await sprint.list_sprints(project_key="not a key", board_id=4)

    method.assert_awaited_once_with(
        project_key=None, board_id=4, states=["active", "future"]
    )


async def test_move_normalizes_and_dedupes(mock_config, monkeypatch):
    method = AsyncMock(return_value={"sprint_id": 5, "moved": []})
    monkeypatch.setattr(JiraClient, "move_issues_to_sprint", method)

    await sprint.move_issues_to_sprint(
        5, [" one-1", "ONE-2", "ONE-1"], config_id="second"
    )

    method.assert_awaited_once_with(5, ["ONE-1", "ONE-2"])
