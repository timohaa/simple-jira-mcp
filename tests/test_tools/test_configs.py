"""Tests for list_configs tool."""

import json
import os

import pytest

import src.config
from src.config import DEFAULT_TIMEOUT, reset_config_state
from src.tools.configs import list_configs


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
def single_config(clean_config):
    """Set up a single config."""
    config_data = [
        {
            "id": "work",
            "url": "https://work.atlassian.net",
            "email": "work@example.com",
            "token": "work-token",
        }
    ]
    os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
    src.config.load_configs()


@pytest.fixture
def multi_config(clean_config):
    """Set up multiple configs."""
    config_data = [
        {
            "id": "work",
            "url": "https://work.atlassian.net",
            "email": "work@example.com",
            "token": "work-token",
        },
        {
            "id": "personal",
            "url": "https://personal.atlassian.net",
            "email": "personal@example.com",
            "token": "personal-token",
        },
    ]
    os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
    src.config.load_configs()


class TestListConfigs:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_configs(self, clean_config):
        result = await list_configs()

        assert result == {"configs": []}

    @pytest.mark.asyncio
    async def test_never_errors_when_no_configs(self, clean_config):
        # Documented contract: an empty roster is not CONFIG_NOT_FOUND.
        result = await list_configs()

        assert "isError" not in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_returns_single_config(self, single_config):
        result = await list_configs()

        assert len(result["configs"]) == 1
        assert result["configs"][0]["id"] == "work"
        assert result["configs"][0]["url"] == "https://work.atlassian.net"
        assert result["configs"][0]["default"] is True
        assert result["configs"][0]["timeout"] == DEFAULT_TIMEOUT

    @pytest.mark.asyncio
    async def test_surfaces_configured_timeout(self, clean_config):
        config_data = [
            {
                "id": "slow",
                "url": "https://slow.atlassian.net",
                "email": "slow@example.com",
                "token": "slow-token",
                "timeout": 120,
            }
        ]
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
        src.config.load_configs()

        result = await list_configs()

        assert result["configs"][0]["timeout"] == 120.0

    @pytest.mark.asyncio
    async def test_returns_multiple_configs(self, multi_config):
        result = await list_configs()

        assert len(result["configs"]) == 2
        assert result["configs"][0]["id"] == "work"
        assert result["configs"][0]["default"] is True
        assert result["configs"][1]["id"] == "personal"
        assert result["configs"][1]["default"] is False

    @pytest.mark.asyncio
    async def test_does_not_expose_credentials(self, single_config):
        result = await list_configs()

        config = result["configs"][0]
        assert "token" not in config
        assert "email" not in config
        assert "password" not in config
