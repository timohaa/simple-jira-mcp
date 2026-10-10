"""Registration of the MCP tools that change Jira or local files."""

from mcp.types import CallToolResult

from simple_jira_mcp import schemas
from simple_jira_mcp.app import DESTRUCTIVE, WRITE, log_call, mcp, tool_result
from simple_jira_mcp.tools.attachment import download_attachment as _download_attachment
from simple_jira_mcp.tools.create import create_issue as _create_issue
from simple_jira_mcp.tools.edit import delete_issue as _delete_issue
from simple_jira_mcp.tools.edit import update_issue as _update_issue
from simple_jira_mcp.tools.workflow import add_comment as _add_comment
from simple_jira_mcp.tools.workflow import transition_issue as _transition_issue


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
    log_call("create_issue", project_key=project_key, config_id=config_id)
    return tool_result(
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
    title="Update Jira issue",
    description=(
        "Update fields on a Jira issue. Omitted parameters stay unchanged. Labels "
        "replace the current set. Use fields for anything else, and a null value "
        'there to clear a field, e.g. {"assignee": null}. Returns the updated '
        "field IDs. To change status, use transition_issue."
    ),
    annotations=DESTRUCTIVE,
)
async def update_issue(
    issue_key: schemas.IssueKey,
    summary: schemas.NewSummary = None,
    description: schemas.Description = None,
    priority: schemas.Priority = None,
    labels: schemas.NewLabels = None,
    assignee_account_id: schemas.AssigneeAccountId = None,
    fields: schemas.UpdateFields = None,
    config_id: schemas.ConfigId = None,
) -> CallToolResult:
    """Update fields on an issue."""
    log_call("update_issue", issue_key=issue_key, config_id=config_id)
    return tool_result(
        await _update_issue(
            issue_key,
            summary=summary,
            description=description,
            priority=priority,
            labels=labels,
            assignee_account_id=assignee_account_id,
            fields=fields,
            config_id=config_id,
        )
    )


@mcp.tool(
    title="Delete Jira issue",
    description=(
        "Permanently delete a Jira issue. Jira cannot restore it. An issue with "
        "subtasks is only deleted when delete_subtasks is true."
    ),
    annotations=DESTRUCTIVE,
)
async def delete_issue(
    issue_key: schemas.IssueKey,
    delete_subtasks: schemas.DeleteSubtasks = False,
    config_id: schemas.ConfigId = None,
) -> CallToolResult:
    """Permanently delete an issue."""
    log_call("delete_issue", issue_key=issue_key, config_id=config_id)
    return tool_result(
        await _delete_issue(
            issue_key, delete_subtasks=delete_subtasks, config_id=config_id
        )
    )


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
    log_call("transition_issue", issue_key=issue_key, config_id=config_id)
    return tool_result(
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
    log_call("add_comment", issue_key=issue_key, config_id=config_id)
    return tool_result(await _add_comment(issue_key, body, config_id=config_id))


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
    log_call(
        "download_attachment",
        issue_key=issue_key,
        attachment_id=attachment_id,
        config_id=config_id,
    )
    return tool_result(
        await _download_attachment(
            issue_key,
            attachment_id,
            output_dir=output_dir,
            config_id=config_id,
        )
    )
