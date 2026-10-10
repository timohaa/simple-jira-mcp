"""Annotated parameter types that give the MCP tool schemas their descriptions."""

from typing import Annotated, Any

from pydantic import Field

from simple_jira_mcp.utils.validation import MAX_LIMIT, MIN_LIMIT, SearchField

ConfigId = Annotated[
    str | None,
    Field(description="Jira instance to use, from list_configs. Omit for the default."),
]
IssueKey = Annotated[str, Field(description="Issue key, e.g. ONE-123.")]

# search_issues
Jql = Annotated[str, Field(description="JQL query with at least one bounding clause.")]
Limit = Annotated[
    int, Field(ge=MIN_LIMIT, le=MAX_LIMIT, description="Maximum issues to return.")
]
NextPageToken = Annotated[
    str | None,
    Field(description="next_page_token from the previous page of this query."),
]
SearchFields = Annotated[
    list[SearchField] | None,
    Field(
        description=(
            "Fields to return. Default: summary, status, assignee, priority, "
            "updated, created, labels, issuetype."
        )
    ),
]

# get_issue
IncludeComments = Annotated[bool, Field(description="Include the issue's comments.")]
IncludeAttachments = Annotated[
    bool, Field(description="Include attachment metadata (IDs, filenames).")
]

# create_issue
ProjectKey = Annotated[str, Field(description="Project key, e.g. ONE.")]
Summary = Annotated[str, Field(description="Issue title, at most 255 characters.")]
IssueType = Annotated[str, Field(description="Issue type name, e.g. Task, Bug, Story.")]
Description = Annotated[
    str | None,
    Field(description="Plain-text description. Blank lines separate paragraphs."),
]
Priority = Annotated[str | None, Field(description="Priority name, e.g. High.")]
Labels = Annotated[list[str] | None, Field(description="Labels to set on the issue.")]
AssigneeAccountId = Annotated[
    str | None, Field(description="Atlassian account ID of the assignee.")
]

# transition_issue
Transition = Annotated[
    str, Field(description="Transition ID, transition name, or target status name.")
]
TransitionComment = Annotated[
    str | None, Field(description="Plain-text comment to add with the transition.")
]
Resolution = Annotated[str | None, Field(description="Resolution name, e.g. Fixed.")]
TransitionFields = Annotated[
    dict[str, Any] | None,
    Field(
        description=(
            "Transition-screen fields in Jira REST format, keyed by field ID "
            "as returned by get_transitions."
        )
    ),
]

# add_comment
CommentBody = Annotated[
    str, Field(description="Plain-text comment. Blank lines separate paragraphs.")
]

# download_attachment
AttachmentId = Annotated[
    str, Field(description="Numeric attachment ID from get_issue.")
]
OutputDir = Annotated[
    str | None,
    Field(
        description=(
            "Existing directory to save into; the file lands in an "
            "<issue_key>/ subdirectory. Default: the server's working directory."
        )
    ),
]
