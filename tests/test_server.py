"""Tests for the tools exposed through the MCP server layer."""

import json
import logging
from unittest.mock import AsyncMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from simple_jira_mcp import app, server, write_tools
from simple_jira_mcp.config import reset_config_state
from simple_jira_mcp.utils.validation import ALLOWED_SEARCH_FIELDS
from tests.server_cases import CALLS, DESTRUCTIVE_TOOLS, READ_ONLY_TOOLS, SCHEMAS


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
            destructive = tool.name in DESTRUCTIVE_TOOLS
            assert tool.annotations.destructive_hint is destructive
            assert tool.annotations.idempotent_hint is destructive
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
    module = server if tool_name in READ_ONLY_TOOLS else write_tools
    monkeypatch.setattr(module, f"_{tool_name}", method)

    result = await server.mcp.call_tool(tool_name, arguments)

    method.assert_awaited_once_with(*expected_args, **expected_kwargs)
    assert result.is_error is is_error
    assert result.structured_content == response
    assert json.loads(result.content[0].text) == response
    assert capsys.readouterr().out == ""


async def test_lifespan_closes_pooled_clients(monkeypatch):
    close = AsyncMock()
    monkeypatch.setattr(app, "close_clients", close)

    async with app._lifespan(app.mcp):
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
