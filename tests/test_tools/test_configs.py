"""Tests for list_configs tool."""

import json
import os

import pytest

import simple_jira_mcp.config
from simple_jira_mcp.tools.configs import list_configs


class TestListConfigs:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_configs(self, clean_config):
        result = await list_configs()

        assert result == {"configs": []}

    @pytest.mark.asyncio
    async def test_never_errors_when_no_configs(self, clean_config):
        # Return an empty list when no configurations are loaded.
        result = await list_configs()

        assert "isError" not in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_returns_single_config(self, mock_config):
        result = await list_configs()

        assert len(result["configs"]) == 1
        assert result["configs"][0]["id"] == "test"
        assert result["configs"][0]["url"] == "https://test.atlassian.net"
        assert result["configs"][0]["default"] is True
        assert result["configs"][0]["timeout"] == 30.0

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
        simple_jira_mcp.config.load_configs()

        result = await list_configs()

        assert result["configs"][0]["timeout"] == 120.0

    @pytest.mark.asyncio
    async def test_returns_multiple_configs(self, two_configs):
        result = await list_configs()

        assert len(result["configs"]) == 2
        assert result["configs"][0]["id"] == "default"
        assert result["configs"][0]["default"] is True
        assert result["configs"][1]["id"] == "second"
        assert result["configs"][1]["default"] is False

    @pytest.mark.asyncio
    async def test_does_not_expose_credentials(self, mock_config):
        result = await list_configs()

        config = result["configs"][0]
        assert "token" not in config
        assert "email" not in config
        assert "password" not in config
