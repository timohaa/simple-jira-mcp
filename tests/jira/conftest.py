"""Shared fixtures for Jira client tests."""

from functools import partial

import httpx
import pytest

from src.config import JiraConfig
from src.jira.client import JiraClient


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
def patch_async_client(monkeypatch):
    """Patch httpx.AsyncClient in all Jira operation modules."""

    def _apply(transport: httpx.MockTransport) -> None:
        async_client = partial(httpx.AsyncClient, transport=transport)
        monkeypatch.setattr("src.jira.search.httpx.AsyncClient", async_client)
        monkeypatch.setattr("src.jira.issue.httpx.AsyncClient", async_client)
        monkeypatch.setattr("src.jira.create.httpx.AsyncClient", async_client)
        monkeypatch.setattr("src.jira.attachment.httpx.AsyncClient", async_client)
        monkeypatch.setattr("src.jira.workflow.httpx.AsyncClient", async_client)

    return _apply


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
