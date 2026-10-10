"""The MCP server instance and the helpers shared by tool registrations."""

import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from simple_jira_mcp.jira.client import close_clients
from simple_jira_mcp.utils.errors import ToolResult

logger = logging.getLogger(__name__)

INSTRUCTIONS = (
    "Tools for Jira Cloud. Every tool except list_configs takes an optional "
    "config_id; omit it to use the default instance, or call list_configs to see "
    "the choices. search_issues needs a bounded JQL query. Call get_transitions "
    "before transition_issue to learn the valid transitions and screen fields."
)

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)
WRITE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=True,
)
# Overwrites or removes existing data; repeating the call changes nothing more.
DESTRUCTIVE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=True,
    open_world_hint=True,
)


@asynccontextmanager
async def _lifespan(_: MCPServer[None]) -> AsyncGenerator[None]:
    """Close pooled Jira HTTP connections on shutdown."""
    try:
        yield
    finally:
        await close_clients()


mcp = MCPServer(
    name="jira",
    version=version("simple-jira-mcp"),
    instructions=INSTRUCTIONS,
    lifespan=_lifespan,
)


def log_call(tool: str, **context: str | None) -> None:
    """Log a tool invocation with its identifying arguments."""
    details = ", ".join(f"{key}={value or 'default'}" for key, value in context.items())
    logger.info("%s invoked (%s)", tool, details or "no arguments")


def tool_result(payload: ToolResult) -> CallToolResult:
    """Wrap a tool payload, setting the protocol error flag for error payloads."""
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, indent=2))],
        structured_content=payload,
        is_error=bool(payload.get("isError")),
    )
