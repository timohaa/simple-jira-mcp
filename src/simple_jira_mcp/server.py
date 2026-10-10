"""MCP Server entry point and registration of the read-only tools."""

import asyncio
import logging
import sys

from mcp.types import CallToolResult, ToolAnnotations

# Imported for its side effect of registering the write tools.
import simple_jira_mcp.write_tools  # noqa: F401
from simple_jira_mcp import schemas
from simple_jira_mcp.app import READ_ONLY, log_call, mcp, tool_result
from simple_jira_mcp.config import load_configs
from simple_jira_mcp.tools.configs import list_configs as _list_configs
from simple_jira_mcp.tools.issue import get_issue as _get_issue
from simple_jira_mcp.tools.search import search_issues as _search_issues
from simple_jira_mcp.tools.workflow import get_transitions as _get_transitions

logger = logging.getLogger(__name__)


@mcp.tool(
    title="List Jira configurations",
    description="List configured Jira instances and their config_id values.",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
async def list_configs() -> CallToolResult:
    """List configured Jira instances."""
    log_call("list_configs")
    return tool_result(await _list_configs())


@mcp.tool(
    title="Search Jira issues",
    description=(
        "Search issues using JQL. Include at least one bounding clause: project, "
        "status, assignee, reporter, priority, type/issuetype, key, id, or "
        "created/updated/resolved. A project filter is optional. "
        'Quote JQL reserved values, for example project = "ON".'
    ),
    annotations=READ_ONLY,
)
async def search_issues(
    jql: schemas.Jql,
    config_id: schemas.ConfigId = None,
    limit: schemas.Limit = 50,
    next_page_token: schemas.NextPageToken = None,
    fields: schemas.SearchFields = None,
) -> CallToolResult:
    """Search for Jira issues using JQL."""
    log_call("search_issues", config_id=config_id)
    return tool_result(
        await _search_issues(
            jql,
            config_id=config_id,
            limit=limit,
            next_page_token=next_page_token,
            fields=fields,
        )
    )


@mcp.tool(
    title="Get Jira issue",
    description="Get full details for a Jira issue by key (e.g., ONE-123).",
    annotations=READ_ONLY,
)
async def get_issue(
    issue_key: schemas.IssueKey,
    config_id: schemas.ConfigId = None,
    include_comments: schemas.IncludeComments = True,
    include_attachments: schemas.IncludeAttachments = True,
) -> CallToolResult:
    """Get detailed information for a single issue."""
    log_call("get_issue", issue_key=issue_key, config_id=config_id)
    return tool_result(
        await _get_issue(
            issue_key,
            config_id=config_id,
            include_comments=include_comments,
            include_attachments=include_attachments,
        )
    )


@mcp.tool(
    title="Get Jira issue transitions",
    description=(
        "Get available transitions for a Jira issue. Returns transition IDs, names, "
        "target statuses, and screen fields with required flags and allowed values."
    ),
    annotations=READ_ONLY,
)
async def get_transitions(
    issue_key: schemas.IssueKey, config_id: schemas.ConfigId = None
) -> CallToolResult:
    """Get available transitions and transition screen fields."""
    log_call("get_transitions", issue_key=issue_key, config_id=config_id)
    return tool_result(await _get_transitions(issue_key, config_id=config_id))


async def main() -> None:
    """Run the MCP server."""
    # Stdout is the JSON-RPC channel, so all logging goes to stderr. force=True
    # replaces the handler MCPServer installs when it is constructed.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
        force=True,
    )

    try:
        load_configs()
    except ValueError as e:
        logger.error("Failed to load configuration: %s", e)
        sys.exit(1)

    logger.info("Starting Jira MCP server...")
    await mcp.run_stdio_async()


def run() -> None:
    """Console-script entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
