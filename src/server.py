"""MCP Server entry point for Jira integration."""

import asyncio
import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.config import load_configs
from src.tools.attachment import download_attachment as _download_attachment
from src.tools.configs import list_configs as _list_configs
from src.tools.create import create_issue as _create_issue
from src.tools.issue import get_issue as _get_issue
from src.tools.search import search_issues as _search_issues

# Configure logging to stderr only (critical for MCP stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP(name="jira")


@mcp.tool(description="List configured Jira instances and their config_id values.")
async def list_configs() -> dict[str, Any]:
    """List configured Jira instances."""
    logger.info("list_configs invoked")
    return await _list_configs()


@mcp.tool(description="Search issues via JQL. Requires bounded query.")
async def search_issues(
    jql: str,
    config_id: str | None = None,
    limit: int = 50,
    next_page_token: str | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Search for Jira issues using JQL."""
    logger.info("search_issues invoked (config_id=%s)", config_id or "default")
    return await _search_issues(
        jql,
        config_id=config_id,
        limit=limit,
        next_page_token=next_page_token,
        fields=fields,
    )


@mcp.tool(description="Get full details for a Jira issue by key (e.g., ONE-123).")
async def get_issue(
    issue_key: str,
    config_id: str | None = None,
    include_comments: bool = True,
    include_attachments: bool = True,
) -> dict[str, Any]:
    """Get detailed information for a single issue."""
    logger.info(
        "get_issue invoked (issue_key=%s, config_id=%s)",
        issue_key,
        config_id or "default",
    )
    return await _get_issue(
        issue_key,
        config_id=config_id,
        include_comments=include_comments,
        include_attachments=include_attachments,
    )


@mcp.tool(description="Create a Jira issue. Returns issue key and URL.")
async def create_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    assignee_account_id: str | None = None,
    config_id: str | None = None,
) -> dict[str, Any]:
    """Create a new Jira issue."""
    logger.info(
        "create_issue invoked (project_key=%s, config_id=%s)",
        project_key,
        config_id or "default",
    )
    return await _create_issue(
        project_key,
        summary,
        issue_type=issue_type,
        description=description,
        priority=priority,
        labels=labels,
        assignee_account_id=assignee_account_id,
        config_id=config_id,
    )


@mcp.tool(description="Download an attachment from a Jira issue to a local file.")
async def download_attachment(
    issue_key: str,
    attachment_id: str,
    output_dir: str | None = None,
    config_id: str | None = None,
) -> dict[str, Any]:
    """Download an attachment from a Jira issue."""
    logger.info(
        "download_attachment invoked (issue_key=%s, attachment_id=%s, config_id=%s)",
        issue_key,
        attachment_id,
        config_id or "default",
    )
    return await _download_attachment(
        issue_key,
        attachment_id,
        output_dir=output_dir,
        config_id=config_id,
    )


async def main() -> None:
    """Run the MCP server."""
    # Load configurations on startup
    try:
        load_configs()
    except ValueError as e:
        logger.error("Failed to load configuration: %s", e)
        sys.exit(1)

    logger.info("Starting Jira MCP server...")
    await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
