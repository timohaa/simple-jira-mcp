"""Tests for workflow tools exposed through FastMCP."""

import json
from unittest.mock import AsyncMock

import pytest

from src import server


async def test_workflow_tool_schemas():
    tools = {tool.name: tool for tool in await server.mcp.list_tools()}
    expected = {
        "get_transitions": ({"issue_key", "config_id"}, {"issue_key"}),
        "transition_issue": (
            {"issue_key", "transition", "comment", "resolution", "fields", "config_id"},
            {"issue_key", "transition"},
        ),
        "add_comment": ({"issue_key", "body", "config_id"}, {"issue_key", "body"}),
    }
    for name, (properties, required) in expected.items():
        assert set(tools[name].inputSchema["properties"]) == properties
        assert set(tools[name].inputSchema["required"]) == required
    description = tools["transition_issue"].description
    assert "resolutiondate" in description
    assert "API cannot edit it" in description
    assert "actual completion date in the comment" in description


@pytest.mark.parametrize(
    "tool_name,arguments,expected_args,expected_kwargs",
    [
        (
            "get_transitions",
            {"issue_key": "ONE-123", "config_id": "work"},
            ("ONE-123",),
            {"config_id": "work"},
        ),
        (
            "transition_issue",
            {
                "issue_key": "ONE-123",
                "transition": "Done",
                "comment": "Completed yesterday",
                "resolution": "Fixed",
                "fields": {"customfield_1": "Done"},
                "config_id": "work",
            },
            ("ONE-123", "Done"),
            {
                "comment": "Completed yesterday",
                "resolution": "Fixed",
                "fields": {"customfield_1": "Done"},
                "config_id": "work",
            },
        ),
        (
            "add_comment",
            {"issue_key": "ONE-123", "body": "Comment", "config_id": "work"},
            ("ONE-123", "Comment"),
            {"config_id": "work"},
        ),
    ],
)
@pytest.mark.parametrize("is_error", [False, True])
async def test_workflow_mcp_calls(
    monkeypatch, capsys, tool_name, arguments, expected_args, expected_kwargs, is_error
):
    response = (
        {"isError": True, "error": {"code": "JIRA_ERROR", "message": "Failed"}}
        if is_error
        else {"status": "Done"}
    )
    method = AsyncMock(return_value=response)
    monkeypatch.setattr(server, f"_{tool_name}", method)

    content, structured = await server.mcp.call_tool(tool_name, arguments)

    method.assert_awaited_once_with(*expected_args, **expected_kwargs)
    assert structured == response
    assert json.loads(content[0].text) == response
    assert capsys.readouterr().out == ""
