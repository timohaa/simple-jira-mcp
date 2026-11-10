"""Fixtures shared by all tests."""

import json
import os
from functools import partial

import httpx
import pytest

from simple_jira_mcp.config import load_configs, reset_config_state


@pytest.fixture
def clean_config():
    """Reset config state before and after each test."""
    original = os.environ.get("JIRA_CONFIG_JSON")

    reset_config_state()

    yield

    if original:
        os.environ["JIRA_CONFIG_JSON"] = original
    elif "JIRA_CONFIG_JSON" in os.environ:
        del os.environ["JIRA_CONFIG_JSON"]

    reset_config_state()


@pytest.fixture
def mock_config(clean_config):
    """Load a single config with id "test"."""
    config_data = [
        {
            "id": "test",
            "url": "https://test.atlassian.net",
            "email": "test@example.com",
            "token": "test-token",
        }
    ]
    os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
    return load_configs()


@pytest.fixture
def two_configs(clean_config):
    """Load two configs: "default" (the default) and "second"."""
    config_data = [
        {
            "id": config_id,
            "url": f"https://{config_id}.atlassian.net",
            "email": "user@example.com",
            "token": "test-token",
        }
        for config_id in ("default", "second")
    ]
    os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
    return load_configs()


@pytest.fixture
def patch_async_client(monkeypatch):
    """Route the Jira client's HTTP requests through a mock transport."""

    def _apply(transport: httpx.MockTransport) -> None:
        async_client = partial(httpx.AsyncClient, transport=transport)
        monkeypatch.setattr("simple_jira_mcp.jira.base.httpx.AsyncClient", async_client)

    return _apply
