"""Tests for per-config timeout handling in configuration loading."""

import json
import os

import pytest

from simple_jira_mcp.config import load_configs


class TestLoadConfigsTimeout:
    @staticmethod
    def _set_env(timeout=None, config_id="test"):
        """Write a one-entry config to the env, optionally with a timeout."""
        item = {
            "id": config_id,
            "url": "https://test.atlassian.net",
            "email": "test@example.com",
            "token": "test-token",
        }
        if timeout is not None:
            item["timeout"] = timeout
        os.environ["JIRA_CONFIG_JSON"] = json.dumps([item])

    @pytest.mark.parametrize(
        "timeout,expected",
        [(None, 30.0), (90, 90.0), (5, 5.0)],
        ids=["omitted", "explicit", "int"],
    )
    def test_loads_timeout_as_float(self, clean_config, timeout, expected):
        self._set_env(timeout=timeout)

        loaded = load_configs()[0].timeout

        assert isinstance(loaded, float)
        assert loaded == expected

    def test_is_per_config(self, clean_config):
        config_data = [
            {
                "id": "fast",
                "url": "https://fast.atlassian.net",
                "email": "a@example.com",
                "token": "a",
                "timeout": 5,
            },
            {
                "id": "slow",
                "url": "https://slow.atlassian.net",
                "email": "b@example.com",
                "token": "b",
            },
        ]
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)

        configs = load_configs()

        assert configs[0].timeout == 5.0
        assert configs[1].timeout == 30.0

    @pytest.mark.parametrize(
        "item,match",
        [
            ({"timeout": "30"}, "must be a number"),
            ({"timeout": True}, "must be a number"),
            # Reject an explicit `"timeout": null` value.
            ({"timeout": None}, "must be a number"),
            ({"timeout": 0}, "must be positive"),
            ({"timeout": -1}, "must be positive"),
        ],
        ids=["string", "bool", "null", "zero", "negative"],
    )
    def test_rejects_invalid_timeout(self, clean_config, item, match):
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(
            [
                {
                    "id": "test",
                    "url": "https://test.atlassian.net",
                    "email": "test@example.com",
                    "token": "test-token",
                    **item,
                }
            ]
        )

        with pytest.raises(ValueError, match=match):
            load_configs()

    def test_error_names_the_config(self, clean_config):
        self._set_env(timeout=-1, config_id="work")

        with pytest.raises(ValueError, match="Config 'work'"):
            load_configs()
