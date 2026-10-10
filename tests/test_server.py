"""Tests for the tools exposed through the MCP server layer."""

import json
import logging
from unittest.mock import AsyncMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from simple_jira_mcp import server
from simple_jira_mcp.config import reset_config_state
from simple_jira_mcp.utils.validation import ALLOWED_SEARCH_FIELDS

# tool name -> (all properties, required properties)
SCHEMAS = {
    "list_configs": (set(), set()),
    "search_issues": (
        {"jql", "config_id", "limit", "next_page_token", "fields"},
        {"jql"},
    ),
    "get_issue": (
        {"issue_key", "config_id", "include_comments", "include_attachments"},
        {"issue_key"},
    ),
    "create_issue": (
        {
            "project_key",
            "summary",
            "issue_type",
            "description",
            "priority",
            "labels",
            "assignee_account_id",
            "config_id",
        },
        {"project_key", "summary"},
    ),
    "get_transitions": ({"issue_key", "config_id"}, {"issue_key"}),
    "transition_issue": (
        {"issue_key", "transition", "comment", "resolution", "fields", "config_id"},
        {"issue_key", "transition"},
    ),
    "add_comment": ({"issue_key", "body", "config_id"}, {"issue_key", "body"}),
    "download_attachment": (
        {"issue_key", "attachment_id", "output_dir", "config_id"},
        {"issue_key", "attachment_id"},
    ),
}

# (tool name, arguments, expected positional args, expected keyword args)
CALLS = [
    ("list_configs", {}, (), {}),
    (
        "search_issues",
        {
            "jql": "project = ONE",
            "config_id": "work",
            "limit": 10,
            "next_page_token": "tok",
            "fields": ["summary"],
        },
        ("project = ONE",),
        {
            "config_id": "work",
            "limit": 10,
            "next_page_token": "tok",
            "fields": ["summary"],
        },
    ),
    (
        "search_issues",
        {"jql": "project = ONE"},
        ("project = ONE",),
        {"config_id": None, "limit": 50, "next_page_token": None, "fields": None},
    ),
    (
        "get_issue",
        {"issue_key": "ONE-123", "config_id": "work", "include_comments": False},
        ("ONE-123",),
        {"config_id": "work", "include_comments": False, "include_attachments": True},
    ),
    (
        "create_issue",
        {
            "project_key": "ONE",
            "summary": "Title",
            "issue_type": "Bug",
            "description": "Body",
            "priority": "High",
            "labels": ["a"],
            "assignee_account_id": "acc",
            "config_id": "work",
        },
        ("ONE", "Title"),
        {
            "issue_type": "Bug",
            "description": "Body",
            "priority": "High",
            "labels": ["a"],
            "assignee_account_id": "acc",
            "config_id": "work",
        },
    ),
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
    (
        "download_attachment",
        {
            "issue_key": "ONE-123",
            "attachment_id": "42",
            "output_dir": "out",
            "config_id": "work",
        },
        ("ONE-123", "42"),
        {"output_dir": "out", "config_id": "work"},
    ),
]


READ_ONLY_TOOLS = {"list_configs", "search_issues", "get_issue", "get_transitions"}


async def test_tool_schemas():
    tools = {tool.name: tool for tool in await server.mcp.list_tools()}
    assert set(tools) == set(SCHEMAS)
    for name, (properties, required) in SCHEMAS.items():
        schema = tools[name].input_schema
        assert set(schema["properties"]) == properties
        assert set(schema.get("required", [])) == required
        assert all("description" in prop for prop in schema["properties"].values())
        assert tools[name].title


async def test_tool_annotations():
    for tool in await server.mcp.list_tools():
        read_only = tool.name in READ_ONLY_TOOLS
        assert tool.annotations.read_only_hint is read_only
        if not read_only:
            assert tool.annotations.destructive_hint is False
            assert tool.annotations.idempotent_hint is False
        assert tool.annotations.open_world_hint is (tool.name != "list_configs")


async def test_search_schema_constraints():
    tools = {tool.name: tool for tool in await server.mcp.list_tools()}
    properties = tools["search_issues"].input_schema["properties"]

    assert properties["limit"]["minimum"] == 1
    assert properties["limit"]["maximum"] == 100
    field_enum = properties["fields"]["anyOf"][0]["items"]["enum"]
    assert set(field_enum) == ALLOWED_SEARCH_FIELDS


@pytest.mark.parametrize(
    "arguments",
    [
        {"jql": "project = ONE", "limit": 0},
        {"jql": "project = ONE", "limit": 101},
        {"jql": "project = ONE", "fields": ["bogus"]},
        {},
    ],
)
async def test_schema_violations_are_rejected(monkeypatch, arguments):
    method = AsyncMock()
    monkeypatch.setattr(server, "_search_issues", method)

    with pytest.raises(ToolError):
        await server.mcp.call_tool("search_issues", arguments)

    method.assert_not_awaited()


def test_server_instructions():
    assert "list_configs" in server.mcp.instructions


async def test_transition_issue_description():
    tools = {tool.name: tool for tool in await server.mcp.list_tools()}
    description = tools["transition_issue"].description
    assert "resolutiondate" in description
    assert "API cannot edit it" in description
    assert "actual completion date in the comment" in description


@pytest.mark.parametrize("tool_name,arguments,expected_args,expected_kwargs", CALLS)
@pytest.mark.parametrize("is_error", [False, True])
async def test_mcp_calls(
    monkeypatch, capsys, tool_name, arguments, expected_args, expected_kwargs, is_error
):
    response = (
        {"isError": True, "error": {"code": "JIRA_ERROR", "message": "Failed"}}
        if is_error
        else {"status": "Done"}
    )
    method = AsyncMock(return_value=response)
    monkeypatch.setattr(server, f"_{tool_name}", method)

    result = await server.mcp.call_tool(tool_name, arguments)

    method.assert_awaited_once_with(*expected_args, **expected_kwargs)
    assert result.is_error is is_error
    assert result.structured_content == response
    assert json.loads(result.content[0].text) == response
    assert capsys.readouterr().out == ""


async def test_lifespan_closes_pooled_clients(monkeypatch):
    close = AsyncMock()
    monkeypatch.setattr(server, "close_clients", close)

    async with server._lifespan(server.mcp):
        close.assert_not_awaited()

    close.assert_awaited_once()


async def test_main_exits_without_config(monkeypatch):
    monkeypatch.delenv("JIRA_CONFIG_JSON", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        await server.main()

    assert exc_info.value.code == 1


async def test_main_runs_stdio_with_stderr_logging(monkeypatch, capsys):
    monkeypatch.setenv(
        "JIRA_CONFIG_JSON",
        json.dumps(
            [{"id": "a", "url": "https://a.atlassian.net", "email": "e", "token": "t"}]
        ),
    )
    run_stdio = AsyncMock()
    monkeypatch.setattr(server.mcp, "run_stdio_async", run_stdio)
    # main() replaces the root handlers; put pytest's back afterwards.
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", root.handlers[:])
    monkeypatch.setattr(root, "level", root.level)

    try:
        await server.main()
    finally:
        reset_config_state()

    run_stdio.assert_awaited_once()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Starting Jira MCP server" in captured.err
