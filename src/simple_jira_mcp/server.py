"""MCP Server entry point for Jira integration."""

import asyncio
import json
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from simple_jira_mcp import schemas
from simple_jira_mcp.config import load_configs
from simple_jira_mcp.jira.client import close_clients
from simple_jira_mcp.tools.attachment import download_attachment as _download_attachment
from simple_jira_mcp.tools.configs import list_configs as _list_configs
from simple_jira_mcp.tools.create import create_issue as _create_issue
from simple_jira_mcp.tools.issue import get_issue as _get_issue
from simple_jira_mcp.tools.search import search_issues as _search_issues
from simple_jira_mcp.tools.workflow import add_comment as _add_comment
from simple_jira_mcp.tools.workflow import get_transitions as _get_transitions
from simple_jira_mcp.tools.workflow import transition_issue as _transition_issue
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


def _log(tool: str, **context: str | None) -> None:
    """Log a tool invocation with its identifying arguments."""
    details = ", ".join(f"{key}={value or 'default'}" for key, value in context.items())
    logger.info("%s invoked (%s)", tool, details or "no arguments")


def _result(payload: ToolResult) -> CallToolResult:
    """Wrap a tool payload, setting the protocol error flag for error payloads."""
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, indent=2))],
        structured_content=payload,
        is_error=bool(payload.get("isError")),
    )


@mcp.tool(
    title="List Jira configurations",
    description="List configured Jira instances and their config_id values.",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
async def list_configs() -> CallToolResult:
    """List configured Jira instances."""
    _log("list_configs")
    return _result(await _list_configs())


@mcp.tool(
    title="Search Jira issues",
    description=(
        "Search issues via JQL. The query needs at least one bounding clause — "
        "project, status, assignee, reporter, priority, type/issuetype, key, id, "
        "or created/updated/resolved — but it does not have to be scoped to a "
        "project. Quote values that are JQL reserved words: "
        'project = "ON", not project = ON.'
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
    _log("search_issues", config_id=config_id)
    return _result(
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
    _log("get_issue", issue_key=issue_key, config_id=config_id)
    return _result(
        await _get_issue(
            issue_key,
            config_id=config_id,
            include_comments=include_comments,
            include_attachments=include_attachments,
        )
    )


@mcp.tool(
    title="Create Jira issue",
    description="Create a Jira issue. Returns issue key and URL.",
    annotations=WRITE,
)
async def create_issue(
    project_key: schemas.ProjectKey,
    summary: schemas.Summary,
    issue_type: schemas.IssueType = "Task",
    description: schemas.Description = None,
    priority: schemas.Priority = None,
    labels: schemas.Labels = None,
    assignee_account_id: schemas.AssigneeAccountId = None,
    config_id: schemas.ConfigId = None,
) -> CallToolResult:
    """Create a new Jira issue."""
    _log("create_issue", project_key=project_key, config_id=config_id)
    return _result(
        await _create_issue(
            project_key,
            summary,
            issue_type=issue_type,
            description=description,
            priority=priority,
            labels=labels,
            assignee_account_id=assignee_account_id,
            config_id=config_id,
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
    _log("get_transitions", issue_key=issue_key, config_id=config_id)
    return _result(await _get_transitions(issue_key, config_id=config_id))


@mcp.tool(
    title="Transition Jira issue",
    description=(
        "Transition a Jira issue using a transition ID or a case-insensitive "
        "transition/target-status name. Optional plain-text comment is posted in "
        "the same request. Resolution and fields must be accepted by the transition "
        "screen. Returns the new status, resolution, and resolutiondate. Jira sets "
        "resolutiondate itself; the API cannot edit it. Record the actual completion "
        "date in the comment."
    ),
    annotations=WRITE,
)
async def transition_issue(
    issue_key: schemas.IssueKey,
    transition: schemas.Transition,
    comment: schemas.TransitionComment = None,
    resolution: schemas.Resolution = None,
    fields: schemas.TransitionFields = None,
    config_id: schemas.ConfigId = None,
) -> CallToolResult:
    """Transition an issue and return its updated state."""
    _log("transition_issue", issue_key=issue_key, config_id=config_id)
    return _result(
        await _transition_issue(
            issue_key,
            transition,
            comment=comment,
            resolution=resolution,
            fields=fields,
            config_id=config_id,
        )
    )


@mcp.tool(
    title="Add Jira comment",
    description="Add a plain-text comment to a Jira issue. Returns ID and created.",
    annotations=WRITE,
)
async def add_comment(
    issue_key: schemas.IssueKey,
    body: schemas.CommentBody,
    config_id: schemas.ConfigId = None,
) -> CallToolResult:
    """Add a comment to an issue."""
    _log("add_comment", issue_key=issue_key, config_id=config_id)
    return _result(await _add_comment(issue_key, body, config_id=config_id))


@mcp.tool(
    title="Download Jira attachment",
    description="Download an attachment from a Jira issue to a local file.",
    annotations=WRITE,
)
async def download_attachment(
    issue_key: schemas.IssueKey,
    attachment_id: schemas.AttachmentId,
    output_dir: schemas.OutputDir = None,
    config_id: schemas.ConfigId = None,
) -> CallToolResult:
    """Download an attachment from a Jira issue."""
    _log(
        "download_attachment",
        issue_key=issue_key,
        attachment_id=attachment_id,
        config_id=config_id,
    )
    return _result(
        await _download_attachment(
            issue_key,
            attachment_id,
            output_dir=output_dir,
            config_id=config_id,
        )
    )


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
