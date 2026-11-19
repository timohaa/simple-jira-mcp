"""Tests for list_configs tool."""

import json
import os

import simple_jira_mcp.config
from simple_jira_mcp.tools.configs import list_configs


class TestListConfigs:
    async def test_returns_empty_when_no_configs(self, clean_config):
        result = await list_configs()

        assert result == {"configs": []}

    async def test_returns_single_config_without_credentials(self, mock_config):
        result = await list_configs()

        assert result == {
            "configs": [
                {
                    "id": "test",
                    "url": "https://test.atlassian.net",
                    "default": True,
                    "timeout": 30.0,
                }
            ]
        }

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

    async def test_returns_multiple_configs(self, two_configs):
        result = await list_configs()

        assert len(result["configs"]) == 2
        assert result["configs"][0]["id"] == "default"
        assert result["configs"][0]["default"] is True
        assert result["configs"][1]["id"] == "second"
        assert result["configs"][1]["default"] is False
