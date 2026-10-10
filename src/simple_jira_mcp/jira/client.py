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

from simple_jira_mcp.config import JiraConfig, get_config
from simple_jira_mcp.jira.attachment import AttachmentOperation
from simple_jira_mcp.jira.base import HttpSession
from simple_jira_mcp.jira.create import CreateIssueParams, CreateOperation
from simple_jira_mcp.jira.issue import IssueOperation
from simple_jira_mcp.jira.search import (
    DEFAULT_SEARCH_FIELDS,
    SearchOperation,
    SearchParams,
)
from simple_jira_mcp.jira.workflow import WorkflowOperation
from simple_jira_mcp.utils.errors import (
    CONFIG_NOT_FOUND,
    ErrorResponse,
    error_response,
)

# Re-export dataclasses for external use
__all__ = [
    "CreateIssueParams",
    "JiraClient",
    "SearchParams",
    "close_clients",
    "get_client",
]


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
        self._session = HttpSession(config)
        self._search = SearchOperation(config, self._session)
        self._issue = IssueOperation(config, self._session)
        self._create = CreateOperation(config, self._session)
        self._attachment = AttachmentOperation(config, self._session)
        self._workflow = WorkflowOperation(config, self._session)

    async def aclose(self) -> None:
        """Close the pooled HTTP connections."""
        await self._session.aclose()

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


_clients: dict[str, JiraClient] = {}


def get_client(config_id: str | None = None) -> JiraClient | ErrorResponse:
    """Return the pooled client for a configuration.

    Args:
        config_id: The configuration ID. If None, the default config is used.

    Returns:
        The client, or a CONFIG_NOT_FOUND error response.
    """
    config = get_config(config_id)
    if not config:
        message = (
            f"Configuration '{config_id}' not found"
            if config_id
            else "No configuration available"
        )
        return error_response(CONFIG_NOT_FOUND, message)

    client = _clients.get(config.id)
    # Reloading the configuration replaces the JiraConfig objects, which
    # invalidates clients built from the old ones.
    if client is None or client.config is not config:
        client = JiraClient(config)
        _clients[config.id] = client
    return client


async def close_clients() -> None:
    """Close every pooled client. Called on server shutdown."""
    while _clients:
        _, client = _clients.popitem()
        await client.aclose()
