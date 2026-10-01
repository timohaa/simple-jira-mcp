"""Jira API client for REST API v3.

This module provides a unified interface to the Jira Cloud API. The implementation
is split across multiple modules for maintainability:
- base.py: Common utilities and constants
- search.py: Search operations
- issue.py: Get issue operations
- create.py: Create issue operations
- attachment.py: Attachment download operations
- workflow.py: Issue transitions and comments
"""

from pathlib import Path
from typing import Any

from src.config import JiraConfig
from src.jira.attachment import AttachmentOperation
from src.jira.create import CreateIssueParams, CreateOperation
from src.jira.issue import IssueOperation
from src.jira.search import DEFAULT_SEARCH_FIELDS, SearchOperation, SearchParams
from src.jira.workflow import WorkflowOperation
from src.utils.errors import ErrorResponse

# Re-export dataclasses for external use
__all__ = ["CreateIssueParams", "JiraClient", "SearchParams"]


class JiraClient:
    """Async client for Jira Cloud REST API v3.

    This is the main entry point for Jira API operations. It delegates to
    specialized operation classes for each type of operation.
    """

    def __init__(self, config: JiraConfig) -> None:
        """Initialize the Jira client.

        Args:
            config: Jira configuration with URL and credentials.
        """
        self.config = config
        self._search = SearchOperation(config)
        self._issue = IssueOperation(config)
        self._create = CreateOperation(config)
        self._attachment = AttachmentOperation(config)
        self._workflow = WorkflowOperation(config)

    async def search(
        self,
        jql: str,
        *,
        max_results: int = 50,
        next_page_token: str | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any] | ErrorResponse:
        """Search for issues using JQL.

        Args:
            jql: JQL query string.
            max_results: Maximum results to return (1-100).
            next_page_token: Token for cursor-based pagination.
            fields: Fields to return in the response.

        Returns:
            Search results or error response.
        """
        params = SearchParams(
            jql=jql,
            max_results=max_results,
            next_page_token=next_page_token,
            fields=fields if fields is not None else DEFAULT_SEARCH_FIELDS.copy(),
        )
        return await self._search.search(params)

    async def get_issue(
        self,
        issue_key: str,
        *,
        include_comments: bool = True,
        include_attachments: bool = True,
    ) -> dict[str, Any] | ErrorResponse:
        """Get detailed information for a single issue.

        Args:
            issue_key: The Jira issue key (e.g., "ONE-123").
            include_comments: Whether to include comments.
            include_attachments: Whether to include attachment metadata.

        Returns:
            Issue details or error response.
        """
        return await self._issue.get_issue(
            issue_key,
            include_comments=include_comments,
            include_attachments=include_attachments,
        )

    async def create_issue(
        self,
        params: CreateIssueParams,
    ) -> dict[str, Any] | ErrorResponse:
        """Create a new issue.

        Args:
            params: Issue creation parameters.

        Returns:
            Created issue info or error response.
        """
        return await self._create.create_issue(params)

    async def get_transitions(self, issue_key: str) -> dict[str, Any] | ErrorResponse:
        """Get available transitions and their screen fields for an issue."""
        return await self._workflow.get_transitions(issue_key)

    async def transition_issue(
        self,
        issue_key: str,
        transition: str,
        *,
        comment: str | None = None,
        resolution: str | None = None,
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any] | ErrorResponse:
        """Transition an issue by ID or name and return the resulting state."""
        return await self._workflow.transition_issue(
            issue_key, transition, comment=comment, resolution=resolution, fields=fields
        )

    async def add_comment(
        self, issue_key: str, body: str
    ) -> dict[str, Any] | ErrorResponse:
        """Add a plain-text comment to an issue."""
        return await self._workflow.add_comment(issue_key, body)

    async def download_attachment(
        self,
        attachment_id: str,
        output_dir: Path,
        issue_key: str,
        filename: str,
    ) -> dict[str, Any] | ErrorResponse:
        """Download an attachment to a local file.

        Args:
            attachment_id: The attachment ID.
            output_dir: Directory to save the file.
            issue_key: The issue key (for subdirectory).
            filename: The original filename.

        Returns:
            Download result or error response.
        """
        return await self._attachment.download_attachment(
            attachment_id,
            output_dir,
            issue_key,
            filename,
        )
