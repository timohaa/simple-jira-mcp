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
mcp = FastMCP(
    name="jira",
    instructions=(
        "Jira Cloud integration server. Use list_configs to see available "
        "Jira instances, search_issues to find issues via JQL, get_issue "
        "for details, create_issue to create new issues, and "
        "download_attachment to retrieve files."
    ),
)


@mcp.tool(
    description=(
        "List all configured Jira instances available to this server. "
        "Use this to discover which config_id values can be used with other tools."
    )
)
async def list_configs() -> dict[str, Any]:
    """List all configured Jira instances."""
    logger.info("list_configs invoked")
    return await _list_configs()


@mcp.tool(
    description=(
        "Search for Jira issues using JQL (Jira Query Language). "
        "Returns a list of matching issues with key fields. "
        "Note: Jira Cloud requires 'bounded' queries - you must include "
        "at least one limiting filter such as a project, date range, or assignee. "
        "Use next_page_token from the response for pagination."
    )
)
async def search_issues(
    jql: str,
    config_id: str | None = None,
    limit: int = 50,
    next_page_token: str | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Search for Jira issues using JQL.

    Args:
        jql: JQL query string (must include at least one filter).
        config_id: Configuration ID to use. Defaults to first config.
        limit: Maximum results to return (1-100). Defaults to 50.
        next_page_token: Token for cursor-based pagination from previous response.
        fields: Specific fields to return.
    """
    logger.info("search_issues invoked (config_id=%s)", config_id or "default")
    return await _search_issues(
        jql,
        config_id=config_id,
        limit=limit,
        next_page_token=next_page_token,
        fields=fields,
    )


@mcp.tool(
    description=(
        "Fetch complete details for a single Jira issue by its key "
        "(e.g., ONE-123). Returns full description, comments, "
        "attachments, and status information."
    )
)
async def get_issue(
    issue_key: str,
    config_id: str | None = None,
    include_comments: bool = True,
    include_attachments: bool = True,
) -> dict[str, Any]:
    """Get detailed information for a single issue.

    Args:
        issue_key: The Jira issue key (e.g., "ONE-123").
        config_id: Configuration ID to use. Defaults to first config.
        include_comments: Whether to include comments. Defaults to true.
        include_attachments: Whether to include attachment metadata.
    """
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


@mcp.tool(
    description=(
        "Create a new Jira issue in the specified project. "
        "Returns the created issue's key and URL. "
        "Use this to log new tasks, bugs, or other work items."
    )
)
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
    """Create a new Jira issue.

    Args:
        project_key: The project key (e.g., "ONE").
        summary: The issue title/summary. Max 255 characters.
        issue_type: The issue type. Defaults to "Task".
        description: Optional description (plain text).
        priority: Optional priority (Highest, High, Medium, Low, Lowest).
        labels: Optional list of labels.
        assignee_account_id: Optional assignee account ID.
        config_id: Configuration ID to use.
    """
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


@mcp.tool(
    description=(
        "Download an attachment from a Jira issue to a local file. "
        "Useful for retrieving images, documents, or other files "
        "attached to issues for analysis."
    )
)
async def download_attachment(
    issue_key: str,
    attachment_id: str,
    output_dir: str | None = None,
    config_id: str | None = None,
) -> dict[str, Any]:
    """Download an attachment from a Jira issue.

    Args:
        issue_key: The Jira issue key (e.g., "ONE-123").
        attachment_id: The attachment ID from get_issue response.
        output_dir: Directory to save the file. Defaults to current directory.
        config_id: Configuration ID to use.
    """
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
