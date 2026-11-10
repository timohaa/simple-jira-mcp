"""Shared fixtures for Jira client tests."""

import pytest

from simple_jira_mcp.config import JiraConfig
from simple_jira_mcp.jira.client import JiraClient


@pytest.fixture
def client():
    """Create a JiraClient with test configuration."""
    config = JiraConfig(
        id="test",
        url="https://example.atlassian.net",
        email="user@example.com",
        token="token",
    )
    return JiraClient(config)


@pytest.fixture
def workflow_transitions():
    """Return transition screen metadata, including a required custom field."""
    return [
        {
            "id": "11",
            "name": "Start work",
            "to": {"id": "3", "name": "In Progress"},
        },
        {
            "id": "31",
            "name": "Finish work",
            "to": {"id": "5", "name": "Done"},
            "fields": {
                "comment": {"name": "Comment", "operations": ["add"]},
                "resolution": {
                    "name": "Resolution",
                    "required": False,
                    "operations": ["set"],
                    "allowedValues": [{"id": "1", "name": "Fixed"}],
                },
                "customfield_10001": {
                    "name": "Completion note",
                    "required": True,
                    "schema": {"type": "string"},
                    "operations": ["set"],
                },
            },
        },
    ]
