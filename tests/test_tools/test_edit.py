"""Tests for update_issue and delete_issue tool validation and config selection."""

import json
from unittest.mock import AsyncMock

import pytest

from simple_jira_mcp.config import load_configs, reset_config_state
from simple_jira_mcp.jira import client as jira_client
from simple_jira_mcp.jira.client import JiraClient, UpdateIssueParams
from simple_jira_mcp.tools import edit

TOOL_ARGUMENTS = [
    ("update_issue", {"summary": "Title"}),
    ("delete_issue", {}),
]


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


@pytest.fixture
def client_method(mock_config, monkeypatch):
    """Replace one JiraClient method with a mock and record the configs used."""

    def _apply(name):
        method = AsyncMock(return_value={"success": True})
        method.configs = []
        real_client = JiraClient

        def make_client(config):
            method.configs.append(config)
            client = real_client(config)
            setattr(client, name, method)
            return client

        monkeypatch.setattr(jira_client, "JiraClient", make_client)
        return method

    return _apply


@pytest.mark.parametrize("tool_name,kwargs", TOOL_ARGUMENTS)
@pytest.mark.parametrize("issue_key", ["", "   ", "invalid", "ONE-1/comment"])
async def test_issue_key_validation(mock_config, tool_name, kwargs, issue_key):
    result = await getattr(edit, tool_name)(issue_key, **kwargs)

    assert result["isError"] is True
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("tool_name,kwargs", TOOL_ARGUMENTS)
async def test_missing_config(tool_name, kwargs):
    result = await getattr(edit, tool_name)("ONE-123", **kwargs)

    assert result["error"]["code"] == "CONFIG_NOT_FOUND"
    assert result["error"]["message"] == "No configuration available"


@pytest.mark.parametrize("tool_name,kwargs", TOOL_ARGUMENTS)
async def test_unknown_config(mock_config, tool_name, kwargs):
    result = await getattr(edit, tool_name)("ONE-123", config_id="unknown", **kwargs)

    assert result["error"]["code"] == "CONFIG_NOT_FOUND"
    assert "unknown" in result["error"]["message"]


@pytest.mark.parametrize("tool_name,kwargs", TOOL_ARGUMENTS)
@pytest.mark.parametrize("config_id", [None, "second"])
async def test_config_and_key_normalization(
    client_method, tool_name, kwargs, config_id
):
    method = client_method(tool_name)

    result = await getattr(edit, tool_name)(" one-123 ", config_id=config_id, **kwargs)

    assert result == {"success": True}
    assert method.configs[0].id == (config_id or "default")
    assert method.await_args.args[0] == "ONE-123"


async def test_update_issue_forwards_params(client_method):
    method = client_method("update_issue")

    await edit.update_issue(
        "ONE-123",
        summary="  Title  ",
        description="",
        priority="High",
        labels=[],
        assignee_account_id="acc",
        fields={"duedate": None},
    )

    method.assert_awaited_once_with(
        "ONE-123",
        UpdateIssueParams(
            summary="Title",
            description="",
            priority="High",
            labels=[],
            assignee_account_id="acc",
            fields={"duedate": None},
        ),
    )


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"summary": ""}, "Summary must not be empty"),
        ({"summary": "   "}, "Summary must not be empty"),
        ({"summary": "x" * 256}, "Summary exceeds maximum length of 255 characters"),
        ({"priority": " "}, "Priority must not be empty"),
        ({"assignee_account_id": ""}, "Assignee account ID must not be empty"),
    ],
)
async def test_update_issue_validation(client_method, kwargs, message):
    method = client_method("update_issue")

    result = await edit.update_issue("ONE-123", **kwargs)

    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert message in result["error"]["message"]
    method.assert_not_awaited()


async def test_update_issue_without_changes(mock_config):
    result = await edit.update_issue("ONE-123")

    assert result["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "No fields to update",
    }


@pytest.mark.parametrize("delete_subtasks", [False, True])
async def test_delete_issue_forwards_subtask_flag(client_method, delete_subtasks):
    method = client_method("delete_issue")

    await edit.delete_issue("ONE-123", delete_subtasks=delete_subtasks)

    method.assert_awaited_once_with("ONE-123", delete_subtasks=delete_subtasks)
