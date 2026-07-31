"""Tests for per-config timeout handling in configuration loading."""

import json
import os

import pytest

from src.config import DEFAULT_TIMEOUT, load_configs, reset_config_state


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

    def test_defaults_when_omitted(self, clean_config):
        self._set_env()

        assert load_configs()[0].timeout == DEFAULT_TIMEOUT

    def test_honours_explicit_value(self, clean_config):
        self._set_env(timeout=90)

        assert load_configs()[0].timeout == 90.0

    def test_coerces_int_to_float(self, clean_config):
        self._set_env(timeout=5)

        timeout = load_configs()[0].timeout

        assert isinstance(timeout, float)
        assert timeout == 5.0

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
        assert configs[1].timeout == DEFAULT_TIMEOUT

    def test_raises_on_string(self, clean_config):
        self._set_env(timeout="30")

        with pytest.raises(ValueError, match="must be a number"):
            load_configs()

    def test_raises_on_bool(self, clean_config):
        self._set_env(timeout=True)

        with pytest.raises(ValueError, match="must be a number"):
            load_configs()

    def test_raises_on_null(self, clean_config):
        # An explicit `"timeout": null` is a mistake, not an omission.
        os.environ["JIRA_CONFIG_JSON"] = json.dumps(
            [
                {
                    "id": "test",
                    "url": "https://test.atlassian.net",
                    "email": "test@example.com",
                    "token": "test-token",
                    "timeout": None,
                }
            ]
        )

        with pytest.raises(ValueError, match="must be a number"):
            load_configs()

    def test_raises_on_zero(self, clean_config):
        self._set_env(timeout=0)

        with pytest.raises(ValueError, match="must be positive"):
            load_configs()

    def test_raises_on_negative(self, clean_config):
        self._set_env(timeout=-1)

        with pytest.raises(ValueError, match="must be positive"):
            load_configs()

    def test_error_names_the_config(self, clean_config):
        self._set_env(timeout=-1, config_id="work")

        with pytest.raises(ValueError, match="Config 'work'"):
            load_configs()
